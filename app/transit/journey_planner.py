# pyright: reportUnknownMemberType=false, reportMissingTypeStubs=false, reportUnknownVariableType=false, reportUnknownArgumentType=false
"""Journey planner service — proxies OTP, enriches with GTFS-RT delay data, caches results."""

from __future__ import annotations

import datetime
import hashlib
import json
from datetime import UTC
from typing import Any, cast, get_args

import httpx

from app.core.agents.exceptions import TransitDataError
from app.core.config import Settings, get_settings
from app.core.logging import get_logger
from app.core.redis import get_redis
from app.transit.otp_client import OTPClient
from app.transit.schemas import (
    JourneyItinerary,
    JourneyLeg,
    JourneyPlanResponse,
    TransportMode,
)

logger = get_logger(__name__)

# Latvia bounding box
_LAT_MIN, _LAT_MAX = 55.5, 58.1
_LON_MIN, _LON_MAX = 20.5, 28.3

_VALID_MODES: set[str] = set(get_args(TransportMode))


class JourneyPlannerService:
    """Multi-modal journey planning with real-time delay enrichment."""

    def __init__(self, otp_client: OTPClient, settings: Settings) -> None:
        self._otp = otp_client
        self._settings = settings

    async def plan_journey(
        self,
        from_lat: float,
        from_lon: float,
        to_lat: float,
        to_lon: float,
        depart_at: datetime.datetime | None = None,
        arrive_by: datetime.datetime | None = None,
        modes: str = "TRANSIT,WALK",
    ) -> JourneyPlanResponse:
        """Plan a multi-modal journey between two points.

        Args:
            from_lat: Origin latitude (must be within Latvia bounds).
            from_lon: Origin longitude.
            to_lat: Destination latitude.
            to_lon: Destination longitude.
            depart_at: Desired departure time (UTC). Defaults to now.
            arrive_by: Desired arrival time (UTC). Mutually exclusive with depart_at.
            modes: Comma-separated OTP transport modes.

        Returns:
            JourneyPlanResponse with itineraries and optional delay enrichment.

        Raises:
            TransitDataError: If coordinates are outside Latvia or OTP fails.
        """
        # Validate coordinates
        for lat, lon, label in [
            (from_lat, from_lon, "origin"),
            (to_lat, to_lon, "destination"),
        ]:
            if not (_LAT_MIN <= lat <= _LAT_MAX and _LON_MIN <= lon <= _LON_MAX):
                raise TransitDataError(f"Coordinates for {label} are outside Latvia bounds")

        # Check cache
        cache_key = _cache_key(from_lat, from_lon, to_lat, to_lon, depart_at, arrive_by, modes)
        cached = await self._get_cached(cache_key)
        if cached is not None:
            logger.debug("transit.journey_planner.cache_hit", cache_key=cache_key)
            return cached

        # Build OTP params
        ref_time = depart_at or arrive_by or datetime.datetime.now(tz=UTC)
        params: dict[str, str] = {
            "fromPlace": f"{from_lat},{from_lon}",
            "toPlace": f"{to_lat},{to_lon}",
            "date": ref_time.strftime("%Y-%m-%d"),
            "time": ref_time.strftime("%H:%M"),
            "mode": modes,
            "numItineraries": str(self._settings.otp_max_itineraries),
            "maxWalkDistance": str(self._settings.otp_max_walk_distance_m),
        }
        if arrive_by is not None:
            params["arriveBy"] = "true"

        logger.info(
            "transit.journey_planner.plan_requested",
            from_lat=from_lat,
            from_lon=from_lon,
            to_lat=to_lat,
            to_lon=to_lon,
        )

        # Call OTP
        raw = await self._otp.plan(params)

        # Build delay map from Redis
        delay_map = await self._build_delay_map()
        enriched = delay_map is not None and len(delay_map) > 0

        # Map response
        plan_data: dict[str, Any] = raw.get("plan", {})
        itineraries_raw: list[dict[str, Any]] = plan_data.get("itineraries", [])
        itineraries = [_map_itinerary(itin, delay_map) for itin in itineraries_raw]

        from_place: dict[str, Any] = plan_data.get("from", {})
        to_place: dict[str, Any] = plan_data.get("to", {})

        result = JourneyPlanResponse(
            from_name=str(from_place.get("name", "Origin")),
            from_lat=from_lat,
            from_lon=from_lon,
            to_name=str(to_place.get("name", "Destination")),
            to_lat=to_lat,
            to_lon=to_lon,
            itineraries=itineraries,
            requested_at=datetime.datetime.now(tz=UTC),
            otp_enriched=enriched,
        )

        # Cache result
        await self._set_cached(cache_key, result)
        logger.info(
            "transit.journey_planner.plan_completed",
            itinerary_count=len(itineraries),
            enriched=enriched,
        )
        return result

    async def _build_delay_map(self) -> dict[str, int] | None:
        """Build trip_id -> delay_seconds map from Redis vehicle data."""
        try:
            redis_client = await get_redis()
            settings = self._settings
            delay_map: dict[str, int] = {}

            feed_ids = [f.feed_id for f in settings.transit_feeds if f.enabled]
            for fid in feed_ids:
                feed_key = f"feed:{fid}:vehicles"
                vehicle_ids_raw = await redis_client.smembers(feed_key)  # type: ignore[misc]
                vehicle_ids: list[str] = [str(vid) for vid in vehicle_ids_raw]
                if not vehicle_ids:
                    continue

                keys = [f"vehicle:{fid}:{vid}" for vid in vehicle_ids]
                values = await redis_client.mget(keys)

                for val in values:
                    if val is None:
                        continue
                    data: dict[str, Any] = json.loads(str(val))
                    trip_id = data.get("trip_id")
                    delay = data.get("delay_seconds")
                    if isinstance(trip_id, str) and isinstance(delay, int):
                        delay_map[trip_id] = delay

            return delay_map
        except Exception:
            logger.warning("transit.journey_planner.delay_map_failed", exc_info=True)
            return None

    async def _get_cached(self, key: str) -> JourneyPlanResponse | None:
        """Try to read a cached journey plan from Redis."""
        try:
            redis_client = await get_redis()
            raw = await redis_client.get(key)
            if raw is not None:
                return JourneyPlanResponse.model_validate_json(str(raw))
        except Exception:
            logger.debug("transit.journey_planner.cache_read_failed", exc_info=True)
        return None

    async def _set_cached(self, key: str, plan: JourneyPlanResponse) -> None:
        """Cache a journey plan in Redis with TTL."""
        try:
            redis_client = await get_redis()
            await redis_client.set(
                key,
                plan.model_dump_json(),
                ex=self._settings.otp_cache_ttl_seconds,
            )
        except Exception:
            logger.debug("transit.journey_planner.cache_write_failed", exc_info=True)


