# VTV Slash Commands & Workflows

---

## Backend Commands (16)

| Command                        | Purpose                                                                  |
|--------------------------------|--------------------------------------------------------------------------|
| `/be-init-project`             | Validate dev environment (Python, Docker, deps, DB connection)           |
| `/be-prime`                    | Load full project context into session (architecture, features, state)   |
| `/be-prime-tools`              | Load AI agent tool designs and patterns specifically                     |
| `/be-create-feature {name}`    | Scaffold a new vertical slice directory with all VSA files               |
| `/be-planning`                 | Research codebase, produce a self-contained implementation plan file     |
| `/be-execute {plan-file}`      | Execute a plan file step-by-step with validation pyramid                 |
| `/be-validate`                 | Run ALL quality checks: ruff format + ruff check + mypy + pyright + pytest |
| `/review`                      | Code review against 8 VTV quality standards                              |
| `/code-review-fix {report}`    | Fix issues found in a code review report                                 |
| `/commit`                      | Stage files + create conventional commit with safety checks              |
| `/rca {issue}`                 | Investigate a bug, produce root cause analysis document                  |
| `/implement-fix {rca-file}`    | Apply a fix from an RCA document with regression tests                   |
| `/execution-report`            | Compare implementation outcomes against the plan                         |
| `/system-review`               | Analyze implementation vs plan for process improvements                  |
| `/update-docs`                 | Update CLAUDE.md, PRD, etc. after feature is committed                   |
| `/be-end-to-end-feature`       | Full autonomous pipeline: prime → plan → execute → validate → report → commit |

---

## Frontend Commands (7)

| Command                        | Purpose                                                                  |
|--------------------------------|--------------------------------------------------------------------------|
| `/fe-prime`                    | Load frontend context (design system, components, i18n, RBAC)            |
| `/fe-planning`                 | Research frontend codebase, create page/feature implementation plan       |
| `/fe-create-page {name}`       | Scaffold Next.js page with i18n, RBAC, sidebar nav, design tokens        |
| `/fe-execute {plan-file}`      | Execute a frontend plan step-by-step                                     |
| `/fe-validate`                 | TypeScript + ESLint + build + design system + i18n + a11y checks         |
| `/fe-review`                   | Review frontend code against 8 VTV frontend quality standards            |
| `/fe-end-to-end-page`          | Full autonomous pipeline for frontend pages                              |

---

## Testing Command (1)

| Command                        | Purpose                                                                  |
|--------------------------------|--------------------------------------------------------------------------|
| `/e2e`                         | Run Playwright e2e tests — auto-detects changed features or runs specific test |

---

## Quick Reference — Which Command When?

| Situation              | Commands                                                                          |
|------------------------|-----------------------------------------------------------------------------------|
| **New feature**        | `/be-prime` → `/be-planning` → `/be-execute` → `/be-validate` → `/commit`        |
| **Bug report**         | `/rca` → `/implement-fix` → `/be-validate` → `/commit`                           |
| **Code review**        | `/review` → `/code-review-fix` → `/be-validate` → `/commit`                      |
| **Quick fix**          | Edit directly → `/be-validate` → `/commit`                                       |
| **New page**           | `/fe-prime` → `/fe-planning` → `/fe-execute` → `/fe-validate` → `/e2e` → `/commit` |
| **Full auto (BE)**     | `/be-end-to-end-feature {description}`                                            |
| **Full auto (FE)**     | `/fe-end-to-end-page {description}`                                               |
| **Just validate**      | `/be-validate` (backend) or `/fe-validate` (frontend)                             |
| **Just test e2e**      | `/e2e` or `make e2e`                                                              |

---

## Command Chaining Workflows

### New Backend Feature (standard)

```
/be-prime → /be-planning → /be-execute {plan} → /be-validate → /commit
```

| Step | Command                                        | What it does                         |
|------|------------------------------------------------|--------------------------------------|
| 1    | `/be-prime`                                    | Load project context                 |
| 2    | `/be-planning add brute force tracking`        | Creates `.agents/plans/brute-force.md` |
| 3    | `/be-execute .agents/plans/brute-force.md`     | Implements step-by-step              |
| 4    | `/be-validate`                                 | Runs all checks (612+ tests)         |
| 5    | `/commit`                                      | Conventional commit                  |

