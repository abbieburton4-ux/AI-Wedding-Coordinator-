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
exec python -m uvicorn app.production:app --host 0.0.0.0 --port "${PORT:-5000}"
