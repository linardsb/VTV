# System Review: Security Hardening v3

**Alignment Score:** 6/10
- Notable divergences, one critical plan bug. The plan was comprehensive in scope (19 tasks, 4 phases, threat matrix, 15 known pitfalls) but contained a production-breaking defect and several downstream impact gaps that required 7 bug fixes during execution.

## Divergence Analysis

### Critical Plan Bug

| # | Divergence | Classification | Root Cause |
|---|-----------|---------------|------------|
| 1 | **Password complexity added to `LoginRequest` instead of `PasswordResetRequest`** | **BAD — Plan bug** | Plan Task 2 (line 150) explicitly instructed: "Add `@field_validator('password')` to `LoginRequest` schema." This would reject every existing user with a weak password at login time (422 before auth service is reached). The fix moved validation to `PasswordResetRequest` only. **This would have been a production outage.** |

**Root cause trace:** The planner confused *password creation/reset* validation with *password submission* validation. Password complexity must be enforced when passwords are SET, not when they are USED. The plan didn't trace the LoginRequest schema's usage path (login endpoint → existing users with weak passwords → locked out).

### Downstream Impact Gaps

| # | Divergence | Classification | Root Cause |
|---|-----------|---------------|------------|
| 2 | Health test assertions broke after field redaction | **BAD — Plan gap** | Task 11 said "remove `provider` and `environment` from responses" but didn't include updating the 4+ existing tests that assert those fields exist. |
| 3 | Auth route tests used complex passwords after schema change | **BAD — Consequence of #1** | Direct cascade from the LoginRequest bug. Tests constructing `LoginRequest(password="admin")` started failing. |
| 4 | Missing logger import in agent routes | **BAD — Plan gap** | Task 12 added `logger.warning("agent.quota_exceeded_http", ...)` but didn't mention importing `get_logger` and creating the logger instance. |
| 5 | Quota test patched wrong module for `get_redis` | **BAD — Known pitfall not applied** | Anti-pattern #36 (lazy imports break `@patch`) is documented in MEMORY.md but the plan's test code in Task 13 used `patch("app.auth.token.get_redis")` without checking whether the import is lazy. |

### Code Quality Issues in Plan Snippets

| # | Divergence | Classification | Root Cause |
|---|-----------|---------------|------------|
| 6 | Redis exception handlers used `pass` or `debug` logging | **BAD — Plan violated project rules** | Plan's code snippets (Tasks 5, 12) included `except Exception: pass` which violates Ruff S110 (bare except pass). The code review had to upgrade these to `logger.warning`. |
| 7 | Brute-force test placed in wrong test class | **Neutral — Implementation detail** | Plan didn't specify which test class to insert into. Executor placed it outside the class that had the `_no_redis` autouse fixture. Minor, but shows plan should specify test class context. |

### Justified Divergences

