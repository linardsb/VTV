"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import { authFetch } from "@/lib/auth-fetch";
import type { BusPosition } from "@/types/route";

/** Raw vehicle from backend API (snake_case). */
interface ApiVehicle {
  vehicle_id: string;
  route_id: string;
  route_short_name: string;
  route_type: number;
  latitude: number;
  longitude: number;
  bearing: number | null;
  speed_kmh: number | null;
  delay_seconds: number;
  current_status: string;
  next_stop_name: string | null;
  current_stop_name: string | null;
  timestamp: string;
}

interface ApiResponse {
  count: number;
  vehicles: ApiVehicle[];
  fetched_at: string;
}

const STATUS_MAP: Record<string, BusPosition["currentStatus"]> = {
  IN_TRANSIT_TO: "in_transit",
  STOPPED_AT: "stopped",
  INCOMING_AT: "incoming",
};

/** Deterministic color from route short name when no color map is available. */
function routeColor(shortName: string): string {
  const PALETTE = [
    "#1E88E5", "#E53935", "#43A047", "#FB8C00",
    "#8E24AA", "#00ACC1", "#D81B60", "#3949AB",
    "#6D4C41", "#546E7A", "#F4511E", "#00897B",
  ];
  let hash = 0;
  for (let i = 0; i < shortName.length; i++) {
    hash = (hash * 31 + shortName.charCodeAt(i)) | 0;
  }
  return PALETTE[Math.abs(hash) % PALETTE.length];
}

function mapVehicle(
  v: ApiVehicle,
  colorMap: Record<string, string>,
): BusPosition {
  return {
    vehicleId: v.vehicle_id,
    routeId: v.route_id,
    routeShortName: v.route_short_name,
    routeType: v.route_type,
    routeColor: colorMap[v.route_id] ?? routeColor(v.route_short_name),
    latitude: v.latitude,
    longitude: v.longitude,
    bearing: v.bearing,
    delaySeconds: v.delay_seconds,
    currentStatus: STATUS_MAP[v.current_status] ?? "in_transit",
    nextStopName: v.next_stop_name,
    timestamp: v.timestamp,
  };
}

interface UseVehiclePositionsOptions {
  /** Polling interval in ms. Default 10000 (10s). */
  interval?: number;
  /** Route color map: routeId -> hex color. */
  colorMap?: Record<string, string>;
  /** Backend API base URL. Default http://localhost:8123. */
  apiBase?: string;
}

interface UseVehiclePositionsResult {
  vehicles: BusPosition[];
  isLoading: boolean;
  error: string | null;
  lastFetchedAt: string | null;
}

export function useVehiclePositions(
  options: UseVehiclePositionsOptions = {},
): UseVehiclePositionsResult {
  const {
    interval = 10000,
    colorMap = {},
    apiBase = "http://localhost:8123",
  } = options;

  const [vehicles, setVehicles] = useState<BusPosition[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [lastFetchedAt, setLastFetchedAt] = useState<string | null>(null);
  const colorMapRef = useRef(colorMap);
  colorMapRef.current = colorMap;

  const fetchVehicles = useCallback(async () => {
    try {
      const res = await authFetch(`${apiBase}/api/v1/transit/vehicles`);
      if (!res.ok) {
        setError(`API error: ${res.status}`);
        return;
      }
      const data: ApiResponse = await res.json();
      setVehicles(data.vehicles.map((v) => mapVehicle(v, colorMapRef.current)));
      setLastFetchedAt(data.fetched_at);
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to fetch vehicles");
    } finally {
      setIsLoading(false);
    }
  }, [apiBase]);

  useEffect(() => {
    void fetchVehicles();
    const timer = setInterval(() => void fetchVehicles(), interval);
    return () => clearInterval(timer);
  }, [fetchVehicles, interval]);

  return { vehicles, isLoading, error, lastFetchedAt };
}
