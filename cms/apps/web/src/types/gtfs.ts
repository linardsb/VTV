/** GTFS data statistics — aggregate counts from multiple endpoints */
export interface GTFSStats {
  agencies: number;
  routes: number;
  calendars: number;
  trips: number;
  stops: number;
}

/** GTFS-RT feed configuration from /api/v1/transit/feeds */
export interface GTFSFeed {
  feed_id: string;
  operator_name: string;
  enabled: boolean;
  poll_interval_seconds: number;
}
