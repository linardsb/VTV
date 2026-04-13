"""Transit tools: intercity stop and route search via CKAN Datastore SQL API.

Provides search_intercity_stops and search_intercity_routes for querying
ATD (Autotransporta direkcija) intercity/regional transit data on data.gov.lv.
"""

from __future__ import annotations

import json
import time

from pydantic_ai import RunContext

from app.core.agents.exceptions import TransitDataError
from app.core.agents.tools.transit.deps import UnifiedDeps
from app.core.logging import get_logger
from app.shared.geo import haversine_distance
from app.transit.ckan_client import CKAN_RESOURCES, CKANClient, _escape_ckan_value

logger = get_logger(__name__)

_DEFAULT_LIMIT = 10
_MAX_LIMIT = 50


def _get_ckan_client(ctx: RunContext[UnifiedDeps]) -> CKANClient:
    """Construct a CKANClient from agent dependencies.

    Args:
        ctx: Pydantic AI run context with UnifiedDeps.

    Returns:
        Configured CKANClient instance.

    Raises:
        TransitDataError: If CKAN HTTP client is not available.
    """
    if ctx.deps.ckan_http_client is None:
        msg = "Intercity data is not available. CKAN HTTP client not configured."
        raise TransitDataError(msg)
    return CKANClient(ctx.deps.ckan_http_client, ctx.deps.settings)


async def search_intercity_stops(
    ctx: RunContext[UnifiedDeps],
    query: str | None = None,
    latitude: float | None = None,
    longitude: float | None = None,
    limit: int = 10,
) -> str:
    """Search for intercity/regional bus stops in Latvia via ATD data on data.gov.lv.

    WHEN TO USE: User asks about intercity or regional stops outside Riga
    (Liepaja, Ventspils, Jelgava, Daugavpils, etc.), ATD bus stops, or
    "starppilsetu pieturas". Covers all of Latvia's intercity bus network.

    WHEN NOT TO USE: For Riga city stops (use search_stops instead).
    For Riga municipal bus data (use query_bus_status or get_route_schedule).

    COMPOSITION: Use this to find intercity stop names/IDs, then pass stop
    names to search_intercity_routes to find routes serving those stops.

    EFFICIENCY: Name search is faster. Proximity search computes distances
    for all matching stops. Default limit is 10 (max 50).

    Args:
        ctx: Pydantic AI run context with UnifiedDeps.
        query: Search text for stop name (case-insensitive substring match).
        latitude: WGS84 latitude for proximity search.
        longitude: WGS84 longitude for proximity search.
        limit: Maximum results to return (default 10, max 50).

    Returns:
        JSON string with stops array or actionable error message.
    """
    start_time = time.monotonic()

    logger.info(
        "transit.ckan.search_stops_started",
        query=query,
        latitude=latitude,
        longitude=longitude,
        limit=limit,
    )

    if not query and latitude is None and longitude is None:
        return (
            "Please provide either a stop name (query) or coordinates "
            "(latitude + longitude) to search. "
            "Example: search_intercity_stops(query='Liepaja') or "
            "search_intercity_stops(latitude=56.51, longitude=21.01)"
        )

    if (latitude is None) != (longitude is None):
        return (
            "Both latitude and longitude are required for proximity search. "
            "Example: search_intercity_stops(latitude=56.51, longitude=21.01)"
        )

    effective_limit = min(max(limit, 1), _MAX_LIMIT)
    stops_resource = CKAN_RESOURCES["stops"]

    try:
        client = _get_ckan_client(ctx)

        if query:
            escaped = _escape_ckan_value(query)
            sql = (
                f'SELECT "stop_id", "stop_name", "stop_lat", "stop_lon" '  # noqa: S608
                f'FROM "{stops_resource}" '
                f"WHERE LOWER(\"stop_name\") LIKE LOWER('%{escaped}%') "
                f'ORDER BY "stop_name" '
                f"LIMIT {effective_limit}"
            )
            records = await client.query_sql(sql)
            stops = [
                {
                    "stop_id": r.get("stop_id", ""),
                    "stop_name": r.get("stop_name", ""),
                    "stop_lat": r.get("stop_lat"),
                    "stop_lon": r.get("stop_lon"),
                }
                for r in records
            ]
        else:
            # Proximity search: fetch all stops, compute haversine in Python
            if latitude is None or longitude is None:
                return "Both latitude and longitude are required for proximity search."
            sql = (
                f'SELECT "stop_id", "stop_name", "stop_lat", "stop_lon" '  # noqa: S608
                f'FROM "{stops_resource}" '
                f'WHERE "stop_lat" IS NOT NULL AND "stop_lon" IS NOT NULL'
            )
            records = await client.query_sql(sql)
            candidates: list[tuple[float, dict[str, object]]] = []
            for r in records:
                try:
                    slat = float(r["stop_lat"])
                    slon = float(r["stop_lon"])
                except (ValueError, TypeError, KeyError):
                    continue
                dist = haversine_distance(latitude, longitude, slat, slon)
                candidates.append(
                    (
                        dist,
                        {
                            "stop_id": r.get("stop_id", ""),
                            "stop_name": r.get("stop_name", ""),
                            "stop_lat": slat,
                            "stop_lon": slon,
                            "distance_m": round(dist),
                        },
                    )
                )
            candidates.sort(key=lambda x: x[0])
            stops = [c[1] for c in candidates[:effective_limit]]

        duration_ms = int((time.monotonic() - start_time) * 1000)
        logger.info(
            "transit.ckan.search_stops_completed",
            result_count=len(stops),
            duration_ms=duration_ms,
        )

        result = {
            "result_count": len(stops),
            "stops": stops,
        }
        return json.dumps(result, ensure_ascii=False)

    except TransitDataError:
        raise
    except Exception as exc:
        duration_ms = int((time.monotonic() - start_time) * 1000)
        logger.error(
            "transit.ckan.search_stops_failed",
            error=str(exc),
            error_type=type(exc).__name__,
            duration_ms=duration_ms,
        )
        return (
            "Intercity stop search failed. "
            "The data.gov.lv service may be temporarily unavailable. "
            "Try again in 30 seconds."
        )


