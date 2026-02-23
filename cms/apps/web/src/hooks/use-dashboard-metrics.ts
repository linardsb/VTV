"use client";

import { useState, useEffect, useCallback, useRef } from "react";
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

const POLL_INTERVAL = 30_000; // 30 seconds

export function useDashboardMetrics(): UseDashboardMetricsResult {
  const apiBase =
    process.env.NEXT_PUBLIC_AGENT_URL ?? "http://localhost:8123";

  const [data, setData] = useState<DashboardMetricsData | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const routesFetchedRef = useRef(false);
  const routeDataRef = useRef({ activeRoutes: 0, totalRoutes: 0 });

  const fetchMetrics = useCallback(async () => {
    try {
      // Always fetch vehicle data (polled)
      const vehicleRes = await authFetch(
        `${apiBase}/api/v1/transit/vehicles`,
      );

      let activeVehicles = 0;
      let onTimeCount = 0;
      let totalVehicles = 0;
      let delayedRoutes = 0;
      let distinctRouteCount = 0;

      if (vehicleRes.ok) {
        const vehicleData: VehicleApiResponse = await vehicleRes.json();
        activeVehicles = vehicleData.count;
        totalVehicles = vehicleData.vehicles.length;

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

        delayedRoutes = delayedRouteIds.size;
        distinctRouteCount = allRouteIds.size;
      }

      const onTimePercentage =
        totalVehicles > 0
          ? Math.round((onTimeCount / totalVehicles) * 1000) / 10
          : 0;

      // Fetch route counts only once
      if (!routesFetchedRef.current) {
        const [activeRes, totalRes] = await Promise.all([
          authFetch(
            `${apiBase}/api/v1/schedules/routes?is_active=true&page_size=1`,
          ),
          authFetch(`${apiBase}/api/v1/schedules/routes?page_size=1`),
        ]);

        if (activeRes.ok) {
          const activeData: PaginatedApiResponse = await activeRes.json();
          routeDataRef.current.activeRoutes = activeData.total;
        }

        if (totalRes.ok) {
          const totalData: PaginatedApiResponse = await totalRes.json();
          routeDataRef.current.totalRoutes = totalData.total;
        }

        routesFetchedRef.current = true;
      }

      setData({
        activeVehicles,
        onTimePercentage,
        onTimeCount,
        totalVehicles,
        delayedRoutes,
        activeRoutes: routeDataRef.current.activeRoutes,
        totalRoutes: routeDataRef.current.totalRoutes,
        distinctRouteCount,
      });
      setError(null);
    } catch (e) {
      setError(
        e instanceof Error ? e.message : "Failed to fetch dashboard metrics",
      );
    } finally {
      setIsLoading(false);
    }
  }, [apiBase]);

  useEffect(() => {
    void fetchMetrics();
    const timer = setInterval(() => void fetchMetrics(), POLL_INTERVAL);
    return () => clearInterval(timer);
  }, [fetchMetrics]);

  return { data, isLoading, error };
}
