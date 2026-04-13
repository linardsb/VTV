# pyright: reportUnknownMemberType=false, reportMissingTypeStubs=false, reportUnknownVariableType=false, reportUnknownArgumentType=false
"""GTFS-RT publisher — builds a combined VehiclePositions protobuf feed.

Reads vehicle positions from Redis (all feeds or a single feed),
serializes them into a GTFS-RT FeedMessage, and caches the result
in Redis with a short TTL.
"""

import json
from datetime import UTC, datetime

from google.transit import gtfs_realtime_pb2

from app.core.config import get_settings
from app.core.logging import get_logger
from app.core.redis import get_redis

logger = get_logger(__name__)

_CACHE_TTL_SECONDS = 5

_STATUS_MAP: dict[str, int] = {
    "IN_TRANSIT_TO": 2,
    "STOPPED_AT": 1,
    "INCOMING_AT": 0,
}


def _status_to_enum(status: str) -> int:
    """Map VehicleStopStatus string to protobuf enum int."""
    return _STATUS_MAP.get(status, 2)


def _cache_key(feed_id: str | None) -> str:
    """Build Redis cache key for the combined feed."""
    if feed_id:
        return f"gtfs_rt:combined:vehicle_positions:{feed_id}"
    return "gtfs_rt:combined:vehicle_positions"


async def build_combined_feed(*, feed_id: str | None = None) -> bytes:
    """Read vehicles from Redis and serialize as GTFS-RT protobuf.

    Args:
        feed_id: Optional feed filter. None returns all feeds combined.

    Returns:
        Serialized protobuf bytes (``application/x-protobuf``).
    """
    redis_client = await get_redis()
    key = _cache_key(feed_id)

    # Check cache
    cached = await redis_client.get(key)
    if cached is not None:
        logger.debug("transit.publisher.cache_hit", feed_id=feed_id)
        return bytes(cached) if not isinstance(cached, bytes) else cached

    logger.info("transit.publisher.build_started", feed_id=feed_id)

    try:
        vehicles = await _read_all_vehicles(feed_id=feed_id)

        feed = gtfs_realtime_pb2.FeedMessage()
        feed.header.gtfs_realtime_version = "2.0"
        feed.header.timestamp = int(datetime.now(tz=UTC).timestamp())

        for v in vehicles:
            entity = feed.entity.add()
            v_feed_id = str(v.get("feed_id", ""))
            v_vehicle_id = str(v.get("vehicle_id", ""))
            entity.id = f"{v_feed_id}_{v_vehicle_id}"

            entity.vehicle.vehicle.id = v_vehicle_id
            label = v.get("vehicle_label")
            if isinstance(label, str):
                entity.vehicle.vehicle.label = label

            trip_id = v.get("trip_id")
            if isinstance(trip_id, str):
                entity.vehicle.trip.trip_id = trip_id
            route_id = v.get("route_id")
            if isinstance(route_id, str):
                entity.vehicle.trip.route_id = route_id

            lat = v.get("latitude")
            lon = v.get("longitude")
            if isinstance(lat, (int, float)) and isinstance(lon, (int, float)):
                entity.vehicle.position.latitude = float(lat)
                entity.vehicle.position.longitude = float(lon)
            bearing = v.get("bearing")
            if isinstance(bearing, (int, float)):
                entity.vehicle.position.bearing = float(bearing)
            speed = v.get("speed")
            if isinstance(speed, (int, float)):
                entity.vehicle.position.speed = float(speed)

            status = v.get("current_status")
            if isinstance(status, str):
                entity.vehicle.current_status = _status_to_enum(status)

            stop_id = v.get("stop_id")
            if isinstance(stop_id, str):
                entity.vehicle.stop_id = stop_id

            ts = v.get("timestamp")
            if isinstance(ts, int):
                entity.vehicle.timestamp = ts

        result: bytes = feed.SerializeToString()

        await redis_client.set(key, result, ex=_CACHE_TTL_SECONDS)

        logger.info(
            "transit.publisher.build_completed",
            vehicle_count=len(vehicles),
            feed_id=feed_id,
            bytes_size=len(result),
        )
        return result

    except Exception:
        logger.exception("transit.publisher.build_failed", feed_id=feed_id)
        raise


async def _read_all_vehicles(*, feed_id: str | None = None) -> list[dict[str, object]]:
    """Read raw vehicle dicts from Redis for one or all feeds."""
    redis_client = await get_redis()
    settings = get_settings()

    if feed_id:
        feed_ids = [feed_id]
    else:
        feed_ids = [f.feed_id for f in settings.transit_feeds if f.enabled]

    vehicles: list[dict[str, object]] = []
    for fid in feed_ids:
        feed_key = f"feed:{fid}:vehicles"
        vehicle_ids_raw: set[object] = await redis_client.smembers(feed_key)  # type: ignore[misc]
        vehicle_ids: list[str] = sorted(str(vid) for vid in vehicle_ids_raw)

        if not vehicle_ids:
            continue

        keys = [f"vehicle:{fid}:{vid}" for vid in vehicle_ids]
        values = await redis_client.mget(keys)

        for val in values:
            if val is None:
                continue
            data: dict[str, object] = json.loads(str(val))
            vehicles.append(data)

    return vehicles
