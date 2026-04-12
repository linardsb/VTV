# Plan: OPS-5.2 — Architecture Decision Records

## Context

Onboarding requires codebase archaeology. New contributors re-propose LangChain, per-feature `shared/` folders, and reverse-proxy-only rate limits — all already decided and rejected for documented reasons nobody wrote down. Four short ADRs capture the non-obvious architectural choices already in the codebase, using the Nygard template (status / context / decision / consequences).

## Security Context Assessment

No security contexts apply. This task creates documentation files only — no endpoints, no code changes, no infrastructure modifications.

## Research Summary

### Evidence Gathered

| ADR | Key Evidence | Source |
|-----|-------------|--------|
| VSA | 15 feature slices with identical structure; three-feature rule enforced; cross-feature read-only access via repositories | `reference/vsa-patterns.md`, `app/shared/`, `docs/TODO.md` |
| Pydantic AI | `pydantic-ai>=1.58.0` in pyproject.toml; 48 files import pydantic_ai; `Agent[UnifiedDeps, str]` with @agent.tool() decorators; zero LangChain imports | `pyproject.toml:22`, `app/core/agents/agent.py:8-26` |
| Redis cache | Vehicle positions (120s TTL), embedding cache (3600s TTL), rate limit storage, WebSocket pub/sub; `redis[hiredis]>=5.2.0` | `app/core/redis.py:31-56`, `app/transit/poller.py`, `app/knowledge/embedding.py`, `app/core/config.py:93-173` |
| slowapi | `slowapi>=0.1.9`; per-endpoint decorators (10/min chat, 30/min transit); Redis-backed cross-worker enforcement; nginx provides defense-in-depth second layer | `app/core/rate_limit.py`, `nginx/nginx.conf:35-41` |

### Existing State

- `docs/adr/` does **not** exist — must be created
- No prior ADR-like documents anywhere in the repo
- Cross-link targets identified: `CLAUDE.md` line 185 (Operations section), `README.md` line 294 (Key References section)
- No conflicts with uncommitted changes (OPS-2.1 metrics work touches different files)

## Test Landscape

No tests required — documentation-only task. Verification is readability-based (see Verification section).

## Type Check Baseline

Not applicable — no Python files created or modified.

## Files to Create/Modify

| Action | File | Purpose |
|--------|------|---------|
| CREATE | `docs/adr/README.md` | ADR index + Nygard template reference |
| CREATE | `docs/adr/0001-vertical-slice-architecture.md` | VSA over layered/hexagonal architecture |
| CREATE | `docs/adr/0002-pydantic-ai-over-langchain.md` | Pydantic AI over LangChain/LlamaIndex |
| CREATE | `docs/adr/0003-redis-for-cache-layer.md` | Redis for embedding + position + rate-limit cache |
| CREATE | `docs/adr/0004-slowapi-rate-limiting.md` | Application-level rate limiting + nginx defense-in-depth |
| UPDATE | `CLAUDE.md` | Add ADR cross-link in Operations section (after line 185) |
| UPDATE | `README.md` | Add ADR entry in Key References section (after line 294) |

## Implementation Steps

### Step 1: Create `docs/adr/README.md`

Create the ADR index with the Nygard template and links to all 4 ADRs.

Content:
```markdown
# Architecture Decision Records

This directory captures the non-obvious architectural choices in the VTV codebase. Each ADR follows the [Nygard template](https://cognitect.com/blog/2011/11/15/documenting-architecture-decisions):

- **Status** — Accepted, Deprecated, or Superseded by ADR-NNNN
- **Context** — The forces at play, including technical, political, and project-specific constraints
- **Decision** — What we decided and why
- **Consequences** — What becomes easier or harder as a result

## Index

| ADR | Title | Status |
|-----|-------|--------|
| [0001](0001-vertical-slice-architecture.md) | Vertical Slice Architecture | Accepted |
| [0002](0002-pydantic-ai-over-langchain.md) | Pydantic AI over LangChain | Accepted |
| [0003](0003-redis-for-cache-layer.md) | Redis for Cache Layer | Accepted |
| [0004](0004-slowapi-rate-limiting.md) | Application-Level Rate Limiting with slowapi | Accepted |

## Adding a New ADR

1. Copy the template below into `docs/adr/NNNN-short-title.md`
2. Fill in all four sections
3. Add a row to the index table above
4. Update cross-links in `CLAUDE.md` and `README.md` if the decision affects documented architecture

### Template

```
# ADR-NNNN: Title

