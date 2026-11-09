# Backlog — known gaps and work queue

Tracked here so debt is visible. **Each item: what, where, why it matters for *this* wedding, the fix shape, and the product decision it depends on.** The product lane ranks items against the wedding date (`docs/product/wedding.md`); engineering closes them. Close an item by moving it to "Recently closed" with the fixing commit.

Convention: also drop a `# TODO(name, YYYY-MM-DD):` comment at the code site for in-flight items, and reconcile this file against `grep -rn TODO` when reviewing.

---

## Next up

*Updated 2026-11-09 by the product lane. Re-rank if this date is more than 14 days old.*

0. **B32** — two Claude reply bots and an automatic PR review. Owner, 2026-11-05: "yes, turn off the extra reply bot and Turn off the automatic review on every PR". Done 2026-11-05: both workflows are disabled in the Actions tab, at the owner's request. Their files stay in `.github/workflows/`; deleting them needs a session the owner runs.
1. **B65–B69** — the full budget tracker, five steps (PD-013). ratified 2026-11-09; B65 `in progress`, then B66–B69 in order
2. **B64** — "Not selected" vendor status (PD-012 follow-up 2). `in review` (#69). Publish shows one addition: `ALTER TABLE couple_vendors ADD COLUMN not_selected BOOLEAN DEFAULT false NOT NULL`
3. **B55** — the Wildman BT contract: questions for the venue before signing; the $6,000 deposit is due Wed 11 Nov 2026. The owner is handling the contract herself: "dont worry about #1" (2026-11-09). `owner-handling`
4. **B56** — the Wildman BT payments on the Budget screen (the checklist tasks V1–V3 came in with the load, #56). `ready`
5. **B45** — the budget screen uses the server's date, not Chicago's; date tests can fail falsely around midnight in Chicago. `ready`
6. **B44** — move the other parts that still read the old euro budget lines to the new budget. `ready`
7. **B43** — small follow-ups from the B23 fix review (wider price filter on AI reasons, three screen tidy-ups). `ready`
8. **B41** — small follow-ups from the B39 review (one tool fix, two tests, one message). `ready`
9. **B40** — remove past sales prospects' first names from `docs/runway.md`, `scripts/build_tracker.py` and `runway-tracker.xlsx` (PD-005, extended again). `ready`
10. **B14** — host the app on Replit (PD-008, ratified: free AI tier, $50 spending alert, US data location, free `.replit.app` address). `ready` (after B46 and B47).
11. **B19** — guest planning: list, food, seating. `needs-owner: guest-planning scope PD, to be proposed`
12. **B33** — stop the backend accepting calls from the original VenueFlow author's website. `ready`
13. **B34** — database-level guard against the same email being added twice. `ready`
14. **B35** — add Firebase's email-enumeration protection to the sign-in setup guide. `ready`
15. **B29** — real budget and checklist briefly show labelled sample content while loading. `ready`
16. **B8** — record missing token counts as empty, not 0. `ready`
17. **B17** — stop tracking the test database files. `ready`
18. **B36** — refresh "What's actually there today" in `.agents/AGENTS.md` and its AI Studio copy, plus the B48 date switch, the B49 check-before-sending rule, Aurelia off (PD-010) the in-app checklist load (PD-011), the new `db_status.py` check (#58) and the Vendors page as the couple's own sections (PD-012), and the B60 migration rule (`migrations/safe_ops.py`) (also the `agent-features` skill; wording suggested in #44). `needs-owner: guardrail files need a session the owner runs`
19. **B52** — move Replit and the automatic checks from Node 20 to Node 22. `ready`

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
- **B19 — Guest planning (must-have 3), but the guest list and seating plan show unlabelled sample data.** `frontend/src/app/wedding/views/Guests.tsx:9` (`GUESTS`, made-up names with dietary tags) and `SeatingPlan.tsx:13` (`GUESTS`, `INITIAL_TABLES`) are hard-coded and never call the API, on the couple's own workspace (rule 10). The backend has a `Guest` table (`backend/app/db/models.py:322`: name, email, phone, RSVP status, `dietary`, plus-one, table number), but no guest endpoint exists in `api/v1/endpoints/`. *Why it matters:* the couple listed "guest planning (list, food, seating)" as must-have 3, for 225 invited guests. Today nothing they enter would be saved. The "food" part includes dietary needs, which are health data (AGENTS.md rule 3). They must never appear in git, fixtures, issues, logs or `AgentDecisionLog` payloads. In the app, family (view only) can see them: "family can see dietary notes" (owner, 2026-11-04, `wedding.md`). *Fix:* label the sample data as sample now, as a quick and separate step. Also reword the sample "Smart Seating" text that names Aurelia, now that Aurelia is off (PD-010; found in #54; decided-by-agent, reversible). Then a proposed PD on guest-planning scope (what "food" covers, what seating needs), then backend guest endpoints and wiring. How it's built is not yet decided. *Depends on:* B10/B22 before real guest data goes in, and that PD.
- **B29 — Sample content flashes before real data loads.** Found while building B28 (PR #12). When a wedding has real budget lines or checklist items, `Budget.tsx` and `Timeline.tsx` show the static fallback, now labelled as sample, until the API answers. *Fix:* show a loading state instead of sample content while the data is loading. *Depends on:* nothing.
- **B20 — The catalogue and its docstring overstate what's verified.** In `backend/app/db/seed_data_real.py`, 10 of 26 suppliers are unchecked (`_verify: True`) and 3 are `_template` placeholders with made-up names (lines 340–361). The docstring (lines 26–28) promises that inquiries route through `agents.resolve_inquiry_recipient` to an owner-controlled inbox, but no such function exists. *Fix:* check or remove the unchecked rows (`add-vendors` skill), keep templates out of recommendations, and correct the docstring.

### Making it fit this wedding

- **B55 — Questions for Wildman BT before signing.** From the product lane's review of the draft contract (2026-11-09; facts in `wedding.md`). The deposit ($6,000, non-refundable) is due Wed 11 Nov 2026, and once signed the date can't move except for events like storms or a pandemic, and then only once. Questions, most urgent first: (1) hold the date a few more days while we review? (2) a full refund if Wildman BT cancels, closes or can't host, in writing; (3) add the groom as a second Contracting Party (only the owner is named, so only she is liable); (4) pay by check to avoid the 3% card fee; (5) how many extra valet attendants for 220 guests, and the cost (60 cars included); (6) chuppah set-up and attaching to the beams or floor; (7) how the ceremony-to-reception flip works and whether it counts toward the 7 live hours; (8) rehearsal time and wedding-suite access; (9) is event insurance required, and how much; (10) opt out of the venue's photos, or no guests' faces; (11) how security deposit deductions are decided, with a walkthrough before and after; (12) bringing our own alcohol through an approved caterer, and any fees. Also for later: whether to buy the $1,500 day-of coordinator package; the contract asks for a named day-of contact either way. *Fix:* the couple send the questions (people send, never the app: rule 1). *Depends on:* the owner.
- **B56 — The venue's payment dates aren't in the app yet.** Owner, 2026-11-09: "record the payment dates and the extra $2,000 security deposit in the wedding facts and budget and checklist". Recorded in `wedding.md`, [budget.md](product/budget.md) and [checklist-list.md](product/checklist-list.md), part 3. The app isn't live yet (B14), and agents don't write to the live database (rule 6). *Fix:* add tasks V1–V3 to the checklist's one-time import, alongside the Jewish-tradition tasks, so they appear when the owner runs it (B53), with the fixed dates kept in the task wording. For the budget, either the couple enter the four rows from `budget.md` on the Budget screen, or the same import adds them; the engineer recommends one. The $2,000 security deposit is refundable, so it's shown as a payment but not counted in the venue's cost. Nothing is marked paid (rule 4). *Depends on:* B53 for loading; nothing else. *Since PD-011 (2026-11-09):* V1–V3 are built into B53's in-app load; the budget rows remain here.

- **B11 — Ireland-only catalogue, but the wedding is in the US.** The regions (`utils/constants.py`), EUR and the vendor catalogue (`seed_data_real.py`) are all Irish. `wedding.md` now puts the wedding in Chicago, IL, United States (owner, 2026-11-04), so none of the 25 venues or 26 suppliers, and none of the regions, apply. The intake planner's budget logic assumes Irish pricing. *Why it matters:* venue and supplier matching can't recommend anything usable for this wedding. If it ran as it is, it would suggest Irish vendors. *Fix:* engineering change to raise, approach not yet decided. Covers regions, catalogue (cited Chicago-area vendors via `add-vendors`), and currency. The app currently assumes EUR everywhere, but the couple want amounts in US dollars (`wedding.md`, owner, 2026-11-04). Any new money fields use integer cents or `Decimal` (AGENTS.md rule 4). The couple prefer Chicago vendors, and don't want euro quotes converted (owner, 2026-11-05: "no need for the conversion as chicago vendors would be preferred"). *Depends on:* a product decision on how to handle the catalogue, to be proposed. The venue status (shortlist being visited, not booked) suggests Chicago suppliers matter more than venues. *Ranking:* the currency part ranks with B23 (budgeting is must-have 1). The catalogue part ranks below the must-haves. *Follow-up from #39 (B51):* the AI budget check is built on Irish euro prices, so it's switched off for this wedding until it has US price rules.

- **B58 — The RUNBOOK backup step doesn't work on Replit.** Found while writing the B53 steps (2026-11-09): the RUNBOOK's checklist-import backup uses `SYNC_DATABASE_URL`, which Replit's Shell doesn't set; there `DATABASE_URL` works, and the Shell always reaches the development database, not the published app's production one. *Fix:* update RUNBOOK for Replit. *Also for B14:* when the app is published, Replit offers to copy development data into production; that is when the imported checklist would carry over, and the publishing plan should cover it. If the wedding is already in production, the Shell can't reach it without pasting a secret, so a safe import route is needed first. *Depends on:* nothing. *#58 (B59):* the backup command now works in Replit's Shell; the publishing note remains.

- **B64 — A "Not selected" vendor status.** Owner, 2026-11-09. PD-012 follow-up 2 (ratified): muted red, faded tile at the bottom of its section; doesn't count toward the category status. *Ratified 2026-11-09.* Likely a database change only if statuses are checked in the database; say what Publish will show.

- **B65–B69 — The full budget tracker (PD-013, ratified 2026-11-09).** The owner's brief, 2026-11-09, split into five steps: B65 expenses and payments that add up (database change; folds in B44, B45 and the budget half of B56); B66 dashboard and allocation; B67 categories and the expense list (small database change); B68 charts and upcoming payments; B69 export (CSV and a printable page). Receipts and contracts are Google Drive links; default categories as in call (b); the engineering team enters Wildman BT in B65 as a one-time data step.

### Housekeeping

- **B13 — Stale material from the XPRIZE.** The prototype and both sales lists are gone (B6, PR #15; B37, PR #20). Left: the `.xlsx` trackers and the XPRIZE framing in `README.md`, `docs/runway.md`, `docs/strategic-memo.md` and `docs/reviews/`. *Fix:* archive or delete them (owner's call). See B40 for the prospects' first names.
- **B40 — Past sales prospects' first names remain.** Found in PR #20. Four first names, one linked to a business, in `docs/runway.md`, `scripts/build_tracker.py` and probably `runway-tracker.xlsx` (rule 3). *Fix:* remove or replace them with roles. *Depends on:* PD-005, extended again 2026-11-05 (ratified).
- **B41 — Small follow-ups from the B39 review (PR #23).** The independent review found nothing blocking, plus three should-fix items: (1) `manage_access.py` flags access-list rows that contain look-alike letters but can't remove them, because `remove` refuses non-ASCII input; let `remove` take a row id. (2) No test proves an existing, linked member keeps access if their sign-in address has a look-alike letter (`auth.py:141-143`). (3) The refusal in wedding creation (`weddings.py:58-61`) is untested. Copy (decided-by-agent, reversible): the refusal message should tell people to ask the couple to add a different address, not to "type in plain letters". *Depends on:* PD-002 note, 2026-11-05 (ratified).
- **B43 — Small follow-ups from the B23 fix review (PR #25).** (1) The guardrail that strips prices from the AI split's reasons misses bare numbers ("Around 12,000 for the venue", "1.5 million", "twelve thousand dollars"); also catch 3+ digit numbers with thousands separators and number + thousand/million (`budget_split.py:31-38`). Rule 2. (2) When a reason is removed, the screen says nothing; show a short note (`budget_split.py:123` warnings are ignored by the UI). (3) Renaming checks for a clash even when the name hasn't changed, so if two look-alike categories ever exist (only via two simultaneous adds), editing either one's amount fails with 409 (`budget.py:371-373`); check only when the normalised name changes. (4) "Over your total by" and the over-total banner both show (`Budget.tsx:180-187`); keep one. *Depends on:* PD-004 (ratified).
- **B44 — Other parts still read the old euro budget lines.** Found in PR #28 (B42). The quote extractor's budget alert and spent roll-up, the venue and supplier matchers (which fall back to a share of the total budget), the concierge's budget context, and the Dashboard's "Budget lines" count still read the planner's old `BudgetLine` rows. Since B42 the planner no longer makes them, so on a newly planned wedding the Dashboard count reads 0 and these parts see no budget. Nothing breaks, and existing rows are kept. *Fix (recommended, reversible):* move each to the new budget tables (PD-004), with the extractor and matcher changes following `agent-features`. *Depends on:* PD-004 (ratified). *Follow-up from #39 (B51):* this includes the old euro budget-warning card.
- **B52 — Node 20 is past upstream support.** Found in PR #42 (B47): Replit and CI run Node 20. *Fix:* move both to Node 22, then run the verify gate and a build on Replit. *Depends on:* nothing; low priority.
- **B50 — Incoming supplier emails can't be read.** Found in PR #34 (B46): the inbound-email path fails on `main` too, so vendor replies never reach the app. *Why it matters:* only if the couple want vendor replies in the app; today they send and read inquiries from their own email. *Fix:* engineering, once the couple want the feature. Vendor emails may name guests, so B49 applies. *Depends on:* the couple wanting it. *Since #44 (B49):* emails that reach the app inbox are skipped, not stored or sent to the AI; vendor replies are pasted on the Vendors screen instead.
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
| 2026-11-09 | **B63** — each vendor its own tile, status in colour plus the word (grey looking, blue contacted, green booked); "Where each section stands" summary at the top. Owner to check on a phone | #66 |
| 2026-11-09 | **B62** — the couple add, edit and remove vendors in each section; family view only; Wildman BT starts as Contacted; "Paste a reply" back on each vendor with the check-before-sending preview. Owner testing on the live app | #64 |
| 2026-11-09 | **B60** — a migration still succeeds when Replit's publish step has already added the new table or column; plain publish rules in `replit.md` (approve additions the team announced; stop on DROP, ALTER or renames). Follow-up: a PostgreSQL test; a dropping or altering release needs the team on the publish screen | #61 |
| 2026-11-09 | **B61** — Vendors page shows the couple's seven sections (Venue: Wildman BT); AI suggestions, the matcher button and the Dashboard shortlist card removed (hidden, not deleted). Pasting a vendor reply returns with B62 | #60 |
| 2026-11-09 | **B59** — Run in the Replit workspace brings the database up to date before the app starts; plain publishing steps; Shell check `db_status.py`; Replit backup command fixed (B58, backup half) | #58 |
| 2026-11-09 | **B53** — the owner loaded her checklist on the published app with "Load my checklist" (PD-011), including the 18 Jewish-tradition tasks and the Wildman BT tasks V1–V3 (B56, checklist part) | #56 |
| 2026-11-09 | **B57** — Aurelia (typed chat and voice) turned off per PD-010; the app refuses assistant calls; nothing deleted, can come back. The ElevenLabs voice agent can also be turned off in the owner's ElevenLabs account | #54 |
| 2026-11-09 | **B49** — every AI feature shows the cleaned text and sends only on a click; known names removed automatically; app-inbox emails no longer go to the AI | #44 |
| 2026-11-09 | **B48** — "This date is confirmed" switch on the Checklist; when on, "provisional" goes from all four places. Starts off; the couple turn it on. #48 was a duplicate, closed | #49 |
| 2026-11-09 | **B54** — the setup form pre-fills the final date, 23 October 2027; the couple change an existing wedding's date on the Checklist screen | #46 |
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
