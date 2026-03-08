/**
 * Geofences API client using authFetch.
 *
 * Uses authFetch directly because the @vtv/sdk does not yet include
 * geofence management endpoints. Can be migrated to SDK wrappers
 * once the SDK is regenerated with the backend running.
 */

import { authFetch } from "@/lib/auth-fetch";
import type {
  Geofence,
  GeofenceCreate,
  GeofenceUpdate,
  PaginatedGeofences,
  PaginatedGeofenceEvents,
  DwellTimeReport,
} from "@/types/geofence";

const BASE = process.env.NEXT_PUBLIC_AGENT_URL ?? "http://localhost:8123";

export class GeofencesApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.name = "GeofencesApiError";
    this.status = status;
  }
}

/** Fetch paginated geofences with optional filters. */
export async function fetchGeofences(params: {
  page?: number;
  page_size?: number;
  search?: string;
  zone_type?: string;
  is_active?: boolean;
}): Promise<PaginatedGeofences> {
  const query = new URLSearchParams();
  if (params.page) query.set("page", String(params.page));
  if (params.page_size) query.set("page_size", String(params.page_size));
  if (params.search) query.set("search", params.search);
  if (params.zone_type) query.set("zone_type", params.zone_type);
  if (params.is_active !== undefined)
    query.set("is_active", String(params.is_active));
  const res = await authFetch(
    `${BASE}/api/v1/geofences/?${query.toString()}`,
  );
  if (!res.ok)
    throw new GeofencesApiError(res.status, "Failed to fetch geofences");
  return res.json() as Promise<PaginatedGeofences>;
}

/** Fetch a single geofence by ID. */
export async function fetchGeofence(geofenceId: number): Promise<Geofence> {
  const res = await authFetch(`${BASE}/api/v1/geofences/${geofenceId}`);
  if (!res.ok)
    throw new GeofencesApiError(res.status, "Failed to fetch geofence");
  return res.json() as Promise<Geofence>;
}

/** Create a new geofence. */
export async function createGeofence(
  data: GeofenceCreate,
): Promise<Geofence> {
  const res = await authFetch(`${BASE}/api/v1/geofences/`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  if (!res.ok)
    throw new GeofencesApiError(res.status, "Failed to create geofence");
  return res.json() as Promise<Geofence>;
}

/** Update an existing geofence. */
export async function updateGeofence(
  geofenceId: number,
  data: GeofenceUpdate,
): Promise<Geofence> {
  const res = await authFetch(`${BASE}/api/v1/geofences/${geofenceId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  if (!res.ok)
    throw new GeofencesApiError(res.status, "Failed to update geofence");
  return res.json() as Promise<Geofence>;
}

/** Delete a geofence. */
export async function deleteGeofence(geofenceId: number): Promise<void> {
  const res = await authFetch(`${BASE}/api/v1/geofences/${geofenceId}`, {
    method: "DELETE",
  });
  if (!res.ok)
    throw new GeofencesApiError(res.status, "Failed to delete geofence");
}

/** Fetch paginated geofence events across all zones. */
export async function fetchGeofenceEvents(params: {
  page?: number;
  page_size?: number;
  vehicle_id?: string;
  event_type?: string;
  geofence_id?: number;
  start_time?: string;
  end_time?: string;
}): Promise<PaginatedGeofenceEvents> {
  const query = new URLSearchParams();
  if (params.page) query.set("page", String(params.page));
  if (params.page_size) query.set("page_size", String(params.page_size));
  if (params.vehicle_id) query.set("vehicle_id", params.vehicle_id);
  if (params.event_type) query.set("event_type", params.event_type);
  if (params.geofence_id)
    query.set("geofence_id", String(params.geofence_id));
  if (params.start_time) query.set("start_time", params.start_time);
  if (params.end_time) query.set("end_time", params.end_time);
  const res = await authFetch(
    `${BASE}/api/v1/geofences/events?${query.toString()}`,
  );
  if (!res.ok)
    throw new GeofencesApiError(
      res.status,
      "Failed to fetch geofence events",
    );
  return res.json() as Promise<PaginatedGeofenceEvents>;
}

/** Fetch paginated events for a specific geofence zone. */
export async function fetchZoneEvents(
  geofenceId: number,
  params: {
    page?: number;
    page_size?: number;
    event_type?: string;
    start_time?: string;
    end_time?: string;
  },
): Promise<PaginatedGeofenceEvents> {
  const query = new URLSearchParams();
  if (params.page) query.set("page", String(params.page));
  if (params.page_size) query.set("page_size", String(params.page_size));
  if (params.event_type) query.set("event_type", params.event_type);
  if (params.start_time) query.set("start_time", params.start_time);
  if (params.end_time) query.set("end_time", params.end_time);
  const res = await authFetch(
    `${BASE}/api/v1/geofences/${geofenceId}/events?${query.toString()}`,
  );
  if (!res.ok)
    throw new GeofencesApiError(
      res.status,
      "Failed to fetch zone events",
    );
  return res.json() as Promise<PaginatedGeofenceEvents>;
}

/** Fetch dwell time report for a specific geofence. */
export async function fetchDwellReport(
  geofenceId: number,
  params: {
    start_time?: string;
    end_time?: string;
  },
): Promise<DwellTimeReport> {
  const query = new URLSearchParams();
  if (params.start_time) query.set("start_time", params.start_time);
  if (params.end_time) query.set("end_time", params.end_time);
  const res = await authFetch(
    `${BASE}/api/v1/geofences/${geofenceId}/dwell-report?${query.toString()}`,
  );
  if (!res.ok)
    throw new GeofencesApiError(
      res.status,
      "Failed to fetch dwell report",
    );
  return res.json() as Promise<DwellTimeReport>;
}
