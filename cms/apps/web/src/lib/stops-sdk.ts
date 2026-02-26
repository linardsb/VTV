/**
 * Stops API client powered by @vtv/sdk.
 *
 * Drop-in replacement for stops-client.ts — same function signatures,
 * backed by the generated SDK instead of hand-written fetch calls.
 */

import "@/lib/sdk";
import {
  listStopsApiV1StopsGet,
  getStopApiV1StopsStopIdGet,
  createStopApiV1StopsPost,
  updateStopApiV1StopsStopIdPatch,
  deleteStopApiV1StopsStopIdDelete,
  listAllStopsForMapApiV1StopsMapGet,
  listTerminalStopIdsApiV1StopsTerminalsGet,
  nearbyStopsApiV1StopsNearbyGet,
} from "@vtv/sdk";
import type {
  Stop,
  StopCreate,
  StopUpdate,
  PaginatedStops,
  NearbyParams,
} from "@/types/stop";

/** Error thrown when the stops API returns a non-OK response. */
export class StopsApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.name = "StopsApiError";
    this.status = status;
  }
}

/** Fetch paginated stops with optional filters. */
export async function fetchStops(params: {
  page?: number;
  page_size?: number;
  search?: string;
  active_only?: boolean;
  location_type?: number;
}): Promise<PaginatedStops> {
  const { data, error, response } = await listStopsApiV1StopsGet({
    query: {
      page: params.page,
      page_size: params.page_size,
      search: params.search ?? null,
      active_only: params.active_only,
      location_type: params.location_type ?? null,
    },
  });
  if (error || !data) {
    throw new StopsApiError(
      response.status,
      typeof error === "string" ? error : "Failed to fetch stops",
    );
  }
  return data as unknown as PaginatedStops;
}

/** Fetch a single stop by ID. */
export async function fetchStop(id: number): Promise<Stop> {
  const { data, error, response } = await getStopApiV1StopsStopIdGet({
    path: { stop_id: id },
  });
  if (error || !data) {
    throw new StopsApiError(
      response.status,
      typeof error === "string" ? error : "Failed to fetch stop",
    );
  }
  return data as unknown as Stop;
}

/** Create a new stop. */
export async function createStop(stopData: StopCreate): Promise<Stop> {
  const { data, error, response } = await createStopApiV1StopsPost({
    body: stopData,
  });
  if (error || !data) {
    throw new StopsApiError(
      response.status,
      typeof error === "string" ? error : "Failed to create stop",
    );
  }
  return data as unknown as Stop;
}

/** Update an existing stop. */
export async function updateStop(
  id: number,
  stopData: StopUpdate,
): Promise<Stop> {
  const { data, error, response } = await updateStopApiV1StopsStopIdPatch({
    path: { stop_id: id },
    body: stopData,
  });
  if (error || !data) {
    throw new StopsApiError(
      response.status,
      typeof error === "string" ? error : "Failed to update stop",
    );
  }
  return data as unknown as Stop;
}

/** Delete a stop. */
export async function deleteStop(id: number): Promise<void> {
  const { error, response } = await deleteStopApiV1StopsStopIdDelete({
    path: { stop_id: id },
  });
  if (error) {
    throw new StopsApiError(
      response.status,
      typeof error === "string" ? error : "Failed to delete stop",
    );
  }
}

/** Fetch all stops for map display (single unpaginated request). */
export async function fetchAllStopsForMap(): Promise<Stop[]> {
  const { data, error, response } = await listAllStopsForMapApiV1StopsMapGet();
  if (error || !data) {
    throw new StopsApiError(
      response.status,
      typeof error === "string" ? error : "Failed to fetch stops for map",
    );
  }
  return data as unknown as Stop[];
}

/** Fetch IDs of terminal stops (last stop of each trip). */
export async function fetchTerminalStopIds(): Promise<number[]> {
  const { data, error, response } =
    await listTerminalStopIdsApiV1StopsTerminalsGet();
  if (error || !data) {
    throw new StopsApiError(
      response.status,
      typeof error === "string" ? error : "Failed to fetch terminal stop IDs",
    );
  }
  return data as unknown as number[];
}

/** Fetch stops near a location. */
export async function fetchNearbyStops(params: NearbyParams): Promise<Stop[]> {
  const { data, error, response } = await nearbyStopsApiV1StopsNearbyGet({
    query: {
      latitude: params.latitude,
      longitude: params.longitude,
      radius_meters: params.radius_meters,
      limit: params.limit,
    },
  });
  if (error || !data) {
    throw new StopsApiError(
      response.status,
      typeof error === "string" ? error : "Failed to fetch nearby stops",
    );
  }
  return data as unknown as Stop[];
}
