# pyright: reportUnknownMemberType=false, reportMissingTypeStubs=false
"""Tests for the anomaly alert router and REST endpoint (ML-4.3)."""

from __future__ import annotations

import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.alerts.schemas import SourceEntityType
from app.ml.anomaly.router import AnomalyAlertRouter
from app.ml.anomaly.schemas import CHANNEL_MATRIX, AnomalyEvent


def _make_event(
    anomaly_type: str = "stuck_vehicle",
    severity: str = "high",
    source_entity_type: SourceEntityType | None = "vehicle",
    source_entity_id: str | None = "v1",
    title: str = "Test anomaly",
) -> AnomalyEvent:
    """Build an AnomalyEvent for testing."""
    return AnomalyEvent(
        anomaly_type=anomaly_type,  # type: ignore[arg-type]
        severity=severity,  # type: ignore[arg-type]
        source_entity_type=source_entity_type,
        source_entity_id=source_entity_id,
        title=title,
        details={"test_key": "test_value"},
        detected_at=datetime.datetime.now(tz=datetime.UTC),
    )


def _make_settings() -> MagicMock:
    """Build mock Settings with ML-4.3 defaults."""
    s = MagicMock()
    s.anomaly_cooldown_critical_seconds = 300
    s.anomaly_cooldown_warning_seconds = 1800
    return s


