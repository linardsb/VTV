---
description: Run all 5 VTV quality checks — formatting, linting, type checking, and tests
argument-hint:
allowed-tools: Bash(uv run ruff:*), Bash(uv run mypy:*), Bash(uv run pyright:*), Bash(uv run pytest:*)
---

This command runs the complete VTV quality validation pipeline in sequence: ruff format (auto-fixes formatting), ruff check (linting for style, imports, security), mypy strict mode (type checking), pyright strict mode (catches issues mypy misses), and pytest with verbose output. Each check must pass before the next is reported, giving you a clear picture of what needs fixing first.

The output is a pass/fail scorecard for all 5 checks. If any check fails, it includes specific error locations with file paths and line numbers so you can fix them immediately. This is the single command you run after any code change to verify nothing is broken — it's faster than running each tool individually and ensures nothing is skipped.

Run `/validate` before every commit, after implementing features with `/execute`, and after applying bug fixes with `/implement-fix`. It's also useful as a quick sanity check during development to catch type errors or linting issues early. Pair it with `/review` for a complete quality assessment — `/validate` catches automated issues while `/review` catches architectural and convention issues.

# Validate — Run Full VTV Validation Suite

## INPUT

No arguments needed. Runs all validation commands against the current codebase state.

## PROCESS

Run each command in order. Report results for each before moving to the next.

### 1. Format

```bash
uv run ruff format .
```

### 2. Lint

```bash
uv run ruff check .
```

### 3. Type Check — MyPy

```bash
uv run mypy app/
```

### 4. Type Check — Pyright

```bash
uv run pyright app/
```

### 5. Tests

```bash
uv run pytest -v
```

## OUTPUT

```
Validation Results:
  1. Ruff format:  PASS / FAIL
  2. Ruff check:   PASS / FAIL  [N issues]
  3. MyPy:         PASS / FAIL  [N errors]
  4. Pyright:      PASS / FAIL  [N errors]
  5. Pytest:       PASS / FAIL  [X passed, Y failed]

Overall: ALL PASS / X FAILURES
```

If any step fails, list the specific errors with file paths and line numbers so they can be fixed.
