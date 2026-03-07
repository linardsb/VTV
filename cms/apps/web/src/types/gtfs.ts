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

/** EU compliance export metadata from /api/v1/compliance/status */
export interface ExportMetadata {
  format: "NeTEx" | "SIRI-VM" | "SIRI-SM";
  version: string;
  codespace: string;
  generated_at: string;
  entity_counts: {
    agencies: number;
    routes: number;
    trips: number;
    stops: number;
  };
}
