# Plan: DDoS Defense - Application-Layer Security Hardening

## Feature Metadata
**Feature Type**: Security Enhancement
**Estimated Complexity**: High
**Primary Systems Affected**: FastAPI middleware, transit service, agent service, health checks, Docker infrastructure, Next.js CMS

## Feature Description

VTV currently has **zero DDoS protection** across the entire stack. The most critical vulnerability: every request to `/api/v1/transit/vehicles` creates a new `httpx.AsyncClient` and `GTFSRealtimeClient` per request, so the 10-second cache is always empty — meaning every single request fires 2 outbound HTTP calls to Rigas Satiksme feeds. The LLM endpoint (`/v1/chat/completions`) is completely open with no rate limiting, no request size limits, and no quota enforcement despite CLAUDE.md documenting "50 queries/user/day" and "EUR 100/month cap".

This plan implements defense-in-depth across 2 phases: Phase 1 fixes critical app-layer vulnerabilities (singleton services, size limits, rate limiting, query quotas). Phase 2 hardens security (HTTP headers, Docker non-root user, nginx reverse proxy, cached health checks, login brute-force protection).

## User Story

As a system administrator deploying VTV
I want the platform to be resilient against abusive traffic and common attack vectors
So that the service remains available for legitimate dispatchers and the LLM API budget is not exhausted by attackers.

## Solution Approach

We use a layered defense strategy that requires **no new infrastructure** for Phase 1 (pure code changes) and minimal infrastructure additions for Phase 2 (nginx container, Docker security).

**Approach Decision:**
We chose `slowapi` for rate limiting because:
- Pure Python, in-memory — no Redis dependency needed for development/MVP
- Built on `limits` library, well-tested with FastAPI
- Per-IP tracking with configurable time windows
- Easily swappable to Redis backend when scaling

**Alternatives Considered:**
- Redis-backed rate limiting: Rejected because VTV is single-instance MVP, Redis adds infrastructure complexity
- Cloudflare/WAF only: Rejected because app-layer defenses are needed regardless of edge protection
- Custom middleware: Rejected because `slowapi` is battle-tested and saves development time

## Relevant Files

The executing agent MUST read these files before starting implementation.

### Core Files
- `CLAUDE.md` — Architecture rules, logging patterns, type checking requirements
- `app/core/config.py` (lines 1-75) — Settings class pattern, `@lru_cache` singleton
- `app/core/middleware.py` (lines 1-114) — Existing middleware setup pattern
- `app/core/exceptions.py` (lines 1-86) — Exception handler registration pattern

### Similar Features (Examples to Follow)
- `app/core/agents/tools/transit/static_cache.py` (lines 406-429) — Module-level singleton pattern with `_static_cache` global variable — **this is exactly the pattern to replicate** for TransitService and AgentService
- `app/core/agents/tools/transit/client.py` (lines 127-150) — `GTFSRealtimeClient` with internal `_CacheEntry` and TTL-based cache

### Files to Modify
- `app/transit/service.py` — Convert `get_transit_service()` to singleton with persistent `GTFSRealtimeClient`
- `app/core/agents/service.py` — Convert `get_agent_service()` to singleton
- `app/core/agents/schemas.py` — Add Pydantic Field constraints for size limits
- `app/core/middleware.py` — Add `BodySizeLimitMiddleware`
- `app/main.py` — Add singleton cleanup in lifespan, register rate limiter exception handler
- `app/core/agents/routes.py` — Add rate limit decorators and quota check
- `app/transit/routes.py` — Add rate limit decorator, use singleton service
- `app/core/health.py` — Add cached health check, rate limit decorators
- `app/core/config.py` — Add rate limit and quota settings
- `pyproject.toml` — Add `slowapi` dependency
- `.env.example` — Add rate limit and quota env vars
- `docker-compose.yml` — Remove exposed DB port, add resource limits, add nginx service, fix AUTH_SECRET
- `Dockerfile` — Add non-root user
- `cms/apps/web/next.config.ts` — Add security headers
- `cms/apps/web/auth.ts` — Add brute-force protection

### New Files to Create
- `app/core/rate_limit.py` — Rate limiter setup and configuration
- `app/core/agents/quota.py` — Daily query quota tracker
- `nginx/nginx.conf` — Reverse proxy configuration
- `nginx/Dockerfile` — Nginx container

## Implementation Plan

### Phase 1: Critical App-Layer Fixes (code changes only)
1. Fix GTFS-RT cache by making TransitService a singleton (biggest immediate impact)
2. Make AgentService a singleton
3. Add Pydantic field constraints + body size middleware
4. Add `slowapi` rate limiting
5. Implement query quota enforcement

### Phase 2: Security Hardening
6. Add HTTP security headers to Next.js
7. Fix hardcoded AUTH_SECRET in docker-compose
8. Add login brute-force protection
9. Docker security hardening (non-root user, resource limits)
10. Add nginx reverse proxy
11. Cache health check DB results

## Step by Step Tasks

IMPORTANT: Execute every step in order, top to bottom. Do not skip steps.

---

### Task 1: Add New Dependencies
**File:** `pyproject.toml` (modify existing)
**Action:** UPDATE

Add `slowapi` to the dependencies list:
- Add `"slowapi>=0.1.9"` to the `[project] dependencies` array (after `sqlalchemy`)

**Per-task validation:**
- `uv run ruff format pyproject.toml`
- `uv run ruff check --fix pyproject.toml` passes

Then run:
```bash
uv sync
```

---

### Task 2: Add Rate Limit and Quota Settings to Config
**File:** `app/core/config.py` (modify existing)
**Action:** UPDATE

Add these fields to the `Settings` class, after the `gtfs_static_cache_ttl_hours` field:

```python
# Rate limiting (requests per minute per IP)
rate_limit_chat: str = "10/minute"
rate_limit_transit: str = "30/minute"
rate_limit_health: str = "60/minute"
rate_limit_default: str = "120/minute"

# Query quota (daily per IP)
agent_daily_quota: int = 50
```

**Per-task validation:**
- `uv run ruff format app/core/config.py`
- `uv run ruff check --fix app/core/config.py` passes
- `uv run mypy app/core/config.py` passes

---

### Task 3: Update .env.example with New Settings
**File:** `.env.example` (modify existing)
**Action:** UPDATE

Add at the end of the file:

