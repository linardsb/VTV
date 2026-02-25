"use client";

import { useMemo } from "react";
import useSWR from "swr";
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
  /** Backend API base URL. Defaults to NEXT_PUBLIC_AGENT_URL env var. */
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
    apiBase = process.env.NEXT_PUBLIC_AGENT_URL ?? "http://localhost:8123",
  } = options;

  // SWR key includes apiBase so different bases get separate cache entries
  const { data, error: swrError, isLoading } = useSWR<ApiResponse>(
    `${apiBase}/api/v1/transit/vehicles`,
    { refreshInterval: interval },
  );

  const vehicles = useMemo(
    () => (data?.vehicles ?? []).map((v) => mapVehicle(v, colorMap)),
    [data, colorMap],
  );

  const lastFetchedAt = data?.fetched_at ?? null;

  return {
    vehicles,
    isLoading,
    error: swrError instanceof Error ? swrError.message : null,
    lastFetchedAt,
  };
}
