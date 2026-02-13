---
description: Run all 5 VTV quality checks — formatting, linting, type checking, and tests
argument-hint:
allowed-tools: Bash(uv run ruff:*), Bash(uv run mypy:*), Bash(uv run pyright:*), Bash(uv run pytest:*), Bash(curl:*), Bash(docker-compose:*)
---

Run all 5 VTV quality checks in sequence and report a pass/fail scorecard.

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

### 6. Server Validation (optional — only if Docker is running)

```bash
docker-compose ps 2>/dev/null
```

If services are running, test endpoints:

```bash
curl -s http://localhost:8123/health
curl -s -o /dev/null -w "%{http_code}" http://localhost:8123/docs
```

## OUTPUT

```
Validation Results:
  1. Ruff format:  PASS / FAIL
  2. Ruff check:   PASS / FAIL  [N issues]
  3. MyPy:         PASS / FAIL  [N errors]
  4. Pyright:      PASS / FAIL  [N errors]
  5. Pytest:       PASS / FAIL  [X passed, Y failed]
  6. Server:       PASS / FAIL / SKIPPED (Docker not running)

Overall: ALL PASS / X FAILURES
```

If any step fails, list the specific errors with file paths and line numbers so they can be fixed.

**Next steps:**
- If all checks pass: Run `/commit` to commit changes, or `/review [path]` for architectural review
- If checks fail: Fix the reported issues and re-run `/validate`
