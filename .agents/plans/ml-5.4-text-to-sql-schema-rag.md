# Plan: ML-5.4 Text-to-SQL with Schema RAG

## Context

Dispatchers and analysts ask analytical questions the existing 11 agent tools don't cover ("how many buses were late by > 15 min on route 22 during rain?"). Text-to-SQL with schema RAG scales without endless manual tool additions. Three-layer safety: retrieval-constrained prompting (LLM sees only example SELECTs), sqlparse whitelist, and read-only DB role with statement timeout + query-plan cost gate.

## Security Context Assessment

| Context | Active | Rationale |
|---------|--------|-----------|
| CTX-AGENT | **Yes** | New agent tool generates SQL from user input via LLM |
| CTX-INPUT | **Yes** | Natural language → SQL generation = injection surface |
| CTX-RBAC | No | Tool runs within existing chat endpoint (already auth'd + rate-limited) |
| CTX-AUTH | No | No new auth flows |
| CTX-FILE | No | No file handling |
| CTX-INFRA | Partial | New DB role in migration; new dependency `sqlparse` |

**CTX-AGENT requirements:**
- LLM prompt constrained by retrieved examples only — never sees raw schema DDL
- Tool output sanitized: column values truncated, no credential columns exposed
- Tool is read-only by design (SELECT-only parser + read-only DB role)

**CTX-INPUT requirements:**
- Three-layer SQL injection defense: (1) sqlparse whitelist rejects non-SELECT, (2) keyword blocklist catches obfuscated DDL/DML, (3) read-only DB role as defense-in-depth
- Input length limit: `natural_language_question` capped at 500 chars
- EXPLAIN cost gate prevents resource exhaustion (DoS via CROSS JOIN)

## Research Summary

### Reference files
| File | Purpose |
|------|---------|
| `app/core/agents/tools/knowledge/search_knowledge.py:56-223` | **Primary template** — 5-principle docstring, RunContext pattern, JSON response, structured logging |
| `app/core/agents/agent.py:125-147` | Tool registration in `create_agent()` tools list |
| `app/core/agents/tools/transit/deps.py:20-38` | `UnifiedDeps` dataclass — `db_session_factory` for standalone sessions |
| `app/knowledge/embedding.py:44-96` | `OpenAIEmbeddingProvider.embed()` — batched embedding, 1024-dim |
| `app/memory/service.py:31-46` | `_get_embedding()` singleton with cache — reuse this pattern |
| `app/knowledge/repository.py:324-358` | `.cosine_distance()` vector search pattern with SQLAlchemy |
| `app/core/config.py:290-344` | Settings pattern for feature flags and thresholds |
| `app/core/database.py:46-59` | `get_db_context()` standalone async session for agent tools |
| `alembic/versions/9d9e77b5b0bf_create_memory_entries.py:23-60` | pgvector migration reference (VECTOR(1024), IVFFlat index) |

### Dependencies
- `sqlparse` — **NOT** in `pyproject.toml` yet, must be added
- `pgvector` — already available (used by knowledge + memory)
- Two alembic heads exist (`i2j3k4l5m6n7`, `k4l5m6n7o8p9`) — must merge before new migration

## Test Landscape

### Existing fixtures (from `app/core/agents/tests/conftest.py`)
- `make_agent_result()` — factory with defaults
- `make_skill_meta()` — skill metadata factory
- `_reset_provider_breakers` — **autouse**, clears AI-8.3 breaker registry
- `_reset_skill_cache` — **autouse**, clears module cache

### Mock patterns
- `MagicMock()` for `ctx` with `ctx.deps.settings`, `ctx.deps.db_session_factory`
- `AsyncMock()` for `session.execute()` returning `MagicMock` with `.all()`/`.scalar()`
- `pydantic_ai.models.ALLOW_MODEL_REQUESTS = False` safety gate in test modules
- `patch("app.core.agents.tools.knowledge.search_knowledge.AsyncSessionLocal")` for DB mocking

### Security test patterns
- `app/core/agents/tests/test_injection_detector.py` — pattern-based detection with confidence scoring
- `app/tests/test_security.py` — convention tests with `inspect.getsource()` assertions
- Injection attempts: stacked queries, comment obfuscation, UNION, encoded chars

## Type Check Baseline

| Target | Pyright | Mypy |
|--------|---------|------|
| `app/core/agents/` | **0 errors** | **0 errors** (107 sources) |
| `app/knowledge/` | **0 errors** | **0 errors** (43 sources) |

New code must maintain zero errors on both.

## Files to Create/Modify

| # | Action | File | Purpose |
|---|--------|------|---------|
| 1 | UPDATE | `pyproject.toml` | Add `sqlparse` + `types-sqlparse` dependencies |
| 2 | CREATE | `alembic/versions/xxxx_merge_heads.py` | Merge two divergent alembic heads |
| 3 | CREATE | `alembic/versions/xxxx_create_schema_examples.py` | `schema_examples` table + pgvector index + `vtv_analytics_readonly` DB role |
| 4 | UPDATE | `app/core/config.py` | Add ML-5.4 settings (6 fields) |
| 5 | CREATE | `app/core/agents/tools/transit/sql_validator.py` | SQL whitelist validation + EXPLAIN cost gate |
| 6 | CREATE | `app/core/agents/tools/transit/sql_schemas.py` | Pydantic response schemas for SQL results |
| 7 | CREATE | `app/core/agents/tools/transit/run_analytics_sql.py` | Main tool: embed → retrieve → generate → validate → execute → return |
| 8 | UPDATE | `app/core/agents/agent.py:130` | Register `run_analytics_sql` in tools list |
| 9 | CREATE | `data/schema_examples.yaml` | 50 curated example question→SQL pairs for seeding |
| 10 | CREATE | `scripts/seed_schema_examples.py` | Idempotent seed script — YAML → embed → upsert into `schema_examples` |
| 11 | CREATE | `app/core/agents/tools/transit/tests/test_sql_validator.py` | Validator unit tests (15 tests) |
| 12 | CREATE | `app/core/agents/tools/transit/tests/test_run_analytics_sql.py` | Tool function tests (15 tests) |
| 13 | UPDATE | `Makefile` | Add `make seed-schema-examples` target |

## Implementation Steps

### Step 1: Add `sqlparse` dependency

**File:** `pyproject.toml`
**Action:** Add `sqlparse>=0.5.0` to `[project] dependencies` and `types-sqlparse` to dev dependencies (if available, otherwise add mypy override).

**Validation:** `uv sync && uv run python -c "import sqlparse; print(sqlparse.__version__)"`

### Step 2: Add mypy/pyright overrides for sqlparse

**File:** `pyproject.toml`
**Action:** Add `[[tool.mypy.overrides]]` for sqlparse with `ignore_missing_imports = true` if no type stubs available.

**Validation:** `uv run mypy app/core/agents/ --no-error-summary 2>&1 | tail -5`

### Step 3: Merge alembic heads

**File:** `alembic/versions/xxxx_merge_heads.py`
**Action:** Run `uv run alembic merge heads -m "merge_divergent_heads"` to create merge migration.

**Validation:** `uv run alembic heads` → single head

### Step 4: Create `schema_examples` migration

**File:** `alembic/versions/xxxx_create_schema_examples.py`
**Action:** CREATE table with columns:

```python
op.create_table(
    "schema_examples",
    sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
    sa.Column("question_text", sa.Text(), nullable=False),
    sa.Column("question_embedding", pgvector.sqlalchemy.vector.VECTOR(dim=1024), nullable=True),
    sa.Column("sql_query", sa.Text(), nullable=False),
    sa.Column("description", sa.Text(), nullable=True),
    sa.Column("validated_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column("tags", postgresql.ARRAY(sa.Text()), nullable=True),
    sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
)
op.execute(
    "CREATE INDEX ix_schema_examples_embedding ON schema_examples "
    "USING ivfflat (question_embedding vector_cosine_ops) WITH (lists = 50)"
)
```

Also create read-only DB role (defense-in-depth):
```sql
DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'vtv_analytics_readonly') THEN
        CREATE ROLE vtv_analytics_readonly NOLOGIN;
    END IF;
END
$$;
GRANT USAGE ON SCHEMA public TO vtv_analytics_readonly;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO vtv_analytics_readonly;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO vtv_analytics_readonly;
```

Downgrade: `DROP TABLE schema_examples; DROP ROLE IF EXISTS vtv_analytics_readonly;`

**Validation:** `uv run alembic upgrade head` (requires Docker DB running)

### Step 5: Add ML-5.4 settings to config

**File:** `app/core/config.py` (insert after line ~343, before `@model_validator`)
**Action:** Add settings block:

```python
# Text-to-SQL with Schema RAG (ML-5.4)
analytics_sql_enabled: bool = False  # Off by default for safe rollout
analytics_sql_statement_timeout_ms: int = 5000  # 5 seconds
analytics_sql_max_query_cost: int = 10000  # EXPLAIN Total Cost threshold
analytics_sql_max_result_rows: int = 100
analytics_sql_example_retrieval_k: int = 5  # Number of similar examples to retrieve
analytics_sql_readonly_dsn: str | None = None  # Separate DSN for read-only role; falls back to DATABASE_URL
```

**Validation:** `uv run pyright app/core/config.py && uv run mypy app/core/config.py`

### Step 6: Create SQL validator module

**File:** `app/core/agents/tools/transit/sql_validator.py`
**Action:** CREATE with two public functions:

```python
"""SQL validation for text-to-sql agent tool (ML-5.4).

Three-layer defense: sqlparse whitelist, keyword blocklist, EXPLAIN cost gate.
"""
import json
import re
from dataclasses import dataclass

import sqlparse
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger

logger = get_logger(__name__)


# Tables the LLM is allowed to reference
ALLOWED_TABLES: frozenset[str] = frozenset({
    "vehicles", "vehicle_positions", "routes", "trips", "stops",
    "stop_times", "drivers", "schedules", "calendar", "calendar_dates",
    "shapes", "agencies", "feed_info", "fleet_devices", "geofences",
    "geofence_events", "alerts", "alert_rules", "events",
    "documents", "document_chunks", "weather_observations",
    "traffic_counts",
})

# Keywords that MUST NOT appear in generated SQL (case-insensitive)
_BLOCKED_KEYWORDS: frozenset[str] = frozenset({
    "INSERT", "UPDATE", "DELETE", "DROP", "CREATE", "ALTER", "TRUNCATE",
    "GRANT", "REVOKE", "COPY", "EXECUTE", "CALL", "DO",
    "SET", "RESET", "LOAD", "VACUUM", "CLUSTER", "REINDEX",
    "COMMENT", "SECURITY", "OWNER",
})

# Patterns that indicate injection attempts
_INJECTION_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r";\s*\w", re.IGNORECASE),           # Stacked queries
    re.compile(r"--\s*$", re.MULTILINE),             # Line comments at end
    re.compile(r"/\*.*?\*/", re.DOTALL),             # Block comments
    re.compile(r"\\x[0-9a-f]{2}", re.IGNORECASE),   # Hex-encoded chars
    re.compile(r"chr\s*\(", re.IGNORECASE),          # CHR() function
    re.compile(r"pg_\w+", re.IGNORECASE),            # System catalog access
    re.compile(r"information_schema", re.IGNORECASE), # Schema introspection
]


@dataclass(frozen=True)
class ValidationResult:
    """Result of SQL validation."""
    valid: bool
    error: str | None = None
    sanitized_sql: str | None = None


def validate_sql(sql: str) -> ValidationResult:
    """Validate SQL is a safe, read-only SELECT statement.

    Three checks:
    1. sqlparse parse → must be exactly one SELECT statement
    2. Keyword blocklist → no DDL/DML tokens
    3. Injection pattern scan → no stacked queries, comments, hex encoding

    Args:
        sql: The SQL string to validate.

    Returns:
        ValidationResult with valid=True and sanitized SQL, or valid=False with error.
    """
    ...


async def check_query_cost(
    db: AsyncSession,
    sql: str,
    max_cost: int,
) -> tuple[bool, float]:
    """Run EXPLAIN to estimate query cost.

    Args:
        db: Async database session.
        sql: Validated SELECT statement.
        max_cost: Maximum allowed Total Cost from EXPLAIN.

    Returns:
        Tuple of (passes_cost_gate, estimated_cost).

    Raises:
        ValueError: If EXPLAIN fails to parse.
    """
    ...
```

Implementation notes:
- `validate_sql()`: Use `sqlparse.parse()`, check `len(statements) == 1`, check `statements[0].get_type() == "SELECT"`, flatten tokens and check against `_BLOCKED_KEYWORDS`, scan with `_INJECTION_PATTERNS`
- `check_query_cost()`: Execute `EXPLAIN (FORMAT JSON) {sql}` via `text()`, parse JSON, extract `[0]["Plan"]["Total Cost"]`
- Log: `agent.analytics_sql.validation_failed` / `agent.analytics_sql.cost_exceeded`

**Validation:** `uv run ruff format app/core/agents/tools/transit/sql_validator.py && uv run ruff check --fix app/core/agents/tools/transit/sql_validator.py && uv run pyright app/core/agents/tools/transit/sql_validator.py`

### Step 7: Create response schemas

**File:** `app/core/agents/tools/transit/sql_schemas.py`
**Action:** CREATE (add to existing `schemas.py` or new file — prefer new file for clarity):

```python
"""Response schemas for text-to-sql agent tool (ML-5.4)."""
from typing import Any
from pydantic import BaseModel, Field


class SchemaExample(BaseModel):
    """A retrieved example query used to guide SQL generation."""
    question: str
    sql: str
    similarity: float = Field(ge=0.0, le=1.0)


class AnalyticsSQLResponse(BaseModel):
    """Response from run_analytics_sql tool."""
    query: str = Field(description="The generated and executed SQL query")
    columns: list[str] = Field(description="Column names in result set")
    rows: list[dict[str, Any]] = Field(description="Result rows (max 100)")  # noqa: ANN401
    row_count: int = Field(ge=0, description="Number of rows returned")
    execution_time_ms: int = Field(ge=0)
    examples_used: list[SchemaExample] = Field(description="Retrieved schema examples that guided generation")
    truncated: bool = Field(default=False, description="True if results were truncated at max_result_rows")
```

**Validation:** `uv run pyright app/core/agents/tools/transit/sql_schemas.py`

### Step 8: Create the main tool function

**File:** `app/core/agents/tools/transit/run_analytics_sql.py`
**Action:** CREATE following `search_knowledge.py` template:

```python
"""Text-to-SQL agent tool with Schema RAG (ML-5.4).

Translates natural language questions into validated SELECT statements
using pgvector-retrieved example queries as LLM context.
"""
from __future__ import annotations

import json
import time
from typing import Any

from pydantic_ai import RunContext
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.agents.tools.transit.deps import UnifiedDeps
from app.core.agents.tools.transit.sql_schemas import AnalyticsSQLResponse, SchemaExample
from app.core.agents.tools.transit.sql_validator import (
    ALLOWED_TABLES,
    ValidationResult,
    check_query_cost,
    validate_sql,
)
from app.core.logging import get_logger

logger = get_logger(__name__)


async def run_analytics_sql(
    ctx: RunContext[UnifiedDeps],
    natural_language_question: str,
) -> str:
    """Generate and execute a SELECT query from a natural language analytics question.

    WHEN TO USE: User asks data questions about transit operations that existing
    tools don't cover — counts, aggregations, trends, comparisons across any
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
    _ = ctx.deps.settings  # Reference deps to satisfy ARG001
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
            examples = await _retrieve_examples(db, embedding, settings.analytics_sql_example_retrieval_k)

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
            passes, cost = await check_query_cost(db, safe_sql, settings.analytics_sql_max_query_cost)
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
                db, safe_sql, settings.analytics_sql_statement_timeout_ms,
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
```

**Private helpers** (in same file):
- `_embed_question(question, settings)` — reuse `_get_embedding()` from memory service pattern
- `_retrieve_examples(db, embedding, k)` — `SELECT question_text, sql_query FROM schema_examples ORDER BY question_embedding <=> $1 LIMIT k`
- `_generate_sql(question, examples, settings)` — build constrained prompt with example queries + `ALLOWED_TABLES` list, call LLM via `pydantic_ai.Agent` one-shot
- `_execute_readonly(db, sql, timeout_ms, max_rows)` — `SET LOCAL statement_timeout = {timeout_ms}; {sql} LIMIT {max_rows}`

**Key implementation details:**
- `_generate_sql` uses a **separate one-shot Agent** (not the main unified agent) to avoid recursion. Model: `settings.llm_fast_model` (cheapest). System prompt constrains to SELECT-only with the allowed tables list.
- `_execute_readonly` uses `SET LOCAL statement_timeout` (transaction-scoped, not session) and appends `LIMIT {max_rows}` if not already present
- Result dict values converted via `str()` for JSON serialization safety (datetime, Decimal, etc.)

**Validation:** `uv run ruff format && uv run ruff check --fix && uv run pyright app/core/agents/tools/transit/run_analytics_sql.py`

### Step 9: Register tool in agent

**File:** `app/core/agents/agent.py:130-146`
**Action:** Add `run_analytics_sql` to the tools list:

```python
from app.core.agents.tools.transit.run_analytics_sql import run_analytics_sql

tools=[
    # Transit (5 read-only + 1 analytics)
    query_bus_status,
    get_route_schedule,
    search_stops,
    get_adherence_report,
    check_driver_availability,
    run_analytics_sql,  # ML-5.4: text-to-SQL with schema RAG
    # Obsidian vault (4)
    ...
```

Also update SYSTEM_PROMPT to mention the new tool's purpose (1-2 sentences in the tool overview section).

**Validation:** `uv run pyright app/core/agents/agent.py && uv run mypy app/core/agents/agent.py`

### Step 10: Create seed data YAML

**File:** `data/schema_examples.yaml`
**Action:** CREATE with 50 curated example pairs. Structure:

```yaml
# Schema examples for ML-5.4 Text-to-SQL with Schema RAG
# Each entry: question (natural language) + sql (validated SELECT)
# Run: make seed-schema-examples
examples:
  - question: "How many vehicles are currently active?"
    sql: "SELECT COUNT(*) AS active_count FROM vehicles WHERE is_active = true"
    description: "Simple count with boolean filter"
    tags: ["vehicles", "count"]

  - question: "What is the average delay per route today?"
    sql: >
      SELECT r.route_short_name, AVG(vp.delay) AS avg_delay_seconds
      FROM vehicle_positions vp
      JOIN trips t ON vp.trip_id = t.trip_id
      JOIN routes r ON t.route_id = r.route_id
      WHERE vp.timestamp >= CURRENT_DATE
      GROUP BY r.route_short_name
      ORDER BY avg_delay_seconds DESC
    description: "Aggregation with join and date filter"
    tags: ["routes", "delays", "aggregation"]
  # ... 48 more examples covering:
  # - Vehicle counts and status queries (5)
  # - Route performance and delays (10)
  # - Driver hours and availability (5)
  # - Stop usage and proximity (5)
  # - Schedule adherence (5)
  # - Fleet telemetry aggregations (5)
  # - Geofence events (5)
  # - Time-series patterns (5)
  # - Multi-table joins (5)
```

**Validation:** `python -c "import yaml; yaml.safe_load(open('data/schema_examples.yaml'))"`

### Step 11: Create seed script

**File:** `scripts/seed_schema_examples.py`
**Action:** CREATE idempotent seed script:

```python
"""Seed schema_examples table from YAML file (ML-5.4).

Usage: uv run python scripts/seed_schema_examples.py [--file data/schema_examples.yaml]
Idempotent: upserts by question_text.
"""
```

- Load YAML, iterate examples
- For each: embed `question_text` via embedding provider
- Upsert into `schema_examples` (ON CONFLICT on question_text)
- Report: inserted N, updated M, total K

**Validation:** `uv run python scripts/seed_schema_examples.py --dry-run`

### Step 12: Create validator tests

**File:** `app/core/agents/tools/transit/tests/test_sql_validator.py`
**Action:** CREATE with ~15 tests:

```python
"""Tests for SQL validator (ML-5.4).

Covers: SELECT whitelist, DDL/DML rejection, injection pattern detection,
stacked queries, comment obfuscation, UNION injection, hex encoding,
system catalog access, role escalation, CROSS JOIN DoS.
"""
```

**Test cases:**
1. `test_valid_simple_select` — basic SELECT passes
2. `test_valid_select_with_joins` — multi-table JOIN passes
3. `test_valid_select_with_aggregation` — GROUP BY/HAVING passes
4. `test_reject_insert` — INSERT INTO rejected
5. `test_reject_update` — UPDATE rejected
6. `test_reject_delete` — DELETE FROM rejected
7. `test_reject_drop_table` — DROP TABLE rejected
8. `test_reject_stacked_queries` — `SELECT 1; DROP TABLE x` rejected
9. `test_reject_comment_obfuscation` — `SELECT/**/1` or `--` variants rejected
10. `test_reject_union_injection` — `UNION SELECT password FROM users` rejected
11. `test_reject_hex_encoding` — `\x44\x52\x4f\x50` rejected
12. `test_reject_pg_catalog_access` — `pg_shadow`, `pg_roles` rejected
13. `test_reject_information_schema` — `information_schema.tables` rejected
14. `test_reject_grant_escalation` — `GRANT ALL` rejected
15. `test_reject_copy_exfiltration` — `COPY TO` rejected
16. `test_check_query_cost_passes` — cost below threshold passes
17. `test_check_query_cost_exceeds` — cost above threshold rejected
18. `test_check_query_cost_explain_failure` — EXPLAIN parse error handled

**Validation:** `uv run pytest app/core/agents/tools/transit/tests/test_sql_validator.py -v`

### Step 13: Create tool function tests

**File:** `app/core/agents/tools/transit/tests/test_run_analytics_sql.py`
**Action:** CREATE with ~15 tests:

```python
"""Tests for run_analytics_sql agent tool (ML-5.4).

Covers: embedding, retrieval, SQL generation, validation gate,
cost gate, execution, result truncation, feature flag, input validation.
"""
from pydantic_ai import models
models.ALLOW_MODEL_REQUESTS = False
```

**Test cases:**
1. `test_feature_flag_disabled` — returns disabled message
2. `test_empty_question_rejected` — empty string rejected
3. `test_question_too_long_rejected` — >500 chars rejected
4. `test_no_db_session_factory` — returns error message
5. `test_no_examples_found` — returns needs-seeding message
6. `test_validation_rejects_unsafe_sql` — validator rejection passes through
7. `test_cost_gate_rejects_expensive` — cost exceeded message returned
8. `test_successful_query_execution` — full happy path with mocked DB
9. `test_result_truncation_at_max_rows` — truncated=True when rows >= max
10. `test_result_json_serialization` — response JSON is valid and complete
11. `test_statement_timeout_set` — `SET LOCAL statement_timeout` is called
12. `test_exception_handling` — unexpected error returns friendly message
13. `test_logging_events` — started/completed/failed log events emitted
14. `test_examples_used_in_response` — retrieved examples included in response
15. `test_datetime_values_serialized` — datetime/Decimal in results → str

**Mock strategy:**
- Patch `_embed_question` → return `[0.1] * 1024`
- Patch `_retrieve_examples` → return 5 fake examples
- Patch `_generate_sql` → return a known SELECT
- Patch `validate_sql` → return `ValidationResult(valid=True, sanitized_sql=...)`
- Patch `check_query_cost` → return `(True, 500.0)`
- Mock `db.execute()` → return mock result with `.keys()` and `.all()`

**Validation:** `uv run pytest app/core/agents/tools/transit/tests/test_run_analytics_sql.py -v`

### Step 14: Add Makefile targets

**File:** `Makefile`
**Action:** Add targets:

```makefile
seed-schema-examples:  ## Seed schema_examples table from YAML (ML-5.4)
	uv run python scripts/seed_schema_examples.py --file data/schema_examples.yaml
```

**Validation:** `make help | grep seed`

## Preflight Warnings

- **Two alembic heads** — must merge FIRST (Step 3) before creating new migration
- **sqlparse has no official type stubs** — will need mypy `ignore_missing_imports` override. Check if `types-sqlparse` exists on PyPI first; if not, add `[[tool.mypy.overrides]]` for sqlparse + pyright file-level directives
- **LLM call inside a tool** — `_generate_sql()` creates a separate one-shot Agent to avoid recursion. Must use `pydantic_ai.models.ALLOW_MODEL_REQUESTS = False` in tests and mock the inner agent
- **`SET LOCAL statement_timeout`** — only works inside a transaction. Ensure `db.begin()` is active before executing. `get_db_context()` sessions are auto-transactional

## Security Checklist

### SQL Injection Defense (3 layers)
- [ ] **Layer 1 — sqlparse whitelist**: Parse with `sqlparse`, reject non-SELECT, check `get_type()`
- [ ] **Layer 2 — keyword blocklist**: Flatten tokens, check against 20+ blocked keywords (DDL/DML/DCL)
- [ ] **Layer 3 — read-only DB role**: `vtv_analytics_readonly` with SELECT-only grants; statement timeout 5s
- [ ] **Injection patterns**: Detect stacked queries (`;`), comments (`--`, `/* */`), hex encoding, `CHR()`, system catalog access (`pg_*`, `information_schema`)

### Agent Tool Safety
- [ ] Feature flag `analytics_sql_enabled` (default False) — admin enables after seeding
- [ ] Input length capped at 500 chars
- [ ] Result rows capped at `analytics_sql_max_result_rows` (100)
- [ ] EXPLAIN cost gate prevents DoS via expensive queries (CROSS JOIN, full scans)
- [ ] No credentials/internal column names exposed in error messages
- [ ] Structured logging never includes raw SQL or raw question (only lengths, hashes, costs)

### Prompt Constraint
- [ ] LLM system prompt includes only: example queries + allowed table names
- [ ] LLM never sees raw DDL, column types, or constraint definitions
- [ ] LLM instructed: "Generate ONLY a single SELECT statement. No explanations."

## Verification

- [ ] `uv run ruff format app/core/agents/tools/transit/ && uv run ruff check app/core/agents/tools/transit/` — clean
- [ ] `uv run pyright app/core/agents/` — 0 errors (matches baseline)
- [ ] `uv run mypy app/core/agents/` — 0 errors (matches baseline)
- [ ] `uv run pytest app/core/agents/tools/transit/tests/test_sql_validator.py -v` — all pass
- [ ] `uv run pytest app/core/agents/tools/transit/tests/test_run_analytics_sql.py -v` — all pass
- [ ] `uv run pytest app/core/agents/ -v` — 490+ existing tests still pass
- [ ] `make check` passes (lint + types + full test suite)
- [ ] `make security-audit-quick` passes

## Anti-Pattern Reminders

From `python-anti-patterns.md`, most relevant to this feature:
- **#1**: No `assert` in production code — use `if not x: return error_msg`
- **#5**: No unused imports — only import what's used
- **#9**: `ctx` param must be referenced — `_ = ctx.deps.settings` or use it
- **#12**: Untyped lib decorators (sqlparse) — add mypy override + pyright directives
- **#18**: ARG001 on unused params — add `_ = param_name`
- **#33**: `dict[str, object]` fails Pydantic `**kwargs` — use `dict[str, Any]`
- **#34**: Redis async stubs — add type ignores on await lines if using Redis
- **#37**: Bare `except: pass` — always log in except blocks
- **#41**: ILIKE params must escape wildcards — use `escape_like()` if any LIKE queries