```
# Rate Limiting (requests per minute per IP)
# RATE_LIMIT_CHAT=10/minute
# RATE_LIMIT_TRANSIT=30/minute
# RATE_LIMIT_HEALTH=60/minute
# RATE_LIMIT_DEFAULT=120/minute

# Agent Query Quota (daily per IP)
# AGENT_DAILY_QUOTA=50

# Auth (REQUIRED — generate with: openssl rand -base64 32)
# AUTH_SECRET=<generate-a-real-secret>
```

**Per-task validation:**
- File is valid (no syntax to check for .env)

---

### Task 4: Fix TransitService — Make Singleton with Persistent Cache
**File:** `app/transit/service.py` (modify existing)
**Action:** UPDATE

The current code creates a new `httpx.AsyncClient` and `GTFSRealtimeClient` per request, so the GTFS-RT cache (10s TTL) is always empty. Fix by:

1. Make `TransitService.__init__` also create a persistent `GTFSRealtimeClient` as `self._rt_client`
2. In `get_vehicle_positions`, use `self._rt_client` instead of creating a new one on line 64
3. Replace `get_transit_service()` factory with a module-level singleton pattern (same as `static_cache.py` lines 406-429):

```python
# --- Module-level singleton ---

_transit_service: TransitService | None = None


def get_transit_service(settings: Settings | None = None) -> TransitService:
    """Get or create the transit service singleton.

    Reuses the same httpx.AsyncClient and GTFSRealtimeClient across requests
    so the GTFS-RT cache (10s TTL) actually works.

    Args:
        settings: Optional settings override. Uses get_settings() if None.

    Returns:
        Singleton TransitService instance.
    """
    global _transit_service  # noqa: PLW0603
    if _transit_service is None:
        if settings is None:
            settings = get_settings()
        client = httpx.AsyncClient(
            timeout=httpx.Timeout(10.0, connect=5.0),
            limits=httpx.Limits(max_connections=10, max_keepalive_connections=5),
        )
        _transit_service = TransitService(http_client=client, settings=settings)
    return _transit_service


async def close_transit_service() -> None:
    """Close the singleton transit service and its HTTP client.

    Called during application shutdown.
    """
    global _transit_service  # noqa: PLW0603
    if _transit_service is not None:
        await _transit_service._http_client.aclose()
        _transit_service = None
```

4. Update `TransitService.__init__` to store a persistent `GTFSRealtimeClient`:

```python
def __init__(self, http_client: httpx.AsyncClient, settings: Settings) -> None:
    self._http_client = http_client
    self._settings = settings
    self._rt_client = GTFSRealtimeClient(http_client, settings)
```

5. In `get_vehicle_positions`, replace line 64 (`client = GTFSRealtimeClient(...)`) with:
```python
raw_vehicles = await self._rt_client.fetch_vehicle_positions()
trip_updates = await self._rt_client.fetch_trip_updates()
```
Remove the local `client` variable entirely.

**IMPORTANT:** The `noqa: PLW0603` comment is required because Ruff flags `global` statements. This is the established pattern in this codebase (see `static_cache.py`). However, check if `static_cache.py` uses this comment — if not, it may not be needed. Use the same style as the existing codebase.

**Per-task validation:**
- `uv run ruff format app/transit/service.py`
- `uv run ruff check --fix app/transit/service.py` passes
- `uv run mypy app/transit/service.py` passes
- `uv run pyright app/transit/service.py` passes

---

### Task 5: Fix AgentService — Make Singleton
**File:** `app/core/agents/service.py` (modify existing)
**Action:** UPDATE

Same pattern as Task 4. Replace `get_agent_service()` with a module-level singleton:

```python
# --- Module-level singleton ---

_agent_service: AgentService | None = None


def get_agent_service() -> AgentService:
    """Get or create the agent service singleton.

    Reuses the same httpx.AsyncClient across requests for connection pooling.

    Returns:
        Singleton AgentService instance.
    """
    global _agent_service
    if _agent_service is None:
        _agent_service = AgentService()
    return _agent_service


async def close_agent_service() -> None:
    """Close the singleton agent service and its HTTP client.

    Called during application shutdown.
    """
    global _agent_service
    if _agent_service is not None:
        await _agent_service.close()
        _agent_service = None
```

Export `close_agent_service` from the module.

**Per-task validation:**
- `uv run ruff format app/core/agents/service.py`
- `uv run ruff check --fix app/core/agents/service.py` passes
- `uv run mypy app/core/agents/service.py` passes

---

### Task 6: Add Singleton Cleanup to Lifespan
**File:** `app/main.py` (modify existing)
**Action:** UPDATE

1. Add imports at the top:
```python
from app.core.agents.service import close_agent_service
from app.transit.service import close_transit_service
```

2. In the `lifespan` function, add cleanup calls in the shutdown section (before `engine.dispose()`):
```python
    # Shutdown
    await close_transit_service()
    await close_agent_service()
    await engine.dispose()
```

3. Add structured logging for the new cleanup:
```python
    logger.info("security.singletons_closed")
```

**Per-task validation:**
- `uv run ruff format app/main.py`
- `uv run ruff check --fix app/main.py` passes
- `uv run mypy app/main.py` passes

---

### Task 7: Add Request Size Limits on LLM Schemas
**File:** `app/core/agents/schemas.py` (modify existing)
**Action:** UPDATE

Add Pydantic Field constraints to prevent oversized payloads:

1. Update `ChatMessage.content` field:
```python
content: str = Field(max_length=4000)
```

2. Update `ChatCompletionRequest.messages` field:
```python
messages: list[ChatMessage] = Field(min_length=1, max_length=20)
```

These constraints ensure:
- No single message exceeds ~4KB of text (enough for transit queries, prevents abuse)
- No conversation exceeds 20 messages (prevents context-stuffing attacks)

**Per-task validation:**
- `uv run ruff format app/core/agents/schemas.py`
- `uv run ruff check --fix app/core/agents/schemas.py` passes
- `uv run mypy app/core/agents/schemas.py` passes

---

### Task 8: Add Body Size Limit Middleware
**File:** `app/core/middleware.py` (modify existing)
**Action:** UPDATE

Add a `BodySizeLimitMiddleware` class before the `setup_middleware` function. This rejects requests with bodies larger than 100KB:

