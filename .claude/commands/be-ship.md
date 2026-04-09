---
description: Full backend quality pipeline — validate, review, fix, validate
argument-hint:
allowed-tools: Read, Write, Edit, Glob, Grep, Bash(uv run ruff:*), Bash(uv run mypy:*), Bash(uv run pyright:*), Bash(uv run pytest:*), Bash(curl:*), Bash(docker-compose:*), mcp__jcodemunch__search_symbols, mcp__jcodemunch__find_references, mcp__jcodemunch__get_file_outline, mcp__jcodemunch__get_symbol_source
---

@.claude/commands/_shared/python-anti-patterns.md

# Backend Ship — Full Quality Pipeline

Run the complete validate → review → fix → validate pipeline in one pass.

Use after completing a feature implementation (`/be-execute`) to catch and fix all issues before commit.

## Phase 1: Initial Validation

Run `/be-validate` — all 10 levels of the VTV quality pyramid:

1. Ruff format
2. Ruff check (lint)
3. MyPy (strict type checking)
4. Pyright (strict type checking)
5. Pytest (unit tests, `-m "not integration"`)
6. Pytest (integration tests, if Docker running)
7. SDK sync check (if FastAPI running)
8. Server validation (if Docker running)
9. Security lint (Ruff Bandit rules: `--select=S`)
10. Security convention tests (`app/tests/test_security.py`)

Steps 1-5 and 9-10 are **hard gates**. Steps 6-8 are conditional/soft.

If there are failures, fix them before moving to Phase 2.

## Phase 2: Code Review

Run `/review` against the changed files (use `git diff --name-only` to identify them). Check all 8 VTV backend quality standards:

1. **Type Safety** — Complete annotations, no `Any`, no suppressions
2. **Pydantic Schemas** — Complete models, validators, inheritance
3. **Structured Logging** — `domain.component.action_state` pattern, started/completed/failed pairs
4. **Database Patterns** — Async/await, `select()` style, `TimestampMixin`, `get_db()`
5. **Architecture** — VSA boundaries, shared utility rules (3-feature rule), router registration
6. **Docstrings** — Google-style for code, 5-principle for agent tools
7. **Testing** — Tests exist, integration tests marked, edge cases covered
8. **Security** — Context-aware checks (CTX-AUTH/RBAC/FILE/AGENT/INFRA/INPUT)

Report all findings with severity (critical, warning, suggestion).

## Phase 3: Fix Review Findings

Run `/be-code-review-fix` for **critical** findings from Phase 2 that violate codified project rules (CLAUDE.md, pyproject.toml, `.claude/rules/`).

- Fix critical findings that reference specific documented rules
- Optionally fix warnings if they match a documented convention and are trivial (<3 lines)
- Do NOT fix subjective LLM opinions (e.g. "could add logging", "consider refactoring") that don't reference a specific project rule

**Skip this phase** if Phase 2 found zero critical issues.

## Phase 4: Final Validation

Run `/be-validate` again to confirm all fixes are clean. This is the gate — nothing ships if this fails.

If Phase 4 fails after fixes, iterate (fix → validate) until clean, **max 3 rounds**. If still failing after 3 rounds, stop and report the remaining issues for manual intervention.

## Output

End with a single summary table:

```
## Ship Report

| Phase | Result | Details |
|-------|--------|---------|
| 1. Validate | PASS/FAIL | {errors found / clean} |
| 2. Review | {N} critical, {N} warning, {N} suggestion | {key findings} |
| 3. Fix | {N} fixes applied | or "skipped — no critical issues" |
| 4. Validate | PASS/FAIL | {final gate result} |

**Status:** READY TO SHIP / BLOCKED — {reason}
```

## Rules

- Do NOT skip phases — run all 4 in order
- Do NOT commit — this pipeline validates only. User runs `/commit` separately
- If Phase 4 fails after 3 fix rounds, stop and report (don't loop forever)
- If a fix requires architectural changes, stop and recommend `/be-planning` instead
- Security convention tests (`app/tests/test_security.py`) are hard gates — must pass
