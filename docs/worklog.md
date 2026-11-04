# Worklog

An append-only log of notable changes — what we did, why, and any follow-up actions.
Newest entries at the top. One dated section per working session.

---

## 2026-11-04 (cleanup) — Legacy business screens removed (PD-003)

**Context:** The app still carried VenueFlow's SaaS surfaces: a payment gate that held back vendor matching, a mock checkout that recorded a €299 "succeeded" payment nobody made, planner and admin areas, and a public marketing site. The owner approved removing them, with nothing to keep.

**Done:**
- Removed checkout, payments, Stripe and the Stripe webhooks, `/metrics`, the planner login and role, `seed_pilot.py`, and the preview teaser and API gating.
- Removed the planner, admin and marketing screens. The app now opens on sign-in.
- The planner moves weddings straight to `planning`. Matching runs only when the couple ask (B11).
- Removed the verify checks for the removed routes, replaced with checks that they're gone. The demo-user count is now 2.

### Follow-ups / not done yet
- The `payments`/`subscriptions` tables and `planner_user_id` stay in the schema, unused. Dropping them needs a migration and a later decision.
- `README.md` is stale XPRIZE material and still describes Stripe and planners.

## 2026-11-04 (security) — Sign-in lock-down and access list (PD-002 step 1)

**Context:** Anyone could sign in as anyone: mock tokens were on by default, an HS256 path used a signing secret committed to this public repo, Firebase sign-up was open, and the planner login had no password. Worker `/tasks/*` routes and the payment and email webhooks needed no sign-in at all. Each wedding also had a single owner account, so the groom and family couldn't be given access.

**Done:**
- Sign-in fails closed. Mock auth is off by default, there's no default secret, and HS256 tokens need an expiry. Firebase needs the couple's own project and accepts only verified, listed emails.
- The first Alembic migrations: a baseline and `wedding_members`. Outside dev mode they're applied at startup, behind a Postgres advisory lock.
- Viewer, editor and owner levels, enforced in one place (`app/api/v1/access.py`).
- Only the couple can create the wedding, and only one.
- The worker routes and webhooks need their own secrets.
- `manage_access.py`, `verify_migrations.py`, and a plain-English owner guide (`docs/setup-sign-in.md`).
- Reviewed by three independent reviewers (general, security, data integrity). Every blocking finding is fixed.

### Follow-ups / not done yet
- B22: the owner's settings screen, owner-only actions, and the email-confirmation step the password fallback needs.
- B26: demo data seeds into production.
- B27: the migration check is SQLite-only.
- B14: hosting. Firebase authorised domains and a Postgres migration run depend on it.

## 2026-11-04 (product) — Wedding facts recorded, PD-001 ratified

**Context:** The product lane interviewed the owner (one of the couple) to fill in
`docs/product/wedding.md`, which was all `[GAP]`, and to confirm or correct PD-001.

**Done:** wedding facts recorded in the owner's words, roles only. The owner agreed
to these facts being in the public repo. PD-001 is ratified (single-wedding app). The
backlog is re-ranked against the couple's must-haves, with new items B22 (owner-managed
access), B23 (budgeting) and B24 (checklist).

### Follow-ups / not done yet
- `.agents/AGENTS.md:9` and `.agents/ai-studio-system-instructions.md` still call
  PD-001 "proposed" and say the app is used by the wedding party; access is couple and
  family for now. This needs an engineering edit.
- Proposed PDs for the couple next: access and permissions (B10/B22), hosting (B14),
  removing legacy SaaS surfaces (B12), then the scope of B23, B24 and B19.
- B24: check how the planner sets `TimelineItem.due_at` when the date is TBD.

---

## 2026-06-02 (fix) — Timeline fitted to the actual runway

**Context:** A couple starting ~7 months before a Dec-2026 wedding got a timeline running
**2024 → 2026** — the first milestone ("Set Budget & Guest List") was dated ~24 months
before the wedding (Dec 2024), i.e. ~18 months in the **past**. Cause: `planner.py`
computed `due_at = wedding_date − months_before` with **no clamping**, so any milestone
whose lead time exceeded the days remaining fell into the past. Not a date-parsing bug —
the plan just wasn't fitted to the time available.

