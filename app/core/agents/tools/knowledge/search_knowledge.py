"""Agent tool for searching the organizational knowledge base.

Provides RAG-powered search over uploaded documents (PDFs, Word docs,
emails, images, text) using hybrid vector + fulltext search with reranking.
"""

from __future__ import annotations

import json
import time

from pydantic_ai import RunContext

from app.core.agents.tools.knowledge.schemas import (
    KnowledgeSearchResponse,
    KnowledgeSearchResult,
)
from app.core.agents.tools.transit.deps import UnifiedDeps
from app.core.database import AsyncSessionLocal
from app.core.logging import get_logger
from app.knowledge.schemas import SearchRequest
from app.knowledge.service import KnowledgeService

logger = get_logger(__name__)

_MAX_CONTENT_CHARS = 500


async def search_knowledge_base(
    ctx: RunContext[UnifiedDeps],
    query: str,
    domain: str | None = None,
    language: str | None = None,
    limit: int = 5,
) -> str:
    """Search organizational documents for policies, procedures, and records.

    WHEN TO USE: User asks about organizational policies, compliance rules,
    driver records, internal communications, legal documents, or any question
    that requires searching uploaded organizational knowledge. Examples:
    "What is the overtime policy?", "Find driver safety guidelines",
    "What does the compliance manual say about X?"

    WHEN NOT TO USE: For real-time transit data (use query_bus_status),
    route schedules (use get_route_schedule), stop locations (use search_stops),
    or Obsidian vault notes (use obsidian_query_vault). This tool searches
    uploaded documents, not live transit feeds or personal notes.

    EFFICIENCY: Keep limit low (3-5) for focused answers. Use domain filter
    ("transit", "hr", "legal", "compliance") when the category is clear.
    Use language filter ("lv" or "en") if the user specifies a language.

    COMPOSITION: Use standalone for document questions. Chain with
    obsidian_manage_notes to save findings. If the answer references
    a driver, chain with check_driver_availability for current status.

    Args:
        ctx: Pydantic AI run context with UnifiedDeps.
        query: Natural language search query (1-1000 chars).
        domain: Optional domain filter (e.g., "transit", "hr", "legal").
        language: Optional language filter ("lv" or "en").
        limit: Maximum results to return (1-20, default 5).

    Returns:
        JSON string with search results including document_id for citation links.
        Each result has document_id - use it to link: [title](/{locale}/documents/{id}).
    """
    _settings = ctx.deps.settings
    start_time = time.monotonic()

    logger.info(
        "agent.knowledge.search_started",
        query_length=len(query),
        domain=domain,
        language=language,
        limit=limit,
        embedding_provider=_settings.embedding_provider,
    )

    # Validate
    if not query or not query.strip():
        return "Error: query cannot be empty. Provide a search term."

    effective_limit = min(max(limit, 1), 20)

    try:
        async with AsyncSessionLocal() as db:
            service = KnowledgeService(db)
            response = await service.search(
                SearchRequest(
                    query=query,
                    domain=domain,
                    language=language,
                    limit=effective_limit,
                )
            )

        # Map to agent-optimized schema (truncate content for token efficiency)
        results = [
            KnowledgeSearchResult(
                document_id=r.document_id,
                content=r.chunk_content[:_MAX_CONTENT_CHARS],
                source=r.document_filename,
                domain=r.domain,
                relevance_score=round(r.score, 4),
                page_or_section=f"chunk {r.chunk_index}",
            )
            for r in response.results
        ]

        result = KnowledgeSearchResponse(
            results=results,
            total_found=response.total_candidates,
            query=query,
        )

        duration_ms = int((time.monotonic() - start_time) * 1000)
        logger.info(
            "agent.knowledge.search_completed",
            result_count=len(results),
            total_found=response.total_candidates,
            duration_ms=duration_ms,
        )

        return json.dumps(result.model_dump(), ensure_ascii=False)

    except Exception as e:
        duration_ms = int((time.monotonic() - start_time) * 1000)
        logger.error(
            "agent.knowledge.search_failed",
            exc_info=True,
            error=str(e),
            error_type=type(e).__name__,
            duration_ms=duration_ms,
        )
        return (
            f"Knowledge base search error: {e}. "
            "The knowledge base may not have any documents yet, "
            "or the database connection failed. "
            "Try again or check if documents have been uploaded."
        )
