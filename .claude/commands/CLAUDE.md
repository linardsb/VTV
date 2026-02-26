# VTV Commands

25 slash commands for AI-assisted development workflows (8 backend + 7 frontend + 9 cross-cutting + 1 testing). Run any command by typing `/command-name` in Claude Code.

Every command is designed to produce artifacts that other commands consume. This creates composable pipelines where each step's output feeds the next. Commands work standalone but are most powerful when chained.

## Token-Optimized Architecture

Commands use a deduplication system to minimize context overhead:

- **`.claude/rules/`** — Path-scoped rules auto-load based on files touched (backend, frontend, security, testing). Backend rules don't load during frontend work and vice versa.
- **`.claude/commands/_shared/`** — Shared reference files loaded via `@` references. Content loads once per invocation instead of being duplicated across 3-4 commands:
  - `python-anti-patterns.md` — 59 Python anti-pattern rules (referenced by `/be-execute`, `/be-planning`)
  - `tailwind-token-map.md` — Forbidden → semantic token mappings (referenced by `/fe-execute`, `/fe-planning`, `/fe-validate`, `/fe-end-to-end-page`)
  - `frontend-security.md` — Security grep commands + checklist (referenced by `/fe-execute`, `/fe-planning`, `/fe-validate`, `/fe-end-to-end-page`)
- **Auto-format hook** (`.claude/settings.local.json`) — Runs ruff on `.py` and prettier on `.ts/.tsx` after every Edit/Write, eliminating formatting round-trips.
- **Compaction instructions** (root `CLAUDE.md`) — Tells Claude what to preserve during auto-compaction.

For full workflow documentation with chaining patterns: `.claude/commands/WORKFLOW.md`.

---

## Setup Commands

### `/be-init-project`

**Usage:** `/be-init-project`

Bootstraps the VTV development environment from scratch. Verifies that Python 3.12+, uv, Docker, and Docker Compose are installed and at compatible versions. Starts PostgreSQL and the FastAPI app containers with `docker-compose up -d`, waits for the database to report healthy, then hits `http://localhost:8123/health` to confirm the API is responding. Reports the full status including a link to Swagger UI at `/docs`.

Run this at the start of a new session, after a reboot, or whenever Docker services need restarting. If Docker Desktop isn't running, it tells you to start it first rather than failing silently.

**What it does:**
1. Verifies Python, uv, Docker, and Docker Compose versions
2. Starts PostgreSQL and app containers
3. Confirms both containers are running and DB is healthy
4. Hits `http://localhost:8123/health` to verify the API
5. Reports status and links to Swagger UI at `/docs`

**Produces:** Running Docker services, healthy API endpoint

**Chains with:**
- Run **before** `/be-prime` — prime checks infrastructure state, so services should be up first
- Required **before** any integration tests — `/be-validate` skips integration tests when Docker is down

---

### `/be-create-feature`

**Usage:** `/be-create-feature orders`

Scaffolds a complete vertical slice feature directory with every file defined in `reference/vsa-patterns.md`. Generates the full directory structure — `schemas.py`, `models.py`, `repository.py`, `service.py`, `exceptions.py`, `routes.py`, `tests/`, and `README.md` — all pre-wired with async SQLAlchemy patterns, structured logging setup, type annotations, and proper imports. Automatically wires the router into `app/main.py` with the correct import and `include_router()` call.

The scaffolded code compiles and passes type checkers but contains placeholder fields and stub logic. You fill in the actual domain model, business rules, and test assertions after scaffolding.

**What it creates:**
- `app/{feature}/` with all VSA files using async SQLAlchemy patterns
- `app/{feature}/tests/` with conftest, test stubs for service and routes
- `app/{feature}/README.md` from the feature README template
- Import + `include_router()` line in `app/main.py`

**Produces:** A compilable feature skeleton ready for implementation

**Chains with:**
- Use **instead of** `/be-planning` + `/be-execute` when you want to hand-write the implementation rather than having an agent do it
- Run `/be-validate` **after** to confirm the skeleton passes all quality gates
- Run `/commit` **after** to save the scaffold before filling in business logic

---

## Context Loading Commands

### `/be-prime`

**Usage:** `/be-prime`

Loads the full VTV project context into Claude's working memory for the current session. This is the most important command for starting productive work — without it, Claude lacks understanding of the project's architecture, conventions, current state, and what's already been built.

Reads three core documents via `@` file references: `CLAUDE.md` (architecture and conventions), `reference/PRD.md` (product requirements), and `reference/mvp-tool-designs.md` (agent tool specs). Then actively explores the codebase: analyzes the `app/` directory tree to map implemented features, reads `app/main.py` for registered routers, checks `docker-compose.yml` and `pyproject.toml` for infrastructure config, reviews the last 10 git commits, and probes whether Docker and the API are currently running.

**Output:** A structured summary covering: project identity, tech stack, implemented vs. planned features, infrastructure health (Docker, API, database), current git branch, recent commits, key entry point file paths, and validation commands.

**Produces:** Session-wide project understanding in Claude's context

**Chains with:**
- Run **after** `/be-init-project` if you need services up first
- Run **before** `/be-planning` — planning needs project context to design features correctly
- Run **before** any manual feature work — Claude needs to know what exists and what conventions to follow
- `/be-end-to-end-feature` runs this automatically as Phase 1

