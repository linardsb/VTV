# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false
"""Tests for e-ticket load correlation and feature extraction (ML-3.1)."""

from __future__ import annotations

import datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pandas as pd
import pytest

from app.ml.features.load_features import (
    correlate_taps_to_stops,
    extract_load_features,
)
from app.ml.features.tests.conftest import SAMPLE_OBSERVED_AT, make_correlated_tap

# SQL dispatch patterns (order matters: check more specific patterns first)
_UNCORRELATED = "NOT EXISTS"
_CORRELATE = "JOIN LATERAL"
_TOTAL_TAPS = "COUNT(*) AS total"
_CAPACITY = "v.fleet_number, v.capacity"


def _make_settings(**overrides: Any) -> MagicMock:
    """Create a mock Settings object with ML load defaults."""
    settings = MagicMock()
    settings.ml_load_time_window_seconds = overrides.get("window", 60)
    settings.ml_load_distance_threshold_m = overrides.get("distance", 100.0)
    settings.ml_load_batch_size = overrides.get("batch_size", 10000)
    settings.ml_load_min_correlation_pct = overrides.get("min_corr", 80.0)
    return settings


def _build_mock_db(
    correlated_rows: list[dict[str, Any]] | None = None,
    total_taps: int = 10,
    uncorrelated: int = 0,
    capacity_rows: list[dict[str, Any]] | None = None,
) -> AsyncMock:
    """Build a mock DB session with substring-matched SQL dispatch.

    Args:
        correlated_rows: Rows returned by correlation query.
        total_taps: Total e-ticket count.
        uncorrelated: Uncorrelated e-ticket count.
        capacity_rows: Rows returned by capacity query.

    Returns:
        AsyncMock configured as a DB session.
    """
    db = AsyncMock()

    def _execute_side_effect(stmt: Any, params: Any = None) -> MagicMock:
        _ = params
        sql_str = str(stmt.text) if hasattr(stmt, "text") else str(stmt)

        result = MagicMock()
        mappings = MagicMock()

        if _UNCORRELATED in sql_str:
            mappings.first.return_value = {"uncorrelated": uncorrelated}
            result.mappings.return_value = mappings
        elif _CORRELATE in sql_str:
            mappings.all.return_value = correlated_rows or []
            result.mappings.return_value = mappings
        elif _TOTAL_TAPS in sql_str:
            mappings.first.return_value = {"total": total_taps}
            result.mappings.return_value = mappings
        elif _CAPACITY in sql_str:
            mappings.all.return_value = capacity_rows or []
            result.mappings.return_value = mappings
        else:
            mappings.all.return_value = []
            mappings.first.return_value = None
            result.mappings.return_value = mappings

        return result

    db.execute = AsyncMock(side_effect=_execute_side_effect)
    return db


class TestCorrelateTapsToStops:
    async def test_single_tap_matches_position(self) -> None:
        tap = make_correlated_tap()
        db = _build_mock_db(correlated_rows=[tap], total_taps=1, uncorrelated=0)
        settings = _make_settings()

        df = await correlate_taps_to_stops(db, SAMPLE_OBSERVED_AT, SAMPLE_OBSERVED_AT, settings)

        assert len(df) == 1
        assert df.iloc[0]["vehicle_number"] == "4521"
        assert df.iloc[0]["gtfs_trip_id"] == "trip_001"

    async def test_no_position_in_window_returns_empty(self) -> None:
        db = _build_mock_db(correlated_rows=[], total_taps=5, uncorrelated=5)
        settings = _make_settings()

        df = await correlate_taps_to_stops(db, SAMPLE_OBSERVED_AT, SAMPLE_OBSERVED_AT, settings)

        assert df.empty

    async def test_nearest_stop_within_radius(self) -> None:
        tap = make_correlated_tap(gtfs_stop_id="stop_nearest", stop_id=42)
        db = _build_mock_db(correlated_rows=[tap], total_taps=1, uncorrelated=0)
        settings = _make_settings()

        df = await correlate_taps_to_stops(db, SAMPLE_OBSERVED_AT, SAMPLE_OBSERVED_AT, settings)

        assert df.iloc[0]["stop_id"] == 42
        assert df.iloc[0]["gtfs_stop_id"] == "stop_nearest"


class TestCorrelationRate:
    async def test_rate_logged_above_threshold(self) -> None:
        tap = make_correlated_tap()
        db = _build_mock_db(correlated_rows=[tap], total_taps=10, uncorrelated=1)
        settings = _make_settings(min_corr=80.0)

        with patch("app.ml.features.load_features.logger") as mock_logger:
            await correlate_taps_to_stops(db, SAMPLE_OBSERVED_AT, SAMPLE_OBSERVED_AT, settings)
            info_calls = [
                c for c in mock_logger.info.call_args_list if "correlation_rate_ok" in str(c)
            ]
            assert len(info_calls) == 1

    async def test_rate_warning_below_threshold(self) -> None:
        tap = make_correlated_tap()
        db = _build_mock_db(correlated_rows=[tap], total_taps=10, uncorrelated=5)
        settings = _make_settings(min_corr=80.0)

        with patch("app.ml.features.load_features.logger") as mock_logger:
            await correlate_taps_to_stops(db, SAMPLE_OBSERVED_AT, SAMPLE_OBSERVED_AT, settings)
            warn_calls = [
                c for c in mock_logger.warning.call_args_list if "correlation_rate_low" in str(c)
            ]
            assert len(warn_calls) == 1


