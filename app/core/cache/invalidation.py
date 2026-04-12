# pyright: reportUnknownMemberType=false, reportMissingTypeStubs=false
"""Cache invalidation utilities for entity mutations.

Provides namespaced key deletion and pattern-based scanning to invalidate
stale Redis caches when upstream data changes in the database.
"""

from __future__ import annotations

import time

from redis.asyncio import Redis

from app.core.config import get_settings
from app.core.logging import get_logger
from app.core.metrics import REDIS_CACHE_INVALIDATIONS
from app.core.redis import get_redis

logger = get_logger(__name__)

# Namespace definitions - central registry of cache key prefixes
NAMESPACES: dict[str, str] = {
    "stops": "stops:*",
    "routes": "routes:*",
    "vehicles:position": "vehicle:*",
    "geofences:spatial": "geofences:spatial:*",
}


class CacheInvalidator:
    """Invalidate Redis cache keys by exact key or namespace pattern.

    Uses SCAN (never KEYS) to find matching keys, deleting in batches
    to avoid blocking Redis. All operations are fire-and-forget safe -
    cache invalidation failures are logged but never raise.
    """

    def __init__(self, redis: Redis | None = None) -> None:
        self._redis = redis

    async def _get_redis(self) -> Redis:
        if self._redis is not None:
            return self._redis
        return await get_redis()

    async def invalidate(self, namespace: str, *keys: str) -> int:
        """Delete exact cache keys within a namespace.

        Args:
            namespace: Cache namespace (e.g., "stops", "vehicles:position").
            *keys: Exact Redis key names to delete.

        Returns:
            Number of keys actually deleted.
        """
        if not keys:
            return 0
        start = time.monotonic()
        deleted = 0
        try:
            redis = await self._get_redis()
            result = await redis.delete(*keys)
            deleted = int(result)
            duration_ms = (time.monotonic() - start) * 1000
            logger.info(
                "cache.invalidation.performed",
                namespace=namespace,
                keys_invalidated=deleted,
                key_count=len(keys),
                duration_ms=round(duration_ms, 2),
            )
            _record_metric(namespace, deleted)
        except Exception:
            logger.warning(
                "cache.invalidation.failed",
                namespace=namespace,
                key_count=len(keys),
                exc_info=True,
            )
        return deleted

    async def invalidate_pattern(
        self, pattern: str, *, namespace: str = "", batch_size: int = 100
    ) -> int:
        """Delete all keys matching a glob pattern using SCAN + DEL.

        Scans in batches to avoid blocking Redis for long periods.

        Args:
            pattern: Redis glob pattern (e.g., "stops:*").
            namespace: Namespace label for logging/metrics.
            batch_size: Keys per SCAN iteration.

        Returns:
            Total number of keys deleted.
        """
        start = time.monotonic()
        deleted = 0
        try:
            redis = await self._get_redis()
            cursor: int = 0
            while True:
                cursor, keys = await redis.scan(cursor, match=pattern, count=batch_size)
                if keys:
                    result = await redis.delete(*keys)
                    deleted += int(result)
                if cursor == 0:
                    break
            duration_ms = (time.monotonic() - start) * 1000
            logger.info(
                "cache.invalidation.performed",
                namespace=namespace or pattern,
                keys_invalidated=deleted,
                pattern=pattern,
                duration_ms=round(duration_ms, 2),
            )
            _record_metric(namespace or pattern, deleted)
        except Exception:
            logger.warning(
                "cache.invalidation.failed",
                namespace=namespace or pattern,
                pattern=pattern,
                exc_info=True,
            )
        return deleted


# Module-level convenience functions for repository hooks


async def invalidate_stop_cache(stop_id: int | None = None) -> int:
    """Invalidate stop-related caches after a stop mutation.

    Args:
        stop_id: Specific stop ID, or None to invalidate all stops.

    Returns:
        Number of keys invalidated.
    """
    inv = CacheInvalidator()
    if stop_id is not None:
        return await inv.invalidate("stops", f"stops:{stop_id}")
    return await inv.invalidate_pattern("stops:*", namespace="stops")


async def invalidate_geofence_cache() -> int:
    """Invalidate all geofence spatial caches after a geofence mutation.

    Returns:
        Number of keys invalidated.
    """
    inv = CacheInvalidator()
    return await inv.invalidate_pattern("geofences:spatial:*", namespace="geofences:spatial")


async def invalidate_vehicle_position_cache(
    feed_id: str | None = None, vehicle_id: str | None = None
) -> int:
    """Invalidate vehicle position caches.

    Args:
        feed_id: Feed to invalidate, or None for all feeds.
        vehicle_id: Specific vehicle, or None for all in feed.

    Returns:
        Number of keys invalidated.
    """
    inv = CacheInvalidator()
    if feed_id and vehicle_id:
        return await inv.invalidate("vehicles:position", f"vehicle:{feed_id}:{vehicle_id}")
    if feed_id:
        return await inv.invalidate_pattern(f"vehicle:{feed_id}:*", namespace="vehicles:position")
    return await inv.invalidate_pattern("vehicle:*", namespace="vehicles:position")


async def invalidate_route_cache() -> int:
    """Invalidate all route-related caches after a route mutation.

    Returns:
        Number of keys invalidated.
    """
    inv = CacheInvalidator()
    return await inv.invalidate_pattern("routes:*", namespace="routes")


def _record_metric(namespace: str, count: int) -> None:
    """Record cache invalidation in Prometheus counter."""
    if not get_settings().metrics_enabled:
        return
    REDIS_CACHE_INVALIDATIONS.labels(cache_name=namespace).inc(count)