```python
class BodySizeLimitMiddleware(BaseHTTPMiddleware):
    """Middleware that rejects request bodies exceeding a size limit.

    Prevents oversized payloads from consuming server memory. Returns
    HTTP 413 (Content Too Large) for requests exceeding the limit.

    Args:
        max_body_size: Maximum allowed body size in bytes.
    """

    def __init__(self, app: FastAPI, max_body_size: int = 102_400) -> None:
        super().__init__(app)
        self._max_body_size = max_body_size

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        """Check Content-Length header and reject oversized requests.

        Args:
            request: The incoming request.
            call_next: The next middleware or route handler.

        Returns:
            Response from the next handler, or 413 if body too large.
        """
        content_length = request.headers.get("content-length")
        if content_length is not None and int(content_length) > self._max_body_size:
            return JSONResponse(
                status_code=413,
                content={"error": "Request body too large", "max_bytes": self._max_body_size},
            )
        return await call_next(request)
```

Add the required import at the top of the file:
```python
from fastapi.responses import JSONResponse
```

Register it in `setup_middleware()` — add BEFORE the request logging middleware:
```python
app.add_middleware(BodySizeLimitMiddleware, max_body_size=102_400)
```

**IMPORTANT:** The `__init__` signature uses `app: FastAPI` as the first positional argument because `BaseHTTPMiddleware.__init__` requires it. However, when registering via `app.add_middleware()`, FastAPI passes the app automatically. The type annotation must match exactly what Starlette expects. Use `app: ASGIApp` from `starlette.types` if `FastAPI` causes type issues, but try `FastAPI` first since that's what the existing `RequestLoggingMiddleware` uses (it inherits from `BaseHTTPMiddleware` without overriding `__init__`).

Actually, `BaseHTTPMiddleware.__init__` takes `app: ASGIApp`. Since we're overriding `__init__`, use:
```python
from starlette.types import ASGIApp

class BodySizeLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: ASGIApp, max_body_size: int = 102_400) -> None:
        super().__init__(app)
        self._max_body_size = max_body_size
```

**Per-task validation:**
- `uv run ruff format app/core/middleware.py`
- `uv run ruff check --fix app/core/middleware.py` passes
- `uv run mypy app/core/middleware.py` passes
- `uv run pyright app/core/middleware.py` passes

---

### Task 9: Create Rate Limiter Module
**File:** `app/core/rate_limit.py` (create new)
**Action:** CREATE

Create the rate limiter configuration module using `slowapi`:

```python
"""Rate limiting configuration using slowapi.

Provides a configured Limiter instance and key extraction function
for per-IP rate limiting across all API endpoints.
"""

from slowapi import Limiter
from slowapi.util import get_remote_address
from starlette.requests import Request

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)


def _get_client_ip(request: Request) -> str:
    """Extract client IP from request for rate limiting.

    Uses X-Forwarded-For header if present (behind reverse proxy),
    falls back to direct client address.

    Args:
        request: The incoming Starlette request.

    Returns:
        Client IP address string.
    """
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return get_remote_address(request)


limiter = Limiter(key_func=_get_client_ip)
```

**IMPORTANT about slowapi types:** slowapi may lack `py.typed`. If mypy or pyright complain about missing type stubs:
- Add `[[tool.mypy.overrides]]` for `slowapi` and `slowapi.util` with `ignore_missing_imports = true` in `pyproject.toml`
- Add `# pyright: reportMissingTypeStubs=false` at the top of this file if needed

**Per-task validation:**
- `uv run ruff format app/core/rate_limit.py`
- `uv run ruff check --fix app/core/rate_limit.py` passes
- `uv run mypy app/core/rate_limit.py` passes
- `uv run pyright app/core/rate_limit.py` passes

---

### Task 10: Register Rate Limiter in Main App
**File:** `app/main.py` (modify existing)
**Action:** UPDATE

1. Add imports:
```python
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.core.rate_limit import limiter
```

2. After `app = FastAPI(...)`, add:
```python
# Setup rate limiting
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
```

**IMPORTANT:** The `_rate_limit_exceeded_handler` is a private import from slowapi but it's the documented way to register the handler. If the import path changes, check slowapi docs. The handler returns HTTP 429 with a "Rate limit exceeded" message.

**IMPORTANT about types:** `_rate_limit_exceeded_handler` may need a type: ignore for the exception handler registration since FastAPI expects a specific signature. Use the same `cast(Any, ...)` pattern from `app/core/exceptions.py` (line 81) if needed:
```python
from typing import Any, cast
app.add_exception_handler(RateLimitExceeded, cast(Any, _rate_limit_exceeded_handler))
```

**Per-task validation:**
- `uv run ruff format app/main.py`
- `uv run ruff check --fix app/main.py` passes
- `uv run mypy app/main.py` passes

---

### Task 11: Add Rate Limits to Agent Routes
**File:** `app/core/agents/routes.py` (modify existing)
**Action:** UPDATE

1. Add import:
```python
from app.core.rate_limit import limiter
```

2. Add rate limit decorator to `chat_completions` endpoint:
```python
@router.post("/chat/completions", response_model=ChatCompletionResponse)
@limiter.limit("10/minute")
async def chat_completions(
    request: Request,
    body: ChatCompletionRequest,
    service: AgentService = Depends(get_agent_service),
) -> ChatCompletionResponse:
```

**CRITICAL:** When using slowapi with FastAPI, the first parameter of the route function MUST be `request: Request` (from `fastapi` or `starlette.requests`). The Pydantic body model must be a separate parameter. Rename the existing `request` parameter to `body` to avoid conflict:
- Change `request: ChatCompletionRequest` to `body: ChatCompletionRequest`
- Add `request: Request` as the first parameter
- Update the function body: `service.chat(body)` instead of `service.chat(request)`

Add the `Request` import from `fastapi`:
```python
from fastapi import APIRouter, Depends, Request
```

3. Add rate limit to `list_models`:
```python
@router.get("/models")
@limiter.limit("60/minute")
async def list_models(request: Request) -> dict[str, Any]:
```

**Per-task validation:**
- `uv run ruff format app/core/agents/routes.py`
- `uv run ruff check --fix app/core/agents/routes.py` passes
- `uv run mypy app/core/agents/routes.py` passes

---

### Task 12: Add Rate Limits to Transit Routes
**File:** `app/transit/routes.py` (modify existing)
**Action:** UPDATE

1. Add imports:
```python
from fastapi import APIRouter, Request

from app.core.rate_limit import limiter
```

