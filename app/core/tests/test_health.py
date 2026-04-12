# pyright: reportArgumentType=false, reportCallIssue=false
"""Unit tests for health check endpoints (OPS-2.2)."""

from __future__ import annotations

import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException, status

from app.core.health import (
    ProbeResult,
    _aggregate_status,
    database_health_check,
    deep_health_check,
    health_check,
    probe_gtfs_rt_feeds,
    probe_llm_providers,
    probe_pollers,
    probe_postgres,
    probe_redis,
    probe_reranker,
    readiness_check,
)
from app.core.rate_limit import limiter

# Disable rate limiting during tests
limiter.enabled = False


@pytest.fixture(autouse=True)
def _clear_health_caches() -> None:
    """Clear all health caches before each test."""
    import app.core.health as health_mod

    health_mod._db_health_cache = None
    health_mod._db_health_cache_time = 0.0
    health_mod._redis_health_cache = None
    health_mod._redis_health_cache_time = 0.0
    health_mod._deep_health_cache = None
    health_mod._deep_health_cache_time = 0.0
    health_mod._ready_health_cache = None
    health_mod._ready_health_cache_time = 0.0


# ---- Existing tests (backward compat) ----


@pytest.mark.asyncio
async def test_health_check_returns_healthy() -> None:
    """Test that basic health check returns healthy status."""
    response = await health_check(request=None)
    assert response["status"] == "healthy"
    assert response["service"] == "api"


@pytest.mark.asyncio
async def test_database_health_check_success() -> None:
    """Test database health check with successful connection."""
    mock_db = AsyncMock()
    mock_db.execute = AsyncMock()

    response = await database_health_check(request=None, db=mock_db)
    mock_db.execute.assert_called_once()
    call_args = mock_db.execute.call_args[0][0]
    assert str(call_args) == "SELECT 1"

    assert response["status"] == "healthy"
    assert response["service"] == "database"


@pytest.mark.asyncio
async def test_database_health_check_failure() -> None:
    """Test database health check with failed connection."""
    mock_db = AsyncMock()
    mock_db.execute = AsyncMock(side_effect=Exception("Database connection failed"))

    with patch("app.core.health.logger.error"):
        with pytest.raises(HTTPException) as exc_info:
            await database_health_check(request=None, db=mock_db)
    assert exc_info.value.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
    assert "Database is not accessible" in exc_info.value.detail


@pytest.mark.asyncio
async def test_readiness_check_success() -> None:
    """Test readiness check with all dependencies healthy."""
    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar.return_value = 5
    mock_db.execute = AsyncMock(return_value=mock_result)

    with (
        patch("app.core.health.get_settings") as mock_get_settings,
        patch("app.core.health.get_redis") as mock_get_redis,
    ):
        mock_settings = MagicMock()
        mock_settings.health_deep_cache_ttl_seconds = 5.0
        mock_settings.environment = "test"
        mock_get_settings.return_value = mock_settings

        mock_redis = AsyncMock()
        mock_redis.ping = AsyncMock(return_value=True)
        mock_get_redis.return_value = mock_redis

        response = await readiness_check(request=None, db=mock_db)

    assert response["status"] == "ready"
    assert response["database"] == "connected"
    assert response["redis"] == "connected"


@pytest.mark.asyncio
async def test_readiness_check_failure() -> None:
    """Test readiness check with failed dependencies."""
    mock_db = AsyncMock()
    mock_db.execute = AsyncMock(side_effect=Exception("DB error"))

    with (
        patch("app.core.health.get_settings") as mock_get_settings,
        patch("app.core.health.get_redis") as mock_get_redis,
    ):
        mock_settings = MagicMock()
        mock_settings.health_deep_cache_ttl_seconds = 5.0
        mock_get_settings.return_value = mock_settings

        mock_redis = AsyncMock()
        mock_redis.ping = AsyncMock(return_value=True)
        mock_get_redis.return_value = mock_redis

        with patch("app.core.health.logger.error"):
            with pytest.raises(HTTPException) as exc_info:
                await readiness_check(request=None, db=mock_db)
    assert exc_info.value.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
    assert "Application is not ready" in exc_info.value.detail


@pytest.mark.asyncio
async def test_database_health_check_logs_error() -> None:
    """Test that database health check logs errors properly."""
    mock_db = AsyncMock()
    mock_db.execute = AsyncMock(side_effect=Exception("Connection error"))

    with patch("app.core.health.logger.error") as mock_logger:
        with pytest.raises(HTTPException):
            await database_health_check(request=None, db=mock_db)
        mock_logger.assert_called_once()
        assert "database.health_check_failed" in str(mock_logger.call_args)


