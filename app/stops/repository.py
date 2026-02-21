"""Data access layer for stop management."""

from __future__ import annotations

import builtins

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.stops.models import Stop
from app.stops.schemas import StopCreate, StopUpdate


class StopRepository:
    """Database operations for stops."""

    def __init__(self, db: AsyncSession) -> None:
        """Initialize with an async database session.

        Args:
            db: SQLAlchemy async session.
        """
        self.db = db

    async def get(self, stop_id: int) -> Stop | None:
        """Get a stop by primary key ID.

        Args:
            stop_id: The stop's database ID.

        Returns:
            Stop instance or None if not found.
        """
        result = await self.db.execute(select(Stop).where(Stop.id == stop_id))
        return result.scalar_one_or_none()

    async def get_by_gtfs_id(self, gtfs_stop_id: str) -> Stop | None:
        """Get a stop by its GTFS stop_id.

        Args:
            gtfs_stop_id: The GTFS identifier string.

        Returns:
            Stop instance or None if not found.
        """
        result = await self.db.execute(select(Stop).where(Stop.gtfs_stop_id == gtfs_stop_id))
        return result.scalar_one_or_none()

    async def list(
        self,
        *,
        offset: int = 0,
        limit: int = 100,
        active_only: bool = True,
        search: str | None = None,
        location_type: int | None = None,
    ) -> list[Stop]:
        """List stops with pagination, filtering, and search.

        Args:
            offset: Number of records to skip.
            limit: Maximum records to return.
            active_only: If True, only return active stops.
            search: Case-insensitive substring filter on stop_name.
            location_type: GTFS location_type filter (0=stop, 1=terminus).

        Returns:
            List of Stop instances.
        """
        query = select(Stop)
        if active_only:
            query = query.where(Stop.is_active.is_(True))
        if search:
            query = query.where(Stop.stop_name.ilike(f"%{search}%"))
        if location_type is not None:
            query = query.where(Stop.location_type == location_type)
        query = query.order_by(Stop.stop_name).offset(offset).limit(limit)
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def count(
        self,
        *,
        active_only: bool = True,
        search: str | None = None,
        location_type: int | None = None,
    ) -> int:
        """Count stops matching the given filters.

        Args:
            active_only: If True, only count active stops.
            search: Case-insensitive substring filter on stop_name.
            location_type: GTFS location_type filter (0=stop, 1=terminus).

        Returns:
            Total number of matching stops.
        """
        query = select(func.count()).select_from(Stop)
        if active_only:
            query = query.where(Stop.is_active.is_(True))
        if search:
            query = query.where(Stop.stop_name.ilike(f"%{search}%"))
        if location_type is not None:
            query = query.where(Stop.location_type == location_type)
        result = await self.db.execute(query)
        return result.scalar_one()

    async def list_all(self) -> builtins.list[Stop]:
        """List all stops without pagination (for GTFS export)."""
        result = await self.db.execute(select(Stop).order_by(Stop.id))
        return builtins.list(result.scalars().all())

    async def create(self, data: StopCreate) -> Stop:
        """Create a new stop record.

        Args:
            data: Stop creation data.

        Returns:
            The newly created Stop instance.
        """
        stop = Stop(**data.model_dump())
        self.db.add(stop)
        await self.db.commit()
        await self.db.refresh(stop)
        return stop

    async def update(self, stop: Stop, data: StopUpdate) -> Stop:
        """Update an existing stop record.

        Args:
            stop: The stop instance to update.
            data: Fields to update (only set fields are applied).

        Returns:
            The updated Stop instance.
        """
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(stop, field, value)
        await self.db.commit()
        await self.db.refresh(stop)
        return stop

    async def delete(self, stop: Stop) -> None:
        """Delete a stop record.

        Args:
            stop: The stop instance to delete.
        """
        await self.db.delete(stop)
        await self.db.commit()
