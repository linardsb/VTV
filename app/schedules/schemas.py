"""Pydantic schemas for schedule management feature."""

import datetime

from pydantic import BaseModel, ConfigDict, Field

# --- Agency ---


class AgencyCreate(BaseModel):
    """Schema for creating an agency."""

    gtfs_agency_id: str = Field(..., min_length=1, max_length=50, description="GTFS agency_id")
    agency_name: str = Field(..., min_length=1, max_length=200, description="Agency name")
    agency_url: str | None = Field(None, max_length=500, description="Agency URL")
    agency_timezone: str = Field(default="Europe/Riga", max_length=50, description="IANA timezone")
    agency_lang: str | None = Field(None, max_length=5, description="ISO 639-1 language code")


class AgencyResponse(BaseModel):
    """Schema for agency responses."""

    id: int
    gtfs_agency_id: str
    agency_name: str
    agency_url: str | None
    agency_timezone: str
    agency_lang: str | None
    created_at: datetime.datetime
    updated_at: datetime.datetime

    model_config = ConfigDict(from_attributes=True)


# --- Route ---


class RouteCreate(BaseModel):
    """Schema for creating a route."""

    gtfs_route_id: str = Field(..., min_length=1, max_length=50, description="GTFS route_id")
    agency_id: int = Field(..., description="FK to agencies.id")
    route_short_name: str = Field(..., min_length=1, max_length=50, description="Short name")
    route_long_name: str = Field(..., min_length=1, max_length=200, description="Long name")
    route_type: int = Field(..., ge=0, le=12, description="GTFS route_type")
    route_color: str | None = Field(None, max_length=6, description="Hex color without #")
    route_text_color: str | None = Field(None, max_length=6, description="Text hex color")
    route_sort_order: int | None = Field(None, description="Sort order")


class RouteUpdate(BaseModel):
    """Schema for updating a route. All fields optional."""

    gtfs_route_id: str | None = Field(None, min_length=1, max_length=50)
    agency_id: int | None = None
    route_short_name: str | None = Field(None, min_length=1, max_length=50)
    route_long_name: str | None = Field(None, min_length=1, max_length=200)
    route_type: int | None = Field(None, ge=0, le=12)
    route_color: str | None = Field(None, max_length=6)
    route_text_color: str | None = Field(None, max_length=6)
    route_sort_order: int | None = None
    is_active: bool | None = None


class RouteResponse(BaseModel):
    """Schema for route responses."""

    id: int
    gtfs_route_id: str
    agency_id: int
    route_short_name: str
    route_long_name: str
    route_type: int
    route_color: str | None
    route_text_color: str | None
    route_sort_order: int | None
    is_active: bool
    created_at: datetime.datetime
    updated_at: datetime.datetime

    model_config = ConfigDict(from_attributes=True)


# --- Calendar ---


class CalendarCreate(BaseModel):
    """Schema for creating a service calendar."""

    gtfs_service_id: str = Field(..., min_length=1, max_length=50, description="GTFS service_id")
    monday: bool = Field(..., description="Service on Monday")
    tuesday: bool = Field(..., description="Service on Tuesday")
    wednesday: bool = Field(..., description="Service on Wednesday")
    thursday: bool = Field(..., description="Service on Thursday")
    friday: bool = Field(..., description="Service on Friday")
    saturday: bool = Field(..., description="Service on Saturday")
    sunday: bool = Field(..., description="Service on Sunday")
    start_date: datetime.date = Field(..., description="Service start date")
    end_date: datetime.date = Field(..., description="Service end date")


class CalendarUpdate(BaseModel):
    """Schema for updating a calendar. All fields optional."""

    gtfs_service_id: str | None = Field(None, min_length=1, max_length=50)
    monday: bool | None = None
    tuesday: bool | None = None
    wednesday: bool | None = None
    thursday: bool | None = None
    friday: bool | None = None
    saturday: bool | None = None
    sunday: bool | None = None
    start_date: datetime.date | None = None
    end_date: datetime.date | None = None


