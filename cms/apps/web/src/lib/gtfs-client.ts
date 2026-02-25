/**
 * VTV GTFS API Client
 *
 * Functions specific to the GTFS Data Management page:
 * stats aggregation, feed status, and GTFS ZIP export.
 */

import { authFetch } from "@/lib/auth-fetch";
import { fetchAgencies } from "@/lib/schedules-client";
import type { GTFSStats, GTFSFeed } from "@/types/gtfs";
import type { PaginatedResponse } from "@/types/schedule";

const BASE_URL =
  process.env.NEXT_PUBLIC_AGENT_URL ?? "http://localhost:8123";

/** Error thrown when a GTFS API request fails. */
export class GTFSApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.name = "GTFSApiError";
    this.status = status;
  }
}

/** Fetch aggregate GTFS data statistics by calling multiple endpoints in parallel. */
export async function fetchGTFSStats(): Promise<GTFSStats> {
  const [agencies, routesRes, calendarsRes, tripsRes, stopsRes] =
    await Promise.all([
      fetchAgencies(),
      authFetch(
        `${BASE_URL}/api/v1/schedules/routes?page=1&page_size=1`,
      ).then((r) => r.json() as Promise<PaginatedResponse<unknown>>),
      authFetch(
        `${BASE_URL}/api/v1/schedules/calendars?page=1&page_size=1`,
      ).then((r) => r.json() as Promise<PaginatedResponse<unknown>>),
      authFetch(
        `${BASE_URL}/api/v1/schedules/trips?page=1&page_size=1`,
      ).then((r) => r.json() as Promise<PaginatedResponse<unknown>>),
      authFetch(`${BASE_URL}/api/v1/stops/?page=1&page_size=1`).then(
        (r) => r.json() as Promise<PaginatedResponse<unknown>>,
      ),
    ]);

  return {
    agencies: agencies.length,
    routes: routesRes.total,
    calendars: calendarsRes.total,
    trips: tripsRes.total,
    stops: stopsRes.total,
  };
}

/** Fetch GTFS-RT feed configuration from the transit API. */
export async function fetchFeeds(): Promise<GTFSFeed[]> {
  const response = await authFetch(`${BASE_URL}/api/v1/transit/feeds`);
  if (!response.ok) {
    const detail = await response.text().catch(() => "Unknown error");
    throw new GTFSApiError(response.status, detail);
  }
  return response.json() as Promise<GTFSFeed[]>;
}

/** Export GTFS data as a ZIP file. Triggers a browser download. */
export async function exportGTFS(agencyId?: number): Promise<void> {
  const params = new URLSearchParams();
  if (agencyId !== undefined) {
    params.set("agency_id", String(agencyId));
  }
  const query = params.toString();
  const url = `${BASE_URL}/api/v1/schedules/export${query ? `?${query}` : ""}`;

  const response = await authFetch(url);
  if (!response.ok) {
    const detail = await response.text().catch(() => "Unknown error");
    throw new GTFSApiError(response.status, detail);
  }

  const blob = await response.blob();
  const downloadUrl = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = downloadUrl;
  a.download = "gtfs.zip";
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(downloadUrl);
}
