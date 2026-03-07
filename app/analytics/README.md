# Analytics

Read-only aggregation layer providing dashboard summary endpoints for the CMS frontend. Queries existing feature tables (vehicles, drivers) and live GTFS-RT feeds without creating new database tables.

## Key Flows

### Fleet Summary

1. Group active vehicles by `vehicle_type` and `status`
2. Count maintenance due within 7 days, registration expiring within 30 days
3. Count unassigned active vehicles, compute average mileage
4. Return `FleetSummaryResponse` with `by_type` breakdown

### Driver Summary

1. Group active drivers by `default_shift` and `status`
2. Count license expiring within 30 days, medical cert expiring within 30 days
3. Return `DriverSummaryResponse` with `by_shift` breakdown

### On-Time Performance

1. Validate date parameter, fetch GTFS-RT trip updates via httpx
2. Load static GTFS cache, compute active service IDs for the date
3. For each route with real-time data, compute adherence using `_compute_route_adherence`
4. Sort by worst on-time percentage, cap at 25 routes
5. Compute network averages, return `OnTimePerformanceResponse`

### Overview (Combined)

1. Call all three methods above
2. On-time performance degrades gracefully — if transit data fails, returns empty on-time section
3. Fleet and driver summaries always succeed independently

## Business Rules

1. All endpoints are read-only — no database writes
2. On-time endpoint has stricter rate limit (10/min) due to external GTFS-RT fetches
3. Overview endpoint never fails — transit errors produce a fallback empty on-time response
4. Fleet/driver counts only include `is_active=True` records
5. On-time network report caps at 25 routes (sorted by worst performance)

## Integration Points

- **vehicles**: Read-only queries on `Vehicle` model (status, type, mileage, maintenance dates, registration expiry)
- **drivers**: Read-only queries on `Driver` model (shift, status, license/medical expiry)
- **core/agents/tools/transit**: Reuses `_compute_route_adherence`, `GTFSRealtimeClient`, `get_static_cache`, `validate_date`, `classify_service_type`, `gtfs_time_to_minutes`

## API Endpoints

| Method | Path | Rate Limit | Description |
|--------|------|------------|-------------|
| GET | `/api/v1/analytics/fleet-summary` | 30/min | Fleet status breakdown with alerts |
| GET | `/api/v1/analytics/driver-summary` | 30/min | Driver coverage breakdown with expiry alerts |
| GET | `/api/v1/analytics/on-time-performance` | 10/min | Route adherence from live GTFS-RT data |
| GET | `/api/v1/analytics/overview` | 10/min | Combined summary (graceful degradation) |

### On-Time Performance Query Parameters

| Param | Type | Description |
|-------|------|-------------|
| `route_id` | `str?` | GTFS route ID for single-route analysis |
| `date` | `str?` | Service date (YYYY-MM-DD), defaults to today |
| `time_from` | `str?` | Analysis window start (HH:MM) |
| `time_until` | `str?` | Analysis window end (HH:MM) |
