---
description: Research codebase and create a self-contained implementation plan
argument-hint: [feature-description] e.g. add obsidian search tool
allowed-tools: Read, Glob, Grep, Write
---

This command researches the VTV codebase and produces a detailed implementation plan that another agent (or `/execute`) can follow without any additional context. It reads CLAUDE.md, PRD.md, and existing features to understand conventions, identifies reusable shared utilities, finds similar features to use as code patterns, and designs the complete vertical slice with explicit file paths, exact code patterns, and per-task validation commands.

If the feature involves AI agent tools (detected by keywords like "tool", "agent", "Obsidian", "transit"), the plan includes tool-specific sections: agent-optimized docstrings following the 5-principle format, dry-run support design, token efficiency considerations, and composition chains showing how the tool fits into multi-step workflows. This ensures agent tools are built with LLM consumption patterns in mind from the start.

The plan is saved to `plans/{feature-name}.md` and is intentionally self-contained — it includes everything needed for execution without referencing the original conversation. This means `/execute` can run it in a completely separate session. After the plan is created, review it, then run `/execute plans/{feature-name}.md` to implement it.

# Planning — Create Feature Implementation Plan

## INPUT

**Feature request:** $ARGUMENTS

You are creating a detailed implementation plan that ANOTHER AGENT will execute without seeing this conversation. The plan must be completely self-contained with explicit file paths, exact code patterns, and unambiguous steps.

**The test:** Could a developer who knows nothing about this feature implement it from the plan alone? If yes, an agent can too.

## PROCESS

### 1. Understand the feature

- Read `CLAUDE.md` for architecture rules and conventions
- Read `PRD.md` to understand how this feature fits the product vision
- Read `mvp-tool-designs.md` if the feature relates to agent tools
- **If this is an AI agent tool:** flag it as tool planning (see "Agent Tool Planning" section below)
- Explore existing features under `app/` to understand established patterns
- Read `app/main.py` to see current router registrations

### 2. Research existing code

- Identify which existing modules this feature will interact with
- Check `app/shared/` for reusable utilities (TimestampMixin, PaginationParams, PaginatedResponse, ErrorResponse, get_db(), get_logger())
- Find similar features and note **exact file paths with line ranges** for patterns the executing agent must follow
- Check `alembic/versions/` for migration context
- Research any external libraries/APIs needed — capture documentation URLs with specific sections

### 3. Agent Tool Planning (if applicable)

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

### 4. Design the vertical slice

Plan the complete feature following VTV's vertical slice structure:
- `app/[feature]/models.py` — SQLAlchemy models inheriting `Base` and `TimestampMixin`
- `app/[feature]/schemas.py` — Pydantic schemas for request/response
- `app/[feature]/routes.py` — FastAPI router with typed endpoints
- `app/[feature]/service.py` — Business logic with structured logging
- `app/[feature]/tests/` — Unit and integration tests

### 5. Write the plan

Create the plan file at `plans/[feature-name].md` using this template:

```markdown
# Plan: [Feature Name]

## Feature Description

[2-3 paragraphs: what this feature does, the problem it solves, and user-facing behavior. Be specific about system impact.]

## User Story

As a [specific type of user]
I want to [specific action/capability]
So that [specific benefit/outcome]

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

### Task 1: [Foundational Task Name]
**File:** `[exact/path/to/file.py]` (create new)
**Action:** Create

Create [schema/model/utility]:
- Define [Specific class name] with:
  - `field_name: Type` — [purpose and validation rules]
  - `field_name: Type` — [purpose and validation rules]
- Include Google-style docstring
- All fields have type annotations
- Follow pattern from: `[reference-file.py]` (lines X-Y)

**Per-task validation:**
- `uv run mypy [exact file path]` passes with 0 errors

---

### Task 2: [Implementation Task Name]
**File:** `[exact/path/to/file.py]` (create new OR modify existing)
**Action:** Create/Modify

Implement [specific function/class]:
- Function signature: `async def function_name(param: Type) -> ReturnType:`
- Use [Specific model] from Task 1
- Add structured logging:
  - `logger.info("[feature].action_started", **context)`
  - `logger.info("[feature].action_completed", **context)`
  - `logger.error("[feature].action_failed", exc_info=True, error=str(e), error_type=type(e).__name__)`
- Follow pattern from: `[reference-file.py]` (lines X-Y)

**Per-task validation:**
- `uv run ruff check [exact file path]` passes
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
- `uv run pytest app/[feature]/tests/ -v` — all tests pass

---

### Task N: Register Router & Final Integration
**File:** `app/main.py`
**Action:** Modify

Add:
```python
from app.[feature].routes import router as [feature]_router
app.include_router([feature]_router)
```

---

## Migration (if applicable)

```bash
uv run alembic revision --autogenerate -m "[description]"
uv run alembic upgrade head
```

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

## Final Validation

Run ALL commands in order — every one must pass with 0 errors:

```bash
# 1. Format (auto-fixes)
uv run ruff format .

# 2. Lint (must pass)
uv run ruff check .

# 3. Type check — MyPy (must pass)
uv run mypy app/

# 4. Type check — Pyright (must pass)
uv run pyright app/

# 5. All tests (must pass)
uv run pytest -v
```

**Success definition:** All commands exit code 0, all tests pass, zero errors or warnings.

## Dependencies

- Shared utilities used: [list from app/shared/]
- Core modules used: [list from app/core/]
- New dependencies: [any new packages — include `uv add [package]` commands]

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

1. Save the plan to `plans/[feature-name].md` (use kebab-case for the filename)
2. Report to the user:
   - Plan file location
   - Summary of what will be created
   - Number of new files and modified files
   - Any architectural decisions made and why (including alternatives rejected)
   - To execute: `/execute plans/[feature-name].md`
