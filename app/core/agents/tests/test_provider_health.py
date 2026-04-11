"""Tests for AI-8.2 per-provider health tracker + admin endpoint."""

from collections.abc import Generator
from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from app.auth.dependencies import get_current_user
from app.auth.models import User
from app.core.agents.circuit_breaker import CircuitState
from app.core.agents.provider_health import (
    ProviderHealthTracker,
    _extract_provider_name,
    get_provider_health_tracker,
    reset_provider_health_tracker,
)
from app.core.rate_limit import limiter
from app.main import app

limiter.enabled = False


def _mock_admin_user() -> User:
    user = MagicMock(spec=User)
    user.id = 1
    user.email = "admin@vtv.lv"
    user.role = "admin"
    user.is_active = True
    return user


def _mock_dispatcher_user() -> User:
    user = MagicMock(spec=User)
    user.id = 2
    user.email = "dispatcher@vtv.lv"
    user.role = "dispatcher"
    user.is_active = True
    return user


@pytest.fixture(autouse=True)
def _reset_singleton() -> Generator[None, None, None]:
    reset_provider_health_tracker()
    yield
    reset_provider_health_tracker()


@pytest.fixture
def _admin_override() -> Generator[None, None, None]:
    app.dependency_overrides[get_current_user] = _mock_admin_user
    try:
        yield
    finally:
        app.dependency_overrides.pop(get_current_user, None)


# ----- Tracker unit tests -----


def test_tracker_starts_empty() -> None:
    tracker = ProviderHealthTracker()
    assert tracker.get_all() == []


def test_record_success_increments_total_calls() -> None:
    tracker = ProviderHealthTracker()
    tracker.record_call("anthropic", latency_ms=120.0, success=True)
    health = tracker.get_health("anthropic")
    assert health is not None
    assert health.total_calls == 1
    assert health.total_failures == 0
    assert health.last_success_at is not None
    assert health.last_failure_at is None


def test_record_failure_sets_last_failure_at() -> None:
    tracker = ProviderHealthTracker()
    tracker.record_call("google", latency_ms=55.0, success=False)
    health = tracker.get_health("google")
    assert health is not None
    assert health.total_calls == 1
    assert health.total_failures == 1
    assert health.last_failure_at is not None
    assert health.last_success_at is None


def test_mixed_calls_compute_failure_rate() -> None:
    tracker = ProviderHealthTracker()
    tracker.record_call("groq", latency_ms=10.0, success=True)
    tracker.record_call("groq", latency_ms=20.0, success=True)
    tracker.record_call("groq", latency_ms=30.0, success=True)
    tracker.record_call("groq", latency_ms=40.0, success=False)
    health = tracker.get_health("groq")
    assert health is not None
    assert health.total_calls == 4
    assert health.total_failures == 1
    assert health.failure_rate == 0.25


def test_p50_p95_none_below_two_observations() -> None:
    tracker = ProviderHealthTracker()
    tracker.record_call("anthropic", latency_ms=100.0, success=True)
    health = tracker.get_health("anthropic")
    assert health is not None
    assert health.p50_latency_ms is None
    assert health.p95_latency_ms is None


def test_p50_p95_quantile_correctness() -> None:
    tracker = ProviderHealthTracker()
    for latency in range(1, 101):
        tracker.record_call("anthropic", latency_ms=float(latency), success=True)
    health = tracker.get_health("anthropic")
    assert health is not None
    assert health.p50_latency_ms is not None
    assert health.p95_latency_ms is not None
    assert abs(health.p50_latency_ms - 50.0) <= 1.0
    assert abs(health.p95_latency_ms - 95.0) <= 1.0


def test_latency_window_bounded_at_100() -> None:
    tracker = ProviderHealthTracker()
    for latency in range(1, 151):
        tracker.record_call("anthropic", latency_ms=float(latency), success=True)
    health = tracker.get_health("anthropic")
    assert health is not None
    # total_calls keeps counting past the window.
    assert health.total_calls == 150
    # The deque is capped at 100 observations.
    assert len(health._latencies_ms) == 100
    # Latencies 51..150 survive; the p50 of that window is ~100.
    assert health.p50_latency_ms is not None
    assert abs(health.p50_latency_ms - 100.0) <= 1.0


