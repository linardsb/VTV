# pyright: reportUnknownMemberType=false, reportMissingTypeStubs=false
"""Background GTFS-RT poller that writes vehicle positions to Redis."""

import asyncio
import json
import time
from collections.abc import Callable
from contextlib import AbstractAsyncContextManager
from datetime import UTC, datetime
from typing import TypedDict

import httpx
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.agents.tools.transit.client import (
    GTFSRealtimeClient,
    TripUpdateData,
    VehiclePositionData,
)
from app.core.agents.tools.transit.static_cache import GTFSStaticCache
from app.core.agents.tools.transit.static_store import get_static_store
from app.core.config import Settings, TransitFeedConfig, get_settings
from app.core.logging import get_logger
from app.core.redis import get_redis

logger = get_logger(__name__)


class EnrichedVehicle(TypedDict):
    """Enriched vehicle position dict for Redis serialization."""

    vehicle_id: str
    route_id: str
    route_short_name: str
    route_type: int
    latitude: float
    longitude: float
    bearing: float | None
    speed_kmh: float | None
    delay_seconds: int
    trip_id: str | None
    current_status: str
    next_stop_name: str | None
    current_stop_name: str | None
    timestamp: str
    feed_id: str
    operator_name: str


class FeedPoller:
    """Polls a single GTFS-RT feed and writes positions to Redis.

    Args:
        feed_config: Configuration for the feed to poll.
        settings: Application settings for cache TTL and feed URLs.
    """

    def __init__(
        self,
        feed_config: TransitFeedConfig,
        settings: Settings,
        db_session_factory: Callable[[], AbstractAsyncContextManager[AsyncSession]] | None = None,
    ) -> None:
        self.feed_config = feed_config
        self._settings = settings
        self._db_session_factory = db_session_factory
        self._http_client = httpx.AsyncClient(
            timeout=httpx.Timeout(10.0, connect=5.0),
            limits=httpx.Limits(max_connections=5, max_keepalive_connections=3),
        )
        self._rt_client = GTFSRealtimeClient(http_client=self._http_client, settings=settings)
        self._running = False

    async def close(self) -> None:
        """Close HTTP client resources."""
        self._running = False
        try:
            await self._http_client.aclose()
        except RuntimeError:
            pass

    async def poll_once(self, redis_client: Redis) -> int:
        """Fetch positions from feed, write to Redis. Returns vehicle count."""
        feed_id = self.feed_config.feed_id
        try:
            raw_vehicles = await self._rt_client.fetch_vehicle_positions()
            trip_updates = await self._rt_client.fetch_trip_updates()
            if self._db_session_factory is None:
                from app.core.database import get_db_context

                self._db_session_factory = get_db_context
            static = await get_static_store(self._db_session_factory, self._settings)
        except Exception as e:
            logger.error(
                "transit.poller.fetch_failed",
                feed_id=feed_id,
                error=str(e),
                error_type=type(e).__name__,
                exc_info=True,
            )
            return 0

        trip_update_map: dict[str, TripUpdateData] = {tu.trip_id: tu for tu in trip_updates}
        ttl = self._settings.redis_vehicle_ttl_seconds
        pipe = redis_client.pipeline()
        count = 0

        enriched_vehicles: list[EnrichedVehicle] = []
        for vp in raw_vehicles:
            vehicle_data = self._enrich_vehicle(vp, trip_update_map, static)
            key = f"vehicle:{feed_id}:{vp.vehicle_id}"
            pipe.set(key, json.dumps(vehicle_data), ex=ttl)
            enriched_vehicles.append(vehicle_data)
            count += 1

        # Track which vehicles belong to this feed (set with TTL)
        feed_key = f"feed:{feed_id}:vehicles"
        vehicle_ids = [vp.vehicle_id for vp in raw_vehicles]
        if vehicle_ids:
            pipe.delete(feed_key)
            pipe.sadd(feed_key, *vehicle_ids)
            pipe.expire(feed_key, ttl)

        try:
            await pipe.execute()
        except Exception as e:
            logger.error(
                "transit.poller.redis_write_failed",
                feed_id=feed_id,
                error=str(e),
                error_type=type(e).__name__,
            )
            return 0

        # Write to historical position storage (TimescaleDB)
        if (
            self._settings.position_history_enabled
            and count > 0
            and self._db_session_factory is not None
        ):
            try:
                async with self._db_session_factory() as db_session:
                    from app.transit.repository import batch_insert_positions

                    db_records: list[dict[str, object]] = []
                    for ev in enriched_vehicles:
                        if not ev["timestamp"]:
                            continue
                        db_records.append(
                            {
                                "recorded_at": ev["timestamp"],
                                "feed_id": ev["feed_id"],
                                "vehicle_id": ev["vehicle_id"],
                                "route_id": ev["route_id"],
                                "route_short_name": ev["route_short_name"],
                                "trip_id": ev["trip_id"],
                                "latitude": ev["latitude"],
                                "longitude": ev["longitude"],
                                "bearing": ev["bearing"],
                                "speed_kmh": ev["speed_kmh"],
                                "delay_seconds": ev["delay_seconds"],
                                "current_status": ev["current_status"],
                            }
                        )
                    if db_records:
                        inserted = await batch_insert_positions(db_session, db_records)
                        logger.info(
                            "transit.poller.history_write_completed",
                            feed_id=feed_id,
                            records_inserted=inserted,
                        )
            except Exception as e:
                # History write failure must NEVER block the poller
                logger.warning(
                    "transit.poller.history_write_failed",
                    feed_id=feed_id,
                    error=str(e),
                    error_type=type(e).__name__,
                )

        # Publish vehicle update to Pub/Sub channel for WebSocket subscribers
        if count > 0:
            try:
                channel = f"transit:vehicles:{feed_id}"
                payload = json.dumps(
                    {
                        "feed_id": feed_id,
                        "count": count,
                        "vehicles": enriched_vehicles,
                        "timestamp": datetime.now(tz=UTC).isoformat(),
                    }
                )
                await redis_client.publish(channel, payload)
            except Exception as e:
                # Pub/Sub failure must never block the poller
                logger.warning(
                    "transit.poller.pubsub_publish_failed",
                    feed_id=feed_id,
                    error=str(e),
                    error_type=type(e).__name__,
                )

        return count

    def _enrich_vehicle(
        self,
        vp: VehiclePositionData,
        trip_update_map: dict[str, TripUpdateData],
        static: GTFSStaticCache,
    ) -> EnrichedVehicle:
        """Enrich a raw vehicle position into a serializable dict."""
        # Resolve route_id (explicit from GTFS-RT, or via trip lookup)
        route_id = vp.route_id or ""
        if not route_id and vp.trip_id:
            resolved = static.get_trip_route_id(vp.trip_id)
            route_id = resolved if resolved else ""

        route_name = static.get_route_name(route_id) if route_id else ""
        route_info = static.routes.get(route_id)
        route_type = route_info.route_type if route_info else 3

        # Extract delay from trip updates
        delay_seconds = 0
        if vp.trip_id and vp.trip_id in trip_update_map:
            tu = trip_update_map[vp.trip_id]
            matching = [
                stu
                for stu in tu.stop_time_updates
                if stu.stop_sequence >= (vp.current_stop_sequence or 0)
            ]
            if matching:
                first = matching[0]
                delay_seconds = (
                    (first.arrival_delay or 0)
                    if first.arrival_delay != 0
                    else (first.departure_delay or 0)
                )

        speed_kmh = round(vp.speed * 3.6, 1) if vp.speed is not None else None
        next_stop = static.get_stop_name(vp.stop_id) if vp.stop_id else None
        timestamp = datetime.fromtimestamp(vp.timestamp, tz=UTC).isoformat() if vp.timestamp else ""

        return {
            "vehicle_id": vp.vehicle_id,
            "route_id": route_id,
            "route_short_name": route_name,
            "route_type": route_type,
            "latitude": vp.latitude,
            "longitude": vp.longitude,
            "bearing": vp.bearing,
            "speed_kmh": speed_kmh,
            "delay_seconds": delay_seconds,
            "trip_id": vp.trip_id,
            "current_status": vp.current_status,
            "next_stop_name": next_stop,
            "current_stop_name": static.get_stop_name(vp.stop_id) if vp.stop_id else None,
            "timestamp": timestamp,
            "feed_id": self.feed_config.feed_id,
            "operator_name": self.feed_config.operator_name,
        }

    async def run(self, redis_client: Redis) -> None:
        """Run the polling loop for this feed."""
        feed_id = self.feed_config.feed_id
        interval = self.feed_config.poll_interval_seconds
        self._running = True
        logger.info("transit.poller.started", feed_id=feed_id, interval_seconds=interval)

        while self._running:
            start = time.monotonic()
            count = await self.poll_once(redis_client)
            duration_ms = round((time.monotonic() - start) * 1000)
            logger.info(
                "transit.poller.cycle_completed",
                feed_id=feed_id,
                vehicle_count=count,
                duration_ms=duration_ms,
            )
            await asyncio.sleep(interval)


