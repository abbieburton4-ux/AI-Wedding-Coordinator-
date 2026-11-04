#!/usr/bin/env bash
# Backend half of the verify gate (verify skill steps 2 and 7, including the migration check), as one command so CI,
# the autopilot and people all run the same thing. Run from anywhere.
set -uo pipefail

cd "$(dirname "$0")/../backend"

PY="python"
if [ -x .venv/bin/python ]; then PY=".venv/bin/python"; fi
export GEMINI_API_KEY="${GEMINI_API_KEY:-dummy}"   # Gemini is mocked in these scripts

status=0
for script in verify_endpoints.py verify_agents.py verify.py verify_migrations.py; do
  echo "== $script"
  if ! "$PY" "$script"; then
    echo "FAILED: $script"
    status=1
  fi
done

# The scripts rewrite tracked test databases and leave SQLite side files (backlog B17).
git restore endpoints_test.db endpoints_test.db-shm endpoints_test.db-wal 2>/dev/null || true
rm -f verify_agents_test.db-shm verify_agents_test.db-wal verify_test.db-shm verify_test.db-wal

exit $status
