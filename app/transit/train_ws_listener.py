# pyright: reportUnknownMemberType=false, reportMissingTypeStubs=false
"""Background task that listens to PV train WebSocket for live train positions.

Connects to wss://trainmap.pv.lv/ws (configurable via TRAIN_WS_URL),
normalizes train positions into the same EnrichedVehicle format used by
the GTFS-RT poller, and writes to Redis + TimescaleDB + Pub/Sub.
"""

import asyncio
import json
from collections.abc import Callable
from contextlib import AbstractAsyncContextManager
from datetime import UTC, datetime
from typing import cast

import websockets
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.logging import get_logger
from app.core.redis import get_redis

logger = get_logger(__name__)

FEED_ID = "pv_trains"
OPERATOR_NAME = "Pasažieru vilciens"
ROUTE_TYPE = 2  # Rail

_listener_task: asyncio.Task[None] | None = None


async def _process_message(
    raw: str,
    redis_client: Redis,
    db_session_factory: Callable[[], AbstractAsyncContextManager[AsyncSession]],
    settings: Settings,
) -> None:
    """Parse a single WS message, write to Redis + TimescaleDB + Pub/Sub."""
    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, TypeError) as e:
        logger.warning(
            "transit.train_ws.message_parse_failed",
            error=str(e),
            raw_snippet=raw[:200],
        )
        return

    # The PV WebSocket sends either a single train dict or a list of trains.
    # Normalize to a list for uniform processing.
    trains: list[dict[str, object]]
    if isinstance(data, list):
        trains = cast(list[dict[str, object]], data)
    elif isinstance(data, dict):
        trains = [cast(dict[str, object], data)]
    else:
        logger.warning(
            "transit.train_ws.message_parse_failed",
            error="unexpected_message_type",
            raw_snippet=str(data)[:200],
        )
        return

    if not trains:
        return

    enriched_vehicles: list[dict[str, object]] = []
    now_iso = datetime.now(tz=UTC).isoformat()

    for train in trains:
        train_id = train.get("id") or train.get("train_id") or train.get("vehicle_id")
        lat = train.get("lat") or train.get("latitude")
        lng = train.get("lng") or train.get("lon") or train.get("longitude")

        if train_id is None or lat is None or lng is None:
            continue

        try:
            latitude = float(str(lat))
            longitude = float(str(lng))
        except (ValueError, TypeError):
            continue

        bearing_raw = train.get("bearing") or train.get("heading")
        bearing: float | None = None
        if bearing_raw is not None:
            try:
                bearing = float(str(bearing_raw))
            except (ValueError, TypeError):
                pass

        speed_raw = train.get("speed") or train.get("speed_kmh")
        speed_kmh: float | None = None
        if speed_raw is not None:
            try:
                speed_kmh = round(float(str(speed_raw)), 1)
            except (ValueError, TypeError):
                pass

        route_name = str(train.get("route", "") or train.get("route_name", "") or "")
        route_id = str(train.get("route_id", "") or train.get("route", "") or "")
        trip_id = str(train.get("trip_id", "")) if train.get("trip_id") else None
        delay_raw = train.get("delay") or train.get("delay_seconds")
        delay_seconds = 0
        if delay_raw is not None:
            try:
                delay_seconds = int(float(str(delay_raw)))
            except (ValueError, TypeError):
                pass

        ts_raw = train.get("timestamp") or train.get("time")
        timestamp = now_iso
        if ts_raw is not None:
            try:
                timestamp = datetime.fromtimestamp(float(str(ts_raw)), tz=UTC).isoformat()
            except (ValueError, TypeError, OSError):
                pass

        vehicle: dict[str, object] = {
            "vehicle_id": str(train_id),
            "route_id": route_id,
            "route_short_name": route_name,
            "route_type": ROUTE_TYPE,
            "latitude": latitude,
            "longitude": longitude,
            "bearing": bearing,
            "speed_kmh": speed_kmh,
            "delay_seconds": delay_seconds,
            "trip_id": trip_id,
            "current_status": "IN_TRANSIT_TO",
            "next_stop_name": None,
            "current_stop_name": None,
            "timestamp": timestamp,
            "feed_id": FEED_ID,
            "operator_name": OPERATOR_NAME,
        }
        enriched_vehicles.append(vehicle)

    if not enriched_vehicles:
        return

    logger.info(
        "transit.train_ws.message_received",
        count=len(enriched_vehicles),
    )

    # Write to Redis
    ttl = settings.redis_vehicle_ttl_seconds
    pipe = redis_client.pipeline()
    vehicle_ids: list[str] = []
    for ev in enriched_vehicles:
        vid = str(ev["vehicle_id"])
        key = f"vehicle:{FEED_ID}:{vid}"
        pipe.set(key, json.dumps(ev), ex=ttl)
        vehicle_ids.append(vid)

    feed_key = f"feed:{FEED_ID}:vehicles"
    if vehicle_ids:
        pipe.delete(feed_key)
        pipe.sadd(feed_key, *vehicle_ids)
        pipe.expire(feed_key, ttl)

    try:
        await pipe.execute()
    except Exception as e:
        logger.warning(
            "transit.train_ws.redis_write_failed",
            error=str(e),
            error_type=type(e).__name__,
        )

    # Write to TimescaleDB (non-blocking)
    if settings.position_history_enabled:
        try:
            async with db_session_factory() as db_session:
                from app.transit.repository import batch_insert_positions

                db_records: list[dict[str, object]] = []
                for ev in enriched_vehicles:
                    ts = ev.get("timestamp")
                    if not ts:
                        continue
                    db_records.append(
                        {
                            "recorded_at": datetime.fromisoformat(str(ts)),
                            "feed_id": FEED_ID,
                            "vehicle_id": str(ev["vehicle_id"]),
                            "route_id": str(ev.get("route_id", "")),
                            "route_short_name": str(ev.get("route_short_name", "")),
                            "trip_id": ev.get("trip_id"),
                            "latitude": ev["latitude"],
                            "longitude": ev["longitude"],
                            "bearing": ev.get("bearing"),
                            "speed_kmh": ev.get("speed_kmh"),
                            "delay_seconds": ev.get("delay_seconds", 0),
                            "current_status": str(ev.get("current_status", "")),
                        }
                    )
                if db_records:
                    inserted = await batch_insert_positions(db_session, db_records)
                    logger.info(
                        "transit.train_ws.history_write_completed",
                        records_inserted=inserted,
                    )
        except Exception as e:
            # History write failure must NEVER block the listener
            logger.warning(
                "transit.train_ws.history_write_failed",
                error=str(e),
                error_type=type(e).__name__,
            )

    # Publish to Pub/Sub
    try:
        channel = f"transit:vehicles:{FEED_ID}"
        payload = json.dumps(
            {
                "feed_id": FEED_ID,
                "count": len(enriched_vehicles),
                "vehicles": enriched_vehicles,
                "timestamp": now_iso,
            }
        )
        await redis_client.publish(channel, payload)
    except Exception as e:
        logger.warning(
            "transit.train_ws.pubsub_publish_failed",
            error=str(e),
            error_type=type(e).__name__,
        )