def _ms_to_dt(ms: int | float) -> datetime.datetime:
    """Convert OTP millisecond timestamp to timezone-aware datetime."""
    try:
        return datetime.datetime.fromtimestamp(ms / 1000, tz=UTC)
    except (ValueError, OSError, OverflowError):
        return datetime.datetime.now(tz=UTC)


def _map_itinerary(
    itin: dict[str, Any],
    delay_map: dict[str, int] | None,
) -> JourneyItinerary:
    """Map a single OTP itinerary dict to JourneyItinerary schema."""
    legs_raw: list[dict[str, Any]] = itin.get("legs", [])
    legs = [_map_leg(leg, delay_map) for leg in legs_raw]

    return JourneyItinerary(
        start_time=_ms_to_dt(itin.get("startTime", 0)),
        end_time=_ms_to_dt(itin.get("endTime", 0)),
        duration_seconds=int(itin.get("duration", 0)),
        walk_distance_m=float(itin.get("walkDistance", 0)),
        transit_time_seconds=int(itin.get("transitTime", 0)),
        waiting_time_seconds=int(itin.get("waitingTime", 0)),
        transfers=int(itin.get("transfers", 0)),
        legs=legs,
    )


def _map_leg(
    leg: dict[str, Any],
    delay_map: dict[str, int] | None,
) -> JourneyLeg:
    """Map a single OTP leg dict to JourneyLeg schema."""
    raw_mode = str(leg.get("mode", "WALK"))
    mode: str = raw_mode if raw_mode in _VALID_MODES else "WALK"

    from_place: dict[str, Any] = leg.get("from", {})
    to_place: dict[str, Any] = leg.get("to", {})

    start_time = _ms_to_dt(leg.get("startTime", 0))
    trip_id = leg.get("tripId")
    trip_id_str: str | None = str(trip_id) if trip_id is not None else None

    # Delay enrichment
    realtime_delay: int | None = None
    scheduled_start: datetime.datetime | None = None
    if trip_id_str and delay_map and trip_id_str in delay_map:
        realtime_delay = delay_map[trip_id_str]
        scheduled_start = start_time - datetime.timedelta(seconds=realtime_delay)

    polyline_data: dict[str, Any] | None = leg.get("legGeometry")
    polyline: str | None = None
    if isinstance(polyline_data, dict):
        points = polyline_data.get("points")
        if isinstance(points, str):
            polyline = points

    return JourneyLeg(
        mode=cast(TransportMode, mode),
        from_name=str(from_place.get("name", "")),
        from_lat=float(from_place.get("lat", 0)),
        from_lon=float(from_place.get("lon", 0)),
        to_name=str(to_place.get("name", "")),
        to_lat=float(to_place.get("lat", 0)),
        to_lon=float(to_place.get("lon", 0)),
        start_time=start_time,
        end_time=_ms_to_dt(leg.get("endTime", 0)),
        duration_seconds=int(leg.get("duration", 0)),
        distance_m=float(leg.get("distance", 0)),
        route_id=str(leg["routeId"]) if leg.get("routeId") is not None else None,
        route_short_name=str(leg["routeShortName"])
        if leg.get("routeShortName") is not None
        else None,
        route_long_name=str(leg["route"]) if leg.get("route") is not None else None,
        trip_id=trip_id_str,
        agency_name=str(leg["agencyName"]) if leg.get("agencyName") is not None else None,
        num_stops=int(leg["numIntermediateStops"])
        if leg.get("numIntermediateStops") is not None
        else None,
        realtime_delay_seconds=realtime_delay,
        scheduled_start_time=scheduled_start,
        polyline=polyline,
    )


