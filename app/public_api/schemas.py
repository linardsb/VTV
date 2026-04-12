"""Pydantic schemas for public developer API."""

import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.shared.schemas import PaginatedResponse

APIKeyTierType = Literal["free", "basic", "pro"]


class APIKeyCreate(BaseModel):
    """Request schema for creating a new API key."""

    name: str = Field(..., max_length=100, description="Human-readable key name")


class APIKeyCreateResponse(BaseModel):
    """Response schema for key creation — raw key shown once."""

    id: int
    name: str
    key: str = Field(..., description="Raw API key (shown once, store securely)")
    key_preview: str
    tier: APIKeyTierType
    created_at: datetime.datetime

    model_config = ConfigDict(from_attributes=True)


class APIKeyResponse(BaseModel):
    """Response schema for API key metadata (no raw key)."""

    id: int
    name: str
    key_preview: str
    tier: APIKeyTierType
    is_active: bool
    last_used_at: datetime.datetime | None
    revoked_at: datetime.datetime | None
    expires_at: datetime.datetime | None
    created_at: datetime.datetime

    model_config = ConfigDict(from_attributes=True)


class APIKeyListResponse(PaginatedResponse[APIKeyResponse]):
    """Paginated list of API keys."""


class PublicRouteResponse(BaseModel):
    """Public transit route data."""

    route_id: str
    short_name: str
    long_name: str
    type: int
    agency_name: str


class PublicStopResponse(BaseModel):
    """Public transit stop data."""

    stop_id: str
    name: str
    lat: float | None
    lon: float | None


class PublicVehicleResponse(BaseModel):
    """Public real-time vehicle position."""

    vehicle_id: str
    route_id: str | None
    latitude: float
    longitude: float
    bearing: float | None
    speed: float | None
    timestamp: datetime.datetime | None
    feed_id: str
