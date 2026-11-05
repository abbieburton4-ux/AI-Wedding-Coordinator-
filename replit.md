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
  Before publishing, resolve the npm dependency advisories (a backlog item),
  configure the bootstrap access list, follow "When you publish" below, and add the published hostname to Firebase's
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

## Database schema

Rule 6 holds on Replit: the schema only changes through the Alembic migrations in
`backend/migrations/versions/`. Every start of `scripts/replit-production.sh`, in
the workspace and in the published app, runs `alembic upgrade head` against that
environment's own database before serving anything. Migrations can carry data
steps (for example `0002` makes each couple their wedding's owner), and only
Alembic runs those. On PostgreSQL the upgrade is one transaction and is serialised
across instances, so a failed or concurrent start can't half-apply it.

The app refuses to start, rather than guess, if the database has app tables but no
Alembic record, or if a migration fails (usually because something else already
changed the schema). Don't fix either by editing the database by hand; ask the team.

**When you publish** (plain steps for the owner):
1. Press **Run** in the workspace first and wait for the app to load. That brings
   the development database up to date, so it is never behind production.
2. Press **Publish**. If Replit shows a step about database or schema changes for
   production, choose the option that does **not** apply them (skip / don't
   apply). The published app applies its own changes when it starts.
3. If that screen only lets you apply the changes, stop and tell the team before
   publishing. [ASSUMPTION] Replit offers a way to skip; nobody has checked
   this screen yet.
4. Once published, open the app. If it shows an error page instead of sign-in,
   tell the team; your data is untouched because the app stops before writing.

Startup then seeds only the vendor catalogue (never fictional users, weddings,
budgets or bookings).

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
aligned with `backend/requirements.txt` (CI and Docker install that file), and
keep `sqlmodel` below 0.0.25. Restore with `uv sync --active`.
Frontend dependencies stay in `frontend/package.json` / `package-lock.json`.
Patched `websocket-driver` and `tar` overrides unblock the imported dependencies;
the remaining npm audit findings are handed to the product lane for the backlog.

Run `bash scripts/verify-backend.sh`: the five backend verify scripts
(including `verify_production.py`) and the sign-in test
(`node --test frontend/src/app/auth/sessionProfile.test.js`), as CI does.
These mock Gemini and Firebase and use temporary SQLite databases, not real data.
From `frontend/`, run `VITE_BASE=/ VITE_API_URL= npm run build`.
Restore the tracked test DB artifacts after verification.

The old `scripts/replit-demo.sh` remains available only for disposable sample-data
work, with Firebase configuration unset. It uses Git-ignored `backend/venueflow.db`;
never point it at real PostgreSQL or enter real personal information there.
