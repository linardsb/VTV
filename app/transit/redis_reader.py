# pyright: reportUnknownMemberType=false, reportMissingTypeStubs=false, reportUnknownArgumentType=false, reportUnknownVariableType=false
"""Read vehicle positions from Redis cache."""

import json
from datetime import UTC, datetime

from app.core.config import get_settings
from app.core.logging import get_logger
from app.core.redis import get_redis
from app.transit.schemas import VehiclePosition, VehiclePositionsResponse

logger = get_logger(__name__)


async def get_vehicles_from_redis(
    *,
    feed_id: str | None = None,
    route_id: str | None = None,
) -> VehiclePositionsResponse:
    """Read vehicle positions from Redis, with optional feed and route filters.

    Args:
        feed_id: Filter by feed source (e.g., "riga"). None = all feeds.
        route_id: Filter by route (e.g., "22"). None = all routes.

    Returns:
        VehiclePositionsResponse with matching vehicles.
    """
    redis_client = await get_redis()
    settings = get_settings()
    vehicles: list[VehiclePosition] = []

    # Determine which feeds to read
    if feed_id:
        feed_ids = [feed_id]
    else:
        feed_ids = [f.feed_id for f in settings.transit_feeds if f.enabled]

    for fid in feed_ids:
        feed_vehicles = await _read_feed_vehicles(fid)
        vehicles.extend(feed_vehicles)

    # Apply route filter
    if route_id is not None:
        vehicles = [v for v in vehicles if v.route_id == route_id]

    _ = redis_client  # Referenced above via get_redis() singleton

    return VehiclePositionsResponse(
        count=len(vehicles),
        vehicles=vehicles,
        fetched_at=datetime.now(tz=UTC).isoformat(),
        feed_id=feed_id,
    )


async def _read_feed_vehicles(
    feed_id: str,
) -> list[VehiclePosition]:
    """Read all vehicles for a single feed from Redis."""
    redis_client = await get_redis()
    feed_key = f"feed:{feed_id}:vehicles"
    vehicle_ids_raw = await redis_client.smembers(feed_key)  # type: ignore[misc]
    vehicle_ids: list[str] = sorted(str(vid) for vid in vehicle_ids_raw)

    if not vehicle_ids:
        return []

    # Batch read with MGET
    keys = [f"vehicle:{feed_id}:{vid}" for vid in vehicle_ids]
    values = await redis_client.mget(keys)

    results: list[VehiclePosition] = []
    for val in values:
        if val is None:
            continue
        data: dict[str, object] = json.loads(str(val))
        results.append(VehiclePosition(**data))  # type: ignore[arg-type]

    return results
