"""Pydantic schemas for stop management feature."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class StopBase(BaseModel):
    """Shared stop attributes for create and response schemas."""

    stop_name: str = Field(
        ..., min_length=1, max_length=200, description="Human-readable stop name"
    )
    gtfs_stop_id: str = Field(
        ..., min_length=1, max_length=50, description="GTFS stop_id identifier"
    )
    stop_lat: float | None = Field(None, ge=-90, le=90, description="WGS84 latitude")
    stop_lon: float | None = Field(None, ge=-180, le=180, description="WGS84 longitude")
    stop_desc: str | None = Field(None, max_length=500, description="Stop description")
    location_type: int = Field(
        default=0, ge=0, le=4, description="GTFS location_type (0=stop, 1=station)"
    )
    parent_station_id: int | None = Field(None, description="FK reference to parent station")
    wheelchair_boarding: int = Field(default=0, ge=0, le=2, description="GTFS wheelchair_boarding")


class StopCreate(StopBase):
    """Schema for creating a stop."""


class StopUpdate(BaseModel):
    """Schema for updating a stop. All fields optional."""

    stop_name: str | None = Field(None, min_length=1, max_length=200)
    gtfs_stop_id: str | None = Field(None, min_length=1, max_length=50)
    stop_lat: float | None = Field(None, ge=-90, le=90)
    stop_lon: float | None = Field(None, ge=-180, le=180)
    stop_desc: str | None = Field(None, max_length=500)
    location_type: int | None = Field(None, ge=0, le=4)
    parent_station_id: int | None = None
    wheelchair_boarding: int | None = Field(None, ge=0, le=2)
    is_active: bool | None = None


class StopResponse(StopBase):
    """Schema for stop responses."""

    id: int
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class StopNearbyParams(BaseModel):
    """Query parameters for proximity search."""

    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)
    radius_meters: int = Field(default=500, ge=1, le=5000, description="Search radius in meters")
