/**
 * Fleet API client using authFetch.
 *
 * Uses authFetch directly because the @vtv/sdk does not yet include
 * fleet management endpoints. Can be migrated to SDK wrappers
 * once the SDK is regenerated with the backend running.
 */

import { authFetch } from "@/lib/auth-fetch";
import type {
  TrackedDevice,
  TrackedDeviceCreate,
  TrackedDeviceUpdate,
  PaginatedDevices,
  VehiclePositionWithTelemetry,
  TelemetryHistoryPoint,
} from "@/types/fleet";

const BASE = process.env.NEXT_PUBLIC_AGENT_URL ?? "http://localhost:8123";

export class FleetApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.name = "FleetApiError";
    this.status = status;
  }
}

/** Fetch paginated fleet devices with optional filters. */
export async function fetchDevices(params: {
  page?: number;
  page_size?: number;
  search?: string;
  status?: string;
  vehicle_linked?: string;
}): Promise<PaginatedDevices> {
  const query = new URLSearchParams();
  if (params.page) query.set("page", String(params.page));
  if (params.page_size) query.set("page_size", String(params.page_size));
  if (params.search) query.set("search", params.search);
  if (params.status) query.set("status", params.status);
  if (params.vehicle_linked) query.set("vehicle_linked", params.vehicle_linked);
  const res = await authFetch(
    `${BASE}/api/v1/fleet/devices?${query.toString()}`,
  );
  if (!res.ok)
    throw new FleetApiError(res.status, "Failed to fetch devices");
  return res.json() as Promise<PaginatedDevices>;
}

/** Fetch a single fleet device by ID. */
export async function fetchDevice(deviceId: number): Promise<TrackedDevice> {
  const res = await authFetch(`${BASE}/api/v1/fleet/devices/${deviceId}`);
  if (!res.ok)
    throw new FleetApiError(res.status, "Failed to fetch device");
  return res.json() as Promise<TrackedDevice>;
}

/** Create a new fleet device. */
export async function createDevice(
  data: TrackedDeviceCreate,
): Promise<TrackedDevice> {
  const res = await authFetch(`${BASE}/api/v1/fleet/devices`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  if (!res.ok)
    throw new FleetApiError(res.status, "Failed to create device");
  return res.json() as Promise<TrackedDevice>;
}

/** Update an existing fleet device. */
export async function updateDevice(
  deviceId: number,
  data: TrackedDeviceUpdate,
): Promise<TrackedDevice> {
  const res = await authFetch(`${BASE}/api/v1/fleet/devices/${deviceId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  if (!res.ok)
    throw new FleetApiError(res.status, "Failed to update device");
  return res.json() as Promise<TrackedDevice>;
}

/** Delete a fleet device. */
export async function deleteDevice(deviceId: number): Promise<void> {
  const res = await authFetch(`${BASE}/api/v1/fleet/devices/${deviceId}`, {
    method: "DELETE",
  });
  if (!res.ok)
    throw new FleetApiError(res.status, "Failed to delete device");
}

/** Fetch real-time fleet device positions. */
export async function fetchFleetPositions(
  feedId?: string,
): Promise<VehiclePositionWithTelemetry[]> {
  const query = new URLSearchParams();
  if (feedId) query.set("feed_id", feedId);
  const res = await authFetch(
    `${BASE}/api/v1/transit/vehicles?${query.toString()}`,
  );
  if (!res.ok)
    throw new FleetApiError(res.status, "Failed to fetch fleet positions");
  return res.json() as Promise<VehiclePositionWithTelemetry[]>;
}

/** Fetch telemetry history for a specific vehicle. */
export async function fetchVehicleHistory(
  vehicleId: string,
  fromTime: string,
  toTime: string,
  limit?: number,
): Promise<TelemetryHistoryPoint[]> {
  const query = new URLSearchParams();
  query.set("from_time", fromTime);
  query.set("to_time", toTime);
  if (limit) query.set("limit", String(limit));
  const res = await authFetch(
    `${BASE}/api/v1/transit/vehicles/${vehicleId}/history?${query.toString()}`,
  );
  if (!res.ok)
    throw new FleetApiError(
      res.status,
      "Failed to fetch vehicle history",
    );
  return res.json() as Promise<TelemetryHistoryPoint[]>;
}
