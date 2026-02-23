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
    @pytest.fixture(autouse=True)
    def _no_redis(self):
        """Disable Redis brute-force helpers so tests use DB-only path."""
        with (
            patch(
                "app.auth.service._check_redis_brute_force",
                new_callable=AsyncMock,
                return_value=False,
            ),
            patch(
                "app.auth.service._record_failed_attempt_redis",
                new_callable=AsyncMock,
            ),
            patch(
                "app.auth.service._clear_redis_brute_force",
                new_callable=AsyncMock,
            ),
        ):
            yield

    @pytest.mark.asyncio
    async def test_success_returns_tokens(self, service):
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
        assert result.access_token != ""
        assert result.refresh_token != ""

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

    @pytest.mark.asyncio
    async def test_brute_force_accumulates_across_calls(self, service):
        """5 consecutive wrong-password attempts should lock the account."""
        user = MagicMock(spec=User)
        user.is_active = True
        user.hashed_password = AuthService.hash_password("correct")
        user.failed_attempts = 0
        user.locked_until = None

        with (
            patch.object(service.repo, "find_by_email", return_value=user),
            patch.object(service.repo, "update", return_value=user),
        ):
            for _ in range(5):
                with pytest.raises(InvalidCredentialsError):
                    await service.authenticate("brute@vtv.lv", "wrong")

            assert user.failed_attempts == 5
            assert user.locked_until is not None

            # 6th attempt hits lockout path
            with pytest.raises(AccountLockedError):
                await service.authenticate("brute@vtv.lv", "wrong")


class TestRefreshAccessToken:
    @pytest.mark.asyncio
    async def test_refresh_returns_new_token(self, service):
        user = MagicMock(spec=User)
        user.id = 1
        user.role = "admin"
        user.is_active = True
        user.locked_until = None

        with patch.object(service.repo, "find_by_id", return_value=user):
            token = await service.refresh_access_token(user_id=1)

        assert isinstance(token, str)
        assert len(token) > 0

    @pytest.mark.asyncio
    async def test_refresh_fails_for_missing_user(self, service):
        with patch.object(service.repo, "find_by_id", return_value=None):
            with pytest.raises(InvalidCredentialsError):
                await service.refresh_access_token(user_id=999)

    @pytest.mark.asyncio
    async def test_refresh_fails_for_inactive_user(self, service):
        user = MagicMock(spec=User)
        user.id = 1
        user.is_active = False

        with patch.object(service.repo, "find_by_id", return_value=user):
            with pytest.raises(InvalidCredentialsError):
                await service.refresh_access_token(user_id=1)


class TestResetPassword:
    @pytest.fixture(autouse=True)
    def _no_redis(self):
        """Disable Redis clear helper so tests use DB-only path."""
        with patch(
            "app.auth.service._clear_redis_brute_force",
            new_callable=AsyncMock,
        ) as mock_clear:
            self.mock_clear_redis = mock_clear
            yield

    @pytest.mark.asyncio
    async def test_reset_password_success(self, service):
        user = MagicMock(spec=User)
        user.id = 1
        user.email = "admin@vtv.lv"
        user.failed_attempts = 3
        user.locked_until = "some-lockout"

        with (
            patch.object(service.repo, "find_by_id", return_value=user),
            patch.object(service.repo, "update", return_value=user),
        ):
            await service.reset_password(user_id=1, new_password="NewSecure123")

        assert user.failed_attempts == 0
        assert user.locked_until is None
        assert user.hashed_password != ""
        self.mock_clear_redis.assert_awaited_once_with("admin@vtv.lv")

    @pytest.mark.asyncio
    async def test_reset_password_user_not_found(self, service):
        with patch.object(service.repo, "find_by_id", return_value=None):
            with pytest.raises(InvalidCredentialsError):
                await service.reset_password(user_id=999, new_password="NewSecure123")


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
