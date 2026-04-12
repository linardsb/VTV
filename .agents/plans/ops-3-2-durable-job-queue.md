# Plan: OPS-3.2 Durable Job Queue for Memory Lifecycle

## Context

Bare `asyncio.create_task()` in `app/memory/lifecycle.py` dies with the process. If Gunicorn restarts during a multi-hour compaction run, the job is lost and procedural promotion never catches up, silently degrading agent memory quality. A durable queue (Arq on Redis) gives at-least-once semantics with retry on transient failure.

## Security Context Assessment

| Context | Active | Reason |
|---------|--------|--------|
| CTX-RBAC | Yes | New admin endpoint (`GET /admin/jobs/status`) needs `require_role(["admin"])` + rate limiting |
| CTX-INFRA | Yes | Docker service addition, Redis connection config, env var interpolation |
| CTX-AUTH | No | No auth flow changes |
| CTX-FILE | No | No file handling |
| CTX-AGENT | No | No agent tool changes |
| CTX-INPUT | No | Admin endpoint is read-only, no user input |

## Research Summary

### Current State (`app/memory/lifecycle.py`:1-107)
- `_run_at_hour()` — infinite sleep loop scheduling daily at UTC hour
- `_run_compaction()` — one cycle: `get_db_context()` → `MemoryService.compact()` → log + metrics
- `_run_promotion()` — one cycle: `get_db_context()` → `MemoryService.promote_episodes()` → log + metrics
- `start_memory_tasks()` / `stop_memory_tasks()` — create/cancel global `asyncio.Task` refs
- Called from `app/main.py`:122-124 (startup) and :153-155 (shutdown)

### Config (`app/core/config.py`:266-282)
- `memory_enabled: bool = True`
- `memory_compaction_cron_hour: int = 3`
- `memory_promotion_cron_hour: int = 3`

### Redis (`app/core/redis.py`)
- Singleton via `get_redis()` — `redis.asyncio.Redis` with `decode_responses=True`
- **Note:** Arq uses its own `arq.connections.RedisSettings`, NOT the redis-py client. Parse `settings.redis_url` into Arq's format.

### Docker (`docker-compose.yml`:37-63, `docker-compose.prod.yml`:20-27)
- Redis already a required service with healthcheck
- App service pattern: env_file, depends_on, healthcheck, security_opt, cap_drop

### Background Task Pattern (weather_etl, traffic_etl, evaluators)
- All use global `_task` + `_running` flag + `asyncio.create_task()` + start/stop in lifespan
- Leader election via Redis SETNX for cross-worker safety

### Key Design Decision: `bridge.py` NOT migrated
- `persist_agent_episode()` is fast fire-and-forget (~ms), not a multi-hour job
- Does NOT need durability guarantees — leave unchanged

## Test Landscape

### Existing Fixtures (`app/memory/tests/conftest.py`)
- `make_memory(**overrides)` — factory with defaults
- `make_embedding(dim=1024)` — dummy vector
- `mock_db`, `repo`, `service` — standard mocks

### Mock Patterns
- Redis: `MagicMock()` (sync methods), `AsyncMock()` only for `.execute()`
- Background tasks: mock `asyncio.create_task()`, verify call count
- Feature flags: `patch("...get_settings")` → set return value attributes
- DB context: mock `__aenter__`/`__aexit__` on `get_db_context()`

## Type Check Baseline

| Directory | Pyright | Mypy |
|-----------|---------|------|
| `app/memory/` | 0 errors | 0 errors (16 files) |
| `app/core/` | 0 errors | 0 errors (133 files) |

**arq** ships `py.typed` (PEP 561) — no stubs needed. Pyright/mypy resolve types natively.

## Files to Create/Modify