### New Backend Feature (fully autonomous)

```
/be-end-to-end-feature add password complexity validation
```

Runs all 6 phases automatically without manual chaining.

---

### New Frontend Page (standard)

```
/fe-prime → /fe-planning → /fe-execute {plan} → /fe-validate → /e2e → /commit
```

| Step | Command                                        | What it does                         |
|------|------------------------------------------------|--------------------------------------|
| 1    | `/fe-prime`                                    | Load frontend context                |
| 2    | `/fe-planning create vehicle management page`  | Creates `.agents/plans/vehicles-page.md` |
| 3    | `/fe-execute .agents/plans/vehicles-page.md`   | Implements step-by-step              |
| 4    | `/fe-validate`                                 | TS + lint + build + tokens           |
| 5    | `/e2e`                                         | Playwright tests                     |
| 6    | `/commit`                                      | Conventional commit                  |

### New Frontend Page (fully autonomous)

```
/fe-end-to-end-page create analytics dashboard
```

---

### Full-Stack Feature

Backend first (API endpoints), then frontend (UI consuming those endpoints):

| Phase    | Chain                                                                             |
|----------|-----------------------------------------------------------------------------------|
| Backend  | `/be-prime` → `/be-planning` → `/be-execute` → `/be-validate` → `/commit`        |
| Frontend | `/fe-prime` → `/fe-planning` → `/fe-execute` → `/fe-validate` → `/e2e` → `/commit` |

---

## Bug Fixing Workflow

### Investigation → Fix → Verify

```
/rca → /implement-fix → /be-validate → /commit
```

| Step | Command                                        | What it does                         |
|------|------------------------------------------------|--------------------------------------|
| 1    | `/rca duplicate stops on map`                  | Creates `docs/rca/duplicate-stops.md`  |
| 2    | `/implement-fix docs/rca/duplicate-stops.md`   | Applies fix + adds regression test   |
| 3    | `/be-validate`                                 | Full validation pyramid              |
| 4    | `/commit`                                      | `fix(stops): deduplicate map markers`  |

### Quick Fix (known issue, no RCA needed)

```
Edit directly → /be-validate → /commit
```

### Code Review Fix

```
/review → /code-review-fix → /be-validate → /commit
```

| Step | Command                                                      | What it does                         |
|------|--------------------------------------------------------------|--------------------------------------|
| 1    | `/review`                                                    | Creates `.agents/code-reviews/uncommitted-review.md` |
| 2    | `/code-review-fix .agents/code-reviews/uncommitted-review.md` | Fixes all flagged issues             |
| 3    | `/be-validate`                                               | Full validation pyramid              |
| 4    | `/commit`                                                    | Conventional commit                  |

---

## Testing Workflows

### Unit/Integration Tests (backend)

| Command              | What it runs                                     |
|----------------------|--------------------------------------------------|
| `make test`          | 612 tests, ~15s                                  |
| `make check`         | lint + types + tests (full)                      |
| `/be-validate`       | ruff format + ruff check + mypy + pyright + pytest |

### E2E Tests (Playwright)

| Command              | What it runs                                     |
|----------------------|--------------------------------------------------|
| `make e2e`           | Auto-detect changed features, run only those     |
| `make e2e-all`       | All 81 e2e tests                                 |
| `make e2e-ui`        | Interactive Playwright UI mode                   |
| `make e2e-headed`    | Run with visible browser                         |
| `/e2e`               | Auto-detects, or pass specific test file         |
| `/e2e schedules`     | Run only schedule-related e2e tests              |

### Frontend Validation

| Command              | What it runs                                     |
|----------------------|--------------------------------------------------|
| `/fe-validate`       | TypeScript + ESLint + build + design system + i18n + a11y |

### Post-Implementation Documentation

| Command              | What it does                                     |
|----------------------|--------------------------------------------------|
| `/execution-report`  | Compare implementation vs plan                   |
| `/system-review`     | Process improvements analysis                    |
| `/update-docs`       | Update CLAUDE.md, PRD after commit               |