## Status

Accepted | Deprecated | Superseded by [ADR-NNNN](NNNN-title.md)

## Context

{Problem statement. What forces are at play? What constraints exist?}

## Decision

{What was decided and why. Reference specific alternatives that were considered and rejected.}

## Consequences

{What becomes easier or harder. Both positive and negative outcomes.}
```
```

**Validation:** File exists and renders valid Markdown.

---

### Step 2: Create `docs/adr/0001-vertical-slice-architecture.md`

```markdown
# ADR-0001: Vertical Slice Architecture

## Status

Accepted

## Context

VTV is a transit operations platform with 15+ domain areas (transit, vehicles, drivers, alerts, knowledge, auth, etc.). The codebase needed an organizing principle that:

- Lets a developer work on one domain without understanding (or breaking) others
- Supports AI-assisted development where agents implement entire features from plans
- Keeps shared code minimal to avoid hidden coupling
- Scales to 20+ features without a "shared utilities" dumping ground

Traditional layered architecture (controllers → services → repositories as top-level directories) forces every feature change to touch files across multiple directories, creates merge conflicts between unrelated features, and makes it hard for AI agents to reason about feature boundaries.

## Decision

We use **Vertical Slice Architecture**: each feature lives under `app/{feature}/` with its own `models.py`, `schemas.py`, `repository.py`, `service.py`, `exceptions.py`, `routes.py`, and `tests/` directory. The full pattern is documented in `reference/vsa-patterns.md`.

Three rules govern cross-feature interaction:

1. **Read-only cross-feature access** — A service may import another feature's *repository* (not service) for read queries. All repositories share the same `AsyncSession`, so reads participate in the caller's transaction. Direct writes to another feature's tables are forbidden.

2. **Three-feature rule for shared code** — Inline the first use, duplicate the second (with a `# NOTE: duplicated from {feature}`), extract to `app/shared/` only on the third use. This prevents premature abstraction.

3. **Core infrastructure in `app/core/`** — Database, Redis, config, logging, middleware, auth, and rate limiting live in `app/core/`. These are framework concerns, not business logic.

## Consequences

**Easier:**
- Feature scaffolding is mechanical (`/be-create-feature` generates the entire skeleton)
- AI agents can implement a feature by reading one directory and its plan
- Deleting a feature is a single directory removal + one line in `app/main.py`
- Test isolation: feature tests depend only on their own fixtures + shared test utilities

**Harder:**
- Cross-feature queries require importing another feature's repository, which can feel indirect
- The three-feature rule means some code is intentionally duplicated before extraction
- New contributors sometimes propose per-feature `shared/` subdirectories — this ADR is the answer to why we don't
```

**Validation:** Self-contained — a new contributor reads this without reading code and understands the decision.

---

### Step 3: Create `docs/adr/0002-pydantic-ai-over-langchain.md`

```markdown
# ADR-0002: Pydantic AI over LangChain

## Status

Accepted

## Context

VTV's AI agent needs to orchestrate 11 tools (transit queries, Obsidian vault operations, knowledge base search, skills management) with:

- Strict type safety (mypy + pyright in strict mode)
- Structured dependency injection (database sessions, Redis clients, API keys)
- Multi-model routing (fast models for simple queries, capable models for complex reasoning)
- Minimal abstraction overhead — tool functions should be plain async Python, not framework-specific classes

We evaluated three frameworks: LangChain, LlamaIndex, and Pydantic AI.

**LangChain** was rejected because:
- Heavy abstraction layer: tools must be `BaseTool` subclasses with `_run()` / `_arun()` methods
- Callback-based architecture adds complexity without benefit for our use case
- Type inference is weak — `Any` proliferates through the chain, breaking strict mypy
- Large dependency tree pulls in packages we don't need

**LlamaIndex** was rejected because:
- Optimized for RAG pipelines, not general-purpose tool orchestration
- Agent abstractions are less mature than its retrieval primitives
- Would require maintaining two frameworks (LlamaIndex for RAG + something else for non-RAG tools)

