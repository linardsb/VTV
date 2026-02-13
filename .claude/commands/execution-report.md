---
description: Generate report comparing implementation against the plan
argument-hint: [plan-file] e.g. .agents/plans/user-auth.md
---

Analyze what was actually implemented and compare against the plan.

# Execution Report

## INPUT

Plan file: $ARGUMENTS

## PROCESS

### 1. Read the plan

Read @$ARGUMENTS to understand what was intended.

### 2. Analyze implementation

- Check git diff to see what was actually changed
- Compare files created/modified against plan's task list
- Identify any divergences

### 3. Assess validation results

Check recent validation output or run:

```bash
uv run ruff check . --statistics 2>&1 | tail -5
uv run pytest -v --tb=no -q 2>&1 | tail -5
```

### 4. Write report

Save to `.agents/execution-reports/[feature-name].md`:

```markdown
# Execution Report: [Feature Name]

**Plan:** [path]
**Date:** [date]

## Files
- Created: [list with paths]
- Modified: [list with paths]

## Validation Results
- Ruff format: PASS/FAIL
- Ruff check: PASS/FAIL
- MyPy: PASS/FAIL
- Pyright: PASS/FAIL
- Pytest: PASS/FAIL [X passed, Y failed]

## What Went Well
- [concrete examples]

## Challenges
- [what was difficult, why]

## Divergences from Plan
| Planned | Actual | Reason | Type |
|---------|--------|--------|------|
| [spec] | [impl] | [why] | Better approach / Plan gap / Security / Performance |

## Skipped Items
- [what, why]

## Recommendations
- Planning improvements: [suggestions]
- Execute improvements: [suggestions]
- CLAUDE.md additions: [suggestions]
```

## OUTPUT

- Report saved to `.agents/execution-reports/[feature-name].md`
- Summary of divergences and key learnings
- **Next step:** `/system-review .agents/plans/X.md .agents/execution-reports/X.md`
