"""Business logic for operational events."""

from __future__ import annotations

import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.events.exceptions import EventNotFoundError
from app.events.repository import EventRepository
from app.events.schemas import (
    EventCreate,
    EventResponse,
    EventUpdate,
)
from app.shared.schemas import PaginatedResponse, PaginationParams

logger = get_logger(__name__)


class EventService:
    """Business logic for operational events."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.repository = EventRepository(db)

    async def get_event(self, event_id: int) -> EventResponse:
        logger.info("events.fetch_started", event_id=event_id)
        event = await self.repository.get(event_id)
        if not event:
            logger.warning("events.fetch_failed", event_id=event_id, reason="not_found")
            raise EventNotFoundError(f"Event {event_id} not found")
        logger.info("events.fetch_completed", event_id=event_id)
        return EventResponse.model_validate(event)

    async def list_events(
        self,
        pagination: PaginationParams,
        *,
        start_date: datetime.datetime | None = None,
        end_date: datetime.datetime | None = None,
    ) -> PaginatedResponse[EventResponse]:
        logger.info(
            "events.list_started",
            page=pagination.page,
            page_size=pagination.page_size,
        )
        events = await self.repository.list(
            offset=pagination.offset,
            limit=pagination.page_size,
            start_date=start_date,
            end_date=end_date,
        )
        total = await self.repository.count(
            start_date=start_date,
            end_date=end_date,
        )
        items = [EventResponse.model_validate(e) for e in events]
        logger.info("events.list_completed", result_count=len(items), total=total)
        return PaginatedResponse[EventResponse](
            items=items,
            total=total,
            page=pagination.page,
            page_size=pagination.page_size,
        )

    async def create_event(self, data: EventCreate) -> EventResponse:
        logger.info("events.create_started", title=data.title)
        event = await self.repository.create(data)
        logger.info("events.create_completed", event_id=event.id)
        return EventResponse.model_validate(event)

    async def update_event(self, event_id: int, data: EventUpdate) -> EventResponse:
        logger.info("events.update_started", event_id=event_id)
        event = await self.repository.get(event_id)
        if not event:
            logger.warning("events.update_failed", event_id=event_id, reason="not_found")
            raise EventNotFoundError(f"Event {event_id} not found")
        event = await self.repository.update(event, data)
        logger.info("events.update_completed", event_id=event.id)
        return EventResponse.model_validate(event)

    async def delete_event(self, event_id: int) -> None:
        logger.info("events.delete_started", event_id=event_id)
        event = await self.repository.get(event_id)
        if not event:
            logger.warning("events.delete_failed", event_id=event_id, reason="not_found")
            raise EventNotFoundError(f"Event {event_id} not found")
        await self.repository.delete(event)
        logger.info("events.delete_completed", event_id=event_id)
