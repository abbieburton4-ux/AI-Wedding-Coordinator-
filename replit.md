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
Alembic record, if a migration fails (for example because a table Publish added
doesn't match what the migration expects, or an old-style migration finds its
change already made), or if `SYNC_DATABASE_URL` points at a different database from
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
Replit's documentation describes no way to skip or turn off that step for a
Replit-managed database: Publish compares the two databases, generates SQL, checks
it on a copy of production, and runs it once you approve. The only other choices
it offers are cancelling or overwriting production
([How Publish updates your production database](https://docs.replit.com/features/data-and-storage/publish-database-changes),
checked 2026-11-09). Publish leaves alone only an external database, such as one
set up on Neon or Supabase directly.

So migrations are written to cope (B60). Publish copies the schema, not the data,
so production's Alembic record stays one behind after Publish has added the
change. When the published app starts, the migration runs anyway: each of its
schema steps (`backend/migrations/safe_ops.py`) looks first and skips anything
Publish already added, then its data steps run as usual. Only Alembic runs data
steps, on both paths. `verify_migrations.py` refuses a migration after `0006` that
changes the schema any other way, and tests both paths. If something Publish added
doesn't match what the migration expects, the app stops and says so rather than
guess.

### What Publish should show

Each migration after `0006` adds a line here, with its backlog item, saying what
Publish will list for it. Changes from earlier publishes are already in production
and won't be listed again, so every change Publish shows must appear somewhere
below. If one doesn't, stop and tell the team. Until a line appears here, a
publish should list **no** database changes.

- `0007` (B62, the couple add their own vendors): two new tables and nothing else.
  `CREATE TABLE couple_vendors` and `CREATE TABLE couple_vendor_quotes`, plus
  `CREATE INDEX ix_couple_vendors_wedding_id` and
  `CREATE INDEX ix_couple_vendor_quotes_vendor_id`. The primary keys
  (`pk_couple_vendors`, `pk_couple_vendor_quotes`), foreign keys
  (`fk_couple_vendors_wedding_id_weddings`,
  `fk_couple_vendor_quotes_vendor_id_couple_vendors`) and checks
  (`ck_couple_vendor_section`, `ck_couple_vendor_status`,
  `ck_couple_vendor_quote_total`) may appear inside the CREATE TABLE lines or as
  separate `ADD CONSTRAINT` lines; either is fine. No existing table changes, so
  there should be no `ADD COLUMN`, `ALTER COLUMN` or `DROP`. Wildman BT is added to
  the Venue section when the published app starts, not by Publish.

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
   may list changes it will make to production. Read every line of the SQL it
   shows, even if the pane isn't orange.
   - **You may approve** when every change is an addition (`CREATE TABLE`,
     `ADD COLUMN`, `CREATE INDEX`, `ADD CONSTRAINT`) and each one appears under
     "What Publish should show" above. The pane may turn orange for a new
     required column, index or constraint; that's expected when the list says so.
     Choose **Approve and publish**. The published app then finishes the job when
     it starts.
   - If any line says **DROP**, first close the publish screen: the development
     database may be behind. In the Shell, type `cd backend && alembic current`
     to see where it is, then `python db_status.py upgrade` (the same as
     `alembic upgrade head`, with the run script's safety checks), and run the
     check in step 3 again. Then press Publish again.
   - **Stop and tell the team** if anything else appears, or still appears: any
     line with **DROP** or **RENAME**, any `ALTER COLUMN`, a question asking
     whether something was renamed, a question about a unique constraint offering
     to remove rows, a change that isn't on the list, or **Migrations failed
     validation**. Choose **Cancel**. Never choose **Copy your development
     database schema & data to production**, and don't ask Replit's Agent to fix
     it.
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
