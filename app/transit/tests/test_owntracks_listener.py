"""Tests for the OwnTracks MQTT listener."""

# pyright: reportUnknownMemberType=false, reportMissingTypeStubs=false
# pyright: reportUnknownVariableType=false, reportUnknownArgumentType=false

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.transit.owntracks_listener import (
    _get_assignment,
    _phone_id_from_topic,
    _process_message,
    start_owntracks_listener,
    stop_owntracks_listener,
)


def _make_settings() -> MagicMock:
    """Create a mock Settings object with OwnTracks config."""
    settings = MagicMock()
    settings.owntracks_mqtt_enabled = True
    settings.owntracks_mqtt_broker_url = "mqtt://localhost:1883"
    settings.owntracks_mqtt_username = "vtv"
    settings.owntracks_mqtt_password = "test"  # pragma: allowlist secret
    settings.owntracks_mqtt_topic_filter = "owntracks/+/+"
    settings.owntracks_mqtt_reconnect_max_seconds = 60
    settings.redis_vehicle_ttl_seconds = 120
    settings.position_history_enabled = False
    return settings


def _make_owntracks_payload(
    lat: float = 56.95,
    lon: float = 24.11,
    vel: int = 45,
    cog: int = 180,
    tst: int = 1700000000,
) -> bytes:
    """Create a valid OwnTracks location JSON payload."""
    return json.dumps(
        {
            "_type": "location",
            "lat": lat,
            "lon": lon,
            "vel": vel,
            "cog": cog,
            "tst": tst,
            "acc": 10,
        }
    ).encode()


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


def _make_assignment(
    vehicle_id: int = 42,
    route_id: int | None = 101,
    phone_identifier: str = "user1_phone",
) -> MagicMock:
    """Create a mock VehiclePhoneAssignment."""
    assignment = MagicMock()
    assignment.vehicle_id = vehicle_id
    assignment.route_id = route_id
    assignment.phone_identifier = phone_identifier
    assignment.active = True
    return assignment


# ── _phone_id_from_topic tests ──────────────────────────────────────


def test_phone_id_from_topic() -> None:
    """Extracts user_device from owntracks/user/device topic."""
    assert _phone_id_from_topic("owntracks/user1/phone") == "user1_phone"


def test_phone_id_from_topic_nested() -> None:
    """Handles deeper topic paths by using last two segments."""
    assert _phone_id_from_topic("owntracks/org/user1/phone") == "user1_phone"


# ── _process_message tests ──────────────────────────────────────────


@pytest.mark.asyncio
async def test_process_message_valid_location() -> None:
    """Valid OwnTracks location writes to Redis with correct key pattern."""
    mock_redis = _make_redis_mock()
    settings = _make_settings()
    assignment = _make_assignment()

    db_factory = MagicMock()
    topic = "owntracks/user1/phone"

    with patch(
        "app.transit.owntracks_listener._get_assignment",
        new_callable=AsyncMock,
        return_value=assignment,
    ):
        await _process_message(topic, _make_owntracks_payload(), mock_redis, db_factory, settings)

    pipe = mock_redis.pipeline.return_value
    pipe.set.assert_called_once()
    call_args = pipe.set.call_args
    key = call_args[0][0]
    assert key == "vehicle:owntracks:42"
    pipe.execute.assert_awaited_once()


@pytest.mark.asyncio
async def test_process_message_non_location_skipped() -> None:
    """Non-location message types are silently skipped."""
    mock_redis = _make_redis_mock()
    settings = _make_settings()
    db_factory = MagicMock()

    payload = json.dumps({"_type": "transition", "event": "enter"}).encode()
    await _process_message("owntracks/user1/phone", payload, mock_redis, db_factory, settings)

    mock_redis.pipeline.assert_not_called()


@pytest.mark.asyncio
async def test_process_message_missing_coords_skipped() -> None:
    """Message without lat/lon is skipped with warning."""
    mock_redis = _make_redis_mock()
    settings = _make_settings()
    db_factory = MagicMock()

    payload = json.dumps({"_type": "location", "vel": 50}).encode()
    await _process_message("owntracks/user1/phone", payload, mock_redis, db_factory, settings)

    mock_redis.pipeline.assert_not_called()


@pytest.mark.asyncio
async def test_process_message_no_assignment_skipped() -> None:
    """Unknown phone identifier logs warning and skips."""
    mock_redis = _make_redis_mock()
    settings = _make_settings()
    db_factory = MagicMock()

    with patch(
        "app.transit.owntracks_listener._get_assignment",
        new_callable=AsyncMock,
        return_value=None,
    ):
        await _process_message(
            "owntracks/unknown/device",
            _make_owntracks_payload(),
            mock_redis,
            db_factory,
            settings,
        )

    mock_redis.pipeline.assert_not_called()


@pytest.mark.asyncio
async def test_process_message_writes_timescaledb() -> None:
    """With position_history_enabled, batch_insert_positions is called."""
    mock_redis = _make_redis_mock()
    settings = _make_settings()
    settings.position_history_enabled = True
    assignment = _make_assignment()

    mock_db = AsyncMock()
    mock_ctx = MagicMock()
    mock_ctx.__aenter__ = AsyncMock(return_value=mock_db)
    mock_ctx.__aexit__ = AsyncMock(return_value=False)
    db_factory = MagicMock(return_value=mock_ctx)

    with (
        patch(
            "app.transit.owntracks_listener._get_assignment",
            new_callable=AsyncMock,
            return_value=assignment,
        ),
        patch(
            "app.transit.repository.batch_insert_positions",
            new_callable=AsyncMock,
            return_value=1,
        ) as mock_insert,
    ):
        await _process_message(
            "owntracks/user1/phone",
            _make_owntracks_payload(),
            mock_redis,
            db_factory,
            settings,
        )

    mock_insert.assert_awaited_once()
    records = mock_insert.call_args[0][1]
    assert records[0]["source"] == "owntracks"


