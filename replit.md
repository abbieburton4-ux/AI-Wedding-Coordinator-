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
  Before publishing, resolve the npm dependency advisories (backlog B47),
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

Aurelia, the assistant (typed chat and voice), is off (PD-010): the backend
refuses it unless `ASSISTANT_ENABLED=True`, and the screens hide it unless
`AURELIA_ENABLED` in `frontend/src/app/wedding/features.ts` is true. If it's
turned back on, voice needs `ELEVENLABS_API_KEY` plus an accessible
`ELEVENLABS_AGENT_ID`. `INBOUND_EMAIL_SECRET` is needed only if inbound email
is enabled. Worker HTTP routes stay locked unless `INTERNAL_TASKS_SECRET` is
configured; direct execution doesn't call those routes or require that secret.
`JWT_SECRET` is unnecessary for Firebase sign-in.

## Database schema

Rule 6 holds on Replit: the schema only changes through the Alembic migrations in
`backend/migrations/versions/`. Every start of `scripts/replit-production.sh`, in
the workspace and in the published app, first runs `python db_status.py upgrade`
from `backend/`. That applies `alembic upgrade head` to that environment's own
database, then checks it is at the latest migration, and stops before serving
anything if it isn't. The app's own startup runs the same upgrade again, which by
then does nothing. Migrations can carry data steps (for example `0002` makes each
couple their wedding's owner), and only Alembic runs those. On PostgreSQL the
upgrade is one transaction and is serialised across instances, so a failed or
concurrent start can't half-apply it.

The app refuses to start, rather than guess, if the database has app tables but no
Alembic record, if a migration fails (usually because something else already
changed the schema), or if `SYNC_DATABASE_URL` points at a different database from
`DATABASE_URL` (don't set `SYNC_DATABASE_URL` or keep a `backend/.env` on Replit;
the app derives it). Don't fix any of these by editing the database by hand; ask
the team.

**Pulling code doesn't update the database.** A running app keeps its old code and
leaves the development database where it was until the app starts again. In B59
the workspace had migration `0006` in its code but its database was still at
`0005`, while the published app had applied `0006` when it started. Publish then
offered to delete the new column from production to match. [ASSUMPTION] The
likeliest cause is that the workspace app was never restarted after the Pull. A
`backend/.env` copied from `.env.example` would also do it, by sending the
workspace's migrations to a local SQLite file; the run script now refuses that.

**A publish that brings a new migration will list additions.** Run puts the
development database at the new migration while production is still one behind,
so Publish offers to add the new table or column to production itself (step 4).

**When you publish** (plain steps for the owner):
1. In the workspace, **Pull** the latest code.
2. If the app is running, press **Stop**. Then press **Run** and wait for the app to
   load. The console shows `Database is up to date (migration ...)`. If it says the
   database is behind, or anything else, or the app doesn't load, stop and tell
   the team.
3. To double-check, open the **Shell** and type
   `cd backend && python db_status.py check`. It must say
   `Database is up to date`.
4. Press **Publish**. Replit compares the development database with production and
   may list changes it will make to production.
   - If any line says **DROP** (for example `DROP COLUMN` or `DROP TABLE`), **don't
     approve it**. Close the publish screen. In the Shell, type
     `cd backend && alembic current` to see where the development database is,
     then `python db_status.py upgrade` (the same as `alembic upgrade head`, with
     the run script's safety checks), and run the check in step 3 again. Then try
     Publish again. If DROP is still offered, stop and tell the team.
   - If it lists only additions (`CREATE TABLE`, `ADD COLUMN`) and lets you skip
     them, skip them: the published app applies its own changes when it starts.
   - If it lists additions and won't let you skip, stop and tell the team before
     publishing. [ASSUMPTION] Approving them would add the change to production
     outside Alembic, and the published app would then refuse to start on that
     migration until the team marks it as applied there. Nobody has seen this
     screen with additions yet.
5. Once published, open the app. If it shows an error page instead of sign-in,
   tell the team. The app stops before changing anything itself, but anything
   Replit applied in step 4 has already happened.

The Shell always reaches the **development** database (`DATABASE_URL`), never the
published app's production one.

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
the remaining npm audit findings are backlog B47.

Run `bash scripts/verify-backend.sh`: the five backend verify scripts
(including `verify_production.py`) and the sign-in test
(`node --test frontend/src/app/auth/sessionProfile.test.js`), as CI does.
These mock Gemini and Firebase and use temporary SQLite databases, not real data.
From `frontend/`, run `VITE_BASE=/ VITE_API_URL= npm run build`.
Restore the tracked test DB artifacts after verification.

The old `scripts/replit-demo.sh` remains available only for disposable sample-data
work, with Firebase configuration unset. It uses Git-ignored `backend/venueflow.db`;
never point it at real PostgreSQL or enter real personal information there.
