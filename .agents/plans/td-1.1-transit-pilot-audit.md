# Plan: Tech-Debt Pilot Audit on `app/transit/`

## Feature Metadata
**Feature Type**: Diagnostic / Analysis (produces a markdown deliverable; no production code changes)
**Estimated Complexity**: Medium
**Primary Systems Affected**: `app/transit/` (read-only); `TECH_DEBT_AUDIT.md` (created at repo root)

## Feature Description

This plan executes Stage 1.1 of `docs/PLANNING/Tech-Debt-Audit-Plan.md` — the pilot run of
the tech-debt audit protocol scoped to `app/transit/`. The output is a single markdown file
at the repo root (`TECH_DEBT_AUDIT.md`) with the 7 sections from §A Phase 3: executive
summary, architectural mental model, findings table (30–80 entries with file:line
citations), top-5 priorities with diff sketches, quick-wins checklist, "looks bad but
actually fine" (≥3 entries, required), and open questions.

Transit is the right pilot target: largest backend slice (10 GTFS-RT REST + 1 WebSocket +
pollers + ETLs + snapshots), clear churn in three files (`routes.py`, `poller.py`,
`service.py`), and it touches every §A dimension that matters for this stack — async DB,
Redis cache + Pub/Sub, TimescaleDB hypertables, PostGIS, GTFS-RT protobufs, background
tasks with circuit breakers, external HTTP clients, WebSocket fan-out. If the protocol is
going to break, it'll break here first.

Downstream: Stage 1.3 ships 3 quick-win PRs, Stage 4 triages, Stage 5 cross-references
agent-adjacent findings. Per §A: cite `file:line` on every finding — vague claims rejected.

## User Story

As the VTV maintainer
I want a Phase-1-grounded, citation-backed tech-debt audit of `app/transit/`
So that I can ship the 3 highest-value quick wins immediately, hand architectural findings
off to the Architecture-Deepening plan, and validate that the §A protocol produces
actionable output before fanning it out across the rest of the backend.

## Security Contexts

This plan produces a read-only audit document. It does not add endpoints, mutate data,
accept file uploads, or change auth surfaces. **No security context is "active" in the
implementation sense** because no new code is shipping.

The audit MUST itself surface security-hygiene findings under §A Phase 2 dimension 8.
While performing the audit, apply the security-context checklist as an inspection lens:

- **CTX-AUTH (lens):** every transit endpoint passes through `get_current_user` /
  `require_role()`. Any miss is a Critical finding.
- **CTX-RBAC (lens):** admin-mutation endpoints (e.g., phone assignment CRUD) use
  `require_role(["admin"])`; dispatcher reads pass through `RequestScope` per OPS-4.2.
