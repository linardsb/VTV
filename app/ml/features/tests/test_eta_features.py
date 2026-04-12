# pyright: reportUnknownMemberType=false, reportUnknownArgumentType=false, reportUnknownParameterType=false, reportMissingParameterType=false, reportArgumentType=false
"""Unit tests for ETA feature extraction (ML-2.1)."""

from __future__ import annotations

import datetime
from typing import Any
from unittest.mock import AsyncMock

import pytest

from app.ml.features.eta_features import (
    ETAFeatures,
    classify_weather,
    extract_features,
    extract_features_batch,
    features_to_dict,
    parse_gtfs_time,
)
from app.ml.features.tests.conftest import SAMPLE_OBSERVED_AT, make_mapping_result

# --- Pure function tests ---


class TestParseGtfsTime:
    def test_standard_time(self):
        assert parse_gtfs_time("08:30:00") == pytest.approx(8.5)

    def test_midnight(self):
        assert parse_gtfs_time("00:00:00") == pytest.approx(0.0)

    def test_overnight_time(self):
        """GTFS allows times > 24:00:00 for overnight trips."""
        assert parse_gtfs_time("25:00:00") == pytest.approx(25.0)

    def test_with_seconds(self):
        assert parse_gtfs_time("12:15:30") == pytest.approx(12.258333, rel=1e-3)


class TestClassifyWeather:
    def test_snow_from_phenomena(self):
        assert classify_weather({"snow": True}, None) == "snow"

    def test_rain_from_phenomena(self):
        assert classify_weather({"rain": True}, None) == "rain"

    def test_fog_from_phenomena(self):
        assert classify_weather({"fog": True}, None) == "fog"

    def test_rain_from_precip(self):
        assert classify_weather(None, 0.5) == "rain"

    def test_clear_no_data(self):
        assert classify_weather(None, None) == "clear"

    def test_clear_zero_precip(self):
        assert classify_weather(None, 0.0) == "clear"

    def test_other_unknown_phenomena(self):
        assert classify_weather({"hail": True}, 0.0) == "other"

    def test_drizzle_maps_to_rain(self):
        assert classify_weather({"drizzle": True}, None) == "rain"

    def test_mist_maps_to_fog(self):
        assert classify_weather({"mist": True}, None) == "fog"


class TestETAFeaturesDataclass:
    def test_frozen_immutability(self):
        f = ETAFeatures(
            day_of_week=0,
            month=3,
            is_school_day=True,
            is_holiday=False,
            weather_bucket="clear",
            route_type=3,
            direction=0,
            operator="RS",
            time_of_day_hour=8.5,
            scheduled_headway_s=600.0,
            historical_avg_delay_at_stop_s=30.0,
            prev_stop_actual_delay_s=15.0,
            trip_elapsed_pct=0.5,
            temp_c=5.0,
            wind_mps=3.0,
            precip_mm_last_hr=0.0,
            traffic_count_rolling_7d=1200.0,
            accident_count_within_500m=0,
        )
        with pytest.raises(AttributeError):
            f.day_of_week = 1  # type: ignore[misc]

    def test_features_to_dict(self):
        f = ETAFeatures(
            day_of_week=2,
            month=6,
            is_school_day=True,
            is_holiday=False,
            weather_bucket="rain",
            route_type=0,
            direction=1,
            operator="Test",
            time_of_day_hour=14.0,
            scheduled_headway_s=300.0,
            historical_avg_delay_at_stop_s=0.0,
            prev_stop_actual_delay_s=0.0,
            trip_elapsed_pct=0.3,
            temp_c=20.0,
            wind_mps=1.0,
            precip_mm_last_hr=2.5,
            traffic_count_rolling_7d=500.0,
            accident_count_within_500m=1,
        )
        d = features_to_dict(f)
        assert d["day_of_week"] == 2
        assert d["weather_bucket"] == "rain"
        assert len(d) == 18


# --- extract_features tests (mocked DB) ---

