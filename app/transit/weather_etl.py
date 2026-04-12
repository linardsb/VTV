"""Weather observation ETL from data.gov.lv (ML-1.3).

Hourly polling loop fetches CSV weather data, parses it defensively,
and upserts into weather_stations + weather_observations tables.
Leader election via Redis SETNX prevents duplicate pulls across workers.
"""

from __future__ import annotations

import asyncio
import csv
import io
import json
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

_weather_task: asyncio.Task[None] | None = None
_running = False

_weather_breaker = CircuitBreaker(
    name="weather-etl",
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


def parse_weather_csv(text_data: str) -> list[dict[str, Any]]:
    """Parse weather observation CSV into records ready for upsert.

    Skips rows with missing station_id or observed_at. Logs a warning
    per skipped row. Non-numeric temperature/wind/precip fields are
    set to None rather than crashing.

    Args:
        text_data: Raw CSV text from the weather observations endpoint.

    Returns:
        List of dicts with keys: station_id, observed_at, temp_c,
        wind_mps, precip_mm, latitude, longitude.
    """
    records: list[dict[str, Any]] = []
    reader = csv.DictReader(io.StringIO(text_data))
    for row_num, row in enumerate(reader, start=2):
        station_id = (row.get("station_id") or "").strip()
        observed_at = (row.get("observed_at") or "").strip()
        if not station_id or not observed_at:
            logger.warning(
                "transit.weather.row_skipped",
                row_num=row_num,
                reason="missing station_id or observed_at",
            )
            continue

        records.append(
            {
                "station_id": station_id,
                "observed_at": observed_at,
                "temp_c": _safe_float(row.get("temp_c")),
                "wind_mps": _safe_float(row.get("wind_mps")),
                "precip_mm": _safe_float(row.get("precip_mm")),
                "latitude": _safe_float(row.get("latitude")),
                "longitude": _safe_float(row.get("longitude")),
            }
        )

    return records


def parse_phenomena_csv(text_data: str) -> dict[str, dict[str, Any]]:
    """Parse road weather phenomena CSV into a lookup by station+timestamp.

    Args:
        text_data: Raw CSV text from the phenomena endpoint.

    Returns:
        Dict keyed by "station_id|observed_at" with phenomena data.
    """
    lookup: dict[str, dict[str, Any]] = {}
    reader = csv.DictReader(io.StringIO(text_data))
    for row in reader:
        station_id = (row.get("station_id") or "").strip()
        observed_at = (row.get("observed_at") or "").strip()
        if not station_id or not observed_at:
            continue
        key = f"{station_id}|{observed_at}"
        phenomena: dict[str, Any] = {}
        for col_name, col_value in row.items():
            if col_name not in ("station_id", "observed_at") and col_value:
                phenomena[col_name] = col_value
        if phenomena:
            lookup[key] = phenomena

    return lookup


async def upsert_observations(
    db: AsyncSession,
    records: list[dict[str, Any]],
) -> int:
    """Insert or update weather observations using ON CONFLICT.

    Args:
        db: Async database session.
        records: Parsed weather observation dicts.

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

        phenomena_val = rec.get("phenomena")
        phenomena_json = json.dumps(phenomena_val) if phenomena_val else None

        stmt = text(
            f"INSERT INTO weather_observations "  # noqa: S608
            f"(station_id, observed_at, temp_c, wind_mps, precip_mm, phenomena, location) "
            f"VALUES (:station_id, :observed_at, :temp_c, :wind_mps, :precip_mm, "
            f":phenomena::jsonb, {location_expr}) "
            f"ON CONFLICT (station_id, observed_at) DO UPDATE SET "
            f"temp_c = COALESCE(EXCLUDED.temp_c, weather_observations.temp_c), "
            f"wind_mps = COALESCE(EXCLUDED.wind_mps, weather_observations.wind_mps), "
            f"precip_mm = COALESCE(EXCLUDED.precip_mm, weather_observations.precip_mm), "
            f"phenomena = COALESCE(EXCLUDED.phenomena, weather_observations.phenomena), "
            f"location = COALESCE(EXCLUDED.location, weather_observations.location)"
        )
        await db.execute(
            stmt,
            {
                "station_id": rec["station_id"],
                "observed_at": rec["observed_at"],
                "temp_c": rec.get("temp_c"),
                "wind_mps": rec.get("wind_mps"),
                "precip_mm": rec.get("precip_mm"),
                "phenomena": phenomena_json,
            },
        )
        count += 1

    await db.commit()
    return count


async def pull_meteo_observations(
    http_client: httpx.AsyncClient,
    settings: Settings,
) -> int:
    """Fetch and upsert weather observations from data.gov.lv.

    Args:
        http_client: Shared async HTTP client.
        settings: Application settings with weather URLs.

    Returns:
        Number of records upserted.
    """
    start = time.monotonic()

    # Fetch observations CSV
    resp = await http_client.get(
        settings.weather_observations_url,
        timeout=60.0,
    )
    resp.raise_for_status()
    if len(resp.content) > MAX_RESPONSE_BYTES:
        logger.warning(
            "transit.weather.response_too_large",
            size_bytes=len(resp.content),
            limit_bytes=MAX_RESPONSE_BYTES,
        )
        return 0

    obs_text = resp.content.decode("utf-8", errors="replace")
    records = parse_weather_csv(obs_text)

    # Fetch phenomena CSV (optional, merge into observations)
    if settings.weather_phenomena_url:
        try:
            phen_resp = await http_client.get(
                settings.weather_phenomena_url,
                timeout=60.0,
            )
            phen_resp.raise_for_status()
            phen_text = phen_resp.content.decode("utf-8", errors="replace")
            phenomena_lookup = parse_phenomena_csv(phen_text)

            for rec in records:
                phen_key = f"{rec['station_id']}|{rec['observed_at']}"
                if phen_key in phenomena_lookup:
                    rec["phenomena"] = phenomena_lookup[phen_key]
        except httpx.HTTPError:
            logger.warning("transit.weather.phenomena_fetch_failed", exc_info=True)

    # Upsert into database
    async with get_db_context() as db:
        count = await upsert_observations(db, records)

    duration_ms = round((time.monotonic() - start) * 1000)
    logger.info(
        "transit.weather.pull_completed",
        count=count,
        duration_ms=duration_ms,
    )
    return count


async def _weather_poll_loop() -> None:
    """Background loop: fetch weather observations on an interval."""
    global _running
    settings = get_settings()

    from app.core.redis import get_redis

    redis = await get_redis()
    worker_id = str(os.getpid())

    # Try to acquire leader lock
    acquired = await redis.set(
        "vtv:weather_etl:leader",
        worker_id,
        nx=True,
        ex=settings.weather_etl_leader_lock_ttl,
    )
    if not acquired:
        logger.info("transit.weather.not_leader", worker_id=worker_id)
        return

    logger.info("transit.weather.leader_acquired", worker_id=worker_id)
    _running = True

    async with httpx.AsyncClient() as http_client:
        while _running:
            try:
                async with _weather_breaker:
                    await pull_meteo_observations(http_client, settings)
                logger.info("transit.weather.cycle_completed")
            except CircuitOpenError:
                logger.warning("transit.weather.circuit_open")
            except Exception:
                logger.warning("transit.weather.cycle_failed", exc_info=True)

            # Refresh leader lock
            try:
                await redis.expire(
                    "vtv:weather_etl:leader",
                    settings.weather_etl_leader_lock_ttl,
                )
            except Exception:
                logger.warning("transit.weather.leader_refresh_failed", exc_info=True)

            await asyncio.sleep(settings.weather_etl_interval_seconds)

    # Release leader lock on exit
    try:
        await redis.delete("vtv:weather_etl:leader")
    except Exception:
        logger.debug("transit.weather.leader_release_failed", exc_info=True)


async def start_weather_etl() -> None:
    """Start the weather ETL background task if enabled."""
    global _weather_task
    settings = get_settings()

    if not settings.weather_etl_enabled:
        logger.info("transit.weather.lifecycle_disabled")
        return

    _weather_task = asyncio.create_task(_weather_poll_loop())
    logger.info("transit.weather.lifecycle_started")


async def stop_weather_etl() -> None:
    """Stop the weather ETL background task."""
    global _weather_task, _running
    _running = False

    if _weather_task is not None:
        _weather_task.cancel()
        try:
            await _weather_task
        except asyncio.CancelledError:
            pass
        except RuntimeError:
            pass
        _weather_task = None
        logger.info("transit.weather.lifecycle_stopped")


async def backfill_weather(days: int = 365) -> int:
    """One-shot backfill of historical weather observations.

    Args:
        days: Number of days of history to fetch.

    Returns:
        Total records upserted.
    """
    settings = get_settings()
    if not settings.weather_observations_url:
        logger.warning("transit.weather.backfill_skipped", reason="no URL configured")
        return 0

    logger.info("transit.weather.backfill_started", days=days)
    start = time.monotonic()

    async with httpx.AsyncClient() as http_client:
        count = await pull_meteo_observations(http_client, settings)

    duration_ms = round((time.monotonic() - start) * 1000)
    logger.info(
        "transit.weather.backfill_completed",
        count=count,
        duration_ms=duration_ms,
    )
    return count
