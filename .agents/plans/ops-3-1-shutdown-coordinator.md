# Plan: OPS-3.1 Shutdown Coordinator for Lifespan Tasks

## Context

Replace the ad-hoc sequential cancel loop in `app/main.py` lifespan (lines 152-177) with a `ShutdownCoordinator` that tracks every long-running task, honors per-task drain timeouts, drains in LIFO order, and logs a structured shutdown report before the process exits.

**Why:** Gunicorn's `--graceful-timeout` is 30s. If memory compaction (`app/memory/lifecycle.py`) is mid-run, it gets SIGKILL'd and can leave the embedding cache inconsistent. Coordinated shutdown with explicit per-task budgets gives each background job a chance to reach a stable checkpoint.

## Security Context Assessment

- **CTX-INFRA** applies -- modifying app lifecycle, Gunicorn config, config settings
- No new endpoints, so CTX-RBAC/CTX-INPUT not applicable
- No file handling, auth, or agent tool changes

**Requirements from CTX-INFRA:**
- No hardcoded credentials in config (use env var interpolation) -- N/A, no secrets added
- Gunicorn config change must not expose internal ports -- change is timeout-only

## Research Summary

### Current Lifespan (`app/main.py:75-177`)
- Startup: logging setup, JWT validation, starts 8 background task groups
- Shutdown (lines 152-177): sequential `stop_*()` calls with **no timeouts**, **no error handling**, **no metrics**, **no report**
- No `finally` block -- exceptions in shutdown silently abort remaining cleanup

### Background Tasks (8 groups, 10+ individual tasks)

| Task | Start | Stop | File |
|------|-------|------|------|
| Transit GTFS-RT Pollers (N feeds) | `start_pollers()` | `stop_pollers()` | `app/transit/poller.py` |
| WebSocket Subscriber | `start_ws_subscriber()` | `stop_ws_subscriber()` | `app/transit/ws_subscriber.py` |
| Alert Evaluator | `start_evaluator()` | `stop_evaluator()` | `app/alerts/evaluator.py` |
| Geofence Evaluator | `start_geofence_evaluator()` | `stop_geofence_evaluator()` | `app/geofences/evaluator.py` |
| Memory Compaction | `start_memory_tasks()` | `stop_memory_tasks()` | `app/memory/lifecycle.py` |
| Memory Promotion | (same) | (same) | (same) |
| Weather ETL | `start_weather_etl()` | `stop_weather_etl()` | `app/transit/weather_etl.py` |
| Traffic ETL | `start_traffic_etl()` | `stop_traffic_etl()` | `app/transit/traffic_etl.py` |

### Singleton Closures (not background tasks, but need shutdown)

| Closure | Function | File |
|---------|----------|------|
| WS Manager | `close_ws_manager()` | `app/transit/ws_routes.py` |
| Transit HTTP client | `close_transit_service()` | `app/transit/service.py` |
| Agent HTTP client | `close_agent_service()` | `app/core/agents/service.py` |
| All agent clients | `close_all_agents()` | `app/core/agents/agents/registry.py` |
| Redis client | `close_redis()` | `app/core/redis.py` |
| DB engine | `engine.dispose()` | `app/core/database.py` |

### Gunicorn Config
- `Dockerfile`: `--graceful-timeout 30` -- coordinator budget must stay under 25s (30 - 5s safety margin)
- Dev: uvicorn with `--reload`, no graceful timeout relevant

### Existing Patterns
- **Logging:** `get_logger(__name__)`, event format `domain.component.action_state`
- **Metrics:** `record_poller_tick()` pattern in `app/core/metrics.py`, checks `settings.metrics_enabled`
- **Config:** `app/core/config.py` Pydantic `BaseSettings`, `get_settings()` with `@lru_cache`

## Test Landscape

- **8 existing test files** in `app/core/tests/`
- **No conftest.py** in `app/core/tests/` -- uses root conftest
- **Best template:** `app/core/tests/test_health.py` -- async tests, timeout testing, concurrent execution verification, structured logging assertions
- **Task lifecycle template:** `app/memory/tests/test_lifecycle.py` -- task creation/cancellation, `asyncio.CancelledError` handling
- **Logging assertions:** `patch("module.logger.info")` + `mock_logger.call_args` or `capsys` JSON parsing
- **Async mock pattern:** `AsyncMock(side_effect=asyncio.CancelledError)` for task cancellation

