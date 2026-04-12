# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false
"""ETA feature engineering pipeline (ML-2.1).

Deterministic feature extraction joining vehicle_positions (TimescaleDB)
with gtfs_stop_times + weather_observations + traffic data to produce
a training matrix. One row per (trip_id, stop_sequence).

Online path: extract_features(db, trip_id, stop_sequence, observed_at) -> ETAFeatures
Offline path: extract_features_batch(db, from_ts, to_ts) -> pd.DataFrame
"""

from __future__ import annotations

import datetime
from dataclasses import asdict, dataclass
from typing import Any, Literal

import pandas as pd
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.ml.features.queries import (
    ACCIDENT_COUNT_NEARBY_SQL,
    BATCH_FEATURES_SQL,
    HISTORICAL_AVG_DELAY_SQL,
    MAX_STOP_SEQUENCE_SQL,
    PREV_STOP_DELAY_SQL,
    SCHEDULED_HEADWAY_SQL,
    STOP_LOCATION_SQL,
    TRAFFIC_ROLLING_7D_SQL,
    TRIP_METADATA_SQL,
    WEATHER_AT_TIME_SQL,
)

logger = get_logger(__name__)

WeatherBucket = Literal["clear", "rain", "snow", "fog", "other"]


@dataclass(frozen=True)
class ETAFeatures:
    """18-feature vector for ETA prediction at a single (trip, stop_sequence).

    Categorical (8):
        day_of_week, month, is_school_day, is_holiday, weather_bucket,
        route_type, direction, operator

    Numeric (10):
        time_of_day_hour, scheduled_headway_s, historical_avg_delay_at_stop_s,
        prev_stop_actual_delay_s, trip_elapsed_pct, temp_c, wind_mps,
        precip_mm_last_hr, traffic_count_rolling_7d, accident_count_within_500m
    """

    # Categorical
    day_of_week: int
    month: int
    is_school_day: bool
    is_holiday: bool
    weather_bucket: WeatherBucket
    route_type: int
    direction: int
    operator: str

    # Numeric
    time_of_day_hour: float
    scheduled_headway_s: float
    historical_avg_delay_at_stop_s: float
    prev_stop_actual_delay_s: float
    trip_elapsed_pct: float
    temp_c: float
    wind_mps: float
    precip_mm_last_hr: float
    traffic_count_rolling_7d: float
    accident_count_within_500m: int


def parse_gtfs_time(time_str: str) -> float:
    """Convert GTFS HH:MM:SS string to fractional hours.

    GTFS allows times > 24:00:00 for overnight trips.

    Args:
        time_str: Time string in HH:MM:SS format.

    Returns:
        Fractional hours (e.g., "08:30:00" -> 8.5, "25:00:00" -> 25.0).
    """
    parts = time_str.strip().split(":")
    hours = int(parts[0])
    minutes = int(parts[1]) if len(parts) > 1 else 0
    seconds = int(parts[2]) if len(parts) > 2 else 0
    return hours + minutes / 60.0 + seconds / 3600.0


def classify_weather(
    phenomena: dict[str, Any] | None,
    precip_mm: float | None,
) -> WeatherBucket:
    """Map weather observation to a bucket category.

    Args:
        phenomena: JSONB dict of weather phenomena (may contain keys like
            "snow", "rain", "fog", etc.).
        precip_mm: Precipitation in millimeters.

    Returns:
        One of: "clear", "rain", "snow", "fog", "other".
    """
    if phenomena:
        phenomena_lower = {k.lower() for k in phenomena}
        if any("snow" in p for p in phenomena_lower):
            return "snow"
        if any("fog" in p or "mist" in p for p in phenomena_lower):
            return "fog"
        if any("rain" in p or "drizzle" in p or "shower" in p for p in phenomena_lower):
            return "rain"
        if phenomena_lower:
            return "other"
    if precip_mm is not None and precip_mm > 0.1:
        return "rain"
    return "clear"


def _is_school_period(dt: datetime.datetime) -> bool:
    """Approximate school term check: weekday + September-June."""
    return dt.weekday() < 5 and dt.month not in (7, 8)


