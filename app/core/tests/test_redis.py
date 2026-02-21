"""Tests for Redis client singleton."""

# pyright: reportUnknownMemberType=false, reportMissingTypeStubs=false

from unittest.mock import AsyncMock, patch

import pytest


@pytest.mark.asyncio
@patch("app.core.redis.Redis")
async def test_get_redis_creates_singleton(mock_redis_cls: AsyncMock) -> None:
    """get_redis creates client once and reuses it."""
    # Reset module state
    import app.core.redis as redis_module
    from app.core.redis import close_redis, get_redis

    redis_module._redis_client = None

    mock_client = AsyncMock()
    mock_redis_cls.from_url.return_value = mock_client

    client1 = await get_redis()
    client2 = await get_redis()

    assert client1 is client2
    mock_redis_cls.from_url.assert_called_once()

    # Cleanup
    await close_redis()


@pytest.mark.asyncio
@patch("app.core.redis.Redis")
async def test_close_redis_cleans_up(mock_redis_cls: AsyncMock) -> None:
    """close_redis calls aclose and resets singleton."""
    import app.core.redis as redis_module
    from app.core.redis import close_redis, get_redis

    redis_module._redis_client = None

    mock_client = AsyncMock()
    mock_redis_cls.from_url.return_value = mock_client

    await get_redis()
    await close_redis()

    mock_client.aclose.assert_called_once()
    assert redis_module._redis_client is None


@pytest.mark.asyncio
@patch("app.core.redis.Redis")
async def test_close_redis_handles_runtime_error(mock_redis_cls: AsyncMock) -> None:
    """close_redis swallows RuntimeError from closed event loop."""
    import app.core.redis as redis_module
    from app.core.redis import close_redis, get_redis

    redis_module._redis_client = None

    mock_client = AsyncMock()
    mock_client.aclose.side_effect = RuntimeError("Event loop closed")
    mock_redis_cls.from_url.return_value = mock_client

    await get_redis()
    # Should not raise
    await close_redis()
    assert redis_module._redis_client is None
