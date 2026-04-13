# Plan: OPS-5.4 Logging Taxonomy Audit + Backfill

## Context

AI-8.1 added 7 `agent.circuit_breaker.*` events, background pollers emit dozens of structured events, and the agent tool layer has grown significantly --- but `docs/logging-standard.md` only documents generic placeholders for many domains. Dashboard builders in GlitchTip hit "what is this event?" dead ends. This task audits every structured log event in `app/`, compares against the taxonomy doc, backfills missing entries, and adds a CI-runnable audit script.

## Security Context Assessment

- **CTX-INPUT**: N/A (no new endpoints)
- **CTX-RBAC**: N/A (no new endpoints)
- **CTX-AUTH**: N/A
- **CTX-FILE**: N/A
- **CTX-AGENT**: N/A (read-only audit)
- **CTX-INFRA**: N/A (no Docker/nginx changes)

**No security contexts active.** This is a docs + tooling task with no production code changes.

## Research Summary

### Current Taxonomy Doc Structure (`docs/logging-standard.md`, 583 lines)

| Section | Lines | Content |
|---------|-------|---------|
| Format Specification | 1-28 | `{domain}.{component}.{action}_{state}` pattern |
| Application Domain | 31-55 | lifecycle, config (6 events) |
| Request Domain | 57-91 | HTTP lifecycle (8 events) |
| Database Domain | 93-130 | connections, queries, transactions, migrations (15 events) |
| Health Domain | 132-157 | health/readiness/liveness (6 events) |
| Agent Domain | 159-216 | tool, llm, memory, self_correction, circuit_breaker (43 events) |
| External Domain | 240-269 | API calls, webhooks (7 events) |
| Feature Domains (examples) | 271-300 | user, product, order --- generic examples |
| Standard States | 302-319 | State suffix table |
| Required Log Attributes | 330-371 | Context field requirements |
| Usage Examples | 372-449 | Code patterns |
| Query Patterns | 450-485 | grep/jq examples |
| Migration Notes | 487-508 | Old vs new pattern |
| Do's/Don'ts | 509-528 | Best practices |
| Type Annotations | 530-545 | Type hints |
| Testing | 547-570 | Test pattern |
| References | 572-583 | Links |

### Logging Module (`app/core/logging.py`)

- `get_logger(name)` returns structlog bound logger (line 191)
- Processors: `add_request_id` -> `merge_contextvars` -> `add_log_level` -> `TimeStamper(iso)` -> `StackInfoRenderer` -> `format_exc_info` -> `redact_sensitive` -> `JSONRenderer`
- Event naming: `logger.info("domain.component.action_state", field=value)`

### Key Gap: Documented But Not In Code

