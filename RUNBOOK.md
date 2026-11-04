# VenueFlow — Local Full-Stack Runbook

Everything needed to build, run, and demo the full stack locally. The whole
universe runs in Docker (Postgres + Cloud Tasks emulator + FastAPI api + worker +
Vite frontend) behind one script.

## Prerequisites

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
| api | 8000 | FastAPI; Swagger at `/docs`. Seeds on startup; builds tables from models in dev mode, applies Alembic migrations otherwise |
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
  AI builds a budget and timeline → live dashboard. Vendor matching runs when you ask.
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

**Never deploy with `DEVELOPMENT_MODE=True`**, even though `backend/.env.example` sets it for local work. It switches off every secret check below and the wedding-creation limit. Leave `DEVELOPMENT_MODE`, `ALLOW_MOCK_AUTH` and `JWT_SECRET` unset; the first two default to off. Outside dev mode, the worker routes and webhooks refuse every call when their secret isn't set. Nobody can sign themselves up. Everyone other than the couple gets in only once they're on the wedding's access list. The team manages that list with `backend/manage_access.py` until the owner's settings screen exists (B22). The owner's setup steps are in [docs/setup-sign-in.md](docs/setup-sign-in.md).

### Migrations

Outside dev mode, the app applies Alembic migrations on startup. On Postgres, an advisory lock stops two processes starting at once from racing.
- **A database that dev mode built with `create_all`:** tell Alembic where it stands, once, before starting the app. If the database has no `wedding_members` table, run `alembic stamp 0001`; the next start adds the table and makes each couple an owner. If the table is already there, run `alembic stamp head`, then add each couple's owner row with `manage_access.py`.
- **Never run `alembic downgrade` against a database holding real data.** The downgrades drop tables, including the access list.

## What happens on intake (the agent flow)

States go `intake` → `planning`. There's no payment step (PD-003).

1. `POST /weddings` (intake) creates the wedding in `intake` status and runs the
   **intake_planner** agent, which builds the budget and timeline and moves the wedding
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
2. The dashboard shows "building…", then the budget and timeline. Watch the worker
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
  budget / timeline / vendors; the vendor **quote loop** (log a reply → quote_extractor →
  live budget + over-budget alert); the couple **AI Concierge** (Aurelia, grounded in the
  couple's real budget/timeline/vendors).
- **Still mock / next slices:** the owner's access screen (B22); SendGrid inbound-email
  auto-ingest of vendor replies.
