"""Transit tool: search_stops.

Provides stop search capabilities by name (text substring) or
geographic proximity (lat/lon radius) using GTFS static data.
"""

from __future__ import annotations

import json
import math
import time

from pydantic_ai import RunContext

from app.core.agents.tools.transit.deps import TransitDeps
from app.core.agents.tools.transit.schemas import (
    StopResult,
    StopSearchResults,
)
from app.core.agents.tools.transit.static_cache import StopInfo, get_static_cache
from app.core.logging import get_logger

logger = get_logger(__name__)

_VALID_ACTIONS = ("search", "nearby")
_DEFAULT_RADIUS_METERS = 500
_MAX_RADIUS_METERS = 2000
_DEFAULT_LIMIT = 10
_MAX_LIMIT = 25
_EARTH_RADIUS_METERS = 6_371_000


def _haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate great-circle distance between two points in meters.

    Uses the Haversine formula for accuracy at city-scale distances.

    Args:
        lat1: Latitude of first point (WGS84 degrees).
        lon1: Longitude of first point (WGS84 degrees).
        lat2: Latitude of second point (WGS84 degrees).
        lon2: Longitude of second point (WGS84 degrees).

    Returns:
        Distance in meters.
    """
    lat1_r = math.radians(lat1)
    lat2_r = math.radians(lat2)
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2) ** 2 + math.cos(lat1_r) * math.cos(lat2_r) * math.sin(dlon / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return _EARTH_RADIUS_METERS * c


def _validate_search_params(
    action: str,
    query: str | None,
    latitude: float | None,
    longitude: float | None,
) -> str | None:
    """Validate required parameters for the given action.

    Returns:
        Error message string if invalid, None if valid.
    """
    if action not in _VALID_ACTIONS:
        return (
            f"Invalid action '{action}'. "
            f"Use one of: {', '.join(_VALID_ACTIONS)}. "
            "Example: search_stops(action='search', query='Brīvības')"
        )
    if action == "search" and not query:
        return (
            "Action 'search' requires a query string. "
            "Example: search_stops(action='search', query='Centrālā stacija')"
        )
    if action == "nearby" and (latitude is None or longitude is None):
        return (
            "Action 'nearby' requires both latitude and longitude. "
            "Example: search_stops(action='nearby', latitude=56.9496, longitude=24.1052)"
        )
    return None


def _search_by_name(
    stops: dict[str, StopInfo],
    stop_routes: dict[str, list[str]],
    query: str,
    limit: int,
) -> tuple[list[StopResult], int]:
    """Search stops by case-insensitive substring match on stop name.

    Args:
        stops: All stops from the static cache.
        stop_routes: Stop-to-route-names index.
        query: Search text (case-insensitive substring).
        limit: Maximum results to return.

    Returns:
        Tuple of (limited results list, total match count).
    """
    query_lower = query.lower()
    matches: list[StopInfo] = []
    for stop in stops.values():
        if query_lower in stop.stop_name.lower():
            matches.append(stop)

    matches.sort(key=lambda s: s.stop_name)
    total = len(matches)

    results: list[StopResult] = []
    for stop in matches[:limit]:
        results.append(
            StopResult(
                stop_id=stop.stop_id,
                stop_name=stop.stop_name,
                stop_lat=stop.stop_lat,
                stop_lon=stop.stop_lon,
                routes=stop_routes.get(stop.stop_id),
            )
        )
    return results, total


def _search_nearby(
    stops: dict[str, StopInfo],
    stop_routes: dict[str, list[str]],
    latitude: float,
    longitude: float,
    radius_meters: int,
    limit: int,
) -> tuple[list[StopResult], int]:
    """Search stops within a radius of a geographic point, sorted by distance.

    Args:
        stops: All stops from the static cache.
        stop_routes: Stop-to-route-names index.
        latitude: Center point latitude.
        longitude: Center point longitude.
        radius_meters: Search radius in meters.
        limit: Maximum results to return.

    Returns:
        Tuple of (limited results list, total match count).
    """
    candidates: list[tuple[float, StopInfo]] = []
    for stop in stops.values():
        if stop.stop_lat is None or stop.stop_lon is None:
            continue
        dist = _haversine_distance(latitude, longitude, stop.stop_lat, stop.stop_lon)
        if dist <= radius_meters:
            candidates.append((dist, stop))

    candidates.sort(key=lambda pair: pair[0])
    total = len(candidates)

    results: list[StopResult] = []
    for dist, stop in candidates[:limit]:
        results.append(
            StopResult(
                stop_id=stop.stop_id,
                stop_name=stop.stop_name,
                stop_lat=stop.stop_lat,
                stop_lon=stop.stop_lon,
                distance_meters=round(dist),
                routes=stop_routes.get(stop.stop_id),
            )
        )
    return results, total


async def search_stops(
    ctx: RunContext[TransitDeps],
    action: str,
    query: str | None = None,
    latitude: float | None = None,
    longitude: float | None = None,
    radius_meters: int | None = None,
    limit: int | None = None,
) -> str:
    """Search for bus stops by name or geographic proximity in Riga's transit network.

    WHEN TO USE: Dispatcher asks "where is stop X?", "find stops near Y",
    "what's the stop ID for Z?", or needs a stop_id for use with other tools.
    This is the entry point for all stop-related queries.

    WHEN NOT TO USE: For real-time departures at a known stop (use
    query_bus_status with action="stop_departures"). For route schedules
    (use get_route_schedule). For route delays (use query_bus_status).

    ACTIONS:
    - "search": Find stops by name (case-insensitive substring match).
      Requires query. Example: search_stops(action="search", query="Brīvības")
    - "nearby": Find stops within a radius of a lat/lon point, sorted by distance.
      Requires latitude and longitude. Default radius is 500m (max 2000m).
      Example: search_stops(action="nearby", latitude=56.9496, longitude=24.1052)

    EFFICIENCY: Use "search" for name lookups (fast). Use "nearby" only when
    the dispatcher provides or implies a geographic location. Default limit
    is 10 results (max 25).

    COMPOSITION: After finding a stop_id, chain with:
    - query_bus_status(action="stop_departures", stop_id=...) for live arrivals
    - get_route_schedule(route_id=...) to check if a route serves the stop

    Args:
        ctx: Pydantic AI run context with TransitDeps.
        action: One of "search" (by name) or "nearby" (by location).
        query: Search text for name matching (required for "search").
        latitude: WGS84 latitude of center point (required for "nearby").
        longitude: WGS84 longitude of center point (required for "nearby").
        radius_meters: Search radius for "nearby" in meters (default 500, max 2000).
        limit: Maximum results to return (default 10, max 25).

    Returns:
        JSON string with StopSearchResults data or actionable error message.
    """
    start_time = time.monotonic()

    logger.info(
        "transit.search_stops.started",
        action=action,
        query=query,
        latitude=latitude,
        longitude=longitude,
        radius_meters=radius_meters,
    )

    # Validate parameters
    validation_error = _validate_search_params(action, query, latitude, longitude)
    if validation_error:
        return validation_error

    # Clamp limit and radius
    effective_limit = min(max(limit or _DEFAULT_LIMIT, 1), _MAX_LIMIT)
    effective_radius = min(max(radius_meters or _DEFAULT_RADIUS_METERS, 1), _MAX_RADIUS_METERS)

    try:
        static = await get_static_cache(ctx.deps.transit_http_client, ctx.deps.settings)

        if action == "search" and query is not None:
            results, total = _search_by_name(
                static.stops, static.stop_routes, query, effective_limit
            )
        elif action == "nearby" and latitude is not None and longitude is not None:
            results, total = _search_nearby(
                static.stops,
                static.stop_routes,
                latitude,
                longitude,
                effective_radius,
                effective_limit,
            )
        else:
            return "Unexpected parameter combination."

        # Build summary
        if action == "search":
            if results:
                stop_names = [s.stop_name for s in results[:5]]
                summary = (
                    f"Found {total} stops matching '{query}': "
                    + ", ".join(stop_names)
                    + ("..." if total > 5 else "")
                    + ". Use stop_id with query_bus_status(action='stop_departures') "
                    "for live departures."
                )
            else:
                summary = (
                    f"No stops found matching '{query}'. "
                    "Try a shorter search term or check spelling. "
                    "Latvian stop names use diacritics (ā, ē, ī, ū, š, ž)."
                )
        else:
            if results:
                nearest = results[0]
                summary = (
                    f"Found {total} stops within {effective_radius}m of "
                    f"({latitude}, {longitude}). "
                    f"Nearest: {nearest.stop_name} ({nearest.distance_meters}m). "
                    "Use stop_id with query_bus_status(action='stop_departures') "
                    "for live departures."
                )
            else:
                summary = (
                    f"No stops found within {effective_radius}m of "
                    f"({latitude}, {longitude}). "
                    f"Try increasing radius_meters (max {_MAX_RADIUS_METERS})."
                )

        result = StopSearchResults(
            action=action,
            query=query,
            result_count=len(results),
            total_matches=total,
            stops=results,
            summary=summary,
        )

        duration_ms = int((time.monotonic() - start_time) * 1000)
        logger.info(
            "transit.search_stops.completed",
            action=action,
            result_count=len(results),
            total_matches=total,
            duration_ms=duration_ms,
        )

        return json.dumps(result.model_dump(), ensure_ascii=False)

    except Exception as e:
        duration_ms = int((time.monotonic() - start_time) * 1000)
        logger.error(
            "transit.search_stops.failed",
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