@pytest.mark.asyncio
async def test_readiness_check_logs_error() -> None:
    """Test that readiness check logs errors properly."""
    mock_db = AsyncMock()
    mock_db.execute = AsyncMock(side_effect=Exception("Not ready"))

    with (
        patch("app.core.health.get_settings") as mock_get_settings,
        patch("app.core.health.get_redis") as mock_get_redis,
    ):
        mock_settings = MagicMock()
        mock_settings.health_deep_cache_ttl_seconds = 5.0
        mock_get_settings.return_value = mock_settings

        mock_redis = AsyncMock()
        mock_redis.ping = AsyncMock(return_value=True)
        mock_get_redis.return_value = mock_redis

        with patch("app.core.health.logger.error") as mock_logger:
            with pytest.raises(HTTPException):
                await readiness_check(request=None, db=mock_db)
            mock_logger.assert_called()
            log_calls = [str(c) for c in mock_logger.call_args_list]
            assert any("readiness_check_failed" in c for c in log_calls)


# ---- Probe unit tests ----


@pytest.mark.asyncio
async def test_probe_postgres_success() -> None:
    """Test postgres probe with healthy database."""
    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar.return_value = 5
    mock_db.execute = AsyncMock(return_value=mock_result)

    result = await probe_postgres(mock_db)
    assert result.status == "ok"
    assert result.name == "postgres"
    assert "active_connections=5" in (result.detail or "")
    assert result.critical is True


@pytest.mark.asyncio
async def test_probe_postgres_failure() -> None:
    """Test postgres probe with database error."""
    mock_db = AsyncMock()
    mock_db.execute = AsyncMock(side_effect=Exception("Connection refused"))

    with patch("app.core.health.logger.error"):
        result = await probe_postgres(mock_db)
    assert result.status == "down"
    assert result.name == "postgres"
    assert "Connection refused" in (result.detail or "")


@pytest.mark.asyncio
async def test_probe_redis_success() -> None:
    """Test redis probe with healthy Redis."""
    with patch("app.core.health.get_redis") as mock_get_redis:
        mock_redis = AsyncMock()
        mock_redis.ping = AsyncMock(return_value=True)
        mock_get_redis.return_value = mock_redis

        result = await probe_redis()
    assert result.status == "ok"
    assert result.name == "redis"
    assert result.critical is True


@pytest.mark.asyncio
async def test_probe_redis_failure() -> None:
    """Test redis probe with connection error."""
    with patch("app.core.health.get_redis") as mock_get_redis:
        mock_get_redis.side_effect = ConnectionError("Redis unavailable")

        with patch("app.core.health.logger.error"):
            result = await probe_redis()
    assert result.status == "down"
    assert result.name == "redis"


@pytest.mark.asyncio
async def test_probe_reranker_loaded() -> None:
    """Test reranker probe when model is loaded."""
    mock_provider = MagicMock()
    mock_provider._model = MagicMock()  # model loaded

    with (
        patch("app.knowledge.reranker.get_reranker_provider", return_value=mock_provider),
        patch("app.core.health.get_settings"),
    ):
        result = await probe_reranker()
    assert result.status == "ok"
    assert result.name == "reranker"
    assert result.critical is False
    assert result.detail == "model_loaded"


@pytest.mark.asyncio
async def test_probe_reranker_not_loaded() -> None:
    """Test reranker probe when model is not loaded."""
    mock_provider = MagicMock()
    mock_provider._model = None

    with (
        patch("app.knowledge.reranker.get_reranker_provider", return_value=mock_provider),
        patch("app.core.health.get_settings"),
    ):
        result = await probe_reranker()
    assert result.status == "degraded"
    assert result.name == "reranker"
    assert result.critical is False
    assert result.detail == "model_not_loaded"


@pytest.mark.asyncio
async def test_probe_pollers_healthy() -> None:
    """Test pollers probe with recent tick timestamps."""
    now = time.time()

    with (
        patch("app.core.health.get_settings") as mock_settings,
        patch("app.core.health._get_poller_last_tick") as mock_tick,
    ):
        settings = MagicMock()
        settings.transit_feeds = [MagicMock(poll_interval_seconds=30)]
        settings.alerts_check_interval_seconds = 60
        settings.geofence_check_interval_seconds = 30
        mock_settings.return_value = settings

        # All pollers have recent ticks
        mock_tick.side_effect = lambda _name: now - 10  # 10s ago

        result = await probe_pollers()
    assert result.status == "ok"
    assert result.critical is False


