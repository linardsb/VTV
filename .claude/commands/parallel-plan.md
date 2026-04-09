---
description: Parallel research + test scout + pyright baseline, then merge into implementation plan
argument-hint: [feature-description] e.g. add driver availability tracking
allowed-tools: Read, Glob, Grep, Write, Agent, Bash(uv run pyright:*), Bash(uv run mypy:*), mcp__jcodemunch__get_repo_outline, mcp__jcodemunch__get_file_outline, mcp__jcodemunch__get_file_tree, mcp__jcodemunch__search_symbols, mcp__jcodemunch__find_references, mcp__jdocmunch__search_sections, mcp__jdocmunch__get_section
---

@CLAUDE.md
@.claude/commands/_shared/python-anti-patterns.md
@.claude/commands/_shared/security-contexts.md

# Parallel Plan — Concurrent Research + Planning

Replaces the sequential `/be-prime` → `/be-planning` flow with parallel agent execution.
Three agents run simultaneously, then results merge into a single implementation plan.

## Input

The user provides:
- **Feature description** — what to build (from `$ARGUMENTS`)
- **Plan filename** — where to save (default: `.agents/plans/{feature-slug}.md`)

## Execution

Launch **three agents in parallel** using the Agent tool:

### Agent 1: Researcher (subagent_type: Explore)
```
Research the VTV backend codebase for implementing: {feature description}

Using jCodeMunch (repo from list_repos):
1. get_file_tree({ "path_prefix": "app/" }) — map backend VSA features
2. search_symbols for functions/classes related to: {feature keywords}
3. get_file_outline on the most relevant files found
4. find_references for key symbols that will need modification
5. get_file_outline on app/core/config.py, app/core/exceptions.py, app/shared/schemas.py

Using jDocMunch (repo: local/VTV):
1. search_sections({ "query": "{feature keywords}", "doc_path": "CLAUDE.md" }) — architecture context
2. search_sections({ "query": "{feature keywords}", "doc_path": "reference/PRD.md" }) — product context

Write a structured research summary including:
- Relevant files and their roles (with file:line references)
- Key functions/classes to modify or extend
- Existing VSA patterns to follow (identify a reference feature)
- Config/settings that apply
- Dependencies and imports needed
- Shared utilities available (TimestampMixin, PaginationParams, escape_like, get_logger, etc.)
```

### Agent 2: Test Scout (subagent_type: Explore)
```
Find all test files and patterns related to: {feature description}

1. Glob for test files in related feature directories: app/{feature}/tests/test_*.py
2. Read test conftest.py files for existing fixtures and factory functions
3. Search for test patterns using Grep:
   - Existing mock patterns for the feature area
   - Factory functions (make_*, create_*)
   - Integration test markers (@pytest.mark.integration)
4. Check for security convention test patterns in app/tests/test_security.py
5. Check for similar feature test structures to use as templates

Write a structured summary including:
- Related test files found
- Existing fixtures and factories available
- Mock patterns used in this area
- Security convention test patterns relevant to this feature
- Test conventions specific to this feature area
```

### Agent 3: Pyright Baseline (subagent_type: general-purpose)
```
Run pyright and mypy baseline on files likely affected by: {feature description}

1. Identify the target directory: app/{feature}/
2. Run: uv run pyright app/{feature}/ 2>&1 | tail -20
3. Count current errors
4. Also run: uv run mypy app/{feature}/ 2>&1 | tail -20
5. Report the baseline error counts

If the feature directory doesn't exist yet (new feature), run on the most similar existing feature directory.
```

## After All Agents Complete

Combine all three agent results and write the implementation plan following the `/be-planning` format:

```markdown
# Plan: {Feature Name}

## Context
{Why this change is needed — from user's feature description}

## Security Context Assessment
{Which of CTX-AUTH/RBAC/FILE/AGENT/INFRA/INPUT apply to this feature — from _shared/security-contexts.md}

## Research Summary
{From Agent 1 — relevant files, VSA patterns, dependencies}

## Test Landscape
{From Agent 2 — existing tests, fixtures, security convention patterns}

## Type Check Baseline
{From Agent 3 — current pyright/mypy error counts for target files}

## Files to Create/Modify
| Action | File | Purpose |
|--------|------|---------|
| CREATE | `app/{feature}/...` | {what it does} |
| UPDATE | `app/main.py` | Register router |

## Implementation Steps
1. {Step with exact code or clear instructions}
   **Validation:** `uv run ruff format {file} && uv run ruff check --fix {file} && uv run pyright {file}`
2. ...

## Preflight Warnings
{Any hardcoded assertions, tuple unpacking, or fragile patterns found by Agent 2 in existing tests}

## Security Checklist
For every new/modified endpoint:
- [ ] `get_current_user` or `require_role()` dependency
- [ ] `@limiter.limit()` rate limiting
- [ ] Input validation via Pydantic schemas
- [ ] Error responses use `AppError` (no internal type leakage)
- [ ] `escape_like()` for any ILIKE queries

## Verification
- [ ] `make check` passes (lint + types + tests)
- [ ] `make security-audit-quick` passes
- [ ] New endpoints have auth + rate limiting
- [ ] Pyright errors ≤ baseline ({N} errors before)
- [ ] Security convention tests pass: `uv run pytest app/tests/test_security.py -v`
```

Save to `.agents/plans/{feature-slug}.md`.

## Rules

- All three agents MUST run in parallel — do not wait for one before starting another
- The plan file must not exceed 700 lines (use compact descriptions, tables, `file:line` refs)
- Include the pyright baseline in the plan so `/be-execute` can compare against it
- Follow VTV's VSA pattern: schemas → models → repository → service → exceptions → routes → tests
- Auto-detect agent tool features (keywords: tool, agent, MCP, Obsidian, transit) and add tool-specific sections if applicable
- Security contexts from `_shared/security-contexts.md` must be assessed for every plan
- Follow all conventions from `_shared/python-anti-patterns.md`
