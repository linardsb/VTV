"""Response schemas for the knowledge base agent tool."""

from pydantic import BaseModel


class KnowledgeSearchResult(BaseModel):
    """Single search result for agent consumption."""

    content: str
    source: str
    domain: str
    relevance_score: float
    page_or_section: str | None = None


class KnowledgeSearchResponse(BaseModel):
    """Search response optimized for agent token efficiency."""

    results: list[KnowledgeSearchResult]
    total_found: int
    query: str