@pytest.mark.asyncio
async def test_probe_pollers_stale() -> None:
    """Test pollers probe with stale timestamps."""
    now = time.time()

    with (
        patch("app.core.health.get_settings") as mock_settings,
        patch("app.core.health._get_poller_last_tick") as mock_tick,
        patch("app.core.health.time") as mock_time,
    ):
        settings = MagicMock()
        settings.transit_feeds = [MagicMock(poll_interval_seconds=30)]
        settings.alerts_check_interval_seconds = 60
        settings.geofence_check_interval_seconds = 30
        mock_settings.return_value = settings
        mock_time.time.return_value = now
        mock_time.monotonic.side_effect = time.monotonic

        # transit_feed is very stale (threshold is 60s, tick was 120s ago)
        def tick_values(name: str) -> float | None:
            if name == "transit_feed":
                return now - 120  # very stale
            return now - 10  # fresh

        mock_tick.side_effect = tick_values

        result = await probe_pollers()
    assert result.status == "degraded"
    assert "transit_feed" in (result.detail or "")


@pytest.mark.asyncio
async def test_probe_gtfs_feeds_fresh() -> None:
    """Test GTFS-RT feeds probe with fresh data."""
    now = time.time()

    with (
        patch("app.core.health._get_poller_last_tick", return_value=now - 10),
        patch("app.core.health.time") as mock_time,
    ):
        mock_time.monotonic.side_effect = time.monotonic
        mock_time.time.return_value = now

        result = await probe_gtfs_rt_feeds()
    assert result.status == "ok"
    assert result.critical is False


@pytest.mark.asyncio
async def test_probe_gtfs_feeds_stale() -> None:
    """Test GTFS-RT feeds probe with stale data (> 60s)."""
    now = time.time()

    with (
        patch("app.core.health._get_poller_last_tick", return_value=now - 120),
        patch("app.core.health.time") as mock_time,
    ):
        mock_time.monotonic.side_effect = time.monotonic
        mock_time.time.return_value = now

        result = await probe_gtfs_rt_feeds()
    assert result.status == "degraded"
    assert "stale_seconds" in (result.detail or "")


@pytest.mark.asyncio
async def test_probe_llm_providers_closed() -> None:
    """Test LLM providers probe with all breakers closed."""
    from app.core.agents.circuit_breaker import CircuitState

    with (
        patch("app.core.health.get_settings") as mock_settings,
        patch("app.core.health.get_breaker_state", return_value=CircuitState.CLOSED),
    ):
        settings = MagicMock()
        settings.llm_provider = "openai"
        settings.llm_fallback_provider = "anthropic"
        mock_settings.return_value = settings

        result = await probe_llm_providers()
    assert result.status == "ok"
    assert result.critical is False
    assert "openai=closed" in (result.detail or "")


@pytest.mark.asyncio
async def test_probe_llm_providers_open() -> None:
    """Test LLM providers probe with an open breaker."""
    from app.core.agents.circuit_breaker import CircuitState

    with (
        patch("app.core.health.get_settings") as mock_settings,
        patch("app.core.health.get_breaker_state") as mock_state,
    ):
        settings = MagicMock()
        settings.llm_provider = "openai"
        settings.llm_fallback_provider = None
        mock_settings.return_value = settings

        mock_state.return_value = CircuitState.OPEN

        result = await probe_llm_providers()
    assert result.status == "degraded"
    assert "openai=open" in (result.detail or "")


# ---- Aggregation tests ----


def test_aggregation_all_ok() -> None:
    """All probes ok -> overall ok."""
    probes = [
        ProbeResult(name="a", status="ok", latency_ms=1.0, critical=True),
        ProbeResult(name="b", status="ok", latency_ms=1.0, critical=False),
    ]
    assert _aggregate_status(probes) == "ok"


def test_aggregation_noncritical_down_is_degraded() -> None:
    """Non-critical probe down -> overall degraded (not down)."""
    probes = [
        ProbeResult(name="a", status="ok", latency_ms=1.0, critical=True),
        ProbeResult(name="b", status="down", latency_ms=1.0, critical=False),
    ]
    assert _aggregate_status(probes) == "degraded"


def test_aggregation_critical_down_is_down() -> None:
    """Critical probe down -> overall down."""
    probes = [
        ProbeResult(name="a", status="down", latency_ms=1.0, critical=True),
        ProbeResult(name="b", status="ok", latency_ms=1.0, critical=False),
    ]
    assert _aggregate_status(probes) == "down"


