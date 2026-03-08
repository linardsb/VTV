# pyright: reportUnknownVariableType=false
"""Pydantic schemas for fleet device management and Traccar telemetry."""

import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

DeviceStatusType = Literal["active", "inactive", "offline"]
DeviceProtocolType = Literal["teltonika", "queclink", "general", "osmand", "other"]
TelemetrySourceType = Literal["hardware", "gtfs-rt"]


class TrackedDeviceBase(BaseModel):
    """Shared fields for tracked device schemas."""

    imei: str = Field(
        ...,
        min_length=15,
        max_length=15,
        pattern=r"^\d{15}$",
        description="15-digit IMEI number",
    )
    device_name: str | None = Field(None, max_length=100)
    sim_number: str | None = Field(None, max_length=20)
    protocol_type: DeviceProtocolType = Field(default="teltonika")
    firmware_version: str | None = Field(None, max_length=50)
    notes: str | None = Field(None, max_length=2000)


class TrackedDeviceCreate(TrackedDeviceBase):
    """Schema for creating a tracked device."""

    vehicle_id: int | None = Field(None, description="Link to existing vehicle")


class TrackedDeviceUpdate(BaseModel):
    """Schema for updating a tracked device. All fields optional."""

    imei: str | None = Field(
        None,
        min_length=15,
        max_length=15,
        pattern=r"^\d{15}$",
    )
    device_name: str | None = Field(None, max_length=100)
    sim_number: str | None = Field(None, max_length=20)
    protocol_type: DeviceProtocolType | None = Field(None)
    firmware_version: str | None = Field(None, max_length=50)
    notes: str | None = Field(None, max_length=2000)
    vehicle_id: int | None = Field(None)
    status: DeviceStatusType | None = Field(None)

    @model_validator(mode="before")
    @classmethod
    def reject_empty_body(cls, data: Any) -> Any:  # noqa: ANN401
        """Reject PATCH requests with no fields set."""
        if isinstance(data, dict) and not any(v is not None for v in data.values()):
            msg = "At least one field must be provided"
            raise ValueError(msg)
        return data


class TrackedDeviceResponse(TrackedDeviceBase):
    """Schema for tracked device responses."""

    id: int
    vehicle_id: int | None
    status: DeviceStatusType
    last_seen_at: datetime.datetime | None
    created_at: datetime.datetime
    updated_at: datetime.datetime

    model_config = ConfigDict(from_attributes=True)


class TraccarWebhookPayload(BaseModel):
    """Traccar event forwarding webhook payload."""

    id: int
    deviceId: int
    protocol: str
    deviceTime: str
    fixTime: str
    serverTime: str
    latitude: float
    longitude: float
    altitude: float | None = None
    speed: float | None = None
    course: float | None = None
    accuracy: float | None = None
    attributes: dict[str, Any] = Field(default_factory=dict)


class OBDTelemetry(BaseModel):
    """Parsed OBD-II diagnostic parameters from device telemetry."""

    speed_kmh: float | None = None
    rpm: int | None = None
    fuel_level_pct: float | None = None
    coolant_temp_c: float | None = None
    odometer_km: float | None = None
    engine_load_pct: float | None = None
    battery_voltage: float | None = None
