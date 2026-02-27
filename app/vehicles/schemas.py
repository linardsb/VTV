# pyright: reportUnknownVariableType=false
"""Pydantic schemas for vehicle management feature."""

import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

VehicleType = Literal["bus", "trolleybus", "tram"]
VehicleStatus = Literal["active", "inactive", "maintenance"]
MaintenanceType = Literal["scheduled", "unscheduled", "inspection", "repair"]


class VehicleBase(BaseModel):
    """Shared vehicle attributes for create and response schemas."""

    fleet_number: str = Field(
        ...,
        min_length=1,
        max_length=20,
        description="Unique fleet identifier matching GTFS-RT vehicle_id",
    )
    vehicle_type: VehicleType = Field(..., description="Vehicle type: bus, trolleybus, or tram")
    license_plate: str = Field(
        ..., min_length=1, max_length=20, description="Vehicle license plate"
    )
    manufacturer: str | None = Field(None, max_length=100, description="Vehicle manufacturer")
    model_name: str | None = Field(None, max_length=100, description="Vehicle model name")
    model_year: int | None = Field(None, ge=1950, le=2100, description="Year of manufacture")
    capacity: int | None = Field(None, ge=1, le=500, description="Passenger capacity")
    qualified_route_ids: str | None = Field(
        None,
        max_length=500,
        description="Comma-separated GTFS route IDs this vehicle is qualified for",
    )
    notes: str | None = Field(None, max_length=2000, description="Free-text notes")


class VehicleCreate(VehicleBase):
    """Schema for creating a vehicle."""


class VehicleUpdate(BaseModel):
    """Schema for updating a vehicle. All fields optional."""

    fleet_number: str | None = Field(None, min_length=1, max_length=20)
    vehicle_type: VehicleType | None = Field(None)
    license_plate: str | None = Field(None, min_length=1, max_length=20)
    manufacturer: str | None = Field(None, max_length=100)
    model_name: str | None = Field(None, max_length=100)
    model_year: int | None = Field(None, ge=1950, le=2100)
    capacity: int | None = Field(None, ge=1, le=500)
    status: VehicleStatus | None = Field(None)
    current_driver_id: int | None = Field(None, ge=1)
    mileage_km: int | None = Field(None, ge=0)
    qualified_route_ids: str | None = Field(None, max_length=500)
    registration_expiry: datetime.date | None = Field(None)
    next_maintenance_date: datetime.date | None = Field(None)
    notes: str | None = Field(None, max_length=2000)

    @model_validator(mode="before")
    @classmethod
    def reject_empty_body(cls, data: Any) -> Any:  # noqa: ANN401
        """Reject PATCH requests with no fields set."""
        if isinstance(data, dict) and not any(v is not None for v in data.values()):
            msg = "At least one field must be provided"
            raise ValueError(msg)
        return data


class VehicleResponse(VehicleBase):
    """Schema for vehicle responses."""

    id: int
    status: VehicleStatus
    current_driver_id: int | None
    mileage_km: int
    registration_expiry: datetime.date | None
    next_maintenance_date: datetime.date | None
    is_active: bool
    created_at: datetime.datetime
    updated_at: datetime.datetime

    model_config = ConfigDict(from_attributes=True)


class MaintenanceRecordBase(BaseModel):
    """Shared maintenance record attributes for create and response schemas."""

    maintenance_type: MaintenanceType = Field(..., description="Type of maintenance")
    description: str = Field(
        ..., min_length=1, max_length=2000, description="Description of work performed"
    )
    performed_date: datetime.date = Field(..., description="Date maintenance was performed")
    mileage_at_service: int | None = Field(
        None, ge=0, description="Vehicle mileage at time of service"
    )
    cost_eur: float | None = Field(None, ge=0, description="Cost in EUR")
    next_scheduled_date: datetime.date | None = Field(
        None, description="Next scheduled maintenance date"
    )
    performed_by: str | None = Field(
        None, max_length=200, description="Technician or workshop name"
    )
    notes: str | None = Field(None, max_length=2000, description="Additional notes")


class MaintenanceRecordCreate(MaintenanceRecordBase):
    """Schema for creating a maintenance record."""


class MaintenanceRecordResponse(MaintenanceRecordBase):
    """Schema for maintenance record responses."""

    id: int
    vehicle_id: int
    created_at: datetime.datetime
    updated_at: datetime.datetime

    model_config = ConfigDict(from_attributes=True)
