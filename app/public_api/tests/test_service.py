# pyright: reportCallIssue=false, reportPrivateUsage=false
"""Unit tests for PublicAPIService."""

import hashlib
from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

import pytest

from app.public_api.exceptions import (
    APIKeyRevokedError,
    InvalidAPIKeyError,
)
from app.public_api.service import PublicAPIService
from app.public_api.tests.conftest import make_api_key


@pytest.fixture
def service(mock_db: AsyncMock) -> PublicAPIService:
    """Create a PublicAPIService with mock DB."""
    return PublicAPIService(mock_db)


class TestGenerateKey:
    """Tests for API key generation."""

    @pytest.mark.asyncio
    async def test_returns_raw_key_and_model(self, service: PublicAPIService) -> None:
        """generate_key returns a raw key starting with prefix and an APIKey model."""
        with patch.object(service.repo, "create_key", new_callable=AsyncMock) as mock_create:
            mock_create.return_value = make_api_key()
            raw_key, api_key = await service.generate_key(name="Test", owner_user_id=1)

        assert raw_key.startswith("vtv_pk_")
        assert len(raw_key) == len("vtv_pk_") + 32  # 16 bytes = 32 hex chars
        assert api_key.id == 1

    @pytest.mark.asyncio
    async def test_hash_is_sha256(self, service: PublicAPIService) -> None:
        """Stored hash matches SHA-256 of the raw key."""
        with patch.object(service.repo, "create_key", new_callable=AsyncMock) as mock_create:
            mock_create.return_value = make_api_key()
            raw_key, _ = await service.generate_key(name="Test", owner_user_id=1)

        expected_hash = hashlib.sha256(raw_key.encode()).hexdigest()
        mock_create.assert_called_once()
        call_kwargs = mock_create.call_args.kwargs
        assert call_kwargs["key_hash"] == expected_hash

    @pytest.mark.asyncio
    async def test_preview_format(self, service: PublicAPIService) -> None:
        """Key preview is vtv_pk_...last4."""
        with patch.object(service.repo, "create_key", new_callable=AsyncMock) as mock_create:
            mock_create.return_value = make_api_key()
            raw_key, _ = await service.generate_key(name="Test", owner_user_id=1)

        call_kwargs = mock_create.call_args.kwargs
        assert call_kwargs["key_preview"] == f"vtv_pk_...{raw_key[-4:]}"


class TestValidateKey:
    """Tests for API key validation."""

    @pytest.mark.asyncio
    async def test_success(self, service: PublicAPIService) -> None:
        """Valid active key returns the APIKey model."""
        key = make_api_key()
        with patch.object(service.repo, "find_by_hash", new_callable=AsyncMock) as mock_find:
            mock_find.return_value = key
            result = await service.validate_key("vtv_pk_" + "a" * 32)

        assert result.id == key.id

    @pytest.mark.asyncio
    async def test_not_found_raises(self, service: PublicAPIService) -> None:
        """Unknown key hash raises InvalidAPIKeyError."""
        with patch.object(service.repo, "find_by_hash", new_callable=AsyncMock) as mock_find:
            mock_find.return_value = None
            with pytest.raises(InvalidAPIKeyError):
                await service.validate_key("vtv_pk_bad")

    @pytest.mark.asyncio
    async def test_revoked_raises(self, service: PublicAPIService) -> None:
        """Revoked key raises APIKeyRevokedError."""
        key = make_api_key(revoked_at=datetime(2026, 1, 1, tzinfo=UTC))
        with patch.object(service.repo, "find_by_hash", new_callable=AsyncMock) as mock_find:
            mock_find.return_value = key
            with pytest.raises(APIKeyRevokedError):
                await service.validate_key("vtv_pk_" + "a" * 32)

    @pytest.mark.asyncio
    async def test_expired_raises(self, service: PublicAPIService) -> None:
        """Expired key raises InvalidAPIKeyError."""
        key = make_api_key(expires_at=datetime(2020, 1, 1, tzinfo=UTC))
        with patch.object(service.repo, "find_by_hash", new_callable=AsyncMock) as mock_find:
            mock_find.return_value = key
            with pytest.raises(InvalidAPIKeyError):
                await service.validate_key("vtv_pk_" + "a" * 32)

    @pytest.mark.asyncio
    async def test_inactive_raises(self, service: PublicAPIService) -> None:
        """Inactive key raises InvalidAPIKeyError."""
        key = make_api_key(is_active=False)
        with patch.object(service.repo, "find_by_hash", new_callable=AsyncMock) as mock_find:
            mock_find.return_value = key
            with pytest.raises(InvalidAPIKeyError):
                await service.validate_key("vtv_pk_" + "a" * 32)


class TestRevokeKey:
    """Tests for key revocation."""

    @pytest.mark.asyncio
    async def test_success(self, service: PublicAPIService) -> None:
        """Revoking owned key sets revoked_at."""
        key = make_api_key(owner_user_id=10)
        revoked = make_api_key(owner_user_id=10, revoked_at=datetime(2026, 1, 1, tzinfo=UTC))
        with (
            patch.object(service.repo, "find_by_id", new_callable=AsyncMock) as mock_find,
            patch.object(service.repo, "revoke_key", new_callable=AsyncMock) as mock_revoke,
        ):
            mock_find.return_value = key
            mock_revoke.return_value = revoked
            result = await service.revoke_key(1, owner_user_id=10)

        assert result.revoked_at is not None

    @pytest.mark.asyncio
    async def test_not_found_raises(self, service: PublicAPIService) -> None:
        """Revoking nonexistent key raises NotFoundError."""
        from app.core.exceptions import NotFoundError

        with patch.object(service.repo, "find_by_id", new_callable=AsyncMock) as mock_find:
            mock_find.return_value = None
            with pytest.raises(NotFoundError):
                await service.revoke_key(999, owner_user_id=10)
