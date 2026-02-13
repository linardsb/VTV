---
description: Review code against all 8 VTV quality standards
argument-hint: [file-or-directory] e.g. app/agent/ or app/core/health.py
---

Review code against VTV's 8 quality standards and produce a findings table with fix suggestions.

@CLAUDE.md

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
- Tool/agent functions have agent-optimized docstrings covering all 5 principles:
  1. **Guide Selection** — When to use this tool (and when NOT to)
  2. **Prevent Token Waste** — Parameter efficiency tips, concise response formats
  3. **Enable Composition** — What tools to chain before/after
  4. **Set Expectations** — Output format, size, performance characteristics
  5. **Provide Examples** — Concrete usage with realistic data

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

**Stats:**
- Files reviewed: [X]
- Files modified: [Y]
- Files added: [Z]
- Issues: [N] total — [A] Critical, [B] High, [C] Medium, [D] Low

Save the review to `.agents/code-reviews/[target-name]-review.md`.

**Next step:** To fix issues: `/code-review-fix .agents/code-reviews/[target-name]-review.md`