| Action | File | Purpose |
|--------|------|---------|
| UPDATE | `pyproject.toml` | Add `arq>=0.26` dependency |
| CREATE | `app/core/jobs/__init__.py` | Package init |
| CREATE | `app/core/jobs/queue.py` | Arq pool wrapper + `enqueue()` helper |
| CREATE | `app/core/jobs/worker.py` | `WorkerSettings` with cron entries for compaction (6h) and promotion (daily 03:00) |
| CREATE | `app/core/jobs/routes.py` | `GET /admin/jobs/status` — last run, next run, failure count |
| CREATE | `app/core/jobs/schemas.py` | Response schemas for job status endpoint |
| UPDATE | `app/core/config.py` | Add `background_queue_enabled: bool = False` + Arq-related settings |
| UPDATE | `app/memory/lifecycle.py` | Dual-path: flag OFF = existing `asyncio.create_task()`; flag ON = no-op (arq worker handles it) |
| UPDATE | `app/main.py` | Register `/admin/jobs` router; add arq pool init/close to lifespan |
| UPDATE | `docker-compose.yml` | Add `vtv-worker` service |
| UPDATE | `docker-compose.prod.yml` | Add `vtv-worker` with resource limits |
| CREATE | `app/core/jobs/tests/__init__.py` | Test package |
| CREATE | `app/core/jobs/tests/conftest.py` | Fixtures: mock_arq_pool, mock_redis_settings |
| CREATE | `app/core/jobs/tests/test_queue.py` | Tests for enqueue + execute, retry, idempotency |
| CREATE | `app/core/jobs/tests/test_worker.py` | Tests for cron trigger, Redis reconnect, shutdown |
| CREATE | `app/core/jobs/tests/test_routes.py` | Tests for admin status API |
| CREATE | `app/core/jobs/tests/test_feature_flag.py` | Tests for flag gating |

## Implementation Steps

### Step 1: Add arq dependency
**File:** `pyproject.toml`
**Action:** Add `"arq>=0.26"` to `dependencies` list.
**Validation:** `uv lock && uv sync`

### Step 2: Add config settings
**File:** `app/core/config.py`
**Action:** Add after line 282 (memory section):
```python
# Durable job queue (OPS-3.2)
background_queue_enabled: bool = False  # Feature flag: False = asyncio tasks, True = arq worker
arq_max_jobs: int = 10
arq_job_timeout_seconds: int = 3600  # 1h default, compaction may take longer
arq_retry_count: int = 3
arq_compaction_interval_hours: int = 6
arq_promotion_cron_hour: int = 3  # UTC
```
**Note:** When `background_queue_enabled=True`, the arq worker's cron entries take over from `memory_compaction_cron_hour`/`memory_promotion_cron_hour`. Both settings remain — old ones for flag-OFF path, new ones for flag-ON path.
**Validation:** `uv run pyright app/core/config.py`

### Step 3: Create queue module
**File:** `app/core/jobs/__init__.py` — empty
**File:** `app/core/jobs/queue.py`
**Action:** Create Arq pool wrapper:
- `_parse_redis_settings(redis_url: str) -> RedisSettings` — parse URL into Arq's `RedisSettings(host, port, password, database)`
- `_pool: ArqRedis | None = None` — module-level singleton
- `async def get_arq_pool() -> ArqRedis` — lazy init from `settings.redis_url`
- `async def close_arq_pool() -> None` — cleanup
- `async def enqueue(task_name: str, *args: Any, _defer_until: datetime | None = None, _job_id: str | None = None) -> Job | None` — wraps `pool.enqueue_job()`
- Guard: if `not settings.background_queue_enabled`, log warning and return None
**Validation:** `uv run ruff format app/core/jobs/ && uv run ruff check --fix app/core/jobs/ && uv run pyright app/core/jobs/`

### Step 4: Create worker settings
**File:** `app/core/jobs/worker.py`
**Action:** Define `WorkerSettings` class for `arq app.core.jobs.worker.WorkerSettings`:
```python
from arq import cron
from arq.connections import RedisSettings

class WorkerSettings:
    functions = [run_compaction, run_promotion]
    cron_jobs = [
        cron(run_compaction, hour=None, minute={0}, second=0,
             run_at_startup=False, unique=True),  # Every hour at :00
        cron(run_promotion, hour={3}, minute=0, second=0,
             run_at_startup=False, unique=True),   # Daily 03:00 UTC
    ]
    redis_settings = ...  # From _parse_redis_settings
    max_jobs = ...        # From settings.arq_max_jobs
    job_timeout = ...     # From settings.arq_job_timeout_seconds
```
- `async def run_compaction(ctx: dict[str, Any]) -> dict[str, int]` — calls existing `_run_compaction()` from lifecycle, returns result dict
- `async def run_promotion(ctx: dict[str, Any]) -> dict[str, int]` — calls existing `_run_promotion()` from lifecycle, returns result dict
- Use `_ = ctx` to satisfy ARG001
- Compaction cron: every `arq_compaction_interval_hours` (use `hour={h for h in range(0, 24, interval)}`)
- Worker startup/shutdown hooks for logging
**Validation:** `uv run pyright app/core/jobs/worker.py`

