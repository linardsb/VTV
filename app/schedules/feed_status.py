"""GTFS feed status model and repository for tracking per-feed import state."""

from __future__ import annotations

import datetime

from sqlalchemy import Boolean, DateTime, Integer, String, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.shared.models import TimestampMixin


class GTFSFeedStatus(Base, TimestampMixin):
    """Tracks import state per GTFS feed.

    Each configured feed gets a row here, updated on every import
    (successful or failed). Used by GET /feeds to enrich config
    with last-import metadata.
    """

    __tablename__ = "gtfs_feed_status"

    feed_id: Mapped[str] = mapped_column(String(50), primary_key=True)
    operator_name: Mapped[str] = mapped_column(String(200), nullable=False)
    static_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    # timezone=True matches the Alembic migration (s3t4u5v6w7x8) which
    # created this column as TIMESTAMP WITH TIME ZONE. Without it, SQLAlchemy
    # infers DateTime() (tz-naive) from the annotation, and asyncpg refuses
    # to encode a tz-aware `utcnow()` value into a tz-naive column.
    last_imported_at: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_import_routes: Mapped[int] = mapped_column(Integer, default=0)
    last_import_trips: Mapped[int] = mapped_column(Integer, default=0)
    last_import_error: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    auto_import_enabled: Mapped[bool] = mapped_column(Boolean, default=True)


class GTFSFeedStatusRepository:
    """Database operations for GTFS feed status tracking."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_feed_status(self, feed_id: str) -> GTFSFeedStatus | None:
        """Get feed status by feed_id.

        Args:
            feed_id: The feed identifier.

        Returns:
            GTFSFeedStatus instance or None.
        """
        result = await self.db.execute(
            select(GTFSFeedStatus).where(GTFSFeedStatus.feed_id == feed_id)
        )
        return result.scalar_one_or_none()

    async def list_feed_statuses(self) -> list[GTFSFeedStatus]:
        """List all feed status records.

        Returns:
            List of GTFSFeedStatus instances ordered by feed_id.
        """
        result = await self.db.execute(select(GTFSFeedStatus).order_by(GTFSFeedStatus.feed_id))
        return list(result.scalars().all())

    async def upsert_feed_status(
        self,
        feed_id: str,
        operator_name: str,
        *,
        static_url: str | None = None,
        last_imported_at: datetime.datetime | None = None,
        last_import_routes: int = 0,
        last_import_trips: int = 0,
        last_import_error: str | None = None,
        auto_import_enabled: bool = True,
    ) -> GTFSFeedStatus:
        """Create or update a feed status record.

        Args:
            feed_id: The feed identifier (primary key).
            operator_name: Human-readable operator name.
            static_url: URL for GTFS static ZIP download.
            last_imported_at: Timestamp of last successful import.
            last_import_routes: Route count from last import.
            last_import_trips: Trip count from last import.
            last_import_error: Error message from last failed import.
            auto_import_enabled: Whether daily auto-import is enabled.

        Returns:
            The upserted GTFSFeedStatus instance.
        """
        existing = await self.get_feed_status(feed_id)
        if existing:
            existing.operator_name = operator_name
            if static_url is not None:
                existing.static_url = static_url
            if last_imported_at is not None:
                existing.last_imported_at = last_imported_at
            existing.last_import_routes = last_import_routes
            existing.last_import_trips = last_import_trips
            existing.last_import_error = last_import_error
            existing.auto_import_enabled = auto_import_enabled
            await self.db.flush()
            return existing

        status = GTFSFeedStatus(
            feed_id=feed_id,
            operator_name=operator_name,
            static_url=static_url,
            last_imported_at=last_imported_at,
            last_import_routes=last_import_routes,
            last_import_trips=last_import_trips,
            last_import_error=last_import_error,
            auto_import_enabled=auto_import_enabled,
        )
        self.db.add(status)
        await self.db.flush()
        return status