_poller_tasks: list[asyncio.Task[None]] = []
_feed_pollers: list[FeedPoller] = []
_leader_refresh_task: asyncio.Task[None] | None = None
_is_leader = False


async def _try_acquire_leader_lock(redis_client: Redis, ttl: int) -> bool:
    """Attempt to acquire the poller leader lock via Redis SETNX.

    With multiple Gunicorn workers, each runs start_pollers() on startup.
    Only the winner should actually start polling to avoid duplicate GTFS-RT requests.

    Returns True if this worker is the leader.
    """
    import os

    worker_id = str(os.getpid())
    acquired = await redis_client.set(
        "vtv:poller:leader",
        worker_id,
        nx=True,
        ex=ttl,
    )
    return bool(acquired)


async def _refresh_leader_lock(redis_client: Redis, ttl: int) -> None:
    """Background task: refresh the leader lock every ttl/2 seconds."""
    refresh_interval = ttl // 2
    while True:
        try:
            await asyncio.sleep(refresh_interval)
            await redis_client.expire("vtv:poller:leader", ttl)
        except asyncio.CancelledError:
            break
        except Exception:
            logger.warning("transit.poller.leader_refresh_failed", exc_info=True)


async def _release_leader_lock(redis_client: Redis) -> None:
    """Release the leader lock on shutdown."""
    try:
        await redis_client.delete("vtv:poller:leader")
    except Exception:
        logger.debug("transit.poller.leader_release_failed", exc_info=True)