@pytest.mark.asyncio
async def test_process_message_db_failure_nonfatal() -> None:
    """DB write failure doesn't prevent Redis write."""
    mock_redis = _make_redis_mock()
    settings = _make_settings()
    settings.position_history_enabled = True
    assignment = _make_assignment()

    mock_ctx = MagicMock()
    mock_ctx.__aenter__ = AsyncMock(side_effect=RuntimeError("db down"))
    mock_ctx.__aexit__ = AsyncMock(return_value=False)
    db_factory = MagicMock(return_value=mock_ctx)

    with patch(
        "app.transit.owntracks_listener._get_assignment",
        new_callable=AsyncMock,
        return_value=assignment,
    ):
        await _process_message(
            "owntracks/user1/phone",
            _make_owntracks_payload(),
            mock_redis,
            db_factory,
            settings,
        )

    # Redis write still happened
    pipe = mock_redis.pipeline.return_value
    pipe.execute.assert_awaited_once()


@pytest.mark.asyncio
async def test_process_message_publishes_pubsub() -> None:
    """Message is published to Redis Pub/Sub channel."""
    mock_redis = _make_redis_mock()
    settings = _make_settings()
    assignment = _make_assignment()
    db_factory = MagicMock()

    with patch(
        "app.transit.owntracks_listener._get_assignment",
        new_callable=AsyncMock,
        return_value=assignment,
    ):
        await _process_message(
            "owntracks/user1/phone",
            _make_owntracks_payload(),
            mock_redis,
            db_factory,
            settings,
        )

    mock_redis.publish.assert_awaited_once()
    channel = mock_redis.publish.call_args[0][0]
    assert channel == "transit:vehicles:owntracks"


@pytest.mark.asyncio
async def test_speed_conversion() -> None:
    """OwnTracks vel (km/h) is mapped to speed_kmh correctly."""
    mock_redis = _make_redis_mock()
    settings = _make_settings()
    assignment = _make_assignment()
    db_factory = MagicMock()

    with patch(
        "app.transit.owntracks_listener._get_assignment",
        new_callable=AsyncMock,
        return_value=assignment,
    ):
        await _process_message(
            "owntracks/user1/phone",
            _make_owntracks_payload(vel=85),
            mock_redis,
            db_factory,
            settings,
        )

    pipe = mock_redis.pipeline.return_value
    stored_json = pipe.set.call_args[0][1]
    stored = json.loads(stored_json)
    assert stored["speed_kmh"] == 85.0


@pytest.mark.asyncio
async def test_coords_out_of_bounds_skipped() -> None:
    """Coordinates outside Latvia bounding box are skipped."""
    mock_redis = _make_redis_mock()
    settings = _make_settings()
    db_factory = MagicMock()

    # Coordinates in Berlin, not Latvia
    payload = _make_owntracks_payload(lat=52.52, lon=13.40)
    await _process_message("owntracks/user1/phone", payload, mock_redis, db_factory, settings)

    mock_redis.pipeline.assert_not_called()


# ── Assignment cache tests ──────────────────────────────────────────


@pytest.mark.asyncio
async def test_assignment_cache_hit() -> None:
    """Second call within TTL doesn't query DB."""
    assignment = _make_assignment()

    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = assignment
    mock_db.execute = AsyncMock(return_value=mock_result)

    mock_ctx = MagicMock()
    mock_ctx.__aenter__ = AsyncMock(return_value=mock_db)
    mock_ctx.__aexit__ = AsyncMock(return_value=False)
    db_factory = MagicMock(return_value=mock_ctx)

    # Clear cache before test
    from app.transit.owntracks_listener import _assignment_cache

    _assignment_cache.clear()

    # First call — hits DB
    result1 = await _get_assignment("user1_phone", db_factory)
    assert result1 is assignment
    assert db_factory.call_count == 1

    # Second call — uses cache
    result2 = await _get_assignment("user1_phone", db_factory)
    assert result2 is assignment
    assert db_factory.call_count == 1  # Still 1, no second DB call


# ── Lifecycle tests ─────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_start_creates_task() -> None:
    """start_owntracks_listener returns an asyncio.Task."""
    settings = _make_settings()

    with patch("app.transit.owntracks_listener._listen_loop", new_callable=AsyncMock):
        task = await start_owntracks_listener(settings)
        assert isinstance(task, asyncio.Task)
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass


@pytest.mark.asyncio
async def test_stop_cancels_task() -> None:
    """stop_owntracks_listener cancels and clears the module-level task."""
    import app.transit.owntracks_listener as mod

    mock_task = AsyncMock(spec=asyncio.Task)
    mock_task.cancel = MagicMock()
    mod._listener_task = mock_task

    await stop_owntracks_listener()

    mock_task.cancel.assert_called_once()
    assert mod._listener_task is None
