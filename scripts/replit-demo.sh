#!/usr/bin/env bash
# Disposable development preview only. Never use with real wedding data.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
ROOT="$PWD"

export DEVELOPMENT_MODE=True
export ALLOW_MOCK_AUTH=True
export DATABASE_URL="sqlite+aiosqlite:///$ROOT/backend/venueflow.db"
export SYNC_DATABASE_URL="sqlite:///$ROOT/backend/venueflow.db"
export WORKER_BASE_URL=http://127.0.0.1:8000
export TASKS_EMULATOR_HOST=127.0.0.1
export VITE_BASE=/
export VITE_API_URL=""

# Do not mix real Firebase sign-in with the explicitly requested demo preview.
if [[ -n "${FIREBASE_PROJECT_ID:-}" || -n "${VITE_FIREBASE_PROJECT_ID:-}" ]]; then
  echo "Refusing demo mode with real Firebase configuration. Use the real-access setup."
  exit 1
fi
echo "DEMO ONLY: simulated sign-in and fictional sample data. Do not enter real information."
if [[ -z "${GEMINI_API_KEY:-}" ]]; then
  echo "GEMINI_API_KEY is not configured. Live AI requests will fail until it is added."
fi

cleanup() {
  kill "${API_PID:-}" "${WEB_PID:-}" 2>/dev/null || true
  wait 2>/dev/null || true
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

(cd backend && python -m uvicorn app.main:app --host 127.0.0.1 --port 8000) &
API_PID=$!

for _ in {1..60}; do
  if curl --silent --fail http://127.0.0.1:8000/health >/dev/null; then
    break
  fi
  if ! kill -0 "$API_PID" 2>/dev/null; then
    echo "Backend exited during startup."
    exit 1
  fi
  sleep 1
done
curl --silent --fail http://127.0.0.1:8000/health >/dev/null

(cd frontend && npm run dev) &
WEB_PID=$!
wait -n "$API_PID" "$WEB_PID"