async def search_intercity_routes(
    ctx: RunContext[UnifiedDeps],
    query: str | None = None,
    stop_name: str | None = None,
) -> str:
    """Search for intercity/regional bus routes in Latvia via ATD data on data.gov.lv.

    WHEN TO USE: User asks about intercity or regional bus routes, "Which
    buses go to Liepaja?", "starppilsetu marsruti", ATD routes, or regional
    connections between Latvian cities.

    WHEN NOT TO USE: For Riga city routes (use query_bus_status or
    get_route_schedule instead).

    COMPOSITION: Use search_intercity_stops first to resolve stop names,
    then pass the stop name here to find routes serving that stop.

    EFFICIENCY: Route name search is fast. Stop-based filtering requires
    joining across GTFS tables and is slower. Limit defaults to 20 routes.

    Args:
        ctx: Pydantic AI run context with UnifiedDeps.
        query: Search text for route name/number (case-insensitive).
        stop_name: Find routes passing through this stop name.

    Returns:
        JSON string with routes array or actionable error message.
    """
    start_time = time.monotonic()

    logger.info(
        "transit.ckan.search_routes_started",
        query=query,
        stop_name=stop_name,
    )

    if not query and not stop_name:
        return (
            "Please provide a route name/number (query) or a stop name (stop_name). "
            "Example: search_intercity_routes(query='Liepaja') or "
            "search_intercity_routes(stop_name='Liepaja AS')"
        )

    routes_resource = CKAN_RESOURCES["routes"]

    try:
        client = _get_ckan_client(ctx)

        if query and not stop_name:
            escaped = _escape_ckan_value(query)
            sql = (
                f'SELECT DISTINCT "route_id", "route_short_name", "route_long_name" '  # noqa: S608
                f'FROM "{routes_resource}" '
                f"WHERE LOWER(\"route_long_name\") LIKE LOWER('%{escaped}%') "
                f"OR LOWER(\"route_short_name\") LIKE LOWER('%{escaped}%') "
                f'ORDER BY "route_short_name" '
                f"LIMIT 20"
            )
            records = await client.query_sql(sql)
        elif stop_name:
            escaped_stop = _escape_ckan_value(stop_name)
            stops_resource = CKAN_RESOURCES["stops"]
            trips_resource = CKAN_RESOURCES["trips"]
            stop_times_resource = CKAN_RESOURCES["stop_times"]

            sql = (
                f'SELECT DISTINCT r."route_id", r."route_short_name", r."route_long_name" '  # noqa: S608
                f'FROM "{routes_resource}" r '
                f'JOIN "{trips_resource}" t ON r."route_id" = t."route_id" '
                f'JOIN "{stop_times_resource}" st ON t."trip_id" = st."trip_id" '
                f'JOIN "{stops_resource}" s ON st."stop_id" = s."stop_id" '
                f"WHERE LOWER(s.\"stop_name\") LIKE LOWER('%{escaped_stop}%') "
                f'ORDER BY r."route_short_name" '
                f"LIMIT 20"
            )
            records = await client.query_sql(sql)
        else:
            records = []

        routes = [
            {
                "route_id": r.get("route_id", ""),
                "route_short_name": r.get("route_short_name", ""),
                "route_long_name": r.get("route_long_name", ""),
            }
            for r in records
        ]

        duration_ms = int((time.monotonic() - start_time) * 1000)
        logger.info(
            "transit.ckan.search_routes_completed",
            result_count=len(routes),
            duration_ms=duration_ms,
        )

        result = {
            "result_count": len(routes),
            "routes": routes,
        }
        return json.dumps(result, ensure_ascii=False)

    except TransitDataError:
        raise
    except Exception as exc:
        duration_ms = int((time.monotonic() - start_time) * 1000)
        logger.error(
            "transit.ckan.search_routes_failed",
            error=str(exc),
            error_type=type(exc).__name__,
            duration_ms=duration_ms,
        )
        return (
            "Intercity route search failed. "
            "The data.gov.lv service may be temporarily unavailable. "
            "Try again in 30 seconds."
        )
