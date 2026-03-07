/** GTFS route_type labels — basic (0-12) and extended (100-1700) */
export const ROUTE_TYPE_LABELS: Record<number, string> = {
  0: "tram",
  1: "subway",
  2: "rail",
  3: "bus",
  4: "ferry",
  5: "cableTram",
  6: "gondola",
  7: "funicular",
  11: "trolleybus",
  12: "monorail",
};

/** Extended GTFS type ranges → basic label key */
const EXTENDED_RANGES: [number, number, string][] = [
  [700, 799, "bus"],
  [800, 899, "trolleybus"],
  [900, 999, "tram"],
];

/** Get a human-readable label key for a route type number (basic or extended) */
export function getRouteTypeLabel(type: number): string {
  const basic = ROUTE_TYPE_LABELS[type];
  if (basic) return basic;
  for (const [min, max, label] of EXTENDED_RANGES) {
    if (type >= min && type <= max) return label;
  }
  return "other";
}

/** Route response matching backend RouteResponse (snake_case) */
export interface Route {
  id: number;
  gtfs_route_id: string;
  agency_id: number;
  route_short_name: string;
  route_long_name: string;
  route_type: number;
  route_color: string | null;
  route_text_color: string | null;
  route_sort_order: number | null;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface RouteCreate {
  gtfs_route_id: string;
  agency_id: number;
  route_short_name: string;
  route_long_name: string;
  route_type: number;
  route_color?: string | null;
  route_text_color?: string | null;
  route_sort_order?: number | null;
}

export interface RouteUpdate {
  route_short_name?: string;
  route_long_name?: string;
  route_type?: number;
  route_color?: string | null;
  route_text_color?: string | null;
  route_sort_order?: number | null;
  is_active?: boolean;
}

/** Live vehicle position (from transit GTFS-RT endpoint — uses its own shape) */
export interface BusPosition {
  vehicleId: string;
  routeId: string;
  routeShortName: string;
  routeType: number;
  routeColor: string;
  latitude: number;
  longitude: number;
  bearing: number | null;
  delaySeconds: number;
  currentStatus: "in_transit" | "stopped" | "incoming";
  nextStopName: string | null;
  timestamp: string;
  /** GTFS-RT feed source identifier (e.g., "riga", "jurmala") */
  feedId: string;
  /** Human-readable operator name (e.g., "Rigas Satiksme") */
  operatorName: string;
}
