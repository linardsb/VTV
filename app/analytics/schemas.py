"""Pydantic response schemas for analytics endpoints.

These models are optimized for the CMS frontend dashboard.
They provide pre-computed summaries from existing data sources
(vehicles, drivers, transit, schedules).
"""

import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict

VehicleType = Literal["bus", "trolleybus", "tram"]
VehicleStatus = Literal["active", "inactive", "maintenance"]
DriverStatus = Literal["available", "on_duty", "on_leave", "sick"]
DriverShift = Literal["morning", "afternoon", "evening", "night"]
ServiceType = Literal["weekday", "saturday", "sunday", "unknown"]


class FleetTypeSummary(BaseModel):
    """Vehicle count breakdown for a single vehicle type."""

    model_config = ConfigDict(from_attributes=True)

    vehicle_type: VehicleType
    total: int
    active: int
    inactive: int
    in_maintenance: int


class FleetSummaryResponse(BaseModel):
    """Fleet overview with status breakdown and operational alerts."""

    model_config = ConfigDict(from_attributes=True)

    total_vehicles: int
    active_vehicles: int
    inactive_vehicles: int
    in_maintenance: int
    by_type: list[FleetTypeSummary]
    maintenance_due_7d: int
    registration_expiring_30d: int
    unassigned_vehicles: int
    average_mileage_km: float
    generated_at: datetime.datetime


class ShiftCoverageSummary(BaseModel):
    """Driver count breakdown for a single shift."""

    model_config = ConfigDict(from_attributes=True)

    shift: DriverShift
    total: int
    available: int
    on_duty: int
    on_leave: int
    sick: int


class DriverSummaryResponse(BaseModel):
    """Driver coverage overview with shift breakdown and expiry alerts."""

    model_config = ConfigDict(from_attributes=True)

    total_drivers: int
    available_drivers: int
    on_duty_drivers: int
    on_leave_drivers: int
    sick_drivers: int
    by_shift: list[ShiftCoverageSummary]
    license_expiring_30d: int
    medical_expiring_30d: int
    generated_at: datetime.datetime


class RoutePerformanceSummary(BaseModel):
    """On-time performance metrics for a single route."""

    model_config = ConfigDict(from_attributes=True)

    route_id: str
    route_short_name: str
    scheduled_trips: int
    tracked_trips: int
    on_time_count: int
    late_count: int
    early_count: int
    on_time_percentage: float
    average_delay_seconds: float


class OnTimePerformanceResponse(BaseModel):
    """Network-wide on-time adherence metrics from GTFS-RT data."""

    model_config = ConfigDict(from_attributes=True)

    service_date: str
    service_type: ServiceType
    time_from: str | None = None
    time_until: str | None = None
    total_routes: int
    network_on_time_percentage: float
    network_average_delay_seconds: float
    routes: list[RoutePerformanceSummary]
    generated_at: datetime.datetime


class AnalyticsOverviewResponse(BaseModel):
    """Combined dashboard summary with fleet, driver, and on-time data."""

    model_config = ConfigDict(from_attributes=True)

    fleet: FleetSummaryResponse
    drivers: DriverSummaryResponse
    on_time: OnTimePerformanceResponse