**Fix (`backend/app/agents/planner.py`):** when the longest `months_before` exceeds the
days between today and the wedding, **compress all milestones proportionally into
`[today, wedding_date]`**, and floor every due date at today. Verified: for a 2026-12-30
wedding started 2026-06-02, the 24-month milestone now lands on today and the rest spread
across the real 7-month window (none in the past, order preserved). Applies to newly
generated plans; existing weddings need a re-plan to pick it up.

**Docs:** added the quota cap + this timeline behavior + vendor-seeding notes to
`CONTRIBUTING.md`.

## 2026-06-01 (data) — Vendor seed tooling + breadth (fix "same vendor" matches)

**Context:** The matcher kept suggesting the same 1–2 vendors because the seed pool was
tiny/lopsided (Dublin had only 3 venues; most supplier categories had 1 per region). With
so few candidates the LLM has nothing to choose from. Built two tools to grow the pool.

### Tools (both at `backend/`, run with the venv)
- `load_vendors_csv.py` + `data/venues.csv` + `data/suppliers.csv` — **CSV bulk loader** so
  a non-coder (Alan) can crowd-source *real* vendors from directories into a spreadsheet and
  import with one command. Idempotent (skips existing by name + region/location).
- `generate_demo_vendors.py` — **LLM generator** that creates realistic *fictional* Irish
  vendors per region/category via Gemini Flash, tagged `source="demo_generated"` with **no
  contact info** (so they're never passed off as real businesses). Idempotent; retries 503/429.

### Result
- Venues **25 → 51** (Dublin 8, Meath 8, Wicklow 7, Kildare 6, Galway 6, Cork 5) — the
  matcher now has real variety.
- Suppliers still **27**: the generator hit the **Gemini free-tier daily cap (20 requests/day)**
  before the supplier batch. Re-run `generate_demo_vendors.py` after the quota resets
  (idempotent — it'll skip venues and fill suppliers), or load via CSV.

### ⚠️ Ops flag (important for outreach demos)
- The free tier is **20 Flash requests/day**. One couple's flow (intake + 4-agent cascade +
  a few concierge questions + quote extractions) easily exceeds that — the live product will
  **429 mid-demo**. **Get a paid Gemini key before doing real prospect demos.**

### Follow-up
- Optional matcher tweak: pass a larger candidate set (~8–10) + light rotation so re-runs
  surface different options even with a modest pool.

## 2026-06-01 (P0) — Quote loop + live budget (the signature agent moment)

**Context:** Post-payment the product went static — `spent_amount` was always €0 and the
`quote_extractor` agent (reads a vendor email → structured quote → over-budget alert) had
no UI. Closed the loop so a couple can log a vendor reply and watch the AI update their
budget. This is the most coordinator-like moment and the agent-native proof for the XPRIZE.

### Backend
- `agents/extractor.py` — `quote_extractor` now **rolls the quote into the live budget**:
  on an available quote it sets the category's `BudgetLine.spent_amount = total_amount`
  (declined quotes don't count). The `budget_monitor` over-budget alert was already there.
- `api/v1/endpoints/weddings.py` — `GET /weddings/{id}/bookings` now joins the latest
  `Quote` + budget allocation per vendor and returns `quote_total`, `quote_currency`,
  `quote_rationale`, `allocated_amount`, `over_budget`.

### Frontend
- `wedding/views/Vendors.tsx` — added `QuoteLogger` (paste a vendor reply → POST
  `/inquiries/{booking_id}/quote` → poll until the agent result lands) and `QuotePanel`
  (shows the AI-read quote, over-budget badge, and the agent's rationale).
- `wedding/views/Budget.tsx` — over-budget categories now render red (capped bar + "€X
  over") plus a top-level over-budget banner; budget is live now that `spent_amount` moves.
- `api/useWedding.ts` — `Booking` type extended with the quote fields.

### Verification (real Gemini call, against the dev DB)
- Logged a simulated florist reply quoting €2,600 vs €2,000 allocated:
  booking → `quoted`; **`spent_amount` €0 → €2,600**; `budget_monitor` alert fired
  ("exceeds allocated by €600"); bookings API returned `over_budget=true`.
- `npm run build` passes; backend imports clean (34 routes).

### Follow-ups
- Quote rollup is "latest available quote per category" (projected spend) — refine to a
  proper quoted-vs-booked model when the booking-confirm flow lands.
- Wire SendGrid Inbound Parse later so replies auto-ingest instead of paste-in.

---

## 2026-06-01 (later) — Freemium preview teaser (value before paywall)

**Context:** The cold paywall (pay before seeing anything) converts badly. Switched to
**value-first**: run the cheap `intake_planner` for free at intake, show a teaser, and
gate the *expensive* venue/supplier cascade behind payment. Cost is aligned with value —
free = 1 Flash call; the 4-call cascade is paid-only.

**New state model:** `intake` (planner running) → `preview` (teaser, awaiting pay) →
`planning` (paid, cascade runs, full plan).

### Backend
- `agents/planner.py` — intake_planner now lands the wedding in **`preview`** on
  success (was `planning`).
- `worker/tasks.py` — extracted `_run_matcher_cascade` + `_mark_planning`;
  `/tasks/intake-planner` now runs the planner **only** (cascade gated; `with_cascade`
  flag for the dev/test path); added **`/tasks/plan-cascade`** (the paid cascade).
- `api/v1/endpoints/weddings.py` — `create_wedding` always runs the free preview
  (`with_cascade = not REQUIRE_PAYMENT`); **budget + timeline endpoints return only a
  teaser slice while status is `preview`** (`PREVIEW_BUDGET_LINES=3`,
  `PREVIEW_TIMELINE_ITEMS=2`) — full data withheld at the API so the blur can't be
  bypassed via DevTools.
- `api/v1/endpoints/payments.py` — `activate_wedding_planning` now enqueues
  **`plan-cascade`** (planner already ran free) and promotes to `planning`.

### Frontend
- `wedding/views/Dashboard.tsx` — added the **preview teaser**: partial budget +
  timeline with blurred `LockedRows` overlays, locked vendor cards, and the
  "Unlock your full plan + matched vendors · €299" CTA. Added cascade polling
  (`status==='planning' && no bookings`) so vendors appear after payment. The existing
  guardrail card ("your coordinator flagged something") still handles the blocked case.
- `wedding/views/Intake.tsx` — after create, navigate to `/wedding` (teaser) instead of
  straight to checkout.
- `wedding/views/Checkout.tsx` — guard now allows `preview` (only bounces once paid).

### Verification
- Backend imports: 34 routes, `/tasks/plan-cascade` registered.
- `verify_endpoints.py`: **all endpoint tests pass** (wedding still created in `intake`).
  (A trailing Windows-only `PermissionError` deleting the test SQLite file is a
  pre-existing teardown quirk, unrelated.)
- Frontend `npm run build`: succeeds.
- `RUNBOOK.md` "What happens on intake" + Testing section updated to the freemium flow.

---

## 2026-06-01 — Codebase review + payment gate (mock-now, Stripe-ready)

**Context:** Revenue is the priority (paying planners/couples + revenue proof for the
XPRIZE submission). A review found the team had heavily built the React/FastAPI
product surface while the actual revenue path was empty: **Stripe Checkout did not
exist** (only a webhook receiver + a dev mock), and intake **auto-ran the AI planner
on creation**, so payment gated nothing. Goal of this session: make payment a real
step in the flow, free for demos today, one env-flag away from real Stripe later.

### Security
- **Scrubbed a live-looking Gemini API key** that was committed in
  `backend/.env.example` (replaced with `your_gemini_api_key_here`).
  - ⚠️ **ACTION REQUIRED (owner): rotate that Gemini key** at
    https://aistudio.google.com/apikey — it was in git history and must be considered
    leaked. Put the real key only in a local `.env` (gitignored).

### Payment gate + Checkout (demo-now, Stripe-ready)
Decision (confirmed with founder): **real gate**, couple price **€299 one-time**.

- **Backend**
  - `app/config.py` — added `PAYMENTS_PROVIDER` (`mock` default | `stripe`),
    `REQUIRE_PAYMENT` (default `True`), `COUPLE_PRICE_EUR` (299), `STRIPE_SECRET_KEY`,
    `STRIPE_PUBLISHABLE_KEY`, `STRIPE_PRICE_ID`, `FRONTEND_BASE_URL`.
  - `app/api/v1/endpoints/payments.py` (new) — `POST /api/v1/payments/checkout`
    (authenticated, ownership-checked). Mock provider records a `Payment` row and
    starts planning instantly with **no charge**; Stripe provider creates a real
    Checkout Session (lazy `import stripe`). Also hosts the shared
    `activate_wedding_planning(db, wedding)` helper ("payment succeeded → status
    `planning` + enqueue `intake-planner`").
  - `app/api/v1/endpoints/webhooks.py` — `/stripe` and `/debug/stripe-mock` now call
    the shared `activate_wedding_planning` helper (removed duplicated logic).
  - `app/api/v1/endpoints/weddings.py` — `create_wedding` no longer auto-enqueues the
    planner when `REQUIRE_PAYMENT` is True; the wedding waits in `intake` until
    checkout completes.
  - `app/main.py` — registered the payments router.
  - `requirements.txt` — added `stripe>=8.0.0` (only used in stripe mode; mock works
    without it via lazy import).
- **Frontend**
  - `app/wedding/views/Checkout.tsx` (new) — €299 "Unlock your AI Wedding
    Coordinator" screen. Mock: pays server-side then routes to dashboard. Stripe:
    redirects to the hosted Checkout URL. Shows a "Demo checkout — no real charge" note.
  - `app/App.tsx` — added nested route `/wedding/checkout`.
  - `app/wedding/views/Intake.tsx` — after creating the wedding, redirect to
    `/wedding/checkout` (was `/wedding`); submit button now reads "Continue".
  - `app/api/config.ts` — added `COUPLE_PRICE_EUR = 299` (display only).

### Docs
- `docs/worklog.md`, `docs/timeline.md` created.
- `RUNBOOK.md` — added a **Testing the product** section (Path A: in-process
  `verify_*.py` on SQLite, no Docker; Path B: full end-to-end via `docker compose` /
  `stack.sh`). Also corrected the "What happens on intake" section, which still
  described the pre-gate flow (intake auto-ran the planner); it now reflects the
  payment-gated checkout step.

### Verification
- Backend: `python -c "import app.main"` imports cleanly — 33 routes, no circular
  import from the webhooks→payments→auth chain.
- Frontend: `npm run build` succeeds (built in ~13s).

### How to flip to real Stripe (test mode, still free)
1. `pip install stripe` (already in requirements).
2. In local `.env`: `PAYMENTS_PROVIDER=stripe`, `STRIPE_SECRET_KEY=sk_test_...`.
3. Run `stripe listen --forward-to localhost:8000/api/v1/webhooks/stripe` and use
   the test card `4242 4242 4242 4242`. No code change needed.

### Follow-ups / not done yet
- Rotate the leaked Gemini key (above).
- Deploy the app to a public URL (no live URL yet — blocks discovery-call demos).
- Reconcile the "Gemini 2.5 Pro" story: code defaults to Flash (free tier is 0-quota
  for Pro). Either use a paid key for Pro or change the README/narrative wording.
- Planner subscription checkout (€199/mo) still uses the static `Subscriptions.tsx`
  view — wire it the same way when planner-direct billing is needed.
- Demo capture scripts under `demo/` may assume the old intake→dashboard auto-plan
  flow; update them to go through checkout.
