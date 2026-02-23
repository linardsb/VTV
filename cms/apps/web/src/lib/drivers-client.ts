/**
 * VTV Drivers API Client
 *
 * Connects to the FastAPI drivers endpoints for driver management.
 */

import type {
  Driver,
  DriverCreate,
  DriverUpdate,
  PaginatedDrivers,
} from "@/types/driver";
import { authFetch } from "@/lib/auth-fetch";

const BASE_URL =
  process.env.NEXT_PUBLIC_AGENT_URL ?? "http://localhost:8123";
const API_PREFIX = "/api/v1/drivers";

/** Error thrown when the drivers API returns a non-OK response. */
export class DriversApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.name = "DriversApiError";
    this.status = status;
  }
}

async function handleResponse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    const detail = await response.text().catch(() => "Unknown error");
    throw new DriversApiError(response.status, detail);
  }
  return response.json() as Promise<T>;
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
  const searchParams = new URLSearchParams();
  if (params.page !== undefined) searchParams.set("page", String(params.page));
  if (params.page_size !== undefined)
    searchParams.set("page_size", String(params.page_size));
  if (params.search) searchParams.set("search", params.search);
  if (params.active_only !== undefined)
    searchParams.set("active_only", String(params.active_only));
  if (params.status) searchParams.set("status", params.status);
  if (params.shift) searchParams.set("shift", params.shift);

  const response = await authFetch(
    `${BASE_URL}${API_PREFIX}/?${searchParams.toString()}`,
  );
  return handleResponse<PaginatedDrivers>(response);
}

/** Fetch a single driver by ID. */
export async function fetchDriver(id: number): Promise<Driver> {
  const response = await authFetch(`${BASE_URL}${API_PREFIX}/${id}`);
  return handleResponse<Driver>(response);
}

/** Create a new driver. */
export async function createDriver(data: DriverCreate): Promise<Driver> {
  const response = await authFetch(`${BASE_URL}${API_PREFIX}/`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  return handleResponse<Driver>(response);
}

/** Update an existing driver. */
export async function updateDriver(
  id: number,
  data: DriverUpdate,
): Promise<Driver> {
  const response = await authFetch(`${BASE_URL}${API_PREFIX}/${id}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  return handleResponse<Driver>(response);
}

/** Delete a driver. */
export async function deleteDriver(id: number): Promise<void> {
  const response = await authFetch(`${BASE_URL}${API_PREFIX}/${id}`, {
    method: "DELETE",
  });
  if (!response.ok) {
    const detail = await response.text().catch(() => "Unknown error");
    throw new DriversApiError(response.status, detail);
  }
}