class TestAnomalyAlertRouter:
    """Tests for AnomalyAlertRouter.route()."""

    @pytest.mark.asyncio
    async def test_route_creates_alert(self) -> None:
        """New anomaly event should create an alert and set cooldown."""
        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(return_value=None)
        mock_redis.set = AsyncMock()
        mock_db = AsyncMock()

        router = AnomalyAlertRouter(mock_redis, _make_settings())
        event = _make_event()

        with patch("app.ml.anomaly.router.AlertInstanceRepository") as mock_repo_cls:
            mock_repo = AsyncMock()
            mock_repo_cls.return_value = mock_repo

            result = await router.route(event, mock_db)

        assert result is True
        mock_repo.create.assert_called_once()
        mock_redis.set.assert_called_once()

    @pytest.mark.asyncio
    async def test_cooldown_suppresses_duplicate(self) -> None:
        """Existing cooldown key should suppress the anomaly."""
        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(return_value=b"1")
        mock_db = AsyncMock()

        router = AnomalyAlertRouter(mock_redis, _make_settings())
        event = _make_event()

        result = await router.route(event, mock_db)

        assert result is False

    @pytest.mark.asyncio
    async def test_cooldown_allows_after_expiry(self) -> None:
        """No cooldown key should allow the alert."""
        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(return_value=None)
        mock_redis.set = AsyncMock()
        mock_db = AsyncMock()

        router = AnomalyAlertRouter(mock_redis, _make_settings())
        event = _make_event()

        with patch("app.ml.anomaly.router.AlertInstanceRepository") as mock_repo_cls:
            mock_repo_cls.return_value = AsyncMock()
            result = await router.route(event, mock_db)

        assert result is True

    @pytest.mark.asyncio
    async def test_critical_severity_uses_short_cooldown(self) -> None:
        """Critical severity should use anomaly_cooldown_critical_seconds."""
        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(return_value=None)
        mock_redis.set = AsyncMock()
        mock_db = AsyncMock()
        settings = _make_settings()

        router = AnomalyAlertRouter(mock_redis, settings)
        event = _make_event(severity="critical")

        with patch("app.ml.anomaly.router.AlertInstanceRepository") as mock_repo_cls:
            mock_repo_cls.return_value = AsyncMock()
            await router.route(event, mock_db)

        mock_redis.set.assert_called_once()
        call_kwargs = mock_redis.set.call_args
        assert call_kwargs[1]["ex"] == 300

    @pytest.mark.asyncio
    async def test_warning_severity_uses_long_cooldown(self) -> None:
        """Non-critical severity should use anomaly_cooldown_warning_seconds."""
        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(return_value=None)
        mock_redis.set = AsyncMock()
        mock_db = AsyncMock()
        settings = _make_settings()

        router = AnomalyAlertRouter(mock_redis, settings)
        event = _make_event(severity="high")

        with patch("app.ml.anomaly.router.AlertInstanceRepository") as mock_repo_cls:
            mock_repo_cls.return_value = AsyncMock()
            await router.route(event, mock_db)

        call_kwargs = mock_redis.set.call_args
        assert call_kwargs[1]["ex"] == 1800

    @pytest.mark.asyncio
    async def test_off_route_dispatches_to_dashboard_slack(self) -> None:
        """Off-route events should log dashboard and slack channels."""
        assert CHANNEL_MATRIX["off_route"] == ["dashboard", "slack"]

    @pytest.mark.asyncio
    async def test_stuck_vehicle_dispatches_to_dashboard_slack(self) -> None:
        """Stuck vehicle events should log dashboard and slack channels."""
        assert CHANNEL_MATRIX["stuck_vehicle"] == ["dashboard", "slack"]

    @pytest.mark.asyncio
    async def test_gps_gap_dispatches_to_dashboard_only(self) -> None:
        """GPS gap events should log dashboard channel only."""
        assert CHANNEL_MATRIX["gps_gap"] == ["dashboard"]

    @pytest.mark.asyncio
    async def test_feed_outage_routes_to_slack_pager(self) -> None:
        """Feed outage events should route to slack and pager."""
        assert CHANNEL_MATRIX["feed_outage"] == ["slack", "pager"]

    @pytest.mark.asyncio
    async def test_cooldown_key_format(self) -> None:
        """Cooldown key should use anomaly:cooldown:{type}:{entity_id} format."""
        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(return_value=None)
        mock_redis.set = AsyncMock()
        mock_db = AsyncMock()

        router = AnomalyAlertRouter(mock_redis, _make_settings())
        event = _make_event(anomaly_type="gps_gap", source_entity_id="v42")

        with patch("app.ml.anomaly.router.AlertInstanceRepository") as mock_repo_cls:
            mock_repo_cls.return_value = AsyncMock()
            await router.route(event, mock_db)

        expected_key = "anomaly:cooldown:gps_gap:v42"
        mock_redis.get.assert_called_with(expected_key)
        mock_redis.set.assert_called_once_with(expected_key, "1", ex=1800)

    @pytest.mark.asyncio
    async def test_feed_outage_event_with_none_entity(self) -> None:
        """Feed outage with None entity type/id should still route correctly."""
        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(return_value=None)
        mock_redis.set = AsyncMock()
        mock_db = AsyncMock()

        router = AnomalyAlertRouter(mock_redis, _make_settings())
        event = _make_event(
            anomaly_type="feed_outage",
            severity="critical",
            source_entity_type=None,
            source_entity_id=None,
        )

        with patch("app.ml.anomaly.router.AlertInstanceRepository") as mock_repo_cls:
            mock_repo = AsyncMock()
            mock_repo_cls.return_value = mock_repo
            result = await router.route(event, mock_db)

        assert result is True
        mock_repo.create.assert_called_once()


class TestAnomalyEndpoint:
    """Tests for GET /api/v1/ml/anomalies/recent."""

    @pytest.mark.asyncio
    async def test_endpoint_requires_auth(self) -> None:
        """Unauthenticated request should return 401 or 403."""
        from app.main import app

        client = TestClient(app, raise_server_exceptions=False)
        response = client.get("/api/v1/ml/anomalies/recent")
        assert response.status_code in (401, 403)

    @pytest.mark.asyncio
    async def test_anomaly_response_schema_matches_spec(self) -> None:
        """AnomalyResponse should have all required fields."""
        from app.ml.anomaly.schemas import AnomalyResponse

        fields = set(AnomalyResponse.model_fields.keys())
        expected = {
            "id",
            "title",
            "severity",
            "alert_type",
            "source_entity_type",
            "source_entity_id",
            "details",
            "status",
            "created_at",
        }
        assert expected == fields
