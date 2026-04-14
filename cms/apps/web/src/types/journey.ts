/** Transport mode for a journey leg. */
export type TransportMode =
  | "WALK"
  | "BUS"
  | "TRAM"
  | "RAIL"
  | "SUBWAY"
  | "FERRY"
  | "TROLLEYBUS"
  | "BICYCLE"
  | "CAR";

/** A single leg of a multi-modal journey. */
export interface JourneyLeg {
  mode: TransportMode;
  from_name: string;
  from_lat: number;
  from_lon: number;
  to_name: string;
  to_lat: number;
  to_lon: number;
  start_time: string;
  end_time: string;
  duration_seconds: number;
  distance_m: number;

  // Transit-specific (null for walk/bicycle legs)
  route_id: string | null;
  route_short_name: string | null;
  route_long_name: string | null;
  trip_id: string | null;
  agency_name: string | null;
  num_stops: number | null;

  // Enrichment from GTFS-RT delay data
  realtime_delay_seconds: number | null;
  scheduled_start_time: string | null;

  // Encoded polyline for map rendering
  polyline: string | null;
}

/** A single itinerary option with one or more legs. */
export interface JourneyItinerary {
  start_time: string;
  end_time: string;
  duration_seconds: number;
  walk_distance_m: number;
  transit_time_seconds: number;
  waiting_time_seconds: number;
  transfers: number;
  legs: JourneyLeg[];
}

/** Response for a journey plan request. */
export interface JourneyPlanResponse {
  from_name: string;
  from_lat: number;
  from_lon: number;
  to_name: string;
  to_lat: number;
  to_lon: number;
  itineraries: JourneyItinerary[];
  requested_at: string;
  otp_enriched: boolean;
}

/** Query parameters for the journey plan endpoint. */
export interface JourneyPlanParams {
  from_lat: number;
  from_lon: number;
  to_lat: number;
  to_lon: number;
  depart_at?: string;
  arrive_by?: string;
  modes?: string;
}
