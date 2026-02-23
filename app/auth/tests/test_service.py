# pyright: reportUnknownParameterType=false, reportMissingParameterType=false, reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false
"""Tests for AuthService."""

import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.auth.exceptions import AccountLockedError, InvalidCredentialsError
from app.auth.models import User
from app.auth.service import AuthService
from app.shared.models import utcnow


@pytest.fixture
def mock_db():
    return AsyncMock()


@pytest.fixture
def service(mock_db):
    return AuthService(mock_db)


class TestPasswordHashing:
    def test_hash_and_verify(self):
        password = "test-password-123"
        hashed = AuthService.hash_password(password)
        assert hashed != password
        assert AuthService.verify_password(password, hashed)

    def test_wrong_password_fails(self):
        hashed = AuthService.hash_password("correct")
        assert not AuthService.verify_password("wrong", hashed)


class TestAuthenticate:
    @pytest.mark.asyncio
    async def test_success(self, service):
        user = MagicMock(spec=User)
        user.id = 1
        user.email = "admin@vtv.lv"
        user.name = "Admin"
        user.role = "admin"
        user.is_active = True
        user.hashed_password = AuthService.hash_password("admin")
        user.failed_attempts = 0
        user.locked_until = None

        with patch.object(service.repo, "find_by_email", return_value=user):
            result = await service.authenticate("admin@vtv.lv", "admin")

        assert result.email == "admin@vtv.lv"
        assert result.role == "admin"

    @pytest.mark.asyncio
    async def test_user_not_found(self, service):
        with patch.object(service.repo, "find_by_email", return_value=None):
            with pytest.raises(InvalidCredentialsError):
                await service.authenticate("nobody@vtv.lv", "pass")

    @pytest.mark.asyncio
    async def test_inactive_user(self, service):
        user = MagicMock(spec=User)
        user.is_active = False

        with patch.object(service.repo, "find_by_email", return_value=user):
            with pytest.raises(InvalidCredentialsError):
                await service.authenticate("inactive@vtv.lv", "pass")

    @pytest.mark.asyncio
    async def test_locked_account(self, service):
        user = MagicMock(spec=User)
        user.is_active = True
        user.locked_until = utcnow() + datetime.timedelta(minutes=10)

        with patch.object(service.repo, "find_by_email", return_value=user):
            with pytest.raises(AccountLockedError):
                await service.authenticate("locked@vtv.lv", "pass")

    @pytest.mark.asyncio
    async def test_wrong_password_increments_attempts(self, service):
        user = MagicMock(spec=User)
        user.is_active = True
        user.hashed_password = AuthService.hash_password("correct")
        user.failed_attempts = 0
        user.locked_until = None

        with (
            patch.object(service.repo, "find_by_email", return_value=user),
            patch.object(service.repo, "update", return_value=user),
        ):
            with pytest.raises(InvalidCredentialsError):
                await service.authenticate("test@vtv.lv", "wrong")
            assert user.failed_attempts == 1

    @pytest.mark.asyncio
    async def test_lockout_after_max_attempts(self, service):
        user = MagicMock(spec=User)
        user.is_active = True
        user.hashed_password = AuthService.hash_password("correct")
        user.failed_attempts = 4
        user.locked_until = None

        with (
            patch.object(service.repo, "find_by_email", return_value=user),
            patch.object(service.repo, "update", return_value=user),
        ):
            with pytest.raises(InvalidCredentialsError):
                await service.authenticate("test@vtv.lv", "wrong")
            assert user.failed_attempts == 5
            assert user.locked_until is not None


class TestSeedDemoUsers:
    @pytest.mark.asyncio
    async def test_seeds_when_empty(self, service):
        with (
            patch.object(service.repo, "count", return_value=0),
            patch.object(service.repo, "create", side_effect=lambda u: u),
        ):
            users = await service.seed_demo_users()
            assert len(users) == 5

    @pytest.mark.asyncio
    async def test_skips_when_users_exist(self, service):
        with patch.object(service.repo, "count", return_value=1):
            users = await service.seed_demo_users()
            assert len(users) == 0
