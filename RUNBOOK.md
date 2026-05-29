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
| `scripts/stack.sh seed` | Re-run the pilot seed |
| `scripts/stack.sh tokens` | Print the pilot planner bearer tokens |
| `scripts/stack.sh verify` | Quick health / CORS / connectivity check |

## Services & ports

| Service | Port | Notes |
|---|---|---|
| frontend | 5173 | Vite dev server; app served under `/VenueFlow/` |
| api | 8000 | FastAPI; Swagger at `/docs`. Runs migrations/seed on startup |
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
  AI builds a budget, timeline, and venue/supplier shortlist → live dashboard.
- **Returning couple** → `/login` → "Continue as a couple (Priya & David)".
- **Planner** → `/login` → "Continue as a planner (Mary-Aoife)" → manages 1 client;
  open a client to drill into their wedding in the shared workspace.

For **production**, set `VITE_FIREBASE_*` (see [frontend/.env.example](frontend/.env.example))
and the backend `FIREBASE_PROJECT_ID`; the backend verifies Firebase ID tokens
against Google's public keys
([backend/app/api/v1/endpoints/auth.py](backend/app/api/v1/endpoints/auth.py)).

## What happens on intake (the agent flow)

`POST /weddings` (intake) → the **intake_planner** agent drafts the budget + timeline
and flips status to `planning`, then cascades to the **venue_matcher** and
**supplier_matcher** agents, which shortlist real seeded vendors. The dashboard
polls and fills in as these land. Every agent action is recorded in
`agent_decision_logs`. Async dispatch goes through the Cloud Tasks emulator with a
direct-to-worker fallback ([backend/app/utils/tasks.py](backend/app/utils/tasks.py)).

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
  [frontend/src/app/auth/](frontend/src/app/auth/), couple workspace in
  [frontend/src/app/wedding/](frontend/src/app/wedding/), planner workspace in
  [frontend/src/app/planner/](frontend/src/app/planner/).

### Wired vs. still-mock (as of this handoff)

- **Wired to real data:** couple signup → intake → dashboard/budget/timeline/vendors;
  planner Overview + Clients + drill-in to a client's wedding.
- **Still mock / next slices:** planner Tasks, Subscriptions, Analytics, AI Concierge;
  planner→couple **invite** (so planners can onboard clients); email notifications.
