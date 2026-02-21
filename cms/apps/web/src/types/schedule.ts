/** Paginated API response wrapper */
export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

/** Agency — transit operator */
export interface Agency {
  id: number;
  gtfs_agency_id: string;
  agency_name: string;
  agency_url: string | null;
  agency_timezone: string;
  agency_lang: string | null;
  created_at: string;
  updated_at: string;
}

export interface AgencyCreate {
  gtfs_agency_id: string;
  agency_name: string;
  agency_url?: string | null;
  agency_timezone?: string;
  agency_lang?: string | null;
}

/** Calendar — service schedule (days of week + date range) */
export interface Calendar {
  id: number;
  gtfs_service_id: string;
  monday: boolean;
  tuesday: boolean;
  wednesday: boolean;
  thursday: boolean;
  friday: boolean;
  saturday: boolean;
  sunday: boolean;
  start_date: string;
  end_date: string;
  created_at: string;
  updated_at: string;
}

export interface CalendarCreate {
  gtfs_service_id: string;
  monday: boolean;
  tuesday: boolean;
  wednesday: boolean;
  thursday: boolean;
  friday: boolean;
  saturday: boolean;
  sunday: boolean;
  start_date: string;
  end_date: string;
}

export interface CalendarUpdate {
  gtfs_service_id?: string;
  monday?: boolean;
  tuesday?: boolean;
  wednesday?: boolean;
  thursday?: boolean;
  friday?: boolean;
  saturday?: boolean;
  sunday?: boolean;
  start_date?: string;
  end_date?: string;
}

/** Calendar exception (added/removed service on specific dates) */
export interface CalendarException {
  id: number;
  calendar_id: number;
  date: string;
  exception_type: 1 | 2; // 1=added, 2=removed
  created_at: string;
  updated_at: string;
}

export interface CalendarExceptionCreate {
  date: string;
  exception_type: 1 | 2;
}

/** Trip — a sequence of stops on a route at specific times */
export interface Trip {
  id: number;
  gtfs_trip_id: string;
  route_id: number;
  calendar_id: number;
  direction_id: number | null;
  trip_headsign: string | null;
  block_id: string | null;
  created_at: string;
  updated_at: string;
}

export interface TripDetail extends Trip {
  stop_times: StopTime[];
}

export interface TripCreate {
  gtfs_trip_id: string;
  route_id: number;
  calendar_id: number;
  direction_id?: number | null;
  trip_headsign?: string | null;
  block_id?: string | null;
}

export interface TripUpdate {
  route_id?: number;
  calendar_id?: number;
  direction_id?: number | null;
  trip_headsign?: string | null;
  block_id?: string | null;
}

/** Stop time — arrival/departure at a stop within a trip */
export interface StopTime {
  id: number;
  trip_id: number;
  stop_id: number;
  stop_sequence: number;
  arrival_time: string;
  departure_time: string;
  pickup_type: number;
  drop_off_type: number;
  created_at: string;
  updated_at: string;
}

export interface StopTimeCreate {
  stop_id: number;
  stop_sequence: number;
  arrival_time: string;
  departure_time: string;
  pickup_type?: number;
  drop_off_type?: number;
}

export interface StopTimesBulkUpdate {
  stop_times: StopTimeCreate[];
}

/** GTFS import result */
export interface GTFSImportResponse {
  agencies_count: number;
  routes_count: number;
  calendars_count: number;
  calendar_dates_count: number;
  trips_count: number;
  stop_times_count: number;
  skipped_stop_times: number;
  warnings: string[];
}

/** Schedule validation result */
export interface ValidationResult {
  valid: boolean;
  errors: string[];
  warnings: string[];
}
