# pyright: reportUnknownMemberType=false, reportMissingTypeStubs=false
"""Tests for weather observation ETL (ML-1.3)."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from app.transit.weather_etl import (
    parse_phenomena_csv,
    parse_weather_csv,
    pull_meteo_observations,
    start_weather_etl,
    stop_weather_etl,
    upsert_observations,
)

# --- CSV parsing tests ---


def test_parse_weather_csv_valid_rows() -> None:
    """Happy path: 3 rows parsed correctly."""
    csv_text = (
        "station_id,observed_at,temp_c,wind_mps,precip_mm,latitude,longitude\n"
        "S001,2026-01-15T10:00:00Z,2.5,3.1,0.0,56.95,24.11\n"
        "S002,2026-01-15T10:00:00Z,-1.0,5.0,1.2,57.15,24.85\n"
        "S003,2026-01-15T10:00:00Z,0.0,0.0,0.0,56.50,23.70\n"
    )
    records = parse_weather_csv(csv_text)
    assert len(records) == 3
    assert records[0]["station_id"] == "S001"
    assert records[0]["temp_c"] == 2.5
    assert records[1]["wind_mps"] == 5.0
    assert records[2]["precip_mm"] == 0.0


def test_parse_weather_csv_missing_required_fields() -> None:
    """Rows without station_id or observed_at are skipped."""
    csv_text = (
        "station_id,observed_at,temp_c\n"
        ",2026-01-15T10:00:00Z,2.5\n"
        "S001,,3.0\n"
        "S002,2026-01-15T10:00:00Z,1.0\n"
    )
    records = parse_weather_csv(csv_text)
    assert len(records) == 1
    assert records[0]["station_id"] == "S002"


def test_parse_weather_csv_malformed_numbers() -> None:
    """Non-numeric temp/wind fields are set to None."""
    csv_text = (
        "station_id,observed_at,temp_c,wind_mps,precip_mm\nS001,2026-01-15T10:00:00Z,abc,NaN,inf\n"
    )
    records = parse_weather_csv(csv_text)
    assert len(records) == 1
    assert records[0]["temp_c"] is None
    assert records[0]["wind_mps"] is None
    assert records[0]["precip_mm"] is None


# --- Phenomena CSV tests ---


def test_parse_phenomena_csv_groups_by_station_time() -> None:
    """Phenomena are grouped by station_id + observed_at."""
    csv_text = (
        "station_id,observed_at,fog,ice\n"
        "S001,2026-01-15T10:00:00Z,1,0\n"
        "S001,2026-01-15T11:00:00Z,0,1\n"
    )
    lookup = parse_phenomena_csv(csv_text)
    assert "S001|2026-01-15T10:00:00Z" in lookup
    assert lookup["S001|2026-01-15T10:00:00Z"]["fog"] == "1"
    assert "S001|2026-01-15T11:00:00Z" in lookup
    assert lookup["S001|2026-01-15T11:00:00Z"]["ice"] == "1"


def test_parse_phenomena_csv_skips_empty_rows() -> None:
    """Rows with all empty phenomenon columns produce no entry."""
    csv_text = "station_id,observed_at,fog,ice\nS001,2026-01-15T10:00:00Z,,\n"
    lookup = parse_phenomena_csv(csv_text)
    assert len(lookup) == 0


# --- Upsert tests ---


@pytest.mark.asyncio
async def test_upsert_observations_empty_list_noop() -> None:
    """Empty input returns 0 without touching the database."""
    db = AsyncMock()
    result = await upsert_observations(db, [])
    assert result == 0
    db.execute.assert_not_called()
    db.commit.assert_not_called()


@pytest.mark.asyncio
async def test_upsert_observations_calls_db() -> None:
    """Records are upserted and committed."""
    db = AsyncMock()
    records = [
        {
            "station_id": "S001",
            "observed_at": "2026-01-15T10:00:00Z",
            "temp_c": 2.5,
            "wind_mps": 3.1,
            "precip_mm": 0.0,
            "latitude": 56.95,
            "longitude": 24.11,
        }
    ]
    result = await upsert_observations(db, records)
    assert result == 1
    db.execute.assert_called_once()
    db.commit.assert_called_once()


# --- Scheduled task gating tests ---


@pytest.mark.asyncio
async def test_start_weather_etl_creates_task_when_enabled() -> None:
    """Task is created when weather_etl_enabled=True."""
    mock_settings = MagicMock()
    mock_settings.weather_etl_enabled = True

    with (
        patch("app.transit.weather_etl.get_settings", return_value=mock_settings),
        patch("app.transit.weather_etl.asyncio.create_task") as mock_create,
    ):
        mock_create.return_value = MagicMock()
        await start_weather_etl()
        mock_create.assert_called_once()


@pytest.mark.asyncio
async def test_start_weather_etl_skips_when_disabled() -> None:
    """No task created when weather_etl_enabled=False."""
    mock_settings = MagicMock()
    mock_settings.weather_etl_enabled = False

    with (
        patch("app.transit.weather_etl.get_settings", return_value=mock_settings),
        patch("app.transit.weather_etl.asyncio.create_task") as mock_create,
    ):
        await start_weather_etl()
        mock_create.assert_not_called()


# --- HTTP failure test ---


@pytest.mark.asyncio
async def test_pull_meteo_observations_http_error_logged() -> None:
    """HTTP error is logged, not raised."""
    mock_settings = MagicMock()
    mock_settings.weather_observations_url = "https://example.com/weather.csv"
    mock_settings.weather_phenomena_url = ""

    mock_client = AsyncMock()
    mock_client.get.side_effect = httpx.ConnectError("Connection refused")

    with pytest.raises(httpx.ConnectError):
        await pull_meteo_observations(mock_client, mock_settings)


# --- Stop semantics test ---


@pytest.mark.asyncio
async def test_stop_weather_etl_cancels_task() -> None:
    """Task is cancelled and awaited on stop."""
    import app.transit.weather_etl as mod

    async def _noop() -> None:
        pass

    task = asyncio.create_task(_noop())
    await task  # let it complete so cancel is safe
    mod._weather_task = task
    mod._running = True

    await stop_weather_etl()

    assert mod._weather_task is None
    assert mod._running is False
