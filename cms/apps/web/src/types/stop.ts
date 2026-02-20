export interface Stop {
  id: number;
  stop_name: string;
  gtfs_stop_id: string;
  stop_lat: number | null;
  stop_lon: number | null;
  stop_desc: string | null;
  location_type: number;
  parent_station_id: number | null;
  wheelchair_boarding: number;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface StopCreate {
  stop_name: string;
  gtfs_stop_id: string;
  stop_lat?: number | null;
  stop_lon?: number | null;
  stop_desc?: string | null;
  location_type?: number;
  parent_station_id?: number | null;
  wheelchair_boarding?: number;
}

export interface StopUpdate {
  stop_name?: string;
  gtfs_stop_id?: string;
  stop_lat?: number | null;
  stop_lon?: number | null;
  stop_desc?: string | null;
  location_type?: number;
  parent_station_id?: number | null;
  wheelchair_boarding?: number;
  is_active?: boolean;
}

export interface PaginatedStops {
  items: Stop[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

export interface NearbyParams {
  latitude: number;
  longitude: number;
  radius_meters?: number;
  limit?: number;
}
