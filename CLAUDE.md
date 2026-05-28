# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository Layout

This repo contains a Vite + React frontend, a FastAPI backend, plus product strategy docs. The data model in [docs/ERD.md](docs/ERD.md) is implemented using SQLModel (supporting SQLite/PostgreSQL) in the backend.

- [backend/](backend/) — FastAPI backend, agent implementations, database schemas (SQLModel), migrations (Alembic), and unit/integration tests.
- [frontend/](frontend/) — Vite + React 18 + TypeScript web app (Landing + Experience + Wedding Planning Views).
- [docs/](docs/) — [ERD.md](docs/ERD.md) (data model), [user-stories.md](docs/user-stories.md) (scope), and [architecture.md](docs/architecture.md) (service map, agent layer, key flows).
- [README.md](README.md) — strategic memo and guide for the Build with Gemini XPRIZE submission.

## Backend

All commands run from [backend/](backend/):

```bash
# Setup virtual environment and dependencies
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Run FastAPI server locally
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload

# Run the verification scripts
python verify_endpoints.py   # Verify API surface and integration
python verify_agents.py      # Verify async agents and guardrails
```

### Stack and conventions

- **FastAPI + SQLModel**: Schema definitions and DB operations live in [backend/app/db/models.py](backend/app/db/models.py). SQLite is used for local development, with PG compatibility.
- **Google GenAI SDK (`google-genai`)**: Interacts with Gemini models via the client helper in [backend/app/agents/base.py](backend/app/agents/base.py).
- **Agent Layer**:
  - `intake_planner` in [backend/app/agents/planner.py](backend/app/agents/planner.py)
  - `venue_matcher` and `supplier_matcher` in [backend/app/agents/matcher.py](backend/app/agents/matcher.py)
  - `quote_extractor` in [backend/app/agents/extractor.py](backend/app/agents/extractor.py)
- **Testing**:
  - Integration tests: `verify_endpoints.py`
  - Agent behavior/guardrail checks: `verify_agents.py`

## Frontend

All commands run from [frontend/](frontend/):

```bash
npm i          # install
npm run dev    # Vite dev server
npm run build  # production build to dist/
```

There is no test runner, linter, or typecheck script configured. `tsc --noEmit` works (the tsconfig has `"noEmit": true`) but is not wired into npm scripts.

### Stack and conventions

- **React 18 + react-router v7** (note: `react-router`, not `react-router-dom`). Routes are declared in [frontend/src/app/App.tsx](frontend/src/app/App.tsx); `*` falls back to `Landing`.
- **Tailwind CSS v4** via `@tailwindcss/vite` (no `tailwind.config.*` file — theme is declared inline in [frontend/src/styles/theme.css](frontend/src/styles/theme.css) via `@theme inline` and CSS custom properties). When adding colors/fonts, extend those variables rather than creating a config file.
- **Path alias** `@/*` → `src/*` (see [frontend/tsconfig.json](frontend/tsconfig.json) and [frontend/vite.config.ts](frontend/vite.config.ts)).
- **Figma asset resolver**: imports of the form `figma:asset/<filename>` are rewritten to `src/assets/<filename>` by a custom Vite plugin in [frontend/vite.config.ts](frontend/vite.config.ts). Existing code uses normal relative imports via the [IMG registry in design-system/assets.ts](frontend/src/app/design-system/assets.ts) — prefer that pattern for new images.
- **Vite plugin note**: the comment in [frontend/vite.config.ts](frontend/vite.config.ts) explicitly says React and Tailwind plugins are both required for Figma Make even if Tailwind appears unused — do not remove them.

### Where to put things

- **Pages** → [frontend/src/app/views/](frontend/src/app/views/) (`Landing.tsx`, `Experience.tsx`). Wire new routes in [App.tsx](frontend/src/app/App.tsx).
- **Site chrome / shared layout** → [frontend/src/app/design-system/](frontend/src/app/design-system/) (`Layout.tsx` wraps everything with `Nav` + `Footer` + a `ScrollManager` that handles hash anchors and route-change scroll-to-top).
- **Project-specific UI primitives** (Button, ButtonLink, Eyebrow, SectionHeading, GoldSpecks, etc.) → [frontend/src/app/design-system/primitives.tsx](frontend/src/app/design-system/primitives.tsx). These encode the brand styling (uppercase tracking, gold accents, serif headings) and should be the first choice for new UI.
- **Generic shadcn/Radix primitives** → [frontend/src/app/components/ui/](frontend/src/app/components/ui/) (full shadcn set is vendored). Use these for form controls, dialogs, etc. Note they import `cn` from a sibling [utils.ts](frontend/src/app/components/ui/utils.ts), while design-system files import `cn` from [design-system/cn.ts](frontend/src/app/design-system/cn.ts) — two copies exist; match the convention of the directory you're editing.
- **Images** → register in [design-system/assets.ts](frontend/src/app/design-system/assets.ts) `IMG` map, then reference as `IMG.foo`.

### Styling

Brand system is warm-ivory / muted-gold / serif-headings (Cormorant Garamond + Montserrat + Great Vibes script). Dark mode variables exist in [theme.css](frontend/src/styles/theme.css) but no theme toggle is wired up. Use semantic Tailwind utilities (`bg-background`, `text-foreground`, `text-primary`, `border-border`) rather than hardcoded hex so dark mode keeps working if enabled.

## Product context

The product is the **AI Wedding Coordinator** — sold to couples directly (€299–€999 one-time per wedding) and to independent wedding planners (€199–€499/mo to scale their client load). The agent does the work of a planner: vendor sourcing, timeline drafting, budget tracking, contract review, RSVP/seating, day-of run-of-show. Category for the Build with Gemini XPRIZE submission is **Professional Services Access**, not Small Business Services.

This is the **Option A pivot** in the [README.md](README.md) strategic memo (Section 4.1), chosen over the original "AI receptionist for venues" wedge because Mikla.ai is already ~4x ahead on that wedge. Read the memo before making positioning, copy, or scope suggestions — Sections 1–3 explain why the original framing was abandoned, Section 4 defines the chosen one.

Implications when working in this repo:

- **Audience is couples + planners, not venue admins.** Landing copy, imagery, and CTAs should speak to couples planning a wedding (already roughly the case in [Landing.tsx](frontend/src/app/views/Landing.tsx)). If you see venue-admin-flavored copy, that's a holdover, not the target.
- **Planned data model** lives in [docs/ERD.md](docs/ERD.md); MVP scope and acceptance criteria in [docs/user-stories.md](docs/user-stories.md). Both were rewritten for the coordinator framing — `Wedding` (owned by a couple, optionally managed by a planner) is the central object; `Venue` is kept as a first-class entity but VenueFlow does not sell to venues. Supplier deposits are tracked-only (couples pay suppliers directly).
- The submission requires **agent execution logs** as proof of "AI-native operations" — `AgentDecisionLog` is the central artifact and every autonomous agent action must land there.
