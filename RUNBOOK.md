# VenueFlow — Local Full-Stack Runbook

Everything needed to build, run, and demo the full stack locally. The whole
universe runs in Docker (Postgres + Cloud Tasks emulator + FastAPI api + worker +
Vite frontend) behind one script.

## Prerequisites

### Replit demo preview (without Docker)

**Real-access setup is now the default on Replit.** Build with
`bash scripts/replit-build.sh`, then run `bash scripts/replit-production.sh`.
This serves the built React app and FastAPI together on port 5000, uses the
managed PostgreSQL database and Firebase, and disables both demo flags.
Set `ACCESS_BOOTSTRAP_EMAILS` privately for the couple's first sign-ins.
AI actions run within the request; no worker secret or task emulator is needed.
Every start applies the Alembic migrations to that environment's own database
(rule 6); when publishing, don't let Replit apply schema changes itself. Full
configuration, publishing steps and verification are in [replit.md](replit.md).

The following demo command is retained for disposable data only, without Firebase:

Run `bash scripts/replit-demo.sh` using the **Start application** workflow.
Open `/login` and choose **Continue as a couple**. This is the existing demo
mode with fictional data, simulated sign-in and a disposable SQLite database;
never enter real information or publish it. Vite serves port 5000 and proxies
`/api` to FastAPI on port 8000. `VITE_BASE=/` and an empty `VITE_API_URL` keep
browser requests on the preview's own origin. Live AI requires a server-side
`GEMINI_API_KEY` Secret; voice requires `ELEVENLABS_API_KEY`. See
[replit.md](replit.md) for dependency installation, limitations and verification.

The Docker instructions below remain available for non-Replit development.

- **Docker Desktop** running (the script checks this). First build pulls ~3 base
  images and runs `npm ci` + `pip install`, so budget a few minutes.
- **A Gemini Developer API key** (`AIza…`) for the AI agents — get one at
  <https://aistudio.google.com/apikey>. The stack runs without it, but the agents
  (intake planner, venue/supplier matchers, quote extractor) will fail.
- `curl` (for the script's health checks) — preinstalled on macOS/Linux.

## Quick start

```bash
# 1. Add your Gemini key (first run only)
cp backend/.env.example backend/.env          # the script also does this for you
#    then edit backend/.env → GEMINI_API_KEY=AIza...

# 2. Bring up the whole stack
./scripts/stack.sh up
```

Then open **<http://localhost:5173/VenueFlow/>** and click **Start planning** (or go
to `/signup`).

### Script commands

| Command | What it does |
|---|---|
| `scripts/stack.sh up` | Build + start all services, seed demo data, print access info (default) |
| `scripts/stack.sh down` | Stop services, keep the database volume |
| `scripts/stack.sh reset` | **Wipe** volumes (fresh DB) and start clean |
| `scripts/stack.sh logs [svc]` | Tail logs (`api`, `worker`, `frontend`, `db`, `tasks-emulator`) |
| `scripts/stack.sh verify` | Quick health / CORS / connectivity check |

## Services & ports

| Service | Port | Notes |
|---|---|---|
| frontend | 5173 | Vite dev server; app served under `/VenueFlow/` |
| api | 8000 | FastAPI; Swagger at `/docs`. On an empty database, seeds the vendor catalogue, plus the fictional demo couples and weddings in dev mode only. Builds tables from models in dev mode, applies Alembic migrations otherwise |
| worker | 8001 | Same app; receives Cloud Tasks pushes at `/tasks/*` |
| db | 5432 | Postgres 16 (`venueflow` / `venueflow_pass`), data in a named volume |
| tasks-emulator | 8123 | Cloud Tasks emulator (gRPC) |

Compose file: [backend/docker-compose.yml](backend/docker-compose.yml).

## Logging in (auth)

Auth is **Firebase in production, dev-mock locally** (see
[frontend/src/app/auth/AuthProvider.tsx](frontend/src/app/auth/AuthProvider.tsx)).
With no `VITE_FIREBASE_*` env vars set, the app runs in **dev-auth mode** — `/login`
and `/signup` show an identity picker that uses `mock-<id>` bearer tokens. No
Firebase project needed to develop.

- **New couple** → `/signup` → "Create a new couple account" → guided intake → the
  AI drafts a budget → live dashboard; the Checklist screen holds the shared planning checklist. Vendor matching runs when you ask.
- **Returning couple** → `/login` → "Continue as a couple (Priya & David)".

For **production**, set `VITE_FIREBASE_*` (see [frontend/.env.example](frontend/.env.example))
and the backend `FIREBASE_PROJECT_ID`; the backend verifies Firebase ID tokens
against Google's public keys
([backend/app/api/v1/endpoints/auth.py](backend/app/api/v1/endpoints/auth.py)).

