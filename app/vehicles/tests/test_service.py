# pyright: reportUnknownParameterType=false, reportMissingParameterType=false, reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false, reportCallIssue=false
"""Unit tests for VehicleService business logic."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.vehicles.exceptions import (
    DriverAssignmentError,
    VehicleAlreadyExistsError,
    VehicleNotFoundError,
)
from app.vehicles.schemas import MaintenanceRecordCreate, VehicleCreate, VehicleUpdate
from app.vehicles.service import VehicleService

from .conftest import make_maintenance_record, make_vehicle


@pytest.fixture
def service() -> VehicleService:
    mock_db = AsyncMock()
    svc = VehicleService(mock_db)
    svc.vehicle_repo = AsyncMock()
    svc.maintenance_repo = AsyncMock()
    return svc


async def test_get_vehicle_success(service):
    vehicle = make_vehicle(id=1, fleet_number="4521")
    service.vehicle_repo.get = AsyncMock(return_value=vehicle)

    result = await service.get_vehicle(1)
    assert result.id == 1
    assert result.fleet_number == "4521"
    service.vehicle_repo.get.assert_awaited_once_with(1)


async def test_get_vehicle_not_found(service):
    service.vehicle_repo.get = AsyncMock(return_value=None)

    with pytest.raises(VehicleNotFoundError):
        await service.get_vehicle(999)


async def test_list_vehicles_with_pagination(service):
    from app.shared.schemas import PaginationParams

    vehicles = [
        make_vehicle(id=1, fleet_number="4521"),
        make_vehicle(id=2, fleet_number="4522"),
    ]
    service.vehicle_repo.list = AsyncMock(return_value=vehicles)
    service.vehicle_repo.count = AsyncMock(return_value=2)

    pagination = PaginationParams(page=1, page_size=20)
    result = await service.list_vehicles(pagination)

    assert len(result.items) == 2
    assert result.total == 2
    assert result.page == 1


async def test_list_vehicles_with_search(service):
    from app.shared.schemas import PaginationParams

    service.vehicle_repo.list = AsyncMock(return_value=[])
    service.vehicle_repo.count = AsyncMock(return_value=0)

    pagination = PaginationParams(page=1, page_size=20)
    await service.list_vehicles(pagination, search="Solaris")

    service.vehicle_repo.list.assert_awaited_once()
    call_kwargs = service.vehicle_repo.list.call_args[1]
    assert call_kwargs["search"] == "Solaris"


async def test_create_vehicle_success(service):
    data = VehicleCreate(
        fleet_number="4530",
        vehicle_type="bus",
        license_plate="CD-5678",
    )
    created = make_vehicle(id=10, fleet_number="4530", license_plate="CD-5678")
    service.vehicle_repo.get_by_fleet_number = AsyncMock(return_value=None)
    service.vehicle_repo.create = AsyncMock(return_value=created)

    result = await service.create_vehicle(data)
    assert result.id == 10
    assert result.fleet_number == "4530"


async def test_create_vehicle_duplicate_fleet_number(service):
    data = VehicleCreate(
        fleet_number="4521",
        vehicle_type="bus",
        license_plate="AB-1234",
    )
    existing = make_vehicle(id=1, fleet_number="4521")
    service.vehicle_repo.get_by_fleet_number = AsyncMock(return_value=existing)

    with pytest.raises(VehicleAlreadyExistsError, match="already exists"):
        await service.create_vehicle(data)


async def test_update_vehicle_success(service):
    vehicle = make_vehicle(id=1, fleet_number="4521")
    updated = make_vehicle(id=1, fleet_number="4521", license_plate="NEW-1234")
    data = VehicleUpdate(license_plate="NEW-1234")

    service.vehicle_repo.get = AsyncMock(return_value=vehicle)
    service.vehicle_repo.update = AsyncMock(return_value=updated)

    result = await service.update_vehicle(1, data)
    assert result.license_plate == "NEW-1234"


async def test_update_vehicle_not_found(service):
    service.vehicle_repo.get = AsyncMock(return_value=None)
    data = VehicleUpdate(license_plate="NEW-1234")

    with pytest.raises(VehicleNotFoundError):
        await service.update_vehicle(999, data)


async def test_update_vehicle_duplicate_fleet_number(service):
    vehicle = make_vehicle(id=1, fleet_number="4521")
    existing = make_vehicle(id=2, fleet_number="4522")
    data = VehicleUpdate(fleet_number="4522")

    service.vehicle_repo.get = AsyncMock(return_value=vehicle)
    service.vehicle_repo.get_by_fleet_number = AsyncMock(return_value=existing)

    with pytest.raises(VehicleAlreadyExistsError, match="already exists"):
        await service.update_vehicle(1, data)


async def test_delete_vehicle_success(service):
    vehicle = make_vehicle(id=1)
    service.vehicle_repo.get = AsyncMock(return_value=vehicle)
    service.vehicle_repo.delete = AsyncMock()

    await service.delete_vehicle(1)
    service.vehicle_repo.delete.assert_awaited_once_with(vehicle)


async def test_delete_vehicle_not_found(service):
    service.vehicle_repo.get = AsyncMock(return_value=None)

    with pytest.raises(VehicleNotFoundError):
        await service.delete_vehicle(999)


async def test_assign_driver_success(service):
    vehicle = make_vehicle(id=1, current_driver_id=None)
    mock_driver = MagicMock(id=5)

    service.vehicle_repo.get = AsyncMock(return_value=vehicle)
    service.vehicle_repo.get_vehicles_by_driver = AsyncMock(return_value=[])

    # Mock DriverRepository via the db session
    mock_driver_repo_get = AsyncMock(return_value=mock_driver)

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(
            "app.vehicles.service.DriverRepository",
            lambda _db: MagicMock(get=mock_driver_repo_get),
        )
        result = await service.assign_driver(1, 5)

    assert result.current_driver_id == 5


async def test_assign_driver_not_found(service):
    vehicle = make_vehicle(id=1)
    service.vehicle_repo.get = AsyncMock(return_value=vehicle)

    mock_driver_repo_get = AsyncMock(return_value=None)

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(
            "app.vehicles.service.DriverRepository",
            lambda _db: MagicMock(get=mock_driver_repo_get),
        )
        with pytest.raises(DriverAssignmentError, match="not found"):
            await service.assign_driver(1, 999)


async def test_assign_driver_unassign(service):
    vehicle = make_vehicle(id=1, current_driver_id=5)

    service.vehicle_repo.get = AsyncMock(return_value=vehicle)

    result = await service.assign_driver(1, None)
    assert result.current_driver_id is None


async def test_add_maintenance_record_success(service):
    import datetime

    vehicle = make_vehicle(id=1, mileage_km=50000)
    record = make_maintenance_record(
        id=1,
        vehicle_id=1,
        mileage_at_service=55000,
        next_scheduled_date=datetime.date(2026, 7, 1),
    )
    data = MaintenanceRecordCreate(
        maintenance_type="scheduled",
        description="Oil change",
        performed_date=datetime.date(2026, 3, 15),
        mileage_at_service=55000,
        next_scheduled_date=datetime.date(2026, 7, 1),
    )

    service.vehicle_repo.get = AsyncMock(return_value=vehicle)
    service.maintenance_repo.create = AsyncMock(return_value=record)

    result = await service.add_maintenance_record(1, data)
    assert result.id == 1
    assert result.maintenance_type == "scheduled"
    # Verify mileage was updated on vehicle
    assert vehicle.mileage_km == 55000


async def test_add_maintenance_record_vehicle_not_found(service):
    import datetime

    service.vehicle_repo.get = AsyncMock(return_value=None)
    data = MaintenanceRecordCreate(
        maintenance_type="scheduled",
        description="Oil change",
        performed_date=datetime.date(2026, 3, 15),
    )

    with pytest.raises(VehicleNotFoundError):
        await service.add_maintenance_record(999, data)