2. Add rate limit decorator and `Request` parameter:
```python
@router.get("/vehicles", response_model=VehiclePositionsResponse)
@limiter.limit("30/minute")
async def get_vehicles(
    request: Request,
    route_id: str | None = None,
) -> VehiclePositionsResponse:
```

**Per-task validation:**
- `uv run ruff format app/transit/routes.py`
- `uv run ruff check --fix app/transit/routes.py` passes
- `uv run mypy app/transit/routes.py` passes

---

### Task 13: Add Rate Limits and Caching to Health Routes
**File:** `app/core/health.py` (modify existing)
**Action:** UPDATE

1. Add imports:
```python
import time as time_module

from fastapi import APIRouter, Depends, HTTPException, Request, status

from app.core.rate_limit import limiter
```

2. Add a module-level cached result for DB health:
```python
_db_health_cache: dict[str, str] | None = None
_db_health_cache_time: float = 0.0
_DB_HEALTH_CACHE_TTL: float = 10.0  # seconds
```

3. Add rate limit decorators to all three endpoints:
```python
@router.get("/health")
@limiter.limit("60/minute")
async def health_check(request: Request) -> dict[str, str]:
```

```python
@router.get("/health/db")
@limiter.limit("60/minute")
async def database_health_check(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
```

```python
@router.get("/health/ready")
@limiter.limit("60/minute")
async def readiness_check(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
```

4. Add DB health caching to `database_health_check`:
```python
async def database_health_check(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    global _db_health_cache, _db_health_cache_time
    now = time_module.monotonic()
    if _db_health_cache is not None and (now - _db_health_cache_time) < _DB_HEALTH_CACHE_TTL:
        return _db_health_cache

    try:
        await db.execute(text("SELECT 1"))
        result = {
            "status": "healthy",
            "service": "database",
            "provider": "postgresql",
        }
        _db_health_cache = result
        _db_health_cache_time = now
        return result
    except Exception as exc:
        _db_health_cache = None
        logger.error("database.health_check_failed", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database is not accessible",
        ) from exc
```

**IMPORTANT:** Import `time` as `time_module` to avoid conflict with any local variables named `time`. Or just use `import time` and reference `time.monotonic()` — check what the existing codebase pattern is. Looking at `client.py`, it uses `import time` and `time.monotonic()`. Use the same pattern. If there's a conflict with the `time` import already in the file, adjust accordingly. The health module does NOT currently import `time`, so `import time` is fine.

**Per-task validation:**
- `uv run ruff format app/core/health.py`
- `uv run ruff check --fix app/core/health.py` passes
- `uv run mypy app/core/health.py` passes

---

### Task 14: Create Query Quota Tracker
**File:** `app/core/agents/quota.py` (create new)
**Action:** CREATE

Create an in-memory daily IP-based quota tracker:

```python
"""Daily query quota enforcement for the agent LLM endpoint.

Tracks per-IP query counts with automatic daily reset. Returns HTTP 429
when a client exceeds the configured daily quota.
"""

import time
from dataclasses import dataclass, field

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)

_SECONDS_PER_DAY: int = 86_400


@dataclass
class _QuotaEntry:
    """Tracks query count and reset time for a single IP."""

    count: int = 0
    reset_at: float = field(default_factory=lambda: time.monotonic() + _SECONDS_PER_DAY)


class QueryQuotaTracker:
    """In-memory daily query quota tracker per IP address.

    Automatically resets counts after 24 hours per IP. Thread-safe
    for single-process async usage (no cross-process sharing).
    """

    def __init__(self, daily_limit: int) -> None:
        """Initialize with the maximum queries per IP per day.

        Args:
            daily_limit: Maximum number of queries allowed per IP per day.
        """
        self._daily_limit = daily_limit
        self._entries: dict[str, _QuotaEntry] = {}

    def check_and_increment(self, client_ip: str) -> bool:
        """Check if the client has quota remaining and increment if so.

        Args:
            client_ip: The client's IP address.

        Returns:
            True if the request is allowed, False if quota exceeded.
        """
        now = time.monotonic()
        entry = self._entries.get(client_ip)

        if entry is None or now >= entry.reset_at:
            self._entries[client_ip] = _QuotaEntry(count=1, reset_at=now + _SECONDS_PER_DAY)
            return True

        if entry.count >= self._daily_limit:
            logger.warning(
                "agent.quota_exceeded",
                client_ip=client_ip,
                daily_limit=self._daily_limit,
                current_count=entry.count,
            )
            return False

        entry.count += 1
        return True

    def get_remaining(self, client_ip: str) -> int:
        """Get the number of queries remaining for a client.

        Args:
            client_ip: The client's IP address.

        Returns:
            Number of queries remaining in the current period.
        """
        now = time.monotonic()
        entry = self._entries.get(client_ip)
        if entry is None or now >= entry.reset_at:
            return self._daily_limit
        return max(0, self._daily_limit - entry.count)


# --- Module-level singleton ---

_quota_tracker: QueryQuotaTracker | None = None


def get_quota_tracker() -> QueryQuotaTracker:
    """Get or create the quota tracker singleton.

    Returns:
        Singleton QueryQuotaTracker instance.
    """
    global _quota_tracker
    if _quota_tracker is None:
        settings = get_settings()
        _quota_tracker = QueryQuotaTracker(daily_limit=settings.agent_daily_quota)
    return _quota_tracker
```

**Per-task validation:**
- `uv run ruff format app/core/agents/quota.py`
- `uv run ruff check --fix app/core/agents/quota.py` passes
- `uv run mypy app/core/agents/quota.py` passes
- `uv run pyright app/core/agents/quota.py` passes

---

### Task 15: Integrate Quota Check into Agent Routes
**File:** `app/core/agents/routes.py` (modify existing — second update)
**Action:** UPDATE

1. Add imports:
```python
from fastapi import APIRouter, Depends, HTTPException, Request

from app.core.agents.quota import get_quota_tracker
from app.core.rate_limit import limiter
```

