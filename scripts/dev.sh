#!/usr/bin/env bash
set -euo pipefail

# === Colors & helpers ===
GREEN='\033[0;32m'; RED='\033[0;31m'; YELLOW='\033[0;33m'; CYAN='\033[0;36m'; BOLD='\033[1m'; NC='\033[0m'
ok()   { echo -e "  ${GREEN}✓${NC} $1"; }
fail() { echo -e "  ${RED}✗${NC} $1"; exit 1; }
info() { echo -e "  ${YELLOW}…${NC} $1"; }

# === Phase 1: Cleanup stale processes on ports ===
cleanup_port() {
  local port=$1
  local pids
  pids=$(lsof -ti :"$port" 2>/dev/null || true)
  if [ -n "$pids" ]; then
    echo "$pids" | xargs kill -9 2>/dev/null || true
    sleep 0.5
  fi
}

# === Phase 3: Wait for Docker container health ===
wait_for_container() {
  local container=$1 timeout=$2
  local elapsed=0
  while true; do
    local health
    health=$(docker inspect --format='{{.State.Health.Status}}' "$container" 2>/dev/null || echo "missing")
    [ "$health" = "healthy" ] && return 0
    [ "$health" = "unhealthy" ] && fail "$container is unhealthy — check: docker logs $container"
    sleep 1
    elapsed=$((elapsed + 1))
    [ $elapsed -lt "$timeout" ] || fail "$container not healthy after ${timeout}s"
  done
}

# === Phase 4: Wait for HTTP endpoint ===
wait_for_url() {
  local url=$1 timeout=$2 label=$3
  local elapsed=0
  while ! curl -sf "$url" >/dev/null 2>&1; do
    sleep 1
    elapsed=$((elapsed + 1))
    [ $elapsed -lt "$timeout" ] || fail "$label not ready after ${timeout}s"
  done
}

# === Trap: kill children on exit ===
BE_PID="" FE_PID="" CLEANED_UP=false
cleanup() {
  [ "$CLEANED_UP" = true ] && return
  CLEANED_UP=true
  echo ""
  info "Shutting down..."
  [ -n "$FE_PID" ] && kill "$FE_PID" 2>/dev/null || true
  [ -n "$BE_PID" ] && kill "$BE_PID" 2>/dev/null || true
  wait 2>/dev/null || true
  ok "All processes stopped"
}
trap cleanup EXIT INT TERM

# === Main ===
echo ""
echo -e "${BOLD}VTV Dev Environment${NC}"
echo "═══════════════════"

# Phase 1: Kill stale processes
info "Cleaning stale processes..."
cleanup_port 8123
cleanup_port 3000
ok "Ports 8123, 3000 free"

# Phase 2: Prerequisites
info "Checking prerequisites..."
docker info >/dev/null 2>&1 || fail "Docker is not running"
command -v uv >/dev/null 2>&1 || fail "'uv' not found — install: https://docs.astral.sh/uv/"
command -v pnpm >/dev/null 2>&1 || fail "'pnpm' not found — install: https://pnpm.io/installation"
[ -d "cms/node_modules" ] || fail "Frontend deps missing — run: cd cms && pnpm install"
ok "Prerequisites met"

# Phase 3: Start containers + wait for health
info "Starting PostgreSQL + Redis..."
docker volume create vtv_postgres_data 2>/dev/null || true
AUTH_SECRET=dev-placeholder docker compose up -d db redis 2>/dev/null
wait_for_container "vtv-db-1" 30
wait_for_container "vtv-redis-1" 30
ok "PostgreSQL + Redis healthy"

# Phase 4: Backend
info "Starting backend on :8123..."
uv run uvicorn app.main:app --reload --port 8123 &
BE_PID=$!
wait_for_url "http://localhost:8123/health" 30 "Backend"
ok "Backend ready on :8123 (PID $BE_PID)"

# Phase 5: Frontend (only after backend is confirmed healthy)
info "Starting frontend on :3000..."
(cd cms && pnpm --filter @vtv/web dev) &
FE_PID=$!
wait_for_url "http://localhost:3000" 45 "Frontend"
ok "Frontend ready on :3000 (PID $FE_PID)"

# Phase 6: Status summary
echo ""
echo -e "${BOLD}═══════════════════════════════════${NC}"
echo -e "  ${CYAN}Backend${NC}   http://localhost:8123"
echo -e "  ${CYAN}Frontend${NC}  http://localhost:3000"
echo -e "  ${CYAN}API Docs${NC}  http://localhost:8123/docs"
echo -e "${BOLD}═══════════════════════════════════${NC}"
echo -e "  Press ${BOLD}Ctrl+C${NC} to stop all services"
echo ""

# Keep running until interrupted
wait
