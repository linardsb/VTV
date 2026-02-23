# pyright: reportUnknownMemberType=false, reportUntypedFunctionDecorator=false
"""REST API routes for driver management."""

from fastapi import APIRouter, Depends, Query, status
from fastapi.requests import Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user, require_role
from app.auth.models import User
from app.core.database import get_db
from app.core.rate_limit import limiter
from app.drivers.schemas import (
    DriverCreate,
    DriverResponse,
    DriverUpdate,
)
from app.drivers.service import DriverService
from app.shared.schemas import PaginatedResponse, PaginationParams

router = APIRouter(prefix="/api/v1/drivers", tags=["drivers"])


def get_service(db: AsyncSession = Depends(get_db)) -> DriverService:  # noqa: B008
    """Dependency to create DriverService with request-scoped session."""
    return DriverService(db)


@router.get("/", response_model=PaginatedResponse[DriverResponse])
@limiter.limit("30/minute")
async def list_drivers(
    request: Request,
    pagination: PaginationParams = Depends(),  # noqa: B008
    search: str | None = Query(None, max_length=200),
    active_only: bool = Query(default=True),
    status: str | None = Query(None, max_length=20),
    shift: str | None = Query(None, max_length=20),
    service: DriverService = Depends(get_service),  # noqa: B008
    _current_user: User = Depends(get_current_user),  # noqa: B008
) -> PaginatedResponse[DriverResponse]:
    """List drivers with pagination and optional filters."""
    _ = request
    return await service.list_drivers(
        pagination, search=search, active_only=active_only, status=status, shift=shift
    )


@router.get("/{driver_id}", response_model=DriverResponse)
@limiter.limit("30/minute")
async def get_driver(
    request: Request,
    driver_id: int,
    service: DriverService = Depends(get_service),  # noqa: B008
    _current_user: User = Depends(get_current_user),  # noqa: B008
) -> DriverResponse:
    """Get a driver by database ID."""
    _ = request
    return await service.get_driver(driver_id)


@router.post("/", response_model=DriverResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit("10/minute")
async def create_driver(
    request: Request,
    data: DriverCreate,
    service: DriverService = Depends(get_service),  # noqa: B008
    _current_user: User = Depends(require_role("admin", "dispatcher")),  # noqa: B008
) -> DriverResponse:
    """Create a new driver."""
    _ = request
    return await service.create_driver(data)


@router.patch("/{driver_id}", response_model=DriverResponse)
@limiter.limit("10/minute")
async def update_driver(
    request: Request,
    driver_id: int,
    data: DriverUpdate,
    service: DriverService = Depends(get_service),  # noqa: B008
    _current_user: User = Depends(require_role("admin", "dispatcher")),  # noqa: B008
) -> DriverResponse:
    """Update an existing driver."""
    _ = request
    return await service.update_driver(driver_id, data)


@router.delete("/{driver_id}", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit("10/minute")
async def delete_driver(
    request: Request,
    driver_id: int,
    service: DriverService = Depends(get_service),  # noqa: B008
    _current_user: User = Depends(require_role("admin", "dispatcher")),  # noqa: B008
) -> None:
    """Delete a driver by database ID."""
    _ = request
    await service.delete_driver(driver_id)