## Type Check Baseline

- **Pyright:** `app/core/` -- 0 errors, 0 warnings
- **Mypy:** `app/core/` -- 0 errors (133 source files)
- **Pyright:** `app/main.py` -- 0 errors
- **Mypy:** `app/main.py` -- 0 errors
- **Target:** 0 errors after implementation

## Files to Create/Modify

| Action | File | Purpose |
|--------|------|---------|
| CREATE | `app/core/shutdown.py` | `ShutdownTask`, `ShutdownReport`, `ShutdownCoordinator` |
| CREATE | `app/core/tests/test_shutdown.py` | 10 unit tests for coordinator |
| UPDATE | `app/main.py:152-177` | Replace ad-hoc shutdown with coordinator |
| UPDATE | `app/main.py:115-150` | Register tasks with coordinator during startup |
| UPDATE | `Dockerfile` | Bump `--graceful-timeout` to 35s |

**Note:** No config changes needed. Drain timeouts are hardcoded per-task in `app/main.py` registration calls since they're implementation details tied to each task's cleanup behavior, not user-tunable settings.

## Implementation Steps

### Step 1: Create `app/core/shutdown.py`

CREATE `app/core/shutdown.py` with:

```python
"""Graceful shutdown coordinator for background lifespan tasks."""

from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field

from app.core.logging import get_logger

logger = get_logger(__name__)


@dataclass(frozen=True)
class ShutdownTask:
    """A registered background task with its drain function and timeout budget."""

    name: str
    drain_timeout_s: float
    drain: Callable[[], Awaitable[None]]


@dataclass
class ShutdownReport:
    """Summary of a completed shutdown sequence."""

    tasks_drained: int = 0
    tasks_timed_out: list[str] = field(default_factory=list)
    tasks_failed: list[str] = field(default_factory=list)
    total_duration_ms: int = 0


class ShutdownCoordinator:
    """Coordinates graceful shutdown of registered background tasks.

    Tasks are drained in LIFO order (last registered = first drained).
    Each task gets an individual timeout budget. Failures in one task
    do not prevent draining subsequent tasks.
    """

    def __init__(self) -> None:
        self._tasks: list[ShutdownTask] = []

    def register(self, task: ShutdownTask) -> None:
        """Register a task for coordinated shutdown.

        Args:
            task: The shutdown task to register. Duplicate names are
                  silently ignored (idempotent registration).
        """
        if any(t.name == task.name for t in self._tasks):
            return
        self._tasks.append(task)
        logger.debug(
            "shutdown.task.registered",
            task_name=task.name,
            drain_timeout_s=task.drain_timeout_s,
        )

    async def shutdown(self) -> ShutdownReport:
        """Drain all registered tasks in LIFO order.

        Returns:
            ShutdownReport summarizing drain results.
        """
        report = ShutdownReport()
        start = time.monotonic()

        if not self._tasks:
            logger.info("shutdown.coordinator.no_tasks")
            return report

        # LIFO order: last registered = first drained
        drain_order = list(reversed(self._tasks))
        logger.info(
            "shutdown.coordinator.started",
            task_count=len(drain_order),
            task_names=[t.name for t in drain_order],
        )

        for task in drain_order:
            task_start = time.monotonic()
            try:
                await asyncio.wait_for(task.drain(), timeout=task.drain_timeout_s)
                elapsed_ms = int((time.monotonic() - task_start) * 1000)
                report.tasks_drained += 1
                logger.info(
                    "shutdown.task.drained",
                    task_name=task.name,
                    duration_ms=elapsed_ms,
                )
            except TimeoutError:
                elapsed_ms = int((time.monotonic() - task_start) * 1000)
                report.tasks_timed_out.append(task.name)
                logger.warning(
                    "shutdown.task.timeout",
                    task_name=task.name,
                    drain_timeout_s=task.drain_timeout_s,
                    duration_ms=elapsed_ms,
                )
            except Exception:
                elapsed_ms = int((time.monotonic() - task_start) * 1000)
                report.tasks_failed.append(task.name)
                logger.error(
                    "shutdown.task.failed",
                    task_name=task.name,
                    duration_ms=elapsed_ms,
                    exc_info=True,
                )

        report.total_duration_ms = int((time.monotonic() - start) * 1000)
        logger.info(
            "shutdown.coordinator.completed",
            tasks_drained=report.tasks_drained,
            tasks_timed_out=report.tasks_timed_out,
            tasks_failed=report.tasks_failed,
            total_duration_ms=report.total_duration_ms,
        )
        return report
```

