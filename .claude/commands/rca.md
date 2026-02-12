---
description: Analyze and document root cause for a GitHub issue
argument-hint: [github-issue-id]
---

# RCA — Root Cause Analysis

## INPUT

**Issue ID:** $ARGUMENTS

## PROCESS

### 1. Gather issue details

- Read the GitHub issue to understand the reported problem
- Note: symptoms, reproduction steps, environment, affected endpoints

### 2. Investigate the codebase

Search VTV's vertical slice structure systematically:

- **Routes**: Check endpoint handlers for the affected functionality
- **Service**: Check business logic for edge cases or missing validation
- **Models**: Check database models for constraint issues or missing fields
- **Schemas**: Check Pydantic schemas for validation gaps
- **Middleware**: Check `app/core/middleware.py` if the issue is cross-cutting
- **Config**: Check `app/core/config.py` for environment-related issues

### 3. Check structured logs

Look for `_failed` events related to the issue:
- Search for error patterns in the codebase
- Check exception handlers in `app/core/exceptions.py`
- Review relevant test files for missing coverage

### 4. Check database state

If the issue involves data:
- Review alembic migration history in `alembic/versions/`
- Check model definitions for missing constraints or indexes
- Verify migration state is current

### 5. Identify root cause

Determine:
- **What** is failing (specific function, line, or interaction)
- **Why** it fails (missing validation, race condition, wrong assumption, etc.)
- **When** it was introduced (if identifiable from git history)

### 6. Write RCA document

Save to `docs/rca/issue-$ARGUMENTS.md`:

```markdown
# RCA: Issue #[ID] — [Title]

## Summary
[One paragraph describing the issue and root cause]

## Symptoms
- [Observable behavior reported]

## Root Cause
**Location:** `[file:line]`
**Category:** [validation gap | logic error | race condition | missing constraint | config issue | etc.]

[Detailed explanation of why this happens]

## Evidence
- [Code snippet or log pattern that confirms the root cause]

## Proposed Fix

### Changes Required
1. **`[file path]`** — [what to change and why]
2. **`[file path]`** — [what to change and why]

### Database Migration
[Required/Not required — if required, describe schema change]

### New Tests
- `test_issue_[ID]_[description]()` — [what the test verifies]

## Validation
After fix, run:
1. `uv run ruff format .`
2. `uv run ruff check .`
3. `uv run mypy app/`
4. `uv run pyright app/`
5. `uv run pytest -v`

## Impact
- **Severity:** [Critical/High/Medium/Low]
- **Affected users:** [who/what is impacted]
- **Related code:** [other files that might be affected]
```

## OUTPUT

1. Save RCA to `docs/rca/issue-$ARGUMENTS.md`
2. Report to the user:
   - Root cause summary (2-3 sentences)
   - Files involved
   - Proposed fix complexity (trivial/moderate/complex)
   - To implement: `/implement-fix $ARGUMENTS`