## Decision

We use **Pydantic AI** (`pydantic-ai>=1.58.0`) as the agent framework. The agent is defined as `Agent[UnifiedDeps, str]` in `app/core/agents/agent.py`, where:

- `UnifiedDeps` is a typed dataclass carrying all dependencies (db session, Redis, settings, API clients)
- Tools are plain `async def` functions decorated with `@agent.tool()` — no base classes, no callbacks
- Structured output uses Pydantic models or `TypedDict` for type-safe responses
- Multi-model routing is built-in via `Agent(model=...)` with tier-based selection

## Consequences

**Easier:**
- Tool functions are plain Python — test with standard pytest, no framework mocking needed
- Full type inference: `Agent[DepsType, ReturnType]` generics propagate through the entire call chain
- Dependency injection is explicit: `ctx.deps.settings`, `ctx.deps.db` — no global state
- Adding a new tool is one function + one import in `agent.py`

**Harder:**
- Pydantic AI has a smaller ecosystem than LangChain (fewer pre-built integrations)
- Contributors familiar with LangChain need to learn a different (simpler) API
- Some advanced patterns (multi-agent handoff, streaming tool calls) require manual implementation
```

**Validation:** A new contributor reads ADR-0002 cold and understands why Pydantic AI won.

---

### Step 4: Create `docs/adr/0003-redis-for-cache-layer.md`

```markdown
# ADR-0003: Redis for Cache Layer

## Status

Accepted

## Context

VTV has three caching needs with different characteristics:

1. **Vehicle position cache** — GTFS-RT feeds polled every 10-30s produce ~200 vehicle positions per feed. These must be readable with sub-ms latency for WebSocket push to connected clients. TTL: 120s.

2. **Embedding cache** — OpenAI embedding API calls cost money and add latency (~200ms per call). The same document chunks are re-embedded during search, rechunking, and eval runs. TTL: 3600s.

3. **Rate limit counters** — slowapi needs a shared counter store that works across multiple Gunicorn workers. Must survive worker restarts.

Alternatives considered:

- **In-process dict** — Fast but not shared across workers. Rate limits would be per-worker (4x the intended limit with 4 workers). Vehicle positions would need to be polled by every worker independently.
- **PostgreSQL** — Adds unnecessary write load for ephemeral data. Position cache writes every 10s would compete with business transactions.
- **Memcached** — Viable but lacks pub/sub for WebSocket fan-out. Would need a second system for real-time push.

## Decision

We use **Redis** (`redis[hiredis]>=5.2.0`) as a unified cache layer, configured in `app/core/redis.py` as an async singleton. Three subsystems share the same Redis instance:

- **Vehicle positions** (`app/transit/poller.py`) — `FeedPoller` writes enriched positions with 120s TTL. `redis_reader.py` reads them. `ws_subscriber.py` uses Redis Pub/Sub for WebSocket fan-out.
- **Embedding cache** (`app/knowledge/embedding.py`) — `CachedEmbeddingProvider` wraps the base provider, caching vectors by content hash with 3600s TTL. Configurable via `embedding_cache_enabled` and `embedding_cache_ttl` in settings.
- **Rate limit storage** (`app/core/rate_limit.py`) — slowapi stores counters in Redis for cross-worker enforcement. Falls back to in-memory storage if Redis is unavailable (unit test mode).

## Consequences

**Easier:**
- Single infrastructure dependency for all caching needs — one connection pool, one health check
- WebSocket fan-out via Pub/Sub without polling or additional message brokers
- Embedding cache reduces API costs proportionally to cache hit rate
- Rate limits enforce correctly across all Gunicorn workers

**Harder:**
- Redis becomes a critical dependency — if it goes down, rate limits fall back to per-worker and vehicle positions stop updating
- Connection pool tuning required under high WebSocket connection counts
- Cache invalidation logic spread across three subsystems (each manages its own TTLs)
```

**Validation:** Self-contained explanation of why Redis, what it caches, and what breaks without it.

---

### Step 5: Create `docs/adr/0004-slowapi-rate-limiting.md`

```markdown
# ADR-0004: Application-Level Rate Limiting with slowapi

## Status

Accepted

## Context

VTV exposes API endpoints with vastly different cost profiles:

