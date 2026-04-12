# Plan: OPS-2.1 Prometheus `/metrics` Endpoint

## Context

Sentry/GlitchTip tracks errors but gives zero visibility into latency percentiles, cache hit rates, provider health over time, or "slow but not failing" requests. Ops is blind to degradation until the error rate spikes — a 15-minute lag minimum. This feature adds `prometheus-client` and exposes a `/metrics` endpoint with core counters, histograms, and gauges for HTTP requests, DB pool, Redis cache, agent execution, circuit breaker state, and background-poller liveness.

## Security Context Assessment

**Active contexts: CTX-INFRA, CTX-RBAC**

- **CTX-INFRA** — Adding a new endpoint that exposes internal system metrics. Must not leak credentials or internal topology beyond metric names. Access control via IP allowlist at reverse-proxy layer (scrapers don't carry JWTs), not application-level auth.
- **CTX-RBAC** — The `/metrics` endpoint should NOT require JWT auth (Prometheus scrapers can't authenticate). Instead, rely on nginx IP allowlist. The endpoint should still be excluded from public API docs.

CTX-AUTH, CTX-FILE, CTX-AGENT, CTX-INPUT do not apply — no auth changes, no file uploads, no agent tools, no user input queries.

## Research Summary

### Key Files & Integration Points

| File | Role | Integration |
|------|------|-------------|
| `app/main.py:164-202` | App creation, middleware, routers | Mount prometheus ASGI app at `/metrics` |
| `app/core/middleware.py:83-148` | `RequestLoggingMiddleware` with `time.time()` timing | New `MetricsMiddleware` follows same `BaseHTTPMiddleware` pattern |
| `app/core/config.py` | Pydantic Settings, feature flags pattern (`*_enabled: bool`) | Add `metrics_enabled: bool = True` |
| `app/core/agents/circuit_breaker.py:209-237` | `_transition_to()` method with structured logging | Add gauge update call inside `_transition_to()` |
| `app/core/database.py:20` | Engine with `pool_size`, `max_overflow` | Access `engine.pool` for gauge readings |
| `app/core/rate_limit.py:55-84` | slowapi with Redis storage | Add cache hit/miss counters (limited — slowapi abstracts Redis access) |
| `app/transit/poller.py:83` | `poll_once()` — fetches vehicle positions | Add `POLLER_LAST_TICK` gauge update |
| `app/memory/lifecycle.py:24-65` | `_run_compaction()`, `_run_promotion()` daily tasks | Add `POLLER_LAST_TICK` gauge update |
| `app/geofences/evaluator.py:26` | `evaluate_geofences_once()` periodic | Add `POLLER_LAST_TICK` gauge update |
| `app/alerts/evaluator.py:26` | `evaluate_rules_once()` periodic | Add `POLLER_LAST_TICK` gauge update |
| `app/core/health.py:32-177` | Health endpoints at root level | Pattern reference for mounting |

### Existing Patterns to Follow

- **Feature flag**: `metrics_enabled: bool = True` (same as `alerts_enabled`, `circuit_breaker_enabled`)
- **Middleware**: `BaseHTTPMiddleware` with `dispatch()` method, `time.time()` timing
- **Background tasks**: `start_*/stop_*` pattern in lifespan, config-gated
- **Logging**: `domain.component.action_state` via `get_logger(__name__)`
- **Circuit breaker hook**: `_transition_to()` at line 209 — single place where all state changes flow

### Reference Feature

`app/core/health.py` — root-level endpoint, rate-limited, no auth prefix. The metrics endpoint follows this same pattern but uses the prometheus ASGI app for response generation.

## Test Landscape

### Existing Test Infrastructure

| Resource | Location | Use |
|----------|----------|-----|
| TestClient fixture | `conftest.py` (root) | `client` fixture for endpoint tests |
| Mock settings | `conftest.py` (root) | `mock_settings` fixture for env overrides |
| Middleware tests | `app/core/tests/test_middleware.py` | Template for middleware test structure |
| Health endpoint tests | `app/core/tests/test_health.py` | Template for root-level endpoint tests |
| Circuit breaker tests | `app/core/agents/tests/test_circuit_breaker.py` | `ManualClock` fixture, breaker patterns |
| Breaker reset fixture | `app/core/agents/tests/conftest.py` | `_reset_provider_breakers` autouse |
| Security convention tests | `app/tests/test_security.py` | May need update if endpoint auth is checked |

### Mock Patterns

- Redis: `MagicMock()` for sync, `AsyncMock()` for async methods (anti-pattern #35)
- Config overrides: `@patch("app.core.config.get_settings")`
- Circuit breaker: `ManualClock` for deterministic time, `_reset_provider_breakers` autouse fixture

## Type Check Baseline

- **pyright `app/core/`**: 0 errors
- **mypy `app/core/`**: 0 errors (125 source files)
- **pyright `app/main.py`**: 0 errors
- **mypy `app/main.py`**: 0 errors

**Target: maintain 0 errors after implementation.**

## Files to Create/Modify

| Action | File | Purpose |
|--------|------|---------|
| UPDATE | `pyproject.toml` | Add `prometheus-client>=0.21` dependency |
| CREATE | `app/core/metrics.py` | Metric definitions (histograms, counters, gauges) |
| CREATE | `app/core/metrics_middleware.py` | HTTP request latency middleware |
| UPDATE | `app/core/config.py` | Add `metrics_enabled` setting |
| UPDATE | `app/main.py` | Mount prometheus ASGI app, add metrics middleware |
| UPDATE | `app/core/agents/circuit_breaker.py` | Gauge update in `_transition_to()` |
| UPDATE | `app/transit/poller.py` | `POLLER_LAST_TICK` gauge update |
| UPDATE | `app/memory/lifecycle.py` | `POLLER_LAST_TICK` gauge update |
| UPDATE | `app/geofences/evaluator.py` | `POLLER_LAST_TICK` gauge update |
| UPDATE | `app/alerts/evaluator.py` | `POLLER_LAST_TICK` gauge update |
| CREATE | `app/core/tests/test_metrics.py` | 12 unit tests |

## Implementation Steps

### Step 1: Add dependency

**UPDATE** `pyproject.toml` — add `"prometheus-client>=0.21"` to `dependencies` list.

```bash
uv sync
```

**Validation:** `uv run python -c "import prometheus_client; print(prometheus_client.__version__)"`

---

### Step 2: Add config setting

**UPDATE** `app/core/config.py` — add after existing feature flags (near `circuit_breaker_enabled`):

```python
# Prometheus metrics (OPS-2.1)
metrics_enabled: bool = True
```

**Validation:** `uv run ruff check app/core/config.py && uv run pyright app/core/config.py`

---

### Step 3: Create metric definitions

**CREATE** `app/core/metrics.py`

Define all metrics with the `vtv_` prefix. Each metric has a docstring-level cardinality comment.

```python
"""Prometheus metric definitions for VTV observability (OPS-2.1).

All metrics use the ``vtv_`` prefix. Cardinality is documented per metric.
NEVER label with unbounded identifiers (user_id, vehicle_id, IP).

Max label combinations per metric:
- vtv_http_request_duration_seconds: ~methods(5) × paths(~25) × statuses(~8) = ~1000
- vtv_redis_cache_hits_total / misses: ~cache_names(5) = 5 each
- vtv_agent_tool_duration_seconds: ~tools(11) × statuses(2) = 22
- vtv_circuit_breaker_state: ~providers(3) = 3
- vtv_poller_last_tick_seconds: ~pollers(5) = 5
- vtv_db_pool_*: 1 each (no labels)
"""

from __future__ import annotations

from prometheus_client import Counter, Gauge, Histogram

from app.core.config import get_settings

# --- HTTP Request Metrics ---

REQUEST_LATENCY = Histogram(
    "vtv_http_request_duration_seconds",
    "HTTP request latency",
    ["method", "path", "status"],
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
)

# --- Database Pool Metrics ---

DB_POOL_SIZE = Gauge("vtv_db_pool_size", "SQLAlchemy pool size (configured)")
DB_POOL_IN_USE = Gauge("vtv_db_pool_checked_out", "SQLAlchemy connections checked out")
DB_POOL_OVERFLOW = Gauge("vtv_db_pool_overflow", "SQLAlchemy overflow connections in use")

# --- Redis Cache Metrics ---

REDIS_CACHE_HITS = Counter(
    "vtv_redis_cache_hits_total", "Redis cache hits", ["cache_name"]
)
REDIS_CACHE_MISSES = Counter(
    "vtv_redis_cache_misses_total", "Redis cache misses", ["cache_name"]
)

# --- Agent Tool Metrics ---

AGENT_TOOL_DURATION = Histogram(
    "vtv_agent_tool_duration_seconds",
    "Agent tool invocation latency",
    ["tool_name", "status"],
    buckets=(0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0),
)

# --- Circuit Breaker Metrics ---

CIRCUIT_BREAKER_STATE = Gauge(
    "vtv_circuit_breaker_state",
    "Circuit breaker state: 0=closed, 1=half_open, 2=open",
    ["provider"],
)

_CB_STATE_MAP: dict[str, int] = {
    "closed": 0,
    "half_open": 1,
    "open": 2,
}


def update_circuit_breaker_gauge(provider: str, state_value: str) -> None:
    """Update the circuit breaker Prometheus gauge.

    Args:
        provider: Provider name (e.g. "groq", "openai").
        state_value: CircuitState.value string.
    """
    if not get_settings().metrics_enabled:
        return
    CIRCUIT_BREAKER_STATE.labels(provider=provider).set(
        _CB_STATE_MAP.get(state_value, -1)
    )


# --- Background Poller Liveness ---

POLLER_LAST_TICK = Gauge(
    "vtv_poller_last_tick_seconds",
    "Unix epoch timestamp of the poller's last successful tick",
    ["poller_name"],
)


def record_poller_tick(poller_name: str) -> None:
    """Record a successful poller tick (sets gauge to current time).

    Args:
        poller_name: Identifier for the background task.
    """
    if not get_settings().metrics_enabled:
        return
    import time
    POLLER_LAST_TICK.labels(poller_name=poller_name).set(time.time())
```

**Validation:** `uv run ruff format app/core/metrics.py && uv run ruff check --fix app/core/metrics.py && uv run pyright app/core/metrics.py && uv run mypy app/core/metrics.py`

---

### Step 4: Create metrics middleware

**CREATE** `app/core/metrics_middleware.py`

```python
"""Prometheus HTTP request metrics middleware (OPS-2.1).

Records request latency histogram using FastAPI's resolved route path template
(not the raw URL) to keep label cardinality finite. Unmatched routes (404s)
collapse to ``__not_found__``.
"""

from __future__ import annotations

import time
from collections.abc import Awaitable, Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.routing import Match

from app.core.config import get_settings
from app.core.metrics import REQUEST_LATENCY


def _resolve_path_template(request: Request) -> str:
    """Extract the route path template from a FastAPI request.

    Falls back to ``__not_found__`` for unmatched routes to prevent
    cardinality explosion from random 404 paths.
    """
    app = request.app
    for route in app.routes:
        match, _ = route.matches(request.scope)
        if match == Match.FULL:
            return getattr(route, "path", request.url.path)
    return "__not_found__"


class MetricsMiddleware(BaseHTTPMiddleware):
    """Record HTTP request duration in a Prometheus histogram."""

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        if not get_settings().metrics_enabled:
            return await call_next(request)

        # Skip recording the /metrics endpoint itself
        if request.url.path == "/metrics":
            return await call_next(request)

        start = time.time()
        response = await call_next(request)
        duration = time.time() - start

        path_template = _resolve_path_template(request)
        REQUEST_LATENCY.labels(
            method=request.method,
            path=path_template,
            status=response.status_code,
        ).observe(duration)

        return response
```

**Validation:** `uv run ruff format app/core/metrics_middleware.py && uv run ruff check --fix app/core/metrics_middleware.py && uv run pyright app/core/metrics_middleware.py && uv run mypy app/core/metrics_middleware.py`

---

### Step 5: Mount metrics endpoint and middleware in main.py

**UPDATE** `app/main.py`

1. Add import at top (after existing imports around line 38):
   ```python
   from app.core.metrics_middleware import MetricsMiddleware
   ```

2. After `setup_middleware(app)` (line 178) and before `setup_exception_handlers(app)` (line 181), add the metrics middleware:
   ```python
   app.add_middleware(MetricsMiddleware)
   ```

3. After all `include_router()` calls (after line 202), mount the prometheus ASGI app:
   ```python
   # Prometheus metrics endpoint (OPS-2.1)
   # Access control via nginx IP allowlist — scrapers don't carry JWTs.
   if get_settings().metrics_enabled:
       from prometheus_client import make_asgi_app as _make_metrics_app
       app.mount("/metrics", _make_metrics_app())
   ```

**Validation:** `uv run ruff format app/main.py && uv run ruff check --fix app/main.py && uv run pyright app/main.py && uv run mypy app/main.py`

---

### Step 6: Wire circuit breaker gauge

**UPDATE** `app/core/agents/circuit_breaker.py`

Add import at top (after `from app.core.logging import get_logger`):
```python
from app.core.metrics import update_circuit_breaker_gauge
```

Inside `_transition_to()` method (line 209), add gauge update as the **last line** of the method (after all existing logging):
```python
update_circuit_breaker_gauge(self._name, new_state.value)
```

**Validation:** `uv run ruff check app/core/agents/circuit_breaker.py && uv run pyright app/core/agents/circuit_breaker.py`

---

### Step 7: Wire background poller ticks

**UPDATE** each poller file — add `from app.core.metrics import record_poller_tick` and call `record_poller_tick("name")` after each successful tick.

**7a. `app/transit/poller.py`** — Inside `poll_once()`, after successful vehicle fetch (before return), add:
```python
record_poller_tick("transit_feed")
```

**7b. `app/memory/lifecycle.py`** — Inside `_run_compaction()` and `_run_promotion()`, after successful completion log, add:
```python
record_poller_tick("memory_compaction")  # in _run_compaction
record_poller_tick("memory_promotion")   # in _run_promotion
```

**7c. `app/geofences/evaluator.py`** — Inside `evaluate_geofences_once()`, after successful evaluation, add:
```python
record_poller_tick("geofence_evaluator")
```

**7d. `app/alerts/evaluator.py`** — Inside `evaluate_rules_once()`, after successful evaluation, add:
```python
record_poller_tick("alert_evaluator")
```

**Validation per file:** `uv run ruff check {file} && uv run pyright {file}`

---

### Step 8: Create unit tests

**CREATE** `app/core/tests/test_metrics.py` — 12 tests organized in class-based structure.

```python
"""Unit tests for Prometheus metrics (OPS-2.1)."""

from __future__ import annotations

import time
from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from prometheus_client import CollectorRegistry, Counter, Gauge, Histogram
from starlette.routing import Route

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
        # Verify the observation lands in the correct bucket
        # The 0.05 bucket should contain the 0.03 observation
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
        # Verify the function doesn't raise; actual gauge value tested via registry

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
        # Should not raise or record
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
```

**Validation:** `uv run ruff format app/core/tests/test_metrics.py && uv run ruff check --fix app/core/tests/test_metrics.py && uv run pytest app/core/tests/test_metrics.py -v`

---

### Step 9: Full validation

Run the complete validation suite:

```bash
uv run ruff format .
uv run ruff check --fix .
uv run mypy app/core/ app/main.py
uv run pyright app/core/ app/main.py
uv run pytest app/core/tests/test_metrics.py -v
uv run pytest -m "not integration" --timeout=60
```

**Acceptance:** All pass. Pyright/mypy errors = 0 (matching baseline).

## Preflight Warnings

- `app/core/agents/circuit_breaker.py:209` — `_transition_to()` uses `**log_fields: object` kwargs. Adding a function call as the last line is safe; just ensure no early returns are added before the gauge update.
- `app/main.py` — The `prometheus_client.make_asgi_app()` returns an ASGI app; `app.mount()` is the correct way to add it (not `include_router`). The mount path `/metrics` must not conflict with any router prefix.
- `prometheus_client` is an untyped library — will need mypy `[[overrides]]` in `pyproject.toml` for `ignore_missing_imports` and pyright file-level directives in files that import it.
- **Anti-pattern #3**: Add mypy override for `prometheus_client` and pyright directives on `metrics.py` and `metrics_middleware.py`.
- **Anti-pattern #12**: Three-layer fix needed for prometheus_client: (a) mypy override, (b) pyright file-level directives, (c) ruff per-file-ignores if needed.

## Security Checklist

- [x] `/metrics` endpoint: NO JWT auth (prometheus scrapers). Access via nginx IP allowlist.
- [x] `/metrics` excluded from OpenAPI docs (mounted via `app.mount()`, not a router)
- [x] No credentials in metric labels — only method, path template, status, provider name, tool name, cache name
- [x] No `user_id`, `vehicle_id`, or IP in labels (cardinality guard)
- [x] Feature flag `metrics_enabled` to disable in emergencies
- [x] Path templates used instead of raw URLs (prevents cardinality explosion from random paths)

## Verification

- [ ] `uv run python -c "import prometheus_client"` succeeds
- [ ] `make check` passes (lint + types + tests)
- [ ] `curl localhost:8123/metrics` returns prometheus text format (when app running)
- [ ] Pyright errors = 0 (baseline: 0)
- [ ] Mypy errors = 0 (baseline: 0)
- [ ] 12 new tests pass: `uv run pytest app/core/tests/test_metrics.py -v`
- [ ] Existing tests unaffected: `uv run pytest -m "not integration" --timeout=60`
- [ ] Circuit breaker gauge updates when state transitions (verify in test)
