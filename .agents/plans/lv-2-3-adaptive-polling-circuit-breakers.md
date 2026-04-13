# Plan: LV-2.3 Adaptive Polling + Per-Feed Circuit Breakers

## Context

Fixed 10s polling wastes bandwidth at 3am and is too slow at rush hour. Per-feed circuit breakers prevent a single failing upstream from consuming HTTP client resources that starve other feeds. This feature extends `FeedPoller` with hour-of-day adaptive intervals and wires `app/core/resilience.py` `CircuitBreaker` into each poller instance independently.

## Security Context Assessment

- **CTX-INFRA** — Modifying background infrastructure (polling intervals, circuit breaker config). No new endpoints, no user input, no auth changes.
- No other contexts apply (no new endpoints, no file uploads, no agent tools, no user input).

## Research Summary

### Current Architecture
- `FeedPoller` in `app/transit/poller.py` (453 lines) uses fixed `feed_config.poll_interval_seconds` (default 10) in `run()` loop (line 284)
- `CircuitBreaker` in `app/core/resilience.py` (161 lines) — async context manager, 3-state (CLOSED/OPEN/HALF_OPEN), consecutive-failure model, `CircuitOpenError` raised when open
- Module-level state: `_poller_tasks`, `_feed_pollers` — pollers created in `start_pollers()` (line 348)
- Leader election via Redis SETNX prevents duplicate polling across Gunicorn workers
- Prometheus gauge `POLLER_LAST_TICK` with label `poller_name` — currently always `"transit_feed"` (line 206)
- Health probe `_poller_staleness_thresholds()` (health.py:103-118) uses `2 * first_feed.poll_interval_seconds` — needs per-feed adaptive threshold
- Health probe `probe_gtfs_rt_feeds()` (health.py:239-270) checks single `"transit_feed"` label with hardcoded 60s staleness

### Key Files
| File | Lines | Role |
|------|-------|------|
| `app/transit/poller.py` | 453 | FeedPoller class + module lifecycle |
| `app/core/resilience.py` | 161 | CircuitBreaker async context manager |
| `app/core/config.py` | ~450 | Settings (TransitFeedConfig at line 18) |
| `app/core/metrics.py` | 95 | POLLER_LAST_TICK gauge, record_poller_tick() |
| `app/core/health.py` | ~300 | Poller staleness thresholds, feed freshness probe |

## Test Landscape

- `app/transit/tests/test_poller.py` (338 lines, 15 tests) — `_make_feed_config()`, `_make_mock_settings()`, poller lifecycle tests
- `app/transit/tests/test_poller_history.py` (164 lines, 3 tests) — non-blocking write isolation
- `app/core/agents/tests/test_circuit_breaker.py` (436 lines, 19 tests) — comprehensive state machine tests (agent-side breaker, different class)
- No existing tests for `app/core/resilience.py` CircuitBreaker — this is the simpler breaker we're wiring in
- Mock patterns: `MagicMock` for Redis sync, `AsyncMock` for async ops, `@patch` for module-level functions

## Type Check Baseline

- **pyright**: 0 errors on `app/transit/` and `app/core/resilience.py`
- **mypy**: 0 errors (40 source files in `app/transit/`)
- Must maintain zero errors.

## Files to Create/Modify

| Action | File | Purpose |
|--------|------|---------|
| UPDATE | `app/core/config.py` | Add 3 adaptive polling settings |
| UPDATE | `app/transit/poller.py` | Add `_adaptive_interval()`, per-feed `CircuitBreaker`, update `run()` loop |
| UPDATE | `app/core/health.py` | Per-feed staleness thresholds + adaptive-aware freshness probe |
| CREATE | `app/transit/tests/test_adaptive_polling.py` | 12+ tests for adaptive intervals + circuit breaker integration |

## Implementation Steps

### Step 1: Add config settings to `app/core/config.py`

Add three settings to the `Settings` class (after existing transit settings, ~line 100):