2. Add quota check at the beginning of `chat_completions`:
```python
@router.post("/chat/completions", response_model=ChatCompletionResponse)
@limiter.limit("10/minute")
async def chat_completions(
    request: Request,
    body: ChatCompletionRequest,
    service: AgentService = Depends(get_agent_service),
) -> ChatCompletionResponse:
    # Check daily quota before expensive LLM call
    client_ip = request.client.host if request.client else "unknown"
    tracker = get_quota_tracker()
    if not tracker.check_and_increment(client_ip):
        remaining = tracker.get_remaining(client_ip)
        raise HTTPException(
            status_code=429,
            detail=f"Daily query quota exceeded. Remaining: {remaining}. Resets in 24 hours.",
        )

    return await service.chat(body)
```

**Per-task validation:**
- `uv run ruff format app/core/agents/routes.py`
- `uv run ruff check --fix app/core/agents/routes.py` passes
- `uv run mypy app/core/agents/routes.py` passes

---

### Task 16: Add pyproject.toml Overrides for slowapi Types
**File:** `pyproject.toml` (modify existing)
**Action:** UPDATE

If Task 9 or Task 10 failed type checking due to slowapi missing type stubs, add mypy overrides:

```toml
[[tool.mypy.overrides]]
module = "slowapi.*"
ignore_missing_imports = true
```

Also add the per-file-ignores for the new rate limit module if needed:
```toml
"app/core/rate_limit.py" = ["B008"]  # slowapi Limiter() pattern
```

**IMPORTANT:** Only add these if the type checkers actually fail. Check Task 9 and 10 results first.

**Per-task validation:**
- `uv run mypy app/` passes
- `uv run pyright app/` passes

---

### Task 17: Update Existing Tests for Singleton Changes
**File:** `app/transit/tests/test_routes.py` (modify existing)
**Action:** UPDATE

The transit route tests use `@patch("app.transit.routes.get_transit_service")` to mock the service factory. Since `get_transit_service` is still a callable function (just with singleton behavior now), the mock pattern should still work. However, the route handler now requires a `Request` parameter for rate limiting.

The test uses `AsyncClient(transport=ASGITransport(app=app))` which provides a full ASGI request, so the `Request` parameter will be populated automatically. **No changes should be needed** — but verify by running the tests.

If tests fail due to rate limiting during test execution, add rate limit state reset. The simplest fix: in each test, reset the limiter state:
```python
from app.core.rate_limit import limiter
# At the start of each test or in a fixture:
limiter.reset()
```

Or alternatively, check if slowapi has a test mode or if the `Limiter` can be configured with `enabled=False` in test settings.

**Per-task validation:**
- `uv run pytest app/transit/tests/ -v` — all tests pass

---

### Task 18: Update Agent Route Tests for New Parameter Names
**File:** `app/core/agents/tests/test_routes.py` (modify existing)
**Action:** UPDATE

The agent route tests send JSON to `/v1/chat/completions`. Since we renamed the parameter from `request` to `body` in Task 11, the endpoint still accepts the same JSON body — the parameter rename is internal. Tests should still pass.

However, the `test_chat_completions_endpoint` test uses `TestClient(app)` synchronously. Rate limiting tracks per-IP, and `TestClient` provides `127.0.0.1` as the client IP. If multiple tests run, they may trigger the rate limit.

If tests fail due to rate limiting:
1. Option A: Increase rate limits in test env vars
2. Option B: Add a test fixture that patches the limiter to be disabled
3. Option C: The simplest — add to each test function or a conftest fixture:

```python
from app.core.rate_limit import limiter
limiter.enabled = False  # Disable rate limiting during tests
```

Actually, `slowapi.Limiter` has an `enabled` property. Set it to `False` in test setup.

Add to `app/core/agents/tests/test_routes.py` at the top (after existing imports):
```python
from app.core.rate_limit import limiter
limiter.enabled = False
```

Do the same for `app/transit/tests/test_routes.py`.

**Per-task validation:**
- `uv run pytest app/core/agents/tests/ -v` — all tests pass

---

### Task 19: Write Tests for Quota Tracker
**File:** `app/core/agents/tests/test_quota.py` (create new)
**Action:** CREATE

```python
"""Tests for daily query quota tracker."""

from app.core.agents.quota import QueryQuotaTracker


def test_quota_allows_within_limit():
    tracker = QueryQuotaTracker(daily_limit=3)
    assert tracker.check_and_increment("1.2.3.4") is True
    assert tracker.check_and_increment("1.2.3.4") is True
    assert tracker.check_and_increment("1.2.3.4") is True


def test_quota_rejects_over_limit():
    tracker = QueryQuotaTracker(daily_limit=2)
    assert tracker.check_and_increment("1.2.3.4") is True
    assert tracker.check_and_increment("1.2.3.4") is True
    assert tracker.check_and_increment("1.2.3.4") is False


def test_quota_tracks_per_ip():
    tracker = QueryQuotaTracker(daily_limit=1)
    assert tracker.check_and_increment("1.1.1.1") is True
    assert tracker.check_and_increment("2.2.2.2") is True
    assert tracker.check_and_increment("1.1.1.1") is False
    assert tracker.check_and_increment("2.2.2.2") is False


def test_quota_get_remaining():
    tracker = QueryQuotaTracker(daily_limit=5)
    assert tracker.get_remaining("1.2.3.4") == 5
    tracker.check_and_increment("1.2.3.4")
    assert tracker.get_remaining("1.2.3.4") == 4


def test_quota_get_remaining_at_zero():
    tracker = QueryQuotaTracker(daily_limit=1)
    tracker.check_and_increment("1.2.3.4")
    assert tracker.get_remaining("1.2.3.4") == 0
```

**Per-task validation:**
- `uv run ruff format app/core/agents/tests/test_quota.py`
- `uv run ruff check --fix app/core/agents/tests/test_quota.py` passes
- `uv run pytest app/core/agents/tests/test_quota.py -v` — all tests pass

---

### Task 20: Write Tests for Body Size Limit Middleware
**File:** `app/core/tests/test_middleware.py` (create new or modify existing)
**Action:** CREATE

Check if `app/core/tests/test_middleware.py` exists. If not, create it:

```python
"""Tests for middleware — body size limit."""

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.rate_limit import limiter
from app.main import app

# Disable rate limiting during tests
limiter.enabled = False


@pytest.mark.asyncio
async def test_body_size_limit_allows_normal_request():
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.post(
            "/v1/chat/completions",
            json={"messages": [{"role": "user", "content": "Hello"}]},
        )
    # Should not be rejected by body size (may be 200 or 502 depending on LLM)
    assert response.status_code != 413


@pytest.mark.asyncio
async def test_body_size_limit_rejects_oversized_request():
    huge_content = "x" * 200_000  # ~200KB, exceeds 100KB limit
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.post(
            "/v1/chat/completions",
            json={"messages": [{"role": "user", "content": huge_content}]},
        )
    assert response.status_code == 413
```

