# pyright: reportUnknownParameterType=false, reportMissingParameterType=false, reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false, reportCallIssue=false
"""Unit tests for RequestScope dataclass and get_request_scope dependency."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.auth.scope import get_request_scope
from app.core.exceptions import RBACConfigurationError
from app.vehicles.repository import VehicleRepository

from .conftest import make_scope


def test_admin_scope_is_unrestricted():
    scope = make_scope(role="admin")
    assert scope.is_unrestricted is True
    assert scope.route_ids is None


def test_editor_scope_is_unrestricted():
    scope = make_scope(role="editor")
    assert scope.is_unrestricted is True


def test_viewer_scope_is_unrestricted():
    scope = make_scope(role="viewer")
    assert scope.is_unrestricted is True


def test_dispatcher_scope_with_routes():
    scope = make_scope(role="dispatcher", route_ids=frozenset({1, 2, 3}))
    assert scope.is_unrestricted is False
    assert scope.route_ids == frozenset({1, 2, 3})


def test_dispatcher_empty_assignments():
    scope = make_scope(role="dispatcher", route_ids=frozenset())
    assert scope.is_unrestricted is False
    assert scope.route_ids == frozenset()


def test_scope_is_frozen():
    scope = make_scope(role="admin")
    with pytest.raises(AttributeError):
        scope.user_id = 999  # type: ignore[misc]


async def test_get_request_scope_admin():
    mock_user = MagicMock(id=1, role="admin")
    mock_db = AsyncMock()

    result = await get_request_scope(current_user=mock_user, db=mock_db)
    assert result.is_unrestricted is True
    assert result.user_id == 1
    assert result.role == "admin"


async def test_get_request_scope_dispatcher():
    mock_user = MagicMock(id=2, role="dispatcher")
    mock_db = AsyncMock()

    # Simulate DB returning route_ids 1, 2, 3
    mock_result = MagicMock()
    mock_result.all.return_value = [(1,), (2,), (3,)]
    mock_db.execute = AsyncMock(return_value=mock_result)

    result = await get_request_scope(current_user=mock_user, db=mock_db)
    assert result.is_unrestricted is False
    assert result.route_ids == frozenset({1, 2, 3})
    assert result.role == "dispatcher"


async def test_get_request_scope_dispatcher_no_assignments():
    mock_user = MagicMock(id=3, role="dispatcher")
    mock_db = AsyncMock()

    mock_result = MagicMock()
    mock_result.all.return_value = []
    mock_db.execute = AsyncMock(return_value=mock_result)

    result = await get_request_scope(current_user=mock_user, db=mock_db)
    assert result.route_ids == frozenset()


async def test_fail_closed_no_scope_raises_on_list():
    repo = VehicleRepository(AsyncMock())
    with pytest.raises(RBACConfigurationError, match="RequestScope required"):
        await repo.list()


async def test_fail_closed_no_scope_raises_on_count():
    repo = VehicleRepository(AsyncMock())
    with pytest.raises(RBACConfigurationError, match="RequestScope required"):
        await repo.count()
