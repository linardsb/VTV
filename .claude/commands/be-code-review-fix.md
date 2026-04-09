---
description: Diagnose and fix backend bugs, review findings, type errors, or test failures
argument-hint: [description of issue] e.g. "pyright error in app/fleet/service.py" or "failing test_security auth check"
allowed-tools: Read, Write, Edit, Glob, Grep, Bash(uv run ruff:*), Bash(uv run mypy:*), Bash(uv run pyright:*), Bash(uv run pytest:*), mcp__jcodemunch__search_symbols, mcp__jcodemunch__find_references, mcp__jcodemunch__get_file_outline, mcp__jcodemunch__get_symbol_source
---

@.claude/commands/_shared/python-anti-patterns.md
@.claude/commands/_shared/security-contexts.md

# Backend Code Review Fix — Diagnose and Fix Issues

Find, diagnose, and fix backend bugs, code review findings, or quality issues.

## Trigger

Use when: bug report, failing test, code review comment, lint/type error, runtime exception, security finding, or any backend issue that needs fixing rather than new feature development.

**Difference from `/code-review-fix`:** That command takes a review file and works through findings by priority. This command accepts any issue description and diagnoses from scratch.

## Process

### 1. Understand the Issue

Read the user's description (from `$ARGUMENTS` or conversation). Classify:
- **Bug**: unexpected behaviour, runtime error, wrong output
- **Code review finding**: style, architecture, security, performance issue
- **Test failure**: failing test that needs code or test fix
- **Type/lint error**: mypy, pyright, or ruff violation
- **Security finding**: convention test failure, Bandit violation, audit finding

### 2. Reproduce / Locate

**jCodeMunch** (repo from `list_repos`) for cross-file tracing:
- `search_symbols(query, kind)` — find related functions/classes
- `find_references(symbol_name)` — trace callers/callees across codebase
- `get_file_outline(file_path)` — understand file structure before deciding what to read
- `get_symbol_source(symbol_name)` — read just the specific function you need

Only `Read` the full file when you need to edit it.

**Direct diagnosis by issue type:**
- **Bugs:** Trace the failing code path through VTV's VSA layers: routes → service → repository → model
- **Test failures:** Run the failing test and read the traceback:
  ```bash
  uv run pytest {test_file}::{test_name} -v --tb=short
  ```
- **Type errors:** Run the checker on the specific file:
  ```bash
  uv run pyright {file}
  uv run mypy {file}
  ```
- **Lint errors:** Run ruff on the specific file:
  ```bash
  uv run ruff check {file}
  ```
- **Security findings:** Run security-specific checks:
  ```bash
  uv run ruff check {file} --select=S --no-fix
  uv run pytest app/tests/test_security.py -v --tb=short -k "{test_name}"
  ```

### 3. Root Cause Analysis

- Trace the issue to its root cause — don't patch symptoms
- Check if the same pattern exists elsewhere (grep for similar code)
- Identify the minimal set of files that need changes
- For security issues, check the relevant security context (CTX-AUTH/RBAC/FILE/AGENT/INFRA/INPUT from `_shared/security-contexts.md`)

### 4. Fix

Apply the fix following VTV project conventions:
- Complete type annotations on every function
- Structured logging: `domain.component.action_state` via `get_logger(__name__)`
- Async `select()` queries (never `.query()`)
- `escape_like()` for ILIKE queries
- `DomainValidationError` (not `ValidationError` — avoids Pydantic clash)
- Pydantic Update schemas: `reject_empty_body` model_validator
- Constrained strings: `Literal[...]` not bare `str`
- All endpoints: `get_current_user` or `require_role()` dependency
- Rate limiting: `@limiter.limit()` on HTTP routes

Don't over-engineer — fix the issue, nothing more. Verify against the security contexts for any routes you touch.

### 5. Verify

Run the validation pyramid on affected files:

```bash
# Format + lint
uv run ruff format {files}
uv run ruff check --fix {files}

# Security-specific lint
uv run ruff check {files} --select=S --ignore=S311 --no-fix

# Type check
uv run pyright {files}
uv run mypy {files}

# Tests — run related tests first, then full suite
uv run pytest {test_file} -v
uv run pytest -v -m "not integration"

# Security convention tests (if touching auth, endpoints, or security-related code)
uv run pytest app/tests/test_security.py -v --tb=short
```

**NEVER** use `--unsafe-fixes` or run `ruff check --fix .` on the entire repo — only lint files you're actively changing.

Fix any issues introduced by the change. Repeat until all checks pass.

### 6. Report

Summarise:
- **Root cause**: what was wrong and why
- **Fix**: what was changed and in which files
- **Verification**: which checks passed
- **Risk**: any side effects or areas to watch

## Rules

- Fix the root cause, not the symptom
- Don't refactor unrelated code while fixing a bug
- Don't add features — only fix the reported issue
- If the fix requires architectural changes, flag it and suggest `/be-planning` instead
- Run verification on every file you touch — never skip type checks
- Check the loaded `_shared/python-anti-patterns.md` before writing any Python
