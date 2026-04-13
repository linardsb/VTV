# Plan: OPS-2.3 SLO Definitions + Prometheus Alert Rules

## Context

Metrics without alerts = dashboards nobody looks at. OPS-2.1 deployed Prometheus metrics (`/metrics` endpoint, HTTP latency histogram, DB pool gauges, Redis cache counters, agent tool duration, circuit breaker state, poller liveness). OPS-2.3 turns those metrics into actionable SLOs and alert rules that can page on-call.

**Deliverables:**
1. `docs/slos.md` — SLO table with endpoints, targets, error budgets, rationale
2. `ops/prometheus/alerts.yml` — Prometheus alerting rules keyed to OPS-2.1 metric names
3. `ops/prometheus/README.md` — how to load rules into Prometheus
4. Runbook placeholders in `docs/runbooks/` for each alert
5. Convention test validating YAML structure
6. Makefile target for alert rule validation

## Security Context Assessment

- **CTX-INFRA** — Creating ops configuration files (Prometheus alert rules). No credentials in alert rules. README must not expose internal IPs or secrets.
- No CTX-AUTH/RBAC/FILE/AGENT/INPUT — no endpoints, no user input, no auth changes.

## Research Summary

### OPS-2.1 Metric Names (exact strings from `app/core/metrics.py`)

| Metric | Type | Labels | Purpose |
|--------|------|--------|---------|
| `vtv_http_request_duration_seconds` | Histogram | `method`, `path`, `status` | HTTP request latency (buckets: 5ms–10s) |
| `vtv_db_pool_size` | Gauge | — | SQLAlchemy pool size (configured=3) |
| `vtv_db_pool_checked_out` | Gauge | — | DB connections checked out |
| `vtv_db_pool_overflow` | Gauge | — | DB overflow connections in use (max_overflow=5) |
| `vtv_redis_cache_hits_total` | Counter | `cache_name` | Redis cache hits |
| `vtv_redis_cache_misses_total` | Counter | `cache_name` | Redis cache misses |
| `vtv_redis_cache_invalidations_total` | Counter | `cache_name` | Redis cache invalidations |
| `vtv_agent_tool_duration_seconds` | Histogram | `tool_name`, `status` | Agent tool execution time (buckets: 10ms–30s) |
| `vtv_circuit_breaker_state` | Gauge | `provider` | 0=closed, 1=half_open, 2=open |
| `vtv_poller_last_tick_seconds` | Gauge | `poller_name` | Unix epoch of last successful tick |

### Active Pollers (from `app/core/health.py` staleness thresholds)

| Poller | Default Interval | Staleness Threshold |
|--------|-----------------|---------------------|
| `transit_feed` | 10s (per-feed configurable) | 2× interval |
| `alert_evaluator` | 60s | 120s |
| `geofence_evaluator` | 30s | 60s |
| `anomaly_evaluator` | 60s | 120s |
| `off_route_evaluator` | 60s | 120s |
| `memory_compaction` | daily 03:00 | 25h |
| `memory_promotion` | daily 03:00 | 25h |

### Existing Infrastructure

- **`docs/runbooks/`** — 2 files: `README.md`, `credential-rotation.md`
- **`ops/`** — does NOT exist, must be created
- **`docs/slos.md`** — does NOT exist
- **promtool** — not installed locally; Python-based YAML validation as primary approach
- **Prometheus service** — not in docker-compose; alert rules designed for external Prometheus deployment

## Test Landscape

- YAML parsing test patterns exist in `app/core/agents/tests/test_eval_loader.py` (381 lines)
- Convention test pattern in `app/tests/test_security.py` (700+ lines) — validates code structure
- PyYAML already a dependency with `types-PyYAML` stubs
- No existing `test_ops_conventions.py` — will create

## Type Check Baseline

- mypy: 0 errors (449 source files)
- pyright: 0 errors
- ruff: clean (501 files)
- Unrelated change: `M app/core/jobs/tests/test_queue.py` (will not conflict)

## Files to Create/Modify

| Action | File | Purpose |
|--------|------|---------|
| CREATE | `docs/slos.md` | SLO definitions table with targets, error budgets, rationale |
| CREATE | `ops/prometheus/alerts.yml` | Prometheus alerting rules (5 alert groups) |
| CREATE | `ops/prometheus/README.md` | Setup instructions for loading rules |
| CREATE | `docs/runbooks/high-latency.md` | Runbook: p95 latency SLO breach |
| CREATE | `docs/runbooks/high-error-rate.md` | Runbook: error rate SLO breach |
| CREATE | `docs/runbooks/circuit-breaker-open.md` | Runbook: LLM provider circuit breaker open |
| CREATE | `docs/runbooks/poller-stale.md` | Runbook: background poller liveness failure |
| CREATE | `docs/runbooks/db-pool-exhaustion.md` | Runbook: DB connection pool saturation |
| CREATE | `app/tests/test_ops_conventions.py` | Convention tests: YAML structure, SLO doc existence |
| UPDATE | `Makefile` | Add `validate-alerts` target |
| UPDATE | `docs/runbooks/README.md` | Add new runbook entries to index |

