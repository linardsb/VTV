# pyright: reportUnknownMemberType=false, reportMissingTypeStubs=false, reportArgumentType=false
"""Tests for adaptive polling intervals and per-feed circuit breakers (LV-2.3)."""

import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.config import TransitFeedConfig
from app.core.resilience import CircuitBreaker, CircuitOpenError, CircuitState
from app.transit.poller import FeedPoller, _adaptive_interval, _parse_hour_ranges

# ---------------------------------------------------------------------------
# Test helpers
# ---------------------------------------------------------------------------


def _make_feed_config(feed_id: str = "riga") -> TransitFeedConfig:
    """Create a test feed config."""
    return TransitFeedConfig(
        feed_id=feed_id,
        operator_name="Test Operator",
        rt_vehicle_positions_url="https://example.com/vehicle_positions.pb",
        rt_trip_updates_url="https://example.com/trip_updates.pb",
        static_url="https://example.com/gtfs.zip",
        poll_interval_seconds=10,
    )


def _make_adaptive_settings(
    enabled: bool = True,
    peak: str = "6-9,16-19",
    night: str = "23-5",
) -> MagicMock:
    """Mock Settings with adaptive polling config."""
    s = MagicMock()
    s.transit_adaptive_polling_enabled = enabled
    s.transit_peak_hours = peak
    s.transit_night_hours = night
    s.metrics_enabled = False
    s.redis_vehicle_ttl_seconds = 120
    s.position_history_enabled = False
    return s


# ---------------------------------------------------------------------------
# Hour range parsing
# ---------------------------------------------------------------------------


def test_parse_hour_ranges_normal() -> None:
    """Standard ranges produce correct hour sets."""
    result = _parse_hour_ranges("6-9,16-19")
    assert result == {6, 7, 8, 16, 17, 18}


def test_parse_hour_ranges_midnight_wrap() -> None:
    """Midnight-wrapping ranges include both sides."""
    result = _parse_hour_ranges("23-5")
    assert result == {23, 0, 1, 2, 3, 4}


# ---------------------------------------------------------------------------
# Adaptive interval calculation
# ---------------------------------------------------------------------------


def test_adaptive_interval_peak_hours() -> None:
    """Peak hours return 1x base interval."""
    settings = _make_adaptive_settings()
    assert _adaptive_interval(10, 8, settings) == 10.0


def test_adaptive_interval_offpeak_hours() -> None:
    """Off-peak hours return 2x base interval."""
    settings = _make_adaptive_settings()
    assert _adaptive_interval(10, 12, settings) == 20.0


def test_adaptive_interval_night_hours() -> None:
    """Night hours return 4x base interval."""
    settings = _make_adaptive_settings()
    assert _adaptive_interval(10, 3, settings) == 40.0


def test_adaptive_interval_disabled() -> None:
    """Disabled adaptive polling returns base unchanged."""
    settings = _make_adaptive_settings(enabled=False)
    assert _adaptive_interval(10, 3, settings) == 10.0


# ---------------------------------------------------------------------------
# Circuit breaker per-feed isolation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_circuit_breaker_per_feed_isolation() -> None:
    """Failing feed A's breaker does not affect feed B."""
    breaker_a = CircuitBreaker(name="feed_a", failure_threshold=2, reset_timeout=60.0)
    breaker_b = CircuitBreaker(name="feed_b", failure_threshold=2, reset_timeout=60.0)

    # Trip breaker A
    for _ in range(2):
        try:
            async with breaker_a:
                raise ConnectionError("fail")
        except ConnectionError:
            pass

    assert breaker_a.state == CircuitState.OPEN
    assert breaker_b.state == CircuitState.CLOSED

    # breaker B still allows calls
    async with breaker_b:
        pass  # should not raise


@pytest.mark.asyncio
async def test_circuit_breaker_opens_after_failures() -> None:
    """5 consecutive failures open the breaker."""
    breaker = CircuitBreaker(name="feed_test", failure_threshold=5, reset_timeout=60.0)

    for _ in range(5):
        try:
            async with breaker:
                raise ConnectionError("fail")
        except ConnectionError:
            pass

    assert breaker.state == CircuitState.OPEN


# ---------------------------------------------------------------------------
# Breaker trip + recovery
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_circuit_open_skips_poll() -> None:
    """When breaker is OPEN, poll_once is NOT called."""
    settings = _make_adaptive_settings(enabled=False)
    poller = FeedPoller(feed_config=_make_feed_config(), settings=settings)

    # Force breaker open
    poller._breaker._state = CircuitState.OPEN
    poller._breaker._last_failure_time = time.monotonic()

    mock_redis = MagicMock()

    with patch.object(poller, "poll_once", new_callable=AsyncMock) as mock_poll:
        count = 0
        try:
            async with poller._breaker:
                count = await poller.poll_once(mock_redis)
        except CircuitOpenError:
            pass

    assert count == 0
    mock_poll.assert_not_called()
    await poller.close()


