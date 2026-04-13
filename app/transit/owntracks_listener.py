# pyright: reportUnknownMemberType=false, reportMissingTypeStubs=false
# pyright: reportUnknownVariableType=false, reportUnknownArgumentType=false
# pyright: reportUnnecessaryIsInstance=false
"""Background task that listens to OwnTracks MQTT for live phone-based positions.

Subscribes to OwnTracks location topics via MQTT, normalizes positions into
the same EnrichedVehicle format used by the GTFS-RT poller, and writes to
Redis + TimescaleDB + Pub/Sub. Requires phone-to-vehicle assignments in DB.
"""

import asyncio
import json
import time
from collections.abc import Callable
from contextlib import AbstractAsyncContextManager
from datetime import UTC, datetime
from urllib.parse import urlparse

import aiomqtt
from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.logging import get_logger
from app.core.redis import get_redis
from app.transit.models import VehiclePhoneAssignment

logger = get_logger(__name__)

FEED_ID = "owntracks"
OPERATOR_NAME = "OwnTracks"
ROUTE_TYPE = 3  # Bus

# Latvia bounding box for coordinate validation
_LAT_MIN, _LAT_MAX = 55.5, 58.1
_LON_MIN, _LON_MAX = 20.5, 28.3

_listener_task: asyncio.Task[None] | None = None

# In-memory cache: phone_identifier -> (assignment, monotonic_timestamp)
_assignment_cache: dict[str, tuple[VehiclePhoneAssignment, float]] = {}
_CACHE_TTL = 60.0  # seconds


async def _get_assignment(
    phone_id: str,
    db_factory: Callable[[], AbstractAsyncContextManager[AsyncSession]],
) -> VehiclePhoneAssignment | None:
    """Look up active phone assignment, using in-memory cache with TTL."""
    cached = _assignment_cache.get(phone_id)
    if cached and (time.monotonic() - cached[1]) < _CACHE_TTL:
        return cached[0]

    async with db_factory() as db:
        result = await db.execute(
            select(VehiclePhoneAssignment).where(
                VehiclePhoneAssignment.phone_identifier == phone_id,
                VehiclePhoneAssignment.active.is_(True),
            )
        )
        assignment = result.scalar_one_or_none()

    if assignment is not None:
        _assignment_cache[phone_id] = (assignment, time.monotonic())
    else:
        # Remove stale cache entry if assignment was deactivated
        _assignment_cache.pop(phone_id, None)

    return assignment


def _phone_id_from_topic(topic: str) -> str:
    """Extract phone identifier from MQTT topic: owntracks/{user}/{device} -> '{user}_{device}'."""
    parts = topic.split("/")
    if len(parts) >= 3:
        return f"{parts[-2]}_{parts[-1]}"
    return topic.replace("/", "_")


