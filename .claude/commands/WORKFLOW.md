# VTV Slash Commands & Workflows

33 slash commands organized into pipelines. Each command produces artifacts that the next command consumes, forming composable workflows.

---

## Architecture — How Commands Work Together

### Token-Optimized System

Commands use a deduplication architecture to minimize token waste:

```
.claude/
├── rules/                  # Path-scoped rules (auto-load based on files touched)
│   ├── backend.md          # Loads for app/**/*.py — middleware, Docker, config details
│   ├── frontend.md         # Loads for cms/**/*.ts{x} — React 19, Tailwind v4, dialog conventions
│   ├── security.md         # Loads for auth/**, middleware**, scripts/** — auth patterns, pre-commit
│   └── testing.md          # Loads for **/tests/**, e2e/**, .github/** — CI, pytest, Playwright
├── commands/
│   ├── _shared/            # Deduplication — loaded via @ references, NOT always-on
│   │   ├── python-anti-patterns.md   # 59 rules, single source of truth
│   │   ├── security-contexts.md      # 6 context-triggered security categories
│   │   ├── tailwind-token-map.md     # Forbidden → semantic token mappings
│   │   └── frontend-security.md      # Security grep commands + checklist
│   ├── be-*.md             # Backend commands (10)
│   ├── fe-*.md             # Frontend commands (9)
│   └── *.md                # Cross-cutting commands
├── hooks/
│   └── filter-test-output.sh  # (Optional) Caps test output to last 60 lines
└── settings.local.json     # Auto-format hook: ruff on .py, prettier on .ts/.tsx
```

