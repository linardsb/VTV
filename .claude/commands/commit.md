---
description: Stage files and create a conventional commit with safety checks
argument-hint: [file1] [file2] ... (optional, commits all changes if empty)
allowed-tools: Bash(git status:*), Bash(git diff:*), Bash(git add:*), Bash(git commit:*), Bash(git log:*), Bash(git push:*), Bash(uv run ruff format:*), Bash(uv run ruff check:*), Bash(uv run pre-commit:*), Bash(uv run detect-secrets:*)
---

Review changes, scan for secrets, stage explicitly, and create a conventional commit.

# Commit — Conventional Git Commit

## INPUT

**Files to commit:** $ARGUMENTS (if empty, commit all changes)

## PROCESS

### 1. Review changes

```
!git status
```

```
!git diff --stat
```

```
!git log --oneline -5
```

### 2. Safety checks

- STOP if any of these files appear in the changes: `.env`, `*.pem`, `*.key`, `credentials.*`, `secrets.*`
- Warn the user and ask for confirmation before proceeding
- Run a quick security lint on staged Python files (same as pre-commit hook):
  ```bash
  git diff --cached --name-only --diff-filter=ACMR | grep '\.py$' | xargs -r uv run ruff check --select=S --no-fix
  ```
  If violations found, STOP and report them. This catches Bandit-level issues even when the pre-commit hook isn't installed.
- For frontend changes, run quick pattern scan on staged `.ts`/`.tsx` files:
  ```bash
  git diff --cached --name-only --diff-filter=ACMR | grep -E '\.(ts|tsx)$' | xargs -r grep -n 'dangerouslySetInnerHTML\|localStorage.*token\|localStorage.*auth'
  ```
  If violations found, WARN the user (soft gate for commit, hard gate in `/fe-validate`).
- **Note:** The inline checks above work even WITHOUT the pre-commit hook. If the hook IS installed (`make install-hooks`), it provides additional coverage (secrets detection, hardcoded postgres credentials).

### 3. Pre-format and stage files

If specific files were provided in $ARGUMENTS:
- Stage only those files: `git add [file1] [file2] ...`

If no files specified:
- Review all changes and stage appropriate files: `git add [specific files]`
- Do NOT use `git add -A` or `git add .` — always stage files explicitly

### 4. Pre-commit convergence loop

Run pre-commit hooks and handle any auto-modifications. This prevents commit failures from formatting or secrets baseline drift.

```bash
uv run pre-commit run --all-files
```

If hooks modify files (exit code 1 with "files were modified by this hook"):
1. Stage ALL files modified by hooks: `git add [modified files]` (always include `.secrets.baseline` if changed)
2. Re-run: `uv run pre-commit run --all-files`
3. Repeat until all hooks pass (max 3 iterations)

If detect-secrets keeps failing due to `generated_at` timestamp churn:
1. Regenerate baseline from scratch: `uv run detect-secrets scan --exclude-files '(\.env\.example|\.env\.production\.example|uv\.lock|pnpm-lock\.yaml)$' > .secrets.baseline`
2. Stage it: `git add .secrets.baseline`
3. Re-run hooks to confirm

**All hooks MUST pass before proceeding to commit. Do not skip this step.**

### 5. Create commit message

Use **conventional commit** format with VTV-relevant scopes:

```
type(scope): short description

[optional body with more detail]

Co-Authored-By: Claude <noreply@anthropic.com>
```

**Types:** `feat`, `fix`, `refactor`, `test`, `docs`, `chore`, `ci`, `style`

**VTV Scopes:** `core`, `shared`, `agent`, `transit`, `obsidian`, `config`, `db`, `health`, `cms`, or feature name

**Rules:**
- Subject line under 72 characters
- Imperative mood ("add feature" not "added feature")
- Body explains WHY, not WHAT (the diff shows what)

### 6. Commit

Use HEREDOC format for the commit message:

```bash
git commit -m "$(cat <<'EOF'
type(scope): description

Optional body.

Co-Authored-By: Claude <noreply@anthropic.com>
EOF
)"
```

### 7. Push

Do NOT push automatically. Report that changes are committed locally. User can push with `git push`.

## OUTPUT

Report:
- Commit hash (short)
- Commit message used
- Files included
- Branch name
- Push status: local only (user can `git push` when ready)
