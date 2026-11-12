#!/usr/bin/env bash
# Replit injects DATABASE_URL and private secrets; never print their values.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
export FRONTEND_DIST_DIR="$PWD/frontend/dist"
export DEVELOPMENT_MODE=False
export ALLOW_MOCK_AUTH=False
export REPLIT_MANAGED_DATABASE=True
export DIRECT_AGENT_EXECUTION=True

python - <<'PY'
import os
from sqlalchemy.engine import make_url

required = [
    "DATABASE_URL", "GEMINI_API_KEY", "FIREBASE_PROJECT_ID",
    "VITE_FIREBASE_API_KEY", "VITE_FIREBASE_AUTH_DOMAIN",
    "VITE_FIREBASE_PROJECT_ID", "VITE_FIREBASE_APP_ID",
]
missing = [key for key in required if not os.environ.get(key)]
if missing:
    raise SystemExit("Missing configuration: " + ", ".join(missing))
if make_url(os.environ["DATABASE_URL"]).get_backend_name() not in ("postgresql", "postgres"):
    raise SystemExit("The real-access server requires PostgreSQL, not the demo SQLite database.")
if os.environ["FIREBASE_PROJECT_ID"] != os.environ["VITE_FIREBASE_PROJECT_ID"]:
    raise SystemExit("Backend and frontend Firebase project IDs must match.")
if not os.environ.get("ACCESS_BOOTSTRAP_EMAILS"):
    print("ACCESS_BOOTSTRAP_EMAILS is missing: new accounts cannot sign in until configured.")
PY

cd backend
# Bring this environment's own database to the latest migration before serving,
# and stop if it isn't there. In the workspace this keeps the development database
# level with the code, so Publish never proposes undoing a migration (B59). The
# app's startup runs the same upgrade again; on an up-to-date database it's a no-op.
python db_status.py upgrade

# In the workspace, a Pull doesn't restart the app, so the development database
# used to stay behind until someone pressed Stop and Run (B86). While the app runs,
# re-run the same upgrade whenever the migration files change, and stop
# watching when the server stops (the server keeps its old code until the next
# Run). The published app's files never change, and
# Replit sets REPLIT_DEPLOYMENT=1 there, so it doesn't watch.
if [ "${REPLIT_DEPLOYMENT:-}" != "1" ]; then
  server_pid=$$
  (
    migrations() { cat migrations/versions/*.py 2>/dev/null | cksum || true; }
    seen="$(migrations)"
    while sleep 10 && kill -0 "$server_pid" 2>/dev/null; do
      now="$(migrations)"
      if [ "$now" != "$seen" ]; then
        echo "New migrations pulled; bringing the workspace database up to date." || true
        DB_STATUS_AUTO=1 python db_status.py upgrade || true
        seen="$now"
      fi
    done
  ) &
fi

exec python -m uvicorn app.production:app --host 0.0.0.0 --port "${PORT:-5000}"
