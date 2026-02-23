"""Transit tool: query_bus_status.

Provides real-time bus status, route overview, and stop departure
information by fetching GTFS-RT feeds from Rigas Satiksme.
"""

from __future__ import annotations

import json
import time
from datetime import UTC, datetime

from pydantic_ai import RunContext

from app.core.agents.tools.transit.client import (
    AlertData,
    GTFSRealtimeClient,
    TripUpdateData,
    VehiclePositionData,
)
from app.core.agents.tools.transit.deps import TransitDeps
from app.core.agents.tools.transit.schemas import (
    Alert,
    BusStatus,
    HeadwayInfo,
    Position,
    RouteOverview,
    StopDeparture,
    StopDepartures,
)
from app.core.agents.tools.transit.static_cache import GTFSStaticCache, get_static_cache
from app.core.agents.tools.transit.utils import delay_description
from app.core.logging import get_logger

logger = get_logger(__name__)

# Delay thresholds
_ON_TIME_THRESHOLD = 300  # +/- 5 minutes
_WARNING_THRESHOLD = 180  # 3 minutes
_CRITICAL_THRESHOLD = 600  # 10 minutes

_VALID_ACTIONS = ("status", "route_overview", "stop_departures")


def _severity(delay_seconds: int) -> str:
    """Classify delay severity for agent prioritization."""
    if abs(delay_seconds) < _WARNING_THRESHOLD:
        return "normal"
    if abs(delay_seconds) < _CRITICAL_THRESHOLD:
        return "warning"
    return "critical"


async def query_bus_status(
    ctx: RunContext[TransitDeps],
    action: str,
    route_id: str | None = None,
    vehicle_id: str | None = None,
    stop_id: str | None = None,
) -> str:
    """Query real-time bus status, delays, and positions for Riga's transit network.

    WHEN TO USE: Dispatcher asks about bus delays, vehicle locations, route performance,
    or upcoming departures at a stop. This is the primary tool for real-time operations.

    WHEN NOT TO USE: For historical performance analysis (use get_adherence_report),
    for timetable/schedule lookups (use get_route_schedule), or for finding stops by
    name or location (use search_stops).

    ACTIONS:
    - "status": Get current status of a specific vehicle or all vehicles on a route.
      Requires vehicle_id OR route_id. Returns position, delay, next stop.
    - "route_overview": Aggregate view of all vehicles on a route with headway analysis.
      Requires route_id. Best for "how is route X performing?" questions.
    - "stop_departures": Upcoming departures at a specific stop with real-time predictions.
      Requires stop_id. Best for "when is the next bus at stop Y?" questions.

    EFFICIENCY: Use "status" with vehicle_id for single-vehicle queries (fastest).
    Use "route_overview" only when the dispatcher asks about overall route performance.

    COMPOSITION: After this tool, consider get_route_schedule to compare against planned
    timetable, or get_adherence_report for historical context.

    Args:
        ctx: Pydantic AI run context with TransitDeps.
        action: One of "status", "route_overview", "stop_departures".
        route_id: GTFS route ID. Required for status (if no vehicle_id) and route_overview.
        vehicle_id: Fleet vehicle ID. Used for single-vehicle status queries.
        stop_id: GTFS stop ID. Required for stop_departures.

    Returns:
        JSON string with structured transit data or actionable error message.
    """
    start_time = time.monotonic()

    logger.info(
        "transit.query_bus_status.started",
        action=action,
        route_id=route_id,
        vehicle_id=vehicle_id,
        stop_id=stop_id,
    )

    # Validate action
    if action not in _VALID_ACTIONS:
        return (
            f"Invalid action '{action}'. "
            f"Use one of: {', '.join(_VALID_ACTIONS)}. "
            "Example: query_bus_status(action='status', route_id='22')"
        )

    # Validate required params
    validation_error = _validate_params(action, route_id, vehicle_id, stop_id)
    if validation_error:
        return validation_error

    try:
        client = GTFSRealtimeClient(ctx.deps.transit_http_client, ctx.deps.settings)
        static = await get_static_cache(ctx.deps.transit_http_client, ctx.deps.settings)

        if action == "status":
            result = await _handle_status(client, static, route_id, vehicle_id)
        elif action == "route_overview" and route_id is not None:
            result = await _handle_route_overview(client, static, route_id)
        elif action == "stop_departures" and stop_id is not None:
            result = await _handle_stop_departures(client, static, stop_id)
        else:
            return "Unexpected parameter combination."

        duration_ms = int((time.monotonic() - start_time) * 1000)
        logger.info(
            "transit.query_bus_status.completed",
            action=action,
            duration_ms=duration_ms,
        )
        return result

    except Exception as e:
        duration_ms = int((time.monotonic() - start_time) * 1000)
        logger.error(
            "transit.query_bus_status.failed",
            exc_info=True,
            error=str(e),
            error_type=type(e).__name__,
            duration_ms=duration_ms,
        )
        return (
            f"Transit data error: {e}. "
            "The Rigas Satiksme data service may be temporarily unavailable. "
            "Try again in 30 seconds."
        )


