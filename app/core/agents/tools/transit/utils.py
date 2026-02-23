"""Shared utility functions for transit tools.

Extracted from individual tool files to eliminate duplication (6 functions
duplicated across 4 files). Each function handles GTFS time/date operations.
"""

from __future__ import annotations

from datetime import date, datetime
from zoneinfo import ZoneInfo

from app.core.agents.tools.transit.static_cache import StopTimeEntry, TripInfo

_RIGA_TZ = ZoneInfo("Europe/Riga")


def validate_date(date_str: str | None) -> tuple[date, str] | str:
    """Validate and parse a date string, defaulting to today in Riga timezone.

    Args:
        date_str: ISO date string (YYYY-MM-DD) or None for today.

    Returns:
        Tuple of (date, date_string) on success, or error message string on failure.
    """
    if date_str is None:
        today = datetime.now(tz=_RIGA_TZ).date()
        return (today, today.isoformat())
    try:
        parsed = date.fromisoformat(date_str)
    except ValueError:
        return f"Invalid date format '{date_str}'. Use YYYY-MM-DD format, e.g., '2026-02-17'."
    return (parsed, date_str)


def classify_service_type(query_date: date) -> str:
    """Classify a date's service type for display.

    Args:
        query_date: The date to classify.

    Returns:
        One of "weekday", "saturday", "sunday".
    """
    day_name = query_date.strftime("%A").lower()
    if day_name == "saturday":
        return "saturday"
    if day_name == "sunday":
        return "sunday"
    return "weekday"


def gtfs_time_to_minutes(gtfs_time: str) -> int:
    """Convert GTFS time string to minutes since midnight.

    Handles times > 24:00:00 (e.g., "25:30:00" = 1530 minutes).

    Args:
        gtfs_time: Time string in HH:MM:SS or HH:MM format.

    Returns:
        Minutes since midnight (can exceed 1440 for next-day trips).
    """
    parts = gtfs_time.strip().split(":")
    hours = int(parts[0])
    minutes = int(parts[1])
    return hours * 60 + minutes


def gtfs_time_to_display(gtfs_time: str) -> str:
    """Convert GTFS time to HH:MM display format.

    Normalizes times > 24h (e.g., "25:30:00" -> "01:30").

    Args:
        gtfs_time: GTFS time string.

    Returns:
        Normalized HH:MM string.
    """
    parts = gtfs_time.strip().split(":")
    hours = int(parts[0]) % 24
    minutes = int(parts[1])
    return f"{hours:02d}:{minutes:02d}"


def delay_description(delay_seconds: int) -> str:
    """Convert delay in seconds to human-readable text.

    Args:
        delay_seconds: Delay in seconds (positive=late, negative=early).

    Returns:
        Human-readable delay description.
    """
    if abs(delay_seconds) < 60:
        return "on time"
    minutes = abs(delay_seconds) // 60
    if delay_seconds > 0:
        return f"{minutes} min late"
    return f"{minutes} min early"


def get_first_departure_minutes(
    trip: TripInfo, trip_stop_times: dict[str, list[StopTimeEntry]]
) -> int:
    """Get the departure time in minutes for a trip's first stop.

    Args:
        trip: Trip to look up.
        trip_stop_times: Index of trip_id -> ordered stop times.

    Returns:
        Minutes since midnight, or 9999 if no stop times found.
    """
    stops = trip_stop_times.get(trip.trip_id, [])
    if not stops:
        return 9999
    return gtfs_time_to_minutes(stops[0].departure_time)
