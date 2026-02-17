/** GTFS route_type codes */
export type RouteType = 0 | 3 | 11; // 0=Tram, 3=Bus, 11=Trolleybus

export type RouteTypeLabel = "tram" | "bus" | "trolleybus";

export interface Route {
  id: string;
  agencyId: string;
  shortName: string;
  longName: string;
  type: RouteType;
  color: string;
  textColor: string;
  description: string;
  isActive: boolean;
  createdAt: string; // ISO date string
  updatedAt: string;
}

export interface RouteFormData {
  shortName: string;
  longName: string;
  type: RouteType;
  agencyId: string;
  color: string;
  textColor: string;
  description: string;
  isActive: boolean;
}

export const ROUTE_TYPE_MAP: Record<RouteType, RouteTypeLabel> = {
  0: "tram",
  3: "bus",
  11: "trolleybus",
};

export const AGENCY_IDS = ["rs", "atd", "lap", "dap", "nordeka"] as const;
export type AgencyId = (typeof AGENCY_IDS)[number];