```python
# Adaptive polling (LV-2.3)
transit_adaptive_polling_enabled: bool = True
transit_peak_hours: str = "6-9,16-19"
transit_night_hours: str = "23-5"
```

No new `TransitFeedConfig` fields needed — adaptive intervals are global, not per-feed. The per-feed `poll_interval_seconds` becomes the base interval that adaptive logic multiplies.

**Validation:** `uv run ruff check app/core/config.py && uv run pyright app/core/config.py`

### Step 2: Add adaptive interval + circuit breaker to `app/transit/poller.py`

#### 2a: Add imports (top of file)
```python
from app.core.resilience import CircuitBreaker, CircuitOpenError
```

#### 2b: Add module-level helper function (before `FeedPoller` class)
```python
def _parse_hour_ranges(spec: str) -> set[int]:
    """Parse comma-separated hour ranges like '6-9,16-19' into a set of hours."""
    hours: set[int] = set()
    for part in spec.split(","):
        part = part.strip()
        if "-" in part:
            start_s, end_s = part.split("-", 1)
            start, end = int(start_s), int(end_s)
            if start <= end:
                hours.update(range(start, end))
            else:  # wraps midnight, e.g. "23-5"
                hours.update(range(start, 24))
                hours.update(range(0, end))
        else:
            hours.add(int(part))
    return hours


def _adaptive_interval(base_interval: int, hour: int, settings: Settings) -> float:
    """Calculate polling interval based on hour-of-day.

    Peak hours (default 6-9, 16-19): 1x base interval.
    Night hours (default 23-5): 4x base interval.
    Off-peak (everything else): 2x base interval.

    Returns base_interval unchanged when adaptive polling is disabled.
    """
    if not settings.transit_adaptive_polling_enabled:
        return float(base_interval)

    peak = _parse_hour_ranges(settings.transit_peak_hours)
    night = _parse_hour_ranges(settings.transit_night_hours)

    if hour in peak:
        return float(base_interval)
    if hour in night:
        return float(base_interval) * 4
    return float(base_interval) * 2
```

#### 2c: Add `CircuitBreaker` to `FeedPoller.__init__` (after line 74)
```python
self._breaker = CircuitBreaker(
    name=f"feed_{feed_config.feed_id}",
    failure_threshold=5,
    reset_timeout=60.0,
)
```

#### 2d: Refactor `FeedPoller.run()` (replace lines 281-298)
```python
async def run(self, redis_client: Redis) -> None:
    """Run the polling loop for this feed."""
    feed_id = self.feed_config.feed_id
    base_interval = self.feed_config.poll_interval_seconds
    self._running = True
    logger.info("transit.poller.started", feed_id=feed_id, interval_seconds=base_interval)

    while self._running:
        current_hour = datetime.datetime.now(datetime.UTC).hour
        interval = _adaptive_interval(base_interval, current_hour, self._settings)

        start = time.monotonic()
        try:
            async with self._breaker:
                count = await self.poll_once(redis_client)
        except CircuitOpenError:
            logger.warning(
                "transit.feed.circuit_open",
                feed_id=feed_id,
                retry_after=self._breaker.reset_timeout,
            )
            count = 0
        duration_ms = round((time.monotonic() - start) * 1000)
        logger.info(
            "transit.poller.cycle_completed",
            feed_id=feed_id,
            vehicle_count=count,
            duration_ms=duration_ms,
            interval_seconds=interval,
        )
        await asyncio.sleep(interval)
```

Add `import datetime` at top if not already present.

#### 2e: Update metric recording (inside `poll_once`, ~line 206)

Change:
```python
record_poller_tick("transit_feed")
```
To:
```python
record_poller_tick(f"transit_feed_{self.feed_config.feed_id}")
```

**Validation:** `uv run ruff format app/transit/poller.py && uv run ruff check --fix app/transit/poller.py && uv run pyright app/transit/poller.py && uv run mypy app/transit/poller.py`

