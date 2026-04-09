"""HyDE (Hypothetical Document Embeddings) query expansion.

Generates a hypothetical answer to a query using a fast LLM,
then embeds that answer instead of the raw query. Improves
retrieval quality for low-resource languages like Latvian.
"""

from __future__ import annotations

import time

from app.core.config import Settings, get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)

_HYDE_SYSTEM_PROMPT = (
    "You are a transit operations knowledge assistant. "
    "Given a question, write a short paragraph that would appear in an "
    "internal document answering it. Write in the same language as the "
    "question. Be specific and factual. Do not include greetings or "
    "meta-commentary - output ONLY the answer paragraph."
)


def _resolve_model(settings: Settings) -> str:
    """Resolve the model string for HyDE expansion.

    Priority: knowledge_hyde_model > llm_fast > primary model.
    """
    if settings.knowledge_hyde_model:
        return settings.knowledge_hyde_model

    if settings.llm_fast_provider and settings.llm_fast_model:
        return f"{settings.llm_fast_provider}:{settings.llm_fast_model}"

    return f"{settings.llm_provider}:{settings.llm_model}"


async def expand_query(query: str, settings: Settings | None = None) -> str:
    """Generate a hypothetical document answering the query.

    Uses a fast/cheap LLM to produce document-like text that embeds
    closer to actual knowledge base documents than the raw query.

    Args:
        query: The user's search query.
        settings: Optional settings override (for testing).

    Returns:
        Hypothetical answer text to embed instead of the raw query.
        Falls back to the original query on any error.
    """
    from pydantic_ai import Agent

    if settings is None:
        settings = get_settings()

    model_str = _resolve_model(settings)
    start = time.monotonic()

    try:
        agent = Agent(
            model_str,
            system_prompt=_HYDE_SYSTEM_PROMPT,
        )
        result = await agent.run(query)
        expanded = str(result.response).strip()

        # Truncate to max_tokens * ~4 chars/token as safety bound
        max_chars = settings.knowledge_hyde_max_tokens * 4
        if len(expanded) > max_chars:
            expanded = expanded[:max_chars]

        elapsed_ms = (time.monotonic() - start) * 1000
        logger.info(
            "knowledge.hyde.expansion_completed",
            query_length=len(query),
            expanded_length=len(expanded),
            model=model_str,
            elapsed_ms=round(elapsed_ms, 1),
        )
        return expanded

    except Exception as e:
        elapsed_ms = (time.monotonic() - start) * 1000
        logger.warning(
            "knowledge.hyde.expansion_failed",
            query_length=len(query),
            error=str(e),
            error_type=type(e).__name__,
            elapsed_ms=round(elapsed_ms, 1),
        )
        # Graceful degradation - fall back to raw query
        return query
