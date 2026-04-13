# pyright: reportUnknownParameterType=false, reportMissingParameterType=false, reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false
"""Unit tests for daily schedule adherence computation, publishing, and lifecycle (ML-5.2)."""

from __future__ import annotations

import datetime
from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.analytics.tests.conftest import make_daily_adherence_report
from app.auth.dependencies import get_current_user
from app.auth.models import User
from app.core.database import get_db
from app.core.rate_limit import limiter
from app.main import app

limiter.enabled = False


def _make_static_store(route_ids: list[str] | None = None) -> MagicMock:
    """Build a mock GTFSStaticStore with correct attribute-based API.

    Args:
        route_ids: Route IDs to populate. Defaults to ["1"].

    Returns:
        Mock static store with routes, route_trips, trip_stop_times, etc.
    """
    if route_ids is None:
        route_ids = ["1"]

    store = MagicMock()
    routes: dict[str, MagicMock] = {}
    route_trips: dict[str, list[MagicMock]] = {}
    for rid in route_ids:
        route_info = MagicMock()
        route_info.route_short_name = rid
        routes[rid] = route_info
        trip = MagicMock()
        trip.trip_id = f"t_{rid}"
        trip.service_id = "svc1"
        route_trips[rid] = [trip]

    store.routes = routes
    store.route_trips = route_trips
    store.trip_stop_times = {}
    store.get_active_service_ids.return_value = {"svc1"}
    return store


def _make_adherence_mock(
    tracked: int = 10,
    on_time: int = 8,
    late: int = 1,
    early: int = 1,
    pct: float = 80.0,
    avg_delay: float = 60.0,
) -> MagicMock:
    """Build a mock RouteAdherence result.

    Returns:
        Mock with tracked_trips, on_time_count, etc.
    """
    m = MagicMock()
    m.tracked_trips = tracked
    m.on_time_count = on_time
    m.late_count = late
    m.early_count = early
    m.on_time_percentage = pct
    m.average_delay_seconds = avg_delay
    m.trips = []
    return m


# ---------------------------------------------------------------------------
# compute_daily_report
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_compute_daily_report_creates_row() -> None:
    """Verify compute_daily_report inserts a DailyAdherenceReport row."""
    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_db.execute.return_value = mock_result

    mock_static = _make_static_store()
    mock_adherence = _make_adherence_mock()

    with (
        patch(
            "app.analytics.daily_adherence.get_static_store",
            new_callable=AsyncMock,
            return_value=mock_static,
        ),
        patch(
            "app.analytics.daily_adherence._compute_route_adherence",
            return_value=mock_adherence,
        ),
        patch("app.analytics.daily_adherence.httpx.AsyncClient"),
        patch("app.analytics.daily_adherence.AlertService"),
    ):
        from app.analytics.daily_adherence import compute_daily_report

        report = await compute_daily_report(datetime.date(2026, 4, 10), mock_db)

    mock_db.add.assert_called_once()
    mock_db.flush.assert_awaited_once()
    mock_db.commit.assert_awaited_once()
    assert report.overall_pct == 80.0
    assert report.total_trips == 10


@pytest.mark.asyncio
async def test_compute_daily_report_per_route_breakdown() -> None:
    """Verify per_route_json contains route metrics for multiple routes."""
    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_db.execute.return_value = mock_result

    mock_static = _make_static_store(["1", "2"])
    mock_adherence = _make_adherence_mock(tracked=5, on_time=4, late=1, early=0, pct=80.0)

    with (
        patch(
            "app.analytics.daily_adherence.get_static_store",
            new_callable=AsyncMock,
            return_value=mock_static,
        ),
        patch(
            "app.analytics.daily_adherence._compute_route_adherence",
            return_value=mock_adherence,
        ),
        patch("app.analytics.daily_adherence.httpx.AsyncClient"),
        patch("app.analytics.daily_adherence.AlertService"),
    ):
        from app.analytics.daily_adherence import compute_daily_report

        report = await compute_daily_report(datetime.date(2026, 4, 10), mock_db)

    assert len(report.per_route_json) == 2
    assert report.per_route_json[0]["route_id"] == "1"
    assert report.per_route_json[1]["route_id"] == "2"


