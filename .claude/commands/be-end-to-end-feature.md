---
description: Autonomously develop a complete feature through all 6 phases (prime, plan, execute, validate, report, commit)
argument-hint: [feature-description] e.g. add health dashboard
allowed-tools: Read, Write, Edit, Bash(uv run ruff:*), Bash(uv run mypy:*), Bash(uv run pyright:*), Bash(uv run pytest:*), Bash(uv run alembic:*), Bash(git:*)
---

Run the complete feature lifecycle autonomously: prime → plan → execute → validate → commit.

@reference/PRD.md

# End-to-End Feature — Full Autonomous Feature Lifecycle

## INPUT

**Feature request:** $ARGUMENTS

You will autonomously develop this feature from research through commit. Follow each phase completely before moving to the next.

## PROCESS

### Phase 1: Prime

```
!git status
!docker-compose ps 2>/dev/null || echo "Docker not running"
```

Load project understanding. Architecture and product context are loaded via `@` references above. **Detect if this is an agent tool feature** (keywords: tool, agent, MCP, Obsidian tool, transit tool).

**If agent tool feature:**
- Load tool context: read `reference/mvp-tool-designs.md`, `reference/PRD.md` (agent sections), `CLAUDE.md` (tool docstrings section)
- Inventory existing tool implementations in `app/`
- Check tool design patterns (docstrings, dry-run, error formats)
- Follow agent tool planning requirements in Phase 2

**For all features:**
- Explore `app/` directory structure to understand existing features
- Read `app/main.py` for current router registrations
- Check existing shared utilities in `app/shared/`

### Phase 2: Plan

Create a detailed implementation plan:

- Design the vertical slice: models, schemas, routes, service, tests
- Identify shared utilities to reuse (TimestampMixin, PaginationParams, get_db(), get_logger())
- Plan database migrations if needed
- Define structured logging events (`feature.action_state`)
- Save plan to `.agents/plans/[feature-name].md`
- Plan must be detailed enough for another agent to execute

### Phase 3: Execute

Implement the plan step by step:

- Create all feature files following VTV conventions
- Complete type annotations on every function
- Models inherit `Base` and `TimestampMixin`
- Use `select()` for queries, `get_db()` for sessions
- Structured logging with `get_logger(__name__)`
- Google-style docstrings on all functions
- Update schemas MUST have `model_validator(mode="before")` to reject empty PATCH/PUT bodies
- Constrained string fields MUST use `Literal[...]` types, not bare `str`
- **Every route endpoint MUST have `get_current_user` or `require_role()` dependency** — the `TestAllEndpointsRequireAuth` convention test auto-discovers all routes and fails CI if auth is missing
- Register router in `app/main.py`
- Run migrations if needed:
  ```bash
  uv run alembic revision --autogenerate -m "[description]"
  uv run alembic upgrade head
  ```

### Phase 4: Validate

ALL must pass before proceeding to commit:

```bash
uv run ruff format .
```

```bash
uv run ruff check .
```

```bash
uv run mypy app/
```

```bash
uv run pyright app/
```

```bash
uv run pytest -v -m "not integration"
```

**Integration tests (if Docker is running):**

```bash
docker-compose ps 2>/dev/null && uv run pytest -v -m integration || echo "Skipped — Docker not running"
```

**Security gate (explicit - must pass):**

```bash
uv run pytest app/tests/test_security.py -v --tb=short
```

Verify all security convention tests pass. If this feature added new endpoints, `TestAllEndpointsRequireAuth` will catch missing auth dependencies. If new SDLC tooling was modified, `TestSDLCSecurityGates` will catch broken gates.

Fix any failures before moving on. Do not proceed to commit with failing checks.

**Error recovery rules:**
- **CRITICAL: After ANY code edit to fix a validation error, re-run from Level 1 (ruff format + ruff check --fix).** Code changes to fix type errors frequently introduce import sorting or lint regressions.
- If a check fails, attempt to fix the issue, then re-run ALL checks from Level 1
- Security test failures are treated as hard failures - do NOT proceed to Phase 5
- Maximum 3 fix attempts per check
- If still failing after 3 attempts: STOP the entire pipeline and report to the user
  - Do NOT proceed to Phase 5 (Execution Report)
  - Report: which phase failed, what was attempted, exact errors

### Phase 5: Execution Report

Generate a brief execution report comparing implementation vs plan.
Save to `.agents/execution-reports/[feature-name].md`.
Note any divergences and their reasons.

### Phase 6: Commit

Stage and commit with conventional format:

- Stage all new and modified files explicitly (not `git add .`)
- Use conventional commit: `feat([scope]): [description]`
- Include `Co-Authored-By: Claude <noreply@anthropic.com>`

## OUTPUT

Present a final summary:

**Feature:** [name]
**Plan:** `.agents/plans/[feature-name].md`

**Files Created:**
- [list with paths]

**Files Modified:**
- [list with paths]

**Validation Results:**
- Ruff format: PASS
- Ruff check: PASS
- MyPy: PASS
- Pyright: PASS
- Pytest: PASS ([X] tests, [Y] new)

**Commit:** `[hash]` — `[commit message]`

**Optional follow-ups:**
- Update documentation: `/update-docs [feature-name]`
- Process improvement: `/system-review .agents/plans/[feature-name].md .agents/execution-reports/[feature-name].md`
