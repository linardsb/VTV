"""Pydantic response schemas for the transit REST API.

These models are optimized for the CMS frontend map component.
They are intentionally separate from the agent schemas in
app/core/agents/tools/transit/schemas.py, which are optimized
for LLM consumption.
"""

from pydantic import BaseModel, ConfigDict


class VehiclePosition(BaseModel):
    """A single vehicle's real-time position for map rendering.

    Attributes:
        vehicle_id: Fleet vehicle identifier (e.g., "4521").
        route_id: GTFS route identifier.
        route_short_name: Human-readable route number (e.g., "22").
        route_type: GTFS route type (0=tram, 3=bus, 11=trolleybus).
        latitude: WGS84 latitude.
        longitude: WGS84 longitude.
        bearing: Compass heading in degrees (0-360), if available.
        speed_kmh: Speed in km/h, if available.
        delay_seconds: Schedule deviation (positive=late, negative=early).
        current_status: One of "IN_TRANSIT_TO", "STOPPED_AT", "INCOMING_AT".
        next_stop_name: Name of next stop, if resolvable.
        current_stop_name: Name of current/nearest stop, if resolvable.
        timestamp: ISO 8601 when position was measured.
    """

    model_config = ConfigDict(strict=True)

    vehicle_id: str
    route_id: str
    route_short_name: str
    route_type: int
    latitude: float
    longitude: float
    bearing: float | None = None
    speed_kmh: float | None = None
    delay_seconds: int = 0
    current_status: str
    next_stop_name: str | None = None
    current_stop_name: str | None = None
    timestamp: str


class VehiclePositionsResponse(BaseModel):
    """Response wrapper for vehicle positions endpoint.

    Attributes:
        count: Number of vehicles in response.
        vehicles: List of vehicle positions.
        fetched_at: ISO 8601 server time when data was assembled.
    """

    model_config = ConfigDict(strict=True)

    count: int
    vehicles: list[VehiclePosition]
    fetched_at: str
