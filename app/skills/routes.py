# pyright: reportUnknownMemberType=false, reportUntypedFunctionDecorator=false
"""REST API routes for agent skills."""

from fastapi import APIRouter, Depends, Query, status
from fastapi.requests import Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user, require_role
from app.auth.models import User
from app.core.database import get_db
from app.core.rate_limit import limiter
from app.shared.schemas import PaginatedResponse, PaginationParams
from app.skills.schemas import (
    CategoryType,
    SkillCreate,
    SkillResponse,
    SkillUpdate,
)
from app.skills.service import SkillService

router = APIRouter(prefix="/api/v1/skills", tags=["skills"])


def get_service(db: AsyncSession = Depends(get_db)) -> SkillService:  # noqa: B008
    """Dependency to create SkillService with request-scoped session."""
    return SkillService(db)


@router.get("/", response_model=PaginatedResponse[SkillResponse])
@limiter.limit("30/minute")
async def list_skills(
    request: Request,
    pagination: PaginationParams = Depends(),  # noqa: B008
    category: CategoryType | None = Query(None),  # noqa: B008
    is_active: bool | None = Query(None),
    service: SkillService = Depends(get_service),  # noqa: B008
    _current_user: User = Depends(get_current_user),  # noqa: B008
) -> PaginatedResponse[SkillResponse]:
    """List agent skills with optional filters.

    Requires authentication. All skill data access is restricted.
    """
    _ = request
    return await service.list_skills(pagination, category=category, is_active=is_active)


@router.get("/{skill_id}", response_model=SkillResponse)
@limiter.limit("30/minute")
async def get_skill(
    request: Request,
    skill_id: int,
    service: SkillService = Depends(get_service),  # noqa: B008
    _current_user: User = Depends(get_current_user),  # noqa: B008
) -> SkillResponse:
    """Get an agent skill by ID.

    Requires authentication. All skill data access is restricted.
    """
    _ = request
    return await service.get_skill(skill_id)


@router.post("/", response_model=SkillResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit("10/minute")
async def create_skill(
    request: Request,
    data: SkillCreate,
    service: SkillService = Depends(get_service),  # noqa: B008
    current_user: User = Depends(require_role("admin")),  # noqa: B008
) -> SkillResponse:
    """Create a new agent skill. Admin only."""
    _ = request
    return await service.create_skill(data, created_by_id=current_user.id)


@router.patch("/{skill_id}", response_model=SkillResponse)
@limiter.limit("10/minute")
async def update_skill(
    request: Request,
    skill_id: int,
    data: SkillUpdate,
    service: SkillService = Depends(get_service),  # noqa: B008
    _current_user: User = Depends(require_role("admin")),  # noqa: B008
) -> SkillResponse:
    """Update an existing agent skill. Admin only."""
    _ = request
    return await service.update_skill(skill_id, data)


@router.delete("/{skill_id}", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit("10/minute")
async def delete_skill(
    request: Request,
    skill_id: int,
    service: SkillService = Depends(get_service),  # noqa: B008
    _current_user: User = Depends(require_role("admin")),  # noqa: B008
) -> None:
    """Delete an agent skill. Admin only."""
    _ = request
    await service.delete_skill(skill_id)


@router.post("/seed", response_model=list[SkillResponse], status_code=status.HTTP_201_CREATED)
@limiter.limit("5/minute")
async def seed_skills(
    request: Request,
    service: SkillService = Depends(get_service),  # noqa: B008
    _current_user: User = Depends(require_role("admin")),  # noqa: B008
) -> list[SkillResponse]:
    """Seed default skills. Admin only. Only seeds when table is empty."""
    _ = request
    skills = await service.seed_default_skills()
    return [SkillResponse.model_validate(s) for s in skills]
