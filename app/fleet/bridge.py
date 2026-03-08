# pyright: reportUnknownMemberType=false, reportMissingTypeStubs=false
"""Traccar webhook bridge - receives, normalizes, and stores hardware GPS telemetry.

Processes Traccar event forwarding webhooks, converts to VTV position format,
and writes to Redis cache + TimescaleDB hypertable + Redis Pub/Sub.
"""

from __future__ import annotations

import datetime
import json
from typing import Any

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.fleet.models import TrackedDevice
from app.fleet.repository import FleetRepository
from app.fleet.schemas import OBDTelemetry, TraccarWebhookPayload
from app.transit.models import VehiclePositionRecord

logger = get_logger(__name__)

# Conversion factor: 1 knot = 1.852 km/h
KNOTS_TO_KMH = 1.852


def parse_obd_attributes(attributes: dict[str, Any]) -> OBDTelemetry:
    """Extract OBD-II parameters from Traccar device attributes.

    Traccar normalizes OBD keys from various device protocols. This function
    maps Traccar's attribute names to VTV's OBDTelemetry schema.

    Args:
        attributes: Traccar's device attributes dict.

    Returns:
        OBDTelemetry with parsed values (None for missing parameters).
    """
    speed_raw = attributes.get("speed")
    rpm_raw = attributes.get("rpm")
    fuel_raw = attributes.get("fuel")
    coolant_raw = attributes.get("coolantTemp")
    odometer_raw = attributes.get("odometer")
    engine_load_raw = attributes.get("engineLoad")
    battery_raw = attributes.get("batteryLevel")

    return OBDTelemetry(
        speed_kmh=float(speed_raw) if speed_raw is not None else None,
        rpm=int(rpm_raw) if rpm_raw is not None else None,
        fuel_level_pct=float(fuel_raw) if fuel_raw is not None else None,
        coolant_temp_c=float(coolant_raw) if coolant_raw is not None else None,
        odometer_km=float(odometer_raw) / 1000.0 if odometer_raw is not None else None,
        engine_load_pct=float(engine_load_raw) if engine_load_raw is not None else None,
        battery_voltage=float(battery_raw) if battery_raw is not None else None,
    )


def normalize_webhook(payload: TraccarWebhookPayload, device: TrackedDevice) -> dict[str, Any]:
    """Convert Traccar webhook payload to VTV vehicle position format.

    Maps Traccar fields to match the existing GTFS-RT position structure,
    enabling unified map rendering and storage in the shared hypertable.

    Args:
        payload: Traccar webhook event data.
        device: The VTV tracked device record.

    Returns:
        Dict ready for Redis SET and TimescaleDB insert.
    """
    # Speed: Traccar sends knots, VTV uses km/h
    speed_kmh: float | None = None
    if payload.speed is not None:
        speed_kmh = payload.speed * KNOTS_TO_KMH

    obd = parse_obd_attributes(payload.attributes)

    fleet_number = ""
    if device.vehicle_id is not None:
        # vehicle_id FK links to vehicles table; fleet_number is on the vehicle
        # We use vehicle_id as string for the position record
        fleet_number = str(device.vehicle_id)

    return {
        "feed_id": "fleet",
        "vehicle_id": fleet_number,
        "route_id": "",
        "route_short_name": "",
        "trip_id": None,
        "latitude": payload.latitude,
        "longitude": payload.longitude,
        "bearing": payload.course,
        "speed_kmh": speed_kmh,
        "delay_seconds": 0,
        "current_status": "IN_TRANSIT_TO",
        "source": "hardware",
        "obd_data": obd.model_dump(exclude_none=True) or None,
        "recorded_at": payload.fixTime,
        "device_imei": device.imei,
    }


class TraccarBridge:
    """Processes Traccar webhook events and stores normalized telemetry."""

    def __init__(self, db: AsyncSession) -> None:
        """Initialize with database session.

        Args:
            db: SQLAlchemy async session.
        """
        self.db = db
        self.fleet_repo = FleetRepository(db)

    async def process_webhook(self, payload: TraccarWebhookPayload, redis_client: Redis) -> bool:
        """Process a Traccar webhook event.

        Looks up the device, normalizes the position data, writes to Redis cache
        and TimescaleDB, and publishes to Pub/Sub for WebSocket push.

        Args:
            payload: Traccar webhook event data.
            redis_client: Redis client for cache writes and Pub/Sub.

        Returns:
            True if position was stored, False if device unknown or unlinked.
        """
        logger.info("fleet.bridge.webhook_received", traccar_device_id=payload.deviceId)

        # Look up device by Traccar's internal ID
        device = await self.fleet_repo.get_by_traccar_id(payload.deviceId)
        if not device:
            logger.warning("fleet.bridge.device_unknown", traccar_device_id=payload.deviceId)
            return False

        if device.vehicle_id is None:
            logger.warning(
                "fleet.bridge.device_unlinked",
                imei=device.imei,
                traccar_device_id=payload.deviceId,
            )
            return False

        # Normalize payload to VTV position format
        position_data = normalize_webhook(payload, device)

        try:
            # Write to Redis cache (same key pattern as transit poller)
            redis_key = f"vehicle:{position_data['feed_id']}:{position_data['vehicle_id']}"
            redis_value = json.dumps(position_data)
            pipe = redis_client.pipeline()
            pipe.set(redis_key, redis_value, ex=120)
            pipe.publish("vehicle_positions", redis_value)
            await pipe.execute()

            # Write to TimescaleDB
            recorded_at = datetime.datetime.fromisoformat(payload.fixTime)
            record = VehiclePositionRecord(
                recorded_at=recorded_at,
                feed_id=position_data["feed_id"],
                vehicle_id=position_data["vehicle_id"],
                route_id=position_data["route_id"],
                route_short_name=position_data["route_short_name"],
                trip_id=position_data["trip_id"],
                latitude=position_data["latitude"],
                longitude=position_data["longitude"],
                bearing=position_data["bearing"],
                speed_kmh=position_data["speed_kmh"],
                delay_seconds=position_data["delay_seconds"],
                current_status=position_data["current_status"],
                source="hardware",
                obd_data=position_data["obd_data"],
            )
            self.db.add(record)

            # Update device last_seen_at
            await self.fleet_repo.update_last_seen(device, recorded_at)

            logger.info(
                "fleet.bridge.position_stored",
                vehicle_id=position_data["vehicle_id"],
                lat=position_data["latitude"],
                lon=position_data["longitude"],
            )
            return True

        except Exception:
            logger.exception("fleet.bridge.storage_failed")
            return False
