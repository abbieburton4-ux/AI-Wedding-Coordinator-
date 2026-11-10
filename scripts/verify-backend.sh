#!/usr/bin/env bash
# Backend half of the verify gate (verify skill steps 2 and 7, including the migration check), as one command so CI,
# the autopilot and people all run the same thing. Run from anywhere.
set -uo pipefail

cd "$(dirname "$0")/../backend"

PY="python"
if [ -x .venv/bin/python ]; then PY=".venv/bin/python"; fi
export GEMINI_API_KEY="${GEMINI_API_KEY:-dummy}"   # Gemini is mocked in these scripts

status=0
for script in verify_endpoints.py verify_agents.py verify.py verify_migrations.py verify_production.py; do
  echo "== $script"
  if ! "$PY" "$script"; then
    echo "FAILED: $script"
    status=1
  fi
done

# The sign-in profile test needs only Node's built-in runner, no npm install, so it
# runs here and CI's backend job (which has Node on its runner) picks it up.
echo "== sessionProfile.test.js"
if ! command -v node >/dev/null 2>&1; then
  echo "FAILED: node is needed for frontend/src/app/auth/sessionProfile.test.js"
  status=1
elif ! node --test ../frontend/src/app/auth/sessionProfile.test.js; then
  echo "FAILED: sessionProfile.test.js"
  status=1
fi

# The budget's "would this go over?" note (B66), same runner.
echo "== forecast.test.js"
if command -v node >/dev/null 2>&1 && ! node --test ../frontend/src/app/wedding/views/budget/forecast.test.js; then
  echo "FAILED: forecast.test.js"
  status=1
fi

# The list of all expenses: filters, search, sorting and moving categories (B67).
echo "== expenses.test.js"
if command -v node >/dev/null 2>&1 && ! node --test ../frontend/src/app/wedding/views/budget/expenses.test.js; then
  echo "FAILED: expenses.test.js"
  status=1
fi

# Upcoming payments and the chart figures (B68).
echo "== figures.test.js"
if command -v node >/dev/null 2>&1 && ! node --test ../frontend/src/app/wedding/views/budget/figures.test.js; then
  echo "FAILED: figures.test.js"
  status=1
fi

# The scripts rewrite tracked test databases and leave SQLite side files (backlog B17).
git restore endpoints_test.db endpoints_test.db-shm endpoints_test.db-wal 2>/dev/null || true
rm -f verify_agents_test.db-shm verify_agents_test.db-wal verify_test.db-shm verify_test.db-wal

exit $status
