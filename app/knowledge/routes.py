# pyright: reportUnknownMemberType=false, reportUntypedFunctionDecorator=false
"""Knowledge base REST API endpoints."""

import tempfile
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile, status
from fastapi.requests import Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.rate_limit import limiter
from app.knowledge.schemas import (
    DocumentResponse,
    DocumentUpload,
    SearchRequest,
    SearchResponse,
)
from app.knowledge.service import KnowledgeService
from app.shared.schemas import PaginatedResponse, PaginationParams

router = APIRouter(prefix="/api/v1/knowledge", tags=["knowledge"])


def get_service(db: AsyncSession = Depends(get_db)) -> KnowledgeService:  # noqa: B008
    """Dependency to create KnowledgeService with request-scoped session."""
    return KnowledgeService(db)


_CONTENT_TYPE_MAP: dict[str, str] = {
    "application/pdf": "pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "docx",
    "message/rfc822": "email",
    "text/plain": "text",
    "text/markdown": "text",
    "text/csv": "text",
}


def _detect_source_type(content_type: str | None) -> str:
    """Detect source type from MIME content type.

    Args:
        content_type: MIME type string from upload.

    Returns:
        Source type string (pdf, docx, email, image, text).
    """
    if content_type is None:
        return "text"
    if content_type in _CONTENT_TYPE_MAP:
        return _CONTENT_TYPE_MAP[content_type]
    if content_type.startswith("image/"):
        return "image"
    if content_type.startswith("text/"):
        return "text"
    return "text"


@router.post("/documents", response_model=DocumentResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit("10/minute")
async def upload_document(
    request: Request,
    file: UploadFile = File(...),  # noqa: B008
    domain: str = Form(...),
    language: str = Form(default="lv"),
    metadata_json: str | None = Form(default=None),
    service: KnowledgeService = Depends(get_service),  # noqa: B008
) -> DocumentResponse:
    """Upload and ingest a document into the knowledge base."""
    _ = request
    upload = DocumentUpload(domain=domain, language=language, metadata_json=metadata_json)
    source_type = _detect_source_type(file.content_type)

    # Save to temp file
    suffix = Path(file.filename or "upload").suffix
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    try:
        content = await file.read()
        tmp.write(content)
        tmp.flush()
        tmp.close()

        return await service.ingest_document(
            file_path=tmp.name,
            upload=upload,
            filename=file.filename or "unknown",
            source_type=source_type,
            file_size=len(content),
        )
    finally:
        Path(tmp.name).unlink(missing_ok=True)


@router.get("/documents", response_model=PaginatedResponse[DocumentResponse])
@limiter.limit("30/minute")
async def list_documents(
    request: Request,
    pagination: PaginationParams = Depends(),  # noqa: B008
    domain: str | None = Query(None, max_length=50),
    document_status: str | None = Query(None, alias="status", max_length=20),
    service: KnowledgeService = Depends(get_service),  # noqa: B008
) -> PaginatedResponse[DocumentResponse]:
    """List documents with pagination and optional filtering."""
    _ = request
    return await service.list_documents(pagination, domain=domain, status=document_status)


@router.get("/documents/{document_id}", response_model=DocumentResponse)
@limiter.limit("30/minute")
async def get_document(
    request: Request,
    document_id: int,
    service: KnowledgeService = Depends(get_service),  # noqa: B008
) -> DocumentResponse:
    """Get a document by its database ID."""
    _ = request
    return await service.get_document(document_id)


@router.delete("/documents/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit("10/minute")
async def delete_document(
    request: Request,
    document_id: int,
    service: KnowledgeService = Depends(get_service),  # noqa: B008
) -> None:
    """Delete a document and its chunks."""
    _ = request
    await service.delete_document(document_id)


@router.post("/search", response_model=SearchResponse)
@limiter.limit("30/minute")
async def search_knowledge(
    request: Request,
    body: SearchRequest,
    service: KnowledgeService = Depends(get_service),  # noqa: B008
) -> SearchResponse:
    """Search the knowledge base with hybrid vector + fulltext search."""
    _ = request
    return await service.search(body)
