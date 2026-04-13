# Analytics

Read-only aggregation layer providing dashboard summary endpoints for the CMS frontend. Queries existing feature tables (vehicles, drivers) and live GTFS-RT feeds. Includes daily schedule adherence monitoring with DB storage, threshold alerting, and Slack/email publish (ML-5.2).

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
2. On-time performance degrades gracefully -- if transit data fails, returns empty on-time section
3. Fleet and driver summaries always succeed independently

### Daily Adherence Report (ML-5.2)

1. Load GTFS static data via DB-backed `get_static_store`, get active service IDs for target date
2. Fetch real-time trip updates across all configured transit feeds
3. For each route with active trips, compute adherence via `_compute_route_adherence`
4. Aggregate: overall on-time %, per-route breakdowns (JSONB), per-hour breakdowns (JSONB)
5. Upsert `DailyAdherenceReport` row (one report per calendar date)
6. If overall adherence < threshold (default 85%), create high-severity `schedule_adherence` alert
7. Publish summary to Slack webhook and/or email (fail-open: errors logged, never raised)
8. Record `daily_adherence` poller tick for Prometheus liveness monitoring

## Database Schema

Table: `daily_adherence_reports`

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | Integer | PK, autoincrement | Primary key |
| `report_date` | Date | Unique, not null, indexed | One report per calendar date |
| `overall_pct` | Float | Not null | Fleet-wide on-time percentage |
| `total_trips` | Integer | Not null | Total tracked trips |
| `on_time_trips` | Integer | Not null | Trips within +/- 300s threshold |
| `late_trips` | Integer | Not null | Trips > 300s late |
| `early_trips` | Integer | Not null | Trips > 300s early |
| `per_route_json` | JSONB | Not null | Per-route adherence breakdowns |
| `per_hour_json` | JSONB | Not null | Per-hour adherence breakdowns |
| `anomaly_count` | Integer | Not null, default 0 | Anomalies detected |
| `alert_triggered` | Boolean | Not null, default false | Whether threshold alert fired |
| `created_at` | DateTime(tz) | Not null | Auto-set on create |
| `updated_at` | DateTime(tz) | Not null | Auto-set on update |

## Business Rules

1. All summary endpoints are read-only -- no database writes (fleet, driver, on-time, overview)
2. On-time endpoint has stricter rate limit (5/hour sub-bucket) due to external GTFS-RT fetches
3. Overview endpoint never fails -- transit errors produce a fallback empty on-time response
4. Fleet/driver counts only include `is_active=True` records
5. On-time network report caps at 25 routes (sorted by worst performance)
6. Daily adherence: one report per calendar date (upsert on `report_date`)
7. Threshold alert fires when `overall_pct < analytics_adherence_threshold_pct` (default 85%)
8. Publish (Slack/email) is fail-open -- errors are logged but never block report creation
9. Daily task runs at `analytics_adherence_cron_hour` (default 06:00 UTC); defers to arq when `background_queue_enabled=True`
10. Date range query capped at 90 days maximum

## Configuration (ML-5.2)

| Setting | Type | Default | Description |
|---------|------|---------|-------------|
| `analytics_adherence_enabled` | bool | `True` | Enable/disable background task |
| `analytics_adherence_threshold_pct` | float | `85.0` | Alert threshold (%) |
| `analytics_adherence_cron_hour` | int | `6` | Daily run hour (UTC) |
| `analytics_adherence_slack_webhook` | str? | `None` | Slack webhook URL |
| `analytics_adherence_smtp_enabled` | bool | `False` | Enable email publish |
| `analytics_adherence_smtp_host` | str | `localhost` | SMTP server host |
| `analytics_adherence_smtp_port` | int | `587` | SMTP server port |
| `analytics_adherence_smtp_from` | str | `vtv@example.com` | Sender address |
| `analytics_adherence_smtp_to` | str | `""` | Recipients (comma-separated) |

## Integration Points

- **vehicles**: Read-only queries on `Vehicle` model (status, type, mileage, maintenance dates, registration expiry)
- **drivers**: Read-only queries on `Driver` model (shift, status, license/medical expiry)
- **core/agents/tools/transit**: Reuses `_compute_route_adherence`, `GTFSRealtimeClient`, `get_static_store`, `validate_date`, `classify_service_type`, `gtfs_time_to_minutes`
- **alerts**: Creates `schedule_adherence` alerts via `AlertService.create_alert()` when adherence drops below threshold
- **core/jobs**: `run_daily_adherence` arq cron job for durable execution when queue is enabled
- **core/config**: 10 settings for threshold, Slack webhook, SMTP publish
- **core/metrics**: `record_poller_tick("daily_adherence")` for Prometheus liveness

## API Endpoints

| Method | Path | Rate Limit | Description |
|--------|------|------------|-------------|
| GET | `/api/v1/analytics/fleet-summary` | 30/min | Fleet status breakdown with alerts |
| GET | `/api/v1/analytics/driver-summary` | 30/min | Driver coverage breakdown with expiry alerts |
| GET | `/api/v1/analytics/on-time-performance` | 5/hour | Route adherence from live GTFS-RT data |
| GET | `/api/v1/analytics/overview` | 10/min | Combined summary (graceful degradation) |
| GET | `/api/v1/analytics/adherence/daily` | 30/min | Stored daily adherence reports (date range) |

### Daily Adherence Query Parameters

| Param | Type | Required | Description |
|-------|------|----------|-------------|
| `date_from` | `str` | Yes | Start date (YYYY-MM-DD) |
| `date_to` | `str` | Yes | End date (YYYY-MM-DD), max 90 days from `date_from` |