- **CTX-INPUT (lens):** flag any LIKE/ILIKE without `escape_like()`, any `Query()` string
  without `max_length`, any constrained string field using bare `str` instead of
  `Literal[...]` (anti-pattern #54).
- **CTX-AGENT (lens):** journey planner and ETA endpoints expose tool-shaped responses;
  inspect for credential leakage in errors, raw connection strings in logs, unsanitised
  LLM-bound payloads.

CTX-FILE and CTX-INFRA are **not applicable** — `app/transit/` does not handle file
uploads and does not own infra config.

## Solution Approach

Follow the §A protocol literally: forced Phase 1 orientation, pause-and-ask, Phase 2
dimension sweep with file:line citations, Phase 3 deliverable. Encoded as numbered tasks
so the executing agent can drive without re-deriving the protocol.

**Approach Decision — encode §A as a numbered task list rather than a single prompt:**
- §A has a **mandatory pause point** between Phase 1 and Phase 2. An unstructured prompt
  routinely skips this; a numbered task with explicit STOP enforces it.
- Quality gates (§1.2) are checkable per-section. Wiring them into per-task validation
  catches a thin Phase 2 sweep before the deliverable is written.
- The deliverable is built incrementally; per-task chunking lets the agent stop/resume and
  the reviewer spot-check.

**Alternatives Considered:**
- **One mega-prompt**: Rejected — almost always skips the surprise-pause.
- **Programmatic audit**: Rejected — most §A dimensions need judgment, not regex.
- **Skip pilot, fan out directly**: Rejected — Stage 1 is the calibration step; fanning
  out on a noisy protocol wastes 4–6 days.

## Relevant Files

The executing agent MUST read these files before starting the audit. Citations are exact —
do not paraphrase findings; quote the file and line.

### Core Files (orientation — Phase 1)
- `CLAUDE.md` — Architecture rules (VSA, type safety), logging taxonomy, anti-pattern ref.
- `docs/PLANNING/Tech-Debt-Audit-Plan.md` (lines 35–84) — Stage 1 procedure & quality gates.
- `docs/PLANNING/Tech-Debt-Audit-Plan.md` (lines 249–311) — §A audit protocol (authoritative).
- `docs/PLANNING/Tech-Debt-Audit-Plan.md` (lines 314–333) — §B triage rubric.
- `app/transit/README.md` — module's own narrative; flag drift vs code as a finding.

### Transit Files (Phase 2 sweep — churn × size order)
Hotspots (intersection of largest + highest-churn — per §A, where debt hides):
- `routes.py` (518 LOC, 12 commits/6mo), `poller.py` (518, 10), `service.py` (376, 9).

Large lower-churn: `traffic_etl.py` (500), `historical_gtfs_importer.py` (408),
`eticket_importer.py` (357), `owntracks_listener.py` (366), `weather_etl.py` (354),
`feed_client.py` (353), `journey_planner.py` (347), `train_ws_listener.py` (314),
`ckan_client.py` (271).

Smaller (≤200 LOC, second pass): `schemas.py`, `schemas_eta.py`, `models.py`,
`repository.py`, `redis_reader.py`, `gtfs_rt_publisher.py`, `locshare.py`,
`otp_client.py`, `snapshot_*.py`, `traffic_models.py`, `weather_models.py`, `ws_*.py`.

### Test Files (dim 4)
`app/transit/tests/` — 27 modules. Verify coverage on hotspots first (`test_routes.py`,
`test_poller.py`, `test_service.py`).

### Files to Modify (output)
- `TECH_DEBT_AUDIT.md` (CREATE at repo root) — sole deliverable.

## Research Documentation

- [§A Audit Protocol](docs/PLANNING/Tech-Debt-Audit-Plan.md#a-audit-protocol-referenced-from-stages-1-2-3-5)
  — Phase 1 (Orient), Phase 2 (12 dimensions), Phase 3 (Deliverable), Rules, Stack tooling.
  Use for: every audit step.
- [§B Triage Rubric](docs/PLANNING/Tech-Debt-Audit-Plan.md#b-triage-rubric-referenced-from-stage-4)
  — Severity 1–4, Effort S/M/L. Quick win = Effort S × Severity ≥ Medium.
  Use for: severity/effort columns of the findings table; quick-wins checklist.
- [Stage 1 procedure](docs/PLANNING/Tech-Debt-Audit-Plan.md#stage-1--pilot-audit-on-apptransit)
  — Run audit → verify gates → ship 3 quick wins. This plan covers Run + Verify.

## Implementation Plan

- **Phase 1 — Orientation.** Build the mental model from primary sources before judgment.
  Follow §A Phase 1 steps 1–6 verbatim. Output: 1–2 paragraph mental model in Section 2.
- **Phase 2 — Pause & ask.** Hard stop. Surface surprises and solicit out-of-dimension
  investigations from the maintainer. Skipping = plan violation.
- **Phase 3 — Audit sweep.** Apply §A Phase 2 dims 1–9 and 11. Skip dim 10 (agent surface
  — excluded) and dims 12–13 (frontend). Cite file:line on every finding.
- **Phase 4 — Deliverable.** Assemble the 7 sections per §A Phase 3 in order. Self-check
  the 4 quality gates from §1.2 before declaring done.

## Step by Step Tasks

IMPORTANT: Execute every step in order. Task 8 is a HARD STOP requiring a user response;
proceeding without it violates the protocol.

### Task 1: Read the audit protocol (no output yet)
**File:** none **Action:** READ

Load `docs/PLANNING/Tech-Debt-Audit-Plan.md` lines 35–84 (Stage 1 + gates), 249–311
(§A protocol), 314–333 (§B rubric). Confirm: (a) 4 quality gates in §1.2, (b) 13 Phase 2
dimensions, (c) 7-section deliverable, (d) file:line on every concrete finding.

**Per-task validation:** Self-check — list the 4 gates from memory.

---

### Task 2: Read the module narrative
**File:** none **Action:** READ

- `app/transit/README.md` (full).
- `CLAUDE.md` — `Project Structure` line for `transit/`; global type-safety, logging, VSA.

Note any claim that looks suspicious vs the inventory (35 files, 27 test modules,
6612 LOC). README/code drift = automatic dim-9 finding.

**Per-task validation:** None.

---

### Task 3: Map the directory structure
**File:** none **Action:** ANALYZE

```bash
ls -la app/transit/
wc -l app/transit/*.py | sort -rn | head -20
ls app/transit/tests/ | wc -l
```

Identify sub-modules within `app/transit/`: REST surface (`routes.py`, `ws_routes.py`),
service layer (`service.py`, `journey_planner.py`), ingestors (`poller.py`,
`*_listener.py`), ETLs (`*_etl.py`, `*_importer.py`), external clients (`*_client.py`),
persistence (`models.py`, `repository.py`, `snapshot_*.py`, `*_models.py`), cache/publish
(`redis_reader.py`, `gtfs_rt_publisher.py`, `ws_*.py`), schemas (`*_schemas.py`).

Any file that doesn't fit one of these is a finding.

**Per-task validation:** `wc -l` output recorded for §A Phase 1 step 5.

---

### Task 4: Run churn + hotspot analysis
**File:** none **Action:** ANALYZE

```bash
git log --oneline --since="6 months ago" -- app/transit/ | wc -l
git log --stat --since="6 months ago" -- app/transit/ \
  | grep -E "^\s+app/transit/.*\.py" \
  | awk '{print $1}' | sort | uniq -c | sort -rn | head -15
git log --oneline -200 -- app/transit/
```

Compute the **intersection** of "top 20 largest files" (Task 3) with "20 most-modified
in 6 months." Per §A: debt concentrates in this intersection.

Expected hotspots: `routes.py`, `poller.py`, `service.py`. Divergence is a finding.

**Per-task validation:** Output of all three commands recorded.

---

### Task 5: Run static-analysis tooling (best effort)
**File:** none **Action:** ANALYZE

Per §A Stack-specific tooling — Python:
```bash
uvx pip-audit 2>&1 | tee /tmp/transit-pip-audit.txt
uvx vulture app/transit/ 2>&1 | tee /tmp/transit-vulture.txt
uv run mypy --strict app/transit/ 2>&1 | tee /tmp/transit-mypy-strict.txt
uv run pyright app/transit/ 2>&1 | tee /tmp/transit-pyright.txt
uvx pydeps app/transit --show-cycles --noshow 2>&1 | tee /tmp/transit-pydeps.txt
```

If a tool isn't installed, log "tool unavailable" inline. DO NOT install dev tools globally.

Tool output feeds: dim 1 (vulture → dead code), dim 3 (mypy/pyright → type debt),
dim 5 (pip-audit → CVEs).

**Per-task validation:** Each tool either produced output OR was logged unavailable.

---

### Task 6: Read hotspot files (in priority order)
**File:** none **Action:** READ

Read in this exact order:
1. `routes.py` — REST surface.
2. `service.py` — business logic spine.
3. `poller.py` — async background spine.
4. `schemas.py` — wire contracts.
5. `models.py` — DB contracts.
6. `repository.py` — DB access.
7. `feed_client.py`, `ckan_client.py`, `otp_client.py` — external boundary.
8. `ws_routes.py`, `ws_manager.py`, `ws_subscriber.py` — realtime surface.

While reading, mark candidate findings in working notes as
`[F-NN] dim=<N> sev=<C/H/M/L> path:line — description`. Renumber later.

**Per-task validation:** All 8 files read in order. Working notes have ≥10 candidate
findings before proceeding.

---

### Task 7: Write Section 2 — architectural mental model (initial scaffold)
**File:** `TECH_DEBT_AUDIT.md` **Action:** CREATE

Create at repo root with all 7 sections present. Sections 1, 3, 4, 5, 6, 7 have `_TBD_`
placeholders. Section 2 is the only populated section.

Section 2 = 1–2 paragraph mental model of `app/transit/` as it actually is. Per §A Phase
1 step 6: "If your model contradicts the README or CLAUDE.md, flag it." Cover: actual
responsibilities (vs README), data-flow shape (request → service → repo → DB; poller →
cache → publish; ETL → hypertable), what's *not* here that you'd expect.

No sycophancy ("overall well-structured" → rejected per §A).

**Per-task validation:** File exists; Section 2 is 1–2 paragraphs (not bulleted); README/
CLAUDE.md deviations flagged with "Drift:" prefix.

---

### Task 8: STOP — pause-and-ask the maintainer
**File:** none **Action:** PAUSE

Required by Stage 1.1. Surface to user: (1) Section 2 mental model verbatim; (2) 2–3
most surprising things from orientation (specific, file:line); (3) ≥1 dimension/sub-area
outside §A worth investigating. Ask: "Anything I should investigate that isn't in the
dimensions list, or any dimension I should de-prioritise?"

DO NOT proceed to Task 9 without a maintainer response. "Proceed" counts.

**Per-task validation:** User response exists between Task 8 and Task 9.

---

### Task 9: Phase 2 dim 1 — architectural decay
**File:** working notes **Action:** ANALYZE

Look for: circular deps in `app/transit/`, layering violations (route → DB direct, repo →
service, **cross-feature writes** per VSA), god files (>800 LOC; `routes.py`/`poller.py`
at 518 are sub-threshold — flag only with function-level evidence), god functions
(>100 LOC), duplicated logic across 3+ sites, unused abstractions, dead code (vulture).

Cross-feature write check: grep `session.add(<not-transit-model>)` or commits mutating
alerts/vehicles/drivers tables from `app/transit/`. Fleet→transit bridge *publishes*
to transit channels (correct); transit writing to other features' tables is the violation.

**Per-task validation:** ≥2 findings tagged `dim=1` with file:line.

---

### Task 10: Phase 2 dim 2 — consistency rot
**File:** working notes **Action:** ANALYZE

```bash
rg "import httpx|import aiohttp|import requests" app/transit/
rg "structlog.get_logger|get_logger" app/transit/
rg "datetime.utcnow|datetime.now\(" app/transit/
```

Multiple HTTP clients, error shapes, logger idioms (`app.core.logging.get_logger` vs
`structlog.get_logger`), config drift, date drift (`datetime.utcnow()` vs
`app.shared.models.utcnow()`).

**Per-task validation:** ≥2 findings tagged `dim=2` with file:line.

---

### Task 11: Phase 2 dim 3 — type & contract debt
**File:** working notes **Action:** ANALYZE

Cross-reference Task 5 mypy/pyright. Every existing `# type: ignore`, `Any`, loose `dict`
is a candidate.

```bash
rg "# type: ignore|:\s*Any\b|->\s*Any\b|dict\[str, Any\]" app/transit/
```

Untyped API boundaries and missing schema validation at trust boundaries (external feeds)
are CRITICAL. Look at `feed_client.py`, `ckan_client.py` payload parsing.

**Per-task validation:** ≥3 findings tagged `dim=3` with file:line.

---

### Task 12: Phase 2 dim 4 — test debt
**File:** working notes **Action:** ANALYZE

For each hotspot file (`routes.py`, `poller.py`, `service.py`):
- Open `tests/test_<file>.py`.
- `git log -p --since="3 months ago" -- app/transit/<file>.py` → recently modified
  functions; check coverage.
- Flag tests asserting internals over observable behavior.
- Flag `@pytest.mark.skip` / `xfail` without an issue link.
- Flag high-churn files with no test file at all.

```bash
rg "@pytest.mark.skip|@pytest.mark.xfail" app/transit/tests/
```

**Per-task validation:** ≥2 findings tagged `dim=4` with file:line.

---

### Task 13: Phase 2 dim 5 — dependency & config debt
**File:** working notes **Action:** ANALYZE

Cross-reference `pip-audit`. Inspect `pyproject.toml` for transit-relevant deps (httpx,
paho-mqtt, websockets, google-transit-protobuf, lxml). Duplicated functionality?

```bash
rg "os.getenv|settings\." app/transit/ | sort -u | head -50
```

Cite env vars read in transit but missing from `.env.example` (or vice versa).

**Per-task validation:** ≥1 finding tagged `dim=5` with file:line, OR "Nothing material".

---

### Task 14: Phase 2 dim 6 — performance & resource hygiene
**File:** working notes **Action:** ANALYZE

```bash
rg "time\.sleep|requests\.(get|post|put|delete)" app/transit/
rg "httpx\.AsyncClient\(\)" app/transit/
```

N+1 queries (`for x in xs: await session.execute(...)`), sync in async (`time.sleep`,
blocking `requests.get`, sync `open()`), unclosed httpx clients (no async-with),
unclosed websockets, polling without back-off, missing circuit breakers (LV-2.3 added
some — verify all feeds covered). `poller.py` is the highest-yield target.

**Per-task validation:** ≥2 findings tagged `dim=6` with file:line.

---

### Task 15: Phase 2 dim 7 — error handling & observability
**File:** working notes **Action:** ANALYZE

```bash
rg "except Exception:\s*$|except.*:\s*pass" app/transit/
rg "raise HTTPException" app/transit/   # should be zero — use AppError
```

Swallowed exceptions (anti-pattern #37), blanket catches, errors logged but not handled,
inconsistent error shapes (`AppError` subclasses vs raw `HTTPException`), missing
structured-log events on critical paths. Cite `make audit-log-taxonomy` output directly
if it covers `app/transit/`.

**Per-task validation:** ≥2 findings tagged `dim=7` with file:line.

---

### Task 16: Phase 2 dim 8 — security hygiene
**File:** working notes **Action:** ANALYZE

Apply security-context lenses:
- Every endpoint in `routes.py`/`ws_routes.py` MUST pass through `get_current_user` /
  `require_role()`. Missing auth = CRITICAL.
- LIKE/ILIKE must use `escape_like()` from `app.shared.utils`.
- All `Query(...)` string params need `max_length`.
- Constrained string fields use `Literal[...]` (anti-pattern #54).
- Hardcoded secrets/API keys (literal values).
- Pydantic constraints on shared models (anti-pattern #15).

```bash
rg "@router\.(get|post|put|delete|patch|websocket)" app/transit/routes.py app/transit/ws_routes.py -A 5
rg "ilike\(|like\(|Query\(" app/transit/
```

**Per-task validation:** ≥1 finding tagged `dim=8` with file:line, OR "Nothing material".

---

### Task 17: Phase 2 dim 9 — documentation drift
**File:** working notes **Action:** ANALYZE

Compare `app/transit/README.md` vs code:
- Endpoint count claimed vs actual `@router.*` count.
- Background tasks claimed vs actual `asyncio.create_task` / arq registrations.
- TODO/FIXME/XXX older than 3 months (`git blame`).

```bash
rg "TODO|FIXME|XXX|HACK" app/transit/
rg "@router\." app/transit/routes.py app/transit/ws_routes.py | wc -l
```

Public functions without docstrings (esp. `service.py`, exposed clients).

**Per-task validation:** ≥1 finding tagged `dim=9` with file:line, OR "Nothing material".

---

### Task 18: Phase 2 dim 11 — GTFS / PostGIS / TimescaleDB
**File:** working notes **Action:** ANALYZE

THE reason we picked transit for the pilot. Spend 30+ minutes.

- **Spatial-index coverage:** every lat/lon in `models.py`, `snapshot_models.py`,
  `weather_models.py`, `traffic_models.py` should be `Geometry(Point, 4326)` with GIST
  index, or have an explicit float reason.
- **Hypertable retention/compression drift:** `vehicle_positions`, `weather_observations`,
  `traffic_counts` — cross-ref `alembic/versions/*` for retention/compression DDL.
- **Feed-poller liveness:** `poller.py` updates a liveness gauge on every poll for every
  feed (OPS-2.1 metric `vtv_*_poller_*`).
- **Raw-SQL spatial queries:**
  ```bash
  rg "ST_DWithin|ST_Contains|ST_Intersects|geography\(|geometry\(" app/transit/
  ```
  Any raw `text("ST_...")` without parameterised form = finding.
- **GTFS-RT protobuf:** unhandled enum drift in `feed_client.py` = finding.

**Per-task validation:** ≥3 findings tagged `dim=11` with file:line. Spec-heaviest
dimension; thin output = thin audit.

---

### Task 19: Re-number findings; assign severity/effort
**File:** working notes **Action:** ANALYZE

Per §B Triage rubric: Severity = Critical/High/Medium/Low; Effort = S (≤4h) / M (1–3 days)
/ L (>3 days).

Re-number every finding as `T-001`, `T-002`, … (T = transit pilot prefix).

Confirm count is in `[30, 80]`. <30 = thin audit (revisit dim 18); >80 = padding (per
§A "above 80 = padding") — collapse related findings.

**Per-task validation:** N findings where 30 ≤ N ≤ 80, each with ID, dim, severity,
effort, file:line.

---

### Task 20: Write Section 1 — Executive summary
**File:** `TECH_DEBT_AUDIT.md` **Action:** UPDATE

Max 10 bullets, ranked by impact, each referencing a finding ID. Example:
> - **Critical: Missing GIST index on `weather_observations.location`** (T-014). Spatial
>   joins fall back to seq scan; affects every weather-feature ETA inference. Effort: S.

No filler. <10 is fine.

**Per-task validation:** 5–10 bullets; every bullet references ≥1 finding ID; no bullet
says "overall the code is well-structured."

---

### Task 21: Write Section 3 — Findings table
**File:** `TECH_DEBT_AUDIT.md` **Action:** UPDATE

```
| ID | Category | File:Line | Severity | Effort | Description | Recommendation |
|----|----------|-----------|----------|--------|-------------|----------------|
| T-001 | Architectural decay | app/transit/poller.py:142 | High | M | <one sentence> | <one sentence> |
```

Every row has a non-empty file:line. Recommendations scoped (§A: "Don't recommend
rewrites"). Bad: "rewrite poller". Good: "extract `_handle_feed_response` from
poller.py:340–410 into `_FeedResponseHandler`."

**Per-task validation:** rows in `[30, 80]`; every row has file:line; spot-check 5 rows
(file exists, line plausible); no recommendation says "rewrite" without scoped follow-up.

---

### Task 22: Write Section 4 — Top 5 priorities
**File:** `TECH_DEBT_AUDIT.md` **Action:** UPDATE

5 highest-impact findings (mostly Critical/High). For each, a concrete diff sketch or
refactor outline (§A: "not vague advice"). Example:
> ### Priority 1: T-007 — async-context-manager for httpx in feed_client.py
> ```python
> # Before: feed_client.py:88
> client = httpx.AsyncClient(timeout=10)
> resp = await client.get(url)   # client never closed on exception
>
> # After:
> async with httpx.AsyncClient(timeout=10) as client:
>     resp = await client.get(url)
> ```

**Per-task validation:** Exactly 5 priorities; each has a code-style diff sketch.

---

### Task 23: Write Section 5 — Quick wins checklist
**File:** `TECH_DEBT_AUDIT.md` **Action:** UPDATE

Quick win = `Effort=S` AND `Severity ≥ Medium` (per §B). Checklist format:
```
- [ ] **T-014** — Add GIST index on weather_observations.location (Effort=S, Severity=High)
```
Stage 1.3 ships 3. Top 3 must each be shippable in <4h.

**Per-task validation:** ≥3 quick wins; each Effort=S, Severity ≥ Medium per findings table.

---

### Task 24: Write Section 6 — Looks bad but actually fine
**File:** `TECH_DEBT_AUDIT.md` **Action:** UPDATE

**REQUIRED ≥3 entries.** "Empty = audit didn't look hard enough" (§A).

Each entry: a finding you considered flagging and chose not to, with the reasoning that
closed it. Example:
> **`poller.py` is 518 LOC and looks like a god file.** Considered flagging as
> architectural decay. Decided against: one orchestrator class with clearly separated
> `_handle_feed_*` methods. Splitting per-source would add cross-file coupling without
> removing complexity. Keep.

Cover at least: an architectural choice (ADR-supported), type debt (intentional `Any` at
protobuf/LLM boundary), test gap (genuinely flaky external).

**Per-task validation:** ≥3 entries (hard gate). Each has surface concern + reasoning.

---

### Task 25: Write Section 7 — Open questions
**File:** `TECH_DEBT_AUDIT.md` **Action:** UPDATE

≥2 entries. Debt-vs-intentional uncertainties unresolvable from code alone:
> **Q1: Is OwnTracks → `transit:vehicles:fleet` the sole ingest path for phone-tracked
> drivers, or is fleet/Traccar redundant once OwnTracks is live?** Both pipelines write
> the same vehicle_id space; no de-duplication exists. If one is meant to win, undocumented.
> Files: `owntracks_listener.py:184`, `app/fleet/service.py:62`.

**Per-task validation:** ≥2 entries (hard gate).

---

### Task 26: Self-check the 4 quality gates
**File:** none **Action:** ANALYZE

Per §1.2: (1) findings in `[30, 80]`; (2) Section 6 ≥3; (3) ≥1 Critical OR ≥3 High;
(4) Section 7 ≥2; (5, implicit) every finding has `file:line`. If any gate fails, do
NOT declare done — re-run Phase 2 with tighter scope. Most common failure: Gate 3 →
under-audited dim 8 + dim 11 → return to Tasks 16, 18.

**Per-task validation:** All 4 gates pass.

---

### Task 27: Final hygiene pass
**File:** `TECH_DEBT_AUDIT.md` **Action:** UPDATE

- Section order matches §A Phase 3. No `_TBD_` left.
- Finding IDs unique and contiguous (T-001 … T-NN).
- Spot-check 10 random `file:line` cells.
- "Nothing material" used only where genuinely nothing material (no padding elsewhere).
- No filler ("well-structured", "comprehensive coverage") — rejected per §A.

**Per-task validation:** `npx -y markdownlint-cli2 TECH_DEBT_AUDIT.md` passes (style
nits OK, hard errors fixed); 10 random file:line cells resolve.

---

## Migration / Logging Events

**Not applicable.** No schema changes; no new code emits structured logs. Dim-7 logging
findings are recorded in the audit, not added as new logs.

## Testing Strategy

Audit deliverable, not code. "Tests" = quality gates (Task 26) + spot-check (Task 27).
No pytest suite.

**Gates (Task 26):** 30 ≤ findings ≤ 80; ≥3 in Section 6; ≥1 Critical OR ≥3 High; ≥2 in
Section 7; every finding cites `file:line`.
**Spot-check (Task 27):** 10 random Section-3 rows resolve; 5 random recommendations are
scoped (no vague "rewrite"/"consider").
**Edge cases:** Tool unavailable → log inline. Empty dimension → "Nothing material" + move
on (no padding). Cross into `app/core/agents/` → Stage-5 advisory note, not Section 3.

## Acceptance Criteria

- [ ] `TECH_DEBT_AUDIT.md` exists at repo root.
- [ ] All 7 sections populated; no `_TBD_`.
- [ ] Findings count in `[30, 80]`.
- [ ] Section 6 has ≥3 entries.
- [ ] ≥1 Critical OR ≥3 High findings.
- [ ] Section 7 has ≥2 entries.
- [ ] Every finding cites `file:line`.
- [ ] Random 10-row spot-check resolves.
- [ ] No sycophancy/filler.
- [ ] Task 8 pause-and-ask honoured (user response between Task 8 and Task 9).
- [ ] No code under `app/transit/` modified.
- [ ] No file under `app/core/agents/` cited.

## Final Validation (5-Level Pyramid — adapted for markdown)

**L1 file hygiene:**
```bash
test -f TECH_DEBT_AUDIT.md
wc -l TECH_DEBT_AUDIT.md            # 600–1500
grep -c "^| T-" TECH_DEBT_AUDIT.md  # 30–80
```
**L2** quality gates (Task 26). **L3** spot-check (Task 27). **L4** no regressions —
`git status app/transit/` clean. **L5** protocol adherence — Phase 1 (Tasks 2–6),
pause-and-ask (Task 8), Phase 2 dim 1–9+11 (Tasks 9–18), Phase 3 (Tasks 7, 20–25, 27).

**Success:** L1–L3 pass, L4 read-only, L5 protocol adherence.

## Dependencies

None. Uses `uvx`-launched (`pip-audit`, `vulture`, `pydeps`) + installed `mypy`/`pyright`.
No shared utilities, core modules, or new env vars.

## Known Pitfalls

The 59 anti-pattern rules apply as **inspection lenses** (spot violations in
`app/transit/`), not as constraints on the audit document.

- **Don't skip Task 8 (pause).** Most common protocol violation; §1.2 gates don't catch it.
- **Don't pad to hit 30.** Worse than "Nothing material". Section 6 is for cut candidates.
- **Don't recommend rewrites.** "Rewrite poller.py" → reject. "Extract
  `_handle_feed_response` from poller.py:340–410 into `_FeedResponseHandler`" → accept.
- **Don't cross into `app/core/agents/`.** Owned by Secure-AI; agent-natural findings →
  Stage 5.
- **Cite file:line, not file alone.** "Coupling between routes.py and service.py" →
  reject. "routes.py:240 imports `_internal_helper` from service.py:340" → accept.
- **Cross-feature reads OK; writes NOT.** Fleet-bridge writes `feed:fleet:*` (own
  namespace), publishes to `transit:vehicles:fleet` — correct. Transit writing to
  `vehicles_table` = Critical.
- **`poller.py`/`routes.py` are 518 LOC, not 800+** — don't auto-flag as god files (§A
  threshold >800); function-level evidence required.
- **Doc drift goes both ways.** README claiming a missing feature OR omitting an existing
  one both count.
- **Logging-taxonomy drift is auto-checkable.** Cite `make audit-log-taxonomy` output
  under dim 7; don't re-derive.
- **Constrained strings → `Literal[...]`** (anti-pattern #54).
- **`AppError` not `HTTPException`** — raw `raise HTTPException(...)` in routes is a
  dim-7 finding.

## Notes

**Unusual shape.** Most `/be-planning` outputs describe code creation; this describes an
analysis producing markdown. Same scaffolding (numbered tasks, per-task validation,
checklist) but the agent reads + synthesises, not writes Python.

**Downstream.** Stage 1.3 ships 3 PRs from Section 5; Stage 4 applies §B compound-score;
Stage 5 cross-references agent-adjacent findings into `SECURE_AI_GAPS.md`; Architecture-
Deepening Stage 1 reads `→ DEEPEN`-tagged findings (tagged in Stage 4).

**Repeat-run mode.** If `TECH_DEBT_AUDIT.md` already exists at repo root, follow §A
Repeat-run: mark resolved findings `RESOLVED`, tag new ones `NEW`. Informational for
the pilot (fresh file expected).

## Pre-Implementation Checklist

Before starting Task 1:
- [ ] Read this entire plan.
- [ ] Read `docs/PLANNING/Tech-Debt-Audit-Plan.md` lines 35–84, 249–333.
- [ ] Confirmed `app/core/agents/` and `cms/` are excluded scope.
- [ ] `uvx`, `uv`, `rg`, `git` available.
- [ ] Can recite the 4 quality gates from §1.2 without looking.
- [ ] Aware that Task 8 is a HARD STOP requiring a user response.
