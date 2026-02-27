"""Geographic utility functions.

Shared spatial calculations used by the transit agent tools
for in-memory proximity filtering on GTFS static cache data.
"""

import math

_EARTH_RADIUS_METERS = 6_371_000


def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate great-circle distance between two points in meters.

    Uses the Haversine formula for accuracy at city-scale distances.
    Used by the agent search_stops tool for in-memory proximity filtering
    on GTFS static cache data.

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