# ---------------------------------------------------------------------------
# publish_report
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_publish_report_slack_webhook() -> None:
    """Verify Slack webhook is called with correct payload."""
    report = make_daily_adherence_report()

    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_client = AsyncMock()
    mock_client.post.return_value = mock_response

    mock_settings = MagicMock()
    mock_settings.analytics_adherence_slack_webhook = "https://hooks.slack.com/test"
    mock_settings.analytics_adherence_smtp_enabled = False
    mock_settings.analytics_adherence_smtp_to = ""

    with (
        patch("app.analytics.daily_adherence.get_settings", return_value=mock_settings),
        patch("app.analytics.daily_adherence.httpx.AsyncClient") as mock_httpx_cls,
    ):
        mock_httpx_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_httpx_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        from app.analytics.daily_adherence import publish_report

        await publish_report(report)

    mock_client.post.assert_awaited_once()
    call_args = mock_client.post.call_args
    assert call_args[0][0] == "https://hooks.slack.com/test"
    assert "text" in call_args[1]["json"]


@pytest.mark.asyncio
async def test_publish_report_slack_fails_open() -> None:
    """Verify Slack failure does not raise."""
    report = make_daily_adherence_report()

    mock_settings = MagicMock()
    mock_settings.analytics_adherence_slack_webhook = "https://hooks.slack.com/test"
    mock_settings.analytics_adherence_smtp_enabled = False
    mock_settings.analytics_adherence_smtp_to = ""

    mock_client = AsyncMock()
    mock_client.post.side_effect = Exception("Slack down")

    with (
        patch("app.analytics.daily_adherence.get_settings", return_value=mock_settings),
        patch("app.analytics.daily_adherence.httpx.AsyncClient") as mock_httpx_cls,
    ):
        mock_httpx_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_httpx_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        from app.analytics.daily_adherence import publish_report

        # Should not raise
        await publish_report(report)


@pytest.mark.asyncio
async def test_publish_report_email_fails_open() -> None:
    """Verify email failure does not raise."""
    report = make_daily_adherence_report()

    mock_settings = MagicMock()
    mock_settings.analytics_adherence_slack_webhook = None
    mock_settings.analytics_adherence_smtp_enabled = True
    mock_settings.analytics_adherence_smtp_to = "admin@vtv.lv"
    mock_settings.analytics_adherence_smtp_host = "localhost"
    mock_settings.analytics_adherence_smtp_port = 587
    mock_settings.analytics_adherence_smtp_from = "vtv@example.com"

    with (
        patch("app.analytics.daily_adherence.get_settings", return_value=mock_settings),
        patch(
            "app.analytics.daily_adherence.asyncio.to_thread",
            side_effect=Exception("SMTP down"),
        ),
    ):
        from app.analytics.daily_adherence import publish_report

        # Should not raise
        await publish_report(report)


# ---------------------------------------------------------------------------
# Threshold alert
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_threshold_below_triggers_alert() -> None:
    """Verify alert is created when overall_pct < threshold."""
    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_db.execute.return_value = mock_result

    mock_static = _make_static_store()
    mock_adherence = _make_adherence_mock(tracked=100, on_time=70, late=20, early=10, pct=70.0)

    mock_alert_service = AsyncMock()

    with (
        patch(
            "app.analytics.daily_adherence.get_static_store",
            new_callable=AsyncMock,
            return_value=mock_static,
        ),
        patch(
            "app.analytics.daily_adherence._compute_route_adherence",
            return_value=mock_adherence,
        ),
        patch("app.analytics.daily_adherence.httpx.AsyncClient"),
        patch(
            "app.analytics.daily_adherence.AlertService",
            return_value=mock_alert_service,
        ),
    ):
        from app.analytics.daily_adherence import compute_daily_report

        report = await compute_daily_report(datetime.date(2026, 4, 10), mock_db)

    assert report.alert_triggered is True
    mock_alert_service.create_alert.assert_awaited_once()
    alert_data = mock_alert_service.create_alert.call_args[0][0]
    assert alert_data.severity == "high"
    assert alert_data.alert_type == "schedule_adherence"