### Step 5: Create response schemas
**File:** `app/core/jobs/schemas.py`
**Action:** Create:
```python
class JobStatusEntry(BaseModel):
    name: str
    last_run: datetime | None
    next_run: datetime | None
    last_result: str | None  # "success" | "failed" | None
    failure_count: int
    last_duration_seconds: float | None

class JobStatusResponse(BaseModel):
    queue_enabled: bool
    jobs: list[JobStatusEntry]
```
**Validation:** `uv run pyright app/core/jobs/schemas.py`

### Step 6: Create admin routes
**File:** `app/core/jobs/routes.py`
**Action:** Create:
```python
router = APIRouter(prefix="/admin/jobs", tags=["admin"])

@router.get("/status", response_model=JobStatusResponse)
@limiter.limit("30/minute")
async def get_job_status(
    request: Request,
    _current_user: User = Depends(require_role(["admin"])),
) -> JobStatusResponse:
```
- If `background_queue_enabled=False`: return `queue_enabled=False, jobs=[]`
- If enabled: query arq for job results via `pool.all_job_results()` or maintain a lightweight status dict updated by worker hooks
- Use `# noqa: B008` on `Depends()` / `Query()` calls
**Validation:** `uv run pyright app/core/jobs/routes.py`

### Step 7: Update lifecycle.py — dual-path gating
**File:** `app/memory/lifecycle.py`
**Action:** Modify `start_memory_tasks()`:
```python
async def start_memory_tasks() -> None:
    global _compaction_task, _promotion_task
    settings = get_settings()

    if not settings.memory_enabled:
        logger.info("memory.lifecycle.disabled")
        return

    if settings.background_queue_enabled:
        logger.info("memory.lifecycle.deferred_to_queue")
        return  # Arq worker handles scheduling

    # Existing asyncio.create_task() path — unchanged
    _compaction_task = asyncio.create_task(...)
    _promotion_task = asyncio.create_task(...)
```
Modify `stop_memory_tasks()` similarly — skip cancellation when queue is enabled (nothing to cancel).
**DO NOT delete old code** — gate it behind the flag.
**Validation:** `uv run pyright app/memory/lifecycle.py && uv run pytest app/memory/tests/test_lifecycle.py -v`

### Step 8: Update main.py — router + pool lifecycle
**File:** `app/main.py`
**Action:**
1. Import and register jobs router: `from app.core.jobs.routes import router as jobs_router` + `app.include_router(jobs_router)`
2. In lifespan startup (after memory tasks): init arq pool if enabled
3. In lifespan shutdown (before close_redis): close arq pool
**Validation:** `uv run pyright app/main.py`

### Step 9: Update Docker services
**File:** `docker-compose.yml`
**Action:** Add after `app` service:
```yaml
  vtv-worker:
    build:
      context: .
      dockerfile: Dockerfile
    command: ["arq", "app.core.jobs.worker.WorkerSettings"]
    volumes:
      - ./app:/app/app
      - /app/.venv
    env_file:
      - path: .env
        required: false
    environment:
      - PYTHONUNBUFFERED=1
      - LOG_LEVEL=${LOG_LEVEL:-INFO}
      - DATABASE_URL=postgresql+asyncpg://${POSTGRES_USER:-postgres}:${POSTGRES_PASSWORD:-postgres}@db:5432/${POSTGRES_DB:-vtv_db}
      - REDIS_URL=redis://:${REDIS_PASSWORD:-devpassword}@redis:6379/0
      - BACKGROUND_QUEUE_ENABLED=true
    depends_on:
      db:
        condition: service_healthy
      redis:
        condition: service_healthy
      migrate:
        condition: service_completed_successfully
    restart: unless-stopped
    security_opt:
      - no-new-privileges:true
    cap_drop:
      - ALL
    deploy:
      resources:
        limits:
          cpus: "1.0"
          memory: 1G
    profiles:
      - worker  # Only starts with --profile worker
```
**Note:** Uses `profiles: [worker]` so `make docker` doesn't start it by default. Start with `docker compose --profile worker up -d`.

**File:** `docker-compose.prod.yml`
**Action:** Add:
```yaml
  vtv-worker:
    volumes: !reset []
    read_only: true
    tmpfs:
      - /tmp:size=100M
    environment:
      - PYTHONUNBUFFERED=1
      - LOG_LEVEL=${LOG_LEVEL:-WARNING}
      - DATABASE_URL=postgresql+asyncpg://${POSTGRES_USER:-postgres}:${POSTGRES_PASSWORD}@db:5432/${POSTGRES_DB:-vtv_db}
      - REDIS_URL=redis://:${REDIS_PASSWORD:-}@redis:6379/0
      - ENVIRONMENT=production
      - BACKGROUND_QUEUE_ENABLED=true
    deploy:
      resources:
        limits:
          cpus: "1.0"
          memory: 1G
```
**Validation:** `docker compose config --quiet`

