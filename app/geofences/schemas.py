# pyright: reportUnknownVariableType=false
"""Pydantic schemas for geofence zone management and event tracking."""

import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

ZoneType = Literal["depot", "terminal", "restricted", "customer", "custom"]
AlertSeverityType = Literal["critical", "high", "medium", "low", "info"]
GeofenceEventType = Literal["enter", "exit", "dwell_exceeded"]


class GeofenceBase(BaseModel):
    """Shared fields for geofence schemas."""

    name: str = Field(..., min_length=1, max_length=200)
    zone_type: ZoneType
    color: str | None = Field(None, max_length=7, pattern=r"^#[0-9A-Fa-f]{6}$")
    alert_on_enter: bool = Field(default=True)
    alert_on_exit: bool = Field(default=True)
    alert_on_dwell: bool = Field(default=False)
    dwell_threshold_minutes: int | None = Field(None, ge=1, le=1440)
    alert_severity: AlertSeverityType = Field(default="medium")
    description: str | None = Field(None, max_length=1000)


class GeofenceCreate(GeofenceBase):
    """Schema for creating a geofence with polygon coordinates."""

    coordinates: list[list[float]] = Field(
        ..., description="GeoJSON polygon coordinates: list of [lon, lat] pairs, first==last"
    )

    @field_validator("coordinates")
    @classmethod
    def validate_coordinates(cls, v: list[list[float]]) -> list[list[float]]:
        """Validate polygon coordinates form a closed ring with valid lat/lon."""
        if len(v) < 4:
            msg = "Polygon must have at least 4 points (3 vertices + closing point)"
            raise ValueError(msg)
        if v[0] != v[-1]:
            msg = "Polygon must be closed (first point must equal last point)"
            raise ValueError(msg)
        for point in v:
            if len(point) != 2:
                msg = "Each coordinate must be [longitude, latitude]"
                raise ValueError(msg)
            lon, lat = point
            if not (-180 <= lon <= 180):
                msg = f"Longitude {lon} out of range [-180, 180]"
                raise ValueError(msg)
            if not (-90 <= lat <= 90):
                msg = f"Latitude {lat} out of range [-90, 90]"
                raise ValueError(msg)
        return v


class GeofenceUpdate(BaseModel):
    """Schema for updating a geofence. All fields optional."""

    name: str | None = Field(None, min_length=1, max_length=200)
    zone_type: ZoneType | None = None
    color: str | None = Field(None, max_length=7, pattern=r"^#[0-9A-Fa-f]{6}$")
    alert_on_enter: bool | None = None
    alert_on_exit: bool | None = None
    alert_on_dwell: bool | None = None
    dwell_threshold_minutes: int | None = Field(None, ge=1, le=1440)
    alert_severity: AlertSeverityType | None = None
    description: str | None = Field(None, max_length=1000)
    coordinates: list[list[float]] | None = None
    is_active: bool | None = None

    @model_validator(mode="before")
    @classmethod
    def reject_empty_body(cls, data: Any) -> Any:  # noqa: ANN401
        """Reject PATCH requests with no fields set."""
        if isinstance(data, dict) and not any(v is not None for v in data.values()):
            msg = "At least one field must be provided"
            raise ValueError(msg)
        return data

    @field_validator("coordinates")
    @classmethod
    def validate_coordinates(cls, v: list[list[float]] | None) -> list[list[float]] | None:
        """Validate polygon coordinates if provided."""
        if v is None:
            return v
        if len(v) < 4:
            msg = "Polygon must have at least 4 points (3 vertices + closing point)"
            raise ValueError(msg)
        if v[0] != v[-1]:
            msg = "Polygon must be closed (first point must equal last point)"
            raise ValueError(msg)
        for point in v:
            if len(point) != 2:
                msg = "Each coordinate must be [longitude, latitude]"
                raise ValueError(msg)
            lon, lat = point
            if not (-180 <= lon <= 180):
                msg = f"Longitude {lon} out of range [-180, 180]"
                raise ValueError(msg)
            if not (-90 <= lat <= 90):
                msg = f"Latitude {lat} out of range [-90, 90]"
                raise ValueError(msg)
        return v


class GeofenceResponse(GeofenceBase):
    """Schema for geofence responses with coordinates and metadata."""

    id: int
    coordinates: list[list[float]]
    is_active: bool
    created_at: datetime.datetime
    updated_at: datetime.datetime

    model_config = ConfigDict(from_attributes=True)


class GeofenceEventResponse(BaseModel):
    """Schema for geofence event responses."""

    id: int
    geofence_id: int
    geofence_name: str
    vehicle_id: str
    event_type: GeofenceEventType
    entered_at: datetime.datetime
    exited_at: datetime.datetime | None
    dwell_seconds: int | None
    latitude: float
    longitude: float
    created_at: datetime.datetime

    model_config = ConfigDict(from_attributes=True)


class DwellTimeReport(BaseModel):
    """Aggregated dwell time statistics for a geofence."""

    geofence_id: int
    geofence_name: str
    total_events: int
    avg_dwell_seconds: float
    max_dwell_seconds: int
    vehicles_inside: int
