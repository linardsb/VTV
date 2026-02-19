"""Business logic for stop management."""

from __future__ import annotations

import math

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.shared.schemas import PaginatedResponse, PaginationParams
from app.stops.exceptions import StopAlreadyExistsError, StopNotFoundError
from app.stops.models import Stop
from app.stops.repository import StopRepository
from app.stops.schemas import (
    StopCreate,
    StopNearbyParams,
    StopResponse,
    StopUpdate,
)

logger = get_logger(__name__)

_EARTH_RADIUS_METERS = 6_371_000


def _haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate great-circle distance between two points in meters.

    Uses the Haversine formula for accuracy at city-scale distances.

    Args:
        lat1: Latitude of first point (WGS84 degrees).
        lon1: Longitude of first point (WGS84 degrees).
        lat2: Latitude of second point (WGS84 degrees).
        lon2: Longitude of second point (WGS84 degrees).

    Returns:
        Distance in meters.
    """
    # NOTE: duplicated from app/core/agents/tools/transit/search_stops.py
    lat1_r = math.radians(lat1)
    lat2_r = math.radians(lat2)
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2) ** 2 + math.cos(lat1_r) * math.cos(lat2_r) * math.sin(dlon / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return _EARTH_RADIUS_METERS * c


class StopService:
    """Business logic for stop management."""

    def __init__(self, db: AsyncSession) -> None:
        """Initialize with database session.

        Args:
            db: SQLAlchemy async session.
        """
        self.db = db
        self.repository = StopRepository(db)

    async def get_stop(self, stop_id: int) -> StopResponse:
        """Get a stop by ID.

        Args:
            stop_id: The stop's database ID.

        Returns:
            StopResponse for the found stop.

        Raises:
            StopNotFoundError: If stop does not exist.
        """
        logger.info("stops.fetch_started", stop_id=stop_id)

        stop = await self.repository.get(stop_id)
        if not stop:
            logger.warning("stops.fetch_failed", stop_id=stop_id, reason="not_found")
            raise StopNotFoundError(f"Stop {stop_id} not found")

        return StopResponse.model_validate(stop)

    async def list_stops(
        self,
        pagination: PaginationParams,
        *,
        search: str | None = None,
        active_only: bool = True,
    ) -> PaginatedResponse[StopResponse]:
        """List stops with pagination and optional filtering.

        Args:
            pagination: Page and page_size parameters.
            search: Case-insensitive substring filter on stop_name.
            active_only: If True, only return active stops.

        Returns:
            Paginated list of StopResponse items.
        """
        logger.info(
            "stops.list_started",
            page=pagination.page,
            page_size=pagination.page_size,
            search=search,
            active_only=active_only,
        )

        stops = await self.repository.list(
            offset=pagination.offset,
            limit=pagination.page_size,
            active_only=active_only,
            search=search,
        )
        total = await self.repository.count(active_only=active_only, search=search)

        items = [StopResponse.model_validate(s) for s in stops]

        logger.info("stops.list_completed", result_count=len(items), total=total)

        return PaginatedResponse[StopResponse](
            items=items,
            total=total,
            page=pagination.page,
            page_size=pagination.page_size,
        )

    async def create_stop(self, data: StopCreate) -> StopResponse:
        """Create a new stop.

        Args:
            data: Stop creation data.

        Returns:
            StopResponse for the created stop.

        Raises:
            StopAlreadyExistsError: If gtfs_stop_id already exists.
        """
        logger.info("stops.create_started", gtfs_stop_id=data.gtfs_stop_id)

        existing = await self.repository.get_by_gtfs_id(data.gtfs_stop_id)
        if existing:
            logger.warning(
                "stops.create_failed",
                gtfs_stop_id=data.gtfs_stop_id,
                reason="duplicate",
            )
            raise StopAlreadyExistsError(
                f"Stop with gtfs_stop_id '{data.gtfs_stop_id}' already exists"
            )

        stop = await self.repository.create(data)
        logger.info("stops.create_completed", stop_id=stop.id, gtfs_stop_id=stop.gtfs_stop_id)

        return StopResponse.model_validate(stop)

    async def update_stop(self, stop_id: int, data: StopUpdate) -> StopResponse:
        """Update an existing stop.

        Args:
            stop_id: The stop's database ID.
            data: Fields to update.

        Returns:
            StopResponse for the updated stop.

        Raises:
            StopNotFoundError: If stop does not exist.
            StopAlreadyExistsError: If updating gtfs_stop_id to a duplicate.
        """
        logger.info("stops.update_started", stop_id=stop_id)

        stop = await self.repository.get(stop_id)
        if not stop:
            logger.warning("stops.update_failed", stop_id=stop_id, reason="not_found")
            raise StopNotFoundError(f"Stop {stop_id} not found")

        # Check for duplicate gtfs_stop_id if it's being changed
        update_fields = data.model_dump(exclude_unset=True)
        new_gtfs_id = update_fields.get("gtfs_stop_id")
        if isinstance(new_gtfs_id, str) and new_gtfs_id != stop.gtfs_stop_id:
            existing = await self.repository.get_by_gtfs_id(new_gtfs_id)
            if existing:
                logger.warning(
                    "stops.update_failed",
                    stop_id=stop_id,
                    gtfs_stop_id=new_gtfs_id,
                    reason="duplicate",
                )
                raise StopAlreadyExistsError(
                    f"Stop with gtfs_stop_id '{new_gtfs_id}' already exists"
                )

        stop = await self.repository.update(stop, data)
        logger.info("stops.update_completed", stop_id=stop.id)

        return StopResponse.model_validate(stop)

    async def delete_stop(self, stop_id: int) -> None:
        """Delete a stop by ID.

        Args:
            stop_id: The stop's database ID.

        Raises:
            StopNotFoundError: If stop does not exist.
        """
        logger.info("stops.delete_started", stop_id=stop_id)

        stop = await self.repository.get(stop_id)
        if not stop:
            logger.warning("stops.delete_failed", stop_id=stop_id, reason="not_found")
            raise StopNotFoundError(f"Stop {stop_id} not found")

        await self.repository.delete(stop)
        logger.info("stops.delete_completed", stop_id=stop_id)

    async def search_nearby(self, params: StopNearbyParams, limit: int = 20) -> list[StopResponse]:
        """Find stops within a radius of a geographic point.

        Uses Haversine formula to calculate great-circle distances.
        Loads all active stops and filters in Python (sufficient for ~2000 stops).

        Args:
            params: Latitude, longitude, and radius parameters.
            limit: Maximum results to return.

        Returns:
            List of StopResponse sorted by distance (nearest first).
        """
        logger.info(
            "stops.nearby_started",
            latitude=params.latitude,
            longitude=params.longitude,
            radius_meters=params.radius_meters,
        )

        all_stops = await self.repository.list(offset=0, limit=10000, active_only=True)

        candidates: list[tuple[float, Stop]] = []
        for stop in all_stops:
            if stop.stop_lat is None or stop.stop_lon is None:
                continue
            dist = _haversine_distance(
                params.latitude, params.longitude, stop.stop_lat, stop.stop_lon
            )
            if dist <= params.radius_meters:
                candidates.append((dist, stop))

        candidates.sort(key=lambda pair: pair[0])

        results = [StopResponse.model_validate(stop) for _dist, stop in candidates[:limit]]

        logger.info("stops.nearby_completed", result_count=len(results))

        return results