In production (PD-002), set these in the deployment environment, never in git:

| Variable | What it's for |
|---|---|
| `FIREBASE_PROJECT_ID` | The couple's own Firebase project. Unset means Firebase sign-in is refused. |
| `ACCESS_BOOTSTRAP_EMAILS` | The couple's two sign-in emails, comma-separated. Only these may create the wedding, and both become its owners. |
| `INTERNAL_TASKS_SECRET` | A long random value. The task dispatcher sends it to the worker `/tasks/*` routes. |
| `INBOUND_EMAIL_SECRET` | A long random value. Put it on the SendGrid inbound-parse URL as `?token=...`. |

**Never deploy with `DEVELOPMENT_MODE=True`**, even though `backend/.env.example` sets it for local work. It switches off every secret check below and the wedding-creation limit. Leave `DEVELOPMENT_MODE`, `ALLOW_MOCK_AUTH` and `JWT_SECRET` unset; the first two default to off. Outside dev mode, the worker routes and webhooks refuse every call when their secret isn't set. Nobody can sign themselves up. Everyone other than the couple gets in only once they're on the wedding's access list. The couple manage that list on the **Who has access** screen (`/wedding/access`, owners only); `backend/manage_access.py` stays as a fallback for the team, and is the only way to change or remove one of the couple's owner rows (on their request). Turn on both Google and Email/Password in Firebase: a password account is let in only after the person confirms their email, using a confirmation email they ask for themselves. The owner's setup steps are in [docs/setup-sign-in.md](docs/setup-sign-in.md).

### Migrations

Outside dev mode, the app applies Alembic migrations on startup. On Postgres, an advisory lock stops two processes starting at once from racing.
- **A database that dev mode built with `create_all`:** tell Alembic where it stands, once, before starting the app. If the database has no `wedding_members` table, run `alembic stamp 0001`; the next start adds the table and makes each couple an owner. If the table is already there, run `alembic stamp head`, then add each couple's owner row with `manage_access.py`.
- **Loading the owner's checklist from the app (PD-011):** on the Checklist screen, an owner or editor sees "Load my checklist" until it has run. They pick the file; the app does a practice run that saves nothing and lists what it would add; "Add these tasks" saves it. It uses the wedding date already set on the Checklist screen, refuses the same things as the script below, and runs once. The file's text goes only into the new tasks: it isn't kept, logged or sent to the AI. A backup first is still wise where the hosting console offers one. No Shell or database secret is needed, so this is the route for the published app.
- **Loading the owner's checklist with the script (PD-007), once, after hosting (B14):** the owner's list comes from their own file, which stays out of git. It adds the approved Jewish-tradition tasks and the Wildman BT payment tasks V1–V3 (PD-011), merges the AI planner's old timeline (a duplicate keeps its tick and notes on the matching task), and removes the timeline rows. A second run is refused. From `backend/`, against the app's database:
  1. **Back up the database first.** The dry run works on the live database and undoes itself; it isn't a copy. On Postgres: `pg_dump "${SYNC_DATABASE_URL/+psycopg2/}" -Fc -f checklist-before-import.dump` (pg_dump needs the URL without `+psycopg2`) (or take an on-demand backup in the hosting console). On SQLite: stop the app and copy the database file. Keep the backup out of git: it holds guest data.
  2. Dry run: `python manage_checklist.py import --wedding <id> --file <path to the owner's file> --wedding-date 2027-10-23`. It prints what it would add, merge and remove, then undoes it. Read it.
  3. Run the same command again with `--apply`. Before deleting any timeline row it reads the checklist back and checks every row is on it; if not, it refuses and saves nothing.
  4. If something looks wrong afterwards, restore the backup (`pg_restore --clean -d "${SYNC_DATABASE_URL/+psycopg2/}" checklist-before-import.dump`, or copy the SQLite file back with the app stopped).
- **Never run `alembic downgrade` against a database holding real data.** The downgrades drop tables, including the access list.
- **Writing a migration:** autogenerate renders `op.batch_alter_table` blocks (`render_as_batch`), so altering or dropping a column or constraint also works on SQLite. Keys and unique constraints get names from the convention on `SQLModel.metadata` (`fk_<table>_<column>_<referred table>`, `pk_<table>`, `uq_<table>_<columns>`); give every `CheckConstraint` an explicit name, which `verify_migrations.py` checks. Never change the convention once a real database exists: migrations `0001` and `0002` take their names from it at run time. Databases built before this convention have unnamed (SQLite) or Postgres-default (`<table>_<column>_fkey`, `<table>_pkey`) key names, so a migration that drops an existing foreign or primary key must look its name up rather than assume the convention. `verify_migrations.py` runs on SQLite only, which doesn't compare check constraints or server defaults; review those by hand until it also runs against Postgres.

