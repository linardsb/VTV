"""Data access layer for operational events."""

from __future__ import annotations

import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.events.models import OperationalEvent
from app.events.schemas import EventCreate, EventUpdate


class EventRepository:
    """Database operations for operational events."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get(self, event_id: int) -> OperationalEvent | None:
        result = await self.db.execute(
            select(OperationalEvent).where(OperationalEvent.id == event_id)
        )
        return result.scalar_one_or_none()

    async def list(
        self,
        *,
        offset: int = 0,
        limit: int = 100,
        start_date: datetime.datetime | None = None,
        end_date: datetime.datetime | None = None,
        driver_id: int | None = None,
    ) -> list[OperationalEvent]:
        query = select(OperationalEvent)
        if start_date is not None:
            query = query.where(OperationalEvent.end_datetime >= start_date)
        if end_date is not None:
            query = query.where(OperationalEvent.start_datetime <= end_date)
        if driver_id is not None:
            query = query.where(OperationalEvent.driver_id == driver_id)
        query = query.order_by(OperationalEvent.start_datetime).offset(offset).limit(limit)
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def count(
        self,
        *,
        start_date: datetime.datetime | None = None,
        end_date: datetime.datetime | None = None,
        driver_id: int | None = None,
    ) -> int:
        query = select(func.count()).select_from(OperationalEvent)
        if start_date is not None:
            query = query.where(OperationalEvent.end_datetime >= start_date)
        if end_date is not None:
            query = query.where(OperationalEvent.start_datetime <= end_date)
        if driver_id is not None:
            query = query.where(OperationalEvent.driver_id == driver_id)
        result = await self.db.execute(query)
        return result.scalar_one()

    async def create(self, data: EventCreate) -> OperationalEvent:
        event = OperationalEvent(**data.model_dump())
        self.db.add(event)
        await self.db.commit()
        await self.db.refresh(event)
        return event

    async def update(self, event: OperationalEvent, data: EventUpdate) -> OperationalEvent:
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(event, field, value)
        await self.db.commit()
        await self.db.refresh(event)
        return event

    async def delete(self, event: OperationalEvent) -> None:
        await self.db.delete(event)
        await self.db.commit()