async def start_pollers() -> None:
    """Start background poller tasks for all enabled feeds.

    Uses Redis-based leader election so only one worker runs pollers
    in a multi-worker Gunicorn deployment.
    """
    global _leader_refresh_task, _is_leader

    settings = get_settings()
    if not settings.poller_enabled:
        logger.info("transit.poller.disabled")
        return

    try:
        redis_client = await get_redis()
    except Exception as e:
        logger.error(
            "transit.poller.redis_unavailable",
            error=str(e),
            error_type=type(e).__name__,
        )
        return

    # Leader election: only one worker starts pollers
    ttl = settings.poller_leader_lock_ttl
    try:
        is_leader = await _try_acquire_leader_lock(redis_client, ttl)
    except Exception as e:
        # Redis auth failure or connection issue — skip leader election,
        # fall through to start pollers (single-worker behavior)
        logger.warning(
            "transit.poller.leader_election_failed",
            error=str(e),
            error_type=type(e).__name__,
            detail="Starting pollers without leader lock (single-worker fallback)",
        )
        is_leader = True

    if not is_leader:
        logger.info("transit.poller.not_leader", reason="another_worker_holds_lock")
        return

    _is_leader = True
    logger.info("transit.poller.leader_elected")

    # Start leader lock refresh task (skip if leader election was bypassed)
    try:
        _leader_refresh_task = asyncio.create_task(_refresh_leader_lock(redis_client, ttl))
    except Exception:
        logger.warning("transit.poller.leader_refresh_setup_failed", exc_info=True)

    feeds = [f for f in settings.transit_feeds if f.enabled]

    for feed_config in feeds:
        poller = FeedPoller(feed_config=feed_config, settings=settings)
        _feed_pollers.append(poller)
        task = asyncio.create_task(poller.run(redis_client))
        _poller_tasks.append(task)
        logger.info("transit.poller.feed_registered", feed_id=feed_config.feed_id)

    logger.info("transit.poller.all_started", feed_count=len(feeds))


async def stop_pollers() -> None:
    """Stop all poller tasks, close HTTP clients, and release leader lock."""
    global _leader_refresh_task, _is_leader

    # Cancel leader refresh task
    if _leader_refresh_task is not None:
        _leader_refresh_task.cancel()
        try:
            await _leader_refresh_task
        except asyncio.CancelledError:
            pass
        except Exception:
            logger.debug("transit.poller.leader_refresh_cleanup_error", exc_info=True)
        _leader_refresh_task = None

    for poller in _feed_pollers:
        poller._running = False

    for task in _poller_tasks:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
        except Exception:
            logger.debug("transit.poller.task_cleanup_error", exc_info=True)

    for poller in _feed_pollers:
        await poller.close()

    # Release leader lock
    if _is_leader:
        try:
            redis_client = await get_redis()
            await _release_leader_lock(redis_client)
        except Exception:
            logger.debug("transit.poller.leader_release_failed", exc_info=True)
        _is_leader = False

    _poller_tasks.clear()
    _feed_pollers.clear()
    logger.info("transit.poller.all_stopped")