### Step 3: Update health probe for per-feed + adaptive thresholds in `app/core/health.py`

#### 3a: Update `_poller_staleness_thresholds()` (lines 103-118)

Replace the single `"transit_feed"` entry with per-feed entries:
```python
def _poller_staleness_thresholds(settings: Settings) -> dict[str, float]:
    """Return per-poller staleness thresholds in seconds."""
    thresholds: dict[str, float] = {}

    # Per-feed transit pollers — use 4x base interval (covers worst-case night multiplier)
    for feed in settings.transit_feeds:
        max_interval = float(feed.poll_interval_seconds) * 4  # night = 4x base
        thresholds[f"transit_feed_{feed.feed_id}"] = max_interval * 2  # 2x safety margin

    if not settings.transit_feeds:
        thresholds["transit_feed"] = 120.0  # fallback

    thresholds["alert_evaluator"] = settings.alerts_check_interval_seconds * 2
    thresholds["geofence_evaluator"] = settings.geofence_check_interval_seconds * 2
    thresholds["memory_compaction"] = 25 * 3600
    thresholds["memory_promotion"] = 25 * 3600
    return thresholds
```

#### 3b: Update `probe_gtfs_rt_feeds()` (lines 239-270)

Replace single-label check with per-feed iteration:
```python
async def probe_gtfs_rt_feeds() -> ProbeResult:
    """Probe GTFS-RT feed freshness per feed (non-critical)."""
    start = time.monotonic()
    settings = get_settings()
    stale_feeds: list[str] = []
    checked = 0
    now = time.time()

    feed_ids = [f.feed_id for f in settings.transit_feeds] if settings.transit_feeds else [""]
    for feed_id in feed_ids:
        label = f"transit_feed_{feed_id}" if feed_id else "transit_feed"
        last_tick = _get_poller_last_tick(label)
        if last_tick is not None:
            checked += 1
            # Use 4x base interval * 2 safety = 8x as staleness ceiling
            base = next(
                (f.poll_interval_seconds for f in settings.transit_feeds if f.feed_id == feed_id),
                10,
            )
            max_age = float(base) * 8  # worst-case night (4x) * 2 safety
            if (now - last_tick) > max_age:
                stale_feeds.append(feed_id or "default")

    latency_ms = (time.monotonic() - start) * 1000

    if stale_feeds:
        return ProbeResult(
            name="gtfs_rt_feeds",
            status="degraded",
            latency_ms=round(latency_ms, 2),
            detail=f"stale_feeds={','.join(stale_feeds)}",
            critical=False,
        )

    if checked == 0:
        return ProbeResult(
            name="gtfs_rt_feeds",
            status="degraded",
            latency_ms=round(latency_ms, 2),
            detail="no_tick_recorded",
            critical=False,
        )

    return ProbeResult(
        name="gtfs_rt_feeds",
        status="ok",
        latency_ms=round(latency_ms, 2),
        detail=f"feeds_checked={checked}",
        critical=False,
    )
```

**Validation:** `uv run ruff format app/core/health.py && uv run ruff check --fix app/core/health.py && uv run pyright app/core/health.py && uv run mypy app/core/health.py`

### Step 4: Write tests in `app/transit/tests/test_adaptive_polling.py`

Create 12+ tests covering:

**Adaptive interval calculation (4 tests):**
1. `test_adaptive_interval_peak_hours` — hour 8 → 1x base (10s → 10.0)
2. `test_adaptive_interval_offpeak_hours` — hour 12 → 2x base (10s → 20.0)
3. `test_adaptive_interval_night_hours` — hour 3 → 4x base (10s → 40.0)
4. `test_adaptive_interval_disabled` — returns base unchanged when `transit_adaptive_polling_enabled=False`

**Hour range parsing (2 tests):**
5. `test_parse_hour_ranges_normal` — "6-9,16-19" → {6,7,8,16,17,18}
6. `test_parse_hour_ranges_midnight_wrap` — "23-5" → {23,0,1,2,3,4}