---

### `/be-prime-tools`

**Usage:** `/be-prime-tools`

Specialized context loading for AI agent tool development. While `/be-prime` gives broad project understanding, `/be-prime-tools` goes deep on the agent tool system: loads tool specifications from `reference/mvp-tool-designs.md`, inventories which of the 9 planned tools (5 transit + 4 Obsidian) are implemented vs. planned, checks existing tool docstrings against the agent-optimized 5-principle format (selection guidance, composition hints, token efficiency, expectations, examples), reviews dry-run patterns, and inspects error response formats.

Use this when you're about to build, modify, or debug any agent tool. It ensures Claude understands the tool design philosophy — tools are consumed by LLMs, not humans, so their docstrings, parameter design, and error messages must be optimized for machine reasoning.

**Output:** A tool-focused summary covering: tool inventory (implemented/planned), design patterns, workflow chains, docstring standards, and recommended next steps.

**Produces:** Deep agent-tool context in Claude's memory

**Chains with:**
- Run **before** `/be-planning` when the feature is an agent tool — planning will auto-detect tool keywords and add tool-specific sections
- Can replace `/be-prime` if you're only working on tools (though running both gives the fullest context)
- Feeds into the Agent Tool Development workflow: `/be-prime-tools` → `/be-planning` → `/be-execute` → `/be-validate` → `/commit`

---

## Planning Commands

### `/be-planning`

**Usage:** `/be-planning add obsidian search tool`

Researches the codebase and creates a detailed, self-contained implementation plan that another agent (or `/be-execute`) can follow without any additional context. This is the bridge between "what should we build?" and "build it step by step."

The command loads `CLAUDE.md` and `PRD.md` for architecture and product context, then actively explores: reads existing features to learn established patterns, identifies reusable shared utilities (`TimestampMixin`, `PaginationParams`, `get_db()`, `get_logger()`), finds similar features to use as reference (with exact file paths and line ranges), checks for migration conflicts, and reviews `pyproject.toml` for dependency needs.

If the feature involves agent tools (detected by keywords: "tool", "agent", "MCP", "Obsidian", "transit"), it automatically adds tool-specific planning sections covering agent-optimized docstrings, dry-run support, token efficiency, error messages for LLMs, and composition chains.

**Output:** A plan file saved to `.agents/plans/{feature-name}.md` containing:
- Feature metadata, description, and user story
- Solution approach with alternatives considered and rejected (with reasons)
- Relevant files with exact line ranges to read before implementing
- Step-by-step tasks (one file per task) with CREATE/UPDATE/ADD/REMOVE action keywords
- Per-task validation commands so each step can be verified independently
- Testing strategy (unit + integration + edge cases)
- Logging events to emit
- Acceptance criteria and completion checklist
- 5-level validation pyramid (syntax → types → feature tests → full suite → server)

**Key design:** The plan is self-contained — it includes everything needed for execution without referencing the original conversation. This means `/be-execute` can run it in a completely separate session with a fresh Claude instance.

**Produces:** `.agents/plans/{feature-name}.md` — a machine-executable implementation plan

**Chains with:**
- Run `/be-prime` (or `/be-prime-tools` for agent tools) **before** this — planning needs project context
- The plan is consumed **by** `/be-execute` to implement the feature
- After execution, the plan is consumed **by** `/execution-report` to compare plan vs. reality
- After the report, the plan is consumed **by** `/system-review` along with the execution report
- `/be-end-to-end-feature` runs this automatically as Phase 2

---

## Execution Commands

### `/be-execute`

**Usage:** `/be-execute .agents/plans/user-profiles.md`

Takes a plan file (created by `/be-planning`) and implements every step in order, transforming the written specification into working code. Starts with pre-flight checks (plan file exists, tools available), then reads the entire plan to understand the implementation sequence and dependencies between steps.

For each task in the plan, creates or modifies the specified file following VTV conventions: complete type annotations on every function, models inheriting `Base` and `TimestampMixin`, async `select()` queries, structured logging with `get_logger(__name__)`, and Google-style docstrings. Runs database migrations if the plan requires them. Documents any deviations from the plan with explanations.

After all implementation steps, runs the full validation suite (ruff format, ruff check, mypy, pyright, pytest unit tests, and integration tests if Docker is running) with a 3-attempt error recovery loop per check. Also verifies post-implementation requirements: router registered, all functions typed, no type suppressions, correct logging patterns, TimestampMixin on models, tests passing.

**What it checks post-implementation:**
- Router registered in `app/main.py`
- All functions have type annotations
- No type suppressions added
- Logging follows `domain.component.action_state` format
- Models inherit `TimestampMixin`
- Tests exist and pass

**Produces:** Implemented feature code, passing validation suite, deviation notes

**Chains with:**
- **Requires** a plan from `/be-planning` as input (the `$ARGUMENTS` path)
- Run `/be-validate` **after** to double-check everything (execute runs validation internally, but an explicit check confirms)
- Run `/execution-report` **after** to document plan vs. reality
- Run `/commit` **after** to save the work
- `/be-end-to-end-feature` runs this automatically as Phase 3

---

### `/implement-fix`

