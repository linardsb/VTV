export interface FleetTypeSummary {
  vehicle_type: "bus" | "trolleybus" | "tram";
  total: number;
  active: number;
  inactive: number;
  in_maintenance: number;
}

export interface FleetSummaryResponse {
  total_vehicles: number;
  active_vehicles: number;
  inactive_vehicles: number;
  in_maintenance: number;
  by_type: FleetTypeSummary[];
  maintenance_due_7d: number;
  registration_expiring_30d: number;
  unassigned_vehicles: number;
  average_mileage_km: number;
  generated_at: string;
}

export interface ShiftCoverageSummary {
  shift: "morning" | "afternoon" | "evening" | "night";
  total: number;
  available: number;
  on_duty: number;
  on_leave: number;
  sick: number;
}

export interface DriverSummaryResponse {
  total_drivers: number;
  available_drivers: number;
  on_duty_drivers: number;
  on_leave_drivers: number;
  sick_drivers: number;
  by_shift: ShiftCoverageSummary[];
  license_expiring_30d: number;
  medical_expiring_30d: number;
  generated_at: string;
}

export interface RoutePerformanceSummary {
  route_id: string;
  route_short_name: string;
  scheduled_trips: number;
  tracked_trips: number;
  on_time_count: number;
  late_count: number;
  early_count: number;
  on_time_percentage: number;
  average_delay_seconds: number;
}

export interface OnTimePerformanceResponse {
  service_date: string;
  service_type: string;
  time_from: string | null;
  time_until: string | null;
  total_routes: number;
  network_on_time_percentage: number;
  network_average_delay_seconds: number;
  routes: RoutePerformanceSummary[];
  generated_at: string;
}

export interface AnalyticsOverviewResponse {
  fleet: FleetSummaryResponse;
  drivers: DriverSummaryResponse;
  on_time: OnTimePerformanceResponse;
}
