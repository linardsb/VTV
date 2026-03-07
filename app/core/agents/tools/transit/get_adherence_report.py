"""Transit tool: get_adherence_report.

Computes on-time performance metrics by cross-referencing real-time
GTFS-RT delay data with the planned GTFS static schedule.
"""

from __future__ import annotations

import json
import time

from pydantic_ai import RunContext

from app.core.agents.tools.transit.client import GTFSRealtimeClient, TripUpdateData
from app.core.agents.tools.transit.deps import TransitDeps
from app.core.agents.tools.transit.schemas import (
    AdherenceReport,
    RouteAdherence,
    TripAdherence,
)
from app.core.agents.tools.transit.static_cache import (
    StopTimeEntry,
    TripInfo,
)
from app.core.agents.tools.transit.static_store import get_static_store
from app.core.agents.tools.transit.utils import (
    classify_service_type,
    delay_description,
    get_first_departure_minutes,
    gtfs_time_to_display,
    gtfs_time_to_minutes,
    validate_date,
)
from app.core.logging import get_logger

logger = get_logger(__name__)

_ON_TIME_THRESHOLD = 300  # +/- 5 minutes
_MAX_TRIPS_PER_ROUTE = 30  # Token efficiency cap
_MAX_ROUTES_NETWORK = 15  # Cap for network-wide report


def _classify_trip_status(delay_seconds: int) -> str:
    """Classify trip adherence status based on delay threshold.

    Args:
        delay_seconds: Delay in seconds (positive=late, negative=early).

    Returns:
        One of "on_time", "late", "early".
    """
    if abs(delay_seconds) <= _ON_TIME_THRESHOLD:
        return "on_time"
    if delay_seconds > _ON_TIME_THRESHOLD:
        return "late"
    return "early"


def _compute_route_adherence(
    route_id: str,
    route_name: str,
    scheduled_trips: list[TripInfo],
    trip_update_map: dict[str, TripUpdateData],
    trip_stop_times: dict[str, list[StopTimeEntry]],
    time_from_minutes: int | None,
    time_until_minutes: int | None,
) -> RouteAdherence:
    """Compute adherence metrics for a single route.

    Args:
        route_id: GTFS route identifier.
        route_name: Human-readable route short name.
        scheduled_trips: Trips scheduled for this route on the service date.
        trip_update_map: Real-time trip updates keyed by trip_id.
        trip_stop_times: Static schedule stop times keyed by trip_id.
        time_from_minutes: Start of time window in minutes, or None.
        time_until_minutes: End of time window in minutes, or None.

    Returns:
        Populated RouteAdherence with per-trip and aggregate metrics.
    """
    trip_adherences: list[TripAdherence] = []

    for trip in scheduled_trips:
        # Get first departure time
        dep_minutes = get_first_departure_minutes(trip, trip_stop_times)

        # Apply time window filter
        if time_from_minutes is not None and dep_minutes < time_from_minutes:
            continue
        if time_until_minutes is not None and dep_minutes > time_until_minutes:
            continue

        stops = trip_stop_times.get(trip.trip_id, [])
        scheduled_dep = gtfs_time_to_display(stops[0].departure_time) if stops else "--:--"

        # Look up real-time data
        tu = trip_update_map.get(trip.trip_id)
        if tu is not None and tu.stop_time_updates:
            stu = tu.stop_time_updates[0]
            delay = stu.arrival_delay or stu.departure_delay or 0
            status = _classify_trip_status(delay)
            trip_adherences.append(
                TripAdherence(
                    trip_id=trip.trip_id,
                    direction_id=trip.direction_id,
                    headsign=trip.trip_headsign,
                    scheduled_departure=scheduled_dep,
                    delay_seconds=delay,
                    delay_description=delay_description(delay),
                    status=status,
                    vehicle_id=tu.vehicle_id,
                )
            )
        else:
            trip_adherences.append(
                TripAdherence(
                    trip_id=trip.trip_id,
                    direction_id=trip.direction_id,
                    headsign=trip.trip_headsign,
                    scheduled_departure=scheduled_dep,
                    delay_seconds=0,
                    delay_description="no data",
                    status="no_data",
                )
            )

    # Aggregate
    tracked = [t for t in trip_adherences if t.status != "no_data"]
    no_data_count = len(trip_adherences) - len(tracked)
    on_time_count = sum(1 for t in tracked if t.status == "on_time")
    late_count = sum(1 for t in tracked if t.status == "late")
    early_count = sum(1 for t in tracked if t.status == "early")

    if tracked:
        on_time_pct = round(on_time_count / len(tracked) * 100, 1)
        avg_delay = round(sum(t.delay_seconds for t in tracked) / len(tracked), 1)
        worst = max(tracked, key=lambda t: abs(t.delay_seconds))
    else:
        on_time_pct = 0.0
        avg_delay = 0.0
        worst = None

    return RouteAdherence(
        route_id=route_id,
        route_short_name=route_name,
        scheduled_trips=len(trip_adherences),
        tracked_trips=len(tracked),
        on_time_count=on_time_count,
        late_count=late_count,
        early_count=early_count,
        no_data_count=no_data_count,
        on_time_percentage=on_time_pct,
        average_delay_seconds=avg_delay,
        worst_trip=worst,
        trips=trip_adherences[:_MAX_TRIPS_PER_ROUTE],
    )