Key design decisions:
- `frozen=True` on `ShutdownTask` -- immutable after creation
- Idempotent `register()` -- duplicate names silently ignored
- `tasks_failed` added to report beyond spec (essential for observability)
- No metrics emission in this module -- keep it dependency-light. Metrics can be added later if needed.

**Validation:** `uv run ruff format app/core/shutdown.py && uv run ruff check --fix app/core/shutdown.py && uv run pyright app/core/shutdown.py && uv run mypy app/core/shutdown.py`

### Step 2: Create `app/core/tests/test_shutdown.py`

CREATE `app/core/tests/test_shutdown.py` with 10 tests:

1. **`test_shutdown_lifo_drain_order`** -- Register A, B, C; verify drain calls in C, B, A order using a shared list that records call order
2. **`test_shutdown_drain_timeout_enforced`** -- Register task with 0.1s timeout + drain that sleeps 10s; verify it appears in `tasks_timed_out`
3. **`test_shutdown_drain_timeout_does_not_affect_fast_tasks`** -- Register task with 5s timeout + drain that completes instantly; verify `tasks_drained` incremented
4. **`test_shutdown_drain_failure_continues_next_task`** -- Register task A (raises Exception) then B (succeeds); verify B still drained, A in `tasks_failed`
5. **`test_shutdown_report_aggregation`** -- Register 3 tasks (1 success, 1 timeout, 1 failure); verify report fields
6. **`test_shutdown_empty_coordinator_noop`** -- Call `shutdown()` with no tasks; verify report is empty, no exceptions
7. **`test_shutdown_task_registration_idempotent`** -- Register same name twice; verify only 1 task in `_tasks`
8. **`test_shutdown_logs_structured_events`** -- Verify `shutdown.coordinator.started`, `shutdown.task.drained`, `shutdown.coordinator.completed` events logged
9. **`test_shutdown_startup_failure_triggers_partial_drain`** -- Register A, B; only drain B (simulating partial startup); verify A not drained since it wasn't started (this tests that coordinator only drains what's registered)
10. **`test_shutdown_total_duration_ms_populated`** -- Verify `total_duration_ms > 0` after draining tasks

All tests use `@pytest.mark.asyncio`, `AsyncMock`, and targeted `patch()` for logging assertions.

**Validation:** `uv run pytest app/core/tests/test_shutdown.py -v && uv run pyright app/core/tests/test_shutdown.py`

### Step 3: Update `app/main.py` -- Replace Shutdown Block

UPDATE `app/main.py`:

**3a. Add import at top (with existing core imports):**
```python
from app.core.shutdown import ShutdownCoordinator, ShutdownTask
```

