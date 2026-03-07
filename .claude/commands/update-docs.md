---
description: Update project documentation after a feature is implemented, validated, and committed
argument-hint: [feature-name-or-report-path] e.g. agents or .agents/execution-reports/agents.md
allowed-tools: Read, Edit, Write, Bash(ls:*), Bash(git log:*), Bash(git diff:*)
---

Update all living documentation to reflect a newly implemented feature. Closes the documentation loop after plan → execute → validate → commit.

@CLAUDE.md
@reference/PRD.md
@reference/feature-readme-template.md

# Update Docs — Post-Implementation Documentation Sync

## INPUT

**Feature or report path:** $ARGUMENTS

Resolve the feature name:
- If the argument is a path to an execution report (e.g., `.agents/execution-reports/agents.md`), extract the feature name from the filename
- If the argument is a feature name (e.g., `agents`), use it directly
- The feature directory must exist at `app/{feature}/`

**Prerequisite:** The feature must be fully implemented, validated, and committed. Do NOT run this before `/be-validate` and `/commit` have succeeded.

## PROCESS

### Step 1: Locate Artifacts

Search for existing artifacts in this order:

1. Execution report at `.agents/execution-reports/{feature}.md`
2. Plan at `.agents/plans/{feature}.md`
3. If neither exists, fall back to scanning `app/{feature}/` directly and recent git commits (`git log --oneline -20`) to understand what was built

Record which artifacts were found — later steps adapt based on availability.

### Step 2: Scan Implementation

Read the actual feature code in `app/{feature}/` to extract concrete details:

- **Endpoints** — Read `routes.py`: HTTP methods, paths, response models, status codes
- **Models/Tables** — Read `models.py`: table names, columns, types, constraints, relationships
- **Schemas** — Read `schemas.py`: request/response models, field names, types, validators
- **Business Rules** — Read `service.py`: validation logic, orchestration flows, error conditions
- **Exceptions** — Read `exceptions.py`: custom exception classes and their HTTP status mappings
- **Cross-feature imports** — Note any imports from other `app/{feature}/` directories
- **Shared utilities** — Note any new additions to `app/shared/` or usage of existing shared code
- **Configuration** — Note any new environment variables or settings added to `app/core/config.py`

### Step 3: Update `CLAUDE.md` Project Structure

Read the current root `CLAUDE.md` and update the following sections:

1. **Project Structure tree** — Diff the ASCII tree against the actual `app/` directory. Add the new feature directory in alphabetical order among other features. Keep the `{feature}/` placeholder line for future features.

2. **Shared Utilities section** — If new utilities were added to `app/shared/`, document them following the existing format (module path, class/function name, brief description).

3. **Configuration section** — If new environment variables were added, document them.

4. **Agent Module section** — If agent tools were added or modified, update the tool lists and descriptions.

5. **Slash Commands count** — Update the command count if this update-docs command itself is being added for the first time (should already be done separately).

Only modify sections where actual changes are needed. Do not rewrite unchanged sections.

### Step 4: Update Feature `README.md`

Read `reference/feature-readme-template.md` for the expected format.

Overwrite `app/{feature}/README.md` with real implementation details:

- **Key Flows** — Actual business flows from `service.py` (not placeholder text)
- **Database Schema** — Real table name, columns, types, and constraints from `models.py`
- **Business Rules** — Actual validation rules, constraints, and behaviors from `service.py`
- **Integration Points** — Real cross-feature dependencies found in Step 2
- **API Endpoints** — Real HTTP methods, paths, and descriptions from `routes.py`

If the feature has no database models (e.g., it's a utility or agent-only feature), omit the Database Schema section rather than leaving placeholder text.

### Step 5: Update `docs/TODO.md`

Read `docs/TODO.md` and update the following:

1. **Progress Overview** — Update the percentage bars and descriptions to reflect the new feature (e.g., increment page count, test count, feature list)
2. **Planned Features** — If the feature was listed under "Planned Features", move it to "Completed" with a `[x]` checkbox and add the commit hash and date
3. **Completed section** — Add a new entry under the appropriate subsection (Backend Features, CMS Frontend Pages, or Infrastructure & Tooling) with a one-line description, commit hash, date, and link to the plan document if one exists

Only modify sections where actual changes are needed.

### Step 6: Update `reference/PRD.md`

Search `reference/PRD.md` for the feature name in the MVP scope sections.

- If found in a "planned" or "future" list, update its status to indicate it's implemented
- If the feature doesn't appear in PRD at all, skip this step entirely
- Do NOT add features to the PRD that weren't already listed there

### Step 7: Log Bugs and Fixes

Check the execution report (if it exists from Step 1) for:
- "Challenges" section — issues encountered during implementation
- "Divergences" section — deviations from the plan
- Validation failures that were encountered and fixed

If bugs were found and fixed during implementation:
- Append a `## Bugs Found During Implementation` section to the execution report
- Document each bug: what broke, root cause, how it was fixed
- Format as a table: | Bug | Root Cause | Fix Applied |

If no execution report exists but bugs are known from git history:
- Create a lightweight execution report at `.agents/execution-reports/{feature}.md` with just the bugs section

If no bugs were found, skip this step.

### Step 8: Summary Diff

Present a summary of every file that was modified:

```
Files Updated:
- CLAUDE.md — [what changed, e.g., "Added agents/ to project structure tree"]
- app/{feature}/README.md — [what changed, e.g., "Replaced scaffold placeholders with real endpoints and schema"]
- docs/TODO.md — [what changed, e.g., "Moved feature to Completed, updated progress bars"]
- reference/PRD.md — [what changed, or "No changes needed"]
- .agents/execution-reports/{feature}.md — [what changed, or "No bugs to log"]
```

## OUTPUT

**Documentation updated for:** `{feature}`

**Files modified:**
- [list each file with a one-line description of what changed]

**Files unchanged (no updates needed):**
- [list any files that were checked but didn't need changes]

**Next steps:**
- Review the changes: `git diff`
- Commit documentation updates: `/commit`