# Unique substrings for each SQL query used by extract_features
_TRIP_META = "a.agency_name AS operator"
_STOP_LOC = "s.stop_lat, s.stop_lon"
_ARRIVAL = "st.arrival_time FROM stop_times"
_MAX_SEQ = "MAX(st.stop_sequence)"
_CALENDAR = "exception_type = 2"
_DELAY_AT_STOP = "vp.delay_seconds, vp.recorded_at, vp.speed_kmh"
_HIST_AVG = "AVG(vp.delay_seconds)::float"
_PREV_DELAY = ":prev_stop_sequence"
_HEADWAY = "t2.route_id"
_WEATHER = "wo.temp_c, wo.wind_mps"
_TRAFFIC = "AVG(tc.avg_count_per_day)"
_ACCIDENT = "ST_DWithin"


def _build_mock_db(
    responses: dict[str, list[dict[str, Any]]],
) -> AsyncMock:
    """Build a mock DB session that returns different results per query pattern.

    Uses longest-match-first to avoid ambiguous substring collisions.

    Args:
        responses: Maps a unique SQL substring to the mock result rows.
    """
    db = AsyncMock()
    sorted_patterns = sorted(responses.keys(), key=len, reverse=True)

    async def mock_execute(stmt, params=None):
        sql_str = str(stmt) if not isinstance(stmt, str) else stmt
        compiled = str(getattr(stmt, "text", sql_str))
        for pattern in sorted_patterns:
            if pattern in compiled:
                return make_mapping_result(responses[pattern])
        return make_mapping_result([])

    db.execute = AsyncMock(side_effect=mock_execute)
    return db


_DEFAULT_META: dict[str, Any] = {
    "route_type": 3,
    "direction_id": 0,
    "operator": "RS",
    "route_fk": 1,
    "calendar_id": 1,
}
_DEFAULT_STOP_LOC: dict[str, Any] = {"stop_lat": 56.95, "stop_lon": 24.10}


