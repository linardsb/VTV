# pyright: reportUnknownMemberType=false, reportUntypedFunctionDecorator=false
"""REST API routes for operational events."""

import datetime

from fastapi import APIRouter, Depends, Query, status
from fastapi.requests import Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user, require_role
from app.auth.models import User
from app.core.database import get_db
from app.core.rate_limit import limiter
from app.events.schemas import (
    EventCreate,
    EventResponse,
    EventUpdate,
)
from app.events.service import EventService
from app.shared.schemas import PaginatedResponse, PaginationParams

router = APIRouter(prefix="/api/v1/events", tags=["events"])


def get_service(db: AsyncSession = Depends(get_db)) -> EventService:  # noqa: B008
    """Dependency to create EventService with request-scoped session."""
    return EventService(db)


@router.get("/", response_model=PaginatedResponse[EventResponse])
@limiter.limit("30/minute")
async def list_events(
    request: Request,
    pagination: PaginationParams = Depends(),  # noqa: B008
    start_date: datetime.datetime | None = Query(None),  # noqa: B008
    end_date: datetime.datetime | None = Query(None),  # noqa: B008
    service: EventService = Depends(get_service),  # noqa: B008
    _current_user: User = Depends(get_current_user),  # noqa: B008
) -> PaginatedResponse[EventResponse]:
    """List operational events with optional date range filter.

    Requires authentication. All operational data access is restricted.
    """
    _ = request
    return await service.list_events(pagination, start_date=start_date, end_date=end_date)


@router.get("/{event_id}", response_model=EventResponse)
@limiter.limit("30/minute")
async def get_event(
    request: Request,
    event_id: int,
    service: EventService = Depends(get_service),  # noqa: B008
    _current_user: User = Depends(get_current_user),  # noqa: B008
) -> EventResponse:
    """Get an operational event by ID.

    Requires authentication. All operational data access is restricted.
    """
    _ = request
    return await service.get_event(event_id)


@router.post("/", response_model=EventResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit("10/minute")
async def create_event(
    request: Request,
    data: EventCreate,
    service: EventService = Depends(get_service),  # noqa: B008
    _current_user: User = Depends(require_role("admin", "editor")),  # noqa: B008
) -> EventResponse:
    """Create a new operational event."""
    _ = request
    return await service.create_event(data)


@router.patch("/{event_id}", response_model=EventResponse)
@limiter.limit("10/minute")
async def update_event(
    request: Request,
    event_id: int,
    data: EventUpdate,
    service: EventService = Depends(get_service),  # noqa: B008
    _current_user: User = Depends(require_role("admin", "editor")),  # noqa: B008
) -> EventResponse:
    """Update an existing operational event."""
    _ = request
    return await service.update_event(event_id, data)


@router.delete("/{event_id}", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit("10/minute")
async def delete_event(
    request: Request,
    event_id: int,
    service: EventService = Depends(get_service),  # noqa: B008
    _current_user: User = Depends(require_role("admin", "editor")),  # noqa: B008
) -> None:
    """Delete an operational event."""
    _ = request
    await service.delete_event(event_id)