The Agent Domain (lines 159-216) documents many events that are aspirational/templated rather than implemented:
- `agent.planning.*` (4 events) --- not used in code
- `agent.tool.*` (13 events) --- not used in code (tools use Pydantic AI's built-in tracing)
- `agent.llm.*` (8 events) --- not used in code (Pydantic AI handles LLM calls)
- `agent.memory.storage_*` (6 events) --- actual code uses different names
- `agent.self_correction.*` (5 events) --- actual code uses `agent.correction.*`

### Key Gap: In Code But Not Documented

**Agent subsystem (~30 undocumented events):**
- `agent.injection.detected/blocked` (base.py:202-216) --- prompt injection detection
- `agent.output_validation.detected/blocked/validator_error` (base.py:291-319) --- output safety
- `agent.provider_chain.preempted/fallback/exhausted` (llm.py:164-180) --- LLM resilience
- `agent.correction.triggered/resolved/exhausted/failed` (correction.py:192-267) --- actual correction events
- `agent.router.decision` (router.py:204) --- multi-agent routing
- `agent.rag_routing` (service.py:122) --- RAG vs direct decision
- `agent.memory.recall_injected/recall_failed` (service.py:213-220) --- memory injection
- `agent.pipeline.summary` (service.py:338) --- tier phase tracking
- `agent.skill_loader.*` (skill_loader.py:115-312) --- 8 events for skill loading
- `agent.config.*` (config.py:75-163) --- 4 API key missing warnings
- `agent.provider_health.record_failed` (provider_health.py:269-281)
- `agent.registry.close_failed` (registry.py:77)
- `agent.quota_exceeded_http` (routes.py:65)
- `agent.create_completed` (agent.py:126)
- `agent.chat.confidence_reroute/confidence_reroute_failed` (base.py:358-376)
- `agent.knowledge.search_skipped` (search_knowledge.py:104)
- `agent.skills.manage_started/list_completed` (manage_skills.py:57-95)
- `agent.validation.*` (validation.py:228, service.py:245) --- 2 events

**Transit/poller subsystem (~36 undocumented events):**
- `transit.poller.*` --- 13 events (poller.py:286-452): started, all_started, all_stopped, leader_elected, leader_refresh_*, not_leader, disabled, feed_registered, etc.
- `transit.weather.*` --- 10 events (weather_etl.py:230-342): lifecycle, cycle, leader, backfill, phenomena
- `transit.traffic.*` --- 10 events (traffic_etl.py:361-488): lifecycle, cycle, leader, backfill
- `transit.ws.*` --- 4 events (ws_subscriber.py:32-91): connected, auth_failed, subscriber_started/stopped
- `transit.api.vehicles_requested` (routes.py)

**Shutdown domain (~6 undocumented events):**
- `shutdown.coordinator.no_tasks/started/completed` (shutdown.py:55-119)
- `shutdown.task.registered/drained/timeout/failed` (shutdown.py)

**Jobs domain (~5 undocumented events):**
- `jobs.worker.started/stopped/compaction_failed/promotion_failed` (worker.py:42-75)
- `jobs.queue.lifecycle_started/pool_initialized/pool_closed` (queue.py)

**Memory domain (~7 undocumented events):**
- `memory.lifecycle.promotion_completed/tasks_stopped/disabled/deferred_to_queue` (lifecycle.py:64-110)
- `memory.service.delete_decayed/llm_merge` (service.py)
- `memory.bridge.storage_failed` (bridge.py:95)

**Feature domains (partially documented via generic examples):**
- `alerts.evaluator.lifecycle_*` --- 3+ events
- `geofences.evaluator.lifecycle_*` --- 3+ events
- `knowledge.*` --- 20+ events (extraction, embedding, reranker, autotag, eval)
- Standard CRUD event families for vehicles, drivers, stops, events, skills, schedules

**Application startup (in main.py):**
- `application.lifecycle_started/lifecycle_stopped`
- `database.connection_initialized`
- Various service startup events

### Script Conventions (from `scripts/`)

- `argparse` for CLI (all scripts use it)
- `_parse_args() -> argparse.Namespace` + `async def main(args) -> int` + `sys.exit(asyncio.run(main(parsed)))`
- Output prefix pattern: `[rechunk]`, `[backfill]`
- Exit code: 0 = success, 1 = failure
- `sys.path.insert(0, ...)` for `app.*` imports
- Docstring with Usage examples at top of file

### Existing Convention Test Patterns (`app/tests/test_ops_conventions.py`)

- `PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent`
- Class-based organization: `TestPrometheusAlertRules`, `TestSLODefinitions`, `TestRunbooks`
- `yaml.safe_load()` for YAML validation
- `@pytest.mark.parametrize` for multi-file checks
- String-in-file assertions for markdown sections
- File existence via `Path.exists()`

## Test Landscape

- **Convention tests:** `app/tests/test_ops_conventions.py` (153 lines, 24 tests) --- model for new taxonomy tests
- **Logging tests:** `app/core/tests/test_logging.py` (347 lines, 25 tests) --- `capsys` + JSON parse + `structlog.testing.capture_logs()`
- **Circuit breaker tests:** `app/core/agents/tests/test_circuit_breaker.py` (437 lines) --- uses `capture_logs()` to verify event names
- **Security convention tests:** `app/tests/test_security.py` (600+ lines, 110 tests) --- source code inspection patterns

## Type Check Baseline

| Target | Pyright | Mypy |
|--------|---------|------|
| `scripts/` | 170 errors (pre-existing, other files) | 21 errors in 5 files (pre-existing) |
| `app/core/logging.py` | 0 errors | 0 errors |

New script must not add to these counts.

## Files to Create/Modify

| Action | File | Purpose |
|--------|------|---------|
| CREATE | `scripts/audit_log_taxonomy.py` | CLI script: grep code for log events, compare against taxonomy doc, report deltas |
| UPDATE | `docs/logging-standard.md` | Backfill all missing events with fields + severity + example |
| UPDATE | `app/tests/test_ops_conventions.py` | Add `TestLoggingTaxonomy` class for CI gate |
| UPDATE | `Makefile` | Add `audit-log-taxonomy` target |

## Implementation Steps

### Step 1: Create `scripts/audit_log_taxonomy.py`

**Action:** CREATE

The script must:
1. Parse `docs/logging-standard.md` to extract all documented event names from the tree-style taxonomy blocks (lines between ``` fences that use `-- #` comment format)
2. Grep `app/` recursively for `logger\.(info|warning|error|debug)\(` calls, extract quoted event names matching `\w+\.\w+[\.\w]*` pattern
3. Compare the two sets:
   - **Undocumented:** events in code but not in taxonomy doc
   - **Stale:** events in taxonomy doc but not in code (informational, not blocking)
4. Print a structured report with counts and event lists
5. Exit 0 if no undocumented events, exit 1 otherwise
6. Support `--verbose` flag for showing file:line of each event
7. Support `--ignore` flag for intentionally undocumented events (e.g., feature-CRUD events that follow a standard pattern)

**Key implementation details:**
- Use `re` for parsing, not AST (events are string literals, not computed)
- Parse taxonomy doc tree blocks: lines matching `^[|+- ]*(\w[\w.]+)\s+#` inside code fences
- Parse code: `re.findall(r'logger\.\w+\("([^"]+)"', line)` across all `.py` files in `app/`
- Exclude `tests/` directories (test code may log synthetic events)
- Follow script convention: argparse, docstring, `_parse_args()`, `main()`, `sys.exit()`
- No async needed (pure file I/O)

**Validation:** `uv run python scripts/audit_log_taxonomy.py --verbose` runs without error

### Step 2: Backfill `docs/logging-standard.md` --- Agent Domain

**Action:** UPDATE (lines 159-238)

Replace the current Agent Domain section with an expanded version that:
1. **Keeps** circuit_breaker events (already accurate, lines 208-215)
2. **Removes** aspirational events not in code: `agent.planning.*`, most of `agent.tool.*`, `agent.llm.*`, `agent.memory.storage_*`
3. **Adds** actual events from code:

```
agent.
-- lifecycle --
+-- create_completed              # Agent instance created (fields: agent_id, model)
+-- chat_started                  # Chat pipeline begun (fields: run_id, provider)
+-- chat_failed                   # Chat pipeline error (fields: run_id, error, error_type)
-- security --
+-- injection.detected            # Prompt injection pattern found (fields: pattern, input_hash)
+-- injection.blocked             # Input blocked by injection filter (fields: pattern)
+-- output_validation.detected    # Output safety violation found (fields: violation_type)
+-- output_validation.blocked     # Output blocked by safety filter (fields: violation_type)
+-- output_validation.validator_error  # Validator itself errored (fields: error)
+-- quota_exceeded_http           # Daily query quota exceeded (fields: client_ip)
-- correction --
+-- correction.triggered          # Self-correction loop started (fields: run_id, reason)
+-- correction.resolved           # Correction succeeded (fields: run_id, attempt)
+-- correction.exhausted          # Max correction attempts reached (fields: run_id, attempts)
+-- correction.failed             # Correction loop errored (fields: run_id, error)
-- routing --
+-- router.decision               # Multi-agent routing decision (fields: prompt_hash, chosen_agent)
+-- rag_routing                   # RAG vs direct decision (fields: decision, score)
+-- chat.confidence_reroute       # Confidence-based reroute (fields: from_agent, to_agent)
+-- chat.confidence_reroute_failed # Reroute failed (fields: error)
-- provider resilience --
+-- provider_chain.preempted      # Provider preempted by health check (fields: provider)
+-- provider_chain.fallback       # Falling back to next provider (fields: from_provider, to_provider)
+-- provider_chain.exhausted      # All providers failed (fields: providers_tried)
+-- provider_health.record_failed # Health recording error (fields: provider, error)
-- memory --
+-- memory.recall_injected        # Memories injected into context (fields: count, types)
+-- memory.recall_failed          # Memory recall error (fields: error)
-- skills --
+-- skills_load_failed            # Skills loading error (fields: error)
+-- l3_skills_load_failed         # L3 skills loading error (fields: error)
+-- skills.manage_started         # Skill management tool invoked (fields: action)
+-- skills.list_completed         # Skill listing completed (fields: count)
+-- skill_loader.*                # 8 events: read_failed, missing_front_matter, unterminated_front_matter, path_escaped, discover_failed, resolve_failed
-- knowledge --
+-- knowledge.search_skipped      # Knowledge search skipped (fields: reason)
-- config --
+-- config.anthropic_api_key_missing  # Anthropic key not set (fields: tier)
+-- config.google_api_key_missing     # Google key not set (fields: tier)
+-- config.groq_api_key_missing       # Groq key not set (fields: tier)
+-- config.tier_api_key_missing       # Tier-specific key not set (fields: tier, provider)
-- validation --
+-- validation.extract_tool_returns_failed  # Tool return extraction error (fields: error)
+-- validation.static_cache_unavailable     # Static validation cache miss (fields: reason)
-- infrastructure --
+-- registry.close_failed         # Agent registry cleanup error (fields: error)
+-- pipeline.summary              # End-of-pipeline summary (fields: phases, duration_ms)
-- circuit_breaker (existing, keep as-is) --
```

**Note:** Keep the existing circuit_breaker tree (lines 208-215) and examples (lines 218-238) intact. Insert the new events BEFORE it in the agent domain block.

**Validation:** `uv run python scripts/audit_log_taxonomy.py` reports fewer missing events

### Step 3: Backfill `docs/logging-standard.md` --- New Domains

**Action:** UPDATE (insert new sections after Agent Domain, before External Domain at line 240)

Add these new domain sections:

#### Transit Domain
```
transit.
-- poller --
+-- poller.started                # Single feed poll cycle (fields: feed_id, url)
+-- poller.all_started            # All pollers launched (fields: feed_count)
+-- poller.all_stopped            # All pollers stopped
+-- poller.leader_elected         # Redis leader lock acquired (fields: worker_id, ttl)
+-- poller.leader_refresh_completed  # Leader lock refreshed
+-- poller.leader_refresh_failed  # Leader lock refresh error (fields: error)
+-- poller.not_leader             # Worker is not leader, skipping
+-- poller.disabled               # Polling disabled by config
+-- poller.feed_registered        # Feed registered for polling (fields: feed_id)
-- weather ETL --
+-- weather.lifecycle_started/stopped
+-- weather.cycle_completed/failed
+-- weather.leader_elected/not_leader
+-- weather.backfill_started/completed/failed
+-- weather.phenomena_fetch_failed
-- traffic ETL --
+-- traffic.lifecycle_started/stopped
+-- traffic.cycle_completed/failed
+-- traffic.leader_elected/not_leader
+-- traffic.backfill_started/completed/failed
-- websocket --
+-- ws.connected                  # Client connected (fields: client_id)
+-- ws.auth_failed                # WS auth rejected (fields: reason)
+-- ws.subscriber_started         # Pub/Sub subscriber started
+-- ws.subscriber_stopped         # Pub/Sub subscriber stopped
-- api --
+-- api.vehicles_requested        # Vehicle positions API call (fields: feed_id)
```

#### Shutdown Domain
```
shutdown.
+-- coordinator.no_tasks          # No tasks registered for shutdown
+-- coordinator.started           # Graceful shutdown initiated (fields: task_count)
+-- coordinator.completed         # All tasks drained (fields: duration_ms)
+-- task.registered               # Task registered for shutdown (fields: name, timeout_s)
+-- task.drained                  # Task drained successfully (fields: name, duration_ms)
+-- task.timeout                  # Task drain timed out (fields: name, timeout_s)
+-- task.failed                   # Task drain error (fields: name, error)
```

#### Jobs Domain
```
jobs.
+-- worker.started                # Arq worker started
+-- worker.stopped                # Arq worker stopped
+-- worker.compaction_failed      # Memory compaction job failed (fields: error)
+-- worker.promotion_failed       # Memory promotion job failed (fields: error)
+-- queue.lifecycle_started       # Queue system initialized
+-- queue.pool_initialized        # Redis pool created (fields: pool_size)
+-- queue.pool_closed             # Redis pool closed
```

#### Memory Domain
```
memory.
-- lifecycle --
+-- lifecycle.promotion_completed     # Episodic-to-procedural promotion done (fields: promoted_count)
+-- lifecycle.tasks_stopped           # Background tasks stopped
+-- lifecycle.disabled                # Memory system disabled by config
+-- lifecycle.deferred_to_queue       # Task deferred to durable queue (fields: task)
-- service --
+-- service.delete_decayed            # Decayed memories cleaned (fields: count)
+-- service.llm_merge                 # LLM-based intent merge (fields: merged_count)
-- bridge --
+-- bridge.storage_failed             # Fire-and-forget storage error (fields: error)
```

#### Evaluator Events (add under Feature Domains)
```
alerts.evaluator.lifecycle_started/stopped/cycle_completed
geofences.evaluator.lifecycle_started/stopped/cycle_completed
```

**Validation:** `uv run python scripts/audit_log_taxonomy.py` reports 0 undocumented events (or near-zero with intentional exclusions)

### Step 4: Update `docs/logging-standard.md` metadata

**Action:** UPDATE (line 581-582)

Update the "Last Updated" date and version:
```
**Last Updated:** 2026-04-13
**Version:** 2.0.0
```

**Validation:** File ends with updated metadata

### Step 5: Add convention test `TestLoggingTaxonomy`

**Action:** UPDATE `app/tests/test_ops_conventions.py`

Add a new test class at the end of the file:

```python
LOGGING_STANDARD_FILE = PROJECT_ROOT / "docs" / "logging-standard.md"
AUDIT_SCRIPT = PROJECT_ROOT / "scripts" / "audit_log_taxonomy.py"


class TestLoggingTaxonomy:
    """Validate logging taxonomy completeness (OPS-5.4)."""

    def test_logging_standard_exists(self) -> None:
        assert LOGGING_STANDARD_FILE.exists()

    def test_audit_script_exists(self) -> None:
        assert AUDIT_SCRIPT.exists()

    def test_no_undocumented_log_events(self) -> None:
        """Run audit script and assert zero undocumented events."""
        import subprocess
        result = subprocess.run(
            ["uv", "run", "python", str(AUDIT_SCRIPT)],
            capture_output=True, text=True, cwd=str(PROJECT_ROOT),
            timeout=30,
        )
        assert result.returncode == 0, (
            f"Logging taxonomy audit found undocumented events:\n{result.stdout}\n{result.stderr}"
        )
```

**Validation:** `uv run pytest app/tests/test_ops_conventions.py::TestLoggingTaxonomy -v`

### Step 6: Add Makefile target

**Action:** UPDATE `Makefile`

Add under the Ops section (near `validate-alerts`):

```makefile
audit-log-taxonomy: ## Audit structured log events against docs/logging-standard.md
	uv run python scripts/audit_log_taxonomy.py
```

**Validation:** `make audit-log-taxonomy` runs and exits 0

## Preflight Warnings

- The taxonomy doc tree-block format uses `├──` and `└──` Unicode box-drawing characters. The audit script parser must handle these.
- Some events in code use abbreviated patterns (e.g., `agent.rag_routing` without a state suffix). The script should still detect these.
- Feature CRUD events (vehicles, drivers, stops, etc.) are numerous and follow a standard pattern. Consider an `--ignore-crud` flag or a patterns allowlist to avoid bloating the taxonomy doc with every CRUD event.
- The `agent.evals.loader.*` events (6+) are internal dev/test tooling --- consider excluding from the taxonomy or adding a "Development/Debug" section.

## Security Checklist

N/A --- no new endpoints, no user input handling, no auth changes.

## Verification

- [ ] `uv run python scripts/audit_log_taxonomy.py` exits 0 with 0 undocumented events
- [ ] `uv run python scripts/audit_log_taxonomy.py --verbose` shows all events with file:line
- [ ] `uv run pytest app/tests/test_ops_conventions.py -v` passes (including new `TestLoggingTaxonomy`)
- [ ] `make audit-log-taxonomy` works
- [ ] `make check` passes (lint + types + tests)
- [ ] Pyright errors in `scripts/` <= 170 (baseline)
- [ ] Mypy errors in `scripts/` <= 21 (baseline)
- [ ] `docs/logging-standard.md` version updated to 2.0.0
- [ ] Every event emitted by code in `app/` is documented with fields + severity
