# pyright: reportUnknownMemberType=false, reportMissingTypeStubs=false
"""Background GTFS-RT poller that writes vehicle positions to Redis."""

import asyncio
import json
import time
from datetime import UTC, datetime

import httpx
from redis.asyncio import Redis

from app.core.agents.tools.transit.client import (
    GTFSRealtimeClient,
    TripUpdateData,
    VehiclePositionData,
)
from app.core.agents.tools.transit.static_cache import GTFSStaticCache, get_static_cache
from app.core.config import Settings, TransitFeedConfig, get_settings
from app.core.logging import get_logger
from app.core.redis import get_redis

logger = get_logger(__name__)


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
    ) -> None:
        self.feed_config = feed_config
        self._settings = settings
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
            static = await get_static_cache(self._http_client, self._settings)
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

        for vp in raw_vehicles:
            vehicle_data = self._enrich_vehicle(vp, trip_update_map, static)
            key = f"vehicle:{feed_id}:{vp.vehicle_id}"
            pipe.set(key, json.dumps(vehicle_data), ex=ttl)
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
        return count

    def _enrich_vehicle(
        self,
        vp: VehiclePositionData,
        trip_update_map: dict[str, TripUpdateData],
        static: GTFSStaticCache,
    ) -> dict[str, object]:
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


async def start_pollers() -> None:
    """Start background poller tasks for all enabled feeds."""
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

    feeds = [f for f in settings.transit_feeds if f.enabled]

    for feed_config in feeds:
        poller = FeedPoller(feed_config=feed_config, settings=settings)
        _feed_pollers.append(poller)
        task = asyncio.create_task(poller.run(redis_client))
        _poller_tasks.append(task)
        logger.info("transit.poller.feed_registered", feed_id=feed_config.feed_id)

    logger.info("transit.poller.all_started", feed_count=len(feeds))


async def stop_pollers() -> None:
    """Stop all poller tasks and close HTTP clients."""
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

    _poller_tasks.clear()
    _feed_pollers.clear()
    logger.info("transit.poller.all_stopped")
