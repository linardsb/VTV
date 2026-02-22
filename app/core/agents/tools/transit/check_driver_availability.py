"""Transit tool: check_driver_availability.

Queries driver availability for shift planning and route coverage.
"""

from __future__ import annotations

import json
import time
from collections import defaultdict
from datetime import date, datetime
from zoneinfo import ZoneInfo

from pydantic_ai import RunContext

from app.core.agents.tools.transit.deps import TransitDeps
from app.core.agents.tools.transit.driver_data import (
    VALID_SHIFTS,
    get_driver_availability,
)
from app.core.agents.tools.transit.schemas import (
    DriverAvailabilityReport,
    DriverInfo,
    ShiftSummary,
)
from app.core.logging import get_logger

logger = get_logger(__name__)

_RIGA_TZ = ZoneInfo("Europe/Riga")
_MAX_DRIVERS_RESPONSE = 30  # Token efficiency cap


def _validate_date(date_str: str | None) -> tuple[date, str] | str:
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


def _classify_service_type(query_date: date) -> str:
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


async def check_driver_availability(
    ctx: RunContext[TransitDeps],
    date: str | None = None,
    shift: str | None = None,
    route_id: str | None = None,
) -> str:
    """Check which drivers are available for a shift, date, or route assignment.

    WHEN TO USE: Dispatcher asks about driver availability, shift staffing,
    who can drive a specific route, coverage gaps, or "who's available for the
    morning shift?" questions. Returns structured availability data with
    per-shift breakdowns and individual driver details.

    WHEN NOT TO USE: For current vehicle positions or delays (use query_bus_status).
    For planned timetables (use get_route_schedule). For on-time performance
    metrics (use get_adherence_report). For finding stops (use search_stops).

    PARAMETERS:
    - date: Service date as YYYY-MM-DD. Defaults to today (Riga timezone).
    - shift: Filter to a specific shift: "morning" (05:00-13:00),
      "afternoon" (13:00-21:00), "evening" (17:00-01:00), or
      "night" (22:00-06:00). Omit for all shifts.
    - route_id: Filter to drivers qualified for a specific GTFS route.
      Example: "bus_22" returns only drivers certified for route 22.

    EFFICIENCY: Omit shift for a quick full-day overview. Combine shift +
    route_id for targeted staffing queries. Response is capped at 30 drivers.

    COMPOSITION: After checking driver availability, use get_route_schedule
    to see how many trips need coverage on a route, or get_adherence_report
    to check if understaffed routes have performance issues.

    Args:
        ctx: Pydantic AI run context with TransitDeps.
        date: Service date (YYYY-MM-DD). Defaults to today.
        shift: Shift filter ("morning", "afternoon", "evening", "night").
        route_id: GTFS route identifier to filter by qualification.

    Returns:
        JSON string with DriverAvailabilityReport data or actionable error message.
    """
    start_time = time.monotonic()
    # ctx.deps will be used by the CMS API client when it replaces the mock provider
    _settings = ctx.deps.settings

    logger.info(
        "transit.check_driver_availability.started",
        date=date,
        shift=shift,
        route_id=route_id,
        environment=_settings.environment,
    )

    # Validate date
    date_result = _validate_date(date)
    if isinstance(date_result, str):
        return date_result
    query_date, date_str = date_result

    # Validate shift
    if shift is not None and shift not in VALID_SHIFTS:
        valid_list = ", ".join(sorted(VALID_SHIFTS))
        return (
            f"Invalid shift '{shift}'. "
            f"Valid shifts are: {valid_list}. "
            "Omit the shift parameter to see all shifts."
        )

    try:
        raw_drivers = await get_driver_availability(
            date_str, shift, route_id, db_session_factory=ctx.deps.db_session_factory
        )

        # Build DriverInfo list
        drivers: list[DriverInfo] = []
        for d in raw_drivers:
            drivers.append(
                DriverInfo(
                    driver_id=str(d["driver_id"]),
                    name=str(d["name"]),
                    license_categories=d["license_categories"],  # type: ignore[arg-type]
                    qualified_route_ids=d["qualified_route_ids"],  # type: ignore[arg-type]
                    shift=str(d["shift"]),
                    status=str(d["status"]),
                    phone=str(phone_val) if isinstance(phone_val := d.get("phone"), str) else None,
                    notes=str(notes_val) if isinstance(notes_val := d.get("notes"), str) else None,
                )
            )

        # Compute shift summaries
        shift_groups: dict[str, list[DriverInfo]] = defaultdict(list)
        for driver in drivers:
            shift_groups[driver.shift].append(driver)

        shift_summaries: list[ShiftSummary] = []
        for shift_name in sorted(shift_groups.keys()):
            group = shift_groups[shift_name]
            shift_summaries.append(
                ShiftSummary(
                    shift=shift_name,
                    total_drivers=len(group),
                    available_count=sum(1 for d in group if d.status == "available"),
                    on_duty_count=sum(1 for d in group if d.status == "on_duty"),
                    on_leave_count=sum(1 for d in group if d.status == "on_leave"),
                    sick_count=sum(1 for d in group if d.status == "sick"),
                )
            )

        # Totals
        total_drivers = len(drivers)
        available_count = sum(1 for d in drivers if d.status == "available")

        # Build summary text
        service_type = _classify_service_type(query_date)
        shift_desc = f", {shift} shift" if shift else ""
        route_desc = f", route {route_id}" if route_id else ""

        if total_drivers == 0:
            summary = (
                f"No drivers found for {date_str} ({service_type}){shift_desc}{route_desc}. "
                "Try broadening your search by removing shift or route filters."
            )
        else:
            status_parts: list[str] = []
            on_duty = sum(1 for d in drivers if d.status == "on_duty")
            on_leave = sum(1 for d in drivers if d.status == "on_leave")
            sick = sum(1 for d in drivers if d.status == "sick")
            if on_duty:
                status_parts.append(f"{on_duty} on duty")
            if on_leave:
                status_parts.append(f"{on_leave} on leave")
            if sick:
                status_parts.append(f"{sick} sick")
            status_text = ", ".join(status_parts) if status_parts else "none unavailable"

            summary = (
                f"Driver availability for {date_str} ({service_type}){shift_desc}{route_desc}: "
                f"{available_count} available of {total_drivers} total. "
                f"Other: {status_text}."
            )

        report = DriverAvailabilityReport(
            report_date=date_str,
            service_type=service_type,
            shift_filter=shift,
            route_filter=route_id,
            total_drivers=total_drivers,
            available_count=available_count,
            shifts=shift_summaries,
            drivers=drivers[:_MAX_DRIVERS_RESPONSE],
            summary=summary,
        )

        duration_ms = int((time.monotonic() - start_time) * 1000)
        logger.info(
            "transit.check_driver_availability.completed",
            total_drivers=total_drivers,
            available_count=available_count,
            duration_ms=duration_ms,
        )

        return json.dumps(report.model_dump(), ensure_ascii=False)

    except Exception as e:
        duration_ms = int((time.monotonic() - start_time) * 1000)
        logger.error(
            "transit.check_driver_availability.failed",
            exc_info=True,
            error=str(e),
            error_type=type(e).__name__,
            duration_ms=duration_ms,
        )
        return (
            f"Driver data error: {e}. "
            "The driver management service may be temporarily unavailable. "
            "Try again in 30 seconds."
        )
