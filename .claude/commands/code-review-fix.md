---
description: Fix issues found in a code review report
argument-hint: [code-review-file] [scope] e.g. .agents/code-reviews/core-review.md all
allowed-tools: Read, Write, Edit, Bash(uv run ruff:*), Bash(uv run mypy:*), Bash(uv run pyright:*), Bash(uv run pytest:*)
---

Fix all issues from a code review, then validate.

# Code Review Fix

## INPUT

**Arguments:** $ARGUMENTS

Parse two values from the arguments:
- **Code review file** (required): first argument — path to the review file
- **Scope** (optional, default: `all`): second argument — which issues to fix (`all`, `critical`, `high`)

## PROCESS

### 1. Read review

Read the entire code review file. Understand all issues, their severities, and file locations.

### 2. Fix issues

For each issue (Critical first, then High, Medium, Low):
1. Read the affected file to understand full context
2. Apply the fix following VTV conventions
3. Explain what was wrong and what you changed

### 3. Validate

Run each command in sequence. Fix any issues before moving to the next:

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

**Security convention tests (explicit gate):**

```bash
uv run pytest app/tests/test_security.py -v --tb=short
```

**Integration tests (if Docker is running):**

```bash
docker-compose ps 2>/dev/null && uv run pytest -v -m integration || echo "Skipped — Docker not running"
```

**Error recovery rules:**
- **CRITICAL: After ANY code edit to fix a validation error, re-run from Level 1 (ruff format + ruff check --fix).** Code changes to fix type errors frequently introduce import sorting or lint regressions.
- If a check fails, attempt to fix the issue, then re-run ALL checks from Level 1
- Maximum 3 fix attempts per check before stopping
- If you cannot fix after 3 attempts, STOP and report the failures to the user

## OUTPUT

- Issues fixed (file:line, what changed)
- Issues skipped (with reason)
- Validation results (5-step scorecard)
- **Next step:** `/commit`