## Implementation Steps

### Step 1: Create `docs/slos.md`

SLO table covering all OPS-2.1 metrics. Structure:

```markdown
# Service Level Objectives (SLOs)

## Overview
SLOs for VTV backend services. Each SLO has a target, measurement window, error budget, and linked alert rule + runbook.

## API Latency
| Endpoint Group | SLO Target | Measurement | Error Budget (30d) | Alert Rule | Runbook |
|---------------|------------|-------------|-------------------|------------|---------|
| All API (p95) | < 500ms | `histogram_quantile(0.95, vtv_http_request_duration_seconds)` | 0.1% of requests > 500ms | `VTVHighLatencyP95` | [high-latency.md](runbooks/high-latency.md) |
| All API (p99) | < 2s | `histogram_quantile(0.99, ...)` | 0.01% of requests > 2s | `VTVHighLatencyP99` | [high-latency.md](runbooks/high-latency.md) |
| Health endpoints | < 100ms | p95 filtered by path | informational | — | — |

## Error Rate
| Scope | SLO Target | Measurement | Error Budget (30d) | Alert Rule | Runbook |
|-------|------------|-------------|-------------------|------------|---------|
| All API (5xx) | < 1% | `rate(status=~"5..")` / `rate(total)` | 1% of requests returning 5xx | `VTVHighErrorRate` | [high-error-rate.md](runbooks/high-error-rate.md) |

## Infrastructure
| Component | SLO Target | Measurement | Alert Rule | Runbook |
|-----------|------------|-------------|------------|---------|
| DB pool utilization | < 80% of (pool_size + max_overflow) | `vtv_db_pool_checked_out + vtv_db_pool_overflow` / 8 | `VTVDBPoolExhaustion` | [db-pool-exhaustion.md](runbooks/db-pool-exhaustion.md) |
| Circuit breaker | closed (0) | `vtv_circuit_breaker_state` | `VTVCircuitBreakerOpen` | [circuit-breaker-open.md](runbooks/circuit-breaker-open.md) |
| Poller liveness | tick within 2× interval | `time() - vtv_poller_last_tick_seconds` | `VTVPollerStale` | [poller-stale.md](runbooks/poller-stale.md) |
| Redis cache hit rate | > 50% (informational) | hits / (hits + misses) | — | — |
```

**Validation:** File exists, markdown renders, all runbook links point to files that will exist.

### Step 2: Create `ops/prometheus/alerts.yml`

Prometheus alerting rules using exact OPS-2.1 metric names. Groups:

**Group 1: `vtv_latency`**
- `VTVHighLatencyP95` — `histogram_quantile(0.95, rate(vtv_http_request_duration_seconds_bucket[10m])) > 0.5` for 10m
- `VTVHighLatencyP99` — `histogram_quantile(0.99, rate(vtv_http_request_duration_seconds_bucket[10m])) > 2` for 10m

**Group 2: `vtv_errors`**
- `VTVHighErrorRate` — `sum(rate(vtv_http_request_duration_seconds_count{status=~"5.."}[5m])) / sum(rate(vtv_http_request_duration_seconds_count[5m])) > 0.01` for 5m

**Group 3: `vtv_infrastructure`**
- `VTVDBPoolExhaustion` — `(vtv_db_pool_checked_out + vtv_db_pool_overflow) / 8 > 0.8` for 5m
- `VTVCircuitBreakerOpen` — `vtv_circuit_breaker_state > 1` for 5m

**Group 4: `vtv_pollers`**
- `VTVPollerStale` — `time() - vtv_poller_last_tick_seconds > 240` for 2m (conservative: 4× typical 60s interval)

**Group 5: `vtv_agent_tools`**
- `VTVAgentToolSlow` — `histogram_quantile(0.95, rate(vtv_agent_tool_duration_seconds_bucket[10m])) > 10` for 10m (informational)

Each alert includes:
- `labels.severity`: critical | warning
- `annotations.summary`: one-line description
- `annotations.description`: detailed description with `{{ $value }}` template
- `annotations.runbook_url`: relative path `docs/runbooks/{name}.md`

**Validation:** `python -c "import yaml; yaml.safe_load(open('ops/prometheus/alerts.yml'))"` succeeds. Structure matches Prometheus alert rule schema.

### Step 3: Create `ops/prometheus/README.md`

