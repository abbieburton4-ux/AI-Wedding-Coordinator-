#!/usr/bin/env bash
#
# VenueFlow — full-stack dev orchestration.
#
# One command brings up the whole local universe (Postgres + Cloud Tasks emulator
# + FastAPI api + worker + Vite frontend), seeds demo data, and prints how to log
# in. See RUNBOOK.md for full docs.
#
#   scripts/stack.sh up        # build + start everything (default)
#   scripts/stack.sh down      # stop (keep data)
#   scripts/stack.sh reset     # wipe the database and start fresh
#   scripts/stack.sh logs api  # tail logs for a service
#   scripts/stack.sh verify    # quick health check
#
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND_DIR="$REPO_ROOT/backend"
FRONTEND_URL="http://localhost:5173/VenueFlow/"
API_URL="http://localhost:8000"

c_blue()   { printf "\033[34m%s\033[0m\n" "$*"; }
c_green()  { printf "\033[32m%s\033[0m\n" "$*"; }
c_yellow() { printf "\033[33m%s\033[0m\n" "$*"; }
c_red()    { printf "\033[31m%s\033[0m\n" "$*"; }

# Run docker compose from the backend dir (the compose file lives there and its
# build contexts are relative to it).
dc() { ( cd "$BACKEND_DIR" && docker compose "$@" ); }

require_docker() {
  command -v docker >/dev/null 2>&1 || {
    c_red "Docker is not installed. Get Docker Desktop: https://www.docker.com/products/docker-desktop/"
    exit 1
  }
  docker info >/dev/null 2>&1 || {
    c_red "Docker daemon is not running. Start Docker Desktop and retry."
    exit 1
  }
}

check_env() {
  if [ ! -f "$BACKEND_DIR/.env" ]; then
    c_yellow "backend/.env not found — creating it from .env.example."
    cp "$BACKEND_DIR/.env.example" "$BACKEND_DIR/.env" 2>/dev/null || true
  fi
  if ! grep -qE "^GEMINI_API_KEY=AIza" "$BACKEND_DIR/.env" 2>/dev/null; then
    c_yellow "⚠  GEMINI_API_KEY is not set to a Gemini Developer key (AIza…) in backend/.env."
    c_yellow "   The stack still runs, but the AI agents (intake/match/quote) will fail until you add one."
    c_yellow "   Get a key at https://aistudio.google.com/apikey, then set GEMINI_API_KEY=AIza… in backend/.env"
  fi
}

wait_for_api() {
  c_blue "Waiting for the API to become healthy…"
  for _ in $(seq 1 45); do
    if curl -sf "$API_URL/health" >/dev/null 2>&1; then c_green "API healthy."; return 0; fi
    sleep 2
  done
  c_red "API did not become healthy in time. Inspect: scripts/stack.sh logs api"
  return 1
}

print_summary() {
  echo
  c_green "============================================================"
  c_green " VenueFlow is UP"
  c_green "============================================================"
  echo "  Frontend (app):   $FRONTEND_URL"
  echo "  API (Swagger):    $API_URL/docs"
  echo "  Worker:           http://localhost:8001"
  echo "  Postgres:         localhost:5432  (venueflow / venueflow_pass)"
  echo "  Tasks emulator:   localhost:8123"
  echo
  echo "  Log in (no Firebase needed locally) — open the app, then /signup or /login:"
  echo "    • New couple   → 'Create a new couple account'  (→ intake → AI builds the plan)"
  echo "    • Couple demo  → 'Continue as a couple (Priya & David)'"
  echo
  echo "  More: scripts/stack.sh {logs|verify|reset}"
  echo
}

cmd_up() {
  require_docker
  check_env
  c_blue "Building + starting services (db, tasks-emulator, api, worker, frontend)…"
  dc up -d --build
  wait_for_api
  c_blue "The api seeds the vendor catalogue and demo weddings on startup."
  print_summary
}

cmd_down()  { require_docker; c_blue "Stopping services (database volume kept)…"; dc down; }
cmd_reset() { require_docker; c_yellow "Removing containers AND volumes (this wipes the database)…"; dc down -v; cmd_up; }

cmd_logs() {
  require_docker
  if [ -n "${1:-}" ]; then dc logs -f "$1"; else dc logs -f; fi
}

cmd_verify() {
  require_docker
  echo -n "api  /health           : "; curl -s -o /dev/null -w "HTTP %{http_code}\n" "$API_URL/health"
  local tok="mock-couple_2"  # dev mock identity, NOT a real secret
  echo -n "api  /auth/me (couple) : "; curl -s -H "Authorization: Bearer $tok" "$API_URL/api/v1/auth/me"; echo  # gitleaks:allow
  echo -n "api  CORS from :5173   : "; curl -s -o /dev/null -w "HTTP %{http_code}\n" -X OPTIONS "$API_URL/api/v1/weddings/" -H "Origin: http://localhost:5173" -H "Access-Control-Request-Method: GET"
  echo -n "frontend               : "; curl -s -o /dev/null -w "HTTP %{http_code}\n" http://localhost:5173/
  dc ps --format 'table {{.Service}}\t{{.Status}}'
}

usage() {
  cat <<EOF
VenueFlow full-stack dev orchestration.

Usage: scripts/stack.sh <command>

  up           Build + start all services, seed demo data, print access info (default)
  down         Stop services (keeps the database volume)
  reset        Wipe volumes (fresh database) and start clean
  logs [svc]   Tail logs; optional service: api | worker | frontend | db | tasks-emulator
  verify       Quick health / connectivity check
  help         Show this help

Full documentation: RUNBOOK.md
EOF
}

case "${1:-up}" in
  up)               cmd_up ;;
  down)             cmd_down ;;
  reset)            cmd_reset ;;
  logs)             shift || true; cmd_logs "${1:-}" ;;
  verify)           cmd_verify ;;
  help|-h|--help)   usage ;;
  *)                c_red "Unknown command: $1"; echo; usage; exit 1 ;;
esac
