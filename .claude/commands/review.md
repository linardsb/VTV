---
description: Review code against all 8 VTV quality standards
argument-hint: [file-or-directory] e.g. app/agent/ or app/core/health.py
allowed-tools: Read, Glob, Grep
---

This command performs a comprehensive code review against VTV's 8 quality standards: type safety, Pydantic schemas, structured logging, database patterns, architecture (VSA boundaries), docstrings, testing, and security. It reads every file in the target path and checks each one systematically, producing a findings table with file:line references, issue descriptions, fix suggestions, and priority levels.

Issues are categorized by priority: Critical (type safety violations, security issues, data corruption risks), High (missing logging, broken patterns, no tests), Medium (inconsistent naming, missing docstrings, suboptimal patterns), and Low (style nits, minor improvements). For agent tool files, it additionally checks that docstrings follow the 5-principle agent-optimized format (selection guidance, composition hints, token efficiency, expectations, examples).

Use this command before committing to catch issues early, or run it on an entire feature directory after implementation. It's read-only and makes no changes — it only reports findings. Pair it with `/validate` which runs automated checks (linting, type checking, tests), while `/review` catches architectural and convention issues that automated tools miss.

# Review — Code Review Against VTV Standards

## INPUT

**Target:** $ARGUMENTS

## PROCESS

Read all files in the target path. For each file, check against VTV's standards in this order:

### 1. Type Safety (CRITICAL)

- All functions have complete type annotations (params + return)
- No `Any` types without justification
- No `# type: ignore` or `# pyright: ignore` suppressions
- Pydantic models use proper field types

### 2. Pydantic Schemas

- Request/response schemas are complete (no missing fields)
- Validators use `@field_validator` or `@model_validator` patterns
- Schemas inherit appropriately (Create, Update, Response variants)

### 3. Structured Logging

- Events follow `domain.component.action_state` pattern
- Actions have `_started` and `_completed`/`_failed` pairs
- Error logs include `exc_info=True`, `error=str(e)`, `error_type=type(e).__name__`
- Logger created with `get_logger(__name__)`
- No generic events like "processing" or "handling"

### 4. Database Patterns

- Async/await used consistently with SQLAlchemy
- `select()` style (not `.query()`)
- Models inherit from `Base` and `TimestampMixin`
- `get_db()` dependency used for sessions
- `expire_on_commit=False` respected

### 5. Architecture

- Vertical slice boundaries respected (no cross-feature imports)
- Shared utilities only in `app/shared/` when used by 3+ features
- Router registered in `app/main.py`
- Feature structure: models.py, schemas.py, routes.py, service.py, tests/

### 6. Docstrings

- Functions have Google-style docstrings
- Tool/agent functions have agent-optimized docstrings (selection guidance, composition hints, examples)

### 7. Testing

- Tests exist in feature's `tests/` subdirectory
- Integration tests marked with `@pytest.mark.integration`
- Async tests use proper patterns
- Edge cases covered

### 8. Security

- No hardcoded secrets or credentials
- Input validation on API boundaries
- SQL injection prevention (parameterized queries via SQLAlchemy)

## OUTPUT

Present findings in this format:

### Review: `[target path]`

**Summary:** [1-2 sentence overall assessment]

| File:Line | Issue | Suggestion | Priority |
|-----------|-------|------------|----------|
| `path:42` | [what's wrong] | [how to fix] | Critical |
| `path:15` | [what's wrong] | [how to fix] | High |
| `path:88` | [what's wrong] | [how to fix] | Medium |
| `path:3`  | [what's wrong] | [how to fix] | Low |

**Priority Guide:**
- **Critical**: Type safety violations, security issues, data corruption risks
- **High**: Missing logging, broken patterns, no tests
- **Medium**: Inconsistent naming, missing docstrings, suboptimal patterns
- **Low**: Style nits, minor improvements

**Stats:** [X] files reviewed | [Y] issues found | [Z] critical
