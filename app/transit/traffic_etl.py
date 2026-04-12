"""Traffic count and accident ETL from Latvian open data (ML-1.3).

Daily scheduled task fetches traffic census data and accident records,
parses CSV defensively, and upserts into traffic_counts + traffic_accidents.
Leader election via Redis SETNX prevents duplicate pulls across workers.
"""

from __future__ import annotations

import asyncio
import csv
import datetime
import io
import math
import os
import time
from typing import Any

import httpx
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.database import get_db_context
from app.core.logging import get_logger
from app.core.resilience import CircuitBreaker, CircuitOpenError

logger = get_logger(__name__)

_traffic_task: asyncio.Task[None] | None = None
_running = False

_traffic_breaker = CircuitBreaker(
    name="traffic-etl",
    failure_threshold=3,
    reset_timeout=300.0,
)

MAX_RESPONSE_BYTES = 50 * 1024 * 1024  # 50 MB cap


def _safe_float(value: str | None) -> float | None:
    """Parse a float from CSV, returning None for invalid values."""
    if value is None or value.strip() == "":
        return None
    try:
        f = float(value)
        if math.isnan(f) or math.isinf(f):
            return None
        return f
    except (ValueError, TypeError):
        return None


def _safe_int(value: str | None) -> int | None:
    """Parse an int from CSV, returning None for invalid values."""
    if value is None or value.strip() == "":
        return None
    try:
        return int(value)
    except (ValueError, TypeError):
        return None


def parse_traffic_counts_csv(text_data: str) -> list[dict[str, Any]]:
    """Parse traffic count CSV into records ready for upsert.

    Skips rows with missing point_id or period_start. Logs a warning
    per skipped row.

    Args:
        text_data: Raw CSV text from the traffic counts endpoint.

    Returns:
        List of dicts with keys: point_id, period_start, period_end,
        avg_count_per_day, vehicle_class, latitude, longitude.
    """
    records: list[dict[str, Any]] = []
    reader = csv.DictReader(io.StringIO(text_data))
    for row_num, row in enumerate(reader, start=2):
        point_id = (row.get("point_id") or "").strip()
        period_start = (row.get("period_start") or "").strip()
        if not point_id or not period_start:
            logger.warning(
                "transit.traffic.count_row_skipped",
                row_num=row_num,
                reason="missing point_id or period_start",
            )
            continue

        avg_count = _safe_float(row.get("avg_count_per_day"))
        if avg_count is None:
            logger.warning(
                "transit.traffic.count_row_skipped",
                row_num=row_num,
                reason="invalid avg_count_per_day",
            )
            continue

        records.append(
            {
                "point_id": point_id,
                "period_start": period_start,
                "period_end": (row.get("period_end") or period_start).strip(),
                "avg_count_per_day": avg_count,
                "vehicle_class": (row.get("vehicle_class") or "").strip() or None,
                "latitude": _safe_float(row.get("latitude")),
                "longitude": _safe_float(row.get("longitude")),
            }
        )

    return records


def parse_traffic_accidents_csv(text_data: str) -> list[dict[str, Any]]:
    """Parse traffic accident CSV into records ready for upsert.

    Skips rows with missing source_id or occurred_at. Logs a warning
    per skipped row.

    Args:
        text_data: Raw CSV text from the accident dataset.

    Returns:
        List of dicts with keys: source_id, occurred_at, severity,
        fatalities, injuries, latitude, longitude.
    """
    records: list[dict[str, Any]] = []
    reader = csv.DictReader(io.StringIO(text_data))
    for row_num, row in enumerate(reader, start=2):
        source_id = (row.get("source_id") or "").strip()
        occurred_at = (row.get("occurred_at") or "").strip()
        if not source_id or not occurred_at:
            logger.warning(
                "transit.traffic.accident_row_skipped",
                row_num=row_num,
                reason="missing source_id or occurred_at",
            )
            continue

        records.append(
            {
                "source_id": source_id,
                "occurred_at": occurred_at,
                "severity": (row.get("severity") or "unknown").strip(),
                "fatalities": _safe_int(row.get("fatalities")) or 0,
                "injuries": _safe_int(row.get("injuries")) or 0,
                "latitude": _safe_float(row.get("latitude")),
                "longitude": _safe_float(row.get("longitude")),
            }
        )

    return records


