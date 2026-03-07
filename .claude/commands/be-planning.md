---
description: Research codebase and create a self-contained implementation plan
argument-hint: [feature-description] e.g. add obsidian search tool
allowed-tools: Read, Glob, Grep, Write, mcp__jcodemunch__get_repo_outline, mcp__jcodemunch__get_file_outline, mcp__jcodemunch__get_file_tree, mcp__jcodemunch__search_symbols
---

Research the codebase and produce a self-contained plan that `/be-execute` can follow without additional context.

@CLAUDE.md
@reference/PRD.md
@.claude/commands/_shared/python-anti-patterns.md
@.claude/commands/_shared/security-contexts.md

# Planning — Create Feature Implementation Plan

## INPUT

**Feature request:** $ARGUMENTS

Make sure the structured planning is between 600 to 700 lines. 

You are creating a detailed implementation plan that ANOTHER AGENT will execute without seeing this conversation. The plan must be completely self-contained with explicit file paths, exact code patterns, and unambiguous steps.

**The test:** Could a developer who knows nothing about this feature implement it from the plan alone? If yes, an agent can too.

## PROCESS

### 1. Understand the feature

- Architecture rules and conventions are loaded via `@CLAUDE.md` above
- Product context is loaded via `@reference/PRD.md` above
- Read `reference/mvp-tool-designs.md` if the feature relates to agent tools
- **If this is an AI agent tool:** flag it as tool planning (see "Agent Tool Planning" section below)
- Explore existing features under `app/` to understand established patterns
- Read `app/main.py` to see current router registrations

### 2. Research existing code

**Token-efficient exploration (use jCodeMunch when the repo is indexed):**
- Use `get_repo_outline` or `get_file_tree` to map `app/` structure instead of multiple Glob calls
- Use `get_file_outline` to discover function signatures and class shapes — only `Read` the specific sections that need exact line references in the plan
- Use `search_symbols` to find reusable utilities (e.g., "PaginationParams", "TimestampMixin") instead of broad Grep sweeps
- Fall back to `Read` for config files, small files, and when you need exact code for the plan's code snippets

- Identify which existing modules this feature will interact with
- Check `app/shared/` for reusable utilities (TimestampMixin, PaginationParams, PaginatedResponse, ErrorResponse, get_db(), get_logger())
- Find similar features and note **exact file paths with line ranges** for patterns the executing agent must follow
- Check `alembic/versions/` for unapplied or recent migrations that could conflict
- Check `pyproject.toml` for existing dependencies; note any new packages needed (`uv add` commands)
- Check `.env.example` for current env vars; note if the feature needs new ones
- Identify existing features that might need changes when this feature is added (cross-feature impact)
- Research any external libraries/APIs needed — capture documentation URLs with specific sections

### 3. Security Context Assessment

Using the loaded `@_shared/security-contexts.md` reference, detect which security contexts apply to this feature:

1. **Match** the feature description and affected file paths against the trigger keywords in each context (CTX-AUTH, CTX-RBAC, CTX-FILE, CTX-AGENT, CTX-INFRA, CTX-INPUT)
2. **List** active contexts in the plan's "Security Contexts" section (see plan template below)
3. **Inject** the corresponding plan task templates into the implementation tasks — security tasks go alongside the feature tasks they protect, not in a separate "security phase"
4. **Add security test cases** to the testing strategy for each active context

Use the "Quick Reference: Context Detection" table from the shared reference for fast matching. Most features activate 1-3 contexts — if you find 0, double-check: at minimum, any feature with endpoints activates CTX-RBAC + CTX-INPUT.

### 4. Agent Tool Planning (if applicable)

> **NOTE: This is tool planning for an AI agent.** Tools are functions that an LLM calls during autonomous workflows. Their docstrings, parameter design, and error handling are optimized for machine consumption, not human developers.

If the feature involves agent tools (detected by keywords: tool, agent, MCP, Obsidian tool, transit tool, or if `mvp-tool-designs.md` has a matching spec), apply these additional requirements:

**Read first:**
- `mvp-tool-designs.md` — check if a tool spec already exists for this feature
- CLAUDE.md "Tool Docstrings for Agents" section — the 5 key principles

**Tool-specific design considerations:**
- **Agent-optimized docstrings** — every tool function must include:
  1. When to use this tool (selection guidance)
  2. When NOT to use it (prevent misuse)
  3. Parameter efficiency tips (avoid token waste)
  4. Expected output format and size
  5. Composition hints (what tools to chain before/after)
