"""SQL queries for e-ticket ↔ GTFS-RT load correlation (ML-3.1).

Spatial-temporal join: e-ticket validations → vehicle positions → nearest stop.
Uses LATERAL JOINs for optimal TimescaleDB + PostGIS performance.

Note: The time window INTERVAL uses Python f-string formatting because
PostgreSQL INTERVAL does not accept parameterized placeholders. The value
comes from settings.ml_load_time_window_seconds (integer, not user input).
"""

from __future__ import annotations


def correlate_taps_sql(window_s: int) -> str:
    """Build the spatial-temporal correlation query.

    Args:
        window_s: Time window in seconds for position matching.

    Returns:
        SQL string with :from_ts, :to_ts, :distance_m parameters.
    """
    # window_s is an integer from settings, not user input - safe to interpolate
    return f"""
    SELECT
        ev.id AS eticket_id,
        ev.vehicle_number,
        ev.validated_at,
        ev.route_code,
        ev.transport_type,
        vp.trip_id AS gtfs_trip_id,
        vp.latitude AS vp_lat,
        vp.longitude AS vp_lon,
        vp.recorded_at AS position_at,
        s.id AS stop_id,
        s.gtfs_stop_id,
        st_sub.stop_sequence
    FROM eticket_validations ev
    JOIN LATERAL (
        SELECT vp2.trip_id, vp2.latitude, vp2.longitude, vp2.recorded_at
        FROM vehicle_positions vp2
        WHERE vp2.vehicle_id = ev.vehicle_number
          AND vp2.recorded_at BETWEEN ev.validated_at - INTERVAL '{window_s} seconds'
                                   AND ev.validated_at + INTERVAL '{window_s} seconds'
        ORDER BY ABS(EXTRACT(EPOCH FROM (vp2.recorded_at - ev.validated_at)))
        LIMIT 1
    ) vp ON true
    JOIN LATERAL (
        SELECT s2.id, s2.gtfs_stop_id
        FROM stops s2
        WHERE s2.geom IS NOT NULL
          AND ST_DWithin(
              s2.geom,
              ST_SetSRID(ST_MakePoint(vp.longitude, vp.latitude), 4326)::geography,
              :distance_m
          )
        ORDER BY ST_Distance(
            s2.geom,
            ST_SetSRID(ST_MakePoint(vp.longitude, vp.latitude), 4326)::geography
        )
        LIMIT 1
    ) s ON true
    LEFT JOIN LATERAL (
        SELECT st2.stop_sequence
        FROM stop_times st2
        JOIN trips t ON st2.trip_id = t.id
        WHERE t.gtfs_trip_id = vp.trip_id
          AND st2.stop_id = s.id
        LIMIT 1
    ) st_sub ON true
    WHERE ev.validated_at >= :from_ts
      AND ev.validated_at < :to_ts
    """


TOTAL_TAPS_SQL = """
SELECT COUNT(*) AS total
FROM eticket_validations
WHERE validated_at >= :from_ts
  AND validated_at < :to_ts
"""


def uncorrelated_count_sql(window_s: int) -> str:
    """Build the uncorrelated count query with the time window.

    Args:
        window_s: Time window in seconds for position matching.

    Returns:
        SQL string with :from_ts, :to_ts parameters.
    """
    # window_s is an integer from settings, not user input - safe to interpolate
    return f"""
    SELECT COUNT(*) AS uncorrelated
    FROM eticket_validations ev
    WHERE ev.validated_at >= :from_ts
      AND ev.validated_at < :to_ts
      AND NOT EXISTS (
          SELECT 1
          FROM vehicle_positions vp
          WHERE vp.vehicle_id = ev.vehicle_number
            AND vp.recorded_at BETWEEN ev.validated_at - INTERVAL '{window_s} seconds'
                                    AND ev.validated_at + INTERVAL '{window_s} seconds'
      )
    """
