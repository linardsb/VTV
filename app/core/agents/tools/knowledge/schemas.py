"""Response schemas for the knowledge base agent tool."""

from pydantic import BaseModel


class KnowledgeSearchResult(BaseModel):
    """Single search result for agent consumption."""

    document_id: int
    content: str
    source: str
    domain: str
    relevance_score: float
    page_or_section: str | None = None
    parent_content: str | None = None
    heading_path: str | None = None
    citation_anchor: str | None = None
    url_fragment: str | None = None


class KnowledgeSearchResponse(BaseModel):
    """Search response optimized for agent token efficiency."""

    results: list[KnowledgeSearchResult]
    total_found: int
    query: str
