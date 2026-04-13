# pyright: reportUnknownParameterType=false, reportMissingParameterType=false, reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false, reportCallIssue=false
"""Unit tests for dispatcher assignment CRUD endpoints."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.auth.repository import AssignmentRepository


@pytest.fixture
def repo() -> AssignmentRepository:
    mock_db = AsyncMock()
    return AssignmentRepository(mock_db)


async def test_list_by_user(repo):
    assignment = MagicMock(id=1, user_id=2, route_id=1, assigned_by=1)
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [assignment]
    repo.db.execute = AsyncMock(return_value=mock_result)

    result = await repo.list_by_user(2)
    assert len(result) == 1
    assert result[0].user_id == 2


async def test_create_assignment(repo):
    repo.db.commit = AsyncMock()
    repo.db.refresh = AsyncMock()
    repo.db.add = MagicMock()

    result = await repo.create(2, 1, 1)
    repo.db.add.assert_called_once()
    repo.db.commit.assert_awaited_once()
    # The real model is created; verify the add call received the right args
    added_obj = repo.db.add.call_args[0][0]
    assert added_obj.user_id == 2
    assert added_obj.route_id == 1
    assert added_obj.assigned_by == 1
    _ = result  # refresh returns mock


async def test_delete_assignment(repo):
    assignment = MagicMock(id=1, user_id=2, route_id=1)
    repo.db.delete = AsyncMock()
    repo.db.commit = AsyncMock()

    await repo.delete(assignment)
    repo.db.delete.assert_awaited_once_with(assignment)
    repo.db.commit.assert_awaited_once()


async def test_get_returns_none_for_missing(repo):
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    repo.db.execute = AsyncMock(return_value=mock_result)

    result = await repo.get(999)
    assert result is None
