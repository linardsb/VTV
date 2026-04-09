# pyright: reportUnknownMemberType=false, reportUntypedFunctionDecorator=false
"""REST endpoints for agent memory management."""

from typing import Literal

from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import require_role
from app.auth.models import User
from app.core.database import get_db
from app.core.rate_limit import limiter
from app.memory.schemas import (
    CompactionResult,
    MemoryEntryCreate,
    MemoryEntryResponse,
    MemoryRecallByQueryRequest,
    MemoryRecallRequest,
    MemoryRecallResponse,
)
from app.memory.service import MemoryService

router = APIRouter(prefix="/api/v1/memory", tags=["memory"])


def get_service(db: AsyncSession = Depends(get_db)) -> MemoryService:  # noqa: B008
    return MemoryService(db)


@router.post("/", response_model=MemoryEntryResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit("10/minute")
async def store_memory(
    request: Request,
    data: MemoryEntryCreate,
    service: MemoryService = Depends(get_service),  # noqa: B008
    _current_user: User = Depends(require_role("admin", "agent")),  # noqa: B008
) -> MemoryEntryResponse:
    """Store a new memory entry."""
    _ = request  # rate limiter requires request param
    entry = await service.store(data)
    return MemoryEntryResponse.model_validate(entry)


@router.post("/compact", response_model=CompactionResult)
@limiter.limit("2/minute")
async def compact_memories(
    request: Request,
    service: MemoryService = Depends(get_service),  # noqa: B008
    _current_user: User = Depends(require_role("admin")),  # noqa: B008
) -> CompactionResult:
    """Trigger memory compaction: decay, delete, merge, promote."""
    _ = request
    return await service.compact()


@router.post("/recall", response_model=list[MemoryRecallResponse])
@limiter.limit("10/minute")
async def recall_memories(
    request: Request,
    data: MemoryRecallRequest,
    service: MemoryService = Depends(get_service),  # noqa: B008
    _current_user: User = Depends(require_role("admin", "agent")),  # noqa: B008
) -> list[MemoryRecallResponse]:
    """Recall memories by vector similarity."""
    _ = request
    return await service.recall(data)


@router.post("/recall/query", response_model=list[MemoryRecallResponse])
@limiter.limit("10/minute")
async def recall_by_query(
    request: Request,
    data: MemoryRecallByQueryRequest,
    service: MemoryService = Depends(get_service),  # noqa: B008
    _current_user: User = Depends(require_role("admin", "agent")),  # noqa: B008
) -> list[MemoryRecallResponse]:
    """Recall memories by text query (embeds the query server-side)."""
    _ = request
    return await service.recall_by_query(data)


@router.get("/{entry_id}", response_model=MemoryEntryResponse)
@limiter.limit("30/minute")
async def get_memory(
    request: Request,
    entry_id: int,
    service: MemoryService = Depends(get_service),  # noqa: B008
    _current_user: User = Depends(require_role("admin", "agent")),  # noqa: B008
) -> MemoryEntryResponse:
    """Get a memory entry by ID."""
    _ = request
    entry = await service.get(entry_id)
    return MemoryEntryResponse.model_validate(entry)


@router.get(
    "/type/{memory_type}",
    response_model=list[MemoryEntryResponse],
)
@limiter.limit("30/minute")
async def list_by_type(
    request: Request,
    memory_type: Literal["procedural", "episodic", "semantic", "query_pattern"],
    limit: int = Query(default=50, ge=1, le=200),
    service: MemoryService = Depends(get_service),  # noqa: B008
    _current_user: User = Depends(require_role("admin", "agent")),  # noqa: B008
) -> list[MemoryEntryResponse]:
    """List memory entries by type."""
    _ = request
    entries = await service.get_by_type(memory_type, limit)
    return [MemoryEntryResponse.model_validate(e) for e in entries]


@router.delete("/decayed", status_code=status.HTTP_200_OK)
@limiter.limit("5/minute")
async def delete_decayed(
    request: Request,
    threshold: float = Query(default=0.1, ge=0.0, le=1.0),
    service: MemoryService = Depends(get_service),  # noqa: B008
    _current_user: User = Depends(require_role("admin")),  # noqa: B008
) -> dict[str, int]:
    """Delete decayed non-evergreen memory entries below threshold."""
    _ = request
    count = await service.delete_decayed(threshold)
    return {"deleted_count": count}
