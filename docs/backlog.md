# Backlog — known gaps and work queue

Tracked here so debt is visible. **Each item: what, where, why it matters for *this* wedding, the fix shape, and the product decision it depends on.** The product lane ranks items against the wedding date (`docs/product/wedding.md`); engineering closes them. Close an item by moving it to "Recently closed" with the fixing commit.

Convention: also drop a `# TODO(name, YYYY-MM-DD):` comment at the code site for in-flight items, and reconcile this file against `grep -rn TODO` when reviewing.

---

## Open

Items B6–B21 come from the 2026-11-04 agent-setup audit, re-checked against the restored backend.

### Ranking (product lane, 2026-11-04)

Ranked against the couple's must-haves in `wedding.md` (1. in depth budgeting, 2. overall planning checklist, 3. guest planning: list, food, seating). The working date is the start of the August–October 2027 window the couple gave; the exact date is still [GAP]. The working date is a product-lane convention for ordering work, not a wedding fact.

1. **Before the wedding party puts real data in:** B22 (owner-managed access; step 1 done), B12 (the checkout gate, `REQUIRE_PAYMENT`, sits in front of the couple's own app) and a hosting and storage PD (B14). Real guest data, including dietary notes, shouldn't go into an app anyone can sign in to. Before the first schema change on tables holding real data, migrations come first (AGENTS.md rule 6). The must-haves below will probably need schema changes.
2. **Must-have 1, in depth budgeting:** B23, plus the currency part of B11 (amounts shown in USD).
3. **Must-have 2, overall planning checklist:** B24.
4. **Must-have 3, guest planning:** B19.
5. **Vendor catalogue for Chicago:** the rest of B11, then B20. These rank below the must-haves because the couple are choosing a venue off their own shortlist and didn't list vendor matching as a must-have.
6. **Honesty fixes for data the couple will see:** B18, B8. Then B9, which depends on B12.
7. **Housekeeping:** B6 (an owner call, quick), B16, B17, B21, B15, B13.

Within each tier, how a must-have gets built is still to be decided. Each one needs a short proposed PD on scope before engineering starts.

### Trust and privacy

- **B6 — A third party's contacts are in a public repo.** `planner-targets.xlsx` (added in `3d728ff3`) is VenueFlow's sales prospect list from the XPRIZE period: named people at real planning businesses, with contact details. *Why it matters:* it's other people's personal data, published. *Fix:* the owner decides whether to delete it; if deleted, it stays in git history unless history is rewritten.
- **B8 — Unmeasured token counts are logged as 0.** Every agent records `"input"`/`"output"` tokens as `0` when Gemini returns no usage data (`usage... if usage else 0` in `planner.py`, `matcher.py`, `extractor.py`, `concierge.py`), so a missing measurement looks like a free call (AGENTS.md rule 10). *Fix:* record `None`, after checking that every consumer of those counts (metrics, logs, frontend) handles a missing value.
- **B9 — The admin agent log is hard-coded.** `frontend/src/app/admin/views/AgentLog.tsx:17` renders a fixed `ENTRIES` list of decisions for other couples' weddings ("Smith Wedding", "Vance Wedding") with invented confidence scores, instead of the real `AgentDecisionLog`. *Fix:* label it as sample data or wire it to `/logs`. *Depends on:* B12, since the admin surface may be removed.
- **B22 — The owner and the groom manage access themselves (PD-002 step 2).** Step 1 is done (2026-11-04): sign-in is locked down, and the access list (`wedding_members`) has viewer, editor and owner levels. The couple's emails (`ACCESS_BOOTSTRAP_EMAILS`) become owners when the wedding is created, and the team edits the list with `backend/manage_access.py`. What's left, with the owner's words in `wedding.md` ("i should be able to add and edit permissions in the future though"; "roles only as long as I can assign mulitple people to 1 role"):
  - **A settings screen** where the owner or groom adds an email, picks "can edit" or "view only", and changes or removes it. Several people can share a level. Wedding party members who aren't family get added here later.
  - **Owner-only actions:** today an `owner` row has the same powers as an `editor`. Managing the list should need `owner`.
  - **Email and password fallback:** PD-002 ratified it, but it doesn't work yet. New accounts need a verified email, and the app has no "confirm your email" step, so family without a Google account can't get in. Adding that step means Firebase sends a confirmation email when the person asks for one, in the same way as the password reset PD-002 already accepts. Until it exists, the setup guide tells the couple to turn on Google sign-in only.
  - *Depends on:* PD-002 (ratified). The email-confirmation step may need the couple's OK, since it's an email to a family member (raised at the 2026-11-04 checkpoint).
- **B18 — Metrics report 0.0 confidence when none was measured.** `backend/app/api/v1/endpoints/metrics.py:33` falls back to `0.0` when every row's confidence is NULL, which reads as "measured zero" (rule 10). *Fix:* return `null` and show "no data" in the UI.
- **B19 — Guest planning (must-have 3), but the guest list and seating plan show unlabelled sample data.** `frontend/src/app/wedding/views/Guests.tsx:9` (`GUESTS`, made-up names with dietary tags) and `SeatingPlan.tsx:13` (`GUESTS`, `INITIAL_TABLES`) are hard-coded and never call the API, on the couple's own workspace (rule 10). The backend has a `Guest` table (`backend/app/db/models.py:322`: name, email, phone, RSVP status, `dietary`, plus-one, table number), but no guest endpoint exists in `api/v1/endpoints/`. *Why it matters:* the couple listed "guest planning (list, food, seating)" as must-have 3, for 225 invited guests. Today nothing they enter would be saved. The "food" part includes dietary needs, which are health data (AGENTS.md rule 3). They must never appear in git, fixtures, issues, logs or `AgentDecisionLog` payloads. In the app, family (view only) can see them: "family can see dietary notes" (owner, 2026-11-04, `wedding.md`). *Fix:* label the sample data as sample now, as a quick and separate step. Then a proposed PD on guest-planning scope (what "food" covers, what seating needs), then backend guest endpoints and wiring. How it's built is not yet decided. *Depends on:* B10/B22 before real guest data goes in, and that PD.
- **B20 — The catalogue and its docstring overstate what's verified.** In `backend/app/db/seed_data_real.py`, 10 of 26 suppliers are unchecked (`_verify: True`) and 3 are `_template` placeholders with made-up names (lines 340–361). The docstring (lines 26–28) promises that inquiries route through `agents.resolve_inquiry_recipient` to an owner-controlled inbox, but no such function exists. *Fix:* check or remove the unchecked rows (`add-vendors` skill), keep templates out of recommendations, and correct the docstring.
- **B21 — The `sqlmodel` ceiling isn't enforced.** AGENTS.md rule 9 says to keep `sqlmodel` below 0.0.25 until the naive datetimes are fixed, but `backend/requirements.txt:3` is `sqlmodel>=0.0.16`, so a fresh install can pull a newer version. *Fix:* pin `sqlmodel>=0.0.16,<0.0.25`, after confirming which version the verify scripts pass on.

### Making it fit this wedding

- **B11 — Ireland-only catalogue, but the wedding is in the US.** The regions (`utils/constants.py`), EUR and the vendor catalogue (`seed_data_real.py`) are all Irish. `wedding.md` now puts the wedding in Chicago, IL, United States (owner, 2026-11-04), so none of the 25 venues or 26 suppliers, and none of the regions, apply. The intake planner's budget logic assumes Irish pricing. *Why it matters:* venue and supplier matching can't recommend anything usable for this wedding. If it ran as it is, it would suggest Irish vendors. *Fix:* engineering change to raise, approach not yet decided. Covers regions, catalogue (cited Chicago-area vendors via `add-vendors`), and currency. The app currently assumes EUR everywhere, but the couple want amounts in US dollars (`wedding.md`, owner, 2026-11-04). Any new money fields use integer cents or `Decimal` (AGENTS.md rule 4). *Depends on:* a product decision on how to handle the catalogue, to be proposed. The venue status (shortlist being visited, not booked) suggests Chicago suppliers matter more than venues. *Ranking:* the currency part ranks with B23 (budgeting is must-have 1). The catalogue part ranks below the must-haves.
- **B12 — Legacy SaaS screens are still routed.** Checkout, the planner area (clients, tasks, subscriptions, analytics), the admin console and the marketing landing are all in `frontend/src/app/App.tsx`, and `REQUIRE_PAYMENT` defaults to `True`, gating the app behind checkout. *Depends on:* a PD on removal. PD-001 is ratified (single-wedding app, 2026-11-04), but that doesn't decide removal.

- **B23 — In depth budgeting (must-have 1).** The couple's top must-have is "in depth budgeting" (`wedding.md`). Today: the intake planner generates `BudgetLine` rows (category, allocated, spent; `backend/app/db/models.py:290`). The only budget endpoint is read-only (`GET /weddings/{id}/budget`, `weddings.py:202`), so the couple can't add or edit lines or record spending. Live budget lines are formatted as euros (`Budget.tsx:36`). When there are no live lines, `Budget.tsx:68` falls back to the hard-coded `STATIC_CATEGORIES`. Those show dollar figures (`Budget.tsx:8-9`, `16-17`) and dollar totals ("$24,500" spent of "$35,000", `Budget.tsx:69-70`). A couple budgeting in USD could mistake these for their real budget (rule 10). `BudgetLine` amounts are floats with no currency field (`models.py:290`). The `EUR` defaults are on other models (`models.py:52`, `216`, `250`, `267`, `280`). *Why it matters:* it's the couple's first priority, and the partner (edit everything) and family (view only, including the budget) will both use it. The total budget is still [GAP]: "still being determined" (owner, 2026-11-04). *Fix:* not yet decided. Needs a proposed PD on what "in depth" means to the couple (for example editable lines, actual vs planned, payments due), then the build. Shown in USD (B11). New money fields use integer cents or `Decimal` (rule 4). Check whether the static fallback is labelled as sample (rule 10). Agents never mark anything paid (rule 4). *Depends on:* that PD, and B10/B22 before real figures go in.
- **B24 — Overall planning checklist (must-have 2).** The couple's second must-have is an "overall planning checklist" (`wedding.md`). Today: the intake planner generates `TimelineItem` rows (title, due date, status `todo`/`in_progress`/`done`; `models.py:305`), compressed into the time between today and the wedding date. The only timeline endpoint is read-only (`GET /weddings/{id}/timeline`, `weddings.py:227`), so items can't be ticked off, added or edited. When there are no live items, `Timeline.tsx:87` falls back to the hard-coded `STATIC_ITEMS`. *Why it matters:* it's the couple's second priority. [ASSUMPTION] The planner needs a single wedding date, but the couple have given a window (August–October 2027), not a date. `planner.py:58` handles a TBD date as a range, with relative descriptions, while `TimelineItem.due_at` is a non-null date (`models.py:313`). An engineer needs to check how the TBD path actually sets `due_at`. The planner's prompt (`backend/app/agents/planner.py:49-55`) has ceremony rules for 'Irish Catholic', 'Civil/Humanist', 'Hindu' and 'Multi-cultural' only, all in Irish terms, and none for a Jewish ceremony. The couple want "the usual jewish traditions", but which traditions is [GAP]. *Fix:* not yet decided. Needs a proposed PD on checklist scope, including how to handle an unfixed date without the app inventing one, and which tradition-specific items to include, asked of the couple rather than assumed. Check whether the static fallback is labelled as sample (rule 10). *Depends on:* that PD.

### Housekeeping

- **B13 — Stale material from the prototype and the XPRIZE.** `streamlit_mock/` (still referenced by `README.md`, `CONTRIBUTING.md`, `docs/runway.md`, `docs/reviews/2026-05-27.md` and `scripts/build_tracker.py`), the `.xlsx` trackers, and the XPRIZE framing in `README.md`, `docs/runway.md`, `docs/strategic-memo.md` and `docs/reviews/`. *Fix:* archive or delete them (owner's call).
- **B14 — The deploy workflow would publish a frontend with no backend.** `.github/workflows/deploy.yml` publishes `frontend/` to GitHub Pages at VenueFlow's domain, `venueflow.ie` (`frontend/public/CNAME`), on every push to `main`. It sets no `VITE_API_URL`, so the published site would have no backend. No runs are recorded on this repo. *Fix:* decide where the app and its backend are hosted, then point the workflow at that. Keep or drop the domain as part of that decision. *Depends on:* a PD on hosting (couple's call).
- **B15 — No CI on pull requests.** Nothing runs the backend verify scripts or the frontend build on PRs. *Fix:* a small workflow running the `verify` skill's steps.
- **B16 — `greenlet` is missing from `requirements.txt`.** SQLAlchemy's async engine needs it, and it isn't installed automatically on Apple Silicon, so `verify_endpoints.py` and `verify_agents.py` crash there. *Fix:* add it, with the one-line reason rule 9 asks for.
- **B17 — The verify scripts rewrite tracked files.** `backend/endpoints_test.db` and its `-shm`/`-wal` files are committed, and every run of `verify_endpoints.py` changes them; the other scripts leave untracked `-shm`/`-wal` files. `.gitignore` already lists `endpoints_test.db*`, but the files were committed before that. *Fix:* `git rm --cached` them and widen the ignore rule to `backend/*_test.db*`.

Not carried over from the audit, because the restored backend already covers them: invented concierge prices in the old `mockService.ts` (the concierge now calls Gemini through the backend), data living in one browser (the backend has a database), and "no real AI" (the agents call Gemini).

---

- **B26 — Demo data is seeded into every database.** `seed_database()` (`backend/app/db/seed.py`) runs on every startup, production included. It adds demo users (`couple_1`, `couple_2`, `planner_1`) and demo weddings when the database is empty. *Why it matters:* the real database would hold made-up couples, and `planner_1`'s email may belong to a real business (rule 3). *Fix:* seed only in `DEVELOPMENT_MODE`; keep the vendor catalogue seed separate.
- **B27 — The migration check can't see Postgres-only drift.** `verify_migrations.py` runs on SQLite, which doesn't compare CHECK constraints or server defaults. `env.py` has no `render_as_batch` and no constraint naming convention, so the first migration that alters or drops a column or constraint may fail on SQLite or can't name the FK. *Fix:* add a naming convention and `render_as_batch=True` before the next schema change, and run the migration check against Postgres in CI once hosting is decided (B14).

## Recently closed

| Closed | Item | Resolved by |
|---|---|---|
| 2026-11-04 | **B10** — mock sign-in on by default, plus a committed default HS256 secret, open Firebase sign-up and a password-less planner login | PD-002 step 1 (this branch) |
| 2026-11-04 | **B7** — unmeasured confidence logged as 1.0 (also 0.8 and 0.0 in each agent) | `ab3ef135` |
| 2026-05-27 | Tab 1 plotly Gold crash | `2032afa6` |
| 2026-05-27 | Region dropdown vs. seed county mismatch | `2032afa6` |
| 2026-05-27 | Supplier dropdown hardcoded to 4 categories | `2ba17b20` |
| 2026-05-27 | Case-sensitive whitelist false positives | `61f34bb2` |
| 2026-05-27 | No test coverage for whitelist + missing wedding | `4c3412f6` |
| 2026-05-27 | Bare `except:` in log viewer | `36806099` |
| 2026-05-27 | Pydantic Field description hardcoded | `36806099` |
| 2026-05-27 | **B3** — category enum in 3 places | `8911810a` |
| 2026-05-27 | **B4** — no Irish region hierarchy for matcher pre-filter | `c42db925` |
| 2026-05-27 | **B1** — agents don't pre-validate `wedding_id` | `b02dbde1` |
| 2026-05-27 | **B2** — `quote_extractor` category fallthrough to 'venue' | `1eab8426` |
| 2026-05-27 | **B5** — refactor commit hygiene (convention codified) | `af97128b` |
