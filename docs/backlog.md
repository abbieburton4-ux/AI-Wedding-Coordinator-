# Backlog — known gaps and work queue

Tracked here so debt is visible. **Each item: what, where, why it matters for *this* wedding, the fix shape, and the product decision it depends on.** The product lane ranks items against the wedding date (`docs/product/wedding.md`); engineering closes them. Close an item by moving it to "Recently closed" with the fixing commit.

Convention: also drop a `# TODO(name, YYYY-MM-DD):` comment at the code site for in-flight items, and reconcile this file against `grep -rn TODO` when reviewing.

---

## Open

Items B6–B21 come from the 2026-11-04 agent-setup audit, re-checked against the restored backend. They're unranked until the wedding date is known.

### Trust and privacy

- **B6 — A third party's contacts are in a public repo.** `planner-targets.xlsx` (added in `3d728ff3`) is VenueFlow's sales prospect list from the XPRIZE period: named people at real planning businesses, with contact details. *Why it matters:* it's other people's personal data, published. *Fix:* the owner decides whether to delete it; if deleted, it stays in git history unless history is rewritten.
- **B8 — Unmeasured token counts are logged as 0.** Every agent records `"input"`/`"output"` tokens as `0` when Gemini returns no usage data (`usage... if usage else 0` in `planner.py`, `matcher.py`, `extractor.py`, `concierge.py`), so a missing measurement looks like a free call (AGENTS.md rule 10). *Fix:* record `None`, after checking that every consumer of those counts (metrics, logs, frontend) handles a missing value.
- **B9 — The admin agent log is hard-coded.** `frontend/src/app/admin/views/AgentLog.tsx:17` renders a fixed `ENTRIES` list of decisions for other couples' weddings ("Smith Wedding", "Vance Wedding") with invented confidence scores, instead of the real `AgentDecisionLog`. *Fix:* label it as sample data or wire it to `/logs`. *Depends on:* B12, since the admin surface may be removed.
- **B10 — Mock sign-in is on by default.** `DEVELOPMENT_MODE` and `ALLOW_MOCK_AUTH` default to `True` (`backend/app/config.py:21-22`), so any deployment that doesn't override them accepts `mock-<any id>` tokens (`api/v1/endpoints/auth.py:49`). Anyone can sign in as any existing user, or invent an id and get a new account auto-created (role `planner` if the id contains "planner"). *Fix:* default both to `False` with dev overrides in `.env.example`, configure Firebase, and allow-list the wedding party's sign-ins. *Depends on:* the access levels in `wedding.md`.
- **B18 — Metrics report 0.0 confidence when none was measured.** `backend/app/api/v1/endpoints/metrics.py:33` falls back to `0.0` when every row's confidence is NULL, which reads as "measured zero" (rule 10). *Fix:* return `null` and show "no data" in the UI.
- **B19 — The guest list and seating plan show unlabelled sample data.** `frontend/src/app/wedding/views/Guests.tsx:9` (`GUESTS`, made-up names with dietary tags) and `SeatingPlan.tsx:13` (`GUESTS`, `INITIAL_TABLES`) are hard-coded and never call the API, on the couple's own workspace (rule 10). *Fix:* label them as sample now; wire them to the backend's guest data before the couple relies on them.
- **B20 — The catalogue and its docstring overstate what's verified.** In `backend/app/db/seed_data_real.py`, 10 of 26 suppliers are unchecked (`_verify: True`) and 3 are `_template` placeholders with made-up names (lines 340–361). The docstring (lines 26–28) promises that inquiries route through `agents.resolve_inquiry_recipient` to an owner-controlled inbox, but no such function exists. *Fix:* check or remove the unchecked rows (`add-vendors` skill), keep templates out of recommendations, and correct the docstring.
- **B21 — The `sqlmodel` ceiling isn't enforced.** AGENTS.md rule 9 says to keep `sqlmodel` below 0.0.25 until the naive datetimes are fixed, but `backend/requirements.txt:3` is `sqlmodel>=0.0.16`, so a fresh install can pull a newer version. *Fix:* pin `sqlmodel>=0.0.16,<0.0.25`, after confirming which version the verify scripts pass on.

### Making it fit this wedding

- **B11 — Ireland-only catalogue.** The regions (`utils/constants.py`), EUR and the vendor catalogue (`seed_data_real.py`) are all Irish. *Depends on:* the country in `wedding.md`.
- **B12 — Legacy SaaS screens are still routed.** Checkout, the planner area (clients, tasks, subscriptions, analytics), the admin console and the marketing landing are all in `frontend/src/app/App.tsx`, and `REQUIRE_PAYMENT` defaults to `True`, gating the app behind checkout. *Depends on:* PD-001 and a PD on removal.

### Housekeeping

- **B13 — Stale material from the prototype and the XPRIZE.** `streamlit_mock/` (still referenced by `README.md`, `CONTRIBUTING.md`, `docs/runway.md`, `docs/reviews/2026-05-27.md` and `scripts/build_tracker.py`), the `.xlsx` trackers, and the XPRIZE framing in `README.md`, `docs/runway.md`, `docs/strategic-memo.md` and `docs/reviews/`. *Fix:* archive or delete them (owner's call).
- **B14 — The deploy workflow would publish a frontend with no backend.** `.github/workflows/deploy.yml` publishes `frontend/` to GitHub Pages at VenueFlow's domain, `venueflow.ie` (`frontend/public/CNAME`), on every push to `main`. It sets no `VITE_API_URL`, so the published site would have no backend. No runs are recorded on this repo. *Fix:* decide where the app and its backend are hosted, then point the workflow at that. Keep or drop the domain as part of that decision. *Depends on:* a PD on hosting (couple's call).
- **B15 — No CI on pull requests.** Nothing runs the backend verify scripts or the frontend build on PRs. *Fix:* a small workflow running the `verify` skill's steps.
- **B16 — `greenlet` is missing from `requirements.txt`.** SQLAlchemy's async engine needs it, and it isn't installed automatically on Apple Silicon, so `verify_endpoints.py` and `verify_agents.py` crash there. *Fix:* add it, with the one-line reason rule 9 asks for.
- **B17 — The verify scripts rewrite tracked files.** `backend/endpoints_test.db` and its `-shm`/`-wal` files are committed, and every run of `verify_endpoints.py` changes them; the other scripts leave untracked `-shm`/`-wal` files. `.gitignore` already lists `endpoints_test.db*`, but the files were committed before that. *Fix:* `git rm --cached` them and widen the ignore rule to `backend/*_test.db*`.

Not carried over from the audit, because the restored backend already covers them: invented concierge prices in the old `mockService.ts` (the concierge now calls Gemini through the backend), data living in one browser (the backend has a database), and "no real AI" (the agents call Gemini).

---

## Recently closed

| Closed | Item | Resolved by |
|---|---|---|
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
