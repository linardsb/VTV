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


class PerRouteAdherence(BaseModel):
    """Per-route adherence breakdown for a daily report."""

    model_config = ConfigDict(from_attributes=True)

    route_id: str
    route_short_name: str
    total_trips: int
    on_time_trips: int
    late_trips: int
    early_trips: int
    on_time_pct: float
    avg_delay_seconds: float


class PerHourAdherence(BaseModel):
    """Per-hour adherence breakdown for a daily report."""

    model_config = ConfigDict(from_attributes=True)

    hour: int  # 0-23
    total_trips: int
    on_time_trips: int
    on_time_pct: float


class DailyAdherenceReportResponse(BaseModel):
    """Response schema for daily schedule adherence reports (ML-5.2)."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    report_date: datetime.date
    overall_pct: float
    total_trips: int
    on_time_trips: int
    late_trips: int
    early_trips: int
    per_route: list[PerRouteAdherence]
    per_hour: list[PerHourAdherence]
    anomaly_count: int
    alert_triggered: bool
    created_at: datetime.datetime


class AnalyticsOverviewResponse(BaseModel):
    """Combined dashboard summary with fleet, driver, and on-time data."""

    model_config = ConfigDict(from_attributes=True)

    fleet: FleetSummaryResponse
    drivers: DriverSummaryResponse
    on_time: OnTimePerformanceResponse


# --- Route Performance Drill-Down Schemas (ML-5.1) ---

WindowLiteral = Literal["7", "14", "30"]


class DailyOnTimePoint(BaseModel):
    """Single day's on-time performance for a route."""

    model_config = ConfigDict(from_attributes=True)

    date: str
    on_time_percentage: float
    tracked_trips: int


class StopDelayPoint(BaseModel):
    """Average delay at a single stop."""

    model_config = ConfigDict(from_attributes=True)

    stop_id: str
    stop_name: str
    average_delay_seconds: float
    sample_count: int


class DailyLoadPoint(BaseModel):
    """Single day's load factor for a route."""

    model_config = ConfigDict(from_attributes=True)

    date: str
    load_factor: float  # 0.0-1.0
    estimated_passengers: int


class DailyAnomalyPoint(BaseModel):
    """Single day's anomaly counts by type for a route."""

    model_config = ConfigDict(from_attributes=True)

    date: str
    off_route: int
    stuck: int
    gps_gap: int


class RoutePerformanceTrendResponse(BaseModel):
    """Time-series on-time performance for a single route."""

    model_config = ConfigDict(from_attributes=True)

    route_id: str
    route_short_name: str
    window_days: int
    overall_on_time_percentage: float
    overall_average_delay_seconds: float
    data: list[DailyOnTimePoint]
    generated_at: str


class RouteDelayByStopResponse(BaseModel):
    """Average delay per stop for a route."""

    model_config = ConfigDict(from_attributes=True)

    route_id: str
    route_short_name: str
    window_days: int
    stops: list[StopDelayPoint]
    generated_at: str


class RouteLoadTrendResponse(BaseModel):
    """Daily load factor trend for a route."""

    model_config = ConfigDict(from_attributes=True)

    route_id: str
    route_short_name: str
    window_days: int
    data: list[DailyLoadPoint]
    generated_at: str


class RouteAnomalyResponse(BaseModel):
    """Daily anomaly counts by type for a route."""

    model_config = ConfigDict(from_attributes=True)

    route_id: str
    route_short_name: str
    window_days: int
    total_anomalies: int
    data: list[DailyAnomalyPoint]
    generated_at: str