def _cache_key(
    from_lat: float,
    from_lon: float,
    to_lat: float,
    to_lon: float,
    depart_at: datetime.datetime | None,
    arrive_by: datetime.datetime | None,
    modes: str,
) -> str:
    """Build a Redis cache key for a journey plan query.

    Rounds coordinates to 4 decimals (~11m) so nearby queries hit cache.
    """
    parts = (
        f"{from_lat:.4f}",
        f"{from_lon:.4f}",
        f"{to_lat:.4f}",
        f"{to_lon:.4f}",
        depart_at.isoformat() if depart_at else "",
        arrive_by.isoformat() if arrive_by else "",
        modes,
    )
    raw = "|".join(parts)
    digest = hashlib.md5(raw.encode(), usedforsecurity=False).hexdigest()[:12]
    return f"journey_plan:{digest}"


# --- Module-level singleton ---

_journey_planner: JourneyPlannerService | None = None
_http_client: httpx.AsyncClient | None = None


def get_journey_planner(settings: Settings | None = None) -> JourneyPlannerService:
    """Get or create the journey planner singleton.

    Args:
        settings: Optional settings override. Uses get_settings() if None.

    Returns:
        Singleton JourneyPlannerService instance.
    """
    global _journey_planner, _http_client
    if _journey_planner is None:
        if settings is None:
            settings = get_settings()
        _http_client = httpx.AsyncClient(
            timeout=httpx.Timeout(settings.otp_timeout_seconds, connect=5.0),
            limits=httpx.Limits(max_connections=5, max_keepalive_connections=3),
        )
        otp_client = OTPClient(http_client=_http_client, settings=settings)
        _journey_planner = JourneyPlannerService(otp_client=otp_client, settings=settings)
    return _journey_planner


async def close_journey_planner() -> None:
    """Close the singleton journey planner and its HTTP client."""
    global _journey_planner, _http_client
    if _http_client is not None:
        try:
            await _http_client.aclose()
        except RuntimeError:
            pass  # Event loop already closed during shutdown
        _http_client = None
    _journey_planner = None