**Per-task validation:**
- `uv run ruff format app/core/tests/test_middleware.py`
- `uv run ruff check --fix app/core/tests/test_middleware.py` passes
- `uv run pytest app/core/tests/test_middleware.py -v` — all tests pass

---

### Task 21: Add Security Headers to Next.js
**File:** `cms/apps/web/next.config.ts` (modify existing)
**Action:** UPDATE

Add security headers configuration:

```typescript
import createNextIntlPlugin from "next-intl/plugin";
import type { NextConfig } from "next";

const withNextIntl = createNextIntlPlugin("./src/i18n/request.ts");

const securityHeaders = [
  {
    key: "X-Frame-Options",
    value: "DENY",
  },
  {
    key: "X-Content-Type-Options",
    value: "nosniff",
  },
  {
    key: "Referrer-Policy",
    value: "strict-origin-when-cross-origin",
  },
  {
    key: "X-DNS-Prefetch-Control",
    value: "on",
  },
  {
    key: "Strict-Transport-Security",
    value: "max-age=63072000; includeSubDomains; preload",
  },
  {
    key: "Content-Security-Policy",
    value: [
      "default-src 'self'",
      "script-src 'self' 'unsafe-inline' 'unsafe-eval'",
      "style-src 'self' 'unsafe-inline'",
      "img-src 'self' data: https://*.tile.openstreetmap.org",
      "connect-src 'self' http://localhost:8123 https://*.tile.openstreetmap.org",
      "font-src 'self'",
      "frame-ancestors 'none'",
    ].join("; "),
  },
];

const nextConfig: NextConfig = {
  images: {
    formats: ["image/avif", "image/webp"],
  },
  experimental: {
    optimizePackageImports: ["lucide-react", "radix-ui"],
  },
  async headers() {
    return [
      {
        source: "/(.*)",
        headers: securityHeaders,
      },
    ];
  },
};

export default withNextIntl(nextConfig);
```

**Per-task validation:**
- `cd cms && pnpm --filter @vtv/web type-check` passes
- `cd cms && pnpm --filter @vtv/web lint` passes

---

### Task 22: Fix Hardcoded AUTH_SECRET in Docker Compose
**File:** `docker-compose.yml` (modify existing)
**Action:** UPDATE

1. Change the `cms` service `AUTH_SECRET` from hardcoded value to environment variable reference:
```yaml
    environment:
      - NEXT_PUBLIC_AGENT_URL=http://app:8123
      - AUTH_SECRET=${AUTH_SECRET:?AUTH_SECRET must be set - run: openssl rand -base64 32}
```

This uses the `${VAR:?message}` syntax which causes docker-compose to fail with a helpful error if `AUTH_SECRET` is not set.

**Per-task validation:**
- `docker-compose config` validates successfully (when AUTH_SECRET is set)

---

### Task 23: Add Login Brute-Force Protection
**File:** `cms/apps/web/auth.ts` (modify existing)
**Action:** UPDATE

Add an in-memory failed-attempt tracker with lockout:

```typescript
import NextAuth from "next-auth";
import Credentials from "next-auth/providers/credentials";
import type { DefaultSession } from "next-auth";

// VTV role type - matches PRD Section 7.5
export type VTVRole = "admin" | "dispatcher" | "editor" | "viewer";

declare module "next-auth" {
  interface Session {
    user: { role: VTVRole } & DefaultSession["user"];
  }
  interface User {
    role: VTVRole;
  }
}

// SECURITY: Brute-force protection - in-memory failed attempt tracking
const LOCKOUT_THRESHOLD = 5;
const LOCKOUT_DURATION_MS = 15 * 60 * 1000; // 15 minutes
const failedAttempts = new Map<string, { count: number; lockedUntil: number }>();

function checkBruteForce(email: string): boolean {
  const entry = failedAttempts.get(email);
  if (!entry) return true;
  if (Date.now() > entry.lockedUntil) {
    failedAttempts.delete(email);
    return true;
  }
  return entry.count < LOCKOUT_THRESHOLD;
}

function recordFailedAttempt(email: string): void {
  const entry = failedAttempts.get(email) ?? { count: 0, lockedUntil: 0 };
  entry.count += 1;
  if (entry.count >= LOCKOUT_THRESHOLD) {
    entry.lockedUntil = Date.now() + LOCKOUT_DURATION_MS;
  }
  failedAttempts.set(email, entry);
}

function clearFailedAttempts(email: string): void {
  failedAttempts.delete(email);
}

export const { handlers, auth, signIn, signOut } = NextAuth({
  providers: [
    Credentials({
      credentials: {
        email: { label: "Email", type: "email" },
        password: { label: "Password", type: "password" },
      },
      async authorize(credentials) {
        const email = credentials?.email as string | undefined;
        if (!email) return null;

        // Check brute-force lockout
        if (!checkBruteForce(email)) {
          return null; // Silently reject - don't reveal lockout to attacker
        }

        // SECURITY: Replace hardcoded credentials before non-localhost deployment
        if (email === "admin@vtv.lv" && credentials?.password === "admin") {
          clearFailedAttempts(email);
          return {
            id: "1",
            email: "admin@vtv.lv",
            name: "VTV Admin",
            role: "admin" as VTVRole,
          };
        }

        recordFailedAttempt(email);
        return null;
      },
    }),
  ],
  callbacks: {
    jwt({ token, user }) {
      if (user) {
        (token as Record<string, unknown>).role = user.role;
      }
      return token;
    },
    session({ session, token }) {
      session.user.role = (token as Record<string, unknown>).role as VTVRole;
      return session;
    },
  },
  pages: {
    signIn: "/lv/login",
  },
});
```

**Per-task validation:**
- `cd cms && pnpm --filter @vtv/web type-check` passes
- `cd cms && pnpm --filter @vtv/web lint` passes

---

### Task 24: Docker Security Hardening - Non-Root User
**File:** `Dockerfile` (modify existing)
**Action:** UPDATE

Add a non-root user in the runtime stage. After the `WORKDIR /app` in Stage 2, add:

