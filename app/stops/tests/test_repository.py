# pyright: reportUnknownParameterType=false, reportMissingParameterType=false, reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false, reportCallIssue=false
"""Unit tests for StopRepository database operations."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.stops.models import Stop
from app.stops.repository import StopRepository
from app.stops.schemas import StopCreate, StopUpdate
from app.stops.tests.conftest import make_stop


@pytest.fixture
def repo() -> StopRepository:
    mock_db = AsyncMock()
    return StopRepository(mock_db)


async def test_get_by_id(repo):
    stop = make_stop(id=1)
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = stop
    repo.db.execute = AsyncMock(return_value=mock_result)

    result = await repo.get(1)
    assert result is stop
    repo.db.execute.assert_awaited_once()


async def test_get_by_id_not_found(repo):
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    repo.db.execute = AsyncMock(return_value=mock_result)

    result = await repo.get(999)
    assert result is None


async def test_get_by_gtfs_id(repo):
    stop = make_stop(gtfs_stop_id="1001")
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = stop
    repo.db.execute = AsyncMock(return_value=mock_result)

    result = await repo.get_by_gtfs_id("1001")
    assert result is stop


async def test_list_default(repo):
    stops = [make_stop(id=1), make_stop(id=2)]
    mock_scalars = MagicMock()
    mock_scalars.all.return_value = stops
    mock_result = MagicMock()
    mock_result.scalars.return_value = mock_scalars
    repo.db.execute = AsyncMock(return_value=mock_result)

    result = await repo.list(offset=0, limit=20)
    assert len(result) == 2
    repo.db.execute.assert_awaited_once()


async def test_list_with_search(repo):
    stops = [make_stop(id=1, stop_name="Centrala stacija")]
    mock_scalars = MagicMock()
    mock_scalars.all.return_value = stops
    mock_result = MagicMock()
    mock_result.scalars.return_value = mock_scalars
    repo.db.execute = AsyncMock(return_value=mock_result)

    result = await repo.list(offset=0, limit=20, search="Centr")
    assert len(result) == 1


async def test_count_active(repo):
    mock_result = MagicMock()
    mock_result.scalar_one.return_value = 42
    repo.db.execute = AsyncMock(return_value=mock_result)

    result = await repo.count(active_only=True)
    assert result == 42


async def test_create(repo):
    data = StopCreate(stop_name="New Stop", gtfs_stop_id="9999")

    # Mock refresh to set attributes
    async def mock_refresh(obj: Stop) -> None:
        object.__setattr__(obj, "id", 10)

    repo.db.commit = AsyncMock()
    repo.db.refresh = AsyncMock(side_effect=mock_refresh)

    result = await repo.create(data)
    assert isinstance(result, Stop)
    repo.db.add.assert_called_once()
    repo.db.commit.assert_awaited_once()
    repo.db.refresh.assert_awaited_once()


async def test_update(repo):
    stop = make_stop(id=1, stop_name="Old Name")
    data = StopUpdate(stop_name="New Name")

    repo.db.commit = AsyncMock()
    repo.db.refresh = AsyncMock()

    result = await repo.update(stop, data)
    assert result.stop_name == "New Name"
    repo.db.commit.assert_awaited_once()
    repo.db.refresh.assert_awaited_once()


async def test_delete(repo):
    stop = make_stop(id=1)
    repo.db.delete = AsyncMock()
    repo.db.commit = AsyncMock()

    await repo.delete(stop)
    repo.db.delete.assert_awaited_once_with(stop)
    repo.db.commit.assert_awaited_once()
