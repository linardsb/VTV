/**
 * Drivers API client powered by @vtv/sdk.
 *
 * Drop-in replacement for drivers-client.ts — same function signatures,
 * backed by the generated SDK instead of hand-written fetch calls.
 */

import "@/lib/sdk";
import {
  listDriversApiV1DriversGet,
  getDriverApiV1DriversDriverIdGet,
  createDriverApiV1DriversPost,
  updateDriverApiV1DriversDriverIdPatch,
  deleteDriverApiV1DriversDriverIdDelete,
} from "@vtv/sdk";
import type {
  Driver,
  DriverCreate,
  DriverUpdate,
  PaginatedDrivers,
} from "@/types/driver";

/** Error thrown when the drivers API returns a non-OK response. */
export class DriversApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.name = "DriversApiError";
    this.status = status;
  }
}

/** Fetch paginated drivers with optional filters. */
export async function fetchDrivers(params: {
  page?: number;
  page_size?: number;
  search?: string;
  active_only?: boolean;
  status?: string;
  shift?: string;
}): Promise<PaginatedDrivers> {
  const { data, error, response } = await listDriversApiV1DriversGet({
    query: {
      page: params.page,
      page_size: params.page_size,
      search: params.search ?? null,
      active_only: params.active_only,
      status: params.status ?? null,
      shift: params.shift ?? null,
    },
  });
  if (error || !data) {
    throw new DriversApiError(
      response.status,
      typeof error === "string" ? error : "Failed to fetch drivers",
    );
  }
  return data as unknown as PaginatedDrivers;
}

/** Fetch a single driver by ID. */
export async function fetchDriver(id: number): Promise<Driver> {
  const { data, error, response } = await getDriverApiV1DriversDriverIdGet({
    path: { driver_id: id },
  });
  if (error || !data) {
    throw new DriversApiError(
      response.status,
      typeof error === "string" ? error : "Failed to fetch driver",
    );
  }
  return data as unknown as Driver;
}

/** Create a new driver. */
export async function createDriver(driverData: DriverCreate): Promise<Driver> {
  const { data, error, response } = await createDriverApiV1DriversPost({
    body: driverData,
  });
  if (error || !data) {
    throw new DriversApiError(
      response.status,
      typeof error === "string" ? error : "Failed to create driver",
    );
  }
  return data as unknown as Driver;
}

/** Update an existing driver. */
export async function updateDriver(
  id: number,
  driverData: DriverUpdate,
): Promise<Driver> {
  const { data, error, response } = await updateDriverApiV1DriversDriverIdPatch(
    {
      path: { driver_id: id },
      body: driverData,
    },
  );
  if (error || !data) {
    throw new DriversApiError(
      response.status,
      typeof error === "string" ? error : "Failed to update driver",
    );
  }
  return data as unknown as Driver;
}

/** Delete a driver. */
export async function deleteDriver(id: number): Promise<void> {
  const { error, response } = await deleteDriverApiV1DriversDriverIdDelete({
    path: { driver_id: id },
  });
  if (error) {
    throw new DriversApiError(
      response.status,
      typeof error === "string" ? error : "Failed to delete driver",
    );
  }
}
