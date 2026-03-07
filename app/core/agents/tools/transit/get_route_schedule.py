"""Transit tool: get_route_schedule.

Provides planned timetable data for bus routes by querying static
GTFS data (stop_times, calendar, calendar_dates).
"""

from __future__ import annotations

import json
import time

from pydantic_ai import RunContext

from app.core.agents.tools.transit.deps import TransitDeps
from app.core.agents.tools.transit.schemas import (
    DirectionSchedule,
    RouteSchedule,
    TripSchedule,
)
from app.core.agents.tools.transit.static_cache import (
    StopTimeEntry,
    TripInfo,
)
from app.core.agents.tools.transit.static_store import get_static_store
from app.core.agents.tools.transit.utils import (
    classify_service_type,
    get_first_departure_minutes,
    gtfs_time_to_display,
    gtfs_time_to_minutes,
    validate_date,
)
from app.core.logging import get_logger

logger = get_logger(__name__)

_MAX_TRIPS_PER_DIRECTION = 30  # Token efficiency cap


def _build_direction_schedules(
    trips: list[TripInfo],
    trip_stop_times: dict[str, list[StopTimeEntry]],
) -> list[DirectionSchedule]:
    """Group trips by direction and build DirectionSchedule objects.

    Args:
        trips: Filtered list of trips for the route.
        trip_stop_times: Index of trip_id -> ordered stop times.

    Returns:
        List of DirectionSchedule, one per direction_id found.
    """
    # Group by direction_id
    by_direction: dict[int | None, list[TripInfo]] = {}
    for trip in trips:
        if trip.direction_id not in by_direction:
            by_direction[trip.direction_id] = []
        by_direction[trip.direction_id].append(trip)

    directions: list[DirectionSchedule] = []
    for direction_id in sorted(by_direction, key=lambda d: d if d is not None else -1):
        dir_trips = by_direction[direction_id]

        # Sort trips by first departure time
        dir_trips.sort(key=lambda t: get_first_departure_minutes(t, trip_stop_times))

        total_count = len(dir_trips)
        display_trips = dir_trips[:_MAX_TRIPS_PER_DIRECTION]

        # Build TripSchedule for each
        trip_schedules: list[TripSchedule] = []
        for trip in display_trips:
            stops = trip_stop_times.get(trip.trip_id, [])
            if stops:
                first_dep = gtfs_time_to_display(stops[0].departure_time)
                last_arr = gtfs_time_to_display(stops[-1].arrival_time)
            else:
                first_dep = "--:--"
                last_arr = "--:--"

            trip_schedules.append(
                TripSchedule(
                    trip_id=trip.trip_id,
                    direction_id=trip.direction_id,
                    headsign=trip.trip_headsign,
                    first_departure=first_dep,
                    last_arrival=last_arr,
                    stop_count=len(stops),
                )
            )

        # Direction-level summary times
        if trip_schedules:
            first_departure = trip_schedules[0].first_departure
            # For last departure, use last from full sorted list (not truncated)
            last_trip_stops = trip_stop_times.get(dir_trips[-1].trip_id, [])
            last_departure = (
                gtfs_time_to_display(last_trip_stops[0].departure_time)
                if last_trip_stops
                else trip_schedules[-1].first_departure
            )
        else:
            first_departure = "--:--"
            last_departure = "--:--"

        # Pick headsign from first trip that has one
        headsign: str | None = None
        for trip in dir_trips:
            if trip.trip_headsign:
                headsign = trip.trip_headsign
                break

        directions.append(
            DirectionSchedule(
                direction_id=direction_id,
                headsign=headsign,
                trip_count=total_count,
                first_departure=first_departure,
                last_departure=last_departure,
                trips=trip_schedules,
            )
        )

    return directions