class CalendarDateCreate(BaseModel):
    """Schema for creating a calendar date exception."""

    date: datetime.date = Field(..., description="Exception date")
    exception_type: int = Field(..., ge=1, le=2, description="1=added, 2=removed")


class CalendarDateResponse(BaseModel):
    """Schema for calendar date exception responses."""

    id: int
    calendar_id: int
    date: datetime.date
    exception_type: int
    created_at: datetime.datetime
    updated_at: datetime.datetime

    model_config = ConfigDict(from_attributes=True)


class CalendarResponse(BaseModel):
    """Schema for calendar responses."""

    id: int
    gtfs_service_id: str
    monday: bool
    tuesday: bool
    wednesday: bool
    thursday: bool
    friday: bool
    saturday: bool
    sunday: bool
    start_date: datetime.date
    end_date: datetime.date
    created_at: datetime.datetime
    updated_at: datetime.datetime

    model_config = ConfigDict(from_attributes=True)


# --- Trip ---


class TripCreate(BaseModel):
    """Schema for creating a trip."""

    gtfs_trip_id: str = Field(..., min_length=1, max_length=100, description="GTFS trip_id")
    route_id: int = Field(..., description="FK to routes.id")
    calendar_id: int = Field(..., description="FK to calendars.id")
    direction_id: int | None = Field(None, ge=0, le=1, description="0=outbound, 1=inbound")
    trip_headsign: str | None = Field(None, max_length=200, description="Trip headsign")
    block_id: str | None = Field(None, max_length=50, description="Block ID")


class TripUpdate(BaseModel):
    """Schema for updating a trip. All fields optional."""

    route_id: int | None = None
    calendar_id: int | None = None
    direction_id: int | None = Field(None, ge=0, le=1)
    trip_headsign: str | None = Field(None, max_length=200)
    block_id: str | None = Field(None, max_length=50)


class TripResponse(BaseModel):
    """Schema for trip responses."""

    id: int
    gtfs_trip_id: str
    route_id: int
    calendar_id: int
    direction_id: int | None
    trip_headsign: str | None
    block_id: str | None
    created_at: datetime.datetime
    updated_at: datetime.datetime

    model_config = ConfigDict(from_attributes=True)


# --- StopTime ---


class StopTimeCreate(BaseModel):
    """Schema for creating a stop time."""

    stop_id: int = Field(..., description="FK to stops.id")
    stop_sequence: int = Field(..., ge=1, description="Order in trip")
    arrival_time: str = Field(
        ..., pattern=r"^\d{2}:\d{2}:\d{2}$", description="HH:MM:SS (can exceed 24:00:00)"
    )
    departure_time: str = Field(
        ..., pattern=r"^\d{2}:\d{2}:\d{2}$", description="HH:MM:SS (can exceed 24:00:00)"
    )
    pickup_type: int = Field(default=0, ge=0, le=3, description="GTFS pickup_type")
    drop_off_type: int = Field(default=0, ge=0, le=3, description="GTFS drop_off_type")


class StopTimeResponse(BaseModel):
    """Schema for stop time responses."""

    id: int
    trip_id: int
    stop_id: int
    stop_sequence: int
    arrival_time: str
    departure_time: str
    pickup_type: int
    drop_off_type: int
    created_at: datetime.datetime
    updated_at: datetime.datetime

    model_config = ConfigDict(from_attributes=True)


class TripDetailResponse(TripResponse):
    """Trip response with stop times included."""

    stop_times: list[StopTimeResponse] = Field(default_factory=lambda: list[StopTimeResponse]())


class StopTimesBulkUpdate(BaseModel):
    """Schema for replacing all stop times on a trip."""

    stop_times: list[StopTimeCreate]


# --- Import ---


class GTFSImportResponse(BaseModel):
    """Response schema for GTFS import operation."""

    agencies_count: int
    routes_count: int
    calendars_count: int
    calendar_dates_count: int
    trips_count: int
    stop_times_count: int
    skipped_stop_times: int
    warnings: list[str]


# --- Validation ---


class ValidationResult(BaseModel):
    """Result of schedule data validation."""

    valid: bool
    errors: list[str]
    warnings: list[str]