def _validate_params(
    action: str,
    route_id: str | None,
    vehicle_id: str | None,
    stop_id: str | None,
) -> str | None:
    """Validate required parameters for the given action.

    Returns:
        Error message string if invalid, None if valid.
    """
    if action == "status" and not route_id and not vehicle_id:
        return (
            "Action 'status' requires vehicle_id or route_id. "
            "Example: query_bus_status(action='status', route_id='22') "
            "or query_bus_status(action='status', vehicle_id='4521')"
        )
    if action == "route_overview" and not route_id:
        return (
            "Action 'route_overview' requires route_id. "
            "Example: query_bus_status(action='route_overview', route_id='22')"
        )
    if action == "stop_departures" and not stop_id:
        return (
            "Action 'stop_departures' requires stop_id. "
            "Use search_stops to find the stop_id first, then: "
            "query_bus_status(action='stop_departures', stop_id='a0072')"
        )
    return None


async def _handle_status(
    client: GTFSRealtimeClient,
    static: GTFSStaticCache,
    route_id: str | None,
    vehicle_id: str | None,
) -> str:
    """Handle the 'status' action."""
    vehicles = await client.fetch_vehicle_positions()
    trip_updates = await client.fetch_trip_updates()
    alerts = await client.fetch_alerts()

    # Build trip update lookup: trip_id -> TripUpdateData
    trip_update_map: dict[str, TripUpdateData] = {}
    for tu in trip_updates:
        trip_update_map[tu.trip_id] = tu

    # Filter vehicles
    filtered = vehicles
    if vehicle_id:
        filtered = [v for v in vehicles if v.vehicle_id == vehicle_id]
    elif route_id:
        filtered = [v for v in vehicles if v.route_id == route_id]

    if not filtered:
        target = f"vehicle {vehicle_id}" if vehicle_id else f"route {route_id}"
        return f"No active vehicles found for {target}. The service may not be running currently."

    # Build BusStatus for each vehicle
    statuses = _build_bus_statuses(filtered, trip_update_map, alerts, static)
    return json.dumps([s.model_dump() for s in statuses], ensure_ascii=False)


async def _handle_route_overview(
    client: GTFSRealtimeClient,
    static: GTFSStaticCache,
    route_id: str,
) -> str:
    """Handle the 'route_overview' action."""
    vehicles = await client.fetch_vehicle_positions()
    trip_updates = await client.fetch_trip_updates()
    alerts = await client.fetch_alerts()

    trip_update_map: dict[str, TripUpdateData] = {tu.trip_id: tu for tu in trip_updates}

    filtered = [v for v in vehicles if v.route_id == route_id]
    route_name = static.get_route_name(route_id)

    if not filtered:
        overview = RouteOverview(
            route_id=route_id,
            route_short_name=route_name,
            active_vehicles=0,
            vehicles=[],
            average_delay_seconds=0.0,
            on_time_count=0,
            late_count=0,
            early_count=0,
            summary=f"Route {route_name}: No active vehicles currently running.",
        )
        return json.dumps(overview.model_dump(), ensure_ascii=False)

    statuses = _build_bus_statuses(filtered, trip_update_map, alerts, static)

    # Aggregate stats
    delays = [s.delay_seconds for s in statuses]
    avg_delay = sum(delays) / len(delays) if delays else 0.0
    on_time = sum(1 for d in delays if abs(d) <= _ON_TIME_THRESHOLD)
    late = sum(1 for d in delays if d > _ON_TIME_THRESHOLD)
    early = sum(1 for d in delays if d < -_ON_TIME_THRESHOLD)

    # Headway calculation
    headway = _calculate_headway(filtered)

    # Summary
    bunching_note = ""
    if headway and headway.is_bunched:
        bunching_note = " Warning: vehicle bunching detected."

    summary = (
        f"Route {route_name}: {len(statuses)} active vehicles, "
        f"avg delay {avg_delay:.0f}s. "
        f"{on_time} on-time, {late} late, {early} early.{bunching_note}"
    )

    overview = RouteOverview(
        route_id=route_id,
        route_short_name=route_name,
        active_vehicles=len(statuses),
        vehicles=statuses,
        average_delay_seconds=round(avg_delay, 1),
        on_time_count=on_time,
        late_count=late,
        early_count=early,
        headway=headway,
        summary=summary,
    )
    return json.dumps(overview.model_dump(), ensure_ascii=False)


