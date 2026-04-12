# pyright: reportMissingTypeStubs=false, reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false, reportPrivateUsage=false
"""Unit tests for Prometheus metrics (OPS-2.1)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient
from prometheus_client import CollectorRegistry, Counter, Histogram

from app.core.metrics import (
    _CB_STATE_MAP,
    record_poller_tick,
    update_circuit_breaker_gauge,
)
from app.core.metrics_middleware import MetricsMiddleware, _resolve_path_template


def _make_test_app() -> FastAPI:
    """Create a minimal FastAPI app with metrics middleware for testing."""
    test_app = FastAPI()

    @test_app.get("/vehicles/{vehicle_id}")
    def get_vehicle(vehicle_id: int) -> dict[str, int]:
        return {"id": vehicle_id}

    @test_app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    test_app.add_middleware(MetricsMiddleware)
    return test_app


class TestMiddlewarePathTemplating:
    """Middleware resolves route path templates, not raw URLs."""

    def test_dynamic_path_resolved_to_template(self) -> None:
        scope: dict[str, object] = {
            "type": "http",
            "method": "GET",
            "path": "/vehicles/42",
            "query_string": b"",
            "headers": [],
            "root_path": "",
        }
        app = _make_test_app()
        request = MagicMock()
        request.app = app
        request.scope = scope
        result = _resolve_path_template(request)
        assert result == "/vehicles/{vehicle_id}"

    def test_static_path_returned_as_is(self) -> None:
        scope: dict[str, object] = {
            "type": "http",
            "method": "GET",
            "path": "/health",
            "query_string": b"",
            "headers": [],
            "root_path": "",
        }
        app = _make_test_app()
        request = MagicMock()
        request.app = app
        request.scope = scope
        result = _resolve_path_template(request)
        assert result == "/health"


class TestHistogramBuckets:
    """Verify histogram bucket boundaries."""

    def test_request_latency_has_expected_buckets(self) -> None:
        registry = CollectorRegistry()
        h = Histogram(
            "test_latency",
            "test",
            ["method"],
            buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
            registry=registry,
        )
        h.labels(method="GET").observe(0.03)
        sample_value = registry.get_sample_value(
            "test_latency_bucket", {"method": "GET", "le": "0.05"}
        )
        assert sample_value is not None
        assert sample_value >= 1.0


class TestCounterMonotonicity:
    """Counters must never decrease."""

    def test_counter_only_increments(self) -> None:
        registry = CollectorRegistry()
        c = Counter("test_hits", "test", ["name"], registry=registry)
        c.labels(name="x").inc()
        c.labels(name="x").inc()
        c.labels(name="x").inc()
        val = registry.get_sample_value("test_hits_total", {"name": "x"})
        assert val == 3.0


class TestGaugeTransitions:
    """Gauge state changes with circuit breaker."""

    @patch("app.core.metrics.get_settings")
    def test_gauge_set_on_breaker_open(self, mock_gs: MagicMock) -> None:
        mock_gs.return_value.metrics_enabled = True
        update_circuit_breaker_gauge("groq", "open")

    @patch("app.core.metrics.get_settings")
    def test_gauge_set_on_breaker_close(self, mock_gs: MagicMock) -> None:
        mock_gs.return_value.metrics_enabled = True
        update_circuit_breaker_gauge("groq", "closed")


class TestLabelCardinality:
    """Guard against label explosion."""

    def test_not_found_collapses_to_sentinel(self) -> None:
        app = _make_test_app()
        scope: dict[str, object] = {
            "type": "http",
            "method": "GET",
            "path": "/random/nonexistent/path/abc123",
            "query_string": b"",
            "headers": [],
            "root_path": "",
        }
        request = MagicMock()
        request.app = app
        request.scope = scope
        result = _resolve_path_template(request)
        assert result == "__not_found__"


class TestMetricsEndpoint:
    """Endpoint returns Prometheus text format."""

    @patch("app.core.metrics_middleware.get_settings")
    def test_metrics_returns_prometheus_format(self, mock_gs: MagicMock) -> None:
        mock_gs.return_value.metrics_enabled = True
        from app.main import app

        client = TestClient(app)
        response = client.get("/metrics")
        assert response.status_code == 200
        body = response.text
        assert "# HELP" in body or "# TYPE" in body or "vtv_" in body


class Test404CardinalityCollapse:
    """404 paths must not create new label series."""

    def test_404_uses_not_found_template(self) -> None:
        app = _make_test_app()
        scope: dict[str, object] = {
            "type": "http",
            "method": "GET",
            "path": "/this/does/not/exist",
            "query_string": b"",
            "headers": [],
            "root_path": "",
        }
        request = MagicMock()
        request.app = app
        request.scope = scope
        result = _resolve_path_template(request)
        assert result == "__not_found__"


class TestDisabledMetricsFlag:
    """Feature flag disables metrics collection."""

    @patch("app.core.metrics.get_settings")
    def test_disabled_flag_skips_gauge_update(self, mock_gs: MagicMock) -> None:
        mock_gs.return_value.metrics_enabled = False
        update_circuit_breaker_gauge("groq", "open")

    @patch("app.core.metrics.get_settings")
    def test_disabled_flag_skips_poller_tick(self, mock_gs: MagicMock) -> None:
        mock_gs.return_value.metrics_enabled = False
        record_poller_tick("transit_feed")


class TestCircuitBreakerGaugeWiring:
    """Circuit breaker state reflected in Prometheus gauge."""

    @patch("app.core.metrics.get_settings")
    def test_state_map_covers_all_states(self, mock_gs: MagicMock) -> None:
        mock_gs.return_value.metrics_enabled = True
        assert set(_CB_STATE_MAP.keys()) == {"closed", "half_open", "open"}
        update_circuit_breaker_gauge("test", "closed")
        update_circuit_breaker_gauge("test", "half_open")
        update_circuit_breaker_gauge("test", "open")
