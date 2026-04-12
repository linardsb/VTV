# Service Level Objectives (SLOs)

## Overview

SLOs for VTV backend services. Each SLO has a target, measurement window, error budget, and linked alert rule + runbook. Metrics are exposed via the OPS-2.1 Prometheus `/metrics` endpoint (see `app/core/metrics.py`).

## API Latency

| Endpoint Group | SLO Target | Measurement | Error Budget (30d) | Alert Rule | Runbook |
|---------------|------------|-------------|-------------------|------------|---------|
| All API (p95) | < 500ms | `histogram_quantile(0.95, vtv_http_request_duration_seconds)` | 0.1% of requests > 500ms | `VTVHighLatencyP95` | [high-latency.md](runbooks/high-latency.md) |
| All API (p99) | < 2s | `histogram_quantile(0.99, vtv_http_request_duration_seconds)` | 0.01% of requests > 2s | `VTVHighLatencyP99` | [high-latency.md](runbooks/high-latency.md) |
| Health endpoints | < 100ms | p95 filtered by `path=~"/health.*"` | informational | - | - |

## Error Rate

| Scope | SLO Target | Measurement | Error Budget (30d) | Alert Rule | Runbook |
|-------|------------|-------------|-------------------|------------|---------|
| All API (5xx) | < 1% | `rate(status=~"5..")` / `rate(total)` | 1% of requests returning 5xx | `VTVHighErrorRate` | [high-error-rate.md](runbooks/high-error-rate.md) |

## Infrastructure

| Component | SLO Target | Measurement | Alert Rule | Runbook |
|-----------|------------|-------------|------------|---------|
| DB pool utilization | < 80% of (pool_size + max_overflow) | `(vtv_db_pool_checked_out + vtv_db_pool_overflow) / 8` | `VTVDBPoolExhaustion` | [db-pool-exhaustion.md](runbooks/db-pool-exhaustion.md) |
| Circuit breaker | closed (0) | `vtv_circuit_breaker_state` | `VTVCircuitBreakerOpen` | [circuit-breaker-open.md](runbooks/circuit-breaker-open.md) |
| Poller liveness | tick within 2x interval | `time() - vtv_poller_last_tick_seconds` | `VTVPollerStale` | [poller-stale.md](runbooks/poller-stale.md) |
| Redis cache hit rate | > 50% (informational) | `hits / (hits + misses)` | - | - |

## Rationale

| SLO | Target | Rationale |
|-----|--------|-----------|
| p95 latency < 500ms | Standard for internal APIs serving a CMS dashboard |
| p99 latency < 2s | Agent tool calls and GTFS imports can be slow; 2s accommodates |
| Error rate < 1% | Conservative first pass; tighten after 30d baseline data |
| DB pool < 80% | pool_size=3 + max_overflow=5 = 8 total; 80% = 6.4 connections as warning threshold |
| Circuit breaker closed | Any open breaker means degraded LLM functionality |
| Poller liveness < 4x interval | 2x is health probe threshold; 4x is alert threshold (avoids flapping) |
