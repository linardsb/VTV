# pyright: reportUnknownMemberType=false, reportMissingTypeStubs=false
"""Text-to-SQL agent tool with Schema RAG (ML-5.4).

Translates natural language questions into validated SELECT statements
using pgvector-retrieved example queries as LLM context.
"""

from __future__ import annotations

import json
import re
import time
from typing import Any

from pydantic_ai import Agent, RunContext
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.agents.tools.transit.deps import UnifiedDeps
from app.core.agents.tools.transit.sql_schemas import AnalyticsSQLResponse, SchemaExample
from app.core.agents.tools.transit.sql_validator import (
    ALLOWED_TABLES,
    check_query_cost,
    validate_sql,
)
from app.core.config import Settings, get_settings
from app.core.logging import get_logger
from app.knowledge.embedding import EmbeddingProvider, get_embedding_provider

logger = get_logger(__name__)

# Module-level lazy singleton for embedding provider
_embedding_provider: EmbeddingProvider | None = None


def _get_embedding() -> EmbeddingProvider:
    """Get or create the embedding provider singleton."""
    global _embedding_provider
    if _embedding_provider is None:
        settings = get_settings()
        provider = get_embedding_provider(settings)
        if settings.embedding_cache_enabled:
            from app.knowledge.embedding import CachedEmbeddingProvider

            provider = CachedEmbeddingProvider(
                provider=provider,
                provider_name=settings.embedding_provider,
                ttl=settings.embedding_cache_ttl,
            )
        _embedding_provider = provider
    return _embedding_provider


async def _embed_question(question: str, settings: Settings) -> list[float]:
    """Embed a natural language question into a vector.

    Args:
        question: The user's question text.
        settings: Application settings (unused, kept for interface consistency).

    Returns:
        Embedding vector as list of floats.
    """
    _ = settings  # kept for interface consistency
    provider = _get_embedding()
    embeddings = await provider.embed([question])
    return embeddings[0]


async def _retrieve_examples(
    db: AsyncSession,
    embedding: list[float],
    k: int,
) -> list[dict[str, Any]]:
    """Retrieve similar schema examples from the database via cosine similarity.

    Args:
        db: Async database session.
        embedding: Query embedding vector.
        k: Number of examples to retrieve.

    Returns:
        List of dicts with question, sql, and similarity fields.
    """
    embedding_str = "[" + ",".join(str(v) for v in embedding) + "]"
    result = await db.execute(
        text(
            "SELECT question_text, sql_query, "
            "1 - (question_embedding <=> :embedding::vector) AS similarity "
            "FROM schema_examples "
            "WHERE question_embedding IS NOT NULL "
            "ORDER BY question_embedding <=> :embedding::vector "
            "LIMIT :k"
        ),
        {"embedding": embedding_str, "k": k},
    )
    rows = result.all()
    return [
        {"question": str(row[0]), "sql": str(row[1]), "similarity": float(row[2])} for row in rows
    ]


_SQL_GENERATION_PROMPT = (
    "You are a PostgreSQL query generator for a transit operations database.\n\n"
    "RULES:\n"
    "- Generate ONLY a single SELECT statement. No explanations, no markdown.\n"
    "- You may ONLY reference these tables: {tables}\n"
    "- Use standard PostgreSQL syntax.\n"
    "- Include appropriate WHERE clauses for date filtering when relevant.\n"
    "- Use aggregate functions (COUNT, AVG, SUM, MIN, MAX) for analytical questions.\n"
    "- Do NOT use subqueries unless absolutely necessary.\n"
    "- Do NOT include LIMIT unless the user asks for a specific number of results.\n\n"
    "EXAMPLE QUERIES (similar questions and their correct SQL):\n"
    "{examples}\n\n"
    "USER QUESTION: {question}\n\n"
    "Generate the SQL SELECT statement:"
)


