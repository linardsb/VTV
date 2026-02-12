---
description: Apply the fix described in an RCA document with regression tests
argument-hint: [github-issue-id] e.g. 42
allowed-tools: Read, Write, Edit, Bash(uv run ruff:*), Bash(uv run mypy:*), Bash(uv run pyright:*), Bash(uv run pytest:*), Bash(uv run alembic:*)
---

This command reads an RCA document (created by `/rca`) and implements the proposed fix. It applies each code change described in the "Proposed Fix" section, writes regression tests to prevent the bug from recurring, and runs the full validation suite. This is the execution half of the `/rca` + `/implement-fix` bug fix workflow.

The command follows the RCA document as its source of truth — it reads the root cause analysis, understands what needs to change and why, then applies changes following VTV conventions (type annotations, async patterns, structured logging). Regression tests are named `test_issue_{id}_{description}()` and placed in the appropriate feature's test directory, making them easy to find later.

After implementation, it runs all 5 validation checks (ruff format, ruff check, mypy, pyright, pytest) and suggests a conventional commit message in `fix(scope): description (Fixes #{id})` format. Prerequisite: you must run `/rca {id}` first to create the RCA document at `docs/rca/issue-{id}.md`.

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
uv run pytest -v
```

## OUTPUT

Report to the user:
- Files modified (with paths)
- Tests added (with names)
- Migration status (if applicable)
- Validation results (pass/fail for each command)
- Suggested commit message: `fix(scope): description (Fixes #$ARGUMENTS)`
- To commit: `/commit`
