---
description: Scan plan target files for fragile patterns before backend execution
argument-hint: [plan-file-path] e.g. .agents/plans/driver-availability.md
allowed-tools: Read, Glob, Grep, Edit, Bash(uv run ruff:*), Bash(uv run pyright:*), Bash(uv run mypy:*)
---

# Preflight Check — Scan & Fix Known Friction Patterns (Backend)

Run this **before** `/be-execute` to catch and auto-fix patterns that historically cause fix cycles.

## Step 1: Parse the Plan

Read the implementation plan file (from `$ARGUMENTS`, or find the most recent `.agents/plans/*.md` that is NOT prefixed with `fe-`).
Extract:
- All file paths listed under "Files to Create/Modify" or "Implementation Steps"
- All function/class names being added or modified
- What changes each function/file is getting (new parameters, new return fields, new items)

## Step 2: Scan & Fix Hardcoded Assertions in Related Tests

For each target file `app/{feature}/{file}.py`, find its test files:

```
Glob: app/{feature}/tests/test_*.py
```

### 2a: Hardcoded Count Assertions
```
Grep pattern: "== \d+|len\(.+\) == \d+|assert.*count.*== \d+|assert.*\.count\("
```
**Assess:** Cross-reference with the plan — will this count change? (e.g., plan adds a new endpoint → existing count `== 14` becomes wrong). If the count is unaffected by the plan's changes, mark as "safe" and skip.

**Auto-fix if affected:** Replace exact count with `>=` to tolerate additions:
- `assert len(results) == 14` → `assert len(results) >= 14`
- `assert result.count("<td") == 5` → `assert result.count("<td") >= 5`

### 2b: Tuple Unpacking
```
Grep pattern: "^\s+\w+,\s*\w+.*=\s*\w+\("
```
**Assess:** Does the plan change the return signature of the unpacked function?

**Auto-fix if affected:** Add the new variable to the unpacking:
- `a, b, c, d = _parse_variables(...)` → `a, b, c, d, e = _parse_variables(...)` (matching the new return signature from the plan)

### 2c: Hardcoded String Assertions
```
Grep pattern: 'assert.*==.*"[^"]{20,}"'
```
**Assess:** Will the plan change the output string?

**Auto-fix if affected:** Replace with `in` check on the critical substring:
- `assert result == "long exact string..."` → `assert "critical_part" in result`

## Step 3: Scan & Fix Target Files for Fragile Patterns

For each file being **modified** (not created):

### 3a: New Parameter Propagation
For any function whose signature is changing (new parameter added by the plan), `Grep` for all callsites across the codebase.

**Auto-fix:** If the new parameter has a default value (e.g., `slot_counter: dict | None = None`), no callsite changes needed — just verify. If it does NOT have a default, add the parameter with a sensible default to each callsite, or add a default to the function signature itself.

### 3b: Return Tuple Expansion
```
Grep pattern: "-> tuple\[|return \w+, \w+"
```
If the plan adds fields to a return tuple, find all callers.

**Auto-fix:** Update the unpacking at each callsite to include the new field with an appropriate variable name. Add `_ =` for unused fields if the caller doesn't need the new value.

### 3c: Pydantic Field Defaults Without Type Annotations
```
Grep pattern: "Field\(default_factory="
```
**Auto-fix:** If the plan adds new `Field(default_factory=...)`, ensure explicit type annotation is present (required for pyright strict). Add the annotation if missing.

## Step 4: Pyright Baseline

Run pyright on only the target files to capture the **before** error count:

```bash
uv run pyright {space-separated target files} 2>&1 | tail -5
```

Also run mypy:

```bash
uv run mypy {space-separated target files} 2>&1 | tail -5
```

Save the error counts. After `/be-execute`, compare against this baseline to distinguish pre-existing errors from newly introduced ones.

## Step 5: Report

Output a preflight report:

```
## Preflight Report for {plan name}

### Fixes Applied

| File | Line | Pattern | What Changed |
|------|------|---------|--------------|
| test_service.py | 42 | `assert len(results) == 14` | Changed to `>= 14` — plan adds new endpoint |
| ... | ... | ... | ... |

### Patterns Found (Safe — No Fix Needed)

| File | Line | Pattern | Why Safe |
|------|------|---------|----------|
| test_routes.py | 20 | `assert len(response) == 3` | Plan doesn't affect this query |
| ... | ... | ... | ... |

### Type Check Baseline
- Pyright: {N} errors before implementation (all pre-existing)
- MyPy: {N} errors before implementation
- Run `uv run pyright {files}` after /be-execute — new errors above {N} are regressions

### Status
{If fixes applied}: {N} patterns auto-fixed. Proceed with /be-execute.
{If clean}: No friction patterns found. Proceed with /be-execute.
```

## Rules

- **Auto-fix** any pattern that WILL break based on the plan's changes
- **Skip** patterns that are unaffected by the plan (mark as "safe" in report)
- Use judgement: read the plan to understand what's changing before deciding fix vs safe
- Run `uv run ruff format {changed_files}` after any fixes to maintain formatting
- Do NOT run the full test suite — only scan and fix test file contents
- Focus on the specific files in the plan, not the entire codebase
- Report everything (fixes applied + safe patterns) for full visibility
