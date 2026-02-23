# pyright: reportUnknownMemberType=false, reportUntypedFunctionDecorator=false
"""Knowledge base REST API endpoints."""

import re
import tempfile
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from fastapi.requests import Request
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.rate_limit import limiter
from app.knowledge.schemas import (
    DocumentContentResponse,
    DocumentResponse,
    DocumentUpdate,
    DocumentUpload,
    DomainListResponse,
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
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": "xlsx",
    "message/rfc822": "email",
    "text/plain": "text",
    "text/markdown": "text",
    "text/csv": "csv",
}


def _detect_source_type(content_type: str | None) -> str:
    """Detect source type from MIME content type.

    Args:
        content_type: MIME type string from upload.

    Returns:
        Source type string (pdf, docx, email, image, text, xlsx, csv).
    """
    if content_type is None:
        return "text"
    if content_type in _CONTENT_TYPE_MAP:
        return _CONTENT_TYPE_MAP[content_type]
    if content_type.startswith("image/"):
        return "image"
    if content_type.startswith("text/"):
        return "text"
    return "unknown"


@router.post("/documents", response_model=DocumentResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit("10/minute")
async def upload_document(
    request: Request,
    file: UploadFile = File(...),  # noqa: B008
    domain: str = Form(...),
    language: str = Form(default="lv"),
    metadata_json: str | None = Form(default=None),
    title: str | None = Form(default=None),
    description: str | None = Form(default=None),
    service: KnowledgeService = Depends(get_service),  # noqa: B008
) -> DocumentResponse:
    """Upload and ingest a document into the knowledge base."""
    _ = request
    upload = DocumentUpload(
        domain=domain,
        language=language,
        metadata_json=metadata_json,
        title=title,
        description=description,
    )
    source_type = _detect_source_type(file.content_type)
    if source_type == "unknown":
        raise HTTPException(
            status_code=415,
            detail=f"Unsupported file type: {file.content_type}. Supported: PDF, DOCX, XLSX, CSV, TXT, images, email.",
        )

    # Sanitize filename: strip path components, limit to basename
    raw_filename = file.filename or "unknown"
    safe_filename = re.sub(r"[^\w\-.]", "_", Path(raw_filename).name.replace("\x00", ""))
    if not safe_filename or safe_filename.startswith("."):
        safe_filename = "upload" + Path(raw_filename).suffix

    # Save to temp file with streaming size limit
    max_upload_size = 50 * 1024 * 1024  # 50MB
    suffix = Path(safe_filename).suffix
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    try:
        size = 0
        while chunk := await file.read(8192):
            size += len(chunk)
            if size > max_upload_size:
                tmp.close()
                Path(tmp.name).unlink(missing_ok=True)
                raise HTTPException(status_code=413, detail="File exceeds 50MB limit")
            tmp.write(chunk)
        tmp.flush()
        tmp.close()

        return await service.ingest_document(
            file_path=tmp.name,
            upload=upload,
            filename=safe_filename,
            source_type=source_type,
            file_size=size,
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


@router.patch("/documents/{document_id}", response_model=DocumentResponse)
@limiter.limit("10/minute")
async def update_document(
    request: Request,
    document_id: int,
    body: DocumentUpdate,
    service: KnowledgeService = Depends(get_service),  # noqa: B008
) -> DocumentResponse:
    """Update document metadata (title, description, domain, language)."""
    _ = request
    return await service.update_document(document_id, body)


@router.get("/documents/{document_id}/download")
@limiter.limit("30/minute")
async def download_document(
    request: Request,
    document_id: int,
    service: KnowledgeService = Depends(get_service),  # noqa: B008
) -> FileResponse:
    """Download the original uploaded file."""
    _ = request
    file_path, filename = await service.get_document_file_path(document_id)
    resolved = Path(file_path).resolve()
    from app.core.config import get_settings

    storage_root = Path(get_settings().document_storage_path).resolve()
    if not resolved.is_relative_to(storage_root):
        from app.knowledge.exceptions import ProcessingError

        raise ProcessingError("File path outside storage directory")
    return FileResponse(
        path=resolved,
        filename=filename,
        media_type="application/octet-stream",
    )


@router.get("/documents/{document_id}/content", response_model=DocumentContentResponse)
@limiter.limit("30/minute")
async def get_document_content(
    request: Request,
    document_id: int,
    service: KnowledgeService = Depends(get_service),  # noqa: B008
) -> DocumentContentResponse:
    """Get extracted text chunks for a document."""
    _ = request
    return await service.get_document_content(document_id)


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


@router.get("/domains", response_model=DomainListResponse)
@limiter.limit("30/minute")
async def list_domains(
    request: Request,
    service: KnowledgeService = Depends(get_service),  # noqa: B008
) -> DomainListResponse:
    """List all unique document domains."""
    _ = request
    return await service.list_domains()


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
