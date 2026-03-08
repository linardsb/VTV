# pyright: reportUnknownMemberType=false, reportUntypedFunctionDecorator=false
"""REST API routes for fleet device management and Traccar webhook."""

from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from fastapi.requests import Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user, require_role
from app.auth.models import User
from app.core.config import get_settings
from app.core.database import get_db
from app.core.rate_limit import limiter
from app.core.redis import get_redis
from app.fleet.bridge import TraccarBridge
from app.fleet.schemas import (
    TraccarWebhookPayload,
    TrackedDeviceCreate,
    TrackedDeviceResponse,
    TrackedDeviceUpdate,
)
from app.fleet.service import FleetService
from app.shared.schemas import PaginatedResponse, PaginationParams

router = APIRouter(prefix="/api/v1/fleet", tags=["fleet"])


def get_service(db: AsyncSession = Depends(get_db)) -> FleetService:  # noqa: B008
    """Dependency to create FleetService with request-scoped session."""
    return FleetService(db)


async def verify_webhook_token(
    authorization: str | None = Header(None),
) -> None:
    """Verify Traccar webhook bearer token.

    Args:
        authorization: Authorization header value.

    Raises:
        HTTPException: If token is missing or invalid.
    """
    settings = get_settings()
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing webhook token")
    token = authorization.removeprefix("Bearer ").strip()
    if token != settings.traccar_webhook_token:
        raise HTTPException(status_code=401, detail="Invalid webhook token")


# --- Device CRUD Endpoints ---


@router.get("/devices", response_model=PaginatedResponse[TrackedDeviceResponse])
@limiter.limit("30/minute")
async def list_devices(
    request: Request,
    pagination: PaginationParams = Depends(),  # noqa: B008
    search: str | None = Query(None, max_length=200),
    device_status: str | None = Query(None, alias="status"),
    vehicle_linked: bool | None = Query(None),
    service: FleetService = Depends(get_service),  # noqa: B008
    _current_user: User = Depends(get_current_user),  # noqa: B008
) -> PaginatedResponse[TrackedDeviceResponse]:
    """List tracked devices with pagination and optional filters."""
    _ = request
    return await service.list_devices(
        pagination,
        search=search,
        status=device_status,
        vehicle_linked=vehicle_linked,
    )


@router.get("/devices/{device_id}", response_model=TrackedDeviceResponse)
@limiter.limit("30/minute")
async def get_device(
    request: Request,
    device_id: int,
    service: FleetService = Depends(get_service),  # noqa: B008
    _current_user: User = Depends(get_current_user),  # noqa: B008
) -> TrackedDeviceResponse:
    """Get a tracked device by database ID."""
    _ = request
    return await service.get_device(device_id)


@router.post(
    "/devices",
    response_model=TrackedDeviceResponse,
    status_code=status.HTTP_201_CREATED,
)
@limiter.limit("10/minute")
async def create_device(
    request: Request,
    data: TrackedDeviceCreate,
    service: FleetService = Depends(get_service),  # noqa: B008
    _current_user: User = Depends(require_role("admin", "editor")),  # noqa: B008
) -> TrackedDeviceResponse:
    """Create a new tracked device."""
    _ = request
    return await service.create_device(data)


@router.patch("/devices/{device_id}", response_model=TrackedDeviceResponse)
@limiter.limit("10/minute")
async def update_device(
    request: Request,
    device_id: int,
    data: TrackedDeviceUpdate,
    service: FleetService = Depends(get_service),  # noqa: B008
    _current_user: User = Depends(require_role("admin", "editor")),  # noqa: B008
) -> TrackedDeviceResponse:
    """Update an existing tracked device."""
    _ = request
    return await service.update_device(device_id, data)


@router.delete("/devices/{device_id}", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit("10/minute")
async def delete_device(
    request: Request,
    device_id: int,
    service: FleetService = Depends(get_service),  # noqa: B008
    _current_user: User = Depends(require_role("admin")),  # noqa: B008
) -> None:
    """Delete a tracked device by database ID."""
    _ = request
    await service.delete_device(device_id)


# --- Webhook Endpoint ---


@router.post("/webhook/traccar")
@limiter.limit("120/minute")
async def traccar_webhook(
    request: Request,
    payload: TraccarWebhookPayload,
    db: AsyncSession = Depends(get_db),  # noqa: B008
    _auth: None = Depends(verify_webhook_token),
) -> dict[str, Any]:
    """Receive Traccar position event via webhook.

    Authenticated via bearer token (not JWT). Processes the position
    and stores it in Redis + TimescaleDB.
    """
    _ = request
    redis_client = await get_redis()
    bridge = TraccarBridge(db)
    processed = await bridge.process_webhook(payload, redis_client)
    return {"status": "ok", "processed": processed}