def test_daily_reset_clears_counters_on_utc_rollover() -> None:
    fake_now = datetime(2026, 4, 11, 12, 0, tzinfo=UTC)

    def clock() -> datetime:
        return fake_now

    tracker = ProviderHealthTracker(clock=clock)
    tracker.record_call("anthropic", latency_ms=120.0, success=True)
    assert len(tracker.get_all()) == 1

    fake_now = fake_now + timedelta(days=1)
    assert tracker.get_all() == []
    assert tracker.period_start().date() == fake_now.date()


def test_get_all_deep_copies_state() -> None:
    tracker = ProviderHealthTracker()
    tracker.record_call("anthropic", latency_ms=120.0, success=True)
    snapshot_list = tracker.get_all()
    assert len(snapshot_list) == 1
    snapshot = snapshot_list[0]
    snapshot.total_calls = 999
    snapshot._latencies_ms.append(9999.0)

    live = tracker.get_health("anthropic")
    assert live is not None
    assert live.total_calls == 1
    assert 9999.0 not in live._latencies_ms


# ----- provider name extraction helper -----


def test_extract_provider_name_from_string() -> None:
    assert _extract_provider_name("anthropic:claude-sonnet-4", "test") == "anthropic"
    assert _extract_provider_name("google:gemini-2.5-pro", "test") == "google"


def test_extract_provider_name_from_none() -> None:
    assert _extract_provider_name(None, "test") == "test"


def test_extract_provider_name_from_model_instance() -> None:
    fake_model = MagicMock()
    fake_model.__class__.__name__ = "AnthropicModel"
    assert _extract_provider_name(fake_model, "test") == "anthropic"


def test_extract_provider_name_from_empty_string_falls_back_to_default() -> None:
    assert _extract_provider_name("", "anthropic") == "anthropic"


# ----- singleton lifecycle -----


def test_singleton_reuse_returns_same_instance() -> None:
    first = get_provider_health_tracker()
    second = get_provider_health_tracker()
    assert first is second


def test_reset_provider_health_tracker_forces_new_instance() -> None:
    first = get_provider_health_tracker()
    reset_provider_health_tracker()
    second = get_provider_health_tracker()
    assert first is not second


# ----- Endpoint tests -----


def test_provider_health_endpoint_returns_empty_when_no_calls(
    _admin_override: None,
) -> None:
    with TestClient(app) as client:
        response = client.get("/v1/chat/provider-health")
    assert response.status_code == 200
    body = response.json()
    assert body["providers"] == []
    assert "period_start" in body
    assert "generated_at" in body


def test_provider_health_endpoint_returns_recorded_providers(
    _admin_override: None,
) -> None:
    tracker = get_provider_health_tracker()
    tracker.record_call("anthropic", latency_ms=100.0, success=True)
    tracker.record_call("anthropic", latency_ms=120.0, success=True)
    tracker.record_call("google", latency_ms=200.0, success=False)
    tracker.record_call("groq", latency_ms=40.0, success=True)
    tracker.record_call("groq", latency_ms=60.0, success=True)

    with TestClient(app) as client:
        response = client.get("/v1/chat/provider-health")
    assert response.status_code == 200
    body = response.json()

    by_name = {p["provider_name"]: p for p in body["providers"]}
    assert set(by_name) == {"anthropic", "google", "groq"}
    # Sorted alphabetically.
    assert [p["provider_name"] for p in body["providers"]] == [
        "anthropic",
        "google",
        "groq",
    ]
    assert by_name["anthropic"]["total_calls"] == 2
    assert by_name["anthropic"]["total_failures"] == 0
    assert by_name["anthropic"]["failure_rate"] == 0.0
    assert by_name["anthropic"]["state"] == "closed"
    assert by_name["google"]["total_failures"] == 1
    assert by_name["google"]["failure_rate"] == 1.0
    assert by_name["groq"]["p50_latency_ms"] is not None


def test_provider_health_endpoint_rejects_non_admin() -> None:
    app.dependency_overrides[get_current_user] = _mock_dispatcher_user
    try:
        with TestClient(app) as client:
            response = client.get("/v1/chat/provider-health")
        assert response.status_code == 403
        assert response.json()["detail"] == "Insufficient permissions"
    finally:
        app.dependency_overrides.pop(get_current_user, None)


def test_provider_health_endpoint_state_field_matches_circuit_state(
    _admin_override: None,
) -> None:
    tracker = get_provider_health_tracker()
    tracker.record_call(
        "anthropic",
        latency_ms=100.0,
        success=True,
        state=CircuitState.OPEN,
    )

    with TestClient(app) as client:
        response = client.get("/v1/chat/provider-health")
    assert response.status_code == 200
    body = response.json()
    assert body["providers"][0]["state"] == "open"
