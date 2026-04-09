---
description: Scan frontend plan target files for fragile patterns before execution
argument-hint: [plan-file-path] e.g. .agents/plans/fe-fleet-telemetry.md
allowed-tools: Read, Glob, Grep, Edit, Bash(pnpm:*)
---

# Frontend Preflight Check — Scan & Fix Known Friction Patterns

Run this **before** `/fe-execute` to catch and auto-fix patterns that historically cause fix cycles.

## Step 1: Parse the Plan

Read the implementation plan file (from `$ARGUMENTS`, or find the most recent `.agents/plans/fe-*.md`).
Extract:
- All file paths listed under "Files to Create/Modify" or "Implementation Steps"
- All components/hooks/functions being added or modified
- What changes each file is getting (new props, new API fields, new hook return values)

## Step 2: Scan & Fix Fragile Patterns in Related Tests

For each target file under `cms/apps/web/src/`, find related test files:

```
Glob: cms/apps/web/e2e/**/*.spec.ts
Glob: cms/apps/web/src/**/__tests__/*.test.{ts,tsx}
```

### 2a: Hardcoded Count Assertions
```
Grep pattern: "toHaveLength\(\d+\)|\.length\)\.toBe\(\d+\)|expect.*==.*\d+"
```
**Assess:** Cross-reference with the plan — will this count change?

**Auto-fix if affected:** Replace with flexible assertion:
- `expect(items).toHaveLength(5)` → `expect(items.length).toBeGreaterThanOrEqual(5)`

### 2b: Snapshot Tests
```
Grep pattern: "toMatchInlineSnapshot|toMatchSnapshot"
```
**Assess:** Does the plan modify the component's render output?

**Auto-fix if affected:** Delete the stale snapshot so it regenerates on next test run:
- For `toMatchInlineSnapshot`: remove the inline snapshot string argument
- For `toMatchSnapshot`: flag the corresponding `.snap` file for regeneration

### 2c: Mock Return Values with Fixed Shape
```
Grep pattern: "mockReturnValue\(|mockResolvedValue\("
```
**Assess:** Does the plan change the API response shape or hook return type?

**Auto-fix if affected:** Add the new fields to the mock return value with sensible defaults matching the plan's new schema.

## Step 3: Scan & Fix Target Files for Fragile Patterns

For each file being **modified** (not created):

### 3a: `as any` Casts
```
Grep pattern: "as any"
```
**Assess:** Will the plan change the type that `as any` is hiding?

**Auto-fix if affected:** Replace `as any` with the correct type from the plan. If the correct type isn't clear, replace with `as unknown as CorrectType` and add a `// TODO: remove cast after types stabilize` comment.

### 3b: Destructured Props/Hook Returns
```
Grep pattern: "^\s*const \{.*\} = (props|use\w+)"
```
**Assess:** Does the plan add new props or change hook return shape?

**Auto-fix if affected:** Add the new destructured fields at each callsite where they're needed by the plan.

### 3c: API Response Types
```
Grep pattern: "interface.*Response|type.*Response"
```
**Assess:** Does the plan change backend API responses?

**Auto-fix if affected:** Add the new fields to the TypeScript interface/type to match the backend changes described in the plan.

### 3d: Hardcoded i18n Strings (VTV-specific)
```
Grep pattern in .tsx files: ">[A-Z][a-z].*</" (JSX text content that should be i18n keys)
```
**Assess:** Does the plan add new user-visible text that should use `useTranslations`?

**Flag for review:** Mark any hardcoded strings in files the plan will modify — they should be converted to `t('key')` calls during `/fe-execute`.

## Step 4: TypeScript Baseline

Run tsc on the frontend to capture the **before** error count:

```bash
cd cms && pnpm --filter @vtv/web type-check 2>&1 | tail -10
```

Save the error count. After `/fe-execute`, compare against this baseline.

## Step 5: Report

Output a preflight report:

```
## Frontend Preflight Report for {plan name}

### Fixes Applied

| File | Line | Pattern | What Changed |
|------|------|---------|--------------|
| use-fleet.test.ts | 42 | `toHaveLength(12)` | Changed to `toBeGreaterThanOrEqual(12)` — plan adds devices |
| types/api.ts | 15 | `interface FleetResponse` | Added `telemetryStatus: string` — matches backend change |
| ... | ... | ... | ... |

### Patterns Found (Safe — No Fix Needed)

| File | Line | Pattern | Why Safe |
|------|------|---------|----------|
| routes.spec.ts | 20 | `toHaveLength(3)` | Plan doesn't affect route count |
| ... | ... | ... | ... |

### i18n Flags
| File | Line | Content | Action Needed |
|------|------|---------|---------------|
| FleetTable.tsx | 45 | `>Status<` | Convert to `t('fleet.status')` during /fe-execute |

### TypeScript Baseline
- Frontend: {N} errors before implementation (all pre-existing)
- Run `cd cms && pnpm --filter @vtv/web type-check` after /fe-execute — new errors above {N} are regressions

### Status
{If fixes applied}: {N} patterns auto-fixed. Proceed with /fe-execute.
{If clean}: No friction patterns found. Proceed with /fe-execute.
```

## Rules

- **Auto-fix** any pattern that WILL break based on the plan's changes
- **Skip** patterns that are unaffected by the plan (mark as "safe" in report)
- Use judgement: read the plan to understand what's changing before deciding fix vs safe
- Run `cd cms && npx prettier --write {changed_files}` after any fixes to maintain formatting
- Do NOT run the full test suite — only scan and fix test file contents
- Focus on the specific files in the plan, not the entire codebase
- Report everything (fixes applied + safe patterns + i18n flags) for full visibility
