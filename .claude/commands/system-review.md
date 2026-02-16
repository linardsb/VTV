---
description: Analyze implementation vs plan for process improvements
argument-hint: [plan-file] [execution-report] e.g. .agents/plans/auth.md .agents/execution-reports/auth.md
allowed-tools: Read, Glob, Grep, Write
---

Process review — find bugs in the PROCESS, not the code.

@.claude/commands/CLAUDE.md

# System Review

## INPUT

**Arguments:** $ARGUMENTS

Parse two values from the arguments:
- **Plan file** (required): first argument — path to the plan (e.g., `.agents/plans/auth.md`)
- **Execution report** (required): second argument — path to the report (e.g., `.agents/execution-reports/auth.md`)

## PROCESS

### 1. Read artifacts

Read the plan ($1) and execution report ($2) completely.

### 2. Classify divergences

For each divergence in the execution report:

**Good (justified):**
- Plan assumption was wrong
- Better pattern discovered during implementation
- Security or performance concern required change

**Bad (problematic):**
- Ignored plan constraints
- Took shortcuts creating tech debt
- Misunderstood requirements

### 3. Trace root causes

For each bad divergence: was the plan unclear? Context missing? Validation missing? Manual step that should be automated?

**Root cause categories:**
- Unclear plan → update `/be-planning` template
- Missing context → update `/be-prime` or `/be-prime-tools`
- Missing validation → update `/be-validate`
- Manual process repeated → create new command

### 4. Generate improvements

Specific, actionable changes to:
- **CLAUDE.md** — new patterns or anti-patterns to document
- **Commands** — missing steps or unclear instructions
- **New commands** — manual processes that should be automated

## OUTPUT

Save to `.agents/system-reviews/[feature-name]-review.md`:

```markdown
# System Review: [Feature Name]

**Alignment Score:** X/10
- 9-10: Plan followed precisely, minimal justified divergences
- 7-8: Minor divergences, all justified
- 5-6: Notable divergences, some unjustified
- 3-4: Significant gaps between plan and execution
- 1-2: Plan was largely abandoned

## Divergence Analysis
[Classification of each divergence with root cause]

## Pattern Compliance
- [ ] Type safety maintained
- [ ] Structured logging follows convention
- [ ] VSA boundaries respected
- [ ] Tests written alongside code
- [ ] Agent docstrings follow 5-principle format (if applicable)

## Recommended Actions
1. [Specific text to add/change in CLAUDE.md, commands, or processes]
2. [...]

## Key Learnings
- [What to carry forward]
```

- Report summary
- **Next step:** Apply recommended actions manually
