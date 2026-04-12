# Plan: OPS-2.2 Deep `/health` Endpoint with Dependency Probes

## Context

Today's `/health` returns 200 as long as the process is up. Docker/Kubernetes/nginx route traffic to workers with exhausted DB pools or crashed pollers. Deep health catches these before user reports by probing every critical dependency in parallel and returning a structured per-dependency status.

## Security Context Assessment

**Active contexts:** CTX-RBAC (new `/health/deep` endpoint needs admin-only auth), CTX-INFRA (modifies core infrastructure).

- `GET /health` remains unauthenticated (Kubernetes liveness probe)
- `GET /health/deep` requires `require_role("admin")` + rate limiting
- No user input handling (CTX-INPUT not active)
- No file uploads (CTX-FILE not active)

## Research Summary

### Current Implementation (`app/core/health.py:1-177`)
- 4 endpoints: `/health` (liveness), `/health/db`, `/health/redis`, `/health/ready` (composite)
- TTL-cached results (10s) to prevent connection pool exhaustion
- Rate limited at 60/min via `@limiter.limit("60/minute")`
- Router: `APIRouter(tags=["health"])`, registered at `app/main.py:187`

### Dependency Access Points
| Dependency | Access | File:Line |
|-----------|--------|-----------|
| PostgreSQL | `get_db()` → `AsyncSession` → `text("SELECT 1")` | `app/core/database.py:62-80` |
| Redis | `get_redis()` → `redis.ping()` | `app/core/redis.py:31-44` |
| Reranker | `_get_reranker()` → check `_model is not None` | `app/knowledge/reranker.py:51-124` |
| GTFS-RT feeds | `POLLER_LAST_TICK` gauge per `poller_name` | `app/core/metrics.py:74-89` |
| Background pollers | Same `POLLER_LAST_TICK` gauge | `app/core/metrics.py:74-89` |
| LLM providers | `get_breaker_state(name) -> CircuitState` | `app/core/agents/llm.py:78-90` |

### Poller Names (from `record_poller_tick` calls)
- `"transit_feed"` — `app/transit/poller.py:206`
- `"alert_evaluator"` — `app/alerts/evaluator.py:54`
- `"geofence_evaluator"` — `app/geofences/evaluator.py:201`
- `"memory_compaction"` — `app/memory/lifecycle.py:56`
- `"memory_promotion"` — `app/memory/lifecycle.py:65`

### Key Patterns to Reuse
- Auth: `require_role("admin")` from `app/auth/dependencies.py:121-144`
- Config: `get_settings()` from `app/core/config.py:329`
- Logging: `get_logger(__name__)` + `domain.component.action_state` pattern
- Metrics: `POLLER_LAST_TICK` gauge `.collect()` for reading current values
- Circuit breaker: `get_breaker_state()` for LLM provider state without token cost

### Reference Feature
`app/core/agents/provider_health.py` — parallel per-provider tracking, admin-only endpoint, singleton pattern. Closest structural match.

## Test Landscape

### Existing Health Tests (`app/core/tests/test_health.py:1-126`)
- 7 tests: basic health, DB success/failure/logging, readiness success/failure/logging
- Autouse fixture `_clear_db_health_cache` resets module-level caches
- Uses `AsyncMock` for DB, patches `get_settings` and `logger.error`
- Rate limiter disabled: `limiter.enabled = False`

### Mock Patterns
| Dep | Pattern |
|-----|---------|
| DB | `mock_db = AsyncMock(); mock_db.execute = AsyncMock()` |
| Redis | `patch("app.core.redis.get_redis")` → `AsyncMock` with `.ping()` |
| Reranker | `MagicMock()` with `._model` attribute check |
| Pollers | Read `POLLER_LAST_TICK` gauge values via prometheus_client API |
| LLM | `patch("app.core.agents.llm.get_breaker_state")` |

### Security Convention Tests
`app/tests/test_security.py` — checks auth on all endpoints. New endpoints must comply.

## Type Check Baseline

- **pyright app/core/:** 0 errors
- **mypy app/core/:** 0 errors
- **pyright app/main.py:** 0 errors
- **mypy app/main.py:** 0 errors

## Files to Create/Modify

| Action | File | Purpose |
|--------|------|---------|
| UPDATE | `app/core/health.py` | Replace with deep health probing system |
| UPDATE | `app/core/tests/test_health.py` | Add 15 new tests for deep probes |
| UPDATE | `app/core/config.py` | Add `health_deep_cache_ttl_seconds` setting |

**NOT modifying `app/main.py`** — the health router is already registered at line 187. The new endpoints are added to the same router.

## Implementation Steps

### Step 1: Add config setting (`app/core/config.py`)

Add after line 313 (`metrics_enabled`):
```python
# Deep health probes (OPS-2.2)
health_deep_cache_ttl_seconds: float = 5.0
```

**Validation:** `uv run ruff format app/core/config.py && uv run ruff check --fix app/core/config.py && uv run pyright app/core/config.py`

### Step 2: Rewrite `app/core/health.py`

Replace the entire file. The new module provides:

**Data structures (Pydantic schemas, not dataclasses — consistent with codebase):**
```python
class ProbeResult(BaseModel):
    """Result of a single dependency probe."""
    model_config = ConfigDict(frozen=True)

    name: str
    status: Literal["ok", "degraded", "down"]
    latency_ms: float
    detail: str | None = None
    critical: bool = True

class HealthReport(BaseModel):
    """Aggregated health report."""
    model_config = ConfigDict(frozen=True)

    status: Literal["ok", "degraded", "down"]
    version: str
    probes: list[ProbeResult]
    timestamp: str  # ISO 8601
```

**Individual probe functions (all async, all catch exceptions internally):**

1. `probe_postgres(db: AsyncSession) -> ProbeResult` — `SELECT 1` with timing; `pg_stat_activity` count as detail
2. `probe_redis() -> ProbeResult` — `PING` with timing
3. `probe_reranker() -> ProbeResult` — checks model loaded (non-critical)
4. `probe_pollers() -> ProbeResult` (non-critical) — reads `POLLER_LAST_TICK` gauge samples via `prometheus_client`; degraded if any poller > 2x its expected interval stale. **Must use per-poller expected interval map** since daily crons (memory_compaction, memory_promotion) tick once per day:
```python
def _poller_staleness_thresholds(settings: Settings) -> dict[str, float]:
    feed_interval = settings.transit_feeds[0].poll_interval_seconds * 2 if settings.transit_feeds else 120.0
    return {
        "transit_feed": feed_interval,
        "alert_evaluator": settings.alerts_check_interval_seconds * 2,
        "geofence_evaluator": settings.geofence_check_interval_seconds * 2,
        "memory_compaction": 25 * 3600,   # daily + 1h grace
        "memory_promotion": 25 * 3600,    # daily + 1h grace
    }
```
Without this, `memory_compaction` would be falsely reported as degraded 23+ hours per day
5. `probe_gtfs_rt_feeds() -> ProbeResult` — reads `transit_feed` tick specifically; degraded if > 60s stale (non-critical)
6. `probe_llm_providers() -> ProbeResult` — reads circuit breaker state per configured provider; reports `closed|half_open|open` (non-critical, no token cost)

**Probe runner:**
```python
async def _run_probe(
    name: str,
    coro: Awaitable[ProbeResult],
    timeout_s: float = 2.0,
) -> ProbeResult:
    """Run a probe with timeout protection."""
    try:
        return await asyncio.wait_for(coro, timeout=timeout_s)
    except asyncio.TimeoutError:
        return ProbeResult(name=name, status="down", latency_ms=timeout_s * 1000, detail="timeout")
    except Exception as exc:
        return ProbeResult(name=name, status="down", latency_ms=0.0, detail=str(exc)[:200])
```

**Status aggregation:**
- `ok` — all critical probes ok
- `degraded` — all critical probes ok, but >=1 non-critical failed
- `down` — any critical probe not ok

**Endpoints:**

1. `GET /health` — unchanged (process liveness, returns `{"status": "healthy", "service": "api"}`)

2. `GET /health/db` — keep existing (backward compat)

3. `GET /health/redis` — keep existing (backward compat)