**Usage:** `/implement-fix 42`

Takes an RCA document (created by `/rca`) and implements the proposed fix. Reads `docs/rca/issue-{id}.md`, applies each code change described in the "Proposed Fix" section, writes regression tests named `test_issue_{id}_{description}()` to prevent the bug from returning, runs migrations if the fix requires schema changes, and validates with the full suite (ruff, mypy, pyright, pytest).

This command is the execution counterpart to `/rca` — where `/rca` investigates and documents, `/implement-fix` applies and verifies. The regression tests it creates are the most important output: they encode the bug's trigger condition so CI will catch any recurrence.

**Prerequisite:** Run `/rca {id}` first to create the RCA document.

**Produces:** Bug fix code, regression tests, suggested commit message in `fix(scope): description (Fixes #{id})` format

**Chains with:**
- **Requires** an RCA document from `/rca` at `docs/rca/issue-{id}.md`
- Run `/be-validate` **after** to confirm the fix doesn't break anything
- Run `/commit` **after** — the command suggests a conventional commit message with `Fixes #{id}`
- Full bug fix chain: `/rca 42` → `/implement-fix 42` → `/be-validate` → `/commit`

---

## Validation & Review Commands

### `/be-validate`

**Usage:** `/be-validate`

Runs all VTV quality checks in sequence against the current codebase and reports a pass/fail scorecard. This is the single command that tells you whether the codebase is in a committable state. Every other command that modifies code runs some form of validation internally, but `/be-validate` is the explicit, standalone check.

Steps run in order — each must pass before the next is reported:

1. **Ruff format** — Auto-fixes formatting issues (tabs, trailing whitespace, line length)
2. **Ruff check** — Linting (style, imports, security, type annotation rules)
3. **MyPy** — Strict mode type checking (catches type errors, missing annotations)
4. **Pyright** — Strict mode type checking (catches issues MyPy misses, different type inference)
5. **Pytest (unit)** — Unit tests (`-m "not integration"`, no Docker required)
6. **Pytest (integration)** — Integration tests (only runs if Docker is running, skipped otherwise)
7. **SDK sync** — Compares live OpenAPI spec against `@vtv/sdk` (only if FastAPI is running, warning only)
8. **Server validation** — Health endpoint check (only if Docker is running, skipped otherwise)

**Output:** A pass/fail scorecard for all 8 checks. Steps 1-5 always run. Steps 6-8 are conditional on Docker/FastAPI being available and are marked SKIPPED (not FAIL) when services are down. Step 7 (SDK sync) is a soft gate — warns but doesn't block commits.

**Produces:** Quality scorecard — the go/no-go signal for committing

**Chains with:**
- Run **after** any code-modifying command: `/be-execute`, `/implement-fix`, `/code-review-fix`, or manual edits
- Run **before** `/commit` — never commit without green validation
- If validation fails, fix the issues and re-run `/be-validate`
- `/be-end-to-end-feature` runs this automatically as Phase 4

---

### `/review`

**Usage:** `/review app/core/` or `/review app/core/health.py`

Performs a deep architectural code review against VTV's 8 quality standards. Unlike `/be-validate` which runs automated tools, `/review` uses Claude's reasoning to catch design issues, missing patterns, and architectural violations that linters can't detect.

Reads every file in the target path and evaluates against:
1. **Type Safety** — Complete annotations, no `Any` without justification, no suppressions
2. **Pydantic Schemas** — Complete request/response models, proper validators
3. **Structured Logging** — Events follow `domain.component.action_state`, started/completed/failed pairs, proper error context
4. **Database Patterns** — Async/await with SQLAlchemy, `select()` style, TimestampMixin, `get_db()`
5. **Architecture** — VSA boundaries, shared utility rules, router registration
6. **Docstrings** — Google-style for regular code, agent-optimized 5-principle format for tool functions
7. **Testing** — Tests exist, integration tests marked, edge cases covered
8. **Security** — No hardcoded secrets, input validation, SQL injection prevention

**Output:** A findings table with file:line references, descriptions, fix suggestions, and priority levels (Critical/High/Medium/Low), plus summary stats.

**Produces:** `.agents/code-reviews/{target-name}-review.md` — a structured review document

**Chains with:**
- Can run **standalone** at any time to assess code quality
- The review document feeds directly into `/code-review-fix` for automated fixing
- Full quality loop: `/review app/core/` → `/code-review-fix .agents/code-reviews/core-review.md` → `/be-validate` → `/commit`

---

### `/code-review-fix`

**Usage:** `/code-review-fix .agents/code-reviews/core-review.md all`

Takes a code review report (created by `/review`) and systematically fixes all identified issues. Reads the review, then works through findings in priority order: Critical issues first, then High, Medium, and Low. For each issue, reads the affected file for full context, applies the fix following VTV conventions, and documents what was changed.

The optional second argument controls scope: `all` (default) fixes everything, `critical` fixes only Critical issues, `high` fixes Critical + High. This lets you do targeted fixes when you don't want to address every finding.

After all fixes, runs the full validation suite (ruff, mypy, pyright, pytest) with a 3-attempt recovery loop per check to ensure fixes didn't introduce regressions.

**Output:** List of issues fixed (with file:line and what changed), issues skipped (with reasons), and validation scorecard.

