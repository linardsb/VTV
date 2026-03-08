# pyright: reportCallIssue=false, reportUnknownMemberType=false
"""Unit tests for GeofenceService."""

from __future__ import annotations

import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.geofences.exceptions import GeofenceNotFoundError
from app.geofences.models import Geofence
from app.geofences.schemas import GeofenceCreate, GeofenceUpdate
from app.geofences.service import GeofenceService
from app.shared.schemas import PaginationParams


@pytest.fixture
def service(mock_db: AsyncMock) -> GeofenceService:
    """GeofenceService with mocked DB."""
    return GeofenceService(mock_db)


def _make_geofence_mock(geofence_id: int = 1, name: str = "Test Zone") -> MagicMock:
    """Create a mock Geofence model instance."""
    geo = MagicMock(spec=Geofence)
    geo.id = geofence_id
    geo.name = name
    geo.zone_type = "depot"
    geo.color = None
    geo.description = None
    geo.alert_on_enter = True
    geo.alert_on_exit = True
    geo.alert_on_dwell = False
    geo.dwell_threshold_minutes = None
    geo.alert_severity = "medium"
    geo.is_active = True
    geo.created_at = datetime.datetime(2026, 1, 1, tzinfo=datetime.UTC)
    geo.updated_at = datetime.datetime(2026, 1, 1, tzinfo=datetime.UTC)
    return geo


class TestCreateGeofence:
    """Tests for GeofenceService.create_geofence."""

    @pytest.mark.asyncio
    async def test_create_geofence_success(
        self, service: GeofenceService, sample_geofence_create: GeofenceCreate
    ) -> None:
        """Happy path - create geofence with valid coordinates."""
        mock_geo = _make_geofence_mock()
        coords = [
            [24.10, 56.94],
            [24.12, 56.94],
            [24.12, 56.96],
            [24.10, 56.96],
            [24.10, 56.94],
        ]

        with (
            patch.object(service.geofence_repo, "create", new_callable=AsyncMock) as mock_create,
            patch.object(
                service.geofence_repo, "get_coordinates", new_callable=AsyncMock
            ) as mock_coords,
        ):
            mock_create.return_value = mock_geo
            mock_coords.return_value = coords

            result = await service.create_geofence(sample_geofence_create)

        assert result.id == 1
        assert result.name == "Test Zone"
        mock_create.assert_called_once()
        call_args = mock_create.call_args
        wkt_arg = call_args[0][1]
        assert wkt_arg.startswith("POLYGON((")

    @pytest.mark.asyncio
    async def test_create_geofence_with_all_options(self, service: GeofenceService) -> None:
        """Create geofence with all optional fields."""
        data = GeofenceCreate(
            name="Restricted Zone",
            zone_type="restricted",
            color="#FF0000",
            alert_on_enter=True,
            alert_on_exit=False,
            alert_on_dwell=True,
            dwell_threshold_minutes=30,
            alert_severity="high",
            description="Test restricted area",
            coordinates=[
                [24.10, 56.94],
                [24.12, 56.94],
                [24.12, 56.96],
                [24.10, 56.96],
                [24.10, 56.94],
            ],
        )
        mock_geo = _make_geofence_mock(name="Restricted Zone")
        mock_geo.zone_type = "restricted"
        mock_geo.color = "#FF0000"
        mock_geo.alert_severity = "high"

        with (
            patch.object(service.geofence_repo, "create", new_callable=AsyncMock) as mock_create,
            patch.object(
                service.geofence_repo, "get_coordinates", new_callable=AsyncMock
            ) as mock_coords,
        ):
            mock_create.return_value = mock_geo
            mock_coords.return_value = data.coordinates

            result = await service.create_geofence(data)

        assert result.name == "Restricted Zone"
        mock_create.assert_called_once()


class TestGetGeofence:
    """Tests for GeofenceService.get_geofence."""

    @pytest.mark.asyncio
    async def test_get_geofence_not_found(self, service: GeofenceService) -> None:
        """Raise GeofenceNotFoundError when ID doesn't exist."""
        with patch.object(service.geofence_repo, "get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = None

            with pytest.raises(GeofenceNotFoundError):
                await service.get_geofence(999)


class TestListGeofences:
    """Tests for GeofenceService.list_geofences."""

    @pytest.mark.asyncio
    async def test_list_geofences_empty(self, service: GeofenceService) -> None:
        """Return empty paginated response when no geofences exist."""
        pagination = PaginationParams(page=1, page_size=20)

        with (
            patch.object(
                service.geofence_repo, "list_geofences", new_callable=AsyncMock
            ) as mock_list,
            patch.object(service.geofence_repo, "count", new_callable=AsyncMock) as mock_count,
        ):
            mock_list.return_value = []
            mock_count.return_value = 0

            result = await service.list_geofences(pagination)

        assert result.items == []
        assert result.total == 0


class TestUpdateGeofence:
    """Tests for GeofenceService.update_geofence."""

    @pytest.mark.asyncio
    async def test_update_geofence_not_found(self, service: GeofenceService) -> None:
        """Raise GeofenceNotFoundError when updating non-existent geofence."""
        update_data = GeofenceUpdate(name="New Name")

        with patch.object(service.geofence_repo, "get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = None

            with pytest.raises(GeofenceNotFoundError):
                await service.update_geofence(999, update_data)


class TestDeleteGeofence:
    """Tests for GeofenceService.delete_geofence."""

    @pytest.mark.asyncio
    async def test_delete_geofence_success(self, service: GeofenceService) -> None:
        """Successfully delete existing geofence."""
        mock_geo = _make_geofence_mock()

        with (
            patch.object(service.geofence_repo, "get", new_callable=AsyncMock) as mock_get,
            patch.object(service.geofence_repo, "delete", new_callable=AsyncMock) as mock_delete,
        ):
            mock_get.return_value = mock_geo

            await service.delete_geofence(1)

        mock_delete.assert_called_once_with(mock_geo)

    @pytest.mark.asyncio
    async def test_delete_geofence_not_found(self, service: GeofenceService) -> None:
        """Raise GeofenceNotFoundError when deleting non-existent geofence."""
        with patch.object(service.geofence_repo, "get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = None

            with pytest.raises(GeofenceNotFoundError):
                await service.delete_geofence(999)


class TestCoordinatesToWkt:
    """Tests for GeofenceService._coordinates_to_wkt."""

    def test_coordinates_to_wkt(self, service: GeofenceService) -> None:
        """Verify coordinate conversion to WKT POLYGON string."""
        coords = [[24.10, 56.94], [24.12, 56.94], [24.12, 56.96], [24.10, 56.94]]
        result = service._coordinates_to_wkt(coords)
        assert result == "POLYGON((24.1 56.94, 24.12 56.94, 24.12 56.96, 24.1 56.94))"
