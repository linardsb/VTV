#!/usr/bin/env bash
# Comprehensive security audit runner for VTV platform.
# Usage: ./scripts/security-audit.sh [--level quick|standard|full]
# Levels:
#   quick    (<10s)  - Bandit lint, sensitive files, hardcoded creds
#   standard (~60s)  - Quick + dependency audit, lock integrity, types, convention tests
#   full     (~120s) - Standard + full test suite, Docker check, nginx check

set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

TOTAL=0
PASSED=0
FAILED=0
SKIPPED=0

LEVEL="standard"
while [[ $# -gt 0 ]]; do
    case "$1" in
        --level) LEVEL="$2"; shift 2 ;;
        quick|standard|full) LEVEL="$1"; shift ;;
        *) echo "Usage: $0 [--level quick|standard|full]"; exit 1 ;;
    esac
done

run_check() {
    local name="$1"
    shift
    TOTAL=$((TOTAL + 1))
    printf "${BLUE}[%d] %s${NC}\n" "$TOTAL" "$name"
    local tmpfile
    tmpfile=$(mktemp)
    if bash -c "$*" > /dev/null 2>"$tmpfile"; then
        PASSED=$((PASSED + 1))
        printf "  ${GREEN}PASS${NC}\n"
    else
        FAILED=$((FAILED + 1))
        printf "  ${RED}FAIL${NC}\n"
        if [ -s "$tmpfile" ]; then
            sed 's/^/    /' "$tmpfile"
        fi
    fi
    rm -f "$tmpfile"
}

skip_check() {
    local name="$1"
    local reason="$2"
    TOTAL=$((TOTAL + 1))
    SKIPPED=$((SKIPPED + 1))
    printf "${BLUE}[%d] %s${NC}\n" "$TOTAL" "$name"
    printf "  ${YELLOW}SKIP: %s${NC}\n" "$reason"
}

echo "========================================="
echo "  VTV Security Audit - Level: ${LEVEL}"
echo "========================================="
echo ""

# === Quick Level Checks ===

run_check "Bandit security lint (ruff --select=S)" \
    "uv run ruff check app/ --select=S --no-fix"

run_check "Sensitive file scan" \
    "! git ls-files | grep -E '\\.env$|\\.pem$|\\.key$|credentials\\.|secrets\\.' | grep -v '.env.example' | grep -v '.env.local.example'"

run_check "Hardcoded postgres credentials" \
    "! grep -rn 'postgres:postgres@' app/ --include='*.py' --include='*.yml' --include='*.yaml' 2>/dev/null | grep -v test_ | grep -v tests/"

if [[ "$LEVEL" == "quick" ]]; then
    echo ""
    echo "========================================="
    printf "  Results: ${GREEN}%d passed${NC}, ${RED}%d failed${NC}, ${YELLOW}%d skipped${NC} / %d total\n" \
        "$PASSED" "$FAILED" "$SKIPPED" "$TOTAL"
    echo "========================================="
    exit "$FAILED"
fi

# === Standard Level Checks ===

if command -v uv > /dev/null 2>&1; then
    # CVE-2025-69872: protobuf - no fix available yet (upstream pending, re-check monthly)
    # CVE-2024-23342: ecdsa - transitive dep, no direct usage, low risk
    run_check "Dependency audit (pip-audit)" \
        "uv run pip-audit --desc --ignore-vuln CVE-2025-69872 --ignore-vuln CVE-2024-23342"

    run_check "Lock file integrity (uv lock --check)" \
        "uv lock --check"

    run_check "Type safety - mypy" \
        "uv run mypy app/"

    run_check "Type safety - pyright" \
        "uv run pyright app/"

    run_check "Security convention tests" \
        "uv run pytest app/tests/test_security.py -v --tb=short -q"
else
    skip_check "Dependency audit" "uv not found"
    skip_check "Lock file integrity" "uv not found"
    skip_check "Type safety - mypy" "uv not found"
    skip_check "Type safety - pyright" "uv not found"
    skip_check "Security convention tests" "uv not found"
fi

if [[ "$LEVEL" == "standard" ]]; then
    echo ""
    echo "========================================="
    printf "  Results: ${GREEN}%d passed${NC}, ${RED}%d failed${NC}, ${YELLOW}%d skipped${NC} / %d total\n" \
        "$PASSED" "$FAILED" "$SKIPPED" "$TOTAL"
    echo "========================================="
    exit "$FAILED"
fi

# === Full Level Checks ===

if command -v uv > /dev/null 2>&1; then
    run_check "Full test suite (unit)" \
        "uv run pytest -v -m 'not integration' --tb=short -q"
else
    skip_check "Full test suite" "uv not found"
fi

if [[ -f "scripts/check-docker-security.py" ]]; then
    run_check "Docker Compose security" \
        "python3 scripts/check-docker-security.py"
else
    skip_check "Docker Compose security" "scripts/check-docker-security.py not found"
fi

if [[ -f "scripts/check-nginx-security.py" ]]; then
    run_check "nginx security headers" \
        "python3 scripts/check-nginx-security.py"
else
    skip_check "nginx security headers" "scripts/check-nginx-security.py not found"
fi

echo ""
echo "========================================="
printf "  Results: ${GREEN}%d passed${NC}, ${RED}%d failed${NC}, ${YELLOW}%d skipped${NC} / %d total\n" \
    "$PASSED" "$FAILED" "$SKIPPED" "$TOTAL"
echo "========================================="
exit "$FAILED"
