"""Pydantic schemas for driver management feature."""

import datetime

from pydantic import BaseModel, ConfigDict, Field


class DriverBase(BaseModel):
    """Shared driver attributes for create and response schemas."""

    first_name: str = Field(..., min_length=1, max_length=100, description="Driver first name")
    last_name: str = Field(..., min_length=1, max_length=100, description="Driver last name")
    employee_number: str = Field(
        ..., min_length=1, max_length=20, description="Unique employee identifier"
    )
    date_of_birth: datetime.date | None = Field(None, description="Date of birth")
    phone: str | None = Field(None, max_length=30, description="Phone number")
    email: str | None = Field(None, max_length=200, description="Email address")
    address: str | None = Field(None, description="Home address")
    emergency_contact_name: str | None = Field(None, max_length=200)
    emergency_contact_phone: str | None = Field(None, max_length=30)
    photo_url: str | None = Field(None, max_length=500)
    hire_date: datetime.date | None = Field(None, description="Employment start date")
    license_categories: str | None = Field(
        None, max_length=50, description="Comma-separated license categories (e.g. D,D1,DE)"
    )
    license_expiry_date: datetime.date | None = Field(None, description="License expiry date")
    medical_cert_expiry: datetime.date | None = Field(
        None, description="Medical certificate expiry date"
    )
    qualified_route_ids: str | None = Field(
        None, description="Comma-separated GTFS route IDs the driver is qualified for"
    )
    default_shift: str = Field(
        default="morning", description="Default shift: morning/afternoon/evening/night"
    )
    status: str = Field(default="available", description="Status: available/on_duty/on_leave/sick")
    notes: str | None = Field(None, description="Free-text notes")
    training_records: str | None = Field(None, description="Training records")


class DriverCreate(DriverBase):
    """Schema for creating a driver."""


class DriverUpdate(BaseModel):
    """Schema for updating a driver. All fields optional."""

    first_name: str | None = Field(None, min_length=1, max_length=100)
    last_name: str | None = Field(None, min_length=1, max_length=100)
    employee_number: str | None = Field(None, min_length=1, max_length=20)
    date_of_birth: datetime.date | None = None
    phone: str | None = Field(None, max_length=30)
    email: str | None = Field(None, max_length=200)
    address: str | None = None
    emergency_contact_name: str | None = Field(None, max_length=200)
    emergency_contact_phone: str | None = Field(None, max_length=30)
    photo_url: str | None = Field(None, max_length=500)
    hire_date: datetime.date | None = None
    license_categories: str | None = Field(None, max_length=50)
    license_expiry_date: datetime.date | None = None
    medical_cert_expiry: datetime.date | None = None
    qualified_route_ids: str | None = None
    default_shift: str | None = Field(None)
    status: str | None = Field(None)
    notes: str | None = None
    training_records: str | None = None
    is_active: bool | None = None


class DriverResponse(DriverBase):
    """Schema for driver responses."""

    id: int
    is_active: bool
    created_at: datetime.datetime
    updated_at: datetime.datetime

    model_config = ConfigDict(from_attributes=True)
