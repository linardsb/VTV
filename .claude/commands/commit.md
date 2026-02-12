---
description: Create git commit with conventional message format
argument-hint: [file1] [file2] ... (optional, defaults to all staged/unstaged changes)
allowed-tools: Bash(git status:*), Bash(git diff:*), Bash(git add:*), Bash(git commit:*), Bash(git log:*)
---

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

### 3. Stage files

If specific files were provided in $ARGUMENTS:
- Stage only those files: `git add [file1] [file2] ...`

If no files specified:
- Review all changes and stage appropriate files: `git add [specific files]`
- Do NOT use `git add -A` or `git add .` — always stage files explicitly

### 4. Create commit message

Use **conventional commit** format with VTV-relevant scopes:

```
type(scope): short description

[optional body with more detail]

Co-Authored-By: Claude <noreply@anthropic.com>
```

**Types:** `feat`, `fix`, `refactor`, `test`, `docs`, `chore`, `ci`, `style`

**VTV Scopes:** `core`, `shared`, `agent`, `transit`, `obsidian`, `config`, `db`, `health`, or feature name

**Rules:**
- Subject line under 72 characters
- Imperative mood ("add feature" not "added feature")
- Body explains WHY, not WHAT (the diff shows what)

### 5. Commit

Use HEREDOC format for the commit message:

```bash
git commit -m "$(cat <<'EOF'
type(scope): description

Optional body.

Co-Authored-By: Claude <noreply@anthropic.com>
EOF
)"
```

## OUTPUT

Report:
- Commit hash (short)
- Commit message used
- Files included
- Branch name
