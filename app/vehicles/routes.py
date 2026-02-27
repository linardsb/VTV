# pyright: reportUnknownMemberType=false, reportUntypedFunctionDecorator=false
"""REST API routes for vehicle management."""

from fastapi import APIRouter, Depends, Query, status
from fastapi.requests import Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user, require_role
from app.auth.models import User
from app.core.database import get_db
from app.core.rate_limit import limiter
from app.shared.schemas import PaginatedResponse, PaginationParams
from app.vehicles.schemas import (
    MaintenanceRecordCreate,
    MaintenanceRecordResponse,
    VehicleCreate,
    VehicleResponse,
    VehicleStatus,
    VehicleType,
    VehicleUpdate,
)
from app.vehicles.service import VehicleService

router = APIRouter(prefix="/api/v1/vehicles", tags=["vehicles"])


def get_service(db: AsyncSession = Depends(get_db)) -> VehicleService:  # noqa: B008
    """Dependency to create VehicleService with request-scoped session."""
    return VehicleService(db)


@router.get("/", response_model=PaginatedResponse[VehicleResponse])
@limiter.limit("30/minute")
async def list_vehicles(
    request: Request,
    pagination: PaginationParams = Depends(),  # noqa: B008
    search: str | None = Query(None, max_length=200),
    vehicle_type: VehicleType | None = Query(None),  # noqa: B008
    vehicle_status: VehicleStatus | None = Query(None, alias="status"),  # noqa: B008
    active_only: bool = Query(default=True),
    service: VehicleService = Depends(get_service),  # noqa: B008
    _current_user: User = Depends(get_current_user),  # noqa: B008
) -> PaginatedResponse[VehicleResponse]:
    """List vehicles with pagination and optional filters."""
    _ = request
    return await service.list_vehicles(
        pagination,
        search=search,
        vehicle_type=vehicle_type,
        status=vehicle_status,
        active_only=active_only,
    )


@router.get("/{vehicle_id}", response_model=VehicleResponse)
@limiter.limit("30/minute")
async def get_vehicle(
    request: Request,
    vehicle_id: int,
    service: VehicleService = Depends(get_service),  # noqa: B008
    _current_user: User = Depends(get_current_user),  # noqa: B008
) -> VehicleResponse:
    """Get a vehicle by database ID."""
    _ = request
    return await service.get_vehicle(vehicle_id)


@router.post("/", response_model=VehicleResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit("10/minute")
async def create_vehicle(
    request: Request,
    data: VehicleCreate,
    service: VehicleService = Depends(get_service),  # noqa: B008
    _current_user: User = Depends(require_role("admin", "editor")),  # noqa: B008
) -> VehicleResponse:
    """Create a new vehicle."""
    _ = request
    return await service.create_vehicle(data)


@router.patch("/{vehicle_id}", response_model=VehicleResponse)
@limiter.limit("10/minute")
async def update_vehicle(
    request: Request,
    vehicle_id: int,
    data: VehicleUpdate,
    service: VehicleService = Depends(get_service),  # noqa: B008
    _current_user: User = Depends(require_role("admin", "editor")),  # noqa: B008
) -> VehicleResponse:
    """Update an existing vehicle."""
    _ = request
    return await service.update_vehicle(vehicle_id, data)


@router.delete("/{vehicle_id}", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit("10/minute")
async def delete_vehicle(
    request: Request,
    vehicle_id: int,
    service: VehicleService = Depends(get_service),  # noqa: B008
    _current_user: User = Depends(require_role("admin")),  # noqa: B008
) -> None:
    """Delete a vehicle by database ID."""
    _ = request
    await service.delete_vehicle(vehicle_id)


@router.post("/{vehicle_id}/assign-driver", response_model=VehicleResponse)
@limiter.limit("10/minute")
async def assign_driver(
    request: Request,
    vehicle_id: int,
    driver_id: int | None = Query(None),
    service: VehicleService = Depends(get_service),  # noqa: B008
    _current_user: User = Depends(require_role("admin", "dispatcher")),  # noqa: B008
) -> VehicleResponse:
    """Assign or unassign a driver to/from a vehicle."""
    _ = request
    return await service.assign_driver(vehicle_id, driver_id)


@router.post(
    "/{vehicle_id}/maintenance",
    response_model=MaintenanceRecordResponse,
    status_code=status.HTTP_201_CREATED,
)
@limiter.limit("10/minute")
async def create_maintenance_record(
    request: Request,
    vehicle_id: int,
    data: MaintenanceRecordCreate,
    service: VehicleService = Depends(get_service),  # noqa: B008
    _current_user: User = Depends(require_role("admin", "editor")),  # noqa: B008
) -> MaintenanceRecordResponse:
    """Add a maintenance record to a vehicle."""
    _ = request
    return await service.add_maintenance_record(vehicle_id, data)


@router.get(
    "/{vehicle_id}/maintenance",
    response_model=PaginatedResponse[MaintenanceRecordResponse],
)
@limiter.limit("30/minute")
async def get_maintenance_history(
    request: Request,
    vehicle_id: int,
    pagination: PaginationParams = Depends(),  # noqa: B008
    service: VehicleService = Depends(get_service),  # noqa: B008
    _current_user: User = Depends(get_current_user),  # noqa: B008
) -> PaginatedResponse[MaintenanceRecordResponse]:
    """Get maintenance history for a vehicle."""
    _ = request
    return await service.get_maintenance_history(vehicle_id, pagination)
