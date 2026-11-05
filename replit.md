# VenueFlow on Replit

Keep the existing FastAPI/SQLModel backend and React/Vite frontend. This is a
private, one-wedding app. The owner approved switching from the initial demo to
real Firebase access backed by Replit PostgreSQL, leaving demo SQLite untouched.

## Run and publish

- **Start application** runs `bash scripts/replit-production.sh`.
- Rebuild the frontend after editing it or changing Firebase web configuration:
  `bash scripts/replit-build.sh`.
- Production build: `bash scripts/replit-build.sh`.
- Production run: `bash scripts/replit-production.sh`.
- One Uvicorn process serves the built SPA and API on `0.0.0.0:5000` (or `PORT`).
  It does not run Vite in production. Browser API requests stay same-origin.
- Publishing is configured for Autoscale but requires the user's Publish action.
  Before publishing, resolve the dependency advisories in backlog B43, configure
  the bootstrap access list, and add the published hostname to Firebase's
  Authentication authorized domains. The preview hostname also needs authorization
  for Google sign-in from the preview.

## Configuration

Required server-side settings:
- `DATABASE_URL`: Replit's managed PostgreSQL connection, injected automatically.
  Async/sync SQLAlchemy URLs are derived in memory; never print them.
- `GEMINI_API_KEY`: private Gemini key, server-side only.
- `GEMINI_PLANNING_MODEL` / `GEMINI_FAST_MODEL`: configured as
  `gemini-3.5-flash`, which passed a live request. The old 2.5 default returned
  HTTP 404, and `gemini-flash-latest` returned HTTP 503 during setup.
- `FIREBASE_PROJECT_ID`: the owner's Firebase project.
- `ACCESS_BOOTSTRAP_EMAILS`: comma-separated couple's allowed sign-in emails.
  Keep this private in environment configuration, never in project files.

Firebase public web configuration (bundled by Vite):
`VITE_FIREBASE_API_KEY`, `VITE_FIREBASE_AUTH_DOMAIN`,
`VITE_FIREBASE_PROJECT_ID`, `VITE_FIREBASE_APP_ID`.
Frontend and backend project IDs must match. Never add Gemini or other private
keys to `VITE_*` variables.

The run script forces `DEVELOPMENT_MODE=False`, `ALLOW_MOCK_AUTH=False`,
`REPLIT_MANAGED_DATABASE=True`, and `DIRECT_AGENT_EXECUTION=True`.
Mock tokens are refused. Missing bootstrap emails leave new sign-ins locked out.

Voice is optional and needs `ELEVENLABS_API_KEY` plus an accessible
`ELEVENLABS_AGENT_ID`. `INBOUND_EMAIL_SECRET` is needed only if inbound email
is enabled. Worker HTTP routes stay locked unless `INTERNAL_TASKS_SECRET` is
configured; direct execution doesn't call those routes or require that secret.
`JWT_SECRET` is unnecessary for Firebase sign-in.

## PostgreSQL schema

The development PostgreSQL database was initialized using the existing Alembic
migrations, without copying demo data or changing the schema.
For future changes, apply the normal Alembic flow **to development only**:
`cd backend && python -m alembic upgrade head`.
Replit Publish diffs development and production and applies the production schema.
Do not put migration commands in build/run scripts or add startup DDL for managed
production databases. Startup verifies required tables, then seeds only the vendor
catalogue (never fictional users, weddings, budgets or bookings).

## AI execution

Replit runs agent actions within the user's HTTP request using the existing
decorated agents and an independent database session. No external worker or task
queue is required. Responses wait for completion; model calls may take up to
90 seconds. Provider failures return an explicit error and retain the decision
log; guardrail blocks are reported as blocks. This is not a durable asynchronous
job queue. Scale or background-processing requirements would need separate work.
Intake saves the profile before planning; a failed plan remains recoverable using
the existing decision log and replan flow.

## Dependencies and verification

Root `pyproject.toml` / `uv.lock` manage Replit Python dependencies; keep them
aligned with `backend/requirements.txt`. Restore with `uv sync --active`.
Frontend dependencies stay in `frontend/package.json` / `package-lock.json`.
Patched `websocket-driver` and `tar` overrides unblock the imported dependencies;
remaining npm audit findings are tracked in backlog B43.

From `backend/`, run `python verify_endpoints.py`, `python verify_agents.py`,
`python verify.py`, `python verify_migrations.py`, and `python verify_production.py`.
These mock Gemini and Firebase and use temporary SQLite databases, not real data.
From `frontend/`, run `VITE_BASE=/ VITE_API_URL= npm run build`.
Restore the tracked test DB artifacts after verification.

The old `scripts/replit-demo.sh` remains available only for disposable sample-data
work, with Firebase configuration unset. It uses Git-ignored `backend/venueflow.db`;
never point it at real PostgreSQL or enter real personal information there.
