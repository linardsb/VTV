"use client";

import { useState, useEffect, useRef, useMemo } from "react";
import useSWR from "swr";
import type { BusPosition } from "@/types/route";
import { getToken } from "@/lib/auth-fetch";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

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
  feed_id: string;
  operator_name: string;
}

interface ApiResponse {
  count: number;
  vehicles: ApiVehicle[];
  fetched_at: string;
}

/** Connection mode exposed to consumers for UI display. */
export type ConnectionMode = "connecting" | "ws" | "polling";

interface UseVehiclePositionsOptions {
  /** SWR fallback polling interval in ms. Default 10000 (10s). */
  interval?: number;
  /** Route color map: routeId -> hex color. */
  colorMap?: Record<string, string>;
  /** Backend API base URL. Defaults to NEXT_PUBLIC_AGENT_URL env var. */
  apiBase?: string;
  /** Optional GTFS route_id to push as server-side WS filter. null = all routes. */
  routeFilter?: string | null;
  /** Optional feed_id to push as server-side WS filter. null = all feeds. */
  feedFilter?: string | null;
}

interface UseVehiclePositionsResult {
  vehicles: BusPosition[];
  isLoading: boolean;
  error: string | null;
  lastFetchedAt: string | null;
  /** Current data delivery mode. */
  connectionMode: ConnectionMode;
}

// ---------------------------------------------------------------------------
// Helpers (module scope — unchanged from original)
// ---------------------------------------------------------------------------

const STATUS_MAP: Record<string, BusPosition["currentStatus"]> = {
  IN_TRANSIT_TO: "in_transit",
  STOPPED_AT: "stopped",
  INCOMING_AT: "incoming",
};

/** Color by route type matching Rīgas Satiksme scheme. */
function routeTypeColor(routeType: number): string {
  // Tram (0, 900-999)
  if (routeType === 0 || (routeType >= 900 && routeType <= 999)) return "#E53935";
  // Trolleybus (800-899)
  if (routeType >= 800 && routeType <= 899) return "#1E88E5";
  // Bus (3, 700-799) and default
  return "#FB8C00";
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
    routeColor: colorMap[v.route_id] ?? routeTypeColor(v.route_type),
    latitude: v.latitude,
    longitude: v.longitude,
    bearing: v.bearing,
    delaySeconds: v.delay_seconds,
    currentStatus: STATUS_MAP[v.current_status] ?? "in_transit",
    nextStopName: v.next_stop_name,
    timestamp: v.timestamp,
    feedId: v.feed_id ?? "",
    operatorName: v.operator_name ?? "",
  };
}

/** Derive WebSocket URL from the REST API base URL. */
function getWsUrl(apiBase: string): string {
  const url = new URL(apiBase);
  url.protocol = url.protocol === "https:" ? "wss:" : "ws:";
  url.pathname = "/ws/transit/vehicles";
  return url.toString();
}

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const MAX_RECONNECT_ATTEMPTS = 3;
/** Retry WebSocket every 60s while in polling fallback. */
const WS_RETRY_INTERVAL = 60_000;

// ---------------------------------------------------------------------------
// Hook
// ---------------------------------------------------------------------------

