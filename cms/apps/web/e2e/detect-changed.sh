#!/usr/bin/env bash
# Detect which e2e test files to run based on changed frontend files.
# Maps git-changed paths → relevant e2e test files.
# Usage: ./e2e/detect-changed.sh [base-ref]
#   base-ref defaults to HEAD (unstaged + staged changes)
#   pass "main" to compare against main branch

set -euo pipefail

BASE="${1:-HEAD}"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
WEB_DIR="$(dirname "$SCRIPT_DIR")"
REPO_ROOT="$(cd "$WEB_DIR/../../.." && pwd)"

# Get changed files relative to repo root
if [ "$BASE" = "HEAD" ]; then
  CHANGED=$(cd "$REPO_ROOT" && git diff --name-only HEAD 2>/dev/null; git diff --name-only --cached 2>/dev/null; git ls-files --others --exclude-standard 2>/dev/null)
else
  CHANGED=$(cd "$REPO_ROOT" && git diff --name-only "$BASE"...HEAD 2>/dev/null)
fi

# Only care about CMS frontend files
CMS_CHANGED=$(echo "$CHANGED" | grep "^cms/apps/web/" | sort -u || true)

if [ -z "$CMS_CHANGED" ]; then
  echo ""
  exit 0
fi

TESTS=""

# Map changed paths to test files
add_test() {
  local test_file="$1"
  if [ -f "$SCRIPT_DIR/$test_file" ] && ! echo "$TESTS" | grep -q "$test_file"; then
    TESTS="$TESTS e2e/$test_file"
  fi
}

while IFS= read -r file; do
  case "$file" in
    # Feature-specific components and pages
    *components/routes/*|*app/*/routes/*)
      add_test "routes.spec.ts" ;;
    *components/stops/*|*app/*/stops/*)
      add_test "stops.spec.ts" ;;
    *components/schedules/*|*app/*/schedules/*)
      add_test "schedules.spec.ts" ;;
    *components/documents/*|*app/*/documents/*)
      add_test "documents.spec.ts" ;;
    *components/dashboard/*|*app/*/\(dashboard\)/page.tsx)
      add_test "dashboard.spec.ts" ;;

    # Auth and login
    *auth.ts|*app/*/login/*)
      add_test "login.noauth.spec.ts"
      add_test "auth.setup.ts" ;;

    # Navigation and layout
    *app-sidebar*|*middleware.ts|*app/*/layout.tsx)
      add_test "navigation.spec.ts" ;;

    # Shared code affects everything
    *components/ui/*|*lib/utils.ts|*lib/*-client.ts|*hooks/*|*types/*)
      add_test "routes.spec.ts"
      add_test "stops.spec.ts"
      add_test "schedules.spec.ts"
      add_test "documents.spec.ts"
      add_test "dashboard.spec.ts"
      add_test "navigation.spec.ts" ;;

    # i18n changes affect everything
    *messages/*.json)
      add_test "routes.spec.ts"
      add_test "stops.spec.ts"
      add_test "schedules.spec.ts"
      add_test "documents.spec.ts"
      add_test "dashboard.spec.ts"
      add_test "navigation.spec.ts" ;;
  esac
done <<< "$CMS_CHANGED"

echo "$TESTS" | xargs