async def _fetch_one(db: AsyncSession, sql: str, params: dict[str, Any]) -> dict[str, Any] | None:
    """Execute SQL and return first row as dict, or None."""
    result = await db.execute(text(sql), params)
    row = result.mappings().first()
    return dict(row) if row else None


async def extract_features(
    db: AsyncSession,
    trip_id: int,
    stop_sequence: int,
    observed_at: datetime.datetime,
) -> ETAFeatures:
    """Extract 18 ETA features for a single (trip, stop_sequence) observation.

    Online inference path. Executes individual queries for each feature group
    and assembles an ETAFeatures dataclass with safe defaults for missing data.

    Args:
        db: Async database session.
        trip_id: trips.id (integer PK, not gtfs_trip_id string).
        stop_sequence: Stop sequence number within the trip.
        observed_at: Observation timestamp (UTC).

    Returns:
        Frozen ETAFeatures dataclass with all 18 fields populated.
    """
    # Trip metadata (route_type, direction, operator, route_fk, calendar_id)
    meta = await _fetch_one(db, TRIP_METADATA_SQL, {"trip_id": trip_id})
    if not meta:
        logger.warning("ml.features.trip_metadata_missing", trip_id=trip_id)
        meta = {
            "route_type": 3,
            "direction_id": 0,
            "operator": "unknown",
            "route_fk": 0,
            "calendar_id": 0,
        }

    route_type: int = int(meta.get("route_type") or 3)
    direction: int = int(meta.get("direction_id") or 0)
    operator: str = str(meta.get("operator") or "unknown")
    route_fk: int = int(meta.get("route_fk") or 0)

    # Stop location
    stop_loc = await _fetch_one(
        db, STOP_LOCATION_SQL, {"trip_id": trip_id, "stop_sequence": stop_sequence}
    )
    stop_lat = float(stop_loc["stop_lat"]) if stop_loc else 0.0
    stop_lon = float(stop_loc["stop_lon"]) if stop_loc else 0.0

    # Stop arrival time for time_of_day_hour
    arrival_result = await db.execute(
        text(
            "SELECT st.arrival_time FROM stop_times st "
            "WHERE st.trip_id = :trip_id AND st.stop_sequence = :stop_sequence"
        ),
        {"trip_id": trip_id, "stop_sequence": stop_sequence},
    )
    arrival_row = arrival_result.mappings().first()
    arrival_time_str = str(arrival_row["arrival_time"]) if arrival_row else "00:00:00"
    time_of_day_hour = parse_gtfs_time(arrival_time_str)

    # Historical average delay
    hist_row = await _fetch_one(
        db,
        HISTORICAL_AVG_DELAY_SQL,
        {
            "route_id": route_fk,
            "stop_sequence": stop_sequence,
            "hour_of_day": observed_at.hour,
            "day_of_week": observed_at.weekday(),
            "lookback_start": observed_at - datetime.timedelta(days=90),
            "lookback_end": observed_at,
        },
    )
    historical_avg = float(hist_row["avg_delay"]) if hist_row and hist_row.get("avg_delay") else 0.0

    # Previous stop delay
    prev_delay: float = 0.0
    if stop_sequence > 1:
        prev_row = await _fetch_one(
            db,
            PREV_STOP_DELAY_SQL,
            {"trip_id": trip_id, "prev_stop_sequence": stop_sequence - 1},
        )
        if prev_row and "delay_seconds" in prev_row:
            prev_delay = float(int(prev_row["delay_seconds"]))

    # Trip elapsed percentage
    max_seq_row = await _fetch_one(db, MAX_STOP_SEQUENCE_SQL, {"trip_id": trip_id})
    max_seq = int(max_seq_row["max_seq"]) if max_seq_row and max_seq_row.get("max_seq") else 1
    trip_elapsed_pct = stop_sequence / max_seq if max_seq > 0 else 0.0

    # Scheduled headway
    headway_row = await _fetch_one(
        db,
        SCHEDULED_HEADWAY_SQL,
        {
            "route_id": route_fk,
            "stop_id": int(stop_loc["stop_id"]) if stop_loc and "stop_id" in stop_loc else 0,
            "stop_sequence": stop_sequence,
            "current_arrival_time": arrival_time_str,
        },
    )
    scheduled_headway_s: float = 0.0
    if headway_row and headway_row.get("arrival_time"):
        prev_time = parse_gtfs_time(str(headway_row["arrival_time"]))
        scheduled_headway_s = (time_of_day_hour - prev_time) * 3600.0

    # Weather
    weather_row = await _fetch_one(db, WEATHER_AT_TIME_SQL, {"target_time": observed_at})
    if weather_row:
        temp_c = float(weather_row["temp_c"]) if weather_row.get("temp_c") is not None else 0.0
        wind_mps = (
            float(weather_row["wind_mps"]) if weather_row.get("wind_mps") is not None else 0.0
        )
        precip_mm = (
            float(weather_row["precip_mm"]) if weather_row.get("precip_mm") is not None else 0.0
        )
        weather_bucket = classify_weather(weather_row.get("phenomena"), precip_mm)
    else:
        logger.debug("ml.features.weather_missing", observed_at=str(observed_at))
        temp_c = 0.0
        wind_mps = 0.0
        precip_mm = 0.0
        weather_bucket = "clear"

    # Traffic rolling 7d
    traffic_row = await _fetch_one(db, TRAFFIC_ROLLING_7D_SQL, {"target_date": observed_at.date()})
    traffic_count = (
        float(traffic_row["rolling_avg"])
        if traffic_row and traffic_row.get("rolling_avg") is not None
        else 0.0
    )

    # Accident count within 500m
    accident_row = await _fetch_one(
        db,
        ACCIDENT_COUNT_NEARBY_SQL,
        {"stop_lat": stop_lat, "stop_lon": stop_lon, "target_time": observed_at},
    )
    accident_count = (
        int(accident_row["accident_count"])
        if accident_row and "accident_count" in accident_row
        else 0
    )

    # Holiday check (calendar_dates exception_type=2)
    holiday_result = await db.execute(
        text(
            "SELECT 1 FROM calendar_dates cd "
            "WHERE cd.calendar_id = :calendar_id "
            "AND cd.date = :check_date AND cd.exception_type = 2 LIMIT 1"
        ),
        {"calendar_id": int(meta.get("calendar_id") or 0), "check_date": observed_at.date()},
    )
    is_holiday = holiday_result.first() is not None
    is_school_day = _is_school_period(observed_at) and not is_holiday

    return ETAFeatures(
        day_of_week=observed_at.weekday(),
        month=observed_at.month,
        is_school_day=is_school_day,
        is_holiday=is_holiday,
        weather_bucket=weather_bucket,
        route_type=route_type,
        direction=direction,
        operator=operator,
        time_of_day_hour=time_of_day_hour,
        scheduled_headway_s=max(scheduled_headway_s, 0.0),
        historical_avg_delay_at_stop_s=historical_avg,
        prev_stop_actual_delay_s=prev_delay,
        trip_elapsed_pct=min(max(trip_elapsed_pct, 0.0), 1.0),
        temp_c=temp_c,
        wind_mps=wind_mps,
        precip_mm_last_hr=precip_mm,
        traffic_count_rolling_7d=traffic_count,
        accident_count_within_500m=accident_count,
    )