- **Dry-run support** — tools should accept a `dry_run: bool` parameter that returns what WOULD happen without side effects
- **Token efficiency** — tool responses should be concise and structured; avoid returning large unfiltered payloads
- **Error messages for LLMs** — errors should be actionable ("File not found at X, try listing directory Y first" not just "404")
- **Idempotency** — tools should be safe to retry without side effects where possible

**Tool-specific task order:**
1. Define Pydantic schemas in `schemas.py`
2. Implement tool with structured logging and type hints
3. Register tool with Pydantic AI agent
4. Create unit tests in `app/[feature]/tests/`
5. Add integration tests if needed

**Plan template additions for tools:**
- Add a "Tool Interface" section with function signature, parameter descriptions, and example calls
- Add a "Composition" section showing how this tool fits into multi-step agent workflows
- Add a "Dry-Run Behavior" section if applicable

### 5. Design the vertical slice

Plan the complete feature following VTV's vertical slice structure:
- `app/[feature]/models.py` — SQLAlchemy models inheriting `Base` and `TimestampMixin`
- `app/[feature]/schemas.py` — Pydantic schemas for request/response
- `app/[feature]/routes.py` — FastAPI router with typed endpoints. **Every endpoint MUST have `get_current_user` or `require_role()` dependency** — `TestAllEndpointsRequireAuth` in `app/tests/test_security.py` auto-discovers all routes and fails CI if any lack auth. Only explicitly allowlisted public endpoints (login, health) are exempt.
- `app/[feature]/service.py` — Business logic with structured logging
- `app/[feature]/tests/` — Unit and integration tests

### 6. Write the plan

Create the plan file at `.agents/plans/[feature-name].md` using this template:

