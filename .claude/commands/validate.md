---
description: Run full VTV validation suite (lint, type check, tests)
allowed-tools: Bash(uv run ruff:*), Bash(uv run mypy:*), Bash(uv run pyright:*), Bash(uv run pytest:*)
---

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
