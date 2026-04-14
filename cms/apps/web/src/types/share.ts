/** Expiry options matching backend Literal[1, 2, 4, 6, 12, 24]. */
export type ShareLinkExpiryHours = 1 | 2 | 4 | 6 | 12 | 24;

/** POST body for creating a share link. */
export interface ShareLinkCreateParams {
  vehicle_id: string;
  route_id?: string | null;
  feed_id?: string; // default "riga"
  expiry_hours?: ShareLinkExpiryHours; // default 1
}

/** Response from POST /api/v1/transit/share (creation). */
export interface ShareLinkResponse {
  id: number;
  token: string;
  share_url: string;
  qr_code_base64: string;
  vehicle_id: string;
  route_id: string | null;
  feed_id: string;
  expires_at: string; // ISO datetime
  created_at: string; // ISO datetime
}

/** Vehicle position data (subset of transit VehiclePosition). */
export interface ShareVehiclePosition {
  vehicle_id: string;
  route_id: string | null;
  route_short_name: string | null;
  route_type: number | null;
  latitude: number;
  longitude: number;
  bearing: number | null;
  speed_kmh: number | null;
  delay_seconds: number | null;
  current_status: string | null;
  next_stop_name: string | null;
  timestamp: string | null;
  feed_id: string;
}

/** Response from GET /api/v1/transit/share/{token} (public resolution). */
export interface ShareLinkData {
  vehicle_id: string;
  route_id: string | null;
  feed_id: string;
  position: ShareVehiclePosition | null;
  expires_at: string; // ISO datetime
  share_link_id: number;
}