4. `GET /health/ready` — upgrade internals to run postgres + redis probes concurrently via `asyncio.gather`, but **preserve the existing response format** (`{"status": "ready", "database": "connected", "redis": "connected|unavailable"}`) for backward compatibility with Docker healthchecks and monitoring. Returns 200 if ok, 503 if down. **No auth required** (k8s probes don't carry JWTs). Cache result for `health_deep_cache_ttl_seconds`.

5. `GET /health/deep` — runs ALL probes concurrently, returns full `HealthReport` JSON. **Admin-only** via `require_role("admin")`. Rate limited 60/min. Returns 200 with status field indicating health (even when degraded — the JSON body carries the truth). Returns 503 only when critical probes are down.

**Key design decisions:**
- Keep existing `/health`, `/health/db`, `/health/redis` endpoints unchanged for backward compatibility
- `/health/ready` upgraded to use parallel probes
- `/health/deep` is new, admin-only
- Probes catch all exceptions internally — a probe failure is reported in the response, never crashes the endpoint
- Cache TTL configurable via settings (default 5s)
- Each probe has a 2s timeout (configurable per probe via the `_run_probe` wrapper)
- **Caching:** `/health/deep` caches the full `HealthReport` for `health_deep_cache_ttl_seconds` (default 5s) in module-level `_deep_health_cache` / `_deep_health_cache_time` (same pattern as existing DB/Redis caches). `/health/ready` similarly caches its result for the same TTL
- Non-critical probes: reranker, GTFS-RT feeds, LLM providers, pollers (their failure = "degraded", not "down")
- Critical probes: postgres, redis only (a stuck `memory_compaction` daily cron shouldn't take the service out of K8s rotation)

**Reading POLLER_LAST_TICK gauge values:**
```python
from prometheus_client import REGISTRY

def _get_poller_last_tick(poller_name: str) -> float | None:
    """Read the last tick timestamp from the Prometheus gauge."""
    for metric in REGISTRY.collect():
        if metric.name == "vtv_poller_last_tick_seconds":
            for sample in metric.samples:
                if sample.labels.get("poller_name") == poller_name:
                    return sample.value
    return None
```

**Structured logging events:**
- `health.deep.probe_completed` — per-probe result (name, status, latency_ms)
- `health.deep.check_completed` — overall status + probe count
- `health.deep.probe_failed` — on probe exception (error level)

**Validation:** `uv run ruff format app/core/health.py && uv run ruff check --fix app/core/health.py && uv run pyright app/core/health.py && uv run mypy app/core/health.py`

### Step 3: Write tests (`app/core/tests/test_health.py`)

Replace with comprehensive test file. Keep existing 7 tests (basic health, DB, readiness) and add 15 new tests:

**Probe unit tests (6 success + 6 failure):**
1. `test_probe_postgres_success` — mock `db.execute` returns, verify `ProbeResult(status="ok")`
2. `test_probe_postgres_failure` — mock `db.execute` raises, verify `status="down"`
3. `test_probe_redis_success` — mock `get_redis()` → `ping()` returns True
4. `test_probe_redis_failure` — mock raises `ConnectionError`
5. `test_probe_reranker_loaded` — mock reranker with `_model` set, verify `status="ok"`
6. `test_probe_reranker_not_loaded` — mock reranker with `_model=None`, verify `status="degraded"`
7. `test_probe_pollers_healthy` — mock `POLLER_LAST_TICK` with recent timestamps
8. `test_probe_pollers_stale` — mock with old timestamps, verify `status="degraded"`
9. `test_probe_gtfs_feeds_fresh` — mock transit_feed tick recent
10. `test_probe_gtfs_feeds_stale` — mock transit_feed tick > 60s old
11. `test_probe_llm_providers_closed` — mock `get_breaker_state` returns CLOSED
12. `test_probe_llm_providers_open` — mock returns OPEN, verify `status="degraded"`

**Endpoint/aggregation tests (3):**
13. `test_deep_health_concurrent_execution` — verify `asyncio.gather` is used (all probes run in parallel)
14. `test_deep_health_timeout_handling` — mock a slow probe, verify it times out at 2s and reports "down"
15. `test_deep_health_aggregation_critical_vs_noncritical` — critical down → status "down"; only non-critical down → status "degraded"; all ok → status "ok"

**Additional endpoint tests (keep from existing + add):**
- `test_deep_health_requires_admin` — non-admin gets 403
- `test_deep_health_returns_full_report` — verify all probe names present in response

**Fixture:**
```python
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
```

**Validation:** `uv run pytest app/core/tests/test_health.py -v && uv run pyright app/core/tests/test_health.py`

## Preflight Warnings

- `app/core/health.py` has module-level mutable caches (`_db_health_cache`, `_redis_health_cache`) — must preserve these for backward compatibility in kept endpoints
- `POLLER_LAST_TICK` is a prometheus_client `Gauge` — reading samples requires iterating `REGISTRY.collect()` which is thread-safe but may return empty list if metrics not initialized
- `get_breaker_state()` returns `CircuitState.CLOSED` for unregistered providers (safe default)
- Redis `ping()` has `# type: ignore[misc]` — keep this pattern for the probe
- Anti-pattern #34: Redis async stubs need `# type: ignore[misc]` on await lines
- Anti-pattern #16: Singleton close must handle closed event loops — not applicable here (probes are request-scoped)

## Security Checklist

| Endpoint | Auth | Rate Limit | Input Validation | Error Handling |
|----------|------|------------|------------------|----------------|
| `GET /health` | None (liveness) | 60/min | N/A | Returns 200 always |
| `GET /health/db` | None | 60/min | N/A | 503 on failure |
| `GET /health/redis` | None | 60/min | N/A | 503 on failure |
| `GET /health/ready` | None (k8s) | 60/min | N/A | 503 on failure |
| `GET /health/deep` | `require_role("admin")` | 60/min | N/A | 200 with status in body, 503 if critical down |

- [x] No user input → no injection risk
- [x] No secrets in probe responses (connection counts, not connection strings)
- [x] Error details truncated to 200 chars (no full stack traces)
- [x] `escape_like()` not needed (no ILIKE queries)

## Verification

- [ ] `uv run ruff format app/core/health.py app/core/config.py app/core/tests/test_health.py`
- [ ] `uv run ruff check --fix app/core/health.py app/core/config.py app/core/tests/test_health.py`
- [ ] `uv run pyright app/core/health.py app/core/config.py app/core/tests/test_health.py`
- [ ] `uv run mypy app/core/health.py app/core/config.py`
- [ ] `uv run pytest app/core/tests/test_health.py -v` — all 22+ tests pass
- [ ] `make check` passes (lint + types + tests)
- [ ] `make security-audit-quick` passes
- [ ] Pyright errors <= baseline (0 errors before)
- [ ] `uv run pytest app/tests/test_security.py -v` — security convention tests pass
- [ ] Manual: Stop Redis → `/health/ready` returns 503 with `redis: down`
- [ ] Manual: `/health/deep` returns full JSON with all 6 probe categories