## What happens on intake (the agent flow)

States go `intake` → `planning`. There's no payment step (PD-003).

1. `POST /weddings` (intake) creates the wedding in `intake` status and runs the
   **intake_planner** agent, which drafts the budget and moves the wedding
   to **`planning`**. The dashboard polls and fills in.
2. Venue and supplier matching doesn't run automatically: the catalogue doesn't cover
   this wedding's area yet (B11). It runs only when the couple ask from the dashboard
   (`POST /weddings/{id}/match` and `/suppliers`). There's no payment step (PD-003).

If the **budget guardrail** fires (e.g. €3,000 for 120 guests), intake_planner blocks,
the wedding stays in `intake`, and the dashboard shows the "your coordinator flagged
something" card to adjust the budget.

Every agent action is recorded in `agent_decision_logs`. Async dispatch goes through the
Cloud Tasks emulator with a direct-to-worker fallback
([backend/app/utils/tasks.py](backend/app/utils/tasks.py)).

## Testing the product

Two ways to test, depending on what you're checking.

### A. Fast checks — agent logic & API routes (no Docker)

The verification suites run the app **in-process** with FastAPI's `TestClient` against
a throwaway SQLite DB — no server, worker, or Postgres needed. This is the day-to-day
inner loop.

```bash
cd backend
python verify_endpoints.py   # API routes, auth, decision-log export
python verify_agents.py      # agent behaviour + guardrails
```

> Windows: activate the venv first — `.\.venv\Scripts\Activate.ps1`.

### B. Full product end-to-end (Docker) — use before any demo

This exercises the real path a customer hits: Postgres, async Cloud Tasks dispatch
(`api` → `worker`). The in-process suites
above do *not* cover that async path.

```bash
scripts/stack.sh up          # or: cd backend && docker compose up --build
```

Then at <http://localhost:5173/VenueFlow/>:

1. `/signup` → **new couple** → fill the intake form
2. The dashboard shows "building…", then the plan. Watch the worker
   live: `scripts/stack.sh logs worker`.

Run the suites against Postgres inside the running container:

```bash
cd backend && docker compose exec api python verify_endpoints.py
```

## Demo assets

[demo/](demo/) holds captured screenshots and a Playwright end-to-end script
(`demo/e2e.mjs`) that drives the couple journey (signup → intake → dashboard) in a
real headless browser. To run it:

```bash
cd demo
npm init -y >/dev/null && npm i playwright >/dev/null && npx playwright install chromium
node e2e.mjs        # screenshots are written next to it
```

## Troubleshooting

- **`Docker daemon is not running`** — start Docker Desktop, retry.
- **Port already in use** (5432/8000/8001/5173/8123) — stop the conflicting process
  or `scripts/stack.sh down`.
- **api exits with `NameError: name 'Optional' is not defined`** — a missing
  `from typing import ...`. Local dev is Python 3.14 (lazy annotations, PEP 649)
  but the container is Python 3.11 (evaluates annotations at import), so missing
  typing imports crash only in Docker. Add the import. Catch them all at once:
  `cd backend && docker compose run --rm --no-deps api python -c "import app.main"`.
- **api logs show `illegal request line` from the emulator** — harmless. The public
  emulator is gRPC-only; `enqueue_agent_task` posts REST, fails, and falls back to
  invoking the worker directly. Tasks still run.
- **Agents fail with `API_KEY_INVALID`** — `GEMINI_API_KEY` in `backend/.env` isn't a
  valid Gemini **Developer** key (must start with `AIza`). Vertex/OAuth tokens won't
  work with this client.
- **Stale / weird data** — `scripts/stack.sh reset` for a clean database + reseed.

## Architecture pointers

- Backend: FastAPI + SQLModel + Alembic; agents under
  [backend/app/agents/](backend/app/agents/); see [docs/architecture.md](docs/architecture.md).
- Frontend: React 18 + react-router v7 + Tailwind v4; auth in
  [frontend/src/app/auth/](frontend/src/app/auth/) and the couple workspace in
  [frontend/src/app/wedding/](frontend/src/app/wedding/). The planner, admin, checkout
  and marketing screens were removed (PD-003).

### Wired vs. still-mock (as of this handoff)

- **Wired to real data:** couple signup → intake → dashboard /
  budget / checklist / vendors; the vendor **quote loop** (log a reply → quote_extractor →
  compared with the matching category's planned dollars on the budget screen, B42); the couple **AI Concierge** (Aurelia, grounded in the
  couple's real budget/checklist/vendors).
- **Still mock / next slices:** SendGrid inbound-email
  auto-ingest of vendor replies.
