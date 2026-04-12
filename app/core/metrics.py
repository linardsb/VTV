# pyright: reportMissingTypeStubs=false, reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false
"""Prometheus metric definitions for VTV observability (OPS-2.1).

All metrics use the ``vtv_`` prefix. Cardinality is documented per metric.
NEVER label with unbounded identifiers (user_id, vehicle_id, IP).
"""

from __future__ import annotations

import time

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

REDIS_CACHE_HITS = Counter("vtv_redis_cache_hits_total", "Redis cache hits", ["cache_name"])
REDIS_CACHE_MISSES = Counter("vtv_redis_cache_misses_total", "Redis cache misses", ["cache_name"])

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
    CIRCUIT_BREAKER_STATE.labels(provider=provider).set(_CB_STATE_MAP.get(state_value, -1))


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
    POLLER_LAST_TICK.labels(poller_name=poller_name).set(time.time())
