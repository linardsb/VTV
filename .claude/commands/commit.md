---
description: Stage files and create a conventional commit with safety checks
argument-hint: [file1] [file2] ... (optional, commits all changes if empty)
allowed-tools: Bash(git status:*), Bash(git diff:*), Bash(git add:*), Bash(git commit:*), Bash(git log:*)
---

This command reviews your changes, performs security checks, and creates a conventional commit. It inspects all staged and unstaged changes, checks recent commit history for message style consistency, and scans for sensitive files (`.env`, `.pem`, `.key`, `credentials.*`, `secrets.*`) — stopping and warning you if any are detected. Files are always staged explicitly by name, never with `git add .` or `git add -A`.

The commit message follows conventional commit format with VTV-specific scopes: `core`, `shared`, `agent`, `transit`, `obsidian`, `config`, `db`, `health`, or the feature name. Types include `feat`, `fix`, `refactor`, `test`, `docs`, `chore`, `ci`, and `style`. The subject line stays under 72 characters in imperative mood, the body explains WHY (not what), and every commit includes a `Co-Authored-By: Claude` trailer.

You can pass specific file paths as arguments to commit only those files, or run without arguments to commit all changes. Use this as the final step after `/validate` passes, or at the end of `/execute` and `/implement-fix` workflows. The command reports the commit hash, message, files included, and branch name.

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