| # | Divergence | Classification | Reason |
|---|-----------|---------------|--------|
| 8 | Added 18 new tests instead of 8 test classes | **GOOD** | Code review identified gaps (cross-request brute-force, password reset, quota exceeded). More tests = better coverage. |
| 9 | Added `test_login_accepts_weak_password` regression test | **GOOD** | Prevents the critical bug (#1) from recurring. Smart defensive testing. |
| 10 | Added Redis clear on expired DB lockout | **GOOD** | Code review caught a DB-Redis sync gap where DB lockout expires but Redis lockout persists. |

## Pattern Compliance

- [x] Type safety maintained — mypy 0 errors, pyright 0 errors
- [x] Structured logging follows convention — all new log events use `domain.component.action_state`
- [x] VSA boundaries respected — changes stayed within auth, core, events verticals
- [x] Tests written alongside code — 18 new tests, 614 total suite passing
- [ ] ~~Agent docstrings follow 5-principle format~~ — N/A (no agent tools modified)

## Recommended Actions

### 1. Add "Schema Impact Tracing" rule to `/be-planning`

**Where:** `/be-planning` template, in the task generation section
**What:** When a plan task adds validation to a Pydantic schema, the plan MUST include:
- A sub-step: "Grep for `SchemaName(` across the codebase to find all constructors"
- Explicit consideration of whether existing data can pass the new validation
- If the schema is used on an INPUT endpoint (login, search), verify existing stored data won't be rejected

**Why:** The LoginRequest bug is a class of error where adding stricter validation to a SUBMISSION schema breaks existing users. This is different from adding validation to a CREATION schema.

**Proposed text for Known Pitfalls:**
```
## Schema Validation Impact
When adding field validators to existing Pydantic schemas:
- INPUT schemas (login, search) — existing stored data must still pass validation.
  Password complexity goes on PasswordResetRequest, NOT LoginRequest.
- OUTPUT schemas — existing code constructing these schemas must be updated.
- Grep for `SchemaName(` to find ALL constructors before adding validators.
```

### 2. Add "Downstream Test Updates" rule to `/be-planning`

**Where:** `/be-planning` template, task template section
**What:** Every task that removes, renames, or changes the shape of a response/schema field MUST include a sub-task: "Update tests that assert the old field/value."

**Why:** Tasks 11 (health redaction) and 2 (password complexity) both broke existing tests that the plan didn't account for. The executor had to discover and fix these during implementation.

**Proposed text:**
```
For each task that modifies response shapes or schema fields:
- Include sub-task: "Update existing tests asserting removed/changed fields"
- Run `grep -r 'field_name' app/*/tests/` to find affected test files
```

### 3. Plan code snippets must follow project lint rules

**Where:** `/be-planning` template, Known Pitfalls section
**What:** Code snippets included in plans must not contain patterns that violate project linting rules. Specifically:
- No `except Exception: pass` (Ruff S110) — always include `logger.warning()`
- No missing imports — if code adds a function call, include the import
- No `@patch` targeting lazily-imported modules — reference anti-pattern #36

**Why:** 3 of the 7 bugs were caused by plan code snippets that violated project rules the executor copied verbatim.

### 4. Add Python anti-pattern to MEMORY.md

**New rule:**
```
44. **Password complexity on LOGIN schema locks out users** — Complexity validation
    (min length, uppercase, digit) must go on PasswordResetRequest/RegisterRequest,
    NEVER on LoginRequest. Existing users with weak passwords get 422 at login.
```

### 5. Add "import completeness" check to plan task template

**Where:** `/be-planning` task template
**What:** Each task's code changes section should include ALL necessary imports, not just the primary function. When adding `logger.warning(...)`, also add `from app.core.logging import get_logger` if not already present.

**Why:** Task 12 added logging to agent routes but omitted the logger import, causing a NameError.

## Key Learnings

1. **The most dangerous plan bugs are validation changes on input schemas.** Adding stricter validation to a schema used for LOGIN/SEARCH will reject existing valid data. This is a production outage pattern.

2. **Plan code snippets are copied verbatim by executors.** If a plan shows `except Exception: pass`, the executor will write it. Plans must be linting-clean.

3. **Removing fields from responses always breaks tests.** Every "redact X from response" task needs a paired "update tests asserting X" sub-task.

4. **The code review phase caught 11 issues the plan missed.** This validates the `/review` → `/code-review-fix` loop as essential. Without it, the critical LoginRequest bug would have shipped.

5. **The plan's Known Pitfalls section (15 rules) was effective for the pitfalls it covered** (Redis typing, ARG001, docker env vars). The misses were in areas the pitfalls didn't cover (schema validation impact, downstream test updates, code snippet quality).

6. **Alignment would have been 8/10 without the LoginRequest bug.** One critical planning error dropped the score significantly because it would have caused a production-breaking regression.

## Process Improvement Priority

| Priority | Action | Impact |
|----------|--------|--------|
| **P0** | Schema impact tracing rule (#1) | Prevents production outages from validation changes |
| **P1** | Downstream test update rule (#2) | Eliminates ~40% of implementation bugs (3 of 7) |
| **P1** | Plan snippet lint compliance (#3) | Eliminates copied-verbatim lint violations |
| **P2** | Import completeness check (#5) | Prevents NameError-class bugs |
| **P2** | MEMORY.md anti-pattern #44 (#4) | Documents the specific LoginRequest lesson |