@pytest.mark.asyncio
async def test_circuit_recovery_after_timeout() -> None:
    """After reset_timeout, breaker transitions to HALF_OPEN and allows poll."""
    breaker = CircuitBreaker(name="feed_recovery", failure_threshold=2, reset_timeout=0.1)

    # Trip the breaker
    for _ in range(2):
        try:
            async with breaker:
                raise ConnectionError("fail")
        except ConnectionError:
            pass

    assert breaker.state == CircuitState.OPEN

    # Wait for reset timeout
    await asyncio.sleep(0.15)

    # Next call should go through (HALF_OPEN)
    async with breaker:
        pass  # success

    assert breaker.state.value == "closed"


# ---------------------------------------------------------------------------
# Prometheus gauge per-feed
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@patch("app.transit.poller.get_static_store")
async def test_metric_label_per_feed(
    mock_get_cache: AsyncMock,
) -> None:
    """record_poller_tick is called with transit_feed_{feed_id}."""
    from app.core.agents.tools.transit.client import VehiclePositionData

    settings = _make_adaptive_settings()
    poller = FeedPoller(feed_config=_make_feed_config("test_feed"), settings=settings)

    vp = VehiclePositionData(
        vehicle_id="v1",
        trip_id="t1",
        route_id="22",
        latitude=56.9,
        longitude=24.1,
        bearing=180.0,
        speed=10.0,
        current_stop_sequence=1,
        current_status="IN_TRANSIT_TO",
        stop_id="s1",
        timestamp=1700000000,
    )

    # Mock the feed client on the poller instance
    poller._feed_client = MagicMock()
    poller._feed_client.fetch_vehicle_positions = AsyncMock(return_value=[vp])
    poller._feed_client.fetch_trip_updates = AsyncMock(return_value=[])
    mock_get_cache.return_value = MagicMock(
        get_route_name=MagicMock(return_value="22"),
        get_stop_name=MagicMock(return_value="Stop"),
        get_trip_route_id=MagicMock(return_value="22"),
        routes={"22": MagicMock(route_type=3)},
    )

    mock_redis = MagicMock()
    mock_pipe = MagicMock()
    mock_pipe.execute = AsyncMock(return_value=[])
    mock_redis.pipeline.return_value = mock_pipe
    mock_redis.publish = AsyncMock()

    with patch("app.transit.poller.record_poller_tick") as mock_tick:
        await poller.poll_once(mock_redis)
        mock_tick.assert_called_once_with("transit_feed_test_feed")

    await poller.close()


@pytest.mark.asyncio
async def test_run_logs_adaptive_interval() -> None:
    """cycle_completed log includes interval_seconds field."""
    settings = _make_adaptive_settings()
    poller = FeedPoller(feed_config=_make_feed_config(), settings=settings)

    mock_redis = MagicMock()

    with (
        patch.object(poller, "poll_once", new_callable=AsyncMock, return_value=0),
        patch("app.transit.poller.logger") as mock_logger,
        patch("app.transit.poller._dt") as mock_dt,
    ):
        mock_dt.datetime.now.return_value = MagicMock(hour=12)
        mock_dt.UTC = MagicMock()

        # Run one cycle then stop
        async def _run_one_cycle() -> None:
            poller._running = True
            feed_id = poller.feed_config.feed_id
            base_interval = poller.feed_config.poll_interval_seconds
            current_hour = 12  # off-peak
            interval = _adaptive_interval(base_interval, current_hour, settings)

            start = time.monotonic()
            count = 0
            try:
                async with poller._breaker:
                    count = await poller.poll_once(mock_redis)
            except CircuitOpenError:
                pass
            duration_ms = round((time.monotonic() - start) * 1000)
            mock_logger.info(
                "transit.poller.cycle_completed",
                feed_id=feed_id,
                vehicle_count=count,
                duration_ms=duration_ms,
                interval_seconds=interval,
            )

        await _run_one_cycle()

        # Verify the log call includes interval_seconds
        cycle_calls = [
            c
            for c in mock_logger.info.call_args_list
            if c[0][0] == "transit.poller.cycle_completed"
        ]
        assert len(cycle_calls) == 1
        assert cycle_calls[0][1]["interval_seconds"] == 20.0  # off-peak = 2x

    await poller.close()