**How it saves tokens:**
- Rules only load when you touch matching files (backend rules don't load during frontend work)
- `_shared/` files load once per command invocation, not 3-4x across duplicate commands
- Auto-format hook eliminates formatting round-trips (~10-25K tokens/session)
- Compaction instructions in `CLAUDE.md` prevent expensive context recovery

### Session Hygiene

- `/clear` between unrelated tasks (resets context, saves tokens)
- `/compact focus on X` at natural breakpoints (keeps important context, discards noise)
- Plan mode for multi-file changes; direct edits for trivial fixes
- Subagents for cross-cutting research; direct tools for 1-2 file edits

---

## All Commands — Detailed Reference

### Setup Commands

#### `/be-init-project`
Bootstraps the dev environment from scratch. Verifies Python 3.12+, uv, Docker, Docker Compose. Starts PostgreSQL + FastAPI containers, waits for health, hits `/health` endpoint. Reports status with link to Swagger UI at `/docs`.

**When to use:** Start of new session, after reboot, when Docker needs restarting.
**Produces:** Running Docker services, healthy API endpoint.

#### `/be-create-feature {name}`
Scaffolds a complete vertical slice directory: `schemas.py`, `models.py`, `repository.py`, `service.py`, `exceptions.py`, `routes.py`, `tests/`, `README.md`. Pre-wired with async SQLAlchemy, structured logging, type annotations. Registers router in `app/main.py`.

**Example:** `/be-create-feature orders` creates `app/orders/` with all files.
**When to use:** Starting a new feature from scratch, prefer over manual file creation.
**Produces:** Compilable skeleton ready for implementation.

#### `/fe-create-page {name}`
Scaffolds a Next.js page with i18n keys (lv + en), sidebar nav entry, RBAC middleware matcher, and semantic design tokens. Uses server component pattern from the dashboard page.

**Example:** `/fe-create-page analytics` creates `cms/apps/web/src/app/[locale]/(dashboard)/analytics/page.tsx`.
**When to use:** Quick page scaffolding without going through the full planning pipeline.
**Produces:** Minimal placeholder page with all integrations wired.

---

### Context Loading Commands

#### `/be-prime`
Loads the full VTV project context: reads `CLAUDE.md`, `PRD.md`, `mvp-tool-designs.md`. Explores `app/` structure, reads `app/main.py`, checks Docker/API status, reviews last 10 commits.

**When to use:** Start of any backend work session.
**Produces:** Session-wide project understanding — architecture, features, current state.
**Chains with:** Run before `/be-planning` or any manual backend work.

#### `/be-prime-tools`
Deep-dive into the AI agent tool system: loads tool specs from `mvp-tool-designs.md`, inventories implemented vs planned tools, checks docstrings against 5-principle format, reviews dry-run patterns and error formats.

**When to use:** Before building, modifying, or debugging any agent tool.
**Produces:** Tool-specific context in session memory.
**Chains with:** Run before `/be-planning` when the feature is an agent tool.

#### `/fe-prime`
Loads the full frontend context: design system master doc, shadcn/ui component inventory, all pages and routes, i18n coverage, RBAC middleware config, SDK generation state.

**When to use:** Start of any frontend work session.
**Produces:** Session-wide frontend understanding.
**Chains with:** Run before `/fe-planning` or any manual frontend work.

---

### Planning Commands

#### `/be-planning {description}`
Researches the codebase and creates a 600-700 line self-contained implementation plan. Explores existing features for patterns (with exact file paths and line ranges), identifies shared utilities to reuse, plans migrations, defines logging events. Auto-detects agent tool features and adds tool-specific sections.

**Example:** `/be-planning add driver availability tracking`
**Loads:** `@CLAUDE.md`, `@reference/PRD.md`, `@_shared/python-anti-patterns.md`
**When to use:** Before implementing any non-trivial backend feature.
**Produces:** `.agents/plans/{feature-name}.md` — a machine-executable plan.
**Chains with:** Plan consumed by `/be-execute` to implement.

#### `/fe-planning {description}`
Researches the frontend codebase and creates a 400-600 line plan. Checks design system overrides, identifies shadcn/ui components, plans i18n keys for both languages, designs RBAC integration and sidebar nav entry.

**Example:** `/fe-planning add routes management page`
**Loads:** `@CLAUDE.md`, `@cms/design-system/vtv/MASTER.md`, `@_shared/tailwind-token-map.md`, `@_shared/frontend-security.md`
**When to use:** Before implementing any non-trivial frontend feature.
**Produces:** `.agents/plans/fe-{page-name}.md` — a machine-executable plan.
**Chains with:** Plan consumed by `/fe-execute` to implement.

---

### Accelerator Commands

#### `/parallel-plan {description}`
Replaces the sequential `/be-prime` → `/be-planning` flow with 3 parallel agents: **Researcher** (jCodeMunch/jDocMunch exploration), **Test Scout** (fixtures, factories, test patterns), and **Pyright Baseline** (current error counts). Results merge into a single 600-700 line plan.

**Example:** `/parallel-plan add driver availability tracking`
**Loads:** `@CLAUDE.md`, `@_shared/python-anti-patterns.md`, `@_shared/security-contexts.md`
**When to use:** When you want faster planning — skips the separate prime step.
**Produces:** `.agents/plans/{feature-name}.md` — same format as `/be-planning`.
**Chains with:** `/parallel-plan` → `/preflight-check` → `/be-execute` → `/be-ship` → `/commit`

#### `/fe-parallel-plan {description}`
Replaces the sequential `/fe-prime` → `/fe-planning` flow with 3 parallel agents: **Researcher** (routes, components, hooks, RBAC), **Test Scout** (Playwright tests, SDK types, mock patterns), and **TypeScript Baseline** (current tsc/eslint error counts). Results merge into a single 400-600 line plan.

**Example:** `/fe-parallel-plan add fleet telemetry dashboard`
**Loads:** `@CLAUDE.md`, `@cms/design-system/vtv/MASTER.md`, `@_shared/tailwind-token-map.md`, `@_shared/frontend-security.md`, `@_shared/security-contexts.md`
**When to use:** When you want faster frontend planning — skips the separate prime step.
**Produces:** `.agents/plans/fe-{feature-name}.md` — same format as `/fe-planning`.
**Chains with:** `/fe-parallel-plan` → `/fe-preflight-check` → `/fe-execute` → `/fe-ship` → `/commit`

#### `/preflight-check {plan-file}`
Scans the plan's target files for fragile patterns that historically cause fix cycles during `/be-execute`. Auto-fixes hardcoded count assertions, tuple unpacking, string assertions, parameter propagation, and Pydantic field annotations. Captures pyright/mypy baseline.

**Example:** `/preflight-check .agents/plans/driver-availability.md`
**When to use:** After `/parallel-plan` or `/be-planning`, before `/be-execute`.
**Produces:** Preflight report with fixes applied + safe patterns + type check baseline.
**Chains with:** Run before `/be-execute` to prevent fix cycles.

#### `/fe-preflight-check {plan-file}`
Scans the plan's target frontend files for fragile patterns. Auto-fixes hardcoded `toHaveLength` assertions, snapshot tests, mock return values, `as any` casts, destructured props, and API response types. Captures tsc baseline. Flags hardcoded i18n strings.

**Example:** `/fe-preflight-check .agents/plans/fe-fleet-telemetry.md`
**When to use:** After `/fe-parallel-plan` or `/fe-planning`, before `/fe-execute`.
**Produces:** Preflight report with fixes applied + safe patterns + tsc baseline + i18n flags.
**Chains with:** Run before `/fe-execute` to prevent fix cycles.

---

### Execution Commands

#### `/be-execute {plan-file}`
Takes a plan file and implements every step in order. Pre-flight checks, then creates/modifies files following VTV conventions: type annotations, TimestampMixin, async select(), structured logging. Runs database migrations if needed. Full 5-level validation pyramid with 3-attempt error recovery.

**Example:** `/be-execute .agents/plans/driver-availability.md`
**Loads:** `@_shared/python-anti-patterns.md` (59 rules for correct code on first pass)
**When to use:** After `/be-planning` creates a plan.
**Produces:** Implemented feature code, passing validation suite.
**Chains with:** Run `/be-ship` after for full quality gate, then `/commit`.

#### `/fe-execute {plan-file}`
Takes a frontend plan and implements every step. Per-task TypeScript validation after each file. Uses semantic design tokens, next-intl translations, server components by default. Design system compliance scan + security verification.

**Example:** `/fe-execute .agents/plans/fe-routes.md`
**Loads:** `@cms/design-system/vtv/MASTER.md`, `@_shared/tailwind-token-map.md`, `@_shared/frontend-security.md`
**When to use:** After `/fe-planning` creates a plan.
**Produces:** Implemented frontend feature, passing validation suite.
**Chains with:** Run `/fe-ship` after for full quality gate, then `/commit`.

#### `/implement-fix {rca-file}`
Takes an RCA document (from `/rca`) and applies the proposed fix. Writes regression tests named `test_issue_{id}_{description}()`. Runs migrations if needed. Full validation suite.

**Example:** `/implement-fix docs/rca/issue-42.md`
**When to use:** After `/rca` produces an investigation document.
**Produces:** Bug fix code, regression tests, suggested commit message.

#### `/fix-error {description or issue ID}`
One-pass error resolution combining investigation + fix. Gathers error details (from GlitchTip, GitHub issue, or description), traces to source code, identifies root cause, applies fix, writes regression test, validates. No separate RCA document — faster for known-class bugs.

**Example:** `/fix-error RuntimeError in /api/v1/schedules/calendars` or `/fix-error 42`
**When to use:** When you want investigation + fix in one shot (skip separate `/rca` step).
**Produces:** Fixed code, regression test, validation results.
**Chains with:** Run `/commit` after.

---

### Validation Commands

#### `/be-validate`
Runs ALL backend quality checks in sequence: ruff format → ruff check → mypy → pyright → pytest (unit) → pytest (integration, if Docker) → SDK sync (if API running) → server health → security lint → security convention tests.

**When to use:** After any backend code changes, before committing.
**Hard gates:** Steps 1-5 and 9-10 must pass. Steps 6-8 are conditional/soft.
**Produces:** Pass/fail scorecard — the go/no-go for committing.

#### `/fe-validate`
Runs ALL frontend quality checks: TypeScript type-check → ESLint lint → Next.js build (hard gates) → security patterns → design system compliance → i18n completeness → accessibility spot-check.

**When to use:** After any frontend code changes, before committing.
**Hard gates:** TypeScript, lint, build, security. Soft gates: design system, i18n, a11y.
**Produces:** Pass/fail scorecard.

#### `/be-ship`
Full backend quality pipeline in 4 phases: **validate** (10-level pyramid) → **review** (8 standards) → **fix** (critical findings only) → **validate** (final gate). Max 3 retry rounds. Does not commit — user runs `/commit` separately.

**When to use:** After `/be-execute`, before `/commit`. The thorough pre-commit gate.
**Produces:** Ship report with phase-by-phase results.
**Chains with:** `/be-execute` → `/be-ship` → `/commit`

#### `/fe-ship`
Full frontend quality pipeline in 4 phases: **validate** (7 checks) → **review** (8 frontend standards) → **fix** (critical findings only) → **validate** (final gate). Max 3 retry rounds. Does not commit — user runs `/commit` separately.

**When to use:** After `/fe-execute`, before `/commit`. The thorough pre-commit gate.
**Produces:** Ship report with phase-by-phase results.
**Chains with:** `/fe-execute` → `/fe-ship` → `/commit`

#### `/review {path}`
Deep architectural code review against 8 VTV quality standards (type safety, schemas, logging, DB patterns, architecture, docstrings, testing, security). Uses Claude's reasoning — catches design issues that linters miss.

**Example:** `/review app/core/` or `/review app/events/service.py`
**Produces:** `.agents/code-reviews/{target}-review.md` with findings table.
**Chains with:** Review feeds into `/code-review-fix` for automated fixing.

#### `/fe-review {path}`
Frontend-specific review against 8 standards (TypeScript quality, design system, component patterns, i18n, accessibility, RBAC, data fetching, security).

**Example:** `/fe-review cms/apps/web/src/app/[locale]/(dashboard)/routes/`
**Produces:** `.agents/code-reviews/fe-{target}-review.md`.
**Chains with:** Review feeds into `/fe-code-review-fix` or `/code-review-fix`.

#### `/code-review-fix {report} [scope]`
Takes a review report and fixes all findings in priority order (Critical → High → Medium → Low). Optional scope: `all` (default), `critical`, `high`.

**Example:** `/code-review-fix .agents/code-reviews/core-review.md` or `/code-review-fix .agents/code-reviews/core-review.md critical`
**When to use:** After `/review` or `/fe-review` produces a report.
**Produces:** Fixed code, validation results.

#### `/be-code-review-fix {description}`
Diagnoses and fixes any backend issue — bug reports, failing tests, type errors, lint violations, security findings. Unlike `/code-review-fix` which takes a review file, this accepts any issue description and diagnoses from scratch via jCodeMunch.

**Example:** `/be-code-review-fix pyright error in app/fleet/service.py` or `/be-code-review-fix failing test_security auth check`
**When to use:** Backend bugs, test failures, type errors, security findings.
**Produces:** Root cause analysis, fix, verification results.
**Chains with:** `/be-code-review-fix` → `/be-validate` → `/commit`

#### `/fe-code-review-fix {description}`
Diagnoses and fixes any frontend issue — TypeScript errors, design system violations, i18n gaps, a11y issues. Accepts any issue description and diagnoses from scratch.

**Example:** `/fe-code-review-fix TypeScript error in fleet map component` or `/fe-code-review-fix design system violation in geofences page`
**When to use:** Frontend bugs, TypeScript errors, design violations, i18n gaps.
**Produces:** Root cause analysis, fix, verification results.
**Chains with:** `/fe-code-review-fix` → `/fe-validate` → `/commit`

---

### Investigation Commands

#### `/rca {issue}`
Systematic root cause analysis for a bug. Accepts a GitHub issue ID or description. Investigates layer by layer (routes → service → repository → model → schema → middleware). Checks structured logs, exception handlers, git blame.

**Example:** `/rca 42` or `/rca duplicate stops appearing on map`
**Produces:** `docs/rca/issue-{id}.md` with root cause, evidence, proposed fix, required tests.
**Chains with:** Feed into `/implement-fix` for automated fixing.

---

### Git & Documentation Commands

#### `/commit`
Reviews all changes, performs secret detection (`.env`, `*.pem`, `*.key`), stages files explicitly (never `git add .`), creates conventional commit. Does NOT push.

**Format:** `type(scope): description` + `Co-Authored-By: Claude`
**When to use:** After all validation passes. Final step in every workflow.

#### `/update-docs {feature}`
Updates all living documentation after a feature is committed: CLAUDE.md project structure, feature README, PRD feature status, execution report bugs section.

**Example:** `/update-docs events` or `/update-docs .agents/execution-reports/events.md`
**When to use:** After `/commit`, to keep docs in sync with implementation.

#### `/execution-report {plan-file}`
Post-execution reflection comparing plan vs implementation. Identifies divergences, classifies them (better approach, plan gap, security concern), documents what worked.

**Example:** `/execution-report .agents/plans/user-auth.md`
**Produces:** `.agents/execution-reports/{feature}.md`.
**Chains with:** Feeds into `/system-review` for process improvement.

#### `/system-review {plan-file} {report-file}`
Meta-level process improvement. Analyzes divergences as justified or problematic, traces root causes to specific process failures, generates actionable improvements to commands and docs.

**Example:** `/system-review .agents/plans/auth.md .agents/execution-reports/auth.md`
**Produces:** `.agents/system-reviews/{feature}-review.md`.

---

### Testing Command

#### `/e2e [feature]`
Runs Playwright end-to-end tests via CLI. Without arguments, auto-detects changed features via git diff and runs only relevant tests. With a feature name, runs that specific test. With a quoted string, matches by test title.

**Example:** `/e2e` (auto-detect) or `/e2e routes` or `/e2e "dashboard loads"`
**Requires:** Backend on :8123 and frontend on :3000 (or `make dev`).
**Produces:** Pass/fail results, HTML report via `npx playwright show-report`.

---

### Autonomous Commands

#### `/be-end-to-end-feature {description}`
Full lifecycle in 6 phases: prime → plan → execute → validate → execution report → commit. Each phase must succeed before the next starts. Stops entirely after 3 failed recovery attempts.

**Example:** `/be-end-to-end-feature add health dashboard`
**Trust level:** Only use after you've run each individual command separately and verified their output.
**Produces:** Complete feature, plan, execution report, and git commit.

#### `/fe-end-to-end-page {description}`
Full frontend lifecycle in 6 phases: prime → plan → execute → validate → execution report → commit.

**Example:** `/fe-end-to-end-page add driver schedule view`
**Produces:** Complete page, plan, execution report, and git commit.

---

## Command Chaining Workflows

### New Backend Feature (standard — 5 steps)

```
/be-prime → /be-planning → /be-execute → /be-ship → /commit
```

| Step | Command | Input | Output |
|------|---------|-------|--------|
| 1 | `/be-prime` | — | Session context loaded |
| 2 | `/be-planning add brute force tracking` | Feature description | `.agents/plans/brute-force.md` |
| 3 | `/be-execute .agents/plans/brute-force.md` | Plan file | Implemented code |
| 4 | `/be-ship` | — | Ship report (validate→review→fix→validate) |
| 5 | `/commit` | — | Git commit |

**Optional follow-ups:** `/update-docs brute-force` → `/commit` (docs update)

### New Backend Feature (fast path — 5 steps)

```
/parallel-plan → /preflight-check → /be-execute → /be-ship → /commit
```

| Step | Command | Input | Output |
|------|---------|-------|--------|
| 1 | `/parallel-plan add brute force tracking` | Feature description | `.agents/plans/brute-force.md` (3 parallel agents) |
| 2 | `/preflight-check .agents/plans/brute-force.md` | Plan file | Preflight report + auto-fixes |
| 3 | `/be-execute .agents/plans/brute-force.md` | Plan file | Implemented code |
| 4 | `/be-ship` | — | Ship report (validate→review→fix→validate) |
| 5 | `/commit` | — | Git commit |

`/parallel-plan` replaces `/be-prime` + `/be-planning` with 3 concurrent agents (researcher, test scout, pyright baseline). `/preflight-check` scans for hardcoded assertions, tuple unpacking, and fragile patterns before execution.

### New Backend Feature (autonomous — 1 step)

```
/be-end-to-end-feature add brute force tracking
```

Equivalent to the standard chain above plus `/execution-report`, all in one command.

---

### Backend Bug Fix / Code Review Fix

```
/be-code-review-fix → /be-validate → /commit
```

| Step | Command | What happens |
|------|---------|-------------|
| 1 | `/be-code-review-fix pyright error in app/fleet/service.py` | Diagnoses and fixes the issue |
| 2 | `/be-validate` | All checks pass |
| 3 | `/commit` | Git commit |

Skip prime/planning — go straight to diagnosis and fix. Use `/be-prime` first only if you need full context for a complex bug.

---

### New Frontend Page (standard — 5 steps)

```
/fe-prime → /fe-planning → /fe-execute → /fe-ship → /commit
```

| Step | Command | Input | Output |
|------|---------|-------|--------|
| 1 | `/fe-prime` | — | Frontend context loaded |
| 2 | `/fe-planning add vehicle management page` | Page description | `.agents/plans/fe-vehicles.md` |
| 3 | `/fe-execute .agents/plans/fe-vehicles.md` | Plan file | Implemented page |
| 4 | `/fe-ship` | — | Ship report (validate→review→fix→validate) |
| 5 | `/commit` | — | Git commit |

### New Frontend Page (fast path — 5 steps)

```
/fe-parallel-plan → /fe-preflight-check → /fe-execute → /fe-ship → /commit
```

| Step | Command | Input | Output |
|------|---------|-------|--------|
| 1 | `/fe-parallel-plan add vehicle management page` | Page description | `.agents/plans/fe-vehicles.md` (3 parallel agents) |
| 2 | `/fe-preflight-check .agents/plans/fe-vehicles.md` | Plan file | Preflight report + auto-fixes |
| 3 | `/fe-execute .agents/plans/fe-vehicles.md` | Plan file | Implemented page |
| 4 | `/fe-ship` | — | Ship report (validate→review→fix→validate) |
| 5 | `/commit` | — | Git commit |

`/fe-parallel-plan` replaces `/fe-prime` + `/fe-planning` with 3 concurrent agents (researcher, test scout, TypeScript baseline). `/fe-preflight-check` scans for hardcoded assertions, snapshot tests, stale mocks, `as any` casts, and i18n flags.

### New Frontend Page (autonomous — 1 step)

```
/fe-end-to-end-page add vehicle management page
```

---

### Frontend Bug Fix / Code Review Fix

```
/fe-code-review-fix → /fe-validate → /commit
```

| Step | Command | What happens |
|------|---------|-------------|
| 1 | `/fe-code-review-fix design system violation in geofences page` | Diagnoses and fixes the issue |
| 2 | `/fe-validate` | All checks pass |
| 3 | `/commit` | Git commit |

---

### Full-Stack Feature (backend API + frontend UI)

Build the backend first (API endpoints), then the frontend (UI consuming those endpoints):

| Phase | Chain | Commit |
|-------|-------|--------|
| 1. Backend | `/parallel-plan` → `/preflight-check` → `/be-execute` → `/be-ship` → `/commit` | `feat(drivers): add availability endpoint` |
| 2. Frontend | `/fe-parallel-plan` → `/fe-preflight-check` → `/fe-execute` → `/fe-ship` → `/commit` | `feat(cms): add driver availability page` |

Or standard path:

| Phase | Chain | Commit |
|-------|-------|--------|
| 1. Backend | `/be-prime` → `/be-planning` → `/be-execute` → `/be-ship` → `/commit` | `feat(drivers): add availability endpoint` |
| 2. Frontend | `/fe-prime` → `/fe-planning` → `/fe-execute` → `/fe-ship` → `/commit` | `feat(cms): add driver availability page` |

---

### Bug Fix — Full Investigation

```
/rca → /implement-fix → /be-validate → /commit
```

| Step | Command | What happens |
|------|---------|-------------|
| 1 | `/rca 42` | Investigates, creates `docs/rca/issue-42.md` |
| 2 | `/implement-fix docs/rca/issue-42.md` | Applies fix + regression test |
| 3 | `/be-validate` | All checks pass |
| 4 | `/commit` | `fix(stops): deduplicate map markers (Fixes #42)` |

### Bug Fix — Quick One-Pass

```
/fix-error → /commit
```

| Step | Command | What happens |
|------|---------|-------------|
| 1 | `/fix-error RuntimeError in /api/v1/schedules` | Investigates + fixes + tests in one pass |
| 2 | `/commit` | `fix(schedules): handle missing calendar dates` |

### Bug Fix — Trivial (no investigation needed)

```
Edit directly → /be-validate → /commit
```

---

### Code Quality Review

```
/review → /code-review-fix → /be-validate → /commit
```

| Step | Command | What happens |
|------|---------|-------------|
| 1 | `/review app/events/` | Creates `.agents/code-reviews/events-review.md` |
| 2 | `/code-review-fix .agents/code-reviews/events-review.md` | Fixes all findings by priority |
| 3 | `/be-validate` | Confirms no regressions |
| 4 | `/commit` | `refactor(events): address code review findings` |

Frontend variant: `/fe-review` → `/code-review-fix` (or `/fe-code-review-fix`) → `/fe-validate` → `/commit`

---

### Process Improvement (after any feature)

```
/execution-report → /system-review
```

| Step | Command | What happens |
|------|---------|-------------|
| 1 | `/execution-report .agents/plans/auth.md` | Compares plan vs reality |
| 2 | `/system-review .agents/plans/auth.md .agents/execution-reports/auth.md` | Finds process bugs, recommends improvements |

---

## Quick Reference — Which Command When?

| Situation | Commands |
|-----------|----------|
| **New backend feature (standard)** | `/be-prime` → `/be-planning` → `/be-execute` → `/be-ship` → `/commit` |
| **New backend feature (fast path)** | `/parallel-plan` → `/preflight-check` → `/be-execute` → `/be-ship` → `/commit` |
| **New frontend page (standard)** | `/fe-prime` → `/fe-planning` → `/fe-execute` → `/fe-ship` → `/commit` |
| **New frontend page (fast path)** | `/fe-parallel-plan` → `/fe-preflight-check` → `/fe-execute` → `/fe-ship` → `/commit` |
| **Full-stack feature** | Backend chain → Frontend chain (2 commits) |
| **Full auto (BE)** | `/be-end-to-end-feature {description}` |
| **Full auto (FE)** | `/fe-end-to-end-page {description}` |
| **Backend bug fix (direct)** | `/be-code-review-fix {description}` → `/be-validate` → `/commit` |
| **Frontend bug fix (direct)** | `/fe-code-review-fix {description}` → `/fe-validate` → `/commit` |
| **Bug with investigation** | `/rca` → `/implement-fix` → `/be-validate` → `/commit` |
| **Quick error fix** | `/fix-error {description}` → `/commit` |
| **Trivial fix** | Edit directly → `/be-validate` → `/commit` |
| **Code review (BE)** | `/review` → `/code-review-fix` → `/be-validate` → `/commit` |
| **Code review (FE)** | `/fe-review` → `/fe-code-review-fix` → `/fe-validate` → `/commit` |
| **Just validate** | `/be-validate` (backend) or `/fe-validate` (frontend) |
| **Just test e2e** | `/e2e` or `make e2e` |
| **Scaffold feature** | `/be-create-feature {name}` (backend) or `/fe-create-page {name}` (frontend) |
| **Update docs** | `/update-docs {feature}` → `/commit` |
| **Process review** | `/execution-report {plan}` → `/system-review {plan} {report}` |

---

## Testing Quick Reference

| Command | What it runs |
|---------|-------------|
| `make test` | Unit tests, ~20s |
| `make check` | lint + types + tests (full backend) |
| `make e2e` | Auto-detect changed features, Playwright |
| `make e2e-all` | All 81 e2e tests |
| `make e2e-ui` | Interactive Playwright UI mode |
| `make e2e-headed` | Run with visible browser |
| `/be-validate` | ruff format + check + mypy + pyright + pytest + security lint + conventions |
| `/fe-validate` | TypeScript + ESLint + build + security + design system + i18n + a11y |
| `/be-ship` | validate → review → fix → validate (4-phase gate) |
| `/fe-ship` | validate → review → fix → validate (4-phase gate) |
| `/e2e [feature]` | Playwright via CLI with auto-detection |

---

## Command Summary Table

### Backend (10)
| Command | Purpose | When to Use |
|---------|---------|-------------|
| `/be-init-project` | Bootstrap dev environment | Session start, Docker restart |
| `/be-prime` | Load full backend context | Start of backend work |
| `/be-prime-tools` | Load agent tool context | Before tool development |
| `/be-planning` | Create implementation plan | New features, multi-file changes |
| `/be-create-feature` | Scaffold VSA feature | New feature from scratch |
| `/be-execute` | Execute plan step by step | After planning approval |
| `/be-validate` | Run all quality checks | After any code changes |
| `/be-ship` | Full quality pipeline (validate→review→fix→validate) | Before committing a feature |
| `/be-code-review-fix` | Diagnose and fix any backend issue | Bugs, test failures, type errors |
| `/be-end-to-end-feature` | Autonomous full lifecycle | After trusting each command individually |

### Frontend (9)
| Command | Purpose | When to Use |
|---------|---------|-------------|
| `/fe-prime` | Load full frontend context | Start of frontend work |
| `/fe-planning` | Create frontend plan | New features, multi-file changes |
| `/fe-create-page` | Scaffold Next.js page | Quick page creation |
| `/fe-execute` | Execute frontend plan | After planning approval |
| `/fe-validate` | Run frontend quality checks | After any frontend changes |
| `/fe-ship` | Full quality pipeline (validate→review→fix→validate) | Before committing a feature |
| `/fe-review` | Deep frontend code review | Quality assessment |
| `/fe-code-review-fix` | Diagnose and fix any frontend issue | Bugs, TypeScript errors, design violations |
| `/fe-end-to-end-page` | Autonomous full lifecycle | After trusting each command individually |

### Accelerators (4)
| Command | Purpose | When to Use |
|---------|---------|-------------|
| `/parallel-plan` | Parallel research + test scout + pyright baseline | Replaces `/be-prime` → `/be-planning` |
| `/preflight-check` | Scan plan for fragile patterns (backend) | Before `/be-execute` to prevent fix cycles |
| `/fe-parallel-plan` | Parallel research + test scout + tsc baseline | Replaces `/fe-prime` → `/fe-planning` |
| `/fe-preflight-check` | Scan plan for fragile patterns (frontend) | Before `/fe-execute` to prevent fix cycles |

### Cross-Cutting (10)
| Command | Purpose | When to Use |
|---------|---------|-------------|
| `/review` | Backend code review (8 standards) | Quality assessment |
| `/code-review-fix` | Fix review findings by priority | After `/review` produces report |
| `/rca` | Root cause analysis | Bug investigation |
| `/implement-fix` | Execute RCA fix | After `/rca` documents root cause |
| `/fix-error` | One-pass error resolution | Quick bug fix without separate RCA |
| `/commit` | Conventional commit with safety checks | Final step in every workflow |
| `/update-docs` | Sync documentation | After committing features |
| `/execution-report` | Plan vs reality comparison | After feature implementation |
| `/system-review` | Process improvement | After execution report |
| `/e2e` | Playwright end-to-end tests | Before committing frontend changes |

---

## Output Directories

| Directory | Created by | Contains |
|-----------|-----------|----------|
| `.agents/plans/` | `/be-planning`, `/fe-planning`, `/parallel-plan`, `/fe-parallel-plan` | Active implementation plans |
| `.agents/plans/archive/` | Manual move | Completed/old plans |
| `.agents/code-reviews/` | `/review`, `/fe-review` | Code review reports |
| `.agents/execution-reports/` | `/execution-report` | Plan vs reality comparisons |
| `.agents/system-reviews/` | `/system-review` | Process improvement recommendations |
| `docs/rca/` | `/rca` | Root cause analysis documents |

---

## Trust Progression

Follow this progression before using autonomous commands:

1. **Manual prompts** — Learn what instructions work with Claude for your project
2. **Individual commands** — Run `/be-prime`, `/be-planning`, `/be-execute`, `/be-validate`, `/commit` separately and verify each
3. **Fast path commands** — Use `/parallel-plan` + `/preflight-check` after trusting the standard path
4. **Ship pipeline** — Use `/be-ship` and `/fe-ship` after trusting validate + review individually
5. **Chained commands** — Use `/be-end-to-end-feature` or `/fe-end-to-end-page` only after trusting each individual command
