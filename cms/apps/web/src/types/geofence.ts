export type ZoneType =
  | "depot"
  | "terminal"
  | "restricted"
  | "customer"
  | "custom";
export type AlertSeverity = "critical" | "high" | "medium" | "low" | "info";
export type GeofenceEventType = "enter" | "exit" | "dwell_exceeded";

export interface Geofence {
  id: number;
  name: string;
  zone_type: ZoneType;
  coordinates: number[][];
  color: string | null;
  alert_on_enter: boolean;
  alert_on_exit: boolean;
  alert_on_dwell: boolean;
  dwell_threshold_minutes: number | null;
  alert_severity: AlertSeverity;
  description: string | null;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface GeofenceCreate {
  name: string;
  zone_type: ZoneType;
  coordinates: number[][];
  color?: string | null;
  alert_on_enter?: boolean;
  alert_on_exit?: boolean;
  alert_on_dwell?: boolean;
  dwell_threshold_minutes?: number | null;
  alert_severity?: AlertSeverity;
  description?: string | null;
}

export interface GeofenceUpdate {
  name?: string;
  zone_type?: ZoneType;
  coordinates?: number[][];
  color?: string | null;
  alert_on_enter?: boolean;
  alert_on_exit?: boolean;
  alert_on_dwell?: boolean;
  dwell_threshold_minutes?: number | null;
  alert_severity?: AlertSeverity;
  description?: string | null;
  is_active?: boolean;
}

export interface PaginatedGeofences {
  items: Geofence[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

export interface GeofenceEvent {
  id: number;
  geofence_id: number;
  geofence_name: string;
  vehicle_id: string;
  event_type: GeofenceEventType;
  entered_at: string;
  exited_at: string | null;
  dwell_seconds: number | null;
  latitude: number;
  longitude: number;
  created_at: string;
}

export interface PaginatedGeofenceEvents {
  items: GeofenceEvent[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

export interface DwellTimeReport {
  geofence_id: number;
  geofence_name: string;
  total_events: number;
  avg_dwell_seconds: number;
  max_dwell_seconds: number;
  vehicles_inside: number;
}
