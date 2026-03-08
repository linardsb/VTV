# pyright: reportUnknownMemberType=false
"""Unit tests for TraccarBridge and telemetry processing."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.fleet.bridge import KNOTS_TO_KMH, TraccarBridge, normalize_webhook, parse_obd_attributes
from app.fleet.models import TrackedDevice
from app.fleet.schemas import TraccarWebhookPayload


class TestParseOBDAttributes:
    """Tests for parse_obd_attributes function."""

    def test_parse_obd_attributes_full(self) -> None:
        """All OBD fields present with correct conversions."""
        attributes = {
            "speed": 45.0,
            "rpm": 2500,
            "fuel": 65.0,
            "coolantTemp": 90.0,
            "odometer": 150000000,  # meters
            "engineLoad": 40.0,
            "batteryLevel": 12.6,
        }

        result = parse_obd_attributes(attributes)

        assert result.speed_kmh == 45.0
        assert result.rpm == 2500
        assert result.fuel_level_pct == 65.0
        assert result.coolant_temp_c == 90.0
        assert result.odometer_km == 150000.0  # meters -> km
        assert result.engine_load_pct == 40.0
        assert result.battery_voltage == 12.6

    def test_parse_obd_attributes_partial(self) -> None:
        """Some fields missing return None."""
        attributes = {"speed": 30.0, "rpm": 1500}

        result = parse_obd_attributes(attributes)

        assert result.speed_kmh == 30.0
        assert result.rpm == 1500
        assert result.fuel_level_pct is None
        assert result.coolant_temp_c is None
        assert result.odometer_km is None

    def test_parse_obd_attributes_empty(self) -> None:
        """Empty dict returns all None values."""
        result = parse_obd_attributes({})

        assert result.speed_kmh is None
        assert result.rpm is None
        assert result.fuel_level_pct is None
        assert result.coolant_temp_c is None
        assert result.odometer_km is None
        assert result.engine_load_pct is None
        assert result.battery_voltage is None


class TestNormalizeWebhook:
    """Tests for normalize_webhook function."""

    def test_normalize_webhook_speed_conversion(
        self, sample_webhook_payload: TraccarWebhookPayload, sample_tracked_device: TrackedDevice
    ) -> None:
        """Converts speed from knots to km/h correctly."""
        sample_webhook_payload.speed = 10.0  # knots

        result = normalize_webhook(sample_webhook_payload, sample_tracked_device)

        expected_speed = 10.0 * KNOTS_TO_KMH
        assert result["speed_kmh"] == pytest.approx(expected_speed, rel=1e-3)

    def test_normalize_webhook_odometer_conversion(
        self, sample_webhook_payload: TraccarWebhookPayload, sample_tracked_device: TrackedDevice
    ) -> None:
        """OBD odometer converted from meters to km."""
        result = normalize_webhook(sample_webhook_payload, sample_tracked_device)

        assert result["obd_data"] is not None
        assert result["obd_data"]["odometer_km"] == 150000.0

    def test_normalize_webhook_source_and_feed(
        self, sample_webhook_payload: TraccarWebhookPayload, sample_tracked_device: TrackedDevice
    ) -> None:
        """Sets source to hardware and feed_id to fleet."""
        result = normalize_webhook(sample_webhook_payload, sample_tracked_device)

        assert result["source"] == "hardware"
        assert result["feed_id"] == "fleet"


class TestProcessWebhook:
    """Tests for TraccarBridge.process_webhook."""

    async def test_process_webhook_unknown_device(
        self, mock_db: AsyncMock, sample_webhook_payload: TraccarWebhookPayload
    ) -> None:
        """Returns False when device is not found by traccar_device_id."""
        bridge = TraccarBridge(mock_db)
        redis_client = MagicMock()

        with patch.object(bridge.fleet_repo, "get_by_traccar_id", return_value=None):
            result = await bridge.process_webhook(sample_webhook_payload, redis_client)

        assert result is False

    async def test_process_webhook_unlinked_device(
        self,
        mock_db: AsyncMock,
        sample_webhook_payload: TraccarWebhookPayload,
        sample_tracked_device: TrackedDevice,
    ) -> None:
        """Returns False when device has no vehicle linked."""
        sample_tracked_device.vehicle_id = None
        bridge = TraccarBridge(mock_db)
        redis_client = MagicMock()

        with patch.object(
            bridge.fleet_repo, "get_by_traccar_id", return_value=sample_tracked_device
        ):
            result = await bridge.process_webhook(sample_webhook_payload, redis_client)

        assert result is False

    async def test_process_webhook_success(
        self,
        mock_db: AsyncMock,
        sample_webhook_payload: TraccarWebhookPayload,
        sample_tracked_device: TrackedDevice,
    ) -> None:
        """Full pipeline: device lookup, normalization, Redis + DB storage."""
        bridge = TraccarBridge(mock_db)

        # Redis mock: pipeline is sync, execute() is async (rule 35)
        mock_pipe = MagicMock()
        mock_pipe.execute = AsyncMock()
        mock_redis = MagicMock()
        mock_redis.pipeline.return_value = mock_pipe

        with (
            patch.object(
                bridge.fleet_repo, "get_by_traccar_id", return_value=sample_tracked_device
            ),
            patch.object(bridge.fleet_repo, "update_last_seen", return_value=None),
        ):
            result = await bridge.process_webhook(sample_webhook_payload, mock_redis)

        assert result is True
        # Verify Redis pipeline was used
        mock_redis.pipeline.assert_called_once()
        mock_pipe.set.assert_called_once()
        mock_pipe.publish.assert_called_once()
        mock_pipe.execute.assert_awaited_once()
        # Verify DB record was added
        mock_db.add.assert_called_once()
