export type DeviceProtocolType =
  | "teltonika"
  | "queclink"
  | "general"
  | "osmand"
  | "other";
export type DeviceStatus = "active" | "inactive" | "offline";

export interface TrackedDevice {
  id: number;
  imei: string;
  device_name: string | null;
  sim_number: string | null;
  protocol_type: DeviceProtocolType;
  firmware_version: string | null;
  notes: string | null;
  vehicle_id: number | null;
  status: DeviceStatus;
  last_seen_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface TrackedDeviceCreate {
  imei: string;
  device_name?: string | null;
  sim_number?: string | null;
  protocol_type?: DeviceProtocolType;
  firmware_version?: string | null;
  notes?: string | null;
  vehicle_id?: number | null;
}

export interface TrackedDeviceUpdate {
  imei?: string;
  device_name?: string | null;
  sim_number?: string | null;
  protocol_type?: DeviceProtocolType;
  firmware_version?: string | null;
  notes?: string | null;
  vehicle_id?: number | null;
  status?: DeviceStatus;
}

export interface PaginatedDevices {
  items: TrackedDevice[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

export interface OBDTelemetry {
  speed_kmh: number | null;
  rpm: number | null;
  fuel_level_pct: number | null;
  coolant_temp_c: number | null;
  odometer_km: number | null;
  engine_load_pct: number | null;
  battery_voltage: number | null;
}

export interface VehiclePositionWithTelemetry {
  vehicle_id: string;
  latitude: number;
  longitude: number;
  speed_kmh: number | null;
  bearing: number | null;
  recorded_at: string;
  source: "hardware" | "gtfs-rt";
  obd_data: OBDTelemetry | null;
}

export interface TelemetryHistoryPoint {
  recorded_at: string;
  latitude: number;
  longitude: number;
  speed_kmh: number | null;
  obd_data: OBDTelemetry | null;
}
