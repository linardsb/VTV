/**
 * Route Performance API client using authFetch.
 *
 * Uses authFetch directly because the @vtv/sdk does not yet include
 * route performance endpoints. Can be migrated to SDK wrappers
 * once the SDK is regenerated with the backend running.
 */

import { authFetch } from "@/lib/auth-fetch";
import { apiBase } from "@/lib/api-base";
import type {
  RoutePerformanceTrendResponse,
  RouteDelayByStopResponse,
  RouteLoadTrendResponse,
  RouteAnomalyResponse,
} from "@/types/analytics";

const BASE = apiBase();

export class RoutePerformanceApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.name = "RoutePerformanceApiError";
    this.status = status;
  }
}

export async function fetchRoutePerformance(
  routeId: string,
  window: "7" | "14" | "30" = "7",
): Promise<RoutePerformanceTrendResponse> {
  const query = new URLSearchParams({ route_id: routeId, window });
  const res = await authFetch(
    `${BASE}/api/v1/analytics/route-performance?${query.toString()}`,
  );
  if (!res.ok)
    throw new RoutePerformanceApiError(
      res.status,
      "Failed to fetch route performance",
    );
  return res.json() as Promise<RoutePerformanceTrendResponse>;
}

export async function fetchRouteDelayByStop(
  routeId: string,
  window: "7" | "14" | "30" = "7",
): Promise<RouteDelayByStopResponse> {
  const query = new URLSearchParams({ route_id: routeId, window });
  const res = await authFetch(
    `${BASE}/api/v1/analytics/route-delay-by-stop?${query.toString()}`,
  );
  if (!res.ok)
    throw new RoutePerformanceApiError(
      res.status,
      "Failed to fetch delay by stop",
    );
  return res.json() as Promise<RouteDelayByStopResponse>;
}

export async function fetchRouteLoadTrend(
  routeId: string,
  window: "7" | "14" | "30" = "7",
): Promise<RouteLoadTrendResponse> {
  const query = new URLSearchParams({ route_id: routeId, window });
  const res = await authFetch(
    `${BASE}/api/v1/analytics/route-load-trend?${query.toString()}`,
  );
  if (!res.ok)
    throw new RoutePerformanceApiError(
      res.status,
      "Failed to fetch load trend",
    );
  return res.json() as Promise<RouteLoadTrendResponse>;
}

export async function fetchRouteAnomalies(
  routeId: string,
  window: "7" | "14" | "30" = "7",
): Promise<RouteAnomalyResponse> {
  const query = new URLSearchParams({ route_id: routeId, window });
  const res = await authFetch(
    `${BASE}/api/v1/analytics/route-anomalies?${query.toString()}`,
  );
  if (!res.ok)
    throw new RoutePerformanceApiError(
      res.status,
      "Failed to fetch anomalies",
    );
  return res.json() as Promise<RouteAnomalyResponse>;
}
