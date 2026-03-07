/**
 * GTFS API client powered by @vtv/sdk.
 *
 * Drop-in replacement for gtfs-client.ts — same function signatures.
 * Stats aggregation uses SDK wrappers. Export keeps authFetch for binary blob.
 */

import "@/lib/sdk";
import { getFeedsApiV1TransitFeedsGet } from "@vtv/sdk";
import { authFetch } from "@/lib/auth-fetch";
import { fetchAgencies, fetchRoutes, fetchCalendars, fetchTrips } from "@/lib/schedules-sdk";
import { fetchStops } from "@/lib/stops-sdk";
import type { GTFSStats, GTFSFeed, ExportMetadata } from "@/types/gtfs";

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
  const [agencies, routes, calendars, trips, stops] = await Promise.all([
    fetchAgencies().catch(() => []),
    fetchRoutes({ page: 1, page_size: 1 }).catch(() => ({ total: 0 })),
    fetchCalendars({ page: 1, page_size: 1 }).catch(() => ({ total: 0 })),
    fetchTrips({ page: 1, page_size: 1 }).catch(() => ({ total: 0 })),
    fetchStops({ page: 1, page_size: 1 }).catch(() => ({ total: 0 })),
  ]);

  return {
    agencies: Array.isArray(agencies) ? agencies.length : 0,
    routes: "total" in routes ? routes.total : 0,
    calendars: "total" in calendars ? calendars.total : 0,
    trips: "total" in trips ? trips.total : 0,
    stops: "total" in stops ? stops.total : 0,
  };
}

/** Fetch GTFS-RT feed configuration from the transit API. */
export async function fetchFeeds(): Promise<GTFSFeed[]> {
  const { data, error, response } = await getFeedsApiV1TransitFeedsGet();
  if (error || !data) {
    throw new GTFSApiError(
      response.status,
      typeof error === "string" ? error : "Failed to fetch feeds",
    );
  }
  return data as unknown as GTFSFeed[];
}

/** Export GTFS data as a ZIP file. Triggers a browser download. Uses authFetch for binary blob. */
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
  const disposition = response.headers.get("Content-Disposition");
  const filenameMatch = disposition?.match(/filename="?([^";\n]+)"?/);
  const filename = filenameMatch?.[1] ?? "gtfs.zip";

  const downloadUrl = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = downloadUrl;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(downloadUrl);
}

/** Download NeTEx XML export. Triggers a browser download. */
export async function exportNeTEx(agencyId?: number): Promise<void> {
  const params = new URLSearchParams();
  if (agencyId !== undefined) {
    params.set("agency_id", String(agencyId));
  }
  const query = params.toString();
  const url = `${BASE_URL}/api/v1/compliance/netex${query ? `?${query}` : ""}`;

  const response = await authFetch(url);
  if (!response.ok) {
    const detail = await response.text().catch(() => "Unknown error");
    throw new GTFSApiError(response.status, detail);
  }

  const blob = await response.blob();
  const downloadUrl = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = downloadUrl;
  a.download = "netex-export.xml";
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(downloadUrl);
}

/** Download SIRI Vehicle Monitoring XML. Triggers a browser download. */
export async function exportSiriVM(
  routeId?: string,
  feedId?: string,
): Promise<void> {
  const params = new URLSearchParams();
  if (routeId) params.set("route_id", routeId);
  if (feedId) params.set("feed_id", feedId);
  const query = params.toString();
  const url = `${BASE_URL}/api/v1/compliance/siri/vm${query ? `?${query}` : ""}`;

  const response = await authFetch(url);
  if (!response.ok) {
    const detail = await response.text().catch(() => "Unknown error");
    throw new GTFSApiError(response.status, detail);
  }

  const blob = await response.blob();
  const downloadUrl = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = downloadUrl;
  a.download = "siri-vm.xml";
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(downloadUrl);
}

/** Download SIRI Stop Monitoring XML. Triggers a browser download. */
export async function exportSiriSM(
  stopName: string,
  feedId?: string,
): Promise<void> {
  const params = new URLSearchParams();
  params.set("stop_name", stopName);
  if (feedId) params.set("feed_id", feedId);
  const query = params.toString();
  const url = `${BASE_URL}/api/v1/compliance/siri/sm?${query}`;

  const response = await authFetch(url);
  if (!response.ok) {
    const detail = await response.text().catch(() => "Unknown error");
    throw new GTFSApiError(response.status, detail);
  }

  const blob = await response.blob();
  const downloadUrl = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = downloadUrl;
  a.download = "siri-sm.xml";
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(downloadUrl);
}

/** Fetch compliance export status metadata. */
export async function fetchComplianceStatus(): Promise<ExportMetadata> {
  const url = `${BASE_URL}/api/v1/compliance/status`;
  const response = await authFetch(url);
  if (!response.ok) {
    const detail = await response.text().catch(() => "Unknown error");
    throw new GTFSApiError(response.status, detail);
  }
  return response.json() as Promise<ExportMetadata>;
}
