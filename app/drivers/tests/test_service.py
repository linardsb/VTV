# pyright: reportUnknownParameterType=false, reportMissingParameterType=false, reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false, reportCallIssue=false
"""Unit tests for DriverService business logic."""

from unittest.mock import AsyncMock

import pytest

from app.drivers.exceptions import DriverAlreadyExistsError, DriverNotFoundError
from app.drivers.schemas import DriverCreate, DriverUpdate
from app.drivers.service import DriverService
from app.drivers.tests.conftest import make_driver
from app.shared.schemas import PaginationParams


@pytest.fixture
def service() -> DriverService:
    mock_db = AsyncMock()
    svc = DriverService(mock_db)
    svc.repository = AsyncMock()
    return svc


async def test_get_driver_success(service):
    driver = make_driver(id=1, first_name="Janis")
    service.repository.get = AsyncMock(return_value=driver)

    result = await service.get_driver(1)
    assert result.id == 1
    assert result.first_name == "Janis"
    service.repository.get.assert_awaited_once_with(1)


async def test_get_driver_not_found(service):
    service.repository.get = AsyncMock(return_value=None)

    with pytest.raises(DriverNotFoundError, match="Driver 999 not found"):
        await service.get_driver(999)


async def test_list_drivers(service):
    drivers = [
        make_driver(id=1, first_name="Janis"),
        make_driver(id=2, first_name="Anna", employee_number="DRV-002"),
    ]
    service.repository.list = AsyncMock(return_value=drivers)
    service.repository.count = AsyncMock(return_value=2)

    pagination = PaginationParams(page=1, page_size=20)
    result = await service.list_drivers(pagination)

    assert len(result.items) == 2
    assert result.total == 2
    assert result.page == 1


async def test_create_driver_success(service):
    data = DriverCreate(
        first_name="New",
        last_name="Driver",
        employee_number="DRV-099",
    )
    created = make_driver(id=10, employee_number="DRV-099", first_name="New", last_name="Driver")
    service.repository.get_by_employee_number = AsyncMock(return_value=None)
    service.repository.create = AsyncMock(return_value=created)

    result = await service.create_driver(data)
    assert result.id == 10
    assert result.employee_number == "DRV-099"


async def test_create_driver_duplicate(service):
    data = DriverCreate(
        first_name="Dup",
        last_name="Driver",
        employee_number="DRV-001",
    )
    existing = make_driver(id=1, employee_number="DRV-001")
    service.repository.get_by_employee_number = AsyncMock(return_value=existing)

    with pytest.raises(DriverAlreadyExistsError, match="already exists"):
        await service.create_driver(data)


async def test_update_driver_success(service):
    driver = make_driver(id=1, first_name="Old")
    updated = make_driver(id=1, first_name="New")
    data = DriverUpdate(first_name="New")

    service.repository.get = AsyncMock(return_value=driver)
    service.repository.update = AsyncMock(return_value=updated)

    result = await service.update_driver(1, data)
    assert result.first_name == "New"


async def test_update_driver_not_found(service):
    service.repository.get = AsyncMock(return_value=None)
    data = DriverUpdate(first_name="New")

    with pytest.raises(DriverNotFoundError, match="Driver 999 not found"):
        await service.update_driver(999, data)


async def test_update_driver_duplicate_employee_number(service):
    driver = make_driver(id=1, employee_number="DRV-001")
    existing = make_driver(id=2, employee_number="DRV-002")
    data = DriverUpdate(employee_number="DRV-002")

    service.repository.get = AsyncMock(return_value=driver)
    service.repository.get_by_employee_number = AsyncMock(return_value=existing)

    with pytest.raises(DriverAlreadyExistsError, match="already exists"):
        await service.update_driver(1, data)


async def test_delete_driver_success(service):
    driver = make_driver(id=1)
    service.repository.get = AsyncMock(return_value=driver)
    service.repository.delete = AsyncMock()

    await service.delete_driver(1)
    service.repository.delete.assert_awaited_once_with(driver)


async def test_delete_driver_not_found(service):
    service.repository.get = AsyncMock(return_value=None)

    with pytest.raises(DriverNotFoundError, match="Driver 999 not found"):
        await service.delete_driver(999)
