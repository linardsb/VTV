"""SQL queries for ETA feature extraction (ML-2.1).

All queries use SQLAlchemy text() parameterized placeholders.
No string interpolation - prevents SQL injection.
"""

from __future__ import annotations

# Closest vehicle position to a scheduled stop arrival.
# Joins vehicle_positions (trip_id is String matching trips.gtfs_trip_id)
# with stop_times via trips table.
VEHICLE_DELAY_AT_STOP_SQL = """
SELECT vp.delay_seconds, vp.recorded_at, vp.speed_kmh
FROM vehicle_positions vp
JOIN trips t ON t.gtfs_trip_id = vp.trip_id
WHERE t.id = :trip_id
  AND vp.recorded_at BETWEEN :scheduled_time - INTERVAL '5 minutes'
                         AND :scheduled_time + INTERVAL '10 minutes'
ORDER BY ABS(EXTRACT(EPOCH FROM (vp.recorded_at - :scheduled_time)))
LIMIT 1
"""

# Historical average delay per (route_id, stop_sequence, hour, dow) over lookback.
HISTORICAL_AVG_DELAY_SQL = """
SELECT AVG(vp.delay_seconds)::float AS avg_delay
FROM vehicle_positions vp
JOIN trips t ON t.gtfs_trip_id = vp.trip_id
JOIN stop_times st ON st.trip_id = t.id AND st.stop_sequence = :stop_sequence
WHERE t.route_id = :route_id
  AND EXTRACT(HOUR FROM vp.recorded_at) = :hour_of_day
  AND EXTRACT(DOW FROM vp.recorded_at) = :day_of_week
  AND vp.recorded_at >= :lookback_start
  AND vp.recorded_at < :lookback_end
"""

# Nearest weather observation within +/-30 min of target time.
WEATHER_AT_TIME_SQL = """
SELECT wo.temp_c, wo.wind_mps, wo.precip_mm, wo.phenomena
FROM weather_observations wo
WHERE wo.observed_at BETWEEN :target_time - INTERVAL '30 minutes'
                        AND :target_time + INTERVAL '30 minutes'
ORDER BY ABS(EXTRACT(EPOCH FROM (wo.observed_at - :target_time)))
LIMIT 1
"""

# Rolling 7-day average traffic count at nearest measurement point.
TRAFFIC_ROLLING_7D_SQL = """
SELECT AVG(tc.avg_count_per_day)::float AS rolling_avg
FROM traffic_counts tc
WHERE tc.period_start >= (:target_date - INTERVAL '7 days')::date
  AND tc.period_end <= :target_date
"""

# Count of accidents within 500m in last 30 days (PostGIS ST_DWithin on geography).
ACCIDENT_COUNT_NEARBY_SQL = """
SELECT COUNT(*)::int AS accident_count
FROM traffic_accidents ta
WHERE ST_DWithin(ta.location, ST_MakePoint(:stop_lon, :stop_lat)::geography, 500)
  AND ta.occurred_at >= :target_time - INTERVAL '30 days'
  AND ta.occurred_at < :target_time
"""

# Scheduled headway: gap to previous trip on same route at same stop.
SCHEDULED_HEADWAY_SQL = """
SELECT st2.arrival_time
FROM stop_times st2
JOIN trips t2 ON st2.trip_id = t2.id
WHERE t2.route_id = :route_id
  AND st2.stop_id = :stop_id
  AND st2.stop_sequence = :stop_sequence
  AND st2.arrival_time < :current_arrival_time
ORDER BY st2.arrival_time DESC
LIMIT 1
"""

# Delay at previous stop_sequence for same trip.
PREV_STOP_DELAY_SQL = """
SELECT vp.delay_seconds
FROM vehicle_positions vp
JOIN trips t ON t.gtfs_trip_id = vp.trip_id
JOIN stop_times st ON st.trip_id = t.id AND st.stop_sequence = :prev_stop_sequence
WHERE t.id = :trip_id
  AND vp.recorded_at BETWEEN
    (SELECT (CURRENT_DATE + st2.arrival_time::interval)
     FROM stop_times st2 WHERE st2.trip_id = :trip_id AND st2.stop_sequence = :prev_stop_sequence)
    - INTERVAL '5 minutes'
    AND
    (SELECT (CURRENT_DATE + st2.arrival_time::interval)
     FROM stop_times st2 WHERE st2.trip_id = :trip_id AND st2.stop_sequence = :prev_stop_sequence)
    + INTERVAL '10 minutes'
ORDER BY ABS(EXTRACT(EPOCH FROM (vp.recorded_at -
    (SELECT (CURRENT_DATE + st2.arrival_time::interval)
     FROM stop_times st2 WHERE st2.trip_id = :trip_id AND st2.stop_sequence = :prev_stop_sequence)
)))
LIMIT 1
"""

# Max stop_sequence for a trip (for trip_elapsed_pct).
MAX_STOP_SEQUENCE_SQL = """
SELECT MAX(st.stop_sequence)::int AS max_seq
FROM stop_times st
WHERE st.trip_id = :trip_id
"""

# Trip metadata: route_type, direction_id, agency_name, route_id FK.
TRIP_METADATA_SQL = """
SELECT
    r.route_type,
    t.direction_id,
    a.agency_name AS operator,
    t.route_id AS route_fk,
    t.calendar_id
FROM trips t
JOIN routes r ON t.route_id = r.id
JOIN agencies a ON r.agency_id = a.id
WHERE t.id = :trip_id
"""

# Stop location for proximity queries.
STOP_LOCATION_SQL = """
SELECT s.id AS stop_id, s.stop_lat, s.stop_lon
FROM stops s
JOIN stop_times st ON st.stop_id = s.id
WHERE st.trip_id = :trip_id AND st.stop_sequence = :stop_sequence
"""

# Batch extraction: all vehicle position observations with trip/route/stop context.
# Used by extract_features_batch for the offline training path.
BATCH_FEATURES_SQL = """
SELECT
    t.id AS trip_id,
    st.stop_sequence,
    st.arrival_time,
    st.departure_time,
    st.stop_id,
    vp.delay_seconds,
    vp.recorded_at,
    vp.speed_kmh,
    r.route_type,
    t.direction_id,
    a.agency_name AS operator,
    t.route_id AS route_fk,
    t.calendar_id,
    s.stop_lat,
    s.stop_lon,
    (SELECT MAX(st2.stop_sequence) FROM stop_times st2 WHERE st2.trip_id = t.id) AS max_stop_seq
FROM stop_times st
JOIN trips t ON st.trip_id = t.id
JOIN routes r ON t.route_id = r.id
JOIN agencies a ON r.agency_id = a.id
JOIN stops s ON st.stop_id = s.id
LEFT JOIN LATERAL (
    SELECT vp2.delay_seconds, vp2.recorded_at, vp2.speed_kmh
    FROM vehicle_positions vp2
    WHERE vp2.trip_id = t.gtfs_trip_id
      AND vp2.recorded_at BETWEEN
          (:from_ts::date + st.arrival_time::interval) - INTERVAL '5 minutes'
          AND (:from_ts::date + st.arrival_time::interval) + INTERVAL '10 minutes'
    ORDER BY ABS(EXTRACT(EPOCH FROM (
        vp2.recorded_at - (:from_ts::date + st.arrival_time::interval)
    )))
    LIMIT 1
) vp ON true
WHERE vp.recorded_at IS NOT NULL
  AND vp.recorded_at >= :from_ts
  AND vp.recorded_at < :to_ts
"""
