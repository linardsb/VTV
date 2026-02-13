---
description: Fix issues found in a code review report
argument-hint: [code-review-file] [scope] e.g. .agents/code-reviews/agent-review.md all
allowed-tools: Read, Write, Edit, Bash(uv run ruff:*), Bash(uv run mypy:*), Bash(uv run pyright:*), Bash(uv run pytest:*)
---

Fix all issues from a code review, then validate.

# Code Review Fix

## INPUT

Code review file: $1
Scope: $2 (default: all issues)

## PROCESS

### 1. Read review

Read the entire code review file. Understand all issues, their severities, and file locations.

### 2. Fix issues

For each issue (Critical first, then High, Medium, Low):
1. Read the affected file to understand full context
2. Apply the fix following VTV conventions
3. Explain what was wrong and what you changed

### 3. Validate

Run full validation:

```bash
uv run ruff format .
uv run ruff check .
uv run mypy app/
uv run pyright app/
uv run pytest -v
```

Max 3 fix attempts per validation failure.

## OUTPUT

- Issues fixed (file:line, what changed)
- Issues skipped (with reason)
- Validation results (5-step scorecard)
- **Next step:** `/commit`
