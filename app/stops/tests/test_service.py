# pyright: reportUnknownParameterType=false, reportMissingParameterType=false, reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false, reportCallIssue=false
"""Unit tests for StopService business logic."""

from unittest.mock import AsyncMock, patch

import pytest

from app.shared.schemas import PaginationParams
from app.stops.exceptions import StopAlreadyExistsError, StopNotFoundError
from app.stops.schemas import StopCreate, StopNearbyParams, StopUpdate
from app.stops.service import StopService
from app.stops.tests.conftest import make_stop


@pytest.fixture
def service() -> StopService:
    mock_db = AsyncMock()
    svc = StopService(mock_db)
    svc.repository = AsyncMock()
    return svc


async def test_get_stop_success(service):
    stop = make_stop(id=1, stop_name="Centrala stacija")
    service.repository.get = AsyncMock(return_value=stop)

    result = await service.get_stop(1)
    assert result.id == 1
    assert result.stop_name == "Centrala stacija"
    service.repository.get.assert_awaited_once_with(1)


async def test_get_stop_not_found(service):
    service.repository.get = AsyncMock(return_value=None)

    with pytest.raises(StopNotFoundError, match="Stop 999 not found"):
        await service.get_stop(999)


async def test_list_stops_success(service):
    stops = [
        make_stop(id=1, stop_name="A Stop"),
        make_stop(id=2, stop_name="B Stop"),
    ]
    service.repository.list = AsyncMock(return_value=stops)
    service.repository.count = AsyncMock(return_value=2)

    pagination = PaginationParams(page=1, page_size=20)
    result = await service.list_stops(pagination)

    assert len(result.items) == 2
    assert result.total == 2
    assert result.page == 1


async def test_list_stops_empty(service):
    service.repository.list = AsyncMock(return_value=[])
    service.repository.count = AsyncMock(return_value=0)

    pagination = PaginationParams(page=1, page_size=20)
    result = await service.list_stops(pagination)

    assert len(result.items) == 0
    assert result.total == 0


async def test_list_stops_with_search(service):
    stops = [make_stop(id=1, stop_name="Centrala stacija")]
    service.repository.list = AsyncMock(return_value=stops)
    service.repository.count = AsyncMock(return_value=1)

    pagination = PaginationParams(page=1, page_size=20)
    result = await service.list_stops(pagination, search="Centr")

    assert len(result.items) == 1
    service.repository.list.assert_awaited_once_with(
        offset=0, limit=20, active_only=True, search="Centr", location_type=None
    )


async def test_create_stop_success(service):
    data = StopCreate(
        stop_name="New Stop",
        gtfs_stop_id="9999",
        stop_lat=56.95,
        stop_lon=24.10,
    )
    created_stop = make_stop(id=10, gtfs_stop_id="9999", stop_name="New Stop")
    service.repository.get_by_gtfs_id = AsyncMock(return_value=None)
    service.repository.create = AsyncMock(return_value=created_stop)

    result = await service.create_stop(data)
    assert result.id == 10
    assert result.gtfs_stop_id == "9999"


async def test_create_stop_duplicate(service):
    data = StopCreate(
        stop_name="Duplicate Stop",
        gtfs_stop_id="1001",
    )
    existing = make_stop(id=1, gtfs_stop_id="1001")
    service.repository.get_by_gtfs_id = AsyncMock(return_value=existing)

    with pytest.raises(StopAlreadyExistsError, match="already exists"):
        await service.create_stop(data)


async def test_update_stop_success(service):
    stop = make_stop(id=1, stop_name="Old Name")
    updated = make_stop(id=1, stop_name="New Name")
    data = StopUpdate(stop_name="New Name")

    service.repository.get = AsyncMock(return_value=stop)
    service.repository.update = AsyncMock(return_value=updated)

    result = await service.update_stop(1, data)
    assert result.stop_name == "New Name"


async def test_update_stop_not_found(service):
    service.repository.get = AsyncMock(return_value=None)
    data = StopUpdate(stop_name="New Name")

    with pytest.raises(StopNotFoundError, match="Stop 999 not found"):
        await service.update_stop(999, data)


async def test_delete_stop_success(service):
    stop = make_stop(id=1)
    service.repository.get = AsyncMock(return_value=stop)
    service.repository.delete = AsyncMock()

    await service.delete_stop(1)
    service.repository.delete.assert_awaited_once_with(stop)


async def test_delete_stop_not_found(service):
    service.repository.get = AsyncMock(return_value=None)

    with pytest.raises(StopNotFoundError, match="Stop 999 not found"):
        await service.delete_stop(999)


async def test_search_nearby_success(service):
    stops = [
        make_stop(id=1, stop_name="Near", stop_lat=56.9497, stop_lon=24.1053),
        make_stop(id=2, stop_name="Far", stop_lat=56.9700, stop_lon=24.1500),
        make_stop(id=3, stop_name="No Coords", stop_lat=None, stop_lon=None),
    ]
    service.repository.list = AsyncMock(return_value=stops)

    params = StopNearbyParams(latitude=56.9496, longitude=24.1052, radius_meters=500)
    result = await service.search_nearby(params, limit=10)

    # Only the "Near" stop is within 500m
    assert len(result) == 1
    assert result[0].stop_name == "Near"


async def test_search_nearby_no_results(service):
    stops = [
        make_stop(id=1, stop_name="Far", stop_lat=57.0, stop_lon=25.0),
    ]
    service.repository.list = AsyncMock(return_value=stops)

    params = StopNearbyParams(latitude=56.9496, longitude=24.1052, radius_meters=100)
    result = await service.search_nearby(params, limit=10)

    assert len(result) == 0


@patch("app.stops.service._haversine_distance")
async def test_search_nearby_sorted_by_distance(mock_haversine, service):
    stops = [
        make_stop(id=1, stop_name="Medium", stop_lat=56.95, stop_lon=24.11),
        make_stop(id=2, stop_name="Near", stop_lat=56.9497, stop_lon=24.1053),
    ]
    # Return distances so "Near" is closer
    mock_haversine.side_effect = [300.0, 50.0]
    service.repository.list = AsyncMock(return_value=stops)

    params = StopNearbyParams(latitude=56.9496, longitude=24.1052, radius_meters=500)
    result = await service.search_nearby(params, limit=10)

    assert len(result) == 2
    assert result[0].stop_name == "Near"
    assert result[1].stop_name == "Medium"