async def _process_message(
    topic: str,
    payload: bytes,
    redis_client: Redis,
    db_session_factory: Callable[[], AbstractAsyncContextManager[AsyncSession]],
    settings: Settings,
) -> None:
    """Parse a single OwnTracks message, write to Redis + TimescaleDB + Pub/Sub."""
    try:
        data = json.loads(payload)
    except (json.JSONDecodeError, TypeError) as e:
        logger.warning(
            "transit.owntracks.message_parse_failed",
            error=str(e),
        )
        return

    if not isinstance(data, dict):
        return

    # Only process location messages
    msg_type = data.get("_type")
    if msg_type != "location":
        return

    # Extract coordinates
    lat = data.get("lat")
    lon = data.get("lon")
    if lat is None or lon is None:
        logger.warning("transit.owntracks.missing_coords", topic=topic)
        return

    try:
        latitude = float(lat)
        longitude = float(lon)
    except (ValueError, TypeError):
        logger.warning("transit.owntracks.invalid_coords", topic=topic)
        return

    # Latvia bounding box validation
    if not (_LAT_MIN <= latitude <= _LAT_MAX and _LON_MIN <= longitude <= _LON_MAX):
        logger.warning(
            "transit.owntracks.coords_out_of_bounds",
            topic=topic,
            lat=latitude,
            lon=longitude,
        )
        return

    # Look up phone -> vehicle assignment
    phone_id = _phone_id_from_topic(topic)
    assignment = await _get_assignment(phone_id, db_session_factory)
    if assignment is None:
        logger.warning(
            "transit.owntracks.no_assignment",
            phone_id=phone_id,
        )
        return

    # Extract optional fields
    bearing: float | None = None
    bearing_raw = data.get("cog") or data.get("bearing")
    if bearing_raw is not None:
        try:
            bearing = float(bearing_raw)
        except (ValueError, TypeError):
            pass

    # OwnTracks vel is already in km/h
    speed_kmh: float | None = None
    vel_raw = data.get("vel")
    if vel_raw is not None:
        try:
            speed_kmh = round(float(vel_raw), 1)
        except (ValueError, TypeError):
            pass

    # Timestamp from OwnTracks (POSIX seconds)
    tst_raw = data.get("tst")
    now_iso = datetime.now(tz=UTC).isoformat()
    timestamp = now_iso
    if tst_raw is not None:
        try:
            timestamp = datetime.fromtimestamp(float(tst_raw), tz=UTC).isoformat()
        except (ValueError, TypeError, OSError):
            pass

    route_id = str(assignment.route_id) if assignment.route_id is not None else ""
    vehicle: dict[str, object] = {
        "vehicle_id": str(assignment.vehicle_id),
        "route_id": route_id,
        "route_short_name": "",
        "route_type": ROUTE_TYPE,
        "latitude": latitude,
        "longitude": longitude,
        "bearing": bearing,
        "speed_kmh": speed_kmh,
        "delay_seconds": 0,
        "trip_id": None,
        "current_status": "IN_TRANSIT_TO",
        "next_stop_name": None,
        "current_stop_name": None,
        "timestamp": timestamp,
        "feed_id": FEED_ID,
        "operator_name": OPERATOR_NAME,
    }

    vid = str(assignment.vehicle_id)
    logger.info(
        "transit.owntracks.message_received",
        phone_id=phone_id,
        vehicle_id=vid,
    )

    # Write to Redis
    ttl = settings.redis_vehicle_ttl_seconds
    pipe = redis_client.pipeline()
    key = f"vehicle:{FEED_ID}:{vid}"
    pipe.set(key, json.dumps(vehicle), ex=ttl)

    feed_key = f"feed:{FEED_ID}:vehicles"
    pipe.delete(feed_key)
    pipe.sadd(feed_key, vid)
    pipe.expire(feed_key, ttl)

    try:
        await pipe.execute()
    except Exception as e:
        logger.warning(
            "transit.owntracks.redis_write_failed",
            error=str(e),
            error_type=type(e).__name__,
        )

    # Write to TimescaleDB (non-blocking)
    if settings.position_history_enabled:
        try:
            async with db_session_factory() as db_session:
                from app.transit.repository import batch_insert_positions

                db_records: list[dict[str, object]] = [
                    {
                        "recorded_at": datetime.fromisoformat(str(timestamp)),
                        "feed_id": FEED_ID,
                        "vehicle_id": vid,
                        "route_id": route_id,
                        "route_short_name": "",
                        "trip_id": None,
                        "latitude": latitude,
                        "longitude": longitude,
                        "bearing": bearing,
                        "speed_kmh": speed_kmh,
                        "delay_seconds": 0,
                        "current_status": "IN_TRANSIT_TO",
                        "source": "owntracks",
                    },
                ]
                inserted = await batch_insert_positions(db_session, db_records)
                logger.info(
                    "transit.owntracks.history_write_completed",
                    records_inserted=inserted,
                )
        except Exception as e:
            logger.warning(
                "transit.owntracks.history_write_failed",
                error=str(e),
                error_type=type(e).__name__,
            )

    # Publish to Pub/Sub
    try:
        channel = f"transit:vehicles:{FEED_ID}"
        pub_payload = json.dumps(
            {
                "feed_id": FEED_ID,
                "count": 1,
                "vehicles": [vehicle],
                "timestamp": now_iso,
            }
        )
        await redis_client.publish(channel, pub_payload)
    except Exception as e:
        logger.warning(
            "transit.owntracks.pubsub_publish_failed",
            error=str(e),
            error_type=type(e).__name__,
        )


def _redact_broker_url(url: str) -> str:
    """Redact credentials from MQTT broker URL for safe logging."""
    parsed = urlparse(url)
    if parsed.password:
        return url.replace(parsed.password, "***")
    return url


async def _listen_loop(
    settings: Settings,
    *,
    _shutdown_event: asyncio.Event | None = None,
) -> None:
    """Main MQTT listener loop with reconnection and backoff."""
    backoff = 1.0
    max_backoff = float(settings.owntracks_mqtt_reconnect_max_seconds)
    broker_url = settings.owntracks_mqtt_broker_url
    topic_filter = settings.owntracks_mqtt_topic_filter

    from app.core.database import get_db_context

    db_session_factory = get_db_context

    # Parse broker URL
    parsed = urlparse(broker_url)
    hostname = parsed.hostname or "localhost"
    port = parsed.port or 1883

    while True:
        try:
            redis_client = await get_redis()
            async with aiomqtt.Client(
                hostname,
                port=port,
                username=settings.owntracks_mqtt_username,
                password=settings.owntracks_mqtt_password,
            ) as client:
                logger.info(
                    "transit.owntracks.connected",
                    broker=_redact_broker_url(broker_url),
                )
                backoff = 1.0

                await client.subscribe(topic_filter)

                async for message in client.messages:
                    topic_str = str(message.topic)
                    payload_bytes = (
                        message.payload
                        if isinstance(message.payload, bytes)
                        else str(message.payload).encode()
                    )
                    await _process_message(
                        topic_str,
                        payload_bytes,
                        redis_client,
                        db_session_factory,
                        settings,
                    )

        except asyncio.CancelledError:
            logger.info("transit.owntracks.listener_stopped")
            return

        except Exception as e:
            logger.warning(
                "transit.owntracks.reconnecting",
                error=str(e),
                error_type=type(e).__name__,
                backoff_seconds=backoff,
            )
            if _shutdown_event is not None and _shutdown_event.is_set():
                return
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, max_backoff)


async def start_owntracks_listener(settings: Settings) -> asyncio.Task[None]:
    """Create and return the OwnTracks MQTT listener background task."""
    global _listener_task
    _listener_task = asyncio.create_task(_listen_loop(settings))
    logger.info("transit.owntracks.listener_started")
    return _listener_task


async def stop_owntracks_listener() -> None:
    """Cancel the listener task and wait for cleanup."""
    global _listener_task
    if _listener_task is not None:
        _listener_task.cancel()
        try:
            await _listener_task
        except asyncio.CancelledError:
            pass
        except Exception:
            logger.warning("transit.owntracks.listener_stop_error", exc_info=True)
        _listener_task = None