async def extract_features_batch(
    db: AsyncSession,
    from_ts: datetime.datetime,
    to_ts: datetime.datetime,
) -> pd.DataFrame:
    """Extract ETA features for all observations in a time range.

    Offline batch path for training data generation. Uses a single large
    SQL query with CTEs instead of N+1 per-row queries.

    Args:
        db: Async database session.
        from_ts: Start of extraction window (inclusive, UTC).
        to_ts: End of extraction window (exclusive, UTC).

    Returns:
        DataFrame with 18 feature columns + trip_id + stop_sequence.
    """
    logger.info(
        "ml.features.batch_extraction_started",
        from_ts=str(from_ts),
        to_ts=str(to_ts),
    )

    result = await db.execute(text(BATCH_FEATURES_SQL), {"from_ts": from_ts, "to_ts": to_ts})
    rows = result.mappings().all()

    if not rows:
        logger.warning("ml.features.batch_extraction_empty", from_ts=str(from_ts), to_ts=str(to_ts))
        return _empty_features_df()

    records: list[dict[str, Any]] = []
    for row in rows:
        row_dict = dict(row)
        recorded_at = row_dict["recorded_at"]
        arrival_time_str = str(row_dict.get("arrival_time") or "00:00:00")
        max_seq = int(row_dict.get("max_stop_seq") or 1)
        stop_seq = int(row_dict["stop_sequence"])

        # Weather lookup for this row (batch query doesn't include weather join)
        weather_row = await _fetch_one(db, WEATHER_AT_TIME_SQL, {"target_time": recorded_at})
        if weather_row:
            w_temp = float(weather_row["temp_c"]) if weather_row.get("temp_c") is not None else 0.0
            w_wind = (
                float(weather_row["wind_mps"]) if weather_row.get("wind_mps") is not None else 0.0
            )
            w_precip = (
                float(weather_row["precip_mm"]) if weather_row.get("precip_mm") is not None else 0.0
            )
            w_phenomena = weather_row.get("phenomena")
        else:
            w_temp = 0.0
            w_wind = 0.0
            w_precip = 0.0
            w_phenomena = None

        # Traffic
        traffic_row = await _fetch_one(
            db, TRAFFIC_ROLLING_7D_SQL, {"target_date": recorded_at.date()}
        )
        traffic_val = (
            float(traffic_row["rolling_avg"])
            if traffic_row and traffic_row.get("rolling_avg") is not None
            else 0.0
        )

        # Accidents
        stop_lat_val = float(row_dict.get("stop_lat") or 0.0)
        stop_lon_val = float(row_dict.get("stop_lon") or 0.0)
        accident_row = await _fetch_one(
            db,
            ACCIDENT_COUNT_NEARBY_SQL,
            {"stop_lat": stop_lat_val, "stop_lon": stop_lon_val, "target_time": recorded_at},
        )
        accident_val = int(accident_row["accident_count"]) if accident_row else 0

        is_holiday = False  # Simplified for batch - full check would need calendar join
        is_school = _is_school_period(recorded_at) and not is_holiday

        records.append(
            {
                "trip_id": int(row_dict["trip_id"]),
                "stop_sequence": stop_seq,
                "day_of_week": recorded_at.weekday(),
                "month": recorded_at.month,
                "is_school_day": is_school,
                "is_holiday": is_holiday,
                "weather_bucket": classify_weather(w_phenomena, w_precip),
                "route_type": int(row_dict.get("route_type") or 3),
                "direction": int(row_dict.get("direction_id") or 0),
                "operator": str(row_dict.get("operator") or "unknown"),
                "time_of_day_hour": parse_gtfs_time(arrival_time_str),
                "scheduled_headway_s": 0.0,  # Computed in post-processing
                "historical_avg_delay_at_stop_s": 0.0,  # Computed in post-processing
                "prev_stop_actual_delay_s": float(int(row_dict.get("delay_seconds") or 0)),
                "trip_elapsed_pct": (stop_seq / max_seq) if max_seq > 0 else 0.0,
                "temp_c": w_temp,
                "wind_mps": w_wind,
                "precip_mm_last_hr": w_precip,
                "traffic_count_rolling_7d": traffic_val,
                "accident_count_within_500m": accident_val,
            }
        )

    df = pd.DataFrame(records)
    logger.info(
        "ml.features.batch_extraction_completed",
        row_count=len(df),
        from_ts=str(from_ts),
        to_ts=str(to_ts),
    )
    return df


def _empty_features_df() -> pd.DataFrame:
    """Return an empty DataFrame with the correct 18-feature column schema."""
    columns = [
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
    ]
    return pd.DataFrame(columns=columns)


def features_to_dict(features: ETAFeatures) -> dict[str, Any]:
    """Convert an ETAFeatures dataclass to a plain dict.

    Args:
        features: Frozen ETAFeatures instance.

    Returns:
        Dict with all 18 feature fields.
    """
    return asdict(features)
