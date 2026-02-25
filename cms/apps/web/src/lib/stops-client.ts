/**
 * VTV Stops API Client
 *
 * Connects to the FastAPI stops endpoints for stop management.
 *
 * Usage:
 *   import { fetchStops, createStop } from "@/lib/stops-client"
 */

import type {
  Stop,
  StopCreate,
  StopUpdate,
  PaginatedStops,
  NearbyParams,
} from "@/types/stop";
import { authFetch } from "@/lib/auth-fetch";

const BASE_URL =
  process.env.NEXT_PUBLIC_AGENT_URL ?? "http://localhost:8123";
const API_PREFIX = "/api/v1/stops";

/** Error thrown when the stops API returns a non-OK response. */
export class StopsApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.name = "StopsApiError";
    this.status = status;
  }
}

async function handleResponse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    const detail = await response.text().catch(() => "Unknown error");
    throw new StopsApiError(response.status, detail);
  }
  return response.json() as Promise<T>;
}

/** Fetch paginated stops with optional filters. */
export async function fetchStops(params: {
  page?: number;
  page_size?: number;
  search?: string;
  active_only?: boolean;
  location_type?: number;
}): Promise<PaginatedStops> {
  const searchParams = new URLSearchParams();
  if (params.page !== undefined) searchParams.set("page", String(params.page));
  if (params.page_size !== undefined)
    searchParams.set("page_size", String(params.page_size));
  if (params.search) searchParams.set("search", params.search);
  if (params.active_only !== undefined)
    searchParams.set("active_only", String(params.active_only));
  if (params.location_type !== undefined)
    searchParams.set("location_type", String(params.location_type));

  const response = await authFetch(
    `${BASE_URL}${API_PREFIX}/?${searchParams.toString()}`,
  );
  return handleResponse<PaginatedStops>(response);
}

/** Fetch all stops for map display (single unpaginated request). */
export async function fetchAllStopsForMap(): Promise<Stop[]> {
  const response = await authFetch(`${BASE_URL}${API_PREFIX}/map`);
  return handleResponse<Stop[]>(response);
}

/** Fetch IDs of terminal stops (last stop of each trip). */
export async function fetchTerminalStopIds(): Promise<number[]> {
  const response = await authFetch(`${BASE_URL}${API_PREFIX}/terminals`);
  return handleResponse<number[]>(response);
}

/** Fetch a single stop by ID. */
export async function fetchStop(id: number): Promise<Stop> {
  const response = await authFetch(`${BASE_URL}${API_PREFIX}/${id}`);
  return handleResponse<Stop>(response);
}

/** Create a new stop. */
export async function createStop(data: StopCreate): Promise<Stop> {
  const response = await authFetch(`${BASE_URL}${API_PREFIX}/`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  return handleResponse<Stop>(response);
}

/** Update an existing stop. */
export async function updateStop(
  id: number,
  data: StopUpdate,
): Promise<Stop> {
  const response = await authFetch(`${BASE_URL}${API_PREFIX}/${id}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  return handleResponse<Stop>(response);
}

/** Delete a stop. */
export async function deleteStop(id: number): Promise<void> {
  const response = await authFetch(`${BASE_URL}${API_PREFIX}/${id}`, {
    method: "DELETE",
  });
  if (!response.ok) {
    const detail = await response.text().catch(() => "Unknown error");
    throw new StopsApiError(response.status, detail);
  }
}

/** Fetch stops near a location. */
export async function fetchNearbyStops(
  params: NearbyParams,
): Promise<Stop[]> {
  const searchParams = new URLSearchParams();
  searchParams.set("latitude", String(params.latitude));
  searchParams.set("longitude", String(params.longitude));
  if (params.radius_meters !== undefined)
    searchParams.set("radius_meters", String(params.radius_meters));
  if (params.limit !== undefined)
    searchParams.set("limit", String(params.limit));

  const response = await authFetch(
    `${BASE_URL}${API_PREFIX}/nearby?${searchParams.toString()}`,
  );
  return handleResponse<Stop[]>(response);
}
