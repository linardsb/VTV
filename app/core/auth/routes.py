# pyright: reportUnknownMemberType=false, reportUntypedFunctionDecorator=false
"""REST API routes for dispatcher assignment management (admin-only)."""

from fastapi import APIRouter, Depends
from fastapi.requests import Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import require_role
from app.auth.models import User
from app.core.auth.repository import AssignmentRepository
from app.core.auth.schemas import AssignmentBulkCreate, AssignmentCreate, AssignmentResponse
from app.core.database import get_db
from app.core.exceptions import NotFoundError
from app.core.rate_limit import limiter

router = APIRouter(prefix="/api/v1/admin/assignments", tags=["assignments"])


def get_repo(db: AsyncSession = Depends(get_db)) -> AssignmentRepository:  # noqa: B008
    """Dependency to create AssignmentRepository with request-scoped session."""
    return AssignmentRepository(db)


@router.get("/", response_model=list[AssignmentResponse])
@limiter.limit("30/minute")
async def list_assignments(
    request: Request,
    user_id: int,
    repo: AssignmentRepository = Depends(get_repo),  # noqa: B008
    _current_user: User = Depends(require_role("admin")),  # noqa: B008
) -> list[AssignmentResponse]:
    """List all route assignments for a dispatcher user."""
    _ = request
    assignments = await repo.list_by_user(user_id)
    return [AssignmentResponse.model_validate(a) for a in assignments]


@router.post("/", response_model=AssignmentResponse, status_code=201)
@limiter.limit("10/minute")
async def create_assignment(
    request: Request,
    data: AssignmentCreate,
    repo: AssignmentRepository = Depends(get_repo),  # noqa: B008
    current_user: User = Depends(require_role("admin")),  # noqa: B008
) -> AssignmentResponse:
    """Create a single dispatcher-to-route assignment."""
    _ = request
    assignment = await repo.create(data.user_id, data.route_id, current_user.id)
    return AssignmentResponse.model_validate(assignment)


@router.put("/{user_id}", response_model=list[AssignmentResponse])
@limiter.limit("10/minute")
async def bulk_replace_assignments(
    request: Request,
    user_id: int,
    data: AssignmentBulkCreate,
    repo: AssignmentRepository = Depends(get_repo),  # noqa: B008
    current_user: User = Depends(require_role("admin")),  # noqa: B008
) -> list[AssignmentResponse]:
    """Replace all route assignments for a dispatcher user."""
    _ = request
    assignments = await repo.bulk_replace(user_id, data.route_ids, current_user.id)
    return [AssignmentResponse.model_validate(a) for a in assignments]


@router.delete("/{assignment_id}", status_code=204)
@limiter.limit("10/minute")
async def delete_assignment(
    request: Request,
    assignment_id: int,
    repo: AssignmentRepository = Depends(get_repo),  # noqa: B008
    _current_user: User = Depends(require_role("admin")),  # noqa: B008
) -> None:
    """Remove a single dispatcher assignment."""
    _ = request
    assignment = await repo.get(assignment_id)
    if not assignment:
        raise NotFoundError(f"Assignment {assignment_id} not found")
    await repo.delete(assignment)
