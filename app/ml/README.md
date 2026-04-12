# ML Pipeline

Machine learning pipeline for transit operations. No REST endpoints — all computation runs as background tasks or CLI tools. Integrates with the alerts system for anomaly notifications.

## Sub-packages

### `app/ml/features/` — ETA Feature Engineering (ML-2.1)

Deterministic feature extraction pipeline joining `vehicle_positions` (TimescaleDB) with `gtfs_stop_times`, `weather_observations`, and `traffic_counts` to produce an 18-field training matrix. One row per `(trip_id, stop_sequence)`.

- **Online:** `extract_features(db, trip_id, stop_sequence, observed_at) -> ETAFeatures`
- **Offline:** `extract_features_batch(db, from_ts, to_ts) -> pd.DataFrame`
- **CLI:** `python -m app.ml.features --from 2026-03-01 --to 2026-03-31 --out features.parquet`
- **Validation:** Pandera schema enforcement via `--validate` flag

### `app/ml/anomaly/` — Anomaly Detection (ML-4)

Three real-time anomaly detectors running as background evaluators on a 60s cycle. Alerts created via `AlertInstanceRepository` with Redis-based cooldown deduplication (15 min per vehicle per alert type).

| Detector | File | Alert Type | Trigger |
|----------|------|------------|---------|
| **Off-Route** | `off_route.py` | `off_route` | Vehicle outside PostGIS route corridor for 3+ consecutive checks |
| **Stuck Vehicle** | `stuck.py` | `stuck_vehicle` | Vehicle moved < 20m in 10 min during active trip |
| **GPS Gap** | `gps_gap.py` | `gps_gap` | No position updates for 5+ min during active trip |
| **Feed Outage** | `gps_gap.py` | `feed_outage` | >= 50% of feed vehicles gap simultaneously |

**Orchestrator:** `evaluator.py` — background loop running stuck + GPS gap detectors, persisting alerts with dedup via `find_active_duplicate()`. Off-route has its own evaluator loop.

**Exclusions (stuck detector):**
- Vehicles at terminal stops (last `stop_sequence` of trip)
- Vehicles at scheduled layovers (within `arrival_time`/`departure_time` window)

## Configuration

All settings in `app/core/config.py`:

| Setting | Default | Description |
|---------|---------|-------------|
| `ml_anomaly_evaluator_enabled` | `true` | Enable/disable stuck + GPS gap evaluator |
| `ml_anomaly_check_interval_seconds` | `60` | Seconds between evaluation cycles |
| `ml_stuck_distance_threshold_m` | `20.0` | Movement threshold in meters |
| `ml_stuck_time_window_minutes` | `10` | Time window for stuck detection |
| `ml_gps_gap_threshold_minutes` | `5` | No-update threshold for gap detection |
| `ml_gps_gap_feed_outage_pct` | `50` | % of feed vehicles gapping to trigger feed outage |
| `ml_anomaly_cooldown_seconds` | `900` | Cooldown per vehicle per alert type (15 min) |

## Integration Points

- **Alerts:** Creates `AlertInstanceCreate` objects via `app.alerts.repository.AlertInstanceRepository`
- **Transit:** Queries `vehicle_positions` TimescaleDB hypertable for position data
- **Schedules:** Cross-references `stop_times` and `trips` tables for layover exclusion
- **Redis:** Cooldown keys (`ml:stuck:{vehicle_id}`, `ml:gps_gap:{vehicle_id}`, `ml:feed_outage:{feed_id}`)
- **Metrics:** `record_poller_tick("anomaly_evaluator")` for Prometheus liveness gauge
- **Lifespan:** `start_anomaly_evaluator()` / `stop_anomaly_evaluator()` registered via `ShutdownCoordinator`

## Tests

61 tests across 6 test files (features: 26, anomaly: 35). All unit tests — no integration tests required.
