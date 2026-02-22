# pyright: reportUnknownParameterType=false, reportMissingParameterType=false, reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false, reportCallIssue=false
"""Unit tests for DriverRepository database operations."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.drivers.models import Driver
from app.drivers.repository import DriverRepository
from app.drivers.schemas import DriverCreate, DriverUpdate
from app.drivers.tests.conftest import make_driver


@pytest.fixture
def repo() -> DriverRepository:
    mock_db = AsyncMock()
    return DriverRepository(mock_db)


async def test_get_by_id(repo):
    driver = make_driver(id=1)
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = driver
    repo.db.execute = AsyncMock(return_value=mock_result)

    result = await repo.get(1)
    assert result is driver
    repo.db.execute.assert_awaited_once()


async def test_get_not_found(repo):
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    repo.db.execute = AsyncMock(return_value=mock_result)

    result = await repo.get(999)
    assert result is None


async def test_get_by_employee_number(repo):
    driver = make_driver(employee_number="DRV-001")
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = driver
    repo.db.execute = AsyncMock(return_value=mock_result)

    result = await repo.get_by_employee_number("DRV-001")
    assert result is driver


async def test_list_default(repo):
    drivers = [make_driver(id=1), make_driver(id=2)]
    mock_scalars = MagicMock()
    mock_scalars.all.return_value = drivers
    mock_result = MagicMock()
    mock_result.scalars.return_value = mock_scalars
    repo.db.execute = AsyncMock(return_value=mock_result)

    result = await repo.list(offset=0, limit=20)
    assert len(result) == 2
    repo.db.execute.assert_awaited_once()


async def test_list_with_search(repo):
    drivers = [make_driver(id=1, first_name="Janis")]
    mock_scalars = MagicMock()
    mock_scalars.all.return_value = drivers
    mock_result = MagicMock()
    mock_result.scalars.return_value = mock_scalars
    repo.db.execute = AsyncMock(return_value=mock_result)

    result = await repo.list(offset=0, limit=20, search="Jan")
    assert len(result) == 1


async def test_list_with_status_filter(repo):
    drivers = [make_driver(id=1, status="on_leave")]
    mock_scalars = MagicMock()
    mock_scalars.all.return_value = drivers
    mock_result = MagicMock()
    mock_result.scalars.return_value = mock_scalars
    repo.db.execute = AsyncMock(return_value=mock_result)

    result = await repo.list(offset=0, limit=20, status="on_leave")
    assert len(result) == 1


async def test_list_with_shift_filter(repo):
    drivers = [make_driver(id=1, default_shift="afternoon")]
    mock_scalars = MagicMock()
    mock_scalars.all.return_value = drivers
    mock_result = MagicMock()
    mock_result.scalars.return_value = mock_scalars
    repo.db.execute = AsyncMock(return_value=mock_result)

    result = await repo.list(offset=0, limit=20, shift="afternoon")
    assert len(result) == 1


async def test_count(repo):
    mock_result = MagicMock()
    mock_result.scalar_one.return_value = 42
    repo.db.execute = AsyncMock(return_value=mock_result)

    result = await repo.count(active_only=True)
    assert result == 42


async def test_create(repo):
    data = DriverCreate(
        first_name="New",
        last_name="Driver",
        employee_number="DRV-099",
    )

    async def mock_refresh(obj: Driver) -> None:
        object.__setattr__(obj, "id", 10)

    repo.db.commit = AsyncMock()
    repo.db.refresh = AsyncMock(side_effect=mock_refresh)

    result = await repo.create(data)
    assert isinstance(result, Driver)
    repo.db.add.assert_called_once()
    repo.db.commit.assert_awaited_once()
    repo.db.refresh.assert_awaited_once()


async def test_update(repo):
    driver = make_driver(id=1, first_name="Old")
    data = DriverUpdate(first_name="New")

    repo.db.commit = AsyncMock()
    repo.db.refresh = AsyncMock()

    result = await repo.update(driver, data)
    assert result.first_name == "New"
    repo.db.commit.assert_awaited_once()
    repo.db.refresh.assert_awaited_once()


async def test_delete(repo):
    driver = make_driver(id=1)
    repo.db.delete = AsyncMock()
    repo.db.commit = AsyncMock()

    await repo.delete(driver)
    repo.db.delete.assert_awaited_once_with(driver)
    repo.db.commit.assert_awaited_once()
