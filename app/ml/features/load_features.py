# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false
"""E-ticket <-> GTFS-RT passenger load correlation pipeline (ML-3.1).

Correlates e-ticket validation taps with vehicle GPS positions and nearest
stops to produce per-(trip, stop_sequence, date) passenger load features
for ML training.

Offline path: extract_load_features(db, from_ts, to_ts, settings) -> pd.DataFrame
"""

from __future__ import annotations

import datetime
from dataclasses import dataclass
from typing import Any

import pandas as pd
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.logging import get_logger
from app.ml.features.load_queries import (
    TOTAL_TAPS_SQL,
    correlate_taps_sql,
    uncorrelated_count_sql,
)
from app.ml.features.vehicle_capacity import get_vehicle_capacities

logger = get_logger(__name__)


@dataclass(frozen=True)
class LoadFeatureRow:
    """Single row in the load features output.

    Represents passenger load at a (trip, stop, date) intersection.
    """

    gtfs_trip_id: str | None
    stop_sequence: int | None
    stop_id: int | None
    date: datetime.date
    hour: int
    route_code: str
    transport_type: str
    tap_count: int
    cumulative_load: int
    capacity: int
    load_factor_pct: float


async def correlate_taps_to_stops(
    db: AsyncSession,
    from_ts: datetime.datetime,
    to_ts: datetime.datetime,
    settings: Settings,
) -> pd.DataFrame:
    """Join e-ticket validations to nearest vehicle position and stop.

    Args:
        db: Async database session.
        from_ts: Start of extraction window (inclusive, UTC).
        to_ts: End of extraction window (exclusive, UTC).
        settings: Application settings for window/distance thresholds.

    Returns:
        DataFrame with correlated tap rows.
    """
    logger.info(
        "ml.load.correlation_started",
        from_ts=str(from_ts),
        to_ts=str(to_ts),
        window_s=settings.ml_load_time_window_seconds,
        distance_m=settings.ml_load_distance_threshold_m,
    )

    sql = correlate_taps_sql(settings.ml_load_time_window_seconds)
    result = await db.execute(
        text(sql),
        {
            "from_ts": from_ts,
            "to_ts": to_ts,
            "distance_m": settings.ml_load_distance_threshold_m,
        },
    )
    rows = result.mappings().all()

    # Correlation rate metrics
    total_result = await db.execute(
        text(TOTAL_TAPS_SQL),
        {"from_ts": from_ts, "to_ts": to_ts},
    )
    total_row = total_result.mappings().first()
    total_taps = int(total_row["total"]) if total_row else 0

    uncorr_sql = uncorrelated_count_sql(settings.ml_load_time_window_seconds)
    uncorr_result = await db.execute(
        text(uncorr_sql),
        {"from_ts": from_ts, "to_ts": to_ts},
    )
    uncorr_row = uncorr_result.mappings().first()
    uncorrelated = int(uncorr_row["uncorrelated"]) if uncorr_row else 0

    correlated = total_taps - uncorrelated
    correlation_rate = (correlated / total_taps * 100) if total_taps > 0 else 0.0

    if correlation_rate >= settings.ml_load_min_correlation_pct:
        logger.info(
            "ml.load.correlation_rate_ok",
            correlation_rate=round(correlation_rate, 1),
            total_taps=total_taps,
            correlated=correlated,
            uncorrelated=uncorrelated,
        )
    else:
        logger.warning(
            "ml.load.correlation_rate_low",
            correlation_rate=round(correlation_rate, 1),
            threshold=settings.ml_load_min_correlation_pct,
            total_taps=total_taps,
            correlated=correlated,
            uncorrelated=uncorrelated,
        )

    if not rows:
        logger.warning("ml.load.correlation_empty", from_ts=str(from_ts), to_ts=str(to_ts))
        return _empty_correlation_df()

    records: list[dict[str, Any]] = [dict(row) for row in rows]
    return pd.DataFrame(records)


