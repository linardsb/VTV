# pyright: reportArgumentType=false
"""Business logic for geofence zone management."""

from __future__ import annotations

import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.geofences.exceptions import GeofenceNotFoundError
from app.geofences.models import Geofence
from app.geofences.repository import GeofenceEventRepository, GeofenceRepository
from app.geofences.schemas import (
    DwellTimeReport,
    GeofenceCreate,
    GeofenceEventResponse,
    GeofenceResponse,
    GeofenceUpdate,
)
from app.shared.schemas import PaginatedResponse, PaginationParams

logger = get_logger(__name__)


class GeofenceService:
    """Business logic for geofence zone management."""

    def __init__(self, db: AsyncSession) -> None:
        """Initialize with database session.

        Args:
            db: SQLAlchemy async session.
        """
        self.db = db
        self.geofence_repo = GeofenceRepository(db)
        self.event_repo = GeofenceEventRepository(db)

    def _coordinates_to_wkt(self, coordinates: list[list[float]]) -> str:
        """Convert GeoJSON coordinate pairs to WKT POLYGON string.

        Args:
            coordinates: List of [lon, lat] pairs.

        Returns:
            WKT POLYGON string.
        """
        points = ", ".join(f"{lon} {lat}" for lon, lat in coordinates)
        return f"POLYGON(({points}))"

    async def _build_response(self, geofence: Geofence) -> GeofenceResponse:
        """Build a GeofenceResponse with coordinates extracted from PostGIS.

        Args:
            geofence: Geofence model instance.

        Returns:
            GeofenceResponse with coordinates.
        """
        coordinates = await self.geofence_repo.get_coordinates(geofence)
        return GeofenceResponse(
            id=geofence.id,
            name=geofence.name,
            zone_type=geofence.zone_type,
            color=geofence.color,
            alert_on_enter=geofence.alert_on_enter,
            alert_on_exit=geofence.alert_on_exit,
            alert_on_dwell=geofence.alert_on_dwell,
            dwell_threshold_minutes=geofence.dwell_threshold_minutes,
            alert_severity=geofence.alert_severity,
            description=geofence.description,
            coordinates=coordinates,
            is_active=geofence.is_active,
            created_at=geofence.created_at,
            updated_at=geofence.updated_at,
        )

    async def get_geofence(self, geofence_id: int) -> GeofenceResponse:
        """Get a geofence by ID.

        Args:
            geofence_id: The geofence's database ID.

        Returns:
            GeofenceResponse for the found geofence.

        Raises:
            GeofenceNotFoundError: If geofence does not exist.
        """
        logger.info("geofences.geofence.fetch_started", geofence_id=geofence_id)

        geofence = await self.geofence_repo.get(geofence_id)
        if not geofence:
            logger.warning(
                "geofences.geofence.fetch_failed", geofence_id=geofence_id, reason="not_found"
            )
            raise GeofenceNotFoundError(geofence_id)

        logger.info("geofences.geofence.fetch_completed", geofence_id=geofence_id)
        return await self._build_response(geofence)

    async def list_geofences(
        self,
        pagination: PaginationParams,
        *,
        search: str | None = None,
        zone_type: str | None = None,
        is_active: bool | None = None,
    ) -> PaginatedResponse[GeofenceResponse]:
        """List geofences with pagination and filtering.

        Args:
            pagination: Page and page_size parameters.
            search: Case-insensitive search on name.
            zone_type: Filter by zone type.
            is_active: Filter by active status.

        Returns:
            Paginated list of GeofenceResponse items.
        """
        logger.info(
            "geofences.geofence.list_started",
            page=pagination.page,
            page_size=pagination.page_size,
            search=search,
        )

        geofences = await self.geofence_repo.list_geofences(
            offset=pagination.offset,
            limit=pagination.page_size,
            search=search,
            zone_type=zone_type,
            is_active=is_active,
        )
        total = await self.geofence_repo.count(
            search=search,
            zone_type=zone_type,
            is_active=is_active,
        )

        items = [await self._build_response(g) for g in geofences]

        logger.info("geofences.geofence.list_completed", result_count=len(items), total=total)

        return PaginatedResponse[GeofenceResponse](
            items=items,
            total=total,
            page=pagination.page,
            page_size=pagination.page_size,
        )

    async def create_geofence(self, data: GeofenceCreate) -> GeofenceResponse:
        """Create a new geofence zone.

        Args:
            data: Geofence creation data with polygon coordinates.

        Returns:
            GeofenceResponse for the created geofence.
        """
        logger.info("geofences.geofence.create_started", name=data.name)

        wkt = self._coordinates_to_wkt(data.coordinates)
        geofence = await self.geofence_repo.create(data, wkt)

        logger.info(
            "geofences.geofence.create_completed",
            geofence_id=geofence.id,
            name=geofence.name,
        )

        return await self._build_response(geofence)

    async def update_geofence(self, geofence_id: int, data: GeofenceUpdate) -> GeofenceResponse:
        """Update an existing geofence zone.

        Args:
            geofence_id: The geofence's database ID.
            data: Fields to update.

        Returns:
            GeofenceResponse for the updated geofence.

        Raises:
            GeofenceNotFoundError: If geofence does not exist.
        """
        logger.info("geofences.geofence.update_started", geofence_id=geofence_id)

        geofence = await self.geofence_repo.get(geofence_id)
        if not geofence:
            logger.warning(
                "geofences.geofence.update_failed", geofence_id=geofence_id, reason="not_found"
            )
            raise GeofenceNotFoundError(geofence_id)

        wkt = None
        if data.coordinates is not None:
            wkt = self._coordinates_to_wkt(data.coordinates)

        geofence = await self.geofence_repo.update(geofence, data, wkt)
        logger.info("geofences.geofence.update_completed", geofence_id=geofence.id)

        return await self._build_response(geofence)

    async def delete_geofence(self, geofence_id: int) -> None:
        """Delete a geofence zone by ID.

        Args:
            geofence_id: The geofence's database ID.

        Raises:
            GeofenceNotFoundError: If geofence does not exist.
        """
        logger.info("geofences.geofence.delete_started", geofence_id=geofence_id)

        geofence = await self.geofence_repo.get(geofence_id)
        if not geofence:
            logger.warning(
                "geofences.geofence.delete_failed", geofence_id=geofence_id, reason="not_found"
            )
            raise GeofenceNotFoundError(geofence_id)

        await self.geofence_repo.delete(geofence)
        logger.info("geofences.geofence.delete_completed", geofence_id=geofence_id)

    async def list_events_by_geofence(
        self,
        geofence_id: int,
        pagination: PaginationParams,
        *,
        event_type: str | None = None,
        start_time: datetime.datetime | None = None,
        end_time: datetime.datetime | None = None,
    ) -> PaginatedResponse[GeofenceEventResponse]:
        """List events for a specific geofence.

        Args:
            geofence_id: The geofence's database ID.
            pagination: Page and page_size parameters.
            event_type: Filter by event type.
            start_time: Filter events after this time.
            end_time: Filter events before this time.

        Returns:
            Paginated list of GeofenceEventResponse items.

        Raises:
            GeofenceNotFoundError: If geofence does not exist.
        """
        geofence = await self.geofence_repo.get(geofence_id)
        if not geofence:
            raise GeofenceNotFoundError(geofence_id)

        events = await self.event_repo.list_by_geofence(
            geofence_id,
            offset=pagination.offset,
            limit=pagination.page_size,
            event_type=event_type,
            start_time=start_time,
            end_time=end_time,
        )
        total = await self.event_repo.count_by_geofence(
            geofence_id,
            event_type=event_type,
            start_time=start_time,
            end_time=end_time,
        )

        items = [
            GeofenceEventResponse(
                id=e.id,
                geofence_id=e.geofence_id,
                geofence_name=geofence.name,
                vehicle_id=e.vehicle_id,
                event_type=e.event_type,
                entered_at=e.entered_at,
                exited_at=e.exited_at,
                dwell_seconds=e.dwell_seconds,
                latitude=e.latitude,
                longitude=e.longitude,
                created_at=e.created_at,
            )
            for e in events
        ]

        return PaginatedResponse[GeofenceEventResponse](
            items=items,
            total=total,
            page=pagination.page,
            page_size=pagination.page_size,
        )

    async def list_all_events(
        self,
        pagination: PaginationParams,
        *,
        vehicle_id: str | None = None,
        event_type: str | None = None,
        geofence_id: int | None = None,
        start_time: datetime.datetime | None = None,
        end_time: datetime.datetime | None = None,
    ) -> PaginatedResponse[GeofenceEventResponse]:
        """List all geofence events with filtering.

        Args:
            pagination: Page and page_size parameters.
            vehicle_id: Filter by vehicle ID.
            event_type: Filter by event type.
            geofence_id: Filter by geofence ID.
            start_time: Filter events after this time.
            end_time: Filter events before this time.

        Returns:
            Paginated list of GeofenceEventResponse items.
        """
        events = await self.event_repo.list_all(
            offset=pagination.offset,
            limit=pagination.page_size,
            vehicle_id=vehicle_id,
            event_type=event_type,
            geofence_id=geofence_id,
            start_time=start_time,
            end_time=end_time,
        )
        total = await self.event_repo.count_all(
            vehicle_id=vehicle_id,
            event_type=event_type,
            geofence_id=geofence_id,
            start_time=start_time,
            end_time=end_time,
        )

        # Build responses - need to fetch geofence names
        items: list[GeofenceEventResponse] = []
        geofence_name_cache: dict[int, str] = {}
        for e in events:
            if e.geofence_id not in geofence_name_cache:
                geo = await self.geofence_repo.get(e.geofence_id)
                geofence_name_cache[e.geofence_id] = geo.name if geo else "Unknown"
            items.append(
                GeofenceEventResponse(
                    id=e.id,
                    geofence_id=e.geofence_id,
                    geofence_name=geofence_name_cache[e.geofence_id],
                    vehicle_id=e.vehicle_id,
                    event_type=e.event_type,
                    entered_at=e.entered_at,
                    exited_at=e.exited_at,
                    dwell_seconds=e.dwell_seconds,
                    latitude=e.latitude,
                    longitude=e.longitude,
                    created_at=e.created_at,
                )
            )

        return PaginatedResponse[GeofenceEventResponse](
            items=items,
            total=total,
            page=pagination.page,
            page_size=pagination.page_size,
        )

    async def get_dwell_report(
        self,
        geofence_id: int,
        start_time: datetime.datetime | None = None,
        end_time: datetime.datetime | None = None,
    ) -> DwellTimeReport:
        """Get aggregated dwell time statistics for a geofence.

        Args:
            geofence_id: The geofence's database ID.
            start_time: Filter events after this time.
            end_time: Filter events before this time.

        Returns:
            DwellTimeReport with aggregated statistics.

        Raises:
            GeofenceNotFoundError: If geofence does not exist.
        """
        geofence = await self.geofence_repo.get(geofence_id)
        if not geofence:
            raise GeofenceNotFoundError(geofence_id)

        return await self.event_repo.get_dwell_report(
            geofence_id, geofence.name, start_time, end_time
        )