```dockerfile
# Create non-root user for security
RUN groupadd --gid 1001 vtv && \
    useradd --uid 1001 --gid vtv --shell /bin/bash --create-home vtv

# Copy only the virtual environment from builder
COPY --from=builder --chown=vtv:vtv /app/.venv /app/.venv

# Copy application code
COPY --chown=vtv:vtv . .

# Switch to non-root user
USER vtv
```

Replace the existing `COPY --from=builder` and `COPY . .` lines with the `--chown` versions.

**Per-task validation:**
- `docker build -t vtv-test .` succeeds

---

### Task 25: Docker Compose Resource Limits and Security
**File:** `docker-compose.yml` (modify existing)
**Action:** UPDATE

1. Remove the exposed PostgreSQL port (security risk — only internal services should access DB):
```yaml
  db:
    # Remove the ports: section entirely
    # ports:
    #   - "5433:5432"
```

**WAIT:** The `.env.example` has `DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5433/vtv_db` which uses port 5433 for local development outside Docker. Removing the port mapping would break local development. **Keep the port but add a comment:**
```yaml
    ports:
      # SECURITY: Remove this mapping in production. Only needed for local dev outside Docker.
      - "5433:5432"
```

2. Add resource limits to all services:
```yaml
  app:
    deploy:
      resources:
        limits:
          cpus: "1.0"
          memory: 512M

  db:
    deploy:
      resources:
        limits:
          cpus: "0.5"
          memory: 256M

  cms:
    deploy:
      resources:
        limits:
          cpus: "0.5"
          memory: 512M
```

**Per-task validation:**
- `docker-compose config` validates successfully

---

### Task 26: Create Nginx Reverse Proxy Configuration
**File:** `nginx/nginx.conf` (create new)
**Action:** CREATE

```nginx
worker_processes auto;
error_log /var/log/nginx/error.log warn;
pid /var/run/nginx.pid;

events {
    worker_connections 1024;
}

http {
    # Hide nginx version
    server_tokens off;

    # Rate limiting zones
    limit_req_zone $binary_remote_addr zone=api:10m rate=30r/s;
    limit_req_zone $binary_remote_addr zone=llm:10m rate=2r/s;
    limit_conn_zone $binary_remote_addr zone=addr:10m;

    # Logging
    log_format main '$remote_addr - $remote_user [$time_local] "$request" '
                    '$status $body_bytes_sent "$http_referer" '
                    '"$http_user_agent" "$http_x_forwarded_for"';
    access_log /var/log/nginx/access.log main;

    upstream backend {
        server app:8123;
    }

    upstream frontend {
        server cms:3000;
    }

    server {
        listen 80;
        server_name _;

        # Connection limits
        limit_conn addr 20;

        # Global body size limit
        client_max_body_size 1m;

        # Security headers
        add_header X-Frame-Options "DENY" always;
        add_header X-Content-Type-Options "nosniff" always;
        add_header X-XSS-Protection "1; mode=block" always;
        add_header Referrer-Policy "strict-origin-when-cross-origin" always;

        # LLM endpoint - strict rate limit
        location /v1/chat/completions {
            limit_req zone=llm burst=5 nodelay;
            client_max_body_size 100k;

            proxy_pass http://backend;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;

            # Timeout for LLM responses (can be slow)
            proxy_read_timeout 60s;
        }

        # Backend API
        location /api/ {
            limit_req zone=api burst=20 nodelay;

            proxy_pass http://backend;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
        }

        # Health checks (backend)
        location /health {
            limit_req zone=api burst=10 nodelay;

            proxy_pass http://backend;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        }

        # Agent models endpoint
        location /v1/models {
            limit_req zone=api burst=10 nodelay;

            proxy_pass http://backend;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        }

        # Backend root and docs
        location /docs {
            proxy_pass http://backend;
            proxy_set_header Host $host;
        }

        location /openapi.json {
            proxy_pass http://backend;
            proxy_set_header Host $host;
        }

        # Frontend (catch-all)
        location / {
            limit_req zone=api burst=50 nodelay;

            proxy_pass http://frontend;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;

            # WebSocket support for Next.js HMR
            proxy_http_version 1.1;
            proxy_set_header Upgrade $http_upgrade;
            proxy_set_header Connection "upgrade";
        }
    }
}
```

**Per-task validation:**
- `nginx -t -c $(pwd)/nginx/nginx.conf` validates (if nginx installed locally), or just review

---

### Task 27: Create Nginx Dockerfile
**File:** `nginx/Dockerfile` (create new)
**Action:** CREATE

```dockerfile
FROM nginx:1.27-alpine

# Remove default config
RUN rm /etc/nginx/conf.d/default.conf

# Copy custom config
COPY nginx.conf /etc/nginx/nginx.conf

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
```

**Per-task validation:**
- File exists and is valid Dockerfile syntax

---

### Task 28: Add Nginx Service to Docker Compose
**File:** `docker-compose.yml` (modify existing)
**Action:** UPDATE

Add the nginx service and adjust port mappings so only nginx is exposed:

1. Remove external port mapping from `app` service:
```yaml
  app:
    # Remove: ports: ["8123:8123"]
    # App is only accessible through nginx
    expose:
      - "8123"
```

2. Remove external port mapping from `cms` service:
```yaml
  cms:
    # Remove: ports: ["3000:3000"]
    # CMS is only accessible through nginx
    expose:
      - "3000"
```

3. Add nginx service:
```yaml
  nginx:
    build:
      context: ./nginx
      dockerfile: Dockerfile
    ports:
      - "80:80"
    depends_on:
      - app
      - cms
    restart: unless-stopped
    deploy:
      resources:
        limits:
          cpus: "0.25"
          memory: 128M
```

**IMPORTANT:** For local development without Docker, developers still use `uv run uvicorn` on port 8123 and `pnpm dev` on port 3000 directly. The nginx proxy is only for Docker-based deployment. Update the comment in docker-compose to reflect this.

**Per-task validation:**
- `docker-compose config` validates successfully

---

### Task 29: Run Full Test Suite
**Action:** VALIDATE

Run the complete validation pyramid:

```bash
# Level 1: Syntax & Style
uv run ruff format .
uv run ruff check --fix .

# Level 2: Type Safety
uv run mypy app/
uv run pyright app/

# Level 3: Unit Tests (all)
uv run pytest -v -m "not integration"
```

Fix any failures before proceeding.

