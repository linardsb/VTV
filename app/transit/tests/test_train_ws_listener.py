"""Tests for the PV train WebSocket listener."""

# pyright: reportUnknownMemberType=false, reportMissingTypeStubs=false
# pyright: reportUnknownVariableType=false, reportUnknownArgumentType=false

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.transit.train_ws_listener import (
    _listen_loop,
    _process_message,
    start_train_ws_listener,
    stop_train_ws_listener,
)

# Safety timeout for any test that calls _listen_loop (which has `while True`).
_LISTEN_LOOP_TIMEOUT = 5.0


def _make_settings() -> MagicMock:
    """Create a mock Settings object with train WS config."""
    settings = MagicMock()
    settings.train_ws_enabled = True
    settings.train_ws_url = "wss://trainmap.pv.lv/ws"
    settings.train_ws_reconnect_max_seconds = 60
    settings.redis_vehicle_ttl_seconds = 120
    settings.position_history_enabled = False
    return settings


def _make_train_message(
    train_id: str = "T101",
    lat: float = 56.95,
    lng: float = 24.11,
) -> str:
    """Create a mock train position JSON message."""
    return json.dumps(
        {
            "id": train_id,
            "lat": lat,
            "lng": lng,
            "bearing": 180.0,
            "speed": 85.5,
            "route": "Riga-Jelgava",
            "route_id": "RJ1",
            "delay": 120,
            "timestamp": 1700000000,
        }
    )


def _make_redis_mock() -> MagicMock:
    """Create a mock Redis client with pipeline support."""
    mock_pipe = MagicMock()
    mock_pipe.set = MagicMock()
    mock_pipe.delete = MagicMock()
    mock_pipe.sadd = MagicMock()
    mock_pipe.expire = MagicMock()
    mock_pipe.execute = AsyncMock()

    mock_redis = MagicMock()
    mock_redis.pipeline.return_value = mock_pipe
    mock_redis.publish = AsyncMock()
    return mock_redis


# ── _process_message tests ───────────────────────────────────────────


@pytest.mark.asyncio
async def test_process_message_writes_to_redis() -> None:
    """Valid train message writes to Redis with correct key pattern."""
    mock_redis = _make_redis_mock()
    settings = _make_settings()
    db_factory = MagicMock()

    raw = _make_train_message("T101")
    await _process_message(raw, mock_redis, db_factory, settings)

    mock_pipe = mock_redis.pipeline.return_value
    mock_pipe.set.assert_called_once()
    call_args = mock_pipe.set.call_args
    assert call_args[0][0] == "vehicle:pv_trains:T101"


@pytest.mark.asyncio
async def test_process_message_enriches_with_feed_id() -> None:
    """Enriched vehicle data contains feed_id='pv_trains' and route_type=2."""
    mock_redis = _make_redis_mock()
    settings = _make_settings()
    db_factory = MagicMock()

    raw = _make_train_message()
    await _process_message(raw, mock_redis, db_factory, settings)

    mock_pipe = mock_redis.pipeline.return_value
    call_args = mock_pipe.set.call_args
    vehicle_json = json.loads(call_args[0][1])
    assert vehicle_json["feed_id"] == "pv_trains"
    assert vehicle_json["route_type"] == 2
    assert vehicle_json["operator_name"] == "Pasažieru vilciens"


@pytest.mark.asyncio
async def test_process_message_publishes_pubsub() -> None:
    """Verify publish to transit:vehicles:pv_trains channel."""
    mock_redis = _make_redis_mock()
    settings = _make_settings()
    db_factory = MagicMock()

    raw = _make_train_message()
    await _process_message(raw, mock_redis, db_factory, settings)

    mock_redis.publish.assert_called_once()
    channel = mock_redis.publish.call_args[0][0]
    assert channel == "transit:vehicles:pv_trains"


@pytest.mark.asyncio
@patch("app.transit.repository.batch_insert_positions", new_callable=AsyncMock)
async def test_process_message_writes_history(mock_insert: AsyncMock) -> None:
    """When position_history_enabled, calls batch_insert_positions."""
    mock_redis = _make_redis_mock()
    settings = _make_settings()
    settings.position_history_enabled = True

    mock_db = AsyncMock()
    mock_ctx = AsyncMock()
    mock_ctx.__aenter__ = AsyncMock(return_value=mock_db)
    mock_ctx.__aexit__ = AsyncMock(return_value=False)
    db_factory = MagicMock(return_value=mock_ctx)

    mock_insert.return_value = 1

    raw = _make_train_message()
    await _process_message(raw, mock_redis, db_factory, settings)

    mock_insert.assert_called_once()
    records = mock_insert.call_args[0][1]
    assert len(records) == 1
    assert records[0]["feed_id"] == "pv_trains"


@pytest.mark.asyncio
async def test_process_message_invalid_json() -> None:
    """Invalid JSON logs warning but doesn't crash."""
    mock_redis = MagicMock()
    settings = _make_settings()
    db_factory = MagicMock()

    # Should not raise
    await _process_message("not json{{{", mock_redis, db_factory, settings)


@pytest.mark.asyncio
async def test_process_message_missing_fields() -> None:
    """JSON with missing required fields skips the train but doesn't crash."""
    mock_redis = _make_redis_mock()
    settings = _make_settings()
    db_factory = MagicMock()

    # Missing lat/lng
    raw = json.dumps({"id": "T101"})
    await _process_message(raw, mock_redis, db_factory, settings)

    mock_pipe = mock_redis.pipeline.return_value
    mock_pipe.set.assert_not_called()
    mock_redis.publish.assert_not_called()


# ── _listen_loop tests ───────────────────────────────────────────────


