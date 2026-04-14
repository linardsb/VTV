"""Pydantic response schemas for the transit REST API.

These models are optimized for the CMS frontend map component.
They are intentionally separate from the agent schemas in
app/core/agents/tools/transit/schemas.py, which are optimized
for LLM consumption.
"""

import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

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


# ── Phone Assignment schemas (LV-3.1) ───────────────────────────────


class PhoneAssignmentCreate(BaseModel):
    """Request body for creating a phone-to-vehicle assignment."""

    phone_identifier: str = Field(..., max_length=100, pattern=r"^[\w\-.:]+$")
    vehicle_id: int
    route_id: int | None = None
    driver_id: int | None = None


class PhoneAssignmentResponse(BaseModel):
    """Response for a phone-to-vehicle assignment."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    phone_identifier: str
    vehicle_id: int
    route_id: int | None
    driver_id: int | None
    assigned_by: str
    active: bool
    created_at: datetime.datetime
    updated_at: datetime.datetime


# ---------------------------------------------------------------------------
# LV-3.3 OTP journey planner
# ---------------------------------------------------------------------------

TransportMode = Literal[
    "WALK", "BUS", "TRAM", "RAIL", "SUBWAY", "FERRY", "TROLLEYBUS", "BICYCLE", "CAR"
]


class JourneyLeg(BaseModel):
    """Single leg of a multi-modal itinerary (LV-3.3)."""

    model_config = ConfigDict(strict=True)

    mode: TransportMode
    from_name: str
    from_lat: float
    from_lon: float
    to_name: str
    to_lat: float
    to_lon: float
    start_time: datetime.datetime
    end_time: datetime.datetime
    duration_seconds: int
    distance_m: float
    route_id: str | None = None
    route_short_name: str | None = None
    route_long_name: str | None = None
    trip_id: str | None = None
    agency_name: str | None = None
    num_stops: int | None = None
    realtime_delay_seconds: int | None = None
    scheduled_start_time: datetime.datetime | None = None
    polyline: str | None = None


class JourneyItinerary(BaseModel):
    """Full itinerary composed of one or more legs (LV-3.3)."""

    model_config = ConfigDict(strict=True)

    start_time: datetime.datetime
    end_time: datetime.datetime
    duration_seconds: int
    walk_distance_m: float
    transit_time_seconds: int
    waiting_time_seconds: int
    transfers: int
    legs: list[JourneyLeg]


class JourneyPlanResponse(BaseModel):
    """Envelope returned by ``GET /api/v1/transit/plan`` (LV-3.3)."""

    from_name: str
    from_lat: float
    from_lon: float
    to_name: str
    to_lat: float
    to_lon: float
    itineraries: list[JourneyItinerary]
    requested_at: datetime.datetime
    otp_enriched: bool = False


# ---------------------------------------------------------------------------
# LV-3.4 Share links
# ---------------------------------------------------------------------------


class ShareLinkCreate(BaseModel):
    """Request body for creating a trip-share link (LV-3.4)."""

    vehicle_id: str = Field(..., max_length=100)
    route_id: str | None = Field(None, max_length=50)
    feed_id: str = Field("riga", max_length=50)
    expiry_hours: int = Field(1, ge=1, le=24)


class ShareLinkResponse(BaseModel):
    """Response after creating a share link (LV-3.4)."""

    id: int
    vehicle_id: str
    route_id: str | None
    feed_id: str
    token: str
    share_url: str
    qr_code_base64: str
    expires_at: datetime.datetime


class ShareResolveResponse(BaseModel):
    """Public resolver payload for a share link (LV-3.4)."""

    vehicle_id: str
    route_id: str | None
    feed_id: str
    expires_at: datetime.datetime
    position: VehiclePosition | None = None
