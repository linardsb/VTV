---
description: Apply the fix described in an RCA document with regression tests
argument-hint: [github-issue-id] e.g. 42
allowed-tools: Read, Write, Edit, Bash(uv run ruff:*), Bash(uv run mypy:*), Bash(uv run pyright:*), Bash(uv run pytest:*), Bash(uv run alembic:*)
---

Read an RCA document and implement the proposed fix with regression tests, then validate.

# Implement Fix — Execute from RCA Document

## INPUT

**Issue ID:** $ARGUMENTS

Read the RCA document at `docs/rca/issue-$ARGUMENTS.md` completely before writing any code.

## PROCESS

### 1. Read and understand the RCA

- Read `docs/rca/issue-$ARGUMENTS.md` in full
- Understand the root cause, proposed changes, and required tests
- Identify all files that need modification

### 2. Implement the fix

Follow the "Proposed Fix" section from the RCA document:

- Apply each change described in "Changes Required"
- Follow VTV conventions:
  - Complete type annotations on all new/modified functions
  - Structured logging: `domain.component.action_state`
  - Async patterns for database operations
  - Google-style docstrings

### 3. Write regression tests

Create tests that verify the fix:
- Test naming: `test_issue_[ID]_[description]()`
- Place in the appropriate feature's `tests/` directory
- Use `@pytest.mark.integration` if the test requires a real database
- Test both the fixed behavior AND edge cases

### 4. Run database migrations (if needed)

If the RCA specifies schema changes:

```bash
uv run alembic revision --autogenerate -m "fix: issue [ID] - [description]"
uv run alembic upgrade head
```

### 5. Validate — ALL must pass

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

**Integration tests (if Docker is running):**

```bash
docker-compose ps 2>/dev/null && uv run pytest -v -m integration || echo "Skipped — Docker not running"
```

**Error recovery rules:**
- If a check fails, attempt to fix the issue and re-run that specific check
- Maximum 3 fix attempts per check before stopping
- If you cannot fix after 3 attempts, STOP and report the failures to the user with:
  - Which check failed
  - What you tried
  - The exact error output

## OUTPUT

Report to the user:
- Files modified (with paths)
- Tests added (with names)
- Migration status (if applicable)
- Validation results (pass/fail for each command)
- Suggested commit message: `fix(scope): description (Fixes #$ARGUMENTS)`
- To commit: `/commit`

**Next steps:**
- If fix succeeds: `/commit` with the suggested message
- If fix fails after validation: re-investigate with `/rca $ARGUMENTS`