**Produces:** Fixed code, validation results

**Chains with:**
- **Requires** a review document from `/review` as input
- Run `/be-validate` **after** to double-check (the command runs validation internally, but explicit confirmation is good practice)
- Run `/commit` **after** to save the fixes
- Full quality loop: `/review` → `/code-review-fix` → `/be-validate` → `/commit`

---

## Git Commands

### `/commit`

**Usage:** `/commit` or `/commit app/core/health.py app/core/middleware.py`

Reviews all changes (or specific files if provided), performs safety checks, stages files explicitly, and creates a conventional commit. This is the final step in every workflow — it captures the work with a well-formatted message.

Safety checks scan for secrets: `.env`, `*.pem`, `*.key`, `credentials.*`, `secrets.*`. If any are detected, the command stops and warns you before proceeding. Files are always staged explicitly by name (never `git add -A` or `git add .`) to prevent accidental inclusion of generated files or secrets.

The commit message follows conventional commit format with VTV-specific scopes. The command reviews the diff, recent commit history (to match the repo's style), and drafts the message. Does NOT push automatically — you push with `git push` when ready.

**Commit format:**
```
type(scope): short description

Optional body explaining WHY.

Co-Authored-By: Claude <noreply@anthropic.com>
```

**Types:** `feat`, `fix`, `refactor`, `test`, `docs`, `chore`, `ci`, `style`
**VTV Scopes:** `core`, `shared`, `agent`, `transit`, `obsidian`, `config`, `db`, `health`, `cms`, or feature name

**Produces:** A git commit (local only, not pushed)

**Chains with:**
- Run **after** `/be-validate` — never commit with failing checks
- Run **after** `/be-execute`, `/implement-fix`, `/code-review-fix`, or any code changes
- The final step in every workflow chain
- `/be-end-to-end-feature` runs this automatically as Phase 6

---

## Documentation Commands

### `/update-docs`

**Usage:** `/update-docs agents` or `/update-docs .agents/execution-reports/agents.md`

Updates all living project documentation to reflect a newly implemented feature. This is the documentation feedback loop — after a feature is built, validated, and committed, the docs still reflect the old state. This command reads the actual implementation and updates everything: CLAUDE.md project structure, the feature README (replacing scaffold placeholders with real content), PRD feature status, and bug logs in execution reports.

The command accepts either a feature name or a path to an execution report. It resolves the feature directory at `app/{feature}/`, scans the actual code to extract endpoints, models, schemas, and business rules, then systematically updates each documentation file. Only sections that actually need changes are modified.

**What it updates:**

1. **Locates artifacts** — Finds execution report, plan, or falls back to scanning code and git history
2. **Scans implementation** — Reads routes, models, schemas, service, exceptions for concrete details
3. **`CLAUDE.md` project structure** — Adds new feature to the ASCII tree, updates shared utilities and config sections
4. **`app/{feature}/README.md`** — Replaces scaffold placeholders with real endpoints, schemas, business rules, and database columns
5. **`reference/PRD.md`** — Updates feature status from planned to implemented (if the feature is listed)
6. **Execution report bugs** — Appends a "Bugs Found During Implementation" section documenting validation failures and fixes
7. **Summary diff** — Shows what changed in each file for user review

**Prerequisite:** Feature must be fully implemented, validated, and committed. Run after `/be-validate` + `/commit`.

**Produces:** Updated documentation across multiple files, summary of changes

**Chains with:**
- Run **after** `/be-validate` + `/commit` — docs should reflect committed, working code
- Run `/commit` **after** this to commit the documentation updates
- Optional follow-up after `/be-end-to-end-feature`
- Full feature documentation chain: `/be-execute` → `/be-validate` → `/commit` → `/update-docs` → `/commit`

---

## Investigation Commands

### `/rca`

**Usage:** `/rca 42`

Performs systematic root cause analysis for a bug. Loads issue details from GitHub (via `gh issue view`) if a numeric ID is provided, or works from the user's description if context is given inline. Then methodically investigates the VTV codebase layer by layer: routes for endpoint issues, services for business logic edge cases, models for constraint violations, schemas for validation gaps, middleware for cross-cutting problems, and config for environment issues.

Also checks structured log patterns for `_failed` events related to the issue, reviews exception handlers in `app/core/exceptions.py`, examines alembic migration history for data-related bugs, and uses git blame to trace when the issue was introduced.

The investigation produces a structured RCA document with the root cause pinpointed to a specific file:line, categorized by type (validation gap, logic error, race condition, missing constraint, config issue, etc.), with evidence and a concrete proposed fix including exact file changes, required tests, and validation steps.

**Output:** An RCA document saved to `docs/rca/issue-{id}.md` containing: summary, symptoms, root cause location and category, evidence, proposed fix with exact file changes, required regression tests, validation steps, and impact assessment.

**Produces:** `docs/rca/issue-{id}.md` — a machine-executable investigation document

**Chains with:**
- Can run **standalone** to investigate any bug
- The RCA document feeds directly into `/implement-fix` for automated fixing
- Full bug fix chain: `/rca 42` → `/implement-fix 42` → `/be-validate` → `/commit`
- The RCA document also serves as permanent documentation of what went wrong and why

---

## Process Improvement Commands

### `/execution-report`

**Usage:** `/execution-report .agents/plans/user-auth.md`

Post-execution reflection that compares what was actually implemented against what was planned. This is the quality feedback loop — it catches divergences, documents what worked, and identifies what needs improvement.

Reads the plan file, then analyzes what actually happened: checks git diff to see real changes, compares files created/modified against the plan's task list, runs validation tools to capture current quality state, and identifies every divergence between plan and implementation. Classifies each divergence by type (better approach discovered, plan gap, security concern, performance optimization).

**Output:** A report saved to `.agents/execution-reports/{feature-name}.md` containing: files changed, validation results (ruff, mypy, pyright, pytest), what went well, challenges encountered, divergence table (planned vs. actual with reasons), skipped items, and recommendations for improving the planning and execution process.

**Produces:** `.agents/execution-reports/{feature-name}.md` — a retrospective document

**Chains with:**
- **Requires** a plan from `/be-planning` as input
- Run **after** `/be-execute` (or `/be-end-to-end-feature`) — needs both plan and implementation to compare
- The execution report feeds into `/system-review` along with the original plan
- Process improvement chain: `/be-execute` → `/execution-report` → `/system-review`
- `/be-end-to-end-feature` runs this automatically as Phase 5

---

### `/system-review`

**Usage:** `/system-review .agents/plans/auth.md .agents/execution-reports/auth.md`

Meta-level process improvement — finds bugs in the PROCESS, not the code. Reads both the original plan and the execution report, then analyzes the development process itself: classifies each divergence as justified (plan was wrong, better pattern discovered, security/performance concern) or problematic (ignored constraints, took shortcuts, misunderstood requirements).

For each problematic divergence, traces the root cause to a specific process failure: unclear plan instructions → update `/be-planning` template; missing context → update `/be-prime` or `/be-prime-tools`; missing validation → update `/be-validate`; manual step repeated → create new command. Generates specific, actionable improvements to CLAUDE.md, command files, or development processes.

**Output:** A review saved to `.agents/system-reviews/{feature-name}-review.md` containing:
- Alignment score (1-10) measuring plan-to-implementation fidelity
- Divergence analysis with root cause classification
- Pattern compliance checklist (type safety, logging, VSA, testing, docstrings)
- Recommended actions (specific text to add/change in CLAUDE.md or commands)
- Key learnings to carry forward

**Produces:** `.agents/system-reviews/{feature-name}-review.md` — process improvement recommendations

**Chains with:**
- **Requires** both a plan from `/be-planning` AND an execution report from `/execution-report`
- The final step in the process improvement chain: `/be-planning` → `/be-execute` → `/execution-report` → `/system-review`
- Recommendations may lead to manual edits of CLAUDE.md, command files, or creation of new commands
- Run **periodically** after feature work to continuously improve the development process

---

## Autonomous Commands

### `/be-end-to-end-feature`

**Usage:** `/be-end-to-end-feature add health dashboard`

Runs the complete feature development lifecycle autonomously in 6 phases, combining `/be-prime` → `/be-planning` → `/be-execute` → `/be-validate` → `/execution-report` → `/commit` into a single command. Each phase must complete successfully before the next begins — if any phase fails after 3 recovery attempts, the entire pipeline stops and reports what went wrong.

**Phase breakdown:**

1. **Prime** — Loads project context via `@CLAUDE.md` and `@reference/PRD.md`. Checks git state and Docker. Auto-detects agent tool features (keywords: tool, agent, MCP, Obsidian, transit) and loads additional tool context if detected.
2. **Plan** — Designs the vertical slice, identifies shared utilities to reuse, plans migrations, defines logging events. Saves plan to `.agents/plans/`. Plan must be detailed enough for another agent to execute.
3. **Execute** — Implements every file with type annotations, async patterns, structured logging, docstrings. Registers router in `app/main.py`, runs migrations if needed.
4. **Validate** — Runs all checks (ruff format, ruff check, mypy, pyright, pytest unit, pytest integration if Docker running). Fixes any failures with max 3 attempts per check. Stops entire pipeline if validation can't be fixed.
5. **Execution Report** — Compares implementation vs plan, documents divergences. Saves to `.agents/execution-reports/`.
6. **Commit** — Stages files explicitly (never `git add .`), creates conventional commit with `Co-Authored-By`.

**Output:** Full summary with files created/modified, validation scorecard, commit hash, and paths to all generated artifacts (plan, execution report).

**Trust level:** Only use this after you've run each individual command (`/be-prime`, `/be-planning`, `/be-execute`, `/be-validate`, `/commit`) separately and verified their output. See Trust Progression below.

**Produces:** Complete implemented feature, plan, execution report, and git commit

**Chains with:**
- Run **standalone** — this IS the full chain
- Optionally run `/system-review` **after** for process improvement insights
- Optionally run `/review` **after** for an additional architectural review of the generated code

---

## Frontend Commands

Frontend commands mirror the backend pipeline but use pnpm/TypeScript/Next.js tooling instead of uv/Python/FastAPI. They integrate with the VTV design system (`cms/design-system/vtv/MASTER.md`) and the ui-ux-pro-max skill for visual design guidance.

### `/fe-prime`

**Usage:** `/fe-prime`

Loads the full VTV frontend context into Claude's working memory. Reads the design system master document, inventories all installed shadcn/ui components, maps all existing pages and their routes, checks i18n coverage across both languages, reviews RBAC middleware configuration, and reports the current SDK generation state.

**Output:** A structured summary covering: pages built vs planned, components available, design system rules, RBAC route mapping, i18n key coverage, and validation commands.

**Produces:** Session-wide frontend understanding in Claude's context

**Chains with:**
- Run **before** `/fe-planning` — planning needs frontend context
- Run **before** any manual frontend work
- Frontend equivalent of `/be-prime`

---

### `/fe-planning`

**Usage:** `/fe-planning add routes management page`

Researches the frontend codebase and creates a self-contained implementation plan that `/fe-execute` can follow. Loads the design system (MASTER.md + page overrides), identifies needed components (existing shadcn/ui vs new), plans i18n keys for both languages, designs RBAC integration, and specifies sidebar navigation entry.

**Output:** A plan file saved to `.agents/plans/fe-{page-name}.md` containing: page metadata, design system rules, components needed, i18n keys, data fetching strategy, RBAC configuration, step-by-step tasks with per-task validation using `pnpm type-check/lint/build`, and post-implementation checks.

**Produces:** `.agents/plans/fe-{page-name}.md` — a machine-executable frontend plan

**Chains with:**
- Run `/fe-prime` **before** this — planning needs frontend context
- The plan is consumed **by** `/fe-execute`
- Frontend equivalent of `/be-planning`

---

### `/fe-create-page`

**Usage:** `/fe-create-page routes`

Scaffolds a new Next.js page with all required integrations: creates the page component with server-side rendering and i18n support, adds translation keys to both `lv.json` and `en.json`, adds a sidebar navigation entry, and updates the RBAC middleware matcher. The scaffolded page uses semantic design tokens and follows established patterns from the dashboard page.

**What it creates:**
- `cms/apps/web/src/app/[locale]/(dashboard)/{page}/page.tsx` — Server component with i18n
- i18n keys in both language files
- Sidebar nav link in locale layout
- Middleware route matcher with role permissions

**Produces:** A minimal placeholder page ready for implementation

**Chains with:**
- Use **instead of** `/fe-planning` + `/fe-execute` for quick scaffolding
- Run `/fe-validate` **after** to verify quality gates
- Frontend equivalent of `/be-create-feature`

---

### `/fe-execute`

**Usage:** `/fe-execute .agents/plans/fe-routes.md`

Takes a frontend plan file (created by `/fe-planning`) and implements every step in order. Starts with pre-flight checks (Node.js, pnpm, plan file), reads the entire plan, then implements each task following VTV frontend conventions: semantic design tokens, next-intl translations, server components by default, shadcn/ui components, and proper TypeScript types.

Runs per-task TypeScript validation after each file, then the full frontend validation suite (type-check, lint, build) with 3-attempt error recovery. Includes a design system compliance scan that checks for hardcoded colors and verifies semantic token usage.

**Produces:** Implemented frontend feature, passing validation suite

**Chains with:**
- **Requires** a plan from `/fe-planning` as input
- Run `/fe-validate` **after** for full quality check
- Run `/commit` **after** to save the work
- Frontend equivalent of `/be-execute`

---

### `/fe-validate`

**Usage:** `/fe-validate`

Runs all VTV frontend quality checks in sequence. Three hard gates (must pass): TypeScript type check, lint, and Next.js build. Three soft gates (warnings): design system compliance (no hardcoded colors), i18n completeness (matching keys across languages), and accessibility spot-check (alt text, ARIA labels, form labels).

**Output:** A pass/fail scorecard for all 6 checks with specific error locations for failures.

**Produces:** Quality scorecard — the go/no-go signal for committing frontend changes

**Chains with:**
- Run **after** `/fe-execute` or any frontend code changes
- Run **before** `/commit` — never commit with failing hard gates
- Frontend equivalent of `/be-validate`

---

### `/fe-review`

**Usage:** `/fe-review cms/apps/web/src/app/[locale]/(dashboard)/routes/`

Performs a deep architectural code review against VTV's 8 frontend quality standards. Unlike `/fe-validate` which runs automated tools, `/fe-review` uses Claude's reasoning to catch design issues, missing patterns, and architectural violations that linters can't detect.

Reads every file in the target path and evaluates against:
1. **TypeScript Quality** — Complete types, no `any` without justification, correct server/client boundaries
2. **Design System Compliance** — Semantic tokens used, no hardcoded colors, spacing/typography follow MASTER.md
3. **Component Patterns** — shadcn/ui used correctly, CVA for variants, `cn()` for class merging, appropriate decomposition
4. **Internationalization** — All user-visible text uses `useTranslations`, keys match in both languages, no hardcoded strings
5. **Accessibility** — Alt text, ARIA labels, form labels, focus indicators, color contrast
6. **RBAC & Auth** — Routes protected in middleware, role-based UI gating, unauthorized redirect
7. **Data Fetching & Performance** — Server components for data, Suspense boundaries, no unnecessary `'use client'`
8. **Security** — No hardcoded secrets, XSS prevention, `rel="noopener noreferrer"` on external links

**Output:** A findings table with file:line references, descriptions, fix suggestions, and priority levels (Critical/High/Medium/Low), plus summary stats.

**Produces:** `.agents/code-reviews/fe-{target-name}-review.md` — a structured frontend review document

**Chains with:**
- Can run **standalone** at any time to assess frontend code quality
- The review document feeds directly into `/code-review-fix` for automated fixing
- Full frontend quality loop: `/fe-review cms/apps/web/src/` → `/code-review-fix .agents/code-reviews/fe-web-review.md` → `/fe-validate` → `/commit`
- Frontend equivalent of `/review`

---

### `/fe-end-to-end-page`

**Usage:** `/fe-end-to-end-page add routes management page`

Runs the complete frontend page development lifecycle autonomously in 6 phases, combining `/fe-prime` → `/fe-planning` → `/fe-execute` → `/fe-validate` → execution report → `/commit` into a single command. Each phase must complete successfully before the next begins — if any phase fails after 3 recovery attempts, the entire pipeline stops and reports what went wrong.

**Phase breakdown:**

1. **Prime** — Loads frontend context via `@CLAUDE.md` and `@cms/design-system/vtv/MASTER.md`. Inventories components, pages, i18n, RBAC, and SDK state.
2. **Plan** — Designs the page, identifies components, plans i18n keys, RBAC integration, sidebar nav entry. Saves plan to `.agents/plans/fe-{page-name}.md` (400-600 lines).
3. **Execute** — Implements every file with semantic tokens, i18n, server components, shadcn/ui, TypeScript types, accessibility. Updates middleware and sidebar nav.
4. **Validate** — Runs all checks (type-check, lint, build as hard gates; design system, i18n, a11y as soft gates). Fixes any failures with max 3 attempts per check. Stops entire pipeline if hard gates can't be fixed.
5. **Execution Report** — Compares implementation vs plan, documents divergences. Saves to `.agents/execution-reports/fe-{page-name}.md`.
6. **Commit** — Stages files explicitly (never `git add .`), creates conventional commit with `Co-Authored-By`.

**Output:** Full summary with files created/modified, validation scorecard, commit hash, and paths to all generated artifacts.

**Trust level:** Only use this after you've run each individual frontend command (`/fe-prime`, `/fe-planning`, `/fe-execute`, `/fe-validate`, `/commit`) separately and verified their output. See Trust Progression below.

**Produces:** Complete implemented page, plan, execution report, and git commit

**Chains with:**
- Run **standalone** — this IS the full frontend chain
- Optionally run `/fe-review` **after** for an additional architectural review
- Optionally run `/system-review` **after** for process improvement insights
- Frontend equivalent of `/be-end-to-end-feature`

---

## Testing Commands

### `/e2e`

**Usage:** `/e2e` or `/e2e routes` or `/e2e "dashboard loads"`

Runs Playwright end-to-end tests for the VTV frontend using the CLI (not MCP). When called without arguments, auto-detects which features have changed files (via `e2e/detect-changed.sh` + git diff) and runs only the relevant test files. When called with a feature name, runs that specific test file. When called with a quoted string, matches tests by title.

Requires backend (port 8123) and frontend (port 3000) to be running. The Playwright config auto-starts the frontend dev server if not already running, but the backend must be started manually (`make dev-be` or `make dev`).

**Test projects:**
- **setup** — Authenticates via login page, saves session state for reuse
- **chromium** — Authenticated tests (depends on setup), uses saved session
- **no-auth** — Unauthenticated tests (login page, redirects), no stored session

**Auto-detection mapping:**
- `components/routes/*` → `routes.spec.ts`
- `components/stops/*` → `stops.spec.ts`
- `components/schedules/*` → `schedules.spec.ts`
- `components/documents/*` → `documents.spec.ts`
- `components/dashboard/*` → `dashboard.spec.ts`
- `app-sidebar*`, `middleware.ts` → `navigation.spec.ts`
- `auth.ts`, `login/*` → `login.noauth.spec.ts`
- Shared code (`ui/*`, `lib/*`, `hooks/*`, `messages/*`) → ALL tests

**Produces:** Pass/fail test results, HTML report viewable via `npx playwright show-report`

**Chains with:**
- Run **after** `/fe-validate` — e2e tests verify the app works in a real browser
- Run **before** `/commit` — don't commit if browser tests fail
- Use `/Browser` skill for visual debugging of test failures
- Frontend workflow: `/fe-execute` → `/fe-validate` → `/e2e` → `/commit`

---

## Workflows

### Feature Development (manual steps)
```
/be-prime                                              # Load project context
/be-planning add user authentication                   # Create the plan
/be-execute .agents/plans/user-authentication.md       # Implement it
/be-validate                                           # Verify everything passes
/execution-report .agents/plans/user-authentication.md  # Document what happened
/commit                                             # Commit with conventional format
/update-docs user-authentication                    # Update all living documentation
```

### Feature Development (autonomous)
```
/be-end-to-end-feature add user authentication
```

### New Feature Scaffolding
```
/be-create-feature orders                    # Generate VSA skeleton
# Fill in schemas, models, business logic
/be-validate                                 # Verify checks pass
/commit                                   # Commit the feature
```

### Bug Fix
```
/rca 42                    # Investigate and document root cause
/implement-fix 42          # Fix from the RCA document
/be-validate                  # Verify the fix
/commit                    # Commit with "Fixes #42"
```

### Agent Tool Development
```
/be-prime-tools                                        # Load tool designs and patterns
/be-planning add obsidian search tool                  # Plan with tool-specific sections
/be-execute .agents/plans/obsidian-search-tool.md      # Implement with agent-optimized docstrings
/be-validate                                           # Verify all checks pass
/commit                                             # Commit
```

### Code Quality Loop
```
/review app/core/                                               # Review, save to .agents/code-reviews/
/code-review-fix .agents/code-reviews/core-review.md            # Fix issues
/be-validate                                                       # Verify
/commit                                                         # Commit
```

### Process Improvement (after feature work)
```
/execution-report .agents/plans/feature.md                      # Document what happened
/system-review .agents/plans/feature.md .agents/execution-reports/feature.md
# Apply recommended improvements manually
```

### Frontend Quality Loop
```
/fe-review cms/apps/web/src/app/[locale]/(dashboard)/routes/    # Review frontend code
/code-review-fix .agents/code-reviews/fe-routes-review.md       # Fix issues
/fe-validate                                                    # Verify
/commit                                                         # Commit
```

### Quick Check
```
/be-validate        # Run all backend linting, type checking, tests, and SDK sync
/fe-validate     # Run all frontend quality checks
/e2e             # Auto-detect changed features, run browser tests
/review app/     # Review backend code against VTV standards
/fe-review cms/apps/web/src/  # Review frontend code against VTV standards
```

### Frontend Page Development (manual steps)
```
/fe-prime                                       # Load frontend context
/fe-planning add routes management page         # Create the plan
/fe-execute .agents/plans/fe-routes.md          # Implement it
/fe-validate                                    # Verify everything passes
/e2e routes                                     # Browser tests for the feature
/commit                                         # Commit with conventional format
```

### Frontend Page Development (autonomous)
```
/fe-end-to-end-page add routes management page
```

### Quick Frontend Page Scaffolding
```
/fe-create-page routes                          # Generate page skeleton
# Fill in content, components, data fetching
/fe-validate                                    # Verify checks pass
/commit                                         # Commit the page
```

## Command Dependency Graph

### Backend Pipeline
```
/be-init-project ──→ /be-prime ──→ /be-planning ──→ /be-execute ──→ /be-validate ──→ /commit ──→ /update-docs
                  /be-prime-tools ─┘               │            │
                                                ├──→ /execution-report ──→ /system-review
                                                │
/rca ──→ /implement-fix ──→ /be-validate ──→ /commit

/review ──→ /code-review-fix ──→ /be-validate ──→ /commit

/be-create-feature ──→ (manual implementation) ──→ /be-validate ──→ /commit ──→ /update-docs

/be-end-to-end-feature = /be-prime + /be-planning + /be-execute + /be-validate + /execution-report + /commit
                      (optional follow-up: /update-docs)
```

### Frontend Pipeline
```
/fe-prime ──→ /fe-planning ──→ /fe-execute ──→ /fe-validate ──→ /e2e ──→ /commit
                                    │                │
               /fe-create-page ─────┘                ├──→ /execution-report ──→ /system-review
                                                     │
/fe-review ──→ /code-review-fix ──→ /fe-validate ──→ /e2e ──→ /commit

/fe-end-to-end-page = /fe-prime + /fe-planning + /fe-execute + /fe-validate + /execution-report + /commit
```

## Output Directories

- `.agents/plans/` — Implementation plans created by `/be-planning` and `/fe-planning`
- `.agents/code-reviews/` — Code review reports created by `/review` and `/fe-review`
- `.agents/execution-reports/` — Execution reports created by `/execution-report`
- `.agents/system-reviews/` — System reviews created by `/system-review`
- `docs/rca/` — Root cause analysis documents created by `/rca`

## Trust Progression

Follow this progression before using autonomous commands:

1. **Manual prompts** — Learn what instructions work
2. **Individual commands** — Run `/be-prime`, `/be-planning`, `/be-execute`, `/commit` (or frontend equivalents) separately and verify each
3. **Chained commands** — Use `/be-end-to-end-feature` or `/fe-end-to-end-page` only after trusting each individual command


<claude-mem-context>
# Recent Activity

<!-- This section is auto-generated by claude-mem. Edit content outside the tags. -->

### Feb 18, 2026

| ID | Time | T | Title | Read |
|----|------|---|-------|------|
| #15703 | 1:41 PM | ✅ | Added 5 new Python anti-patterns from DDoS defense implementation learnings | ~475 |
| #15409 | 6:03 AM | ✅ | Frontend Planning Command Enhanced with Prop API Verification Step | ~402 |
| #15408 | " | 🔵 | Frontend Planning Command Documentation | ~510 |

### Feb 26, 2026

| ID | Time | T | Title | Read |
|----|------|---|-------|------|
| #17522 | 1:21 PM | 🔵 | VTV Slash Command System Architecture Documented | ~1163 |
| #17521 | " | 🔵 | Comprehensive Assessment of Existing PAI and VTV Cognitive Infrastructure | ~834 |
</claude-mem-context>