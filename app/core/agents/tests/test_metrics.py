"""Tests for AI-5.3 self-correction metrics tracker + admin endpoint."""

from collections.abc import Generator
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.auth.dependencies import get_current_user
from app.auth.models import User
from app.core.agents.correction import SelfCorrectionLoop
from app.core.agents.metrics import (
    CorrectionMetricsTracker,
    get_metrics_tracker,
    reset_metrics_tracker,
)
from app.core.agents.validation import Issue, ValidationResult
from app.core.rate_limit import limiter
from app.main import app

# Disable rate limiting for these tests (matches test_routes.py:21)
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
    """Ensure each test starts with a fresh tracker singleton."""
    reset_metrics_tracker()
    yield
    reset_metrics_tracker()


@pytest.fixture
def _admin_override() -> Generator[None, None, None]:
    app.dependency_overrides[get_current_user] = _mock_admin_user
    yield
    app.dependency_overrides.pop(get_current_user, None)


# ----- Tracker unit tests -----


def test_tracker_starts_empty() -> None:
    tracker = CorrectionMetricsTracker()
    assert tracker.snapshot() == {}


def test_record_triggered_increments_per_unique_check() -> None:
    tracker = CorrectionMetricsTracker()
    tracker.record_triggered(["route_existence", "route_existence", "diacritics"])
    snap = tracker.snapshot()
    assert snap["route_existence"].triggered == 1
    assert snap["diacritics"].triggered == 1


def test_record_resolved_records_latency_and_count() -> None:
    tracker = CorrectionMetricsTracker()
    tracker.record_triggered(["route_existence"])
    tracker.record_resolved(["route_existence"], latency_ms=250)
    snap = tracker.snapshot()
    assert snap["route_existence"].resolved == 1
    assert snap["route_existence"].total_latency_ms == 250


def test_record_exhausted_records_latency_and_count() -> None:
    tracker = CorrectionMetricsTracker()
    tracker.record_triggered(["citation_grounding"])
    tracker.record_exhausted(["citation_grounding"], latency_ms=900)
    snap = tracker.snapshot()
    assert snap["citation_grounding"].exhausted == 1
    assert snap["citation_grounding"].total_latency_ms == 900


def test_daily_reset_clears_counters_on_utc_rollover() -> None:
    fake_now = datetime(2026, 4, 10, 12, 0, tzinfo=UTC)

    def clock() -> datetime:
        return fake_now

    tracker = CorrectionMetricsTracker(clock=clock)
    tracker.record_triggered(["route_existence"])
    tracker.record_resolved(["route_existence"], latency_ms=100)
    assert tracker.snapshot()["route_existence"].resolved == 1

    # Roll over to next UTC day
    fake_now = fake_now + timedelta(days=1)
    snap = tracker.snapshot()
    assert snap == {}
    # period_start follows the new day
    assert tracker.period_start().date() == fake_now.date()


# ----- Correction loop integration -----


def _validation_result(*issues: Issue) -> ValidationResult:
    return ValidationResult(
        is_valid=not issues,
        issues=list(issues),
        warnings=[i.description for i in issues],
        sanitized_response="",
    )


def _fake_run_result(output: str) -> MagicMock:
    result = MagicMock()
    result.output = output
    result.all_messages = MagicMock(return_value=[])
    return result


@pytest.mark.asyncio
async def test_correction_loop_records_resolved_metric() -> None:
    error = Issue(
        check_name="route_existence",
        description="Route 999 not found.",
        severity="error",
    )
    fake_agent = MagicMock()
    fake_agent.run = AsyncMock(
        side_effect=[_fake_run_result("bad"), _fake_run_result("good")],
    )

    loop = SelfCorrectionLoop(max_rounds=1)
    with patch(
        "app.core.agents.correction.validate_transit_response",
        side_effect=[_validation_result(error), _validation_result()],
    ):
        result = await loop.run_with_correction(
            fake_agent,
            "Where is bus 999?",
            deps=MagicMock(),
            message_history=None,
            instructions=None,
            model=None,
        )
    assert result.corrected is True

    snap = get_metrics_tracker().snapshot()
    assert snap["route_existence"].triggered == 1
    assert snap["route_existence"].resolved == 1
    assert snap["route_existence"].exhausted == 0
    assert snap["route_existence"].total_latency_ms >= 0


@pytest.mark.asyncio
async def test_correction_loop_records_exhausted_metric() -> None:
    error = Issue(
        check_name="diacritics",
        description="Missing diacritic.",
        severity="error",
    )
    fake_agent = MagicMock()
    fake_agent.run = AsyncMock(
        side_effect=[_fake_run_result("bad1"), _fake_run_result("bad2")],
    )

    loop = SelfCorrectionLoop(max_rounds=1)
    with patch(
        "app.core.agents.correction.validate_transit_response",
        side_effect=[_validation_result(error), _validation_result(error)],
    ):
        result = await loop.run_with_correction(
            fake_agent,
            "Kur ir autobuss?",
            deps=MagicMock(),
            message_history=None,
            instructions=None,
            model=None,
        )
    assert result.corrected is False

    snap = get_metrics_tracker().snapshot()
    assert snap["diacritics"].triggered == 1
    assert snap["diacritics"].resolved == 0
    assert snap["diacritics"].exhausted == 1


# ----- Endpoint tests -----


def test_metrics_endpoint_returns_empty_snapshot(_admin_override: None) -> None:
    with TestClient(app) as client:
        response = client.get("/v1/chat/metrics")
    assert response.status_code == 200
    body = response.json()
    assert body["checks"] == []
    assert body["totals"]["triggered"] == 0
    assert body["totals"]["success_rate"] == 0.0
    assert "period_start" in body
    assert "generated_at" in body


def test_metrics_endpoint_aggregates_counts(_admin_override: None) -> None:
    tracker = get_metrics_tracker()
    tracker.record_triggered(["route_existence"])
    tracker.record_resolved(["route_existence"], latency_ms=400)
    tracker.record_triggered(["diacritics"])
    tracker.record_exhausted(["diacritics"], latency_ms=800)

    with TestClient(app) as client:
        response = client.get("/v1/chat/metrics")
    assert response.status_code == 200
    body = response.json()

    by_name = {c["check_name"]: c for c in body["checks"]}
    assert by_name["route_existence"]["resolved"] == 1
    assert by_name["route_existence"]["success_rate"] == 1.0
    assert by_name["route_existence"]["avg_latency_ms"] == 400.0
    assert by_name["diacritics"]["exhausted"] == 1
    assert by_name["diacritics"]["success_rate"] == 0.0

    assert body["totals"]["triggered"] == 2
    assert body["totals"]["resolved"] == 1
    assert body["totals"]["exhausted"] == 1
    assert body["totals"]["success_rate"] == 0.5


def test_metrics_endpoint_rejects_non_admin() -> None:
    app.dependency_overrides[get_current_user] = _mock_dispatcher_user
    try:
        with TestClient(app) as client:
            response = client.get("/v1/chat/metrics")
        assert response.status_code == 403
        assert response.json()["detail"] == "Insufficient permissions"
    finally:
        app.dependency_overrides.pop(get_current_user, None)
