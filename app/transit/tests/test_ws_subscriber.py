"""Tests for the Redis Pub/Sub WebSocket subscriber."""

# pyright: reportUnknownMemberType=false, reportMissingTypeStubs=false

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.transit.ws_manager import ConnectionManager
from app.transit.ws_subscriber import _subscribe_loop


def _make_pmessage(feed_id: str, vehicles: list[dict[str, object]]) -> dict[str, object]:
    """Create a mock Redis Pub/Sub pmessage."""
    return {
        "type": "pmessage",
        "pattern": b"transit:vehicles:*",
        "channel": f"transit:vehicles:{feed_id}".encode(),
        "data": json.dumps(
            {
                "feed_id": feed_id,
                "count": len(vehicles),
                "vehicles": vehicles,
                "timestamp": "2026-01-01T00:00:00Z",
            }
        ),
    }


@pytest.mark.asyncio
@patch("app.transit.ws_subscriber.get_redis")
async def test_subscriber_dispatches_to_manager(mock_get_redis: AsyncMock) -> None:
    """Valid pmessage triggers manager.broadcast with correct args."""
    vehicles: list[dict[str, object]] = [{"vehicle_id": "v1", "route_id": "22"}]
    msg = _make_pmessage("riga", vehicles)

    # Mock pubsub that yields one message then cancels
    mock_pubsub = MagicMock()
    mock_pubsub.psubscribe = AsyncMock()

    async def _listen():
        yield msg
        # Trigger cancellation after processing
        raise asyncio.CancelledError

    mock_pubsub.listen = _listen
    mock_pubsub.punsubscribe = AsyncMock()
    mock_pubsub.aclose = AsyncMock()

    mock_redis = MagicMock()
    mock_redis.pubsub.return_value = mock_pubsub
    mock_get_redis.return_value = mock_redis

    manager = MagicMock(spec=ConnectionManager)
    manager.broadcast = AsyncMock()

    await _subscribe_loop(manager)

    manager.broadcast.assert_called_once_with("riga", vehicles, "2026-01-01T00:00:00Z")


@pytest.mark.asyncio
@patch("app.transit.ws_subscriber.get_redis")
async def test_subscriber_skips_non_pmessage(mock_get_redis: AsyncMock) -> None:
    """Subscribe confirmation messages are ignored."""
    subscribe_msg: dict[str, object] = {
        "type": "psubscribe",
        "pattern": b"transit:vehicles:*",
        "channel": b"transit:vehicles:*",
        "data": 1,
    }

    mock_pubsub = MagicMock()
    mock_pubsub.psubscribe = AsyncMock()

    async def _listen():
        yield subscribe_msg
        raise asyncio.CancelledError

    mock_pubsub.listen = _listen
    mock_pubsub.punsubscribe = AsyncMock()
    mock_pubsub.aclose = AsyncMock()

    mock_redis = MagicMock()
    mock_redis.pubsub.return_value = mock_pubsub
    mock_get_redis.return_value = mock_redis

    manager = MagicMock(spec=ConnectionManager)
    manager.broadcast = AsyncMock()

    await _subscribe_loop(manager)

    manager.broadcast.assert_not_called()


@pytest.mark.asyncio
@patch("app.transit.ws_subscriber.get_redis")
async def test_subscriber_handles_invalid_json(mock_get_redis: AsyncMock) -> None:
    """Invalid JSON in message data logs warning but doesn't crash."""
    bad_msg: dict[str, object] = {
        "type": "pmessage",
        "pattern": b"transit:vehicles:*",
        "channel": b"transit:vehicles:riga",
        "data": "not-valid-json{{{",
    }

    mock_pubsub = MagicMock()
    mock_pubsub.psubscribe = AsyncMock()

    async def _listen():
        yield bad_msg
        raise asyncio.CancelledError

    mock_pubsub.listen = _listen
    mock_pubsub.punsubscribe = AsyncMock()
    mock_pubsub.aclose = AsyncMock()

    mock_redis = MagicMock()
    mock_redis.pubsub.return_value = mock_pubsub
    mock_get_redis.return_value = mock_redis

    manager = MagicMock(spec=ConnectionManager)
    manager.broadcast = AsyncMock()

    # Should not raise
    await _subscribe_loop(manager)

    manager.broadcast.assert_not_called()


@pytest.mark.asyncio
@patch("app.transit.ws_subscriber.asyncio.sleep", new_callable=AsyncMock)
@patch("app.transit.ws_subscriber.get_redis")
async def test_subscriber_reconnects_on_error(
    mock_get_redis: AsyncMock,
    mock_sleep: AsyncMock,
) -> None:
    """Connection errors trigger reconnect with backoff."""
    vehicles: list[dict[str, object]] = [{"vehicle_id": "v1", "route_id": "22"}]
    msg = _make_pmessage("riga", vehicles)

    call_count = 0

    async def _get_redis_with_failure() -> MagicMock:
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise ConnectionError("Redis unavailable")
        # Second call succeeds
        mock_pubsub = MagicMock()
        mock_pubsub.psubscribe = AsyncMock()

        async def _listen():
            yield msg
            raise asyncio.CancelledError

        mock_pubsub.listen = _listen
        mock_pubsub.punsubscribe = AsyncMock()
        mock_pubsub.aclose = AsyncMock()

        mock_redis = MagicMock()
        mock_redis.pubsub.return_value = mock_pubsub
        return mock_redis

    mock_get_redis.side_effect = _get_redis_with_failure

    manager = MagicMock(spec=ConnectionManager)
    manager.broadcast = AsyncMock()

    await _subscribe_loop(manager)

    # First attempt failed (sleep called), second succeeded
    mock_sleep.assert_called_once_with(1.0)
    manager.broadcast.assert_called_once()
