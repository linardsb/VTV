export interface Vehicle {
  id: number;
  fleet_number: string;
  vehicle_type: "bus" | "trolleybus" | "tram";
  license_plate: string;
  manufacturer: string | null;
  model_name: string | null;
  model_year: number | null;
  capacity: number | null;
  status: "active" | "inactive" | "maintenance";
  current_driver_id: number | null;
  mileage_km: number;
  qualified_route_ids: string | null;
  registration_expiry: string | null;
  next_maintenance_date: string | null;
  notes: string | null;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface VehicleCreate {
  fleet_number: string;
  vehicle_type: "bus" | "trolleybus" | "tram";
  license_plate: string;
  manufacturer?: string | null;
  model_name?: string | null;
  model_year?: number | null;
  capacity?: number | null;
  qualified_route_ids?: string | null;
  notes?: string | null;
}

export interface VehicleUpdate {
  fleet_number?: string;
  vehicle_type?: "bus" | "trolleybus" | "tram";
  license_plate?: string;
  manufacturer?: string | null;
  model_name?: string | null;
  model_year?: number | null;
  capacity?: number | null;
  status?: "active" | "inactive" | "maintenance";
  current_driver_id?: number | null;
  mileage_km?: number;
  qualified_route_ids?: string | null;
  registration_expiry?: string | null;
  next_maintenance_date?: string | null;
  notes?: string | null;
}

export interface MaintenanceRecord {
  id: number;
  vehicle_id: number;
  maintenance_type: "scheduled" | "unscheduled" | "inspection" | "repair";
  description: string;
  performed_date: string;
  mileage_at_service: number | null;
  cost_eur: number | null;
  next_scheduled_date: string | null;
  performed_by: string | null;
  notes: string | null;
  created_at: string;
  updated_at: string;
}

export interface MaintenanceRecordCreate {
  maintenance_type: "scheduled" | "unscheduled" | "inspection" | "repair";
  description: string;
  performed_date: string;
  mileage_at_service?: number | null;
  cost_eur?: number | null;
  next_scheduled_date?: string | null;
  performed_by?: string | null;
  notes?: string | null;
}

export interface PaginatedVehicles {
  items: Vehicle[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

export interface PaginatedMaintenanceRecords {
  items: MaintenanceRecord[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}