async def upsert_traffic_counts(
    db: AsyncSession,
    records: list[dict[str, Any]],
) -> int:
    """Insert or update traffic counts using ON CONFLICT.

    Args:
        db: Async database session.
        records: Parsed traffic count dicts.

    Returns:
        Number of rows affected.
    """
    if not records:
        return 0

    count = 0
    for rec in records:
        lat = rec.get("latitude")
        lon = rec.get("longitude")
        location_expr = (
            f"ST_SetSRID(ST_MakePoint({lon}, {lat}), 4326)::geography"
            if lat is not None and lon is not None
            else "NULL"
        )

        stmt = text(
            f"INSERT INTO traffic_counts "  # noqa: S608
            f"(point_id, period_start, period_end, avg_count_per_day, "
            f"vehicle_class, location) "
            f"VALUES (:point_id, :period_start, :period_end, :avg_count_per_day, "
            f":vehicle_class, {location_expr}) "
            f"ON CONFLICT (point_id, period_start, period_end, vehicle_class) "
            f"DO UPDATE SET "
            f"avg_count_per_day = EXCLUDED.avg_count_per_day, "
            f"location = COALESCE(EXCLUDED.location, traffic_counts.location)"
        )
        await db.execute(
            stmt,
            {
                "point_id": rec["point_id"],
                "period_start": rec["period_start"],
                "period_end": rec["period_end"],
                "avg_count_per_day": rec["avg_count_per_day"],
                "vehicle_class": rec.get("vehicle_class"),
            },
        )
        count += 1

    await db.commit()
    return count


async def upsert_traffic_accidents(
    db: AsyncSession,
    records: list[dict[str, Any]],
) -> int:
    """Insert or update traffic accidents using ON CONFLICT.

    Args:
        db: Async database session.
        records: Parsed accident dicts.

    Returns:
        Number of rows affected.
    """
    if not records:
        return 0

    count = 0
    for rec in records:
        lat = rec.get("latitude")
        lon = rec.get("longitude")
        location_expr = (
            f"ST_SetSRID(ST_MakePoint({lon}, {lat}), 4326)::geography"
            if lat is not None and lon is not None
            else "NULL"
        )

        stmt = text(
            f"INSERT INTO traffic_accidents "  # noqa: S608
            f"(source_id, occurred_at, severity, fatalities, injuries, location) "
            f"VALUES (:source_id, :occurred_at, :severity, :fatalities, "
            f":injuries, {location_expr}) "
            f"ON CONFLICT (source_id) DO UPDATE SET "
            f"occurred_at = EXCLUDED.occurred_at, "
            f"severity = EXCLUDED.severity, "
            f"fatalities = EXCLUDED.fatalities, "
            f"injuries = EXCLUDED.injuries, "
            f"location = COALESCE(EXCLUDED.location, traffic_accidents.location)"
        )
        await db.execute(
            stmt,
            {
                "source_id": rec["source_id"],
                "occurred_at": rec["occurred_at"],
                "severity": rec["severity"],
                "fatalities": rec["fatalities"],
                "injuries": rec["injuries"],
            },
        )
        count += 1

    await db.commit()
    return count


async def pull_traffic_counts(
    http_client: httpx.AsyncClient,
    settings: Settings,
) -> int:
    """Fetch and upsert traffic counts from data.lvceli.lv.

    Args:
        http_client: Shared async HTTP client.
        settings: Application settings with traffic URLs.

    Returns:
        Number of records upserted.
    """
    start = time.monotonic()

    resp = await http_client.get(settings.traffic_counts_url, timeout=120.0)
    resp.raise_for_status()
    if len(resp.content) > MAX_RESPONSE_BYTES:
        logger.warning(
            "transit.traffic.counts_response_too_large",
            size_bytes=len(resp.content),
            limit_bytes=MAX_RESPONSE_BYTES,
        )
        return 0

    csv_text = resp.content.decode("utf-8", errors="replace")
    records = parse_traffic_counts_csv(csv_text)

    async with get_db_context() as db:
        count = await upsert_traffic_counts(db, records)

    duration_ms = round((time.monotonic() - start) * 1000)
    logger.info(
        "transit.traffic.counts_pull_completed",
        count=count,
        duration_ms=duration_ms,
    )
    return count


async def pull_traffic_accidents(
    http_client: httpx.AsyncClient,
    settings: Settings,
) -> int:
    """Fetch and upsert traffic accidents from CAIS dataset.

    Args:
        http_client: Shared async HTTP client.
        settings: Application settings with accident URL.

    Returns:
        Number of records upserted.
    """
    start = time.monotonic()

    resp = await http_client.get(settings.traffic_accidents_url, timeout=120.0)
    resp.raise_for_status()
    if len(resp.content) > MAX_RESPONSE_BYTES:
        logger.warning(
            "transit.traffic.accidents_response_too_large",
            size_bytes=len(resp.content),
            limit_bytes=MAX_RESPONSE_BYTES,
        )
        return 0

    csv_text = resp.content.decode("utf-8", errors="replace")
    records = parse_traffic_accidents_csv(csv_text)

    async with get_db_context() as db:
        count = await upsert_traffic_accidents(db, records)

    duration_ms = round((time.monotonic() - start) * 1000)
    logger.info(
        "transit.traffic.accidents_pull_completed",
        count=count,
        duration_ms=duration_ms,
    )
    return count