async def get_adherence_report(
    ctx: RunContext[TransitDeps],
    route_id: str | None = None,
    date: str | None = None,
    time_from: str | None = None,
    time_until: str | None = None,
) -> str:
    """Analyze on-time performance for a route or the entire transit network.

    WHEN TO USE: Dispatcher asks about punctuality, on-time performance,
    service reliability, delay patterns, or "how is route X performing today?"
    questions. Returns aggregate metrics comparing real-time data vs schedule.

    WHEN NOT TO USE: For current vehicle positions or delays (use query_bus_status).
    For the planned timetable without real-time comparison (use get_route_schedule).
    For finding stops (use search_stops).

    PARAMETERS:
    - route_id: GTFS route ID for single-route analysis. Omit for network-wide
      summary of all routes with active vehicles. Network reports are capped at
      15 routes sorted by worst on-time percentage.
    - date: Service date as YYYY-MM-DD. Defaults to today (Riga timezone).
      Determines which scheduled trips to compare against.
    - time_from: Start of analysis window (HH:MM). Filters to trips departing
      after this time. Example: "07:00" for morning peak analysis.
    - time_until: End of analysis window (HH:MM). Filters to trips departing
      before this time.

    EFFICIENCY: For quick network health checks, omit route_id.
    For detailed single-route analysis, always provide route_id.
    Use time_from/time_until to focus on peak periods.

    COMPOSITION: After identifying underperforming routes, use
    query_bus_status(action="route_overview") for live vehicle details, or
    get_route_schedule for the planned timetable comparison.

    Args:
        ctx: Pydantic AI run context with TransitDeps.
        route_id: GTFS route identifier for single-route report, or None for network.
        date: Service date (YYYY-MM-DD). Defaults to today.
        time_from: Start of time window filter (HH:MM).
        time_until: End of time window filter (HH:MM).

    Returns:
        JSON string with AdherenceReport data or actionable error message.
    """
    start_time = time.monotonic()

    logger.info(
        "transit.get_adherence_report.started",
        route_id=route_id,
        date=date,
        time_from=time_from,
        time_until=time_until,
    )

    # Validate date
    date_result = validate_date(date)
    if isinstance(date_result, str):
        return date_result
    query_date, date_str = date_result

    try:
        client = GTFSRealtimeClient(ctx.deps.transit_http_client, ctx.deps.settings)
        if ctx.deps.db_session_factory is None:
            return "Database session not available. Adherence report requires database access."
        static = await get_static_store(ctx.deps.db_session_factory, ctx.deps.settings)
        trip_updates = await client.fetch_trip_updates()

        # Build trip update lookup
        trip_update_map: dict[str, TripUpdateData] = {tu.trip_id: tu for tu in trip_updates}

        # Active services for the date
        service_ids = static.get_active_service_ids(query_date)

        # Time window
        time_from_minutes = gtfs_time_to_minutes(time_from) if time_from else None
        time_until_minutes = gtfs_time_to_minutes(time_until) if time_until else None

        service_type = classify_service_type(query_date)
        route_adherences: list[RouteAdherence] = []

        if route_id is not None:
            # --- Single route report ---
            if route_id not in static.routes:
                sample_routes = list(static.routes.keys())[:10]
                return (
                    f"Route '{route_id}' not found in GTFS data. "
                    f"Available routes include: {', '.join(sample_routes)}. "
                    "Check route ID format."
                )

            route_info = static.routes[route_id]
            route_name = route_info.route_short_name

            all_route_trips = static.route_trips.get(route_id, [])
            active_trips = [t for t in all_route_trips if t.service_id in service_ids]

            if not active_trips:
                day_name = query_date.strftime("%A")
                return (
                    f"Route {route_name} has no scheduled service on "
                    f"{date_str} ({day_name}). "
                    "Try an adjacent date or check if this is a holiday."
                )

            adherence = _compute_route_adherence(
                route_id,
                route_name,
                active_trips,
                trip_update_map,
                static.trip_stop_times,
                time_from_minutes,
                time_until_minutes,
            )
            route_adherences.append(adherence)

            summary = (
                f"Route {route_name} adherence on {date_str} ({service_type}): "
                f"{adherence.on_time_percentage}% on-time "
                f"({adherence.tracked_trips} tracked of {adherence.scheduled_trips} scheduled). "
                f"Avg delay: {adherence.average_delay_seconds}s. "
                f"{adherence.on_time_count} on-time, {adherence.late_count} late, "
                f"{adherence.early_count} early, {adherence.no_data_count} no data."
            )

            report = AdherenceReport(
                report_type="route",
                route_id=route_id,
                service_date=date_str,
                service_type=service_type,
                time_from=time_from,
                time_until=time_until,
                routes=route_adherences,
                summary=summary,
            )

        else:
            # --- Network report ---
            # Find routes that have at least one trip with real-time data
            rt_route_ids: set[str] = set()
            for tu in trip_updates:
                trip_info = static.trips.get(tu.trip_id)
                if trip_info is not None:
                    rt_route_ids.add(trip_info.route_id)

            for rid in rt_route_ids:
                if rid not in static.routes:
                    continue
                r_info = static.routes[rid]
                all_trips = static.route_trips.get(rid, [])
                active = [t for t in all_trips if t.service_id in service_ids]
                if not active:
                    continue

                adherence = _compute_route_adherence(
                    rid,
                    r_info.route_short_name,
                    active,
                    trip_update_map,
                    static.trip_stop_times,
                    time_from_minutes,
                    time_until_minutes,
                )
                if adherence.scheduled_trips > 0:
                    route_adherences.append(adherence)

            # Sort by worst on-time percentage (ascending)
            route_adherences.sort(key=lambda r: r.on_time_percentage)
            route_adherences = route_adherences[:_MAX_ROUTES_NETWORK]

            # Network averages
            total_tracked = sum(r.tracked_trips for r in route_adherences)
            total_on_time = sum(r.on_time_count for r in route_adherences)
            total_delay_sum = sum(
                r.average_delay_seconds * r.tracked_trips for r in route_adherences
            )
            network_on_time_pct = (
                round(total_on_time / total_tracked * 100, 1) if total_tracked > 0 else 0.0
            )
            network_avg_delay = (
                round(total_delay_sum / total_tracked, 1) if total_tracked > 0 else 0.0
            )

            if route_adherences:
                worst_route = route_adherences[0]
                summary = (
                    f"Network adherence on {date_str} ({service_type}): "
                    f"{network_on_time_pct}% on-time across "
                    f"{len(route_adherences)} routes ({total_tracked} tracked trips). "
                    f"Avg delay: {network_avg_delay}s. "
                    f"Worst: Route {worst_route.route_short_name} "
                    f"({worst_route.on_time_percentage}% on-time)."
                )
            else:
                summary = (
                    f"No real-time data available for any routes on {date_str}. "
                    "The Rigas Satiksme GTFS-RT feed may be temporarily unavailable."
                )

            report = AdherenceReport(
                report_type="network",
                service_date=date_str,
                service_type=service_type,
                time_from=time_from,
                time_until=time_until,
                routes=route_adherences,
                network_on_time_percentage=network_on_time_pct,
                network_average_delay_seconds=network_avg_delay,
                summary=summary,
            )

        duration_ms = int((time.monotonic() - start_time) * 1000)
        logger.info(
            "transit.get_adherence_report.completed",
            report_type=report.report_type,
            route_count=len(route_adherences),
            total_tracked_trips=sum(r.tracked_trips for r in route_adherences),
            duration_ms=duration_ms,
        )

        return json.dumps(report.model_dump(), ensure_ascii=False)

    except Exception as e:
        duration_ms = int((time.monotonic() - start_time) * 1000)
        logger.error(
            "transit.get_adherence_report.failed",
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