async def _listen_loop(
    settings: Settings,
    *,
    _shutdown_event: asyncio.Event | None = None,
) -> None:
    """Main WebSocket listener loop with reconnection and backoff.

    Args:
        settings: Application settings.
        _shutdown_event: Optional event for testing — when set, the loop exits
            after the current iteration instead of looping forever.
    """
    backoff = 1.0
    max_backoff = float(settings.train_ws_reconnect_max_seconds)
    url = settings.train_ws_url
    first_message = True

    from app.core.database import get_db_context

    db_session_factory = get_db_context

    while True:
        try:
            redis_client = await get_redis()
            async with websockets.connect(
                url,
                ping_interval=20,
                ping_timeout=10,
                close_timeout=5,
            ) as ws:
                logger.info("transit.train_ws.connected", url=url)
                backoff = 1.0  # Reset on successful connection

                async for message in ws:
                    raw = str(message)
                    if first_message:
                        logger.info(
                            "transit.train_ws.first_message",
                            raw_snippet=raw[:500],
                        )
                        first_message = False

                    await _process_message(raw, redis_client, db_session_factory, settings)

        except asyncio.CancelledError:
            logger.info("transit.train_ws.listener_stopped")
            return

        except Exception as e:
            logger.warning(
                "transit.train_ws.reconnecting",
                error=str(e),
                error_type=type(e).__name__,
                backoff_seconds=backoff,
            )
            if _shutdown_event is not None and _shutdown_event.is_set():
                return
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, max_backoff)


async def start_train_ws_listener(settings: Settings) -> asyncio.Task[None]:
    """Create and return the train WS listener background task."""
    global _listener_task
    _listener_task = asyncio.create_task(_listen_loop(settings))
    logger.info("transit.train_ws.listener_started")
    return _listener_task


async def stop_train_ws_listener() -> None:
    """Cancel the listener task and wait for cleanup."""
    global _listener_task
    if _listener_task is not None:
        _listener_task.cancel()
        try:
            await _listener_task
        except asyncio.CancelledError:
            pass
        except Exception:
            logger.warning("transit.train_ws.listener_stop_error", exc_info=True)
        _listener_task = None