### Step 10: Write tests (14 total)

**File:** `app/core/jobs/tests/conftest.py`
```python
# Fixtures: mock_arq_pool (MagicMock with async enqueue_job),
# mock_settings_queue_enabled, mock_settings_queue_disabled
```

**File:** `app/core/jobs/tests/test_queue.py` — 4 tests
1. `test_enqueue_and_execute` — enqueue a compaction job, verify pool.enqueue_job called with correct args
2. `test_enqueue_returns_job_reference` — verify Job object returned
3. `test_retry_on_transient_failure` — mock first call raising `ConnectionError`, verify arq retry config
4. `test_retry_exhausted_logs_failure` — after max retries, verify error logged

**File:** `app/core/jobs/tests/test_worker.py` — 3 tests
5. `test_cron_schedules_compaction` — verify WorkerSettings.cron_jobs contains compaction entry
6. `test_worker_survives_redis_reconnect` — mock Redis disconnect + reconnect, verify worker continues
7. `test_shutdown_coordinator_integration` — verify worker shutdown hook logs and cleans up

**File:** `app/core/jobs/tests/test_routes.py` — 3 tests
8. `test_admin_status_returns_job_info` — GET /admin/jobs/status with admin user returns JobStatusResponse
9. `test_admin_status_requires_admin_role` — dispatcher user gets 403
10. `test_job_idempotency_via_job_id` — enqueue with same `_job_id` twice, verify only one job created

**File:** `app/core/jobs/tests/test_feature_flag.py` — 3 tests
11. `test_queue_disabled_preserves_asyncio_tasks` — flag OFF: `start_memory_tasks()` creates asyncio tasks as before
12. `test_queue_enabled_skips_asyncio_tasks` — flag ON: `start_memory_tasks()` returns without creating tasks
13. `test_enqueue_noop_when_disabled` — flag OFF: `enqueue()` logs warning and returns None

**File:** `app/core/jobs/tests/test_results.py` — 1 test
14. `test_compaction_result_persisted` — run_compaction job returns dict with `decayed_deleted`, `merged`, `promoted` keys

**Validation per test file:** `uv run pytest {file} -v`

### Step 11: Final validation
```bash
uv run ruff format app/core/jobs/ app/memory/lifecycle.py
uv run ruff check --fix app/core/jobs/ app/memory/lifecycle.py
uv run pyright app/core/jobs/ app/memory/
uv run mypy app/core/jobs/ app/memory/
uv run pytest app/core/jobs/tests/ app/memory/tests/ -v
uv run pytest -m "not integration" -q  # Full unit suite
```

## Preflight Warnings

- `app/memory/tests/test_lifecycle.py` mocks `asyncio.create_task` — tests must be updated to handle the new `background_queue_enabled` branch
- `app/main.py` lifespan has many imports — keep the arq pool init lightweight (lazy via `get_arq_pool()`)
- arq's `cron()` function uses set syntax for hours (`hour={0, 6, 12, 18}`), not integer

## Security Checklist

- [x] `GET /admin/jobs/status` uses `require_role(["admin"])` — admin only
- [x] `@limiter.limit("30/minute")` rate limiting on admin endpoint
- [x] No user input beyond auth token — read-only endpoint
- [x] Docker Redis password via `${REDIS_PASSWORD:-devpassword}` env var interpolation
- [x] Worker service: `security_opt: no-new-privileges`, `cap_drop: ALL`
- [x] No credentials in logs — Redis URL logged via existing `_redact_url()` pattern
- [x] Error responses use generic messages (no internal type leakage)

## Verification

- [ ] `make check` passes (lint + types + tests)
- [ ] `make security-audit-quick` passes
- [ ] `GET /admin/jobs/status` returns 403 for non-admin users
- [ ] `GET /admin/jobs/status` returns 200 with `queue_enabled: false` when flag OFF
- [ ] Pyright errors = 0 (baseline: 0 for both `app/memory/` and `app/core/`)
- [ ] MyPy errors = 0
- [ ] Security convention tests pass: `uv run pytest app/tests/test_security.py -v`
- [ ] All 14 new tests pass: `uv run pytest app/core/jobs/tests/ -v`
- [ ] Existing memory tests still pass: `uv run pytest app/memory/tests/ -v`
- [ ] Docker validation: `docker compose --profile worker config --quiet`
- [ ] Worker starts: `docker compose --profile worker up vtv-worker` → logs show arq startup
