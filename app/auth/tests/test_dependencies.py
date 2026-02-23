# pyright: reportUnknownParameterType=false, reportMissingParameterType=false, reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false
"""Tests for auth dependencies (get_current_user, require_role)."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials

from app.auth.dependencies import get_current_user, require_role
from app.auth.models import User
from app.auth.token import create_access_token


class TestGetCurrentUser:
    @pytest.mark.asyncio
    async def test_valid_token_returns_user(self):
        token = create_access_token(user_id=1, role="admin")
        credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)

        mock_user = MagicMock(spec=User)
        mock_user.id = 1
        mock_user.is_active = True

        mock_db = AsyncMock()
        with patch("app.auth.dependencies.UserRepository") as MockRepo:
            MockRepo.return_value.find_by_id = AsyncMock(return_value=mock_user)
            user = await get_current_user(credentials=credentials, db=mock_db)

        assert user == mock_user

    @pytest.mark.asyncio
    async def test_invalid_token_raises_401(self):
        credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials="bad-token")
        mock_db = AsyncMock()

        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(credentials=credentials, db=mock_db)
        assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_refresh_token_raises_401(self):
        from app.auth.token import create_refresh_token

        token = create_refresh_token(user_id=1)
        credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)
        mock_db = AsyncMock()

        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(credentials=credentials, db=mock_db)
        assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_user_not_found_raises_401(self):
        token = create_access_token(user_id=999, role="admin")
        credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)
        mock_db = AsyncMock()

        with patch("app.auth.dependencies.UserRepository") as MockRepo:
            MockRepo.return_value.find_by_id = AsyncMock(return_value=None)
            with pytest.raises(HTTPException) as exc_info:
                await get_current_user(credentials=credentials, db=mock_db)
        assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_inactive_user_raises_403(self):
        token = create_access_token(user_id=1, role="admin")
        credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)

        mock_user = MagicMock(spec=User)
        mock_user.id = 1
        mock_user.is_active = False

        mock_db = AsyncMock()
        with patch("app.auth.dependencies.UserRepository") as MockRepo:
            MockRepo.return_value.find_by_id = AsyncMock(return_value=mock_user)
            with pytest.raises(HTTPException) as exc_info:
                await get_current_user(credentials=credentials, db=mock_db)
        assert exc_info.value.status_code == 403


class TestRequireRole:
    @pytest.mark.asyncio
    async def test_allowed_role_passes(self):
        mock_user = MagicMock(spec=User)
        mock_user.id = 1
        mock_user.role = "admin"
        mock_user.is_active = True

        check_fn = require_role("admin", "editor")
        result = await check_fn(current_user=mock_user)
        assert result == mock_user

    @pytest.mark.asyncio
    async def test_disallowed_role_raises_403(self):
        mock_user = MagicMock(spec=User)
        mock_user.id = 1
        mock_user.role = "viewer"
        mock_user.is_active = True

        check_fn = require_role("admin", "editor")
        with pytest.raises(HTTPException) as exc_info:
            await check_fn(current_user=mock_user)
        assert exc_info.value.status_code == 403

    @pytest.mark.asyncio
    async def test_dispatcher_can_manage_drivers(self):
        mock_user = MagicMock(spec=User)
        mock_user.id = 1
        mock_user.role = "dispatcher"
        mock_user.is_active = True

        check_fn = require_role("admin", "dispatcher")
        result = await check_fn(current_user=mock_user)
        assert result == mock_user

    @pytest.mark.asyncio
    async def test_viewer_cannot_write(self):
        mock_user = MagicMock(spec=User)
        mock_user.id = 1
        mock_user.role = "viewer"
        mock_user.is_active = True

        check_fn = require_role("admin", "editor")
        with pytest.raises(HTTPException) as exc_info:
            await check_fn(current_user=mock_user)
        assert exc_info.value.status_code == 403
        assert exc_info.value.detail == "Insufficient permissions"