def _default_responses(**overrides: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    """Build standard mock responses with optional overrides."""
    base: dict[str, list[dict[str, Any]]] = {
        _TRIP_META: [_DEFAULT_META],
        _STOP_LOC: [_DEFAULT_STOP_LOC],
        _ARRIVAL: [{"arrival_time": "08:00:00"}],
        _MAX_SEQ: [{"max_seq": 10}],
        _CALENDAR: [],
    }
    base.update(overrides)
    return base


class TestExtractFeatures:
    @pytest.mark.asyncio
    async def test_day_of_week_extraction(self):
        """Monday=0, Sunday=6."""
        # March 15 2026 is a Sunday
        sunday = datetime.datetime(2026, 3, 15, 10, 0, tzinfo=datetime.UTC)
        db = _build_mock_db(_default_responses(**{_ARRIVAL: [{"arrival_time": "10:00:00"}]}))
        result = await extract_features(db, trip_id=1, stop_sequence=5, observed_at=sunday)
        assert result.day_of_week == 6  # Sunday

    @pytest.mark.asyncio
    async def test_is_school_day_weekday_not_summer(self):
        """Weekday in March = school day."""
        monday = datetime.datetime(2026, 3, 16, 8, 0, tzinfo=datetime.UTC)
        db = _build_mock_db(_default_responses())
        result = await extract_features(db, trip_id=1, stop_sequence=3, observed_at=monday)
        assert result.is_school_day is True
        assert result.is_holiday is False

    @pytest.mark.asyncio
    async def test_is_school_day_summer(self):
        """July weekday = not school day."""
        july_monday = datetime.datetime(2026, 7, 6, 8, 0, tzinfo=datetime.UTC)
        db = _build_mock_db(_default_responses())
        result = await extract_features(db, trip_id=1, stop_sequence=3, observed_at=july_monday)
        assert result.is_school_day is False

    @pytest.mark.asyncio
    async def test_trip_elapsed_pct(self):
        """stop_sequence / max_stop_sequence."""
        db = _build_mock_db(_default_responses(**{_MAX_SEQ: [{"max_seq": 20}]}))
        result = await extract_features(
            db, trip_id=1, stop_sequence=10, observed_at=SAMPLE_OBSERVED_AT
        )
        assert result.trip_elapsed_pct == pytest.approx(0.5)

    @pytest.mark.asyncio
    async def test_prev_stop_delay_first_stop(self):
        """First stop (sequence=1) returns 0.0 for prev delay."""
        db = _build_mock_db(_default_responses())
        result = await extract_features(
            db, trip_id=1, stop_sequence=1, observed_at=SAMPLE_OBSERVED_AT
        )
        assert result.prev_stop_actual_delay_s == 0.0

    @pytest.mark.asyncio
    async def test_missing_weather_uses_defaults(self):
        """No weather observation -> temp_c=0, wind_mps=0, precip=0, bucket=clear."""
        db = _build_mock_db(_default_responses())
        result = await extract_features(
            db, trip_id=1, stop_sequence=5, observed_at=SAMPLE_OBSERVED_AT
        )
        assert result.temp_c == 0.0
        assert result.wind_mps == 0.0
        assert result.precip_mm_last_hr == 0.0
        assert result.weather_bucket == "clear"

    @pytest.mark.asyncio
    async def test_missing_traffic_uses_defaults(self):
        """No traffic/accident data -> 0.0/0 defaults."""
        db = _build_mock_db(_default_responses())
        result = await extract_features(
            db, trip_id=1, stop_sequence=5, observed_at=SAMPLE_OBSERVED_AT
        )
        assert result.traffic_count_rolling_7d == 0.0
        assert result.accident_count_within_500m == 0

    @pytest.mark.asyncio
    async def test_missing_trip_metadata_uses_defaults(self):
        """No trip metadata -> route_type=3, direction=0, operator='unknown'."""
        responses = _default_responses()
        responses[_TRIP_META] = []  # No trip metadata
        db = _build_mock_db(responses)
        result = await extract_features(
            db, trip_id=999, stop_sequence=1, observed_at=SAMPLE_OBSERVED_AT
        )
        assert result.route_type == 3
        assert result.direction == 0
        assert result.operator == "unknown"


# --- extract_features_batch tests ---


class TestExtractFeaturesBatch:
    @pytest.mark.asyncio
    async def test_empty_range_returns_empty_df(self):
        """No data in range -> empty DataFrame with correct columns."""
        db = _build_mock_db({})
        df = await extract_features_batch(
            db,
            from_ts=SAMPLE_OBSERVED_AT,
            to_ts=SAMPLE_OBSERVED_AT + datetime.timedelta(days=1),
        )
        assert len(df) == 0
        assert "day_of_week" in df.columns
        assert "weather_bucket" in df.columns

    @pytest.mark.asyncio
    async def test_batch_returns_correct_columns(self):
        """Batch result has all 18 feature columns + trip_id + stop_sequence."""
        batch_row: dict[str, Any] = {
            "trip_id": 1,
            "stop_sequence": 3,
            "arrival_time": "08:30:00",
            "departure_time": "08:31:00",
            "stop_id": 10,
            "delay_seconds": 45,
            "recorded_at": SAMPLE_OBSERVED_AT,
            "speed_kmh": 25.0,
            "route_type": 3,
            "direction_id": 0,
            "operator": "RS",
            "route_fk": 1,
            "calendar_id": 1,
            "stop_lat": 56.95,
            "stop_lon": 24.10,
            "max_stop_seq": 20,
        }
        # The batch query SQL contains "stop_times st" as unique prefix
        db = _build_mock_db({"stop_times st\nJOIN trips": [batch_row]})
        df = await extract_features_batch(
            db,
            from_ts=SAMPLE_OBSERVED_AT - datetime.timedelta(hours=1),
            to_ts=SAMPLE_OBSERVED_AT + datetime.timedelta(hours=1),
        )
        expected_cols = {
            "trip_id",
            "stop_sequence",
            "day_of_week",
            "month",
            "is_school_day",
            "is_holiday",
            "weather_bucket",
            "route_type",
            "direction",
            "operator",
            "time_of_day_hour",
            "scheduled_headway_s",
            "historical_avg_delay_at_stop_s",
            "prev_stop_actual_delay_s",
            "trip_elapsed_pct",
            "temp_c",
            "wind_mps",
            "precip_mm_last_hr",
            "traffic_count_rolling_7d",
            "accident_count_within_500m",
        }
        assert expected_cols.issubset(set(df.columns))
        assert len(df) == 1