export function useVehiclePositions(
  options: UseVehiclePositionsOptions = {},
): UseVehiclePositionsResult {
  const {
    interval = 10_000,
    colorMap = {},
    apiBase = process.env.NEXT_PUBLIC_AGENT_URL ?? "http://localhost:8123",
    routeFilter,
    feedFilter,
  } = options;

  // -- State (all useState FIRST per React 19 hook ordering) ----------------
  const [vehicles, setVehicles] = useState<BusPosition[]>([]);
  const [lastFetchedAt, setLastFetchedAt] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isWsConnected, setIsWsConnected] = useState(false);
  const [connectionFailed, setConnectionFailed] = useState(false);
  const [connectTrigger, setConnectTrigger] = useState(0);

  // -- Refs (after all useState) --------------------------------------------
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const reconnectAttemptRef = useRef(0);
  const colorMapRef = useRef<Record<string, string>>(colorMap);
  const rawVehiclesRef = useRef<ApiVehicle[]>([]);
  const routeFilterRef = useRef<string | null>(routeFilter ?? null);
  const feedFilterRef = useRef<string | null>(feedFilter ?? null);

  // -- Sync colorMap ref ----------------------------------------------------
  useEffect(() => {
    colorMapRef.current = colorMap;
  }, [colorMap]);

  // -- Sync routeFilter ref + re-subscribe on change -----------------------
  useEffect(() => {
    routeFilterRef.current = routeFilter ?? null;
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(
        JSON.stringify({
          action: "subscribe",
          route_id: routeFilter ?? undefined,
          feed_id: feedFilterRef.current ?? undefined,
        }),
      );
    }
  }, [routeFilter]);

  // -- Sync feedFilter ref + re-subscribe on change ------------------------
  useEffect(() => {
    feedFilterRef.current = feedFilter ?? null;
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(
        JSON.stringify({
          action: "subscribe",
          route_id: routeFilterRef.current ?? undefined,
          feed_id: feedFilter ?? undefined,
        }),
      );
    }
  }, [feedFilter]);

  // -- Main WebSocket lifecycle ---------------------------------------------
  useEffect(() => {
    let cancelled = false;

    async function connect() {
      const token = await getToken();
      if (cancelled) return;
      if (!token) {
        setConnectionFailed(true);
        return;
      }

      const wsUrl = getWsUrl(apiBase);
      const fullUrl = `${wsUrl}?token=${encodeURIComponent(token)}`;
      const ws = new WebSocket(fullUrl);
      wsRef.current = ws;

      ws.onopen = () => {
        if (cancelled) {
          ws.close();
          return;
        }
        reconnectAttemptRef.current = 0;
        setIsWsConnected(true);
        setConnectionFailed(false);
        setError(null);
        // Subscribe with current route + feed filters
        ws.send(
          JSON.stringify({
            action: "subscribe",
            route_id: routeFilterRef.current ?? undefined,
            feed_id: feedFilterRef.current ?? undefined,
          }),
        );
      };

      ws.onmessage = (event) => {
        try {
          const msg = JSON.parse(event.data as string) as Record<
            string,
            unknown
          >;
          const msgType = msg.type as string | undefined;

          if (msgType === "vehicle_update") {
            const apiVehicles = (msg.vehicles as ApiVehicle[]) ?? [];
            rawVehiclesRef.current = apiVehicles;
            setVehicles(
              apiVehicles.map((v) => mapVehicle(v, colorMapRef.current)),
            );
            setLastFetchedAt(
              (msg.timestamp as string) ?? new Date().toISOString(),
            );
            setError(null);
          } else if (msgType === "ping") {
            ws.send(JSON.stringify({ action: "pong" }));
          } else if (msgType === "error") {
            setError((msg.message as string) ?? "WebSocket error");
          }
          // "ack" messages are informational — no action needed
        } catch {
          // Malformed message — ignore
        }
      };

      ws.onclose = () => {
        if (cancelled) return;
        wsRef.current = null;
        setIsWsConnected(false);

        if (reconnectAttemptRef.current < MAX_RECONNECT_ATTEMPTS) {
          const delay = Math.min(
            1000 * Math.pow(2, reconnectAttemptRef.current),
            8000,
          );
          reconnectAttemptRef.current += 1;
          reconnectTimerRef.current = setTimeout(() => {
            if (!cancelled) void connect();
          }, delay);
        } else {
          setConnectionFailed(true);
        }
      };

      ws.onerror = () => {
        // Browser fires error before close — close handler manages reconnect
      };
    }

    void connect();

    return () => {
      cancelled = true;
      if (reconnectTimerRef.current) clearTimeout(reconnectTimerRef.current);
      if (wsRef.current) {
        wsRef.current.onclose = null; // Prevent reconnect on intentional close
        wsRef.current.close(1000);
        wsRef.current = null;
      }
    };
  }, [apiBase, connectTrigger]);

  // -- Periodic WS retry while in polling fallback --------------------------
  useEffect(() => {
    if (!connectionFailed) return;

    const retryTimer = setInterval(() => {
      reconnectAttemptRef.current = 0;
      setConnectionFailed(false);
      setConnectTrigger((n) => n + 1);
    }, WS_RETRY_INTERVAL);

    return () => clearInterval(retryTimer);
  }, [connectionFailed]);

  // -- SWR fallback when WebSocket fails ------------------------------------
  const swrUrl = connectionFailed
    ? `${apiBase}/api/v1/transit/vehicles${feedFilterRef.current ? `?feed_id=${feedFilterRef.current}` : ""}`
    : null;
  const { data: swrData } = useSWR<ApiResponse>(swrUrl, {
    refreshInterval: interval,
  });

  // Map SWR data when in fallback mode
  useEffect(() => {
    if (!connectionFailed || !swrData) return;
    rawVehiclesRef.current = swrData.vehicles;
    setVehicles(
      swrData.vehicles.map((v) => mapVehicle(v, colorMapRef.current)),
    );
    setLastFetchedAt(swrData.fetched_at);
  }, [connectionFailed, swrData]);

  // -- Derived values -------------------------------------------------------

  // Re-map when colorMap changes (for already-received data)
  const mappedVehicles = useMemo(
    () => rawVehiclesRef.current.map((v) => mapVehicle(v, colorMap)),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [colorMap, vehicles], // vehicles state change signals new rawVehiclesRef data
  );

  // Connection mode for UI display
  const connectionMode: ConnectionMode = isWsConnected
    ? "ws"
    : connectionFailed
      ? "polling"
      : "connecting";

  const isLoading = vehicles.length === 0 && !lastFetchedAt && !error;

  return {
    vehicles: mappedVehicles,
    isLoading,
    error,
    lastFetchedAt,
    connectionMode,
  };
}