**Circuit breaker per-feed isolation (2 tests):**
7. `test_circuit_breaker_per_feed_isolation` — fail feed A's breaker, feed B still polls normally
8. `test_circuit_breaker_opens_after_failures` — 5 consecutive poll failures → breaker opens → logs `transit.feed.circuit_open`

**Breaker trip + recovery (2 tests):**
9. `test_circuit_open_skips_poll` — when breaker is OPEN, `poll_once` is NOT called, returns 0
10. `test_circuit_recovery_after_timeout` — after reset_timeout, breaker transitions to HALF_OPEN and allows poll

**Prometheus gauge per-feed (2 tests):**
11. `test_metric_label_per_feed` — `record_poller_tick` called with `transit_feed_{feed_id}` not `transit_feed`
12. `test_run_logs_adaptive_interval` — cycle_completed log includes `interval_seconds` field

**Test helpers to create:**
```python
def _make_adaptive_settings(**overrides: Any) -> MagicMock:
    """Mock Settings with adaptive polling config."""
    s = MagicMock()
    s.transit_adaptive_polling_enabled = overrides.get("enabled", True)
    s.transit_peak_hours = overrides.get("peak", "6-9,16-19")
    s.transit_night_hours = overrides.get("night", "23-5")
    s.metrics_enabled = False
    s.redis_vehicle_ttl_seconds = 120
    s.transit_history_enabled = False
    return s
```

**Validation:** `uv run pytest app/transit/tests/test_adaptive_polling.py -v && uv run pyright app/transit/tests/test_adaptive_polling.py`

### Step 5: Update existing poller tests

Update `app/transit/tests/test_poller.py`:
- The metric label change from `"transit_feed"` to `"transit_feed_{feed_id}"` may affect existing assertions — grep for `record_poller_tick` in tests and update any hardcoded `"transit_feed"` string.

Update `app/core/tests/test_health.py` (if assertions reference `"transit_feed"` label):
- Grep for `transit_feed` in health tests and update to per-feed pattern.

**Validation:** `uv run pytest app/transit/tests/ -v && uv run pytest app/core/tests/test_health.py -v`

## Preflight Warnings

- `test_poller.py` line ~206: `record_poller_tick("transit_feed")` assertion will break after metric label change — update in Step 5
- `health.py` `_poller_staleness_thresholds` returns a dict keyed by `"transit_feed"` — must update all consumers
- `probe_gtfs_rt_feeds` has hardcoded `_get_poller_last_tick("transit_feed")` — must update

## Logging Events

| Event | Level | When |
|-------|-------|------|
| `transit.poller.started` | info | Already exists — add `adaptive_enabled` field |
| `transit.poller.cycle_completed` | info | Already exists — add `interval_seconds` field |
| `transit.feed.circuit_open` | warning | New — breaker is OPEN, poll skipped |
| `resilience.circuit_breaker.state_changed` | info/warning | Already exists in CircuitBreaker |

## Security Checklist

No new endpoints added. Infrastructure-only change (CTX-INFRA):
- [x] No hardcoded credentials
- [x] Config via env vars with safe defaults
- [x] No external ports exposed
- [x] Feature-flagged (`transit_adaptive_polling_enabled`)

## Verification

- [ ] `make lint` passes (ruff format + check)
- [ ] `make types` passes (mypy + pyright)
- [ ] `uv run pytest app/transit/tests/ -v` — all transit tests pass
- [ ] `uv run pytest app/core/tests/test_health.py -v` — health tests pass
- [ ] `make test` passes (full unit suite)
- [ ] Pyright errors = 0 (baseline: 0)
- [ ] New tests: 12+ in `test_adaptive_polling.py`
- [ ] Manual verification scenario: Configure 2 feeds. Fail one feed → its breaker opens, other polls normally. Hour 3am → 4x interval. Hour 8am → 1x interval.