Short operational README:
- What the alert rules file contains
- How to load into Prometheus (`rule_files` config directive)
- How to validate (`promtool check rules alerts.yml`)
- How to test alerts (`amtool` or Alertmanager web UI)
- Link to `docs/slos.md` for SLO rationale
- Link to `docs/runbooks/` for remediation

**Validation:** File exists, links are valid.

### Step 4: Create runbook placeholders

5 runbook files in `docs/runbooks/`, each with consistent structure:

```markdown
# {Alert Name} Runbook

## Alert
- **Name:** `{AlertName}`
- **Severity:** {critical|warning}
- **Fires when:** {human-readable condition}

## Impact
{What users/services are affected}

## Investigation
1. {Step 1}
2. {Step 2}
3. {Step 3}

## Remediation
- **Quick fix:** {immediate action}
- **Root cause fix:** {longer-term action}

## Escalation
- If not resolved in 15 minutes: escalate to {team/person}

## Related
- SLO: [docs/slos.md](../slos.md)
- Metrics: [app/core/metrics.py](../../app/core/metrics.py)
- Health probes: [app/core/health.py](../../app/core/health.py)
```

Runbooks to create:
1. `docs/runbooks/high-latency.md` — p95/p99 latency breach. Check: slow queries, Redis, external APIs.
2. `docs/runbooks/high-error-rate.md` — 5xx error rate > 1%. Check: logs, recent deploys, DB health.
3. `docs/runbooks/circuit-breaker-open.md` — LLM provider circuit breaker open. Check: provider status page, fallback behavior.
4. `docs/runbooks/poller-stale.md` — Background poller stopped ticking. Check: task logs, Redis connectivity, asyncio task list.
5. `docs/runbooks/db-pool-exhaustion.md` — DB pool > 80%. Check: slow queries, connection leaks, pool config.

**Validation:** All 5 files exist, consistent heading structure.

### Step 5: Update `docs/runbooks/README.md`

Add the 5 new runbooks to the index, maintaining existing format.

**Validation:** README lists all runbook files in `docs/runbooks/`.

### Step 6: Create `app/tests/test_ops_conventions.py`

Convention tests that validate:
1. `ops/prometheus/alerts.yml` exists and parses as valid YAML
2. Alert rules have required structure (`groups` → `rules` → `alert`, `expr`, `for`, `annotations`)
3. Every alert has `annotations.runbook_url` pointing to an existing file
4. `docs/slos.md` exists
5. Every runbook referenced in SLOs exists in `docs/runbooks/`

Pattern: Follow `app/tests/test_security.py` convention test style.

**Validation:** `uv run pytest app/tests/test_ops_conventions.py -v` passes.

### Step 7: Update `Makefile`

Add target:
```makefile
validate-alerts: ## Validate Prometheus alert rules YAML structure
	@uv run python -c "import yaml, sys; rules = yaml.safe_load(open('ops/prometheus/alerts.yml')); assert 'groups' in rules, 'Missing groups key'; print(f'✓ {sum(len(g[\"rules\"]) for g in rules[\"groups\"])} alert rules validated')"
	@echo "Note: Install promtool for full validation: promtool check rules ops/prometheus/alerts.yml"
```

**Validation:** `make validate-alerts` exits 0.

## SLO Rationale

| SLO | Target | Rationale |
|-----|--------|-----------|
| p95 latency < 500ms | Standard for internal APIs serving a CMS dashboard |
| p99 latency < 2s | Agent tool calls and GTFS imports can be slow; 2s accommodates |
| Error rate < 1% | Conservative first pass; tighten after 30d baseline data |
| DB pool < 80% | pool_size=3 + max_overflow=5 = 8 total; 80% = 6.4 connections as warning threshold |
| Circuit breaker closed | Any open breaker means degraded LLM functionality |
| Poller liveness < 4× interval | 2× is health probe threshold; 4× is alert threshold (avoid flapping) |

## Preflight Warnings

- No existing files to overwrite — all targets are net-new
- `promtool` not installed locally — Python YAML validation is primary, promtool is advisory
- Unrelated change in `app/core/jobs/tests/test_queue.py` — will not conflict

## Security Checklist

- [x] No credentials in alert rules YAML
- [x] No internal IPs/hostnames in README (use placeholders like `<prometheus-host>`)
- [x] Runbook URLs are relative paths, not absolute URLs
- [x] No sensitive information in runbook placeholders

## Verification

- [ ] `make check` passes (lint + types + tests)
- [ ] `make validate-alerts` exits 0
- [ ] `uv run pytest app/tests/test_ops_conventions.py -v` passes
- [ ] `python -c "import yaml; yaml.safe_load(open('ops/prometheus/alerts.yml'))"` succeeds
- [ ] All runbook files referenced in alerts exist
- [ ] `docs/slos.md` renders correctly in markdown
- [ ] pyright errors ≤ baseline (0 errors before)
- [ ] No secrets in any new files