@pytest.mark.asyncio
async def test_threshold_above_no_alert() -> None:
    """Verify no alert when overall_pct >= threshold."""
    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_db.execute.return_value = mock_result

    mock_static = _make_static_store()
    mock_adherence = _make_adherence_mock(tracked=100, on_time=90, late=5, early=5, pct=90.0)

    mock_alert_service = AsyncMock()

    with (
        patch(
            "app.analytics.daily_adherence.get_static_store",
            new_callable=AsyncMock,
            return_value=mock_static,
        ),
        patch(
            "app.analytics.daily_adherence._compute_route_adherence",
            return_value=mock_adherence,
        ),
        patch("app.analytics.daily_adherence.httpx.AsyncClient"),
        patch(
            "app.analytics.daily_adherence.AlertService",
            return_value=mock_alert_service,
        ),
    ):
        from app.analytics.daily_adherence import compute_daily_report

        report = await compute_daily_report(datetime.date(2026, 4, 10), mock_db)

    assert report.alert_triggered is False
    mock_alert_service.create_alert.assert_not_awaited()


# ---------------------------------------------------------------------------
# get_daily_reports
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_daily_reports_date_range() -> None:
    """Verify DB query filters by date range and orders by report_date."""
    mock_db = AsyncMock()
    mock_scalars = MagicMock()
    mock_scalars.all.return_value = [make_daily_adherence_report()]
    mock_result = MagicMock()
    mock_result.scalars.return_value = mock_scalars
    mock_db.execute.return_value = mock_result

    from app.analytics.daily_adherence import get_daily_reports

    result = await get_daily_reports(
        mock_db,
        datetime.date(2026, 4, 1),
        datetime.date(2026, 4, 10),
    )

    assert len(result) == 1
    mock_db.execute.assert_awaited_once()


# ---------------------------------------------------------------------------
# Lifecycle
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_adherence_task_lifecycle() -> None:
    """Verify start_adherence_task creates a task and stop cancels it."""
    import app.analytics.daily_adherence as mod

    mock_settings = MagicMock()
    mock_settings.analytics_adherence_enabled = True
    mock_settings.background_queue_enabled = False
    mock_settings.analytics_adherence_cron_hour = 6

    with patch.object(mod, "get_settings", return_value=mock_settings):
        await mod.start_adherence_task()
        assert mod._adherence_task is not None

        task = mod._adherence_task
        await mod.stop_adherence_task()
        assert mod._adherence_task is None
        assert task.cancelled()


# ---------------------------------------------------------------------------
# Route endpoint tests
# ---------------------------------------------------------------------------


def _mock_admin_user() -> User:
    """Return a mock admin user for route testing."""
    user = MagicMock(spec=User)
    user.id = 1
    user.email = "admin@vtv.lv"
    user.name = "Admin"
    user.role = "admin"
    user.is_active = True
    return user


@pytest.fixture()
def client() -> Generator[TestClient, None, None]:
    """Test client with auth and DB overrides."""
    app.dependency_overrides[get_current_user] = _mock_admin_user
    app.dependency_overrides[get_db] = lambda: AsyncMock()
    yield TestClient(app)
    app.dependency_overrides.pop(get_current_user, None)
    app.dependency_overrides.pop(get_db, None)


def test_adherence_endpoint_valid_range(client: TestClient) -> None:
    """200 with valid date range."""
    mock_reports: list[MagicMock] = [make_daily_adherence_report()]

    with patch("app.analytics.routes.get_daily_reports", new_callable=AsyncMock) as mock_fn:
        mock_fn.return_value = mock_reports
        resp = client.get(
            "/api/v1/analytics/adherence/daily",
            params={"date_from": "2026-04-01", "date_to": "2026-04-10"},
        )

    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["overall_pct"] == 88.5


def test_adherence_endpoint_invalid_date_from_gt_to(client: TestClient) -> None:
    """400 when date_from > date_to."""
    resp = client.get(
        "/api/v1/analytics/adherence/daily",
        params={"date_from": "2026-04-10", "date_to": "2026-04-01"},
    )
    assert resp.status_code == 400
    assert "date_from" in resp.json()["detail"]


def test_adherence_endpoint_range_exceeds_90_days(client: TestClient) -> None:
    """400 when range > 90 days."""
    resp = client.get(
        "/api/v1/analytics/adherence/daily",
        params={"date_from": "2026-01-01", "date_to": "2026-12-31"},
    )
    assert resp.status_code == 400
    assert "90 days" in resp.json()["detail"]


def test_adherence_endpoint_requires_auth() -> None:
    """No auth override -> 401/403."""
    app.dependency_overrides.pop(get_current_user, None)
    app.dependency_overrides.pop(get_db, None)
    test_client = TestClient(app)
    resp = test_client.get(
        "/api/v1/analytics/adherence/daily",
        params={"date_from": "2026-04-01", "date_to": "2026-04-10"},
    )
    assert resp.status_code in (401, 403)
