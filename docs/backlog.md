# Backlog — known gaps and work queue

Tracked here so debt is visible. **Each item: what, where, why it matters for *this* wedding, the fix shape, and the product decision it depends on.** The product lane ranks items against the wedding date (`docs/product/wedding.md`); engineering closes them. Close an item by moving it to "Recently closed" with the fixing commit.

Convention: also drop a `# TODO(name, YYYY-MM-DD):` comment at the code site for in-flight items, and reconcile this file against `grep -rn TODO` when reviewing.

---

## Next up

*(Empty. The first autopilot run turns the ranking under "Open" into this ordered list, each item marked `ready` or `needs-owner: <question>`. See `docs/autonomy.md`.)*

## Open

Items B6–B21 come from the 2026-11-04 agent-setup audit, re-checked against the restored backend.

### Ranking (product lane, 2026-11-04)

Ranked against the couple's must-haves in `wedding.md` (1. in depth budgeting, 2. overall planning checklist, 3. guest planning: list, food, seating). The working date is the start of the August–October 2027 window the couple gave; the exact date is still [GAP]. The working date is a product-lane convention for ordering work, not a wedding fact.

1. **Before the wedding party puts real data in:** B10 (mock sign-in), B22 (owner-managed access), B12 (the checkout gate, `REQUIRE_PAYMENT`, sits in front of the couple's own app) and a hosting and storage PD (B14). Real guest data, including dietary notes, shouldn't go into an app anyone can sign in to. Before the first schema change on tables holding real data, migrations come first (AGENTS.md rule 6). The must-haves below will probably need schema changes.
2. **Must-have 1, in depth budgeting:** B23, plus the currency part of B11 (amounts shown in USD).
3. **Must-have 2, overall planning checklist:** B24.
4. **Must-have 3, guest planning:** B19.
5. **Vendor catalogue for Chicago:** the rest of B11, then B20. These rank below the must-haves because the couple are choosing a venue off their own shortlist and didn't list vendor matching as a must-have.
6. **Honesty fixes for data the couple will see:** B18, B8. Then B9, which depends on B12.
7. **Housekeeping:** B6 (an owner call, quick), B17, B15, B13.

Within each tier, how a must-have gets built is still to be decided. Each one needs a short proposed PD on scope before engineering starts.

### Trust and privacy

- **B6 — A third party's contacts are in a public repo.** `planner-targets.xlsx` (added in `3d728ff3`) is VenueFlow's sales prospect list from the XPRIZE period: named people at real planning businesses, with contact details. *Why it matters:* it's other people's personal data, published. *Fix:* the owner decides whether to delete it; if deleted, it stays in git history unless history is rewritten.
- **B8 — Unmeasured token counts are logged as 0.** Every agent records `"input"`/`"output"` tokens as `0` when Gemini returns no usage data (`usage... if usage else 0` in `planner.py`, `matcher.py`, `extractor.py`, `concierge.py`), so a missing measurement looks like a free call (AGENTS.md rule 10). *Fix:* record `None`, after checking that every consumer of those counts (metrics, logs, frontend) handles a missing value.
- **B9 — The admin agent log is hard-coded.** `frontend/src/app/admin/views/AgentLog.tsx:17` renders a fixed `ENTRIES` list of decisions for other couples' weddings ("Smith Wedding", "Vance Wedding") with invented confidence scores, instead of the real `AgentDecisionLog`. *Fix:* label it as sample data or wire it to `/logs`. *Depends on:* B12, since the admin surface may be removed.
- **B10 — Mock sign-in is on by default.** `DEVELOPMENT_MODE` and `ALLOW_MOCK_AUTH` default to `True` (`backend/app/config.py:21-22`), so any deployment that doesn't override them accepts `mock-<any id>` tokens (`api/v1/endpoints/auth.py:49`). Anyone can sign in as any existing user, or invent an id and get a new account auto-created (role `planner` if the id contains "planner"). *Fix:* default both to `False` with dev overrides in `.env.example`, configure Firebase, and allow-list the sign-ins of the people listed in `wedding.md`. *Depends on:* the access levels in `wedding.md`. Partner and family levels are now recorded (2026-11-04). Wedding party members who aren't family get no access for now, but will later (owner, 2026-11-04). See also B22 (owner-managed permissions).
- **B22 — The owner needs to add people and change their permissions.** The owner said (`wedding.md`, 2026-11-04): "i should be able to add and edit permissions in the future though". The access levels so far are partner (the groom): edit everything; family of the couple (parents 4, siblings 2): view only, including the budget. Wedding party members who aren't family get no access now, but "in the future yes", so the owner has to be able to add them later. The owner also needs to put several people in one role, e.g. several family members as "family": "roles only as long as I can assign mulitple people to 1 role" (owner, 2026-11-04). Today, roles come from the legacy SaaS model (`couple`/`planner`/`admin`), and with mock sign-in on, anyone can create an account (B10). There's no way for the owner to invite someone or set what they can do. *Why it matters:* family need view-only access, the partner needs full edit access, and the owner must be able to manage both later without engineering help. *Fix:* not yet chosen. Auth and access are stop-and-ask for engineering, so the approach (who can grant access, which permission levels, how people are invited) goes to the couple as a proposed PD first. *Depends on:* that PD. Do it with or after B10.
- **B18 — Metrics report 0.0 confidence when none was measured.** `backend/app/api/v1/endpoints/metrics.py:33` falls back to `0.0` when every row's confidence is NULL, which reads as "measured zero" (rule 10). *Fix:* return `null` and show "no data" in the UI.
- **B19 — Guest planning (must-have 3), but the guest list and seating plan show unlabelled sample data.** `frontend/src/app/wedding/views/Guests.tsx:9` (`GUESTS`, made-up names with dietary tags) and `SeatingPlan.tsx:13` (`GUESTS`, `INITIAL_TABLES`) are hard-coded and never call the API, on the couple's own workspace (rule 10). The backend has a `Guest` table (`backend/app/db/models.py:322`: name, email, phone, RSVP status, `dietary`, plus-one, table number), but no guest endpoint exists in `api/v1/endpoints/`. *Why it matters:* the couple listed "guest planning (list, food, seating)" as must-have 3, for 225 invited guests. Today nothing they enter would be saved. The "food" part includes dietary needs, which are health data (AGENTS.md rule 3). They must never appear in git, fixtures, issues, logs or `AgentDecisionLog` payloads. In the app, family (view only) can see them: "family can see dietary notes" (owner, 2026-11-04, `wedding.md`). *Fix:* label the sample data as sample now, as a quick and separate step. Then a proposed PD on guest-planning scope (what "food" covers, what seating needs), then backend guest endpoints and wiring. How it's built is not yet decided. *Depends on:* B10/B22 before real guest data goes in, and that PD.
- **B20 — The catalogue and its docstring overstate what's verified.** In `backend/app/db/seed_data_real.py`, 10 of 26 suppliers are unchecked (`_verify: True`) and 3 are `_template` placeholders with made-up names (lines 340–361). The docstring (lines 26–28) promises that inquiries route through `agents.resolve_inquiry_recipient` to an owner-controlled inbox, but no such function exists. *Fix:* check or remove the unchecked rows (`add-vendors` skill), keep templates out of recommendations, and correct the docstring.

### Making it fit this wedding

- **B11 — Ireland-only catalogue, but the wedding is in the US.** The regions (`utils/constants.py`), EUR and the vendor catalogue (`seed_data_real.py`) are all Irish. `wedding.md` now puts the wedding in Chicago, IL, United States (owner, 2026-11-04), so none of the 25 venues or 26 suppliers, and none of the regions, apply. The intake planner's budget logic assumes Irish pricing. *Why it matters:* venue and supplier matching can't recommend anything usable for this wedding. If it ran as it is, it would suggest Irish vendors. *Fix:* engineering change to raise, approach not yet decided. Covers regions, catalogue (cited Chicago-area vendors via `add-vendors`), and currency. The app currently assumes EUR everywhere, but the couple want amounts in US dollars (`wedding.md`, owner, 2026-11-04). Any new money fields use integer cents or `Decimal` (AGENTS.md rule 4). *Depends on:* a product decision on how to handle the catalogue, to be proposed. The venue status (shortlist being visited, not booked) suggests Chicago suppliers matter more than venues. *Ranking:* the currency part ranks with B23 (budgeting is must-have 1). The catalogue part ranks below the must-haves.
- **B12 — Legacy SaaS screens are still routed.** Checkout, the planner area (clients, tasks, subscriptions, analytics), the admin console and the marketing landing are all in `frontend/src/app/App.tsx`, and `REQUIRE_PAYMENT` defaults to `True`, gating the app behind checkout. *Depends on:* a PD on removal. PD-001 is ratified (single-wedding app, 2026-11-04), but that doesn't decide removal.

- **B23 — In depth budgeting (must-have 1).** The couple's top must-have is "in depth budgeting" (`wedding.md`). Today: the intake planner generates `BudgetLine` rows (category, allocated, spent; `backend/app/db/models.py:290`). The only budget endpoint is read-only (`GET /weddings/{id}/budget`, `weddings.py:202`), so the couple can't add or edit lines or record spending. Live budget lines are formatted as euros (`Budget.tsx:36`). When there are no live lines, `Budget.tsx:68` falls back to the hard-coded `STATIC_CATEGORIES`. Those show dollar figures (`Budget.tsx:8-9`, `16-17`) and dollar totals ("$24,500" spent of "$35,000", `Budget.tsx:69-70`). A couple budgeting in USD could mistake these for their real budget (rule 10). `BudgetLine` amounts are floats with no currency field (`models.py:290`). The `EUR` defaults are on other models (`models.py:52`, `216`, `250`, `267`, `280`). *Why it matters:* it's the couple's first priority, and the partner (edit everything) and family (view only, including the budget) will both use it. The total budget is still [GAP]: "still being determined" (owner, 2026-11-04). *Fix:* not yet decided. Needs a proposed PD on what "in depth" means to the couple (for example editable lines, actual vs planned, payments due), then the build. Shown in USD (B11). New money fields use integer cents or `Decimal` (rule 4). Check whether the static fallback is labelled as sample (rule 10). Agents never mark anything paid (rule 4). *Depends on:* that PD, and B10/B22 before real figures go in.
- **B24 — Overall planning checklist (must-have 2).** The couple's second must-have is an "overall planning checklist" (`wedding.md`). Today: the intake planner generates `TimelineItem` rows (title, due date, status `todo`/`in_progress`/`done`; `models.py:305`), compressed into the time between today and the wedding date. The only timeline endpoint is read-only (`GET /weddings/{id}/timeline`, `weddings.py:227`), so items can't be ticked off, added or edited. When there are no live items, `Timeline.tsx:87` falls back to the hard-coded `STATIC_ITEMS`. *Why it matters:* it's the couple's second priority. [ASSUMPTION] The planner needs a single wedding date, but the couple have given a window (August–October 2027), not a date. `planner.py:58` handles a TBD date as a range, with relative descriptions, while `TimelineItem.due_at` is a non-null date (`models.py:313`). An engineer needs to check how the TBD path actually sets `due_at`. The planner's prompt (`backend/app/agents/planner.py:49-55`) has ceremony rules for 'Irish Catholic', 'Civil/Humanist', 'Hindu' and 'Multi-cultural' only, all in Irish terms, and none for a Jewish ceremony. The couple want "the usual jewish traditions", but which traditions is [GAP]. *Fix:* not yet decided. Needs a proposed PD on checklist scope, including how to handle an unfixed date without the app inventing one, and which tradition-specific items to include, asked of the couple rather than assumed. Check whether the static fallback is labelled as sample (rule 10). *Depends on:* that PD.

### Housekeeping

- **B13 — Stale material from the prototype and the XPRIZE.** `streamlit_mock/` (still referenced by `README.md`, `CONTRIBUTING.md`, `docs/runway.md`, `docs/reviews/2026-05-27.md` and `scripts/build_tracker.py`), the `.xlsx` trackers, and the XPRIZE framing in `README.md`, `docs/runway.md`, `docs/strategic-memo.md` and `docs/reviews/`. *Fix:* archive or delete them (owner's call).
- **B14 — The deploy workflow would publish a frontend with no backend.** `.github/workflows/deploy.yml` publishes `frontend/` to GitHub Pages at VenueFlow's domain, `venueflow.ie` (`frontend/public/CNAME`), on every push to `main`. It sets no `VITE_API_URL`, so the published site would have no backend. No runs are recorded on this repo. *Fix:* decide where the app and its backend are hosted, then point the workflow at that. Keep or drop the domain as part of that decision. *Depends on:* a PD on hosting (couple's call).
- **B15 — CI is new and untested.** `.github/workflows/ci.yml` runs the backend verify scripts and the frontend build on every PR. *Fix:* confirm the first run passes, then make `CI / backend` and `CI / frontend` required checks (see `docs/autonomy.md`).
- **B17 — The verify scripts rewrite tracked files.** `backend/endpoints_test.db` and its `-shm`/`-wal` files are committed, and every run of `verify_endpoints.py` changes them; the other scripts leave untracked `-shm`/`-wal` files. `.gitignore` already lists `endpoints_test.db*`, but the files were committed before that. *Fix:* `git rm --cached` them and widen the ignore rule to `backend/*_test.db*`.
- **B25 — Unattended agents need a first test.** `.github/workflows/claude-agents.yml` is new, and its third-party plugins aren't pinned to a version. Known gaps from its review (2026-11-04):
  - Nothing scans agent commits for secrets: the gitleaks hook runs only locally, and CI has no gitleaks step.
  - The tool list allows `git push origin agent/x --delete` and edits to `.claude/hooks/`.
  - The "Next up" list carries no date, so "older than 14 days" can't be checked.
  - With no open PR, there's nowhere to post `[BLOCKED]`.
  - The `reply` job installs no dependencies, so it can't run the verify gate.
  
  *Fix:* follow the test checklist in `docs/autonomy.md` before relying on it, then close these gaps.

Not carried over from the audit, because the restored backend already covers them: invented concierge prices in the old `mockService.ts` (the concierge now calls Gemini through the backend), data living in one browser (the backend has a database), and "no real AI" (the agents call Gemini).

---

## Recently closed

| Closed | Item | Resolved by |
|---|---|---|
| 2026-11-04 | **B21** — `sqlmodel` ceiling not enforced (CI pulled 0.0.48 and the verify scripts failed on naive datetimes) | this PR (#6) |
| 2026-11-04 | **B16** — `greenlet` missing from `requirements.txt` (backend verify crashed on Apple Silicon and in CI) | this PR (#6) |
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
