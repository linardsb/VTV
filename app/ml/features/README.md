# ML Feature Engineering (ML-2.1)

Deterministic ETA feature extraction pipeline joining vehicle_positions (TimescaleDB) with GTFS stop_times, weather observations, and traffic data to produce a training matrix. One row per (trip_id, stop_sequence) with 18 features (8 categorical, 10 numeric).

## Key Flows

### Online Feature Extraction

1. Receive (trip_id, stop_sequence, observed_at) from inference service
2. Query trip metadata (route_type, direction, operator) via TRIP_METADATA_SQL
3. Look up stop location, arrival time, max stop_sequence
4. Query weather, traffic, accident data with time/proximity windows
5. Check holiday status via calendar_dates
6. Return frozen `ETAFeatures` dataclass with safe defaults for any missing data

### Batch Feature Extraction

1. Accept (from_ts, to_ts) date range
2. Execute single BATCH_FEATURES_SQL joining stop_times + trips + routes + agencies + stops + vehicle_positions via LATERAL join
3. Enrich each row with weather, traffic, accident lookups
4. Return pandas DataFrame with 20 columns (18 features + trip_id + stop_sequence)

### CLI Extraction

1. Parse `--from`, `--to`, `--out`, `--dry-run`, `--validate` args
2. Open standalone DB session via `get_db_context()`
3. Call `extract_features_batch()`
4. Optionally validate with Pandera schema
5. Write to Parquet or log summary

## Feature Schema

| # | Feature | Type | Source |
|---|---------|------|--------|
| 1 | `day_of_week` | int (0-6) | vehicle_positions.recorded_at |
| 2 | `month` | int (1-12) | vehicle_positions.recorded_at |
| 3 | `is_school_day` | bool | Calendar + weekday + not summer |
| 4 | `is_holiday` | bool | calendar_dates exception_type=2 |
| 5 | `weather_bucket` | Literal["clear","rain","snow","fog","other"] | weather_observations |
| 6 | `route_type` | int (0-12) | routes.route_type |
| 7 | `direction` | int (0/1) | trips.direction_id |
| 8 | `operator` | str | agencies.agency_name |
| 9 | `time_of_day_hour` | float (0-48) | stop_times.arrival_time |
| 10 | `scheduled_headway_s` | float | stop_times gap to prev trip |
| 11 | `historical_avg_delay_at_stop_s` | float | AVG(delay_seconds) by route/stop/hour/dow |
| 12 | `prev_stop_actual_delay_s` | float | Delay at stop_sequence-1 |
| 13 | `trip_elapsed_pct` | float (0-1) | stop_sequence / max_sequence |
| 14 | `temp_c` | float | weather_observations.temp_c |
| 15 | `wind_mps` | float | weather_observations.wind_mps |
| 16 | `precip_mm_last_hr` | float | weather_observations.precip_mm |
| 17 | `traffic_count_rolling_7d` | float | traffic_counts 7-day avg |
| 18 | `accident_count_within_500m` | int | traffic_accidents via ST_DWithin |

## Business Rules

1. Missing weather/traffic data uses safe defaults (0.0) — never raises
2. GTFS times support >24:00:00 for overnight trips (parsed to fractional hours)
3. is_school_day approximation: weekday + not holiday + September-June
4. Weather classification priority: snow > fog > rain > other > clear
5. All SQL uses parameterized placeholders (no string interpolation)

## Integration Points

- **transit**: Reads vehicle_positions, weather_observations, traffic_counts, traffic_accidents
- **schedules**: Reads trips, stop_times, routes, agencies, calendars, calendar_dates
- **stops**: Reads stops (location for proximity queries)

## CLI Usage

```bash
python -m app.ml.features --from 2026-03-01 --to 2026-03-31 --out /tmp/features.parquet
python -m app.ml.features --from 2026-03-01 --to 2026-03-31 --dry-run
python -m app.ml.features --from 2026-03-01 --to 2026-03-31 --validate
```

## Dependencies

Runtime: pandas, pandera, pyarrow. Dev: pandas-stubs.