async def extract_load_features(
    db: AsyncSession,
    from_ts: datetime.datetime,
    to_ts: datetime.datetime,
    settings: Settings,
) -> pd.DataFrame:
    """Extract passenger load features for ML training.

    Correlates e-ticket taps with GPS positions, finds nearest stops,
    then aggregates to (trip, stop_sequence, date) granularity with
    cumulative load and load factor calculations.

    Args:
        db: Async database session.
        from_ts: Start of extraction window (inclusive, UTC).
        to_ts: End of extraction window (exclusive, UTC).
        settings: Application settings.

    Returns:
        DataFrame with load feature columns.
    """
    logger.info(
        "ml.load.extraction_started",
        from_ts=str(from_ts),
        to_ts=str(to_ts),
    )

    correlated_df = await correlate_taps_to_stops(db, from_ts, to_ts, settings)

    if correlated_df.empty:
        logger.warning("ml.load.extraction_empty", from_ts=str(from_ts), to_ts=str(to_ts))
        return _empty_load_features_df()

    # Resolve vehicle capacities
    vehicle_numbers: list[str] = correlated_df["vehicle_number"].unique().tolist()
    transport_types: dict[str, str] = dict(
        zip(
            correlated_df["vehicle_number"].tolist(),
            correlated_df["transport_type"].tolist(),
            strict=False,
        )
    )
    capacities = await get_vehicle_capacities(db, vehicle_numbers, transport_types)

    # Add date/hour columns for grouping
    correlated_df["date"] = pd.to_datetime(correlated_df["validated_at"]).dt.date
    correlated_df["hour"] = pd.to_datetime(correlated_df["validated_at"]).dt.hour

    # Group by (gtfs_trip_id, stop_sequence, date)
    group_cols = ["gtfs_trip_id", "stop_sequence", "date"]
    grouped = correlated_df.groupby(group_cols, dropna=False)

    feature_rows: list[dict[str, Any]] = []
    for group_key, group_df in grouped:
        raw_trip_id, raw_stop_seq, date_val = group_key
        first_row = group_df.iloc[0]

        trip_id_val = str(raw_trip_id) if raw_trip_id is not None else None
        stop_seq_val = int(str(raw_stop_seq)) if raw_stop_seq is not None else None
        stop_id_val = int(first_row["stop_id"]) if first_row["stop_id"] is not None else None

        tap_count = len(group_df)
        vehicle_num = str(first_row["vehicle_number"])
        capacity = capacities.get(vehicle_num, 60)
        route_code = str(first_row["route_code"])
        transport_type = str(first_row["transport_type"])
        hour = int(first_row["hour"])

        feature_rows.append(
            {
                "gtfs_trip_id": trip_id_val,
                "stop_sequence": stop_seq_val,
                "stop_id": stop_id_val,
                "date": date_val,
                "hour": hour,
                "route_code": route_code,
                "transport_type": transport_type,
                "tap_count": tap_count,
                "capacity": capacity,
                "vehicle_number": vehicle_num,
            }
        )

    features_df = pd.DataFrame(feature_rows)

    if features_df.empty:
        return _empty_load_features_df()

    # Compute cumulative load per (trip, date) ordered by stop_sequence
    features_df = features_df.sort_values(["gtfs_trip_id", "date", "stop_sequence"])
    features_df["cumulative_load"] = features_df.groupby(["gtfs_trip_id", "date"], dropna=False)[
        "tap_count"
    ].cumsum()

    # Load factor: (cumulative_load / capacity) * 100, capped at 100
    features_df["load_factor_pct"] = (
        (features_df["cumulative_load"] / features_df["capacity"]) * 100
    ).clip(upper=100.0)

    # Drop intermediate column
    features_df = features_df.drop(columns=["vehicle_number"])

    logger.info(
        "ml.load.extraction_completed",
        row_count=len(features_df),
        from_ts=str(from_ts),
        to_ts=str(to_ts),
    )

    return features_df


def _empty_correlation_df() -> pd.DataFrame:
    """Return empty DataFrame with correlation column schema."""
    columns = [
        "eticket_id",
        "vehicle_number",
        "validated_at",
        "route_code",
        "transport_type",
        "gtfs_trip_id",
        "vp_lat",
        "vp_lon",
        "position_at",
        "stop_id",
        "gtfs_stop_id",
        "stop_sequence",
    ]
    return pd.DataFrame(columns=columns)


def _empty_load_features_df() -> pd.DataFrame:
    """Return empty DataFrame with load features column schema."""
    columns = [
        "gtfs_trip_id",
        "stop_sequence",
        "stop_id",
        "date",
        "hour",
        "route_code",
        "transport_type",
        "tap_count",
        "cumulative_load",
        "capacity",
        "load_factor_pct",
    ]
    return pd.DataFrame(columns=columns)