class TestExtractLoadFeatures:
    def _make_taps_for_trip(
        self, trip_id: str, stop_sequences: list[int], taps_per_stop: int = 3
    ) -> list[dict[str, Any]]:
        """Generate correlated taps for multiple stops on one trip."""
        taps: list[dict[str, Any]] = []
        for seq in stop_sequences:
            for i in range(taps_per_stop):
                taps.append(
                    make_correlated_tap(
                        eticket_id=len(taps) + 1,
                        gtfs_trip_id=trip_id,
                        stop_sequence=seq,
                        validated_at=SAMPLE_OBSERVED_AT + datetime.timedelta(seconds=seq * 60 + i),
                    )
                )
        return taps

    async def test_load_factor_calculation(self) -> None:
        taps = [make_correlated_tap(eticket_id=i) for i in range(30)]
        db = _build_mock_db(correlated_rows=taps, total_taps=30, uncorrelated=0)
        settings = _make_settings()

        df = await extract_load_features(
            db, SAMPLE_OBSERVED_AT, SAMPLE_OBSERVED_AT + datetime.timedelta(days=1), settings
        )

        assert len(df) >= 1
        row = df.iloc[0]
        assert row["tap_count"] == 30
        assert row["capacity"] == 60  # default bus
        assert row["load_factor_pct"] == pytest.approx(50.0)

    async def test_cumulative_load_across_stops(self) -> None:
        taps = self._make_taps_for_trip("trip_A", [1, 2], taps_per_stop=5)
        db = _build_mock_db(correlated_rows=taps, total_taps=10, uncorrelated=0)
        settings = _make_settings()

        df = await extract_load_features(
            db, SAMPLE_OBSERVED_AT, SAMPLE_OBSERVED_AT + datetime.timedelta(days=1), settings
        )

        df_sorted = df.sort_values("stop_sequence")
        assert len(df_sorted) == 2
        assert df_sorted.iloc[0]["tap_count"] == 5
        assert df_sorted.iloc[0]["cumulative_load"] == 5
        assert df_sorted.iloc[1]["tap_count"] == 5
        assert df_sorted.iloc[1]["cumulative_load"] == 10

    async def test_capacity_from_db_override(self) -> None:
        tap = make_correlated_tap()
        db = _build_mock_db(
            correlated_rows=[tap],
            total_taps=1,
            uncorrelated=0,
            capacity_rows=[{"fleet_number": "4521", "capacity": 75, "vehicle_type": "bus"}],
        )
        settings = _make_settings()

        df = await extract_load_features(
            db, SAMPLE_OBSERVED_AT, SAMPLE_OBSERVED_AT + datetime.timedelta(days=1), settings
        )

        assert df.iloc[0]["capacity"] == 75

    async def test_capacity_default_by_transport_type(self) -> None:
        tap = make_correlated_tap(transport_type="tram")
        db = _build_mock_db(correlated_rows=[tap], total_taps=1, uncorrelated=0)
        settings = _make_settings()

        df = await extract_load_features(
            db, SAMPLE_OBSERVED_AT, SAMPLE_OBSERVED_AT + datetime.timedelta(days=1), settings
        )

        assert df.iloc[0]["capacity"] == 200  # tram default

    async def test_same_input_produces_same_output(self) -> None:
        taps = self._make_taps_for_trip("trip_det", [1, 2, 3], taps_per_stop=2)
        from_ts = SAMPLE_OBSERVED_AT
        to_ts = SAMPLE_OBSERVED_AT + datetime.timedelta(days=1)

        db1 = _build_mock_db(correlated_rows=taps, total_taps=6, uncorrelated=0)
        settings = _make_settings()
        df1 = await extract_load_features(db1, from_ts, to_ts, settings)

        db2 = _build_mock_db(correlated_rows=taps, total_taps=6, uncorrelated=0)
        df2 = await extract_load_features(db2, from_ts, to_ts, settings)

        pd.testing.assert_frame_equal(df1.reset_index(drop=True), df2.reset_index(drop=True))

    async def test_mixed_vehicles_different_capacities(self) -> None:
        tap_bus = make_correlated_tap(
            eticket_id=1,
            vehicle_number="1001",
            transport_type="bus",
            stop_sequence=1,
            validated_at=SAMPLE_OBSERVED_AT,
        )
        tap_tram = make_correlated_tap(
            eticket_id=2,
            vehicle_number="2001",
            transport_type="tram",
            stop_sequence=1,
            validated_at=SAMPLE_OBSERVED_AT + datetime.timedelta(seconds=1),
            gtfs_trip_id="trip_tram",
        )
        db = _build_mock_db(correlated_rows=[tap_bus, tap_tram], total_taps=2, uncorrelated=0)
        settings = _make_settings()

        df = await extract_load_features(
            db, SAMPLE_OBSERVED_AT, SAMPLE_OBSERVED_AT + datetime.timedelta(days=1), settings
        )

        # Both have route_code "22" but different vehicles - check capacities differ
        assert 60 in df["capacity"].values  # bus
        assert 200 in df["capacity"].values  # tram

    async def test_vehicle_with_no_capacity_or_type(self) -> None:
        tap = make_correlated_tap(vehicle_number="unknown_v", transport_type="hovercraft")
        db = _build_mock_db(correlated_rows=[tap], total_taps=1, uncorrelated=0)
        settings = _make_settings()

        df = await extract_load_features(
            db, SAMPLE_OBSERVED_AT, SAMPLE_OBSERVED_AT + datetime.timedelta(days=1), settings
        )

        assert df.iloc[0]["capacity"] == 60  # fallback

    async def test_empty_correlation_returns_empty_df(self) -> None:
        db = _build_mock_db(correlated_rows=[], total_taps=0, uncorrelated=0)
        settings = _make_settings()

        df = await extract_load_features(
            db, SAMPLE_OBSERVED_AT, SAMPLE_OBSERVED_AT + datetime.timedelta(days=1), settings
        )

        assert df.empty