async def _generate_sql(
    question: str,
    examples: list[dict[str, Any]],
    settings: Settings,
) -> str:
    """Generate SQL from a natural language question using LLM with example context.

    Args:
        question: The user's natural language question.
        examples: Retrieved similar schema examples.
        settings: Application settings for model configuration.

    Returns:
        Generated SQL string.
    """
    examples_text = "\n".join(f"Q: {ex['question']}\nSQL: {ex['sql']}" for ex in examples)
    tables_str = ", ".join(sorted(ALLOWED_TABLES))

    prompt = _SQL_GENERATION_PROMPT.format(
        tables=tables_str,
        examples=examples_text,
        question=question,
    )

    # Use fast model if configured, otherwise primary model
    model_name: str | None = None
    if settings.llm_fast_provider and settings.llm_fast_model:
        model_name = f"{settings.llm_fast_provider}:{settings.llm_fast_model}"
    elif settings.llm_provider != "test":
        model_name = f"{settings.llm_provider}:{settings.llm_model}"

    # Use a separate one-shot agent to avoid recursion with the main agent
    sql_agent: Agent[None, str] = Agent(
        model=model_name or "test",
        output_type=str,
        system_prompt="You are a SQL generator. Return ONLY a valid PostgreSQL SELECT statement.",
    )
    result = await sql_agent.run(prompt)

    # Clean the result: strip markdown code fences if present
    generated = result.output.strip()
    generated = re.sub(r"^```(?:sql)?\s*", "", generated)
    generated = re.sub(r"\s*```$", "", generated)
    return generated.strip()


async def _execute_readonly(
    db: AsyncSession,
    sql: str,
    timeout_ms: int,
    max_rows: int,
) -> tuple[list[dict[str, Any]], list[str]]:
    """Execute a validated SQL query with statement timeout and row limit.

    Args:
        db: Async database session.
        sql: Validated SELECT statement.
        timeout_ms: Statement timeout in milliseconds.
        max_rows: Maximum rows to return.

    Returns:
        Tuple of (rows as list of dicts, column names).
    """
    # SET LOCAL is transaction-scoped
    await db.execute(text(f"SET LOCAL statement_timeout = '{timeout_ms}'"))

    # Append LIMIT if not already present
    sql_upper = sql.upper().strip()
    if "LIMIT" not in sql_upper.split("ORDER BY")[-1] if "ORDER BY" in sql_upper else sql_upper:
        sql = f"{sql} LIMIT {max_rows}"

    result = await db.execute(text(sql))
    columns = list(result.keys())
    raw_rows = result.fetchmany(max_rows)

    rows: list[dict[str, Any]] = []
    for row in raw_rows:
        row_dict: dict[str, Any] = {}
        for i, col in enumerate(columns):
            val = row[i]
            # Convert non-JSON-serializable types to strings
            row_dict[col] = (
                str(val)
                if val is not None and not isinstance(val, (int, float, bool, str))
                else val
            )
        rows.append(row_dict)

    return rows, columns


