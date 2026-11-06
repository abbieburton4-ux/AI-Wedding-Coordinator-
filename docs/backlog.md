# Backlog — known gaps and work queue

Tracked here so debt is visible. **Each item: what, where, why it matters for *this* wedding, the fix shape, and the product decision it depends on.** The product lane ranks items against the wedding date (`docs/product/wedding.md`); engineering closes them. Close an item by moving it to "Recently closed" with the fixing commit.

Convention: also drop a `# TODO(name, YYYY-MM-DD):` comment at the code site for in-flight items, and reconcile this file against `grep -rn TODO` when reviewing.

---

## Next up

*Updated 2026-11-06 by the product lane. Re-rank if this date is more than 14 days old.*

0. **B32** — two Claude reply bots and an automatic PR review. Owner, 2026-11-05: "yes, turn off the extra reply bot and Turn off the automatic review on every PR". Done 2026-11-05: both workflows are disabled in the Actions tab, at the owner's request. Their files stay in `.github/workflows/`; deleting them needs a session the owner runs.
1. **B53** — the live checklist is empty until the one-time import of the owner's list runs. `needs-owner: run the import on Replit (the team gives step-by-step instructions)`
2. **B49** — make sure no AI feature sends guest names, contact details or dietary notes to Gemini (PD-008 follow-up, ratified). `in review` (#44). `needs-owner: names the filter doesn't know yet (typed into chat, a task or a pasted vendor email): (1) show the cleaned text to check before sending (recommended), (2) send automatically, as #44 does now, or (3) turn off AI quote reading`
3. **B48** — a "This date is confirmed" switch that hides the "Dates are provisional" note. `ready` (owner, 2026-11-05: "yes to the provisional dates note")
4. **B45** — the budget screen uses the server's date, not Chicago's; date tests can fail falsely around midnight in Chicago. `ready`
5. **B44** — move the other parts that still read the old euro budget lines to the new budget. `ready`
6. **B43** — small follow-ups from the B23 fix review (wider price filter on AI reasons, three screen tidy-ups). `ready`
7. **B41** — small follow-ups from the B39 review (one tool fix, two tests, one message). `ready`
8. **B40** — remove past sales prospects' first names from `docs/runway.md`, `scripts/build_tracker.py` and `runway-tracker.xlsx` (PD-005, extended again). `ready`
9. **B14** — host the app on Replit (PD-008, ratified: free AI tier, $50 spending alert, US data location, free `.replit.app` address). `ready` (after B46 and B47).
10. **B19** — guest planning: list, food, seating. `needs-owner: guest-planning scope PD, to be proposed`
11. **B33** — stop the backend accepting calls from the original VenueFlow author's website. `ready`
12. **B34** — database-level guard against the same email being added twice. `ready`
13. **B35** — add Firebase's email-enumeration protection to the sign-in setup guide. `ready`
14. **B29** — real budget and checklist briefly show labelled sample content while loading. `ready`
15. **B8** — record missing token counts as empty, not 0. `ready`
16. **B17** — stop tracking the test database files. `ready`
17. **B36** — refresh "What's actually there today" in `.agents/AGENTS.md` and its AI Studio copy. `needs-owner: guardrail files need a session the owner runs`
18. **B52** — move Replit and the automatic checks from Node 20 to Node 22. `ready`

## Open

Items B6–B21 come from the 2026-11-04 agent-setup audit, re-checked against the restored backend.

### Ranking (product lane, 2026-11-04)

Ranked against the couple's must-haves in `wedding.md` (1. in depth budgeting, 2. overall planning checklist, 3. guest planning: list, food, seating). The working date is the start of the August–October 2027 window the couple gave; the exact date is still [GAP]. The working date is a product-lane convention for ordering work, not a wedding fact.

1. **Before the wedding party puts real data in:** B22 (owner-managed access; step 1 done) and a hosting and storage PD (B14). Real guest data, including dietary notes, shouldn't go into an app anyone can sign in to. Before the first schema change on tables holding real data, migrations come first (AGENTS.md rule 6). The must-haves below will probably need schema changes.
2. **Must-have 1, in depth budgeting:** B23, plus the currency part of B11 (amounts shown in USD).
3. **Must-have 2, overall planning checklist:** B24 (done, #32); the tasks load after hosting (B14, B46).
4. **Must-have 3, guest planning:** B19.
5. **Vendor catalogue for Chicago:** the rest of B11, then B20. These rank below the must-haves because the couple are choosing a venue off their own shortlist and didn't list vendor matching as a must-have.
6. **Honesty fixes for data the couple will see:** B8.
7. **Housekeeping:** B6 (an owner call, quick), B17, B15, B13.

Within each tier, how a must-have gets built is still to be decided. Each one needs a short proposed PD on scope before engineering starts.

### Trust and privacy

- **B8 — Unmeasured token counts are logged as 0.** Every agent records `"input"`/`"output"` tokens as `0` when Gemini returns no usage data (`usage... if usage else 0` in `planner.py`, `matcher.py`, `extractor.py`, `concierge.py`), so a missing measurement looks like a free call (AGENTS.md rule 10). *Fix:* record `None`, after checking that every consumer of those counts (metrics, logs, frontend) handles a missing value.
- **B22 — The owner and the groom manage access themselves (PD-002 step 2).** Done in PR #14: the access settings screen, owner-only access changes, and email confirmation for password sign-in. The remaining follow-up is B38.
- **B19 — Guest planning (must-have 3), but the guest list and seating plan show unlabelled sample data.** `frontend/src/app/wedding/views/Guests.tsx:9` (`GUESTS`, made-up names with dietary tags) and `SeatingPlan.tsx:13` (`GUESTS`, `INITIAL_TABLES`) are hard-coded and never call the API, on the couple's own workspace (rule 10). The backend has a `Guest` table (`backend/app/db/models.py:322`: name, email, phone, RSVP status, `dietary`, plus-one, table number), but no guest endpoint exists in `api/v1/endpoints/`. *Why it matters:* the couple listed "guest planning (list, food, seating)" as must-have 3, for 225 invited guests. Today nothing they enter would be saved. The "food" part includes dietary needs, which are health data (AGENTS.md rule 3). They must never appear in git, fixtures, issues, logs or `AgentDecisionLog` payloads. In the app, family (view only) can see them: "family can see dietary notes" (owner, 2026-11-04, `wedding.md`). *Fix:* label the sample data as sample now, as a quick and separate step. Then a proposed PD on guest-planning scope (what "food" covers, what seating needs), then backend guest endpoints and wiring. How it's built is not yet decided. *Depends on:* B10/B22 before real guest data goes in, and that PD.
- **B29 — Sample content flashes before real data loads.** Found while building B28 (PR #12). When a wedding has real budget lines or checklist items, `Budget.tsx` and `Timeline.tsx` show the static fallback, now labelled as sample, until the API answers. *Fix:* show a loading state instead of sample content while the data is loading. *Depends on:* nothing.
- **B20 — The catalogue and its docstring overstate what's verified.** In `backend/app/db/seed_data_real.py`, 10 of 26 suppliers are unchecked (`_verify: True`) and 3 are `_template` placeholders with made-up names (lines 340–361). The docstring (lines 26–28) promises that inquiries route through `agents.resolve_inquiry_recipient` to an owner-controlled inbox, but no such function exists. *Fix:* check or remove the unchecked rows (`add-vendors` skill), keep templates out of recommendations, and correct the docstring.

### Making it fit this wedding

- **B11 — Ireland-only catalogue, but the wedding is in the US.** The regions (`utils/constants.py`), EUR and the vendor catalogue (`seed_data_real.py`) are all Irish. `wedding.md` now puts the wedding in Chicago, IL, United States (owner, 2026-11-04), so none of the 25 venues or 26 suppliers, and none of the regions, apply. The intake planner's budget logic assumes Irish pricing. *Why it matters:* venue and supplier matching can't recommend anything usable for this wedding. If it ran as it is, it would suggest Irish vendors. *Fix:* engineering change to raise, approach not yet decided. Covers regions, catalogue (cited Chicago-area vendors via `add-vendors`), and currency. The app currently assumes EUR everywhere, but the couple want amounts in US dollars (`wedding.md`, owner, 2026-11-04). Any new money fields use integer cents or `Decimal` (AGENTS.md rule 4). The couple prefer Chicago vendors, and don't want euro quotes converted (owner, 2026-11-05: "no need for the conversion as chicago vendors would be preferred"). *Depends on:* a product decision on how to handle the catalogue, to be proposed. The venue status (shortlist being visited, not booked) suggests Chicago suppliers matter more than venues. *Ranking:* the currency part ranks with B23 (budgeting is must-have 1). The catalogue part ranks below the must-haves. *Follow-up from #39 (B51):* the AI budget check is built on Irish euro prices, so it's switched off for this wedding until it has US price rules.

- **B48 — The checklist always says "Dates are provisional".** Found in PR #32 (B24). PD-007 doesn't say whether the note goes once the date is final. *Fix (decided, owner, 2026-11-05: "yes to the provisional dates note"):* a "This date is confirmed" switch for owners and editors; the note goes when it's on, and comes back if it's switched off.

### Housekeeping

- **B13 — Stale material from the XPRIZE.** The prototype and both sales lists are gone (B6, PR #15; B37, PR #20). Left: the `.xlsx` trackers and the XPRIZE framing in `README.md`, `docs/runway.md`, `docs/strategic-memo.md` and `docs/reviews/`. *Fix:* archive or delete them (owner's call). See B40 for the prospects' first names.
- **B40 — Past sales prospects' first names remain.** Found in PR #20. Four first names, one linked to a business, in `docs/runway.md`, `scripts/build_tracker.py` and probably `runway-tracker.xlsx` (rule 3). *Fix:* remove or replace them with roles. *Depends on:* PD-005, extended again 2026-11-05 (ratified).
- **B41 — Small follow-ups from the B39 review (PR #23).** The independent review found nothing blocking, plus three should-fix items: (1) `manage_access.py` flags access-list rows that contain look-alike letters but can't remove them, because `remove` refuses non-ASCII input; let `remove` take a row id. (2) No test proves an existing, linked member keeps access if their sign-in address has a look-alike letter (`auth.py:141-143`). (3) The refusal in wedding creation (`weddings.py:58-61`) is untested. Copy (decided-by-agent, reversible): the refusal message should tell people to ask the couple to add a different address, not to "type in plain letters". *Depends on:* PD-002 note, 2026-11-05 (ratified).
- **B43 — Small follow-ups from the B23 fix review (PR #25).** (1) The guardrail that strips prices from the AI split's reasons misses bare numbers ("Around 12,000 for the venue", "1.5 million", "twelve thousand dollars"); also catch 3+ digit numbers with thousands separators and number + thousand/million (`budget_split.py:31-38`). Rule 2. (2) When a reason is removed, the screen says nothing; show a short note (`budget_split.py:123` warnings are ignored by the UI). (3) Renaming checks for a clash even when the name hasn't changed, so if two look-alike categories ever exist (only via two simultaneous adds), editing either one's amount fails with 409 (`budget.py:371-373`); check only when the normalised name changes. (4) "Over your total by" and the over-total banner both show (`Budget.tsx:180-187`); keep one. *Depends on:* PD-004 (ratified).
- **B44 — Other parts still read the old euro budget lines.** Found in PR #28 (B42). The quote extractor's budget alert and spent roll-up, the venue and supplier matchers (which fall back to a share of the total budget), the concierge's budget context, and the Dashboard's "Budget lines" count still read the planner's old `BudgetLine` rows. Since B42 the planner no longer makes them, so on a newly planned wedding the Dashboard count reads 0 and these parts see no budget. Nothing breaks, and existing rows are kept. *Fix (recommended, reversible):* move each to the new budget tables (PD-004), with the extractor and matcher changes following `agent-features`. *Depends on:* PD-004 (ratified). *Follow-up from #39 (B51):* this includes the old euro budget-warning card.
- **B49 — Keep guest details away from the free AI.** PD-008: the app uses Gemini's free tier, where Google may use what it's sent and human reviewers may read it. The owner decided (2026-11-05, "yes") that the AI never receives guest names, contact details or dietary notes, only counts and categories. *Fix:* check every agent's prompt and context (concierge, planner, matchers, quote extractor, and anything reading the `Guest` table or inbound email), strip or summarise guest personal data, add a guardrail and a test in `verify_agents.py` that fails if guest fields reach a prompt. Inbound vendor emails may contain guest names; say how they're handled. *Depends on:* PD-008 (ratified). Must be done before real guest data goes in (B19). *In #44:* one privacy filter on every AI call and its log; it refuses to send if personal data is left. It only knows names already in the app (the couple and the access list until B19). Known gaps: a name typed without its apostrophe; some Irish-format numbers. A guest named like a place or month ("Clare", "June") is also removed from capitalised text.
- **B52 — Node 20 is past upstream support.** Found in PR #42 (B47): Replit and CI run Node 20. *Fix:* move both to Node 22, then run the verify gate and a build on Replit. *Depends on:* nothing; low priority.
- **B53 — The live checklist starts empty.** Found in PR #42 (B47): on a fresh database the Checklist screen shows no tasks. Expected: all tasks, including the 18 approved Jewish traditions, are added only by `manage_checklist.py import`, from the owner's own file kept out of git (PD-007). *Why it matters:* the checklist is must-have 2, and it'll be empty on Replit until the import runs. *Fix:* the owner runs the import once on Replit, dry run first, after the wedding is created; agents don't write to the live database (rule 6). *Depends on:* the owner, and the wedding existing on Replit.
- **B50 — Incoming supplier emails can't be read.** Found in PR #34 (B46): the inbound-email path fails on `main` too, so vendor replies never reach the app. *Why it matters:* only if the couple want vendor replies in the app; today they send and read inquiries from their own email. *Fix:* engineering, once the couple want the feature. Vendor emails may name guests, so B49 applies. *Depends on:* the couple wanting it.
- **B45 — Two small date follow-ups from PR #32 (B24).** The budget screen still works out "today" from the server's clock, not Chicago's, so a payment can show as due or late a few hours early in the evening. The checklist's date tests could fail falsely if run across midnight in Chicago. *Fix:* use the same Chicago "today" as the checklist, and pin "today" in the tests. *Depends on:* nothing.
- **B14 — The deploy workflow would publish a frontend with no backend.** `.github/workflows/deploy.yml` publishes `frontend/` to GitHub Pages at VenueFlow's domain, `venueflow.ie` (`frontend/public/CNAME`), on every push to `main`. It sets no `VITE_API_URL`, so the published site would have no backend. No runs are recorded on this repo. *Fix:* decide where the app and its backend are hosted, then point the workflow at that. Keep or drop the domain as part of that decision. *Depends on:* a PD on hosting (couple's call).
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


- **B32 — Two "@claude" reply bots, and an automatic review on every PR.** `/install-github-app` opened PR #11, which the owner merged on 2026-11-04. It added `.github/workflows/claude.yml`, which answers any "@claude" comment, and `claude-code-review.yml`, which reviews every PR when it's opened or updated. `claude-agents.yml` already answers "@claude" with the repo's autopilot rules, so once B31 is fixed, each owner comment would start two separate runs. Only one of them follows this repo's rules. The automatic review also uses subscription allowance on every agent PR, which the repo's own reviewer already checks. *Fix (recommended):* turn off `claude.yml`. Whether to keep the automatic review is the owner's call. *Depends on:* the owner's answer. It's a `.github/` change, so it needs an owner-run session.

- **B33 — The backend allows calls from VenueFlow's original website.** Found in PR #14. The list of websites allowed to call the backend still includes the upstream author's address. *Fix:* remove it, and add the real address once hosting is decided (B14).
- **B34 — No database-level guard on duplicate access entries.** Found in PR #14. The app checks for an email already on the access list, but the `wedding_members` table doesn't enforce it. *Fix:* a unique constraint per wedding and email, through a migration (rule 6, see B27).
- **B35 — Sign-in setup should turn on email-enumeration protection.** Found in PR #14. Firebase can hide whether an email has an account. *Fix:* add the step to `docs/setup-sign-in.md`.
- **B36 — The shared agent instructions describe the app as it was before B22, B26 and B28.** "What's actually there today" in `.agents/AGENTS.md` and `ai-studio-system-instructions.md` is out of date. Agents may not edit their own instructions, so this needs a session the owner runs. It also covers removing their references to `streamlit_mock/` (B37), and adding back the owner's Replit notes (now in `replit.md`, PR #34). *Follow-up from #39 (B51):* also describe the new setup form (Chicago, USD, optional budget, AI budget check off). *Follow-up from #44 (B49):* add a line about the AI privacy filter.


## Recently closed

| Closed | Item | Resolved by |
|---|---|---|
| 2026-11-06 | **B47** — frontend security advisories patched, 13 down to one Firebase cause the app doesn't ship; owner to confirm Google sign-in on Replit | #42 |
| 2026-11-05 | **B51** — the setup form fits this wedding: Chicago, USD, Jewish ceremony, budget optional (PD-009); browser-tested | #39 |
| 2026-11-05 | **B46** — the owner's Replit setup and Google sign-in fix made merge-ready: installs outside Replit, migrations on startup, readable AI errors | #34 |
| 2026-11-05 | **B24** — shared planning checklist (PD-007): stages, catch up, overdue, provisional date; the owner's list, Jewish-tradition tasks and old AI tasks load through a one-time import after hosting | #32 |
| 2026-11-05 | **B42** — vendor cards compare quotes with the new dollar budget; the planner no longer makes old euro lines | #28 |
| 2026-11-05 | **B23** — in depth budgeting (PD-004, option C): categories, vendor costs, payments and due dates, contributions, AI-suggested split, in US dollars | #25 |
| 2026-11-05 | **B30** — the budget ring now shows real totals, or is hidden when there are none (folded into B23) | #25 |
| 2026-11-05 | **B39** — look-alike email addresses no longer pass as the couple's or an access-list entry at sign-in | #23 |
| 2026-11-05 | **B31** — autopilot signs in with the owner's Claude subscription (owner's own edit) | #19 |
| 2026-11-05 | **B38** — neither owner can remove or demote the other from the access screen (PD-002 note) | #18 |
| 2026-11-05 | **B37** — old outreach list and first prototype deleted, references fixed (PD-005, extended) | #20 |
| 2026-11-05 | **B15** — CI passes on PRs. `main` is protected by the owner: PR required, `backend` and `frontend` checks required, applies to admins, no force pushes or deletion | repo settings (owner) |
| 2026-11-05 | **B22** — access settings screen, owner-only access changes, email confirmation (PD-002 step 2) | #14 |
| 2026-11-05 | **B27** — migration naming convention and batch mode | #16 |
| 2026-11-05 | **B6** — sales prospect list deleted, prototype contacts made fictional (PD-005) | #15 |
| 2026-11-05 | **B26** — demo couples and weddings seeded only in dev mode | #13 |
| 2026-11-05 | **B28** — sample data on guests, seating, budget and timeline labelled | #12 |
| 2026-11-04 | **B21** — `sqlmodel` ceiling not enforced (CI pulled 0.0.48 and the verify scripts failed on naive datetimes) | #6 |
| 2026-11-04 | **B16** — `greenlet` missing from `requirements.txt` (backend verify crashed on Apple Silicon and in CI) | #6 |
| 2026-11-04 | **B12** — legacy SaaS screens, the payment gate and the mock €299 payment, removed per PD-003 | `fd3157b5` (PD-003) |
| 2026-11-04 | **B9** — hard-coded admin agent log: moot, the admin console was removed (PD-003) | `fd3157b5` (PD-003) |
| 2026-11-04 | **B18** — metrics reporting 0.0 confidence: moot, `/metrics` was removed (PD-003) | `fd3157b5` (PD-003) |
| 2026-11-04 | **B10** — mock sign-in on by default, plus a committed default HS256 secret, open Firebase sign-up and a password-less planner login | `42049acc` (PD-002 step 1) |
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