```markdown
# Plan: [Feature Name]

## Feature Metadata
**Feature Type**: [New Capability / Enhancement / Refactor / Bug Fix]
**Estimated Complexity**: [Low / Medium / High]
**Primary Systems Affected**: [list]

## Feature Description

[2-3 paragraphs: what this feature does, the problem it solves, and user-facing behavior. Be specific about system impact.]

## User Story

As a [specific type of user]
I want to [specific action/capability]
So that [specific benefit/outcome]

## Security Contexts

**Active contexts** (detected from feature scope — see `_shared/security-contexts.md`):
- [CTX-XXX]: [Why this context applies — 1 sentence]
- [CTX-YYY]: [Why this context applies — 1 sentence]

**Not applicable:** [List contexts that don't apply and why, e.g., "CTX-FILE: No file uploads in this feature"]

Security requirements from active contexts are woven into the implementation tasks below, not in a separate phase.

## Solution Approach

[2-3 paragraphs describing the technical approach and why we chose it.]

**Approach Decision:**
We chose [approach] because:
- [Reason 1]
- [Reason 2]

**Alternatives Considered:**
- [Alternative 1]: Rejected because [reason]
- [Alternative 2]: Rejected because [reason]

## Relevant Files

The executing agent MUST read these files before starting implementation.

### Core Files
- `CLAUDE.md` — Architecture rules, logging patterns, type checking requirements
- `[file-path]` (lines X-Y) — [why relevant, what pattern to learn from it]

### Similar Features (Examples to Follow)
- `[file-path]` (lines X-Y) — [specific pattern demonstrated that should be replicated]

### Files to Modify
- `app/main.py` — Register [feature]_router

## Research Documentation

Use these resources for implementation guidance:

- [Documentation Title](https://url.com/path#anchor)
  - Section: [specific section name]
  - Summary: [what to learn — 1-2 sentences]
  - Use for: [which implementation step needs this]

## Implementation Plan

### Phase 1: Foundation
[What foundational work must happen first — schemas, types, shared utilities, new dependencies]

### Phase 2: Core Implementation
[Main feature implementation — business logic, routes, database models]

### Phase 3: Integration & Validation
[Integration with existing features, testing, validation]

## Step by Step Tasks

IMPORTANT: Execute every step in order, top to bottom. Do not skip steps.
Create one task per file — each task targets exactly one file path.
Use action keywords: CREATE, UPDATE, ADD, REMOVE, REFACTOR, MIRROR

**Schema Impact Tracing:** For any task that adds validators to existing schemas or removes/renames response fields, include a sub-step: "Grep for `SchemaName(` and update all constructors and test assertions." See Known Pitfalls #58-59.

**Import Completeness:** Every code change in a task that adds a function call (e.g., `logger.warning(...)`, `get_redis()`) MUST also specify the required import if it's not already present in the file. Don't assume imports exist — check the file first, include the import in the task.

**Plan Code Quality:** Code snippets included in tasks must follow project lint rules. No `except Exception: pass` (violates Ruff S110 — always include `logger.warning()`). No missing imports. No patterns that the executor would copy verbatim and then fail validation.

CRITICAL: Every task MUST include a **Per-task validation** block with ALL applicable checks in this order:
1. `uv run ruff format [file path]` — auto-format (ALWAYS include)
2. `uv run ruff check --fix [file path]` — lint + auto-fix (ALWAYS include; `--fix` resolves import sorting I001 which `ruff format` does NOT handle)
3. `uv run mypy [file path]` — type check (for all non-test .py files)
4. `uv run pyright [file path]` — type check (when strict typing is critical)
5. `uv run pytest [test path] -v` — run tests (for test files only)
Never omit linting from per-task validation. Every file gets formatted and lint-checked.

### Task 1: [Foundational Task Name]
**File:** `[exact/path/to/file.py]` (create new)
**Action:** CREATE

Create [schema/model/utility]:
- Define [Specific class name] with:
  - `field_name: Type` — [purpose and validation rules]
  - `field_name: Type` — [purpose and validation rules]
- Include Google-style docstring
- All fields have type annotations
- Follow pattern from: `[reference-file.py]` (lines X-Y)

**Per-task validation:**
- `uv run ruff format [exact file path]`
- `uv run ruff check --fix [exact file path]` passes
- `uv run mypy [exact file path]` passes with 0 errors

---

### Task 2: [Implementation Task Name]
**File:** `[exact/path/to/file.py]` (create new OR modify existing)
**Action:** CREATE / UPDATE

Implement [specific function/class]:
- Function signature: `async def function_name(param: Type) -> ReturnType:`
- Use [Specific model] from Task 1
- Add structured logging:
  - `logger.info("[feature].action_started", **context)`
  - `logger.info("[feature].action_completed", **context)`
  - `logger.error("[feature].action_failed", exc_info=True, error=str(e), error_type=type(e).__name__)`
- Follow pattern from: `[reference-file.py]` (lines X-Y)

**Per-task validation:**
- `uv run ruff format [exact file path]`
- `uv run ruff check --fix [exact file path]` passes
- `uv run mypy [exact file path]` passes

---

### Task N-1: [Testing Task Name]
**File:** `app/[feature]/tests/test_[module].py` (create new)
**Action:** Create

**Test 1: Happy path**
```python
async def test_[feature]_success():
    # Test successful execution with valid input
    # Assert expected behavior
```

**Test 2: Edge case — [specific case]**
```python
async def test_[feature]_[edge_case]():
    # Test [specific edge case]
    # Assert proper handling
```

**Test 3: Error case — [specific error]**
```python
@pytest.mark.integration
async def test_[feature]_[error_case]():
    # Test error handling for [specific error]
    # Assert proper exception raised
```

**Per-task validation:**
- `uv run ruff format app/[feature]/tests/test_[module].py`
- `uv run ruff check --fix app/[feature]/tests/test_[module].py` passes
- `uv run pytest app/[feature]/tests/ -v` — all tests pass

---

### Task N: Register Router & Final Integration
**File:** `app/main.py`
**Action:** UPDATE

Add:
```python
from app.[feature].routes import router as [feature]_router
app.include_router([feature]_router)
```

---

## Migration (if applicable)

**If database is running:**
```bash
uv run alembic revision --autogenerate -m "[description]"
uv run alembic upgrade head
```

**If database is NOT running (fallback):** Create migration manually. Specify column types, nullable flags, and foreign keys below so the executing agent can write `op.add_column()` / `op.create_table()` calls by hand:
- [Column 1]: `type`, nullable=[yes/no], default=[value]
- [Column 2]: `type`, nullable=[yes/no]

## Logging Events

- `[feature].action_started` — [when emitted]
- `[feature].action_completed` — [when emitted, include what metrics]
- `[feature].action_failed` — [when emitted, include error context]

## Testing Strategy

### Unit Tests
**Location:** `app/[feature]/tests/test_[module].py`
- [Component 1] — [what to test]
- [Component 2] — [what to test]

### Integration Tests
**Location:** `app/[feature]/tests/test_[module].py`
**Mark with:** `@pytest.mark.integration`
- [Integration point] — [what to test]

### Edge Cases
- [Edge case 1] — [expected behavior]
- [Edge case 2] — [expected behavior]
- Empty/null inputs — [expected behavior]

## Acceptance Criteria

This feature is complete when:
- [ ] [Specific, measurable criterion 1]
- [ ] [Specific, measurable criterion 2]
- [ ] All type checkers pass (mypy + pyright)
- [ ] All tests pass (unit + integration)
- [ ] Structured logging follows `domain.component.action_state` pattern
- [ ] No type suppressions added
- [ ] Router registered in `app/main.py`
- [ ] No regressions in existing tests
- [ ] Security context requirements met (all active CTX-* items addressed)

## Completion Checklist

Before marking this plan as fully executed:
- [ ] All tasks completed in order
- [ ] Per-task validations passed
- [ ] Full validation pyramid passed (Levels 1-4)
- [ ] No deviations from plan (or deviations documented with reasons)
- [ ] Ready for `/commit`

## Final Validation (5-Level Pyramid)

Run each level in order — every one must pass with 0 errors:

**Level 1: Syntax & Style**
```bash
uv run ruff format .
uv run ruff check --fix .
```

**Level 2: Type Safety**
```bash
uv run mypy app/
uv run pyright app/
```

**Level 3: Unit Tests (feature-specific)**
```bash
uv run pytest app/[feature]/tests/ -v
```

**Level 4: Full Test Suite (unit)**
```bash
uv run pytest -v -m "not integration"
```

**Level 5: Server Validation (if Docker running)**
```bash
curl -s http://localhost:8123/health
```

**Success definition:** Levels 1-4 exit code 0, all tests pass, zero errors or warnings. Level 5 optional.

## Dependencies

- Shared utilities used: [list from app/shared/]
- Core modules used: [list from app/core/]
- New dependencies: [any new packages — include `uv add [package]` commands]
- New env vars: [any new environment variables — include `.env.example` updates]

## Known Pitfalls

The executing agent MUST follow all 59 Python anti-pattern rules. These are loaded via `@_shared/python-anti-patterns.md` and cover:
- Type safety (rules 1-10): No assert in production, no object hints, walrus narrowing, schema field additions
- Library integration (rules 11-17): 3-layer untyped lib fix, test import ordering, singleton cleanup
- Testing (rules 18-28): ARG001, dict invariance, list annotations, Field(None) constructors
- Schema safety (rules 29-32): Optional field ripple effects, computed_field, validate-then-ignore
- Infrastructure (rules 33-38): Redis stubs, pipeline sync, lazy imports, background task exceptions
- Security (rules 39-53): datetime shadows, ILIKE escaping, file upload limits, filename sanitization
- Auth & validation (rules 54-59): HTTPBearer 403->401, dependency override leaks, role enumeration, schema validators

**Additional planning-specific rules:**
- **Schema Impact Tracing:** For any task that adds validators or removes/renames response fields, include a sub-step: "Grep for `SchemaName(` and update all constructors and test assertions."
- **Import Completeness:** Every code change that adds a function call MUST also specify the required import if it's not already present.
- **Plan Code Quality:** Code snippets must follow project lint rules. No `except Exception: pass` (Ruff S110). No missing imports.
- **Constrained string fields:** Must use `Literal[...]` types, not bare `str` (rule 54).

## Migration (if applicable)

**Prefer autogenerate when database is running:**
```bash
uv run alembic revision --autogenerate -m "[description]"
uv run alembic upgrade head
```

**When database may not be running:** The plan MUST note that manual migration creation is an acceptable fallback. Include the column types, nullable flags, and foreign keys needed so the executing agent can write the migration by hand if `--autogenerate` fails due to no database connection.

## Notes

[Any additional context: future considerations, known limitations, performance implications, security considerations]

## Pre-Implementation Checklist

The executing agent MUST verify before writing any code:
- [ ] Read all files listed in "Relevant Files" section
- [ ] Reviewed research documentation
- [ ] Understood the solution approach and why alternatives were rejected
- [ ] Clear on task execution order
- [ ] Validation commands are executable in this environment
```

## OUTPUT

1. Save the plan to `.agents/plans/[feature-name].md` (use kebab-case for the filename)
2. Report to the user:
   - Plan file location
   - Summary of what will be created
   - Number of new files and modified files
   - Any architectural decisions made and why (including alternatives rejected)
   - To execute: `/be-execute .agents/plans/[feature-name].md`