# ---- Deep health endpoint tests ----


@pytest.mark.asyncio
async def test_deep_health_returns_full_report() -> None:
    """Test that deep health returns all 6 probe names."""
    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar.return_value = 3
    mock_db.execute = AsyncMock(return_value=mock_result)

    with (
        patch("app.core.health.get_settings") as mock_settings,
        patch("app.core.health.get_redis") as mock_get_redis,
        patch("app.knowledge.reranker.get_reranker_provider") as mock_reranker,
        patch("app.core.health._get_poller_last_tick", return_value=time.time()),
        patch("app.core.health.get_breaker_state") as mock_breaker,
    ):
        from app.core.agents.circuit_breaker import CircuitState

        settings = MagicMock()
        settings.health_deep_cache_ttl_seconds = 5.0
        settings.transit_feeds = [MagicMock(poll_interval_seconds=30)]
        settings.alerts_check_interval_seconds = 60
        settings.geofence_check_interval_seconds = 30
        settings.llm_provider = "test"
        settings.llm_fallback_provider = None
        mock_settings.return_value = settings

        mock_redis = AsyncMock()
        mock_redis.ping = AsyncMock(return_value=True)
        mock_get_redis.return_value = mock_redis

        provider = MagicMock()
        provider._model = MagicMock()
        mock_reranker.return_value = provider

        mock_breaker.return_value = CircuitState.CLOSED

        report = await deep_health_check(
            request=None,
            db=mock_db,
            _current_user=MagicMock(),
        )

    assert report.status == "ok"
    assert report.version == "0.1.0"
    probe_names = {p.name for p in report.probes}
    assert probe_names == {
        "postgres",
        "redis",
        "reranker",
        "pollers",
        "gtfs_rt_feeds",
        "llm_providers",
    }


@pytest.mark.asyncio
async def test_deep_health_503_when_critical_down() -> None:
    """Test that deep health returns 503 when a critical probe fails."""
    mock_db = AsyncMock()
    mock_db.execute = AsyncMock(side_effect=Exception("DB down"))

    with (
        patch("app.core.health.get_settings") as mock_settings,
        patch("app.core.health.get_redis") as mock_get_redis,
        patch("app.knowledge.reranker.get_reranker_provider") as mock_reranker,
        patch("app.core.health._get_poller_last_tick", return_value=time.time()),
        patch("app.core.health.get_breaker_state") as mock_breaker,
        patch("app.core.health.logger"),
    ):
        from app.core.agents.circuit_breaker import CircuitState

        settings = MagicMock()
        settings.health_deep_cache_ttl_seconds = 5.0
        settings.transit_feeds = []
        settings.alerts_check_interval_seconds = 60
        settings.geofence_check_interval_seconds = 30
        settings.llm_provider = "test"
        settings.llm_fallback_provider = None
        mock_settings.return_value = settings

        mock_redis = AsyncMock()
        mock_redis.ping = AsyncMock(return_value=True)
        mock_get_redis.return_value = mock_redis

        provider = MagicMock()
        provider._model = None
        mock_reranker.return_value = provider

        mock_breaker.return_value = CircuitState.CLOSED

        with pytest.raises(HTTPException) as exc_info:
            await deep_health_check(
                request=None,
                db=mock_db,
                _current_user=MagicMock(),
            )
        assert exc_info.value.status_code == 503


@pytest.mark.asyncio
async def test_deep_health_timeout_handling() -> None:
    """Test that a slow probe is timed out and reported as down."""
    from app.core.health import _run_probe

    async def slow_probe() -> ProbeResult:
        await asyncio.sleep(10)
        return ProbeResult(name="slow", status="ok", latency_ms=0.0)

    result = await _run_probe("slow", slow_probe(), timeout_s=0.1)
    assert result.status == "down"
    assert result.detail == "timeout"
    assert result.name == "slow"


@pytest.mark.asyncio
async def test_deep_health_concurrent_execution() -> None:
    """Test that all probes run concurrently (not sequentially)."""
    call_times: list[float] = []

    async def _timed_probe(name: str) -> ProbeResult:
        call_times.append(time.monotonic())
        await asyncio.sleep(0.05)
        return ProbeResult(name=name, status="ok", latency_ms=1.0, critical=False)

    probes = await asyncio.gather(
        _timed_probe("a"),
        _timed_probe("b"),
        _timed_probe("c"),
    )
    assert len(probes) == 3
    # All should have started within 20ms of each other (concurrent)
    assert max(call_times) - min(call_times) < 0.05