async def get_route_schedule(
    ctx: RunContext[TransitDeps],
    route_id: str,
    date: str | None = None,
    direction_id: int | None = None,
    time_from: str | None = None,
    time_until: str | None = None,
) -> str:
    """Look up the planned timetable for a bus route on a specific service date.

    WHEN TO USE: Dispatcher asks about scheduled departure times, service hours,
    trip frequency, timetable, or "when does route X run?" questions. Returns
    the PLANNED schedule from GTFS static data.

    WHEN NOT TO USE: For current delays or vehicle positions (use query_bus_status
    instead). For historical on-time performance (use get_adherence_report).
    For finding stops by name or location (use search_stops).

    PARAMETERS:
    - route_id: GTFS route ID (e.g., "bus_22"). Required. If unsure, check
      query_bus_status(action="route_overview") output for valid route IDs.
    - date: Service date as YYYY-MM-DD. Defaults to today (Riga timezone).
      Use this to check future or past schedules.
    - direction_id: 0 or 1 to filter by direction. Omit for both directions.
      Direction 0 is typically outbound, 1 is inbound.
    - time_from: Filter trips departing after this time (HH:MM).
      Example: time_from="08:00" to see only morning trips.
    - time_until: Filter trips departing before this time (HH:MM).
      Example: time_until="12:00" combined with time_from="08:00".

    EFFICIENCY: Always provide direction_id and time_from/time_until when
    the question targets a specific period. Without filters, response may
    be truncated to 30 trips per direction.

    COMPOSITION: Compare with query_bus_status to see if real-time service
    matches the planned schedule. Chain: get_route_schedule → query_bus_status
    for "is route X running on schedule?" analysis.

    Args:
        ctx: Pydantic AI run context with TransitDeps.
        route_id: GTFS route identifier.
        date: Service date (YYYY-MM-DD). Defaults to today.
        direction_id: Direction filter (0 or 1).
        time_from: Start of time window filter (HH:MM).
        time_until: End of time window filter (HH:MM).

    Returns:
        JSON string with RouteSchedule data or actionable error message.
    """
    start_time = time.monotonic()

    logger.info(
        "transit.get_route_schedule.started",
        route_id=route_id,
        date=date,
        direction_id=direction_id,
        time_from=time_from,
        time_until=time_until,
    )

    # Validate date
    date_result = validate_date(date)
    if isinstance(date_result, str):
        return date_result
    query_date, date_str = date_result

    try:
        if ctx.deps.db_session_factory is None:
            return "Database session not available. Transit schedule data requires database access."
        static = await get_static_store(ctx.deps.db_session_factory, ctx.deps.settings)

        # Validate route exists
        if route_id not in static.routes:
            sample_routes = list(static.routes.keys())[:10]
            return (
                f"Route '{route_id}' not found in GTFS data. "
                f"Available routes include: {', '.join(sample_routes)}. "
                "Check route ID format."
            )

        route_info = static.routes[route_id]
        route_name = route_info.route_short_name

        # Get active service IDs for the date
        service_ids = static.get_active_service_ids(query_date)

        # Filter trips for this route that run on the queried date
        all_route_trips = static.route_trips.get(route_id, [])
        active_trips = [t for t in all_route_trips if t.service_id in service_ids]

        # No service check
        if not active_trips:
            day_name = query_date.strftime("%A")
            return (
                f"Route {route_name} exists but has no scheduled service "
                f"on {date_str} ({day_name}). "
                "Try an adjacent date or check if this is a holiday."
            )

        # Direction filter
        if direction_id is not None:
            active_trips = [t for t in active_trips if t.direction_id == direction_id]
            if not active_trips:
                return (
                    f"Route {route_name} has no trips in direction {direction_id} "
                    f"on {date_str}. Try direction_id={1 - direction_id} instead."
                )

        # Time window filter
        total_before_time_filter = len(active_trips)
        if time_from is not None or time_until is not None:
            from_minutes = gtfs_time_to_minutes(time_from) if time_from else 0
            until_minutes = gtfs_time_to_minutes(time_until) if time_until else 99999

            filtered: list[TripInfo] = []
            for trip in active_trips:
                dep_minutes = get_first_departure_minutes(trip, static.trip_stop_times)
                if from_minutes <= dep_minutes <= until_minutes:
                    filtered.append(trip)

            if not filtered:
                # Find actual first and last departures for the error message
                all_deps = [
                    get_first_departure_minutes(t, static.trip_stop_times) for t in active_trips
                ]
                valid_deps = [d for d in all_deps if d < 9999]
                if valid_deps:
                    first_dep = min(valid_deps)
                    last_dep = max(valid_deps)
                    first_h, first_m = divmod(first_dep, 60)
                    last_h, last_m = divmod(last_dep, 60)
                    return (
                        f"Route {route_name} has {total_before_time_filter} trips "
                        f"on {date_str}, but none between "
                        f"{time_from or '00:00'}-{time_until or '23:59'}. "
                        f"First departure: {first_h:02d}:{first_m:02d}, "
                        f"last: {last_h:02d}:{last_m:02d}."
                    )
                return (
                    f"Route {route_name} has trips on {date_str} but no stop time "
                    "data available for time filtering."
                )

            active_trips = filtered

        # Build direction schedules
        directions = _build_direction_schedules(active_trips, static.trip_stop_times)

        # Build summary
        service_type = classify_service_type(query_date)
        total_trips = sum(d.trip_count for d in directions)

        dir_summaries: list[str] = []
        for d in directions:
            label = d.headsign or f"Direction {d.direction_id}"
            dir_summaries.append(
                f"{label}: {d.trip_count} trips, {d.first_departure}-{d.last_departure}"
            )

        summary = (
            f"Route {route_name} ({route_info.route_long_name}): "
            f"{total_trips} trips on {date_str} ({service_type} schedule). "
            + ". ".join(dir_summaries)
            + "."
        )

        # Truncation note
        for d in directions:
            if d.trip_count > _MAX_TRIPS_PER_DIRECTION:
                summary += (
                    f" Note: showing {_MAX_TRIPS_PER_DIRECTION} of {d.trip_count} "
                    f"trips for {d.headsign or f'direction {d.direction_id}'}. "
                    "Use time_from/time_until to narrow results."
                )

        result = RouteSchedule(
            route_id=route_id,
            route_short_name=route_name,
            route_long_name=route_info.route_long_name,
            service_date=date_str,
            service_type=service_type,
            trip_count=total_trips,
            directions=directions,
            summary=summary,
        )

        duration_ms = int((time.monotonic() - start_time) * 1000)
        logger.info(
            "transit.get_route_schedule.completed",
            route_id=route_id,
            duration_ms=duration_ms,
            trip_count=total_trips,
        )

        return json.dumps(result.model_dump(), ensure_ascii=False)

    except Exception as e:
        duration_ms = int((time.monotonic() - start_time) * 1000)
        logger.error(
            "transit.get_route_schedule.failed",
            exc_info=True,
            error=str(e),
            error_type=type(e).__name__,
            duration_ms=duration_ms,
        )
        return (
            f"Transit data error: {e}. "
            "The GTFS data service may be temporarily unavailable. "
            "Try again in 30 seconds."
        )