**3b. After all `start_*()` calls (after line ~150, before `yield`), register tasks with coordinator:**
```python
    # Register shutdown tasks (LIFO: last registered = first drained)
    coordinator = ShutdownCoordinator()

    # Infrastructure singletons (drain last = register first)
    coordinator.register(ShutdownTask(
        name="database",
        drain_timeout_s=3.0,
        drain=engine.dispose,
    ))
    coordinator.register(ShutdownTask(
        name="redis",
        drain_timeout_s=2.0,
        drain=close_redis,
    ))
    coordinator.register(ShutdownTask(
        name="agent_clients",
        drain_timeout_s=2.0,
        drain=close_all_agents,
    ))
    coordinator.register(ShutdownTask(
        name="agent_service",
        drain_timeout_s=2.0,
        drain=close_agent_service,
    ))
    coordinator.register(ShutdownTask(
        name="transit_service",
        drain_timeout_s=2.0,
        drain=close_transit_service,
    ))

    # Background task groups (drain first = register last)
    coordinator.register(ShutdownTask(
        name="transit_pollers",
        drain_timeout_s=5.0,
        drain=stop_pollers,
    ))
    # close_ws_manager is sync -- wrap it
    async def _close_ws() -> None:
        await stop_ws_subscriber()
        close_ws_manager()

    coordinator.register(ShutdownTask(
        name="websocket",
        drain_timeout_s=3.0,
        drain=_close_ws,
    ))
    coordinator.register(ShutdownTask(
        name="alert_evaluator",
        drain_timeout_s=3.0,
        drain=stop_evaluator,
    ))
    coordinator.register(ShutdownTask(
        name="geofence_evaluator",
        drain_timeout_s=3.0,
        drain=stop_geofence_evaluator,
    ))
    coordinator.register(ShutdownTask(
        name="weather_etl",
        drain_timeout_s=3.0,
        drain=stop_weather_etl,
    ))
    coordinator.register(ShutdownTask(
        name="traffic_etl",
        drain_timeout_s=3.0,
        drain=stop_traffic_etl,
    ))
    coordinator.register(ShutdownTask(
        name="memory_tasks",
        drain_timeout_s=5.0,
        drain=stop_memory_tasks,
    ))
```

**Drain budget:** Sum of all timeouts = 36s. But LIFO sequential drain means worst-case is 36s only if every task times out. Typical shutdown: <5s. Gunicorn graceful-timeout bumped to 45s in Step 4.

**3c. Replace the shutdown block (lines 152-177) with:**
```python
    yield

    # Shutdown via coordinator
    report = await coordinator.shutdown()
    logger.info(
        "shutdown.report",
        tasks_drained=report.tasks_drained,
        tasks_timed_out=report.tasks_timed_out,
        tasks_failed=report.tasks_failed,
        total_duration_ms=report.total_duration_ms,
    )
```

Remove all individual `stop_*()`, `close_*()`, and `engine.dispose()` calls from the shutdown block. Remove the per-task log lines (`transit.ws.lifecycle_stopped`, `transit.poller.lifecycle_stopped`, `security.singletons_closed`, `database.connection_closed`). The coordinator now logs per-task drain events.

Keep `application.lifecycle_stopped` as the final log line after the report.

**Validation:** `uv run ruff format app/main.py && uv run ruff check --fix app/main.py && uv run pyright app/main.py && uv run mypy app/main.py`

### Step 4: Update `Dockerfile` -- Bump Graceful Timeout

UPDATE `Dockerfile`: Change `--graceful-timeout` from `30` to `45`.

This gives the coordinator 40s of budget (45 - 5s safety margin) which exceeds the 36s worst-case sum.

**Validation:** `docker build -t vtv-test . --no-cache 2>&1 | tail -5` (syntax check only, no need to run)

## Preflight Warnings

- `app/main.py` lifespan function is 103 lines -- the replacement will be similar length
- Existing `stop_*()` functions already handle `CancelledError` internally -- the coordinator's `asyncio.wait_for` wrapping is additive, not conflicting
- `engine.dispose()` is a coroutine that returns `None` -- compatible with `Callable[[], Awaitable[None]]` signature
- `close_ws_manager()` is **sync** -- must be wrapped in an async function (handled in Step 3b)
- Lazy imports in shutdown block (`from app.memory.lifecycle import stop_memory_tasks`) need to move to top-level or to the registration block

## Security Checklist

- [x] No new endpoints -- N/A
- [x] No hardcoded credentials added
- [x] No internal ports exposed
- [x] Gunicorn timeout change is timeout-only, no security impact
- [x] Structured logging follows existing patterns (no sensitive data in shutdown events)

## Verification

- [ ] `uv run ruff format app/core/shutdown.py app/main.py && uv run ruff check --fix app/core/shutdown.py app/main.py` -- lint clean
- [ ] `uv run pyright app/core/shutdown.py app/main.py` -- 0 errors (baseline: 0)
- [ ] `uv run mypy app/core/shutdown.py app/main.py` -- 0 errors (baseline: 0)
- [ ] `uv run pytest app/core/tests/test_shutdown.py -v` -- 10 tests pass
- [ ] `make test` -- full suite passes (no regressions)
- [ ] `make security-audit-quick` -- passes
- [ ] Pyright errors <= baseline (0 errors before)