async def run_analytics_sql(
    ctx: RunContext[UnifiedDeps],
    natural_language_question: str,
) -> str:
    """Generate and execute a SELECT query from a natural language analytics question.

    WHEN TO USE: User asks data questions about transit operations that existing
    tools don't cover - counts, aggregations, trends, comparisons across any
    database table. Examples: "How many buses were late by >10 min on route 22
    yesterday?", "Average delay by route this week", "Driver hours by month".

    WHEN NOT TO USE: For real-time vehicle positions (use query_bus_status),
    scheduled timetables (use get_route_schedule), stop lookups (use search_stops),
    adherence metrics (use get_adherence_report), driver availability
    (use check_driver_availability), documents (use search_knowledge_base),
    or notes (use obsidian_query_vault). Those tools are faster and more reliable
    for their specific domains.

    EFFICIENCY: Retrieves 5 similar example queries via pgvector to constrain
    LLM generation. Results capped at 100 rows. Query cost validated via EXPLAIN
    before execution. Statement timeout 5s. Read-only database role.

    COMPOSITION: Use standalone for analytics. Chain with obsidian_manage_notes
    to save query results as a note. Chain with search_knowledge_base to find
    SOPs related to the metric you're analyzing.

    Args:
        ctx: Pydantic AI run context with UnifiedDeps.
        natural_language_question: The user's analytical question (1-500 chars).

    Returns:
        JSON with query, columns, rows (max 100), execution time, and examples used.
        On error, returns a user-friendly error message string.
    """
    settings = ctx.deps.settings
    start_time = time.monotonic()

    # Guard: feature flag
    if not settings.analytics_sql_enabled:
        return "Analytics SQL is currently disabled. Contact an administrator."

    # Guard: input length
    question = natural_language_question.strip()
    if not question or len(question) > 500:
        return "Question must be 1-500 characters."

    logger.info(
        "agent.analytics_sql.started",
        question_length=len(question),
    )

    try:
        # Phase 1: Embed the question
        embedding = await _embed_question(question, settings)

        # Phase 2: Retrieve similar examples from schema_examples
        db_factory = ctx.deps.db_session_factory
        if db_factory is None:
            return "Database session not available."

        async with db_factory() as db:
            examples = await _retrieve_examples(
                db, embedding, settings.analytics_sql_example_retrieval_k
            )

        if not examples:
            return "No schema examples found. The analytics SQL feature needs seeding first."

        # Phase 3: Generate SQL via LLM
        generated_sql = await _generate_sql(question, examples, settings)

        # Phase 4: Validate SQL (parser whitelist + injection patterns)
        validation = validate_sql(generated_sql)
        if not validation.valid:
            logger.warning(
                "agent.analytics_sql.validation_rejected",
                error=validation.error,
                question_length=len(question),
            )
            return f"Generated query failed safety validation: {validation.error}"

        safe_sql = validation.sanitized_sql or generated_sql

        # Phase 5: Cost gate via EXPLAIN
        async with db_factory() as db:
            passes, cost = await check_query_cost(
                db, safe_sql, settings.analytics_sql_max_query_cost
            )
            if not passes:
                logger.warning(
                    "agent.analytics_sql.cost_exceeded",
                    estimated_cost=cost,
                    max_cost=settings.analytics_sql_max_query_cost,
                )
                return (
                    f"Query too expensive (estimated cost {cost:.0f}, "
                    f"limit {settings.analytics_sql_max_query_cost}). "
                    "Try narrowing your question with date ranges or specific routes."
                )

            # Phase 6: Execute with statement timeout
            exec_start = time.monotonic()
            rows, columns = await _execute_readonly(
                db,
                safe_sql,
                settings.analytics_sql_statement_timeout_ms,
                settings.analytics_sql_max_result_rows,
            )
            exec_ms = int((time.monotonic() - exec_start) * 1000)

        # Phase 7: Build response
        truncated = len(rows) >= settings.analytics_sql_max_result_rows
        response = AnalyticsSQLResponse(
            query=safe_sql,
            columns=columns,
            rows=rows,
            row_count=len(rows),
            execution_time_ms=exec_ms,
            examples_used=[
                SchemaExample(question=e["question"], sql=e["sql"], similarity=e["similarity"])
                for e in examples
            ],
            truncated=truncated,
        )

        duration_ms = int((time.monotonic() - start_time) * 1000)
        logger.info(
            "agent.analytics_sql.completed",
            row_count=len(rows),
            execution_time_ms=exec_ms,
            total_duration_ms=duration_ms,
            query_cost=cost,
            truncated=truncated,
        )

        return json.dumps(response.model_dump(), ensure_ascii=False, default=str)

    except Exception as e:
        duration_ms = int((time.monotonic() - start_time) * 1000)
        logger.error(
            "agent.analytics_sql.failed",
            exc_info=True,
            error=str(e),
            error_type=type(e).__name__,
            duration_ms=duration_ms,
        )
        return f"Analytics query failed: {type(e).__name__}. Please rephrase your question."
