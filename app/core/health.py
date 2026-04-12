# pyright: reportUnknownMemberType=false, reportUntypedFunctionDecorator=false
"""Health check endpoints with deep dependency probing (OPS-2.2).

Provides liveness (`/health`), individual dependency checks (`/health/db`,
`/health/redis`), readiness (`/health/ready`), and deep health probing
(`/health/deep`) that runs all dependency probes concurrently and returns
a structured per-dependency status report.
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable
from datetime import UTC, datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request, status
from prometheus_client import REGISTRY
from pydantic import BaseModel, ConfigDict
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import require_role
from app.core.agents.circuit_breaker import CircuitState
from app.core.agents.llm import get_breaker_state
from app.core.config import Settings, get_settings
from app.core.database import get_db
from app.core.logging import get_logger
from app.core.rate_limit import limiter
from app.core.redis import get_redis

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------

HealthStatus = Literal["ok", "degraded", "down"]


class ProbeResult(BaseModel):
    """Result of a single dependency probe."""

    model_config = ConfigDict(frozen=True)

    name: str
    status: HealthStatus
    latency_ms: float
    detail: str | None = None
    critical: bool = True


class HealthReport(BaseModel):
    """Aggregated health report."""

    model_config = ConfigDict(frozen=True)

    status: HealthStatus
    version: str
    probes: list[ProbeResult]
    timestamp: str  # ISO 8601


# ---------------------------------------------------------------------------
# Module-level caches (backward compat for /health/db, /health/redis)
# ---------------------------------------------------------------------------

_db_health_cache: dict[str, str] | None = None
_db_health_cache_time: float = 0.0
_DB_HEALTH_CACHE_TTL: float = 10.0

_redis_health_cache: dict[str, str] | None = None
_redis_health_cache_time: float = 0.0
_REDIS_HEALTH_CACHE_TTL: float = 10.0

# Deep health cache
_deep_health_cache: HealthReport | None = None
_deep_health_cache_time: float = 0.0

# Ready cache
_ready_health_cache: dict[str, str] | None = None
_ready_health_cache_time: float = 0.0

# ---------------------------------------------------------------------------
# Prometheus gauge reader
# ---------------------------------------------------------------------------


def _get_poller_last_tick(poller_name: str) -> float | None:
    """Read the last tick timestamp from the Prometheus gauge."""
    for metric in REGISTRY.collect():
        if metric.name == "vtv_poller_last_tick_seconds":
            for sample in metric.samples:
                if sample.labels.get("poller_name") == poller_name:
                    return float(sample.value)
    return None


# ---------------------------------------------------------------------------
# Poller staleness thresholds
# ---------------------------------------------------------------------------


def _poller_staleness_thresholds(settings: Settings) -> dict[str, float]:
    """Return per-poller staleness thresholds in seconds.

    Daily crons get 25h (24h + 1h grace). Real-time pollers get 2x their
    configured interval.
    """
    feed_interval = (
        settings.transit_feeds[0].poll_interval_seconds * 2 if settings.transit_feeds else 120.0
    )
    return {
        "transit_feed": feed_interval,
        "alert_evaluator": settings.alerts_check_interval_seconds * 2,
        "geofence_evaluator": settings.geofence_check_interval_seconds * 2,
        "memory_compaction": 25 * 3600,  # daily + 1h grace
        "memory_promotion": 25 * 3600,  # daily + 1h grace
    }


# ---------------------------------------------------------------------------
# Individual probe functions
# ---------------------------------------------------------------------------


async def probe_postgres(db: AsyncSession) -> ProbeResult:
    """Probe PostgreSQL with SELECT 1 + active connection count."""
    start = time.monotonic()
    try:
        await db.execute(text("SELECT 1"))
        result = await db.execute(text("SELECT count(*) FROM pg_stat_activity"))
        row = result.scalar()
        active_conns = int(row) if row is not None else 0
        latency_ms = (time.monotonic() - start) * 1000
        return ProbeResult(
            name="postgres",
            status="ok",
            latency_ms=round(latency_ms, 2),
            detail=f"active_connections={active_conns}",
        )
    except Exception as exc:
        latency_ms = (time.monotonic() - start) * 1000
        logger.error("health.deep.probe_failed", probe="postgres", error=str(exc)[:200])
        return ProbeResult(
            name="postgres",
            status="down",
            latency_ms=round(latency_ms, 2),
            detail=str(exc)[:200],
        )


async def probe_redis() -> ProbeResult:
    """Probe Redis with PING."""
    start = time.monotonic()
    try:
        redis_client = await get_redis()
        await redis_client.ping()
        latency_ms = (time.monotonic() - start) * 1000
        return ProbeResult(
            name="redis",
            status="ok",
            latency_ms=round(latency_ms, 2),
        )
    except Exception as exc:
        latency_ms = (time.monotonic() - start) * 1000
        logger.error("health.deep.probe_failed", probe="redis", error=str(exc)[:200])
        return ProbeResult(
            name="redis",
            status="down",
            latency_ms=round(latency_ms, 2),
            detail=str(exc)[:200],
        )


async def probe_reranker() -> ProbeResult:
    """Probe reranker model load status (non-critical)."""
    start = time.monotonic()
    try:
        from app.knowledge.reranker import get_reranker_provider

        settings = get_settings()
        provider = get_reranker_provider(settings)
        model_loaded = hasattr(provider, "_model") and getattr(provider, "_model", None) is not None
        latency_ms = (time.monotonic() - start) * 1000
        return ProbeResult(
            name="reranker",
            status="ok" if model_loaded else "degraded",
            latency_ms=round(latency_ms, 2),
            detail="model_loaded" if model_loaded else "model_not_loaded",
            critical=False,
        )
    except Exception as exc:
        latency_ms = (time.monotonic() - start) * 1000
        return ProbeResult(
            name="reranker",
            status="degraded",
            latency_ms=round(latency_ms, 2),
            detail=str(exc)[:200],
            critical=False,
        )


async def probe_pollers() -> ProbeResult:
    """Probe background poller liveness via Prometheus gauges (non-critical)."""
    start = time.monotonic()
    settings = get_settings()
    thresholds = _poller_staleness_thresholds(settings)
    now = time.time()
    stale_pollers: list[str] = []
    checked = 0

    for poller_name, max_age in thresholds.items():
        last_tick = _get_poller_last_tick(poller_name)
        if last_tick is not None:
            checked += 1
            if (now - last_tick) > max_age:
                stale_pollers.append(poller_name)

    latency_ms = (time.monotonic() - start) * 1000

    if stale_pollers:
        return ProbeResult(
            name="pollers",
            status="degraded",
            latency_ms=round(latency_ms, 2),
            detail=f"stale: {', '.join(stale_pollers)}",
            critical=False,
        )

    return ProbeResult(
        name="pollers",
        status="ok",
        latency_ms=round(latency_ms, 2),
        detail=f"checked={checked}",
        critical=False,
    )


async def probe_gtfs_rt_feeds() -> ProbeResult:
    """Probe GTFS-RT feed freshness (non-critical)."""
    start = time.monotonic()
    last_tick = _get_poller_last_tick("transit_feed")
    latency_ms = (time.monotonic() - start) * 1000

    if last_tick is None:
        return ProbeResult(
            name="gtfs_rt_feeds",
            status="degraded",
            latency_ms=round(latency_ms, 2),
            detail="no_tick_recorded",
            critical=False,
        )

    age_s = time.time() - last_tick
    if age_s > 60.0:
        return ProbeResult(
            name="gtfs_rt_feeds",
            status="degraded",
            latency_ms=round(latency_ms, 2),
            detail=f"stale_seconds={age_s:.0f}",
            critical=False,
        )

    return ProbeResult(
        name="gtfs_rt_feeds",
        status="ok",
        latency_ms=round(latency_ms, 2),
        detail=f"age_seconds={age_s:.0f}",
        critical=False,
    )


async def probe_llm_providers() -> ProbeResult:
    """Probe LLM provider circuit breaker states (non-critical, no token cost)."""
    start = time.monotonic()
    settings = get_settings()
    providers: list[str] = [settings.llm_provider]
    if settings.llm_fallback_provider:
        providers.append(settings.llm_fallback_provider)

    states: dict[str, str] = {}
    any_open = False
    for provider_name in providers:
        state = get_breaker_state(provider_name)
        states[provider_name] = state.value
        if state == CircuitState.OPEN:
            any_open = True

    latency_ms = (time.monotonic() - start) * 1000
    detail_parts = [f"{name}={st}" for name, st in states.items()]

    return ProbeResult(
        name="llm_providers",
        status="degraded" if any_open else "ok",
        latency_ms=round(latency_ms, 2),
        detail=", ".join(detail_parts),
        critical=False,
    )


# ---------------------------------------------------------------------------
# Probe runner with timeout
# ---------------------------------------------------------------------------


async def _run_probe(
    name: str,
    coro: Awaitable[ProbeResult],
    timeout_s: float = 2.0,
) -> ProbeResult:
    """Run a probe with timeout protection.

    Args:
        name: Probe name (used in fallback result on timeout/error).
        coro: The coroutine task to await.
        timeout_s: Maximum seconds to wait.

    Returns:
        ProbeResult from the probe, or a synthetic "down"/"timeout" result.
    """
    try:
        return await asyncio.wait_for(coro, timeout=timeout_s)
    except TimeoutError:
        return ProbeResult(name=name, status="down", latency_ms=timeout_s * 1000, detail="timeout")
    except Exception as exc:
        logger.error("health.deep.probe_failed", probe=name, error=str(exc)[:200])
        return ProbeResult(name=name, status="down", latency_ms=0.0, detail=str(exc)[:200])


# ---------------------------------------------------------------------------
# Status aggregation
# ---------------------------------------------------------------------------


def _aggregate_status(probes: list[ProbeResult]) -> HealthStatus:
    """Aggregate probe results into an overall health status.

    - ``ok`` - all critical probes ok
    - ``degraded`` - all critical probes ok, but >= 1 non-critical not ok
    - ``down`` - any critical probe not ok
    """
    for p in probes:
        if p.critical and p.status != "ok":
            return "down"

    for p in probes:
        if not p.critical and p.status != "ok":
            return "degraded"

    return "ok"


# ---------------------------------------------------------------------------
# Router and endpoints
# ---------------------------------------------------------------------------

router = APIRouter(tags=["health"])


@router.get("/health")
@limiter.limit("60/minute")
async def health_check(request: Request) -> dict[str, str]:
    """Basic health check endpoint.

    Args:
        request: The incoming HTTP request (used for rate limiting).

    Returns:
        dict: Health status of the API service.

    Example response:
        {"status": "healthy", "service": "api"}
    """
    return {"status": "healthy", "service": "api"}


@router.get("/health/db")
@limiter.limit("60/minute")
async def database_health_check(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    """Database connectivity health check with 10s result caching.

    Caches successful results for 10 seconds to prevent connection pool
    exhaustion from frequent health check polling.

    Args:
        request: The incoming HTTP request (used for rate limiting).
        db: Database session dependency.

    Returns:
        dict: Health status of the database connection.

    Raises:
        HTTPException: 503 if database is not accessible.
    """
    global _db_health_cache, _db_health_cache_time
    now = time.monotonic()
    if _db_health_cache is not None and (now - _db_health_cache_time) < _DB_HEALTH_CACHE_TTL:
        return _db_health_cache

    try:
        await db.execute(text("SELECT 1"))
        result = {
            "status": "healthy",
            "service": "database",
        }
        _db_health_cache = result
        _db_health_cache_time = now
        return result
    except Exception as exc:
        _db_health_cache = None
        logger.error("database.health_check_failed", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database is not accessible",
        ) from exc


@router.get("/health/redis")
@limiter.limit("60/minute")
async def health_redis(request: Request) -> dict[str, str]:
    """Redis health check with 10s result caching.

    Args:
        request: The incoming HTTP request (used for rate limiting).

    Returns:
        dict: Health status of the Redis connection.

    Raises:
        HTTPException: 503 if Redis is not accessible.
    """
    global _redis_health_cache, _redis_health_cache_time
    now = time.monotonic()
    if (
        _redis_health_cache is not None
        and (now - _redis_health_cache_time) < _REDIS_HEALTH_CACHE_TTL
    ):
        return _redis_health_cache
    try:
        redis_client = await get_redis()
        result = await redis_client.ping()
        if not result:
            raise HTTPException(status_code=503, detail="Redis ping failed")
        _redis_health_cache = {"status": "healthy", "service": "redis"}
        _redis_health_cache_time = now
        return _redis_health_cache
    except HTTPException:
        raise
    except Exception as e:
        logger.error("redis.health_check_failed", error=str(e), exc_info=True)
        raise HTTPException(status_code=503, detail="Service dependency unavailable") from e


@router.get("/health/ready")
@limiter.limit("60/minute")
async def readiness_check(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    """Readiness check for all application dependencies.

    Runs postgres and redis probes concurrently. Returns the existing response
    format for backward compatibility with Docker healthchecks and monitoring.

    Args:
        request: The incoming HTTP request (used for rate limiting).
        db: Database session dependency.

    Returns:
        dict: Readiness status with dependency information.

    Raises:
        HTTPException: 503 if critical dependencies are not ready.
    """
    global _ready_health_cache, _ready_health_cache_time
    settings = get_settings()
    now = time.monotonic()
    if (
        _ready_health_cache is not None
        and (now - _ready_health_cache_time) < settings.health_deep_cache_ttl_seconds
    ):
        return _ready_health_cache

    try:
        pg_result, redis_result = await asyncio.gather(
            probe_postgres(db),
            probe_redis(),
        )

        if pg_result.status == "down":
            logger.error("health.readiness_check_failed", reason="postgres_down")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Application is not ready",
            )

        redis_status = "connected" if redis_result.status == "ok" else "unavailable"

        result = {
            "status": "ready",
            "database": "connected",
            "redis": redis_status,
        }
        _ready_health_cache = result
        _ready_health_cache_time = now
        return result
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("health.readiness_check_failed", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Application is not ready",
        ) from exc


@router.get("/health/deep")
@limiter.limit("60/minute")
async def deep_health_check(
    request: Request,
    db: AsyncSession = Depends(get_db),
    _current_user: object = Depends(require_role("admin")),
) -> HealthReport:
    """Deep health check with all dependency probes (admin-only).

    Runs all probes concurrently and returns a structured HealthReport.
    Returns 200 with status field indicating health (even when degraded).
    Returns 503 only when critical probes are down.

    Args:
        request: The incoming HTTP request (used for rate limiting).
        db: Database session dependency.
        _current_user: Admin user (injected by require_role).

    Returns:
        HealthReport with per-probe results and aggregate status.
    """
    global _deep_health_cache, _deep_health_cache_time
    settings = get_settings()
    now = time.monotonic()

    if (
        _deep_health_cache is not None
        and (now - _deep_health_cache_time) < settings.health_deep_cache_ttl_seconds
    ):
        if _deep_health_cache.status == "down":
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=_deep_health_cache.model_dump(),
            )
        return _deep_health_cache

    probes = await asyncio.gather(
        _run_probe("postgres", probe_postgres(db)),
        _run_probe("redis", probe_redis()),
        _run_probe("reranker", probe_reranker()),
        _run_probe("pollers", probe_pollers()),
        _run_probe("gtfs_rt_feeds", probe_gtfs_rt_feeds()),
        _run_probe("llm_providers", probe_llm_providers()),
    )

    probe_list = list(probes)

    for p in probe_list:
        logger.info(
            "health.deep.probe_completed",
            probe=p.name,
            status=p.status,
            latency_ms=p.latency_ms,
        )

    overall = _aggregate_status(probe_list)

    report = HealthReport(
        status=overall,
        version="0.1.0",
        probes=probe_list,
        timestamp=datetime.now(UTC).isoformat(),
    )

    _deep_health_cache = report
    _deep_health_cache_time = time.monotonic()

    logger.info(
        "health.deep.check_completed",
        status=overall,
        probe_count=len(probe_list),
    )

    if overall == "down":
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=report.model_dump(),
        )

    return report
