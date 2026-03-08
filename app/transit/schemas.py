"""Pydantic response schemas for the transit REST API.

These models are optimized for the CMS frontend map component.
They are intentionally separate from the agent schemas in
app/core/agents/tools/transit/schemas.py, which are optimized
for LLM consumption.
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict

VehicleStopStatus = Literal["IN_TRANSIT_TO", "STOPPED_AT", "INCOMING_AT"]


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
    current_status: VehicleStopStatus
    next_stop_name: str | None = None
    current_stop_name: str | None = None
    timestamp: str
    feed_id: str = ""
    operator_name: str = ""


class VehiclePositionsResponse(BaseModel):
    """Response wrapper for vehicle positions endpoint.

    Attributes:
        count: Number of vehicles in response.
        vehicles: List of vehicle positions.
        fetched_at: ISO 8601 server time when data was assembled.
        feed_id: Feed filter applied, if any.
    """

    model_config = ConfigDict(strict=True)

    count: int
    vehicles: list[VehiclePosition]
    fetched_at: str
    feed_id: str | None = None


class TransitFeedStatus(BaseModel):
    """Status of a single configured transit feed.

    Attributes:
        feed_id: Unique identifier for the feed (e.g., "riga").
        operator_name: Human-readable operator name.
        enabled: Whether the feed is actively polled.
        poll_interval_seconds: Polling frequency in seconds.
    """

    model_config = ConfigDict(strict=True)

    feed_id: str
    operator_name: str
    enabled: bool
    poll_interval_seconds: int


class TransitFeedsResponse(BaseModel):
    """Response for transit feeds status endpoint.

    Attributes:
        feeds: List of configured transit feed statuses.
    """

    model_config = ConfigDict(strict=True)

    feeds: list[TransitFeedStatus]


class HistoricalPosition(BaseModel):
    """A single historical position data point."""

    model_config = ConfigDict(strict=True)

    recorded_at: str
    vehicle_id: str
    route_id: str
    route_short_name: str
    latitude: float
    longitude: float
    bearing: float | None = None
    speed_kmh: float | None = None
    delay_seconds: int = 0
    current_status: VehicleStopStatus
    feed_id: str = ""


class VehicleHistoryResponse(BaseModel):
    """Response for vehicle position history query."""

    model_config = ConfigDict(strict=True)

    vehicle_id: str
    count: int
    positions: list[HistoricalPosition]
    from_time: str
    to_time: str


class RouteDelayTrendPoint(BaseModel):
    """A single data point in a delay trend time series."""

    model_config = ConfigDict(strict=True)

    time_bucket: str
    avg_delay_seconds: float
    min_delay_seconds: float
    max_delay_seconds: float
    sample_count: int


class RouteDelayTrendResponse(BaseModel):
    """Response for route delay trend query."""

    model_config = ConfigDict(strict=True)

    route_id: str
    route_short_name: str
    interval_minutes: int
    count: int
    data_points: list[RouteDelayTrendPoint]
    from_time: str
    to_time: str
