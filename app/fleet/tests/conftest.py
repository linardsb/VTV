# pyright: reportCallIssue=false
"""Test fixtures for fleet feature tests."""

import datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.fleet.models import TrackedDevice
from app.fleet.schemas import TraccarWebhookPayload, TrackedDeviceCreate


@pytest.fixture
def mock_db() -> AsyncMock:
    """Mock AsyncSession for unit tests."""
    return AsyncMock()


@pytest.fixture
def sample_device_create() -> TrackedDeviceCreate:
    """Sample device creation data."""
    return TrackedDeviceCreate(
        imei="123456789012345",
        device_name="Test Device",
        sim_number="12345678",
        protocol_type="teltonika",
        vehicle_id=None,
    )


@pytest.fixture
def sample_tracked_device() -> TrackedDevice:
    """Sample TrackedDevice model instance."""
    device = MagicMock(spec=TrackedDevice)
    device.id = 1
    device.imei = "123456789012345"
    device.device_name = "Test Device"
    device.sim_number = "12345678"
    device.protocol_type = "teltonika"
    device.firmware_version = None
    device.vehicle_id = 10
    device.status = "active"
    device.last_seen_at = None
    device.traccar_device_id = 42
    device.notes = None
    device.created_at = datetime.datetime(2026, 1, 1, tzinfo=datetime.UTC)
    device.updated_at = datetime.datetime(2026, 1, 1, tzinfo=datetime.UTC)
    return device


@pytest.fixture
def sample_webhook_payload() -> TraccarWebhookPayload:
    """Sample Traccar webhook payload."""
    return TraccarWebhookPayload(
        id=1,
        deviceId=42,
        protocol="teltonika",
        deviceTime="2026-03-08T12:00:00+00:00",
        fixTime="2026-03-08T12:00:00+00:00",
        serverTime="2026-03-08T12:00:01+00:00",
        latitude=56.9496,
        longitude=24.1052,
        altitude=10.0,
        speed=10.0,
        course=180.0,
        accuracy=5.0,
        attributes={
            "speed": 45.0,
            "rpm": 2500,
            "fuel": 65.0,
            "coolantTemp": 90.0,
            "odometer": 150000000,
            "engineLoad": 40.0,
            "batteryLevel": 12.6,
        },
    )
