"use client";

import { useState, useRef, useCallback } from "react";
import useSWR from "swr";
import { useSession } from "next-auth/react";
import { authFetch } from "@/lib/auth-fetch";

interface VehicleApiResponse {
  count: number;
  vehicles: Array<{
    vehicle_id: string;
    route_id: string;
    delay_seconds: number;
  }>;
  fetched_at: string;
}

interface PaginatedApiResponse {
  items: unknown[];
  total: number;
  page: number;
  page_size: number;
}

export interface DashboardMetricsData {
  activeVehicles: number;
  onTimePercentage: number;
  onTimeCount: number;
  totalVehicles: number;
  delayedRoutes: number;
  activeRoutes: number;
  totalRoutes: number;
  distinctRouteCount: number;
}

interface UseDashboardMetricsResult {
  data: DashboardMetricsData | null;
  isLoading: boolean;
  error: string | null;
}

const API_BASE = process.env.NEXT_PUBLIC_AGENT_URL ?? "http://localhost:8123";

export function useDashboardMetrics(): UseDashboardMetricsResult {
  const { status } = useSession();
  const routesFetchedRef = useRef(false);
  const [routeData, setRouteData] = useState({ activeRoutes: 0, totalRoutes: 0 });

  const fetchRouteCountsOnce = useCallback(async () => {
    if (routesFetchedRef.current) return;

    const [activeRes, totalRes] = await Promise.all([
      authFetch(`${API_BASE}/api/v1/schedules/routes?is_active=true&page_size=1`),
      authFetch(`${API_BASE}/api/v1/schedules/routes?page_size=1`),
    ]);

    let activeRoutes = 0;
    let totalRoutes = 0;

    if (activeRes.ok) {
      const activeData: PaginatedApiResponse = await activeRes.json();
      activeRoutes = activeData.total;
    }
    if (totalRes.ok) {
      const totalData: PaginatedApiResponse = await totalRes.json();
      totalRoutes = totalData.total;
    }

    setRouteData({ activeRoutes, totalRoutes });
    routesFetchedRef.current = true;
  }, []);

  // SWR key is null when not authenticated (disables fetching)
  const swrKey = status === "authenticated" ? `${API_BASE}/api/v1/transit/vehicles` : null;

  const { data: vehicleData, error: swrError, isLoading } = useSWR<VehicleApiResponse>(
    swrKey,
    {
      refreshInterval: 30_000,
      onSuccess: () => {
        // Fetch route counts once on first successful vehicle fetch
        void fetchRouteCountsOnce();
      },
    },
  );

  let metrics: DashboardMetricsData | null = null;

  if (vehicleData) {
    let onTimeCount = 0;
    const delayedRouteIds = new Set<string>();
    const allRouteIds = new Set<string>();

    for (const v of vehicleData.vehicles) {
      allRouteIds.add(v.route_id);
      if (Math.abs(v.delay_seconds) <= 300) {
        onTimeCount++;
      }
      if (v.delay_seconds > 300) {
        delayedRouteIds.add(v.route_id);
      }
    }

    const totalVehicles = vehicleData.vehicles.length;

    metrics = {
      activeVehicles: vehicleData.count,
      onTimePercentage:
        totalVehicles > 0
          ? Math.round((onTimeCount / totalVehicles) * 1000) / 10
          : 0,
      onTimeCount,
      totalVehicles,
      delayedRoutes: delayedRouteIds.size,
      activeRoutes: routeData.activeRoutes,
      totalRoutes: routeData.totalRoutes,
      distinctRouteCount: allRouteIds.size,
    };
  }

  return {
    data: metrics,
    isLoading,
    error: swrError instanceof Error ? swrError.message : null,
  };
}