**Per-task validation:**
- All commands exit with code 0
- Zero errors, zero warnings
- All existing 198+ tests still pass

---

## Logging Events

- `security.singletons_closed` — When singleton services are closed during shutdown
- `agent.quota_exceeded` — When a client exceeds daily query quota (includes client_ip, daily_limit, current_count)
- `request.body_too_large` — (implicit via 413 response) When body size middleware rejects a request

## Testing Strategy

### Unit Tests
**Location:** `app/core/agents/tests/test_quota.py`
- QueryQuotaTracker — allows within limit, rejects over limit, per-IP isolation, remaining count

**Location:** `app/core/tests/test_middleware.py`
- BodySizeLimitMiddleware — allows normal requests, rejects oversized

### Integration Tests
- Existing tests in `app/transit/tests/` and `app/core/agents/tests/` must continue passing
- Rate limiting disabled in test environment via `limiter.enabled = False`

### Edge Cases
- Rate limit counter reset after time window
- Quota reset after 24 hours
- Body size check with missing Content-Length header (should pass through)
- Singleton services handle concurrent requests correctly (asyncio is single-threaded, so no threading issues)

## Acceptance Criteria

This feature is complete when:
- [ ] TransitService is a singleton — GTFS-RT cache works across requests
- [ ] AgentService is a singleton — httpx client is reused
- [ ] Chat messages limited to 4000 chars, 20 messages max
- [ ] Request bodies over 100KB are rejected with 413
- [ ] All endpoints have per-IP rate limits enforced by slowapi
- [ ] Agent endpoint has daily quota (50 queries/IP/day) returning 429 when exceeded
- [ ] All type checkers pass (mypy + pyright)
- [ ] All tests pass (unit + integration)
- [ ] No regressions in existing 198+ tests
- [ ] Next.js security headers configured (CSP, X-Frame-Options, HSTS, etc.)
- [ ] AUTH_SECRET is environment-variable based in docker-compose
- [ ] Login has brute-force protection (5 attempts, 15-min lockout)
- [ ] Docker runs as non-root user
- [ ] Nginx reverse proxy configured with connection/rate limits

## Completion Checklist

Before marking this plan as fully executed:
- [ ] All tasks completed in order
- [ ] Per-task validations passed
- [ ] Full validation pyramid passed (Levels 1-4)
- [ ] No deviations from plan (or deviations documented with reasons)
- [ ] Ready for `/commit`

## Final Validation (5-Level Pyramid)

Run each level in order — every one must pass with 0 errors:

**Level 1: Syntax & Style**
```bash
uv run ruff format .
uv run ruff check --fix .
```

**Level 2: Type Safety**
```bash
uv run mypy app/
uv run pyright app/
```

**Level 3: Unit Tests (feature-specific)**
```bash
uv run pytest app/core/agents/tests/test_quota.py -v
uv run pytest app/core/tests/test_middleware.py -v
```

**Level 4: Full Test Suite (unit)**
```bash
uv run pytest -v -m "not integration"
```

**Level 5: Frontend Validation**
```bash
cd cms && pnpm --filter @vtv/web type-check
cd cms && pnpm --filter @vtv/web lint
```

**Success definition:** Levels 1-5 exit code 0, all tests pass, zero errors or warnings.

## Dependencies

- Shared utilities used: `app/core/config.get_settings()`, `app/core/logging.get_logger()`
- Core modules used: `app/core/middleware`, `app/core/exceptions`
- New dependencies: `slowapi>=0.1.9` — install via `uv add slowapi`
- New env vars: `RATE_LIMIT_CHAT`, `RATE_LIMIT_TRANSIT`, `RATE_LIMIT_HEALTH`, `RATE_LIMIT_DEFAULT`, `AGENT_DAILY_QUOTA`, `AUTH_SECRET`

## Known Pitfalls

The executing agent MUST follow these rules to avoid common errors:

1. **No `assert` in production code** — Ruff S101 forbids assert outside test files. Use conditional checks instead.
2. **No `object` type hints** — Import and use actual types directly.
3. **Untyped third-party libraries** — slowapi likely lacks `py.typed`. Add mypy `[[tool.mypy.overrides]]` with `ignore_missing_imports = true` for `slowapi.*`. Add pyright file-level `# pyright: reportMissingTypeStubs=false` to `app/core/rate_limit.py` if needed.
4. **No unused imports or variables** — Ruff F401/F841 catch these.
5. **No EN DASH in strings** — Use `-` (HYPHEN-MINUS) only.
6. **slowapi requires `Request` as first route parameter** — When using `@limiter.limit()`, the decorated function MUST have `request: Request` as its first parameter. If the route already has a Pydantic body parameter named `request`, rename it to `body`.
7. **slowapi `_rate_limit_exceeded_handler` is a private import** — It's the documented way but may need `cast(Any, ...)` for type checking.
8. **Global statements need `noqa` comments** — Check if existing `static_cache.py` uses `# noqa` on its `global _static_cache` statements. Match the existing style.
9. **Test isolation with rate limiting** — Set `limiter.enabled = False` in test files to prevent rate limit interference across tests.
10. **Docker Compose `${VAR:?msg}` syntax** — Requires the variable to be set or docker-compose fails. This is intentional for AUTH_SECRET.
11. **Schema field additions break ALL consumers** — Adding `max_length=4000` to `ChatMessage.content` is backward-compatible (just adds validation). But verify existing tests don't send content longer than 4000 chars.

## Notes

- Phase 3 (Prometheus metrics, deployment recommendations, incident playbook) is deferred to a separate plan — it's monitoring/docs only, no security impact
- The slowapi rate limits are in-memory (per-process). If VTV scales to multiple workers, switch to Redis-backed storage
- The query quota tracker is also in-memory. For production multi-worker deployment, use Redis or a database table
- CSP headers allow `unsafe-inline` and `unsafe-eval` for scripts because Next.js requires them for development. Tighten for production by using nonces.
- The nginx config does NOT include SSL/TLS. For production, add Cloudflare (recommended) or Let's Encrypt certbot

## Pre-Implementation Checklist

The executing agent MUST verify before writing any code:
- [ ] Read all files listed in "Relevant Files" section
- [ ] Reviewed the singleton pattern in `static_cache.py` (lines 406-429)
- [ ] Understood slowapi API (Limiter, limit decorator, Request requirement)
- [ ] Clear on task execution order
- [ ] Validation commands are executable in this environment
