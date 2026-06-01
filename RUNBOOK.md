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

The flow is **freemium**: a free preview earns the payment. States go
`intake` → `preview` → `planning`.

1. `POST /weddings` (intake) creates the wedding in `intake` status and immediately
   runs the **intake_planner** agent as a **free preview** (1 cheap call → budget +
   timeline), landing it in **`preview`**.
2. The dashboard shows a **teaser**: a few budget lines + timeline milestones (the rest
   withheld), locked vendor cards, and an "Unlock · €299" CTA.
3. Payment unlocks the rest. The mock €299 checkout / Stripe Checkout / Stripe webhook
   all call `activate_wedding_planning`
   ([payments.py](backend/app/api/v1/endpoints/payments.py)), which flips status to
   **`planning`** and enqueues the **plan-cascade** task — the paid **venue_matcher** +
   **supplier_matcher** shortlist real seeded vendors. The dashboard polls and fills in.

The budget/timeline endpoints return only a teaser slice while status is `preview`
(`PREVIEW_BUDGET_LINES` / `PREVIEW_TIMELINE_ITEMS` in `weddings.py`) — the full data is
generated and stored but **withheld at the API**, so the blurred UI can't be bypassed
via DevTools.

If the **budget guardrail** fires (e.g. €3,000 for 120 guests), intake_planner blocks,
the wedding stays in `intake`, and the dashboard shows the "your coordinator flagged
something" card to adjust the budget — no payment prompt until there's a real plan.

Every agent action is recorded in `agent_decision_logs`. Async dispatch goes through the
Cloud Tasks emulator with a direct-to-worker fallback
([backend/app/utils/tasks.py](backend/app/utils/tasks.py)).

Payments default to `PAYMENTS_PROVIDER=mock` (no real charge). Flipping to real Stripe
test mode is a one env change — see [docs/worklog.md](docs/worklog.md).

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
(`api` → `worker`), and the **payment → planning** trigger. The in-process suites
above do *not* cover that async path.

```bash
scripts/stack.sh up          # or: cd backend && docker compose up --build
```

Then at <http://localhost:5173/VenueFlow/>:

1. `/signup` → **new couple** → fill the intake form
2. Dashboard shows "building…" then a **preview teaser** (budget + timeline partial,
   locked vendor cards) — the free `intake_planner` run.
3. Click **Unlock · €299** → checkout → "Pay" (mock — no real charge)
4. The **worker** runs the paid matcher cascade; the dashboard fills in with venues +
   suppliers. Watch it live: `scripts/stack.sh logs worker`.

Run the suites against Postgres inside the running container:

```bash
cd backend && docker compose exec api python verify_endpoints.py
```

> **Payment gate note.** With `REQUIRE_PAYMENT=True` (default), a new wedding stays in
> `intake` until checkout completes, so testing the plan now goes through the checkout
> step. For a payment-free run (e.g. a script that wants the planner to fire on
> creation), set `REQUIRE_PAYMENT=False` in `backend/.env`.

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