async def _handle_stop_departures(
    client: GTFSRealtimeClient,
    static: GTFSStaticCache,
    stop_id: str,
) -> str:
    """Handle the 'stop_departures' action."""
    trip_updates = await client.fetch_trip_updates()
    stop_name = static.get_stop_name(stop_id)

    departures: list[StopDeparture] = []
    for tu in trip_updates:
        for stu in tu.stop_time_updates:
            if stu.stop_id != stop_id:
                continue

            route_id_resolved = tu.route_id or static.get_trip_route_id(tu.trip_id) or ""
            route_name = static.get_route_name(route_id_resolved)
            delay = stu.arrival_delay or 0

            predicted = None
            if stu.arrival_time:
                predicted = datetime.fromtimestamp(stu.arrival_time, tz=UTC).isoformat()

            departures.append(
                StopDeparture(
                    route_id=route_id_resolved,
                    route_short_name=route_name,
                    vehicle_id=tu.vehicle_id,
                    trip_id=tu.trip_id,
                    predicted_arrival=predicted,
                    delay_seconds=delay,
                    delay_description=delay_description(delay),
                )
            )

    # Sort by predicted arrival (nulls last)
    departures.sort(key=lambda d: d.predicted_arrival or "9999")
    departures = departures[:10]  # Limit to 10

    if departures:
        lines = [f"Route {d.route_short_name} ({d.delay_description})" for d in departures[:5]]
        summary = f"Next departures at {stop_name}: " + ", ".join(lines)
    else:
        summary = f"No upcoming departures found at {stop_name}."

    result = StopDepartures(
        stop_id=stop_id,
        stop_name=stop_name,
        departures=departures,
        summary=summary,
    )
    return json.dumps(result.model_dump(), ensure_ascii=False)


def _build_bus_statuses(
    vehicles: list[VehiclePositionData],
    trip_update_map: dict[str, TripUpdateData],
    alerts: list[AlertData],
    static: GTFSStaticCache,
) -> list[BusStatus]:
    """Build BusStatus models from raw vehicle positions and trip updates."""
    statuses: list[BusStatus] = []
    for v in vehicles:
        route_id = v.route_id or (static.get_trip_route_id(v.trip_id) if v.trip_id else None) or ""
        route_name = static.get_route_name(route_id)

        # Get delay from trip update
        delay = 0
        next_stop_name: str | None = None
        predicted_arrival: str | None = None
        if v.trip_id and v.trip_id in trip_update_map:
            tu = trip_update_map[v.trip_id]
            if tu.stop_time_updates:
                # Find the next stop update
                relevant = tu.stop_time_updates
                if v.current_stop_sequence is not None:
                    relevant = [
                        s
                        for s in tu.stop_time_updates
                        if s.stop_sequence >= v.current_stop_sequence
                    ] or tu.stop_time_updates
                next_stu = relevant[0]
                delay = next_stu.arrival_delay or next_stu.departure_delay or 0
                if next_stu.stop_id:
                    next_stop_name = static.get_stop_name(next_stu.stop_id)
                if next_stu.arrival_time:
                    predicted_arrival = datetime.fromtimestamp(
                        next_stu.arrival_time, tz=UTC
                    ).isoformat()

        # Get current stop name
        current_stop_name = static.get_stop_name(v.stop_id) if v.stop_id else None

        # Get direction from trip headsign
        direction = static.get_trip_headsign(v.trip_id) if v.trip_id else None

        # Match alerts
        vehicle_alerts: list[Alert] = []
        for a in alerts:
            if route_id in a.route_ids or (v.stop_id and v.stop_id in a.stop_ids):
                vehicle_alerts.append(
                    Alert(
                        header=a.header_text,
                        description=a.description_text,
                        cause=a.cause,
                        effect=a.effect,
                    )
                )

        # Build position
        position = Position(
            latitude=v.latitude,
            longitude=v.longitude,
            bearing=v.bearing,
            speed_kmh=round(v.speed * 3.6, 1) if v.speed else None,
        )

        # Timestamp
        ts = datetime.fromtimestamp(v.timestamp, tz=UTC).isoformat() if v.timestamp else ""

        statuses.append(
            BusStatus(
                vehicle_id=v.vehicle_id,
                route_id=route_id,
                route_short_name=route_name,
                trip_id=v.trip_id,
                direction=direction,
                current_status=v.current_status,
                current_stop_name=current_stop_name,
                next_stop_name=next_stop_name,
                position=position,
                delay_seconds=delay,
                delay_description=delay_description(delay),
                predicted_arrival=predicted_arrival,
                timestamp=ts,
                severity=_severity(delay),
                alerts=vehicle_alerts,
            )
        )

    return statuses


def _calculate_headway(
    vehicles: list[VehiclePositionData],
) -> HeadwayInfo | None:
    """Calculate headway statistics for vehicles on a route."""
    # Need at least 2 vehicles for headway
    if len(vehicles) < 2:
        return None

    # Sort by timestamp to approximate headway gaps
    sorted_vehicles = sorted(vehicles, key=lambda v: v.timestamp)
    gaps_minutes: list[float] = []
    for i in range(1, len(sorted_vehicles)):
        gap = abs(sorted_vehicles[i].timestamp - sorted_vehicles[i - 1].timestamp) / 60.0
        if gap > 0:
            gaps_minutes.append(gap)

    if not gaps_minutes:
        return None

    avg_headway = sum(gaps_minutes) / len(gaps_minutes)
    is_bunched = any(gap < 2.0 for gap in gaps_minutes)

    return HeadwayInfo(
        average_headway_minutes=round(avg_headway, 1),
        is_bunched=is_bunched,
    )
