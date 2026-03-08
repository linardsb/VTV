# pyright: reportCallIssue=false
"""Unit tests for FleetService."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.fleet.exceptions import (
    DeviceAlreadyExistsError,
    DeviceNotFoundError,
    DeviceValidationError,
)
from app.fleet.models import TrackedDevice
from app.fleet.schemas import TrackedDeviceCreate, TrackedDeviceUpdate
from app.fleet.service import FleetService
from app.shared.schemas import PaginationParams


@pytest.fixture
def service(mock_db: AsyncMock) -> FleetService:
    """Create FleetService with mocked dependencies."""
    return FleetService(mock_db)


class TestCreateDevice:
    """Tests for FleetService.create_device."""

    async def test_create_device_success(self, service: FleetService) -> None:
        """Creates device successfully when IMEI is unique."""
        data = TrackedDeviceCreate(imei="123456789012345")

        mock_device = MagicMock(spec=TrackedDevice)
        mock_device.id = 1
        mock_device.imei = "123456789012345"
        mock_device.device_name = None
        mock_device.sim_number = None
        mock_device.protocol_type = "teltonika"
        mock_device.firmware_version = None
        mock_device.vehicle_id = None
        mock_device.status = "active"
        mock_device.last_seen_at = None
        mock_device.notes = None
        mock_device.created_at = MagicMock()
        mock_device.updated_at = MagicMock()

        with (
            patch.object(service.fleet_repo, "get_by_imei", return_value=None),
            patch.object(service.fleet_repo, "create", return_value=mock_device),
        ):
            result = await service.create_device(data)

        assert result.id == 1
        assert result.imei == "123456789012345"

    async def test_create_device_duplicate_imei(self, service: FleetService) -> None:
        """Raises DeviceAlreadyExistsError when IMEI is duplicated."""
        data = TrackedDeviceCreate(imei="123456789012345")
        existing = MagicMock(spec=TrackedDevice)

        with (
            patch.object(service.fleet_repo, "get_by_imei", return_value=existing),
            pytest.raises(DeviceAlreadyExistsError),
        ):
            await service.create_device(data)

    async def test_create_device_invalid_vehicle(self, service: FleetService) -> None:
        """Raises DeviceValidationError when vehicle_id does not exist."""
        data = TrackedDeviceCreate(imei="123456789012345", vehicle_id=999)

        with (
            patch.object(service.fleet_repo, "get_by_imei", return_value=None),
            patch.object(service.vehicle_repo, "get", return_value=None),
            pytest.raises(DeviceValidationError, match="Vehicle with id 999 not found"),
        ):
            await service.create_device(data)

    async def test_create_device_vehicle_already_linked(self, service: FleetService) -> None:
        """Raises DeviceValidationError when vehicle already linked to another device."""
        data = TrackedDeviceCreate(imei="123456789012345", vehicle_id=10)
        existing_device = MagicMock(spec=TrackedDevice)
        existing_device.id = 99

        with (
            patch.object(service.fleet_repo, "get_by_imei", return_value=None),
            patch.object(service.vehicle_repo, "get", return_value=MagicMock()),
            patch.object(service.fleet_repo, "get_by_vehicle_id", return_value=existing_device),
            pytest.raises(DeviceValidationError, match="already linked"),
        ):
            await service.create_device(data)


class TestGetDevice:
    """Tests for FleetService.get_device."""

    async def test_get_device_not_found(self, service: FleetService) -> None:
        """Raises DeviceNotFoundError when device does not exist."""
        with (
            patch.object(service.fleet_repo, "get", return_value=None),
            pytest.raises(DeviceNotFoundError),
        ):
            await service.get_device(999)


class TestUpdateDevice:
    """Tests for FleetService.update_device."""

    async def test_update_device_success(self, service: FleetService) -> None:
        """Updates device fields successfully."""
        mock_device = MagicMock(spec=TrackedDevice)
        mock_device.id = 1
        mock_device.imei = "123456789012345"
        mock_device.device_name = "Updated"
        mock_device.sim_number = None
        mock_device.protocol_type = "teltonika"
        mock_device.firmware_version = None
        mock_device.vehicle_id = None
        mock_device.status = "active"
        mock_device.last_seen_at = None
        mock_device.notes = None
        mock_device.created_at = MagicMock()
        mock_device.updated_at = MagicMock()

        data = TrackedDeviceUpdate(device_name="Updated")

        with (
            patch.object(service.fleet_repo, "get", return_value=mock_device),
            patch.object(service.fleet_repo, "update", return_value=mock_device),
        ):
            result = await service.update_device(1, data)

        assert result.device_name == "Updated"


class TestDeleteDevice:
    """Tests for FleetService.delete_device."""

    async def test_delete_device_success(self, service: FleetService) -> None:
        """Deletes device successfully."""
        mock_device = MagicMock(spec=TrackedDevice)

        with (
            patch.object(service.fleet_repo, "get", return_value=mock_device),
            patch.object(service.fleet_repo, "delete", return_value=None),
        ):
            await service.delete_device(1)


class TestListDevices:
    """Tests for FleetService.list_devices."""

    async def test_list_devices_pagination(self, service: FleetService) -> None:
        """Returns PaginatedResponse with correct structure."""
        pagination = PaginationParams(page=1, page_size=10)

        with (
            patch.object(service.fleet_repo, "list", return_value=[]),
            patch.object(service.fleet_repo, "count", return_value=0),
        ):
            result = await service.list_devices(pagination)

        assert result.total == 0
        assert result.page == 1
        assert result.page_size == 10
        assert result.items == []
