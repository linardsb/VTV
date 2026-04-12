# pyright: reportUnknownMemberType=false, reportMissingTypeStubs=false
"""Tests for traffic count and accident ETL (ML-1.3)."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.transit.traffic_etl import (
    parse_traffic_accidents_csv,
    parse_traffic_counts_csv,
    start_traffic_etl,
    stop_traffic_etl,
    upsert_traffic_accidents,
    upsert_traffic_counts,
)

# --- CSV parsing tests ---


def test_parse_traffic_counts_csv_valid() -> None:
    """Happy path: rows parsed correctly."""
    csv_text = (
        "point_id,period_start,period_end,avg_count_per_day,vehicle_class,latitude,longitude\n"
        "P001,2025-01-01,2025-12-31,1500.5,car,56.95,24.11\n"
        "P002,2025-06-01,2025-06-30,800.0,,57.15,24.85\n"
    )
    records = parse_traffic_counts_csv(csv_text)
    assert len(records) == 2
    assert records[0]["point_id"] == "P001"
    assert records[0]["avg_count_per_day"] == 1500.5
    assert records[0]["vehicle_class"] == "car"
    assert records[1]["vehicle_class"] is None


def test_parse_traffic_counts_csv_skips_missing_fields() -> None:
    """Rows without point_id or period_start are skipped."""
    csv_text = (
        "point_id,period_start,period_end,avg_count_per_day\n"
        ",2025-01-01,2025-12-31,100.0\n"
        "P001,,2025-12-31,200.0\n"
        "P002,2025-01-01,2025-12-31,300.0\n"
    )
    records = parse_traffic_counts_csv(csv_text)
    assert len(records) == 1
    assert records[0]["point_id"] == "P002"


def test_parse_traffic_accidents_csv_valid() -> None:
    """Happy path with severity and location."""
    csv_text = (
        "source_id,occurred_at,severity,fatalities,injuries,latitude,longitude\n"
        "ACC001,2025-03-15T14:30:00Z,serious,0,2,56.95,24.11\n"
        "ACC002,2025-04-01T08:00:00Z,fatal,1,3,57.15,24.85\n"
    )
    records = parse_traffic_accidents_csv(csv_text)
    assert len(records) == 2
    assert records[0]["source_id"] == "ACC001"
    assert records[0]["severity"] == "serious"
    assert records[0]["injuries"] == 2
    assert records[1]["fatalities"] == 1


def test_parse_traffic_accidents_csv_skips_missing_fields() -> None:
    """Rows without source_id or occurred_at are skipped."""
    csv_text = (
        "source_id,occurred_at,severity,fatalities,injuries\n"
        ",2025-03-15T14:30:00Z,minor,0,1\n"
        "ACC001,2025-03-15T14:30:00Z,minor,0,1\n"
    )
    records = parse_traffic_accidents_csv(csv_text)
    assert len(records) == 1
    assert records[0]["source_id"] == "ACC001"


# --- Upsert tests ---


@pytest.mark.asyncio
async def test_upsert_traffic_counts_empty_noop() -> None:
    """Empty input returns 0."""
    db = AsyncMock()
    result = await upsert_traffic_counts(db, [])
    assert result == 0
    db.execute.assert_not_called()


@pytest.mark.asyncio
async def test_upsert_traffic_counts_calls_db() -> None:
    """Records are upserted and committed."""
    db = AsyncMock()
    records = [
        {
            "point_id": "P001",
            "period_start": "2025-01-01",
            "period_end": "2025-12-31",
            "avg_count_per_day": 1500.0,
            "vehicle_class": "car",
            "latitude": 56.95,
            "longitude": 24.11,
        }
    ]
    result = await upsert_traffic_counts(db, records)
    assert result == 1
    db.execute.assert_called_once()
    db.commit.assert_called_once()


@pytest.mark.asyncio
async def test_upsert_traffic_accidents_empty_noop() -> None:
    """Empty input returns 0."""
    db = AsyncMock()
    result = await upsert_traffic_accidents(db, [])
    assert result == 0
    db.execute.assert_not_called()


@pytest.mark.asyncio
async def test_upsert_traffic_accidents_calls_db() -> None:
    """Records are upserted and committed."""
    db = AsyncMock()
    records = [
        {
            "source_id": "ACC001",
            "occurred_at": "2025-03-15T14:30:00Z",
            "severity": "serious",
            "fatalities": 0,
            "injuries": 2,
            "latitude": 56.95,
            "longitude": 24.11,
        }
    ]
    result = await upsert_traffic_accidents(db, records)
    assert result == 1
    db.execute.assert_called_once()
    db.commit.assert_called_once()


# --- Scheduled task tests ---


@pytest.mark.asyncio
async def test_start_traffic_etl_creates_task_when_enabled() -> None:
    """Task is created when traffic_etl_enabled=True."""
    mock_settings = MagicMock()
    mock_settings.traffic_etl_enabled = True

    with (
        patch("app.transit.traffic_etl.get_settings", return_value=mock_settings),
        patch("app.transit.traffic_etl.asyncio.create_task") as mock_create,
    ):
        mock_create.return_value = MagicMock()
        await start_traffic_etl()
        mock_create.assert_called_once()


@pytest.mark.asyncio
async def test_start_traffic_etl_skips_when_disabled() -> None:
    """No task created when traffic_etl_enabled=False."""
    mock_settings = MagicMock()
    mock_settings.traffic_etl_enabled = False

    with (
        patch("app.transit.traffic_etl.get_settings", return_value=mock_settings),
        patch("app.transit.traffic_etl.asyncio.create_task") as mock_create,
    ):
        await start_traffic_etl()
        mock_create.assert_not_called()


@pytest.mark.asyncio
async def test_stop_traffic_etl_cancels_task() -> None:
    """Task is cancelled and awaited on stop."""
    import app.transit.traffic_etl as mod

    async def _noop() -> None:
        pass

    task = asyncio.create_task(_noop())
    await task  # let it complete so cancel is safe
    mod._traffic_task = task
    mod._running = True

    await stop_traffic_etl()

    assert mod._traffic_task is None
    assert mod._running is False