async def _run_daily_traffic_pull() -> None:
    """Background loop: run traffic ETL daily at the configured hour."""
    global _running
    settings = get_settings()

    from app.core.redis import get_redis

    redis = await get_redis()
    worker_id = str(os.getpid())

    # Try to acquire leader lock
    acquired = await redis.set(
        "vtv:traffic_etl:leader",
        worker_id,
        nx=True,
        ex=3600,
    )
    if not acquired:
        logger.info("transit.traffic.not_leader", worker_id=worker_id)
        return

    logger.info("transit.traffic.leader_acquired", worker_id=worker_id)
    _running = True

    while _running:
        # Wait until the target hour
        now = datetime.datetime.now(datetime.UTC)
        target = now.replace(
            hour=settings.traffic_etl_cron_hour,
            minute=0,
            second=0,
            microsecond=0,
        )
        if target <= now:
            target += datetime.timedelta(days=1)
        wait_seconds = (target - now).total_seconds()
        logger.info(
            "transit.traffic.next_run",
            wait_seconds=int(wait_seconds),
            target_hour=settings.traffic_etl_cron_hour,
        )
        await asyncio.sleep(wait_seconds)

        if not _running:
            break

        async with httpx.AsyncClient() as http_client:
            try:
                async with _traffic_breaker:
                    if settings.traffic_counts_url:
                        await pull_traffic_counts(http_client, settings)
                    if settings.traffic_accidents_url:
                        await pull_traffic_accidents(http_client, settings)
                logger.info("transit.traffic.cycle_completed")
            except CircuitOpenError:
                logger.warning("transit.traffic.circuit_open")
            except Exception:
                logger.warning("transit.traffic.cycle_failed", exc_info=True)

        # Refresh leader lock
        try:
            await redis.expire("vtv:traffic_etl:leader", 3600)
        except Exception:
            logger.warning("transit.traffic.leader_refresh_failed", exc_info=True)

    # Release leader lock on exit
    try:
        await redis.delete("vtv:traffic_etl:leader")
    except Exception:
        logger.debug("transit.traffic.leader_release_failed", exc_info=True)


async def start_traffic_etl() -> None:
    """Start the traffic ETL background task if enabled."""
    global _traffic_task
    settings = get_settings()

    if not settings.traffic_etl_enabled:
        logger.info("transit.traffic.lifecycle_disabled")
        return

    _traffic_task = asyncio.create_task(_run_daily_traffic_pull())
    logger.info("transit.traffic.lifecycle_started")


async def stop_traffic_etl() -> None:
    """Stop the traffic ETL background task."""
    global _traffic_task, _running
    _running = False

    if _traffic_task is not None:
        _traffic_task.cancel()
        try:
            await _traffic_task
        except asyncio.CancelledError:
            pass
        except RuntimeError:
            pass
        _traffic_task = None
        logger.info("transit.traffic.lifecycle_stopped")


async def backfill_traffic_counts() -> int:
    """One-shot backfill of traffic count data.

    Returns:
        Total records upserted.
    """
    settings = get_settings()
    if not settings.traffic_counts_url:
        logger.warning(
            "transit.traffic.backfill_counts_skipped",
            reason="no URL configured",
        )
        return 0

    logger.info("transit.traffic.backfill_counts_started")
    start = time.monotonic()

    async with httpx.AsyncClient() as http_client:
        count = await pull_traffic_counts(http_client, settings)

    duration_ms = round((time.monotonic() - start) * 1000)
    logger.info(
        "transit.traffic.backfill_counts_completed",
        count=count,
        duration_ms=duration_ms,
    )
    return count


async def backfill_traffic_accidents() -> int:
    """One-shot backfill of traffic accident data.

    Returns:
        Total records upserted.
    """
    settings = get_settings()
    if not settings.traffic_accidents_url:
        logger.warning(
            "transit.traffic.backfill_accidents_skipped",
            reason="no URL configured",
        )
        return 0

    logger.info("transit.traffic.backfill_accidents_started")
    start = time.monotonic()

    async with httpx.AsyncClient() as http_client:
        count = await pull_traffic_accidents(http_client, settings)

    duration_ms = round((time.monotonic() - start) * 1000)
    logger.info(
        "transit.traffic.backfill_accidents_completed",
        count=count,
        duration_ms=duration_ms,
    )
    return count