| Endpoint | Cost | Target Rate |
|----------|------|-------------|
| `/api/v1/chat/completions` | LLM inference (~$0.01/call, 2-10s latency) | 10/minute |
| `/api/v1/transit/vehicles` | Redis read (~0.1ms) | 30/minute |
| `/api/v1/health` | In-memory check (~0.01ms) | 60/minute |
| Default CRUD endpoints | DB query (~5ms) | 120/minute |

Rate limiting at the **reverse proxy only** (nginx) was rejected because:

- nginx `limit_req` operates on URL patterns, not semantic endpoints. A single `location /api/` block can't distinguish between a $0.01 LLM call and a free health check.
- nginx rate limiting is per-worker (each nginx worker has its own counter zone), though shared memory zones mitigate this.
- Changing rate limits requires nginx config reload, not application config change.

Rate limiting at the **application only** was also rejected — nginx provides a coarse defense-in-depth layer against volumetric abuse that shouldn't reach the Python process at all.

## Decision

We use a **two-layer approach**:

**Layer 1 — slowapi (application-level):** `slowapi>=0.1.9` with Redis-backed storage for cross-worker enforcement. Rate limits are per-endpoint decorators (`@limiter.limit("10/minute")`) configured in `app/core/rate_limit.py`. IP extraction uses `X-Real-IP` header (not `X-Forwarded-For`, which is client-spoofable). Falls back to in-memory storage when Redis is unavailable.

**Layer 2 — nginx (reverse proxy):** Coarse rate limiting zones in `nginx/nginx.conf` — 30 req/s general API, 2 req/s LLM endpoint, 60 req/s health. This catches volumetric abuse before it reaches Python.

Rate limit values are configurable via `app/core/config.py` settings (`rate_limit_chat`, `rate_limit_transit`, `rate_limit_health`, `rate_limit_default`).

## Consequences

**Easier:**
- Per-endpoint semantic rate limits: the LLM endpoint has 10/min while health has 60/min
- Rate limit changes deploy with the application, no nginx reload needed
- Cross-worker enforcement via Redis — 4 Gunicorn workers share one counter
- Defense-in-depth: volumetric attacks are stopped at nginx before reaching Python

**Harder:**
- Two rate limit configurations to maintain (slowapi + nginx)
- Must keep nginx limits looser than slowapi limits to avoid false positives at the proxy layer
- `Request` parameter required on every rate-limited route function (ruff ARG001 exception configured)
```

**Validation:** Explains both layers and why neither alone suffices.

---

### Step 6: Update `CLAUDE.md` — Add ADR cross-link

Add after line 185 (after the Prometheus metrics bullet in the Operations section):

```markdown
- **Architecture decisions:** `docs/adr/README.md` — 4 ADRs documenting non-obvious choices (VSA, Pydantic AI, Redis cache, slowapi rate limiting). Nygard template: status, context, decision, consequences.
```

**Validation:** `grep -n "Architecture decisions" CLAUDE.md` returns the new line.

---

### Step 7: Update `README.md` — Add ADR entry in Key References

Add after line 294 (after the Commands reference, before `## License`):

```markdown
- [Architecture Decision Records](docs/adr/README.md) — Why VSA, Pydantic AI, Redis, and slowapi
```

**Validation:** `grep -n "Architecture Decision Records" README.md` returns the new line.

---

## Preflight Warnings

None — no existing code or tests are modified. All files are new or have simple line insertions.

## Security Checklist

Not applicable — no endpoints, no code, no infrastructure changes. Documentation only.

## Verification

- [ ] `docs/adr/README.md` exists with index table linking all 4 ADRs
- [ ] Each ADR has all 4 Nygard sections: Status, Context, Decision, Consequences
- [ ] Each ADR is self-contained: readable without prior codebase knowledge
- [ ] ADR-0002 explains why LangChain was rejected (not just why Pydantic AI was chosen)
- [ ] ADR-0004 explains the two-layer approach (not just slowapi)
- [ ] `CLAUDE.md` has cross-link to `docs/adr/README.md`
- [ ] `README.md` has cross-link to `docs/adr/README.md`
- [ ] All relative links between ADR files resolve correctly
- [ ] `make lint` passes (no markdown issues in Python tooling)