@pytest.mark.asyncio
@patch("app.core.database.get_db_context")
@patch("app.transit.train_ws_listener.get_redis", new_callable=AsyncMock)
async def test_listener_reconnects_with_backoff(
    mock_get_redis: AsyncMock,
    mock_db_context: MagicMock,
) -> None:
    """Connection errors trigger reconnect with backoff."""
    mock_get_redis.return_value = MagicMock()
    shutdown = asyncio.Event()
    sleep_calls: list[float] = []

    call_count = 0

    async def _fake_connect(*_args: object, **_kwargs: object) -> None:
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise ConnectionError("WS unavailable")
        # Signal shutdown so the loop exits after sleep
        shutdown.set()
        raise ConnectionError("WS unavailable again")

    async def _fake_sleep(seconds: float) -> None:
        sleep_calls.append(seconds)

    settings = _make_settings()

    with (
        patch("app.transit.train_ws_listener.websockets.connect", side_effect=_fake_connect),
        patch("asyncio.sleep", side_effect=_fake_sleep),
    ):
        await asyncio.wait_for(
            _listen_loop(settings, _shutdown_event=shutdown),
            timeout=_LISTEN_LOOP_TIMEOUT,
        )

    # First attempt failed, sleep called with initial backoff of 1.0
    assert sleep_calls[0] == 1.0


@pytest.mark.asyncio
@patch("app.core.database.get_db_context")
@patch("app.transit.train_ws_listener.get_redis", new_callable=AsyncMock)
async def test_listener_backoff_caps_at_max(
    mock_get_redis: AsyncMock,
    mock_db_context: MagicMock,
) -> None:
    """Backoff never exceeds train_ws_reconnect_max_seconds."""
    mock_get_redis.return_value = MagicMock()
    shutdown = asyncio.Event()
    sleep_calls: list[float] = []

    call_count = 0
    max_failures = 10

    async def _fake_connect(*_args: object, **_kwargs: object) -> None:
        nonlocal call_count
        call_count += 1
        if call_count >= max_failures:
            shutdown.set()
        raise ConnectionError("WS unavailable")

    async def _fake_sleep(seconds: float) -> None:
        sleep_calls.append(seconds)

    settings = _make_settings()
    settings.train_ws_reconnect_max_seconds = 30

    with (
        patch("app.transit.train_ws_listener.websockets.connect", side_effect=_fake_connect),
        patch("asyncio.sleep", side_effect=_fake_sleep),
    ):
        await asyncio.wait_for(
            _listen_loop(settings, _shutdown_event=shutdown),
            timeout=_LISTEN_LOOP_TIMEOUT,
        )

    # All sleep calls should be <= 30
    assert len(sleep_calls) >= max_failures - 1
    for backoff in sleep_calls:
        assert backoff <= 30.0


@pytest.mark.asyncio
@patch("app.core.database.get_db_context")
@patch("app.transit.train_ws_listener.get_redis", new_callable=AsyncMock)
async def test_listener_cancellation_exits_cleanly(
    mock_get_redis: AsyncMock,
    mock_db_context: MagicMock,
) -> None:
    """CancelledError during connect exits cleanly (no infinite loop)."""
    mock_get_redis.return_value = MagicMock()

    async def _fake_connect(*_args: object, **_kwargs: object) -> None:
        raise asyncio.CancelledError

    settings = _make_settings()

    with patch("app.transit.train_ws_listener.websockets.connect", side_effect=_fake_connect):
        await asyncio.wait_for(
            _listen_loop(settings),
            timeout=_LISTEN_LOOP_TIMEOUT,
        )


# ── start/stop tests ────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_start_creates_task() -> None:
    """start_train_ws_listener returns an asyncio.Task."""
    settings = _make_settings()

    with patch("app.transit.train_ws_listener._listen_loop", new_callable=AsyncMock):
        task = await start_train_ws_listener(settings)
        assert isinstance(task, asyncio.Task)
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass


@pytest.mark.asyncio
async def test_stop_cancels_task() -> None:
    """stop_train_ws_listener cancels and awaits the task."""
    import app.transit.train_ws_listener as module

    mock_task = AsyncMock(spec=asyncio.Task)
    mock_task.cancel = MagicMock()
    mock_task.__await__ = MagicMock(return_value=iter([]))

    module._listener_task = mock_task  # pyright: ignore[reportAttributeAccessIssue]

    await stop_train_ws_listener()

    mock_task.cancel.assert_called_once()
    assert module._listener_task is None


# ── resilience tests ─────────────────────────────────────────────────


@pytest.mark.asyncio
@patch(
    "app.transit.repository.batch_insert_positions",
    new_callable=AsyncMock,
    side_effect=RuntimeError("DB connection failed"),
)
async def test_history_write_failure_non_blocking(mock_insert: AsyncMock) -> None:
    """batch_insert_positions failure doesn't prevent Redis write."""
    _ = mock_insert  # ARG001: consumed by decorator
    mock_redis = _make_redis_mock()
    settings = _make_settings()
    settings.position_history_enabled = True

    mock_db = AsyncMock()
    mock_ctx = AsyncMock()
    mock_ctx.__aenter__ = AsyncMock(return_value=mock_db)
    mock_ctx.__aexit__ = AsyncMock(return_value=False)
    db_factory = MagicMock(return_value=mock_ctx)

    raw = _make_train_message()
    await _process_message(raw, mock_redis, db_factory, settings)

    mock_pipe = mock_redis.pipeline.return_value
    mock_pipe.set.assert_called_once()
    mock_pipe.execute.assert_called_once()
    mock_redis.publish.assert_called_once()
