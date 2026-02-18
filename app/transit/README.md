# Transit REST API

Real-time vehicle position endpoint for the CMS frontend map. Bridges the existing GTFS-RT client infrastructure into a REST-friendly JSON API optimized for frontend polling.

## Key Flows

### Get Vehicle Positions

1. Frontend polls `GET /api/v1/transit/vehicles` every 10 seconds
2. Service fetches GTFS-RT vehicle positions via `GTFSRealtimeClient` (10s cache)
3. Service fetches GTFS-RT trip updates for delay data
4. Service loads `GTFSStaticCache` for route/stop name resolution
5. Vehicles enriched with: route short name, delay seconds, next stop name, speed in km/h
6. Optional `?route_id=X` filter applied
7. Response returned as `VehiclePositionsResponse`

### Error Handling

1. If GTFS-RT feeds are unavailable, `TransitDataError` propagates
2. Global exception handler maps `TransitDataError` to HTTP 503
3. Frontend receives 503 and retains last successful data

## Business Rules

1. Route ID resolved from vehicle data first, then trip-to-route lookup via static cache
2. Delay computed from next stop time update relative to current stop sequence
3. Speed converted from GTFS-RT m/s to km/h (rounded to 1 decimal)
4. Timestamps converted from POSIX to ISO 8601 UTC
5. No authentication required (GTFS-RT data is public)

## Integration Points

- **`app.core.agents.tools.transit.client`**: Reuses `GTFSRealtimeClient` for GTFS-RT feed parsing (vehicle positions + trip updates)
- **`app.core.agents.tools.transit.static_cache`**: Reuses `GTFSStaticCache` singleton for route/stop/trip name resolution
- **`app.core.config`**: Uses `Settings` for feed URLs and cache TTL
- **`app.core.agents.exceptions`**: Uses `TransitDataError` for feed failure propagation (HTTP 503)
- **CMS Frontend**: `cms/apps/web/src/hooks/use-vehicle-positions.ts` polls this endpoint every 10s

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v1/transit/vehicles` | Real-time vehicle positions (optional `?route_id=X` filter) |

### Response Schema

```json
{
  "count": 42,
  "vehicles": [
    {
      "vehicle_id": "4521",
      "route_id": "22",
      "route_short_name": "22",
      "latitude": 56.9496,
      "longitude": 24.1052,
      "bearing": 180.0,
      "speed_kmh": 36.0,
      "delay_seconds": 120,
      "current_status": "IN_TRANSIT_TO",
      "next_stop_name": "Centraltirgus",
      "current_stop_name": "Stacija",
      "timestamp": "2024-01-15T10:30:00+00:00"
    }
  ],
  "fetched_at": "2024-01-15T10:30:05+00:00"
}
```
