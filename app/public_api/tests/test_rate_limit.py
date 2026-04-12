# pyright: reportCallIssue=false, reportPrivateUsage=false
"""Unit tests for per-key rate limiting logic."""

from unittest.mock import AsyncMock, patch

import pytest

from app.public_api.exceptions import APIKeyRateLimitError
from app.public_api.service import PublicAPIService
from app.public_api.tests.conftest import make_api_key


@pytest.fixture
def service(mock_db: AsyncMock) -> PublicAPIService:
    """Create a PublicAPIService with mock DB."""
    return PublicAPIService(mock_db)


class TestCheckRateLimit:
    """Tests for the fixed-window rate counter."""

    @pytest.mark.asyncio
    async def test_under_limit_allows(self, service: PublicAPIService) -> None:
        """Request under the limit returns (limit, remaining)."""
        key = make_api_key(tier="free")
        mock_redis = AsyncMock()
        mock_redis.incr.return_value = 5
        with patch("app.public_api.service.get_redis", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_redis
            limit, remaining = await service.check_rate_limit(key)

        assert limit == 60
        assert remaining == 55

    @pytest.mark.asyncio
    async def test_first_request_sets_expiry(self, service: PublicAPIService) -> None:
        """First request (count=1) sets TTL on the counter key."""
        key = make_api_key(tier="free")
        mock_redis = AsyncMock()
        mock_redis.incr.return_value = 1
        with patch("app.public_api.service.get_redis", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_redis
            await service.check_rate_limit(key)

        mock_redis.expire.assert_called_once()
        args = mock_redis.expire.call_args
        assert args[0][1] == 60  # 60 second window

    @pytest.mark.asyncio
    async def test_exceeds_limit_raises(self, service: PublicAPIService) -> None:
        """Exceeding the tier limit raises APIKeyRateLimitError."""
        key = make_api_key(tier="free")
        mock_redis = AsyncMock()
        mock_redis.incr.return_value = 61  # Over the 60 limit
        with patch("app.public_api.service.get_redis", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_redis
            with pytest.raises(APIKeyRateLimitError) as exc_info:
                await service.check_rate_limit(key)

        assert exc_info.value.retry_after == 60

    @pytest.mark.asyncio
    async def test_pro_tier_allows_1000(self, service: PublicAPIService) -> None:
        """Pro tier allows up to 1000 requests per minute."""
        key = make_api_key(tier="pro")
        mock_redis = AsyncMock()
        mock_redis.incr.return_value = 999
        with patch("app.public_api.service.get_redis", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_redis
            limit, remaining = await service.check_rate_limit(key)

        assert limit == 1000
        assert remaining == 1

    @pytest.mark.asyncio
    async def test_redis_failure_allows_request(self, service: PublicAPIService) -> None:
        """Redis failure gracefully allows the request (non-critical)."""
        key = make_api_key(tier="free")
        with patch(
            "app.public_api.service.get_redis",
            new_callable=AsyncMock,
            side_effect=ConnectionError("Redis down"),
        ):
            limit, remaining = await service.check_rate_limit(key)

        assert limit == 60
        assert remaining == 60  # Fully allowed on Redis failure
