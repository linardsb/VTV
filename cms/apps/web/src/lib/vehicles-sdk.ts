/**
 * Vehicles API client using authFetch.
 *
 * Uses authFetch directly because the @vtv/sdk does not yet include
 * vehicle management endpoints. Can be migrated to SDK wrappers
 * once the SDK is regenerated with the backend running.
 */

import { authFetch } from "@/lib/auth-fetch";
import type {
  Vehicle,
  VehicleCreate,
  VehicleUpdate,
  PaginatedVehicles,
  MaintenanceRecordCreate,
  MaintenanceRecord,
  PaginatedMaintenanceRecords,
} from "@/types/vehicle";

const BASE = process.env.NEXT_PUBLIC_AGENT_URL ?? "http://localhost:8123";

export class VehiclesApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.name = "VehiclesApiError";
    this.status = status;
  }
}

/** Fetch paginated vehicles with optional filters. */
export async function fetchVehicles(params: {
  page?: number;
  page_size?: number;
  search?: string;
  vehicle_type?: string;
  status?: string;
  active_only?: boolean;
}): Promise<PaginatedVehicles> {
  const query = new URLSearchParams();
  if (params.page) query.set("page", String(params.page));
  if (params.page_size) query.set("page_size", String(params.page_size));
  if (params.search) query.set("search", params.search);
  if (params.vehicle_type) query.set("vehicle_type", params.vehicle_type);
  if (params.status) query.set("status", params.status);
  if (params.active_only !== undefined)
    query.set("active_only", String(params.active_only));
  const res = await authFetch(
    `${BASE}/api/v1/vehicles/?${query.toString()}`,
  );
  if (!res.ok)
    throw new VehiclesApiError(res.status, "Failed to fetch vehicles");
  return res.json() as Promise<PaginatedVehicles>;
}

/** Fetch a single vehicle by ID. */
export async function fetchVehicle(id: number): Promise<Vehicle> {
  const res = await authFetch(`${BASE}/api/v1/vehicles/${id}`);
  if (!res.ok)
    throw new VehiclesApiError(res.status, "Failed to fetch vehicle");
  return res.json() as Promise<Vehicle>;
}

/** Create a new vehicle. */
export async function createVehicle(
  data: VehicleCreate,
): Promise<Vehicle> {
  const res = await authFetch(`${BASE}/api/v1/vehicles/`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  if (!res.ok)
    throw new VehiclesApiError(res.status, "Failed to create vehicle");
  return res.json() as Promise<Vehicle>;
}

/** Update an existing vehicle. */
export async function updateVehicle(
  id: number,
  data: VehicleUpdate,
): Promise<Vehicle> {
  const res = await authFetch(`${BASE}/api/v1/vehicles/${id}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  if (!res.ok)
    throw new VehiclesApiError(res.status, "Failed to update vehicle");
  return res.json() as Promise<Vehicle>;
}

/** Delete a vehicle. */
export async function deleteVehicle(id: number): Promise<void> {
  const res = await authFetch(`${BASE}/api/v1/vehicles/${id}`, {
    method: "DELETE",
  });
  if (!res.ok)
    throw new VehiclesApiError(res.status, "Failed to delete vehicle");
}

/** Assign or unassign a driver to/from a vehicle. */
export async function assignDriver(
  vehicleId: number,
  driverId: number | null,
): Promise<Vehicle> {
  const query =
    driverId !== null ? `?driver_id=${driverId}` : "";
  const res = await authFetch(
    `${BASE}/api/v1/vehicles/${vehicleId}/assign-driver${query}`,
    { method: "POST" },
  );
  if (!res.ok)
    throw new VehiclesApiError(res.status, "Failed to assign driver");
  return res.json() as Promise<Vehicle>;
}

/** Fetch maintenance history for a vehicle. */
export async function fetchMaintenanceHistory(
  vehicleId: number,
  params: { page?: number; page_size?: number },
): Promise<PaginatedMaintenanceRecords> {
  const query = new URLSearchParams();
  if (params.page) query.set("page", String(params.page));
  if (params.page_size) query.set("page_size", String(params.page_size));
  const res = await authFetch(
    `${BASE}/api/v1/vehicles/${vehicleId}/maintenance?${query.toString()}`,
  );
  if (!res.ok)
    throw new VehiclesApiError(
      res.status,
      "Failed to fetch maintenance history",
    );
  return res.json() as Promise<PaginatedMaintenanceRecords>;
}

/** Add a maintenance record to a vehicle. */
export async function createMaintenanceRecord(
  vehicleId: number,
  data: MaintenanceRecordCreate,
): Promise<MaintenanceRecord> {
  const res = await authFetch(
    `${BASE}/api/v1/vehicles/${vehicleId}/maintenance`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data),
    },
  );
  if (!res.ok)
    throw new VehiclesApiError(
      res.status,
      "Failed to create maintenance record",
    );
  return res.json() as Promise<MaintenanceRecord>;
}
