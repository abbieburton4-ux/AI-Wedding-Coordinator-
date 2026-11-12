# Backlog — known gaps and work queue

Tracked here so debt is visible. **Each item: what, where, why it matters for *this* wedding, the fix shape, and the product decision it depends on.** The product lane ranks items against the wedding date (`docs/product/wedding.md`); engineering closes them. Close an item by moving it to "Recently closed" with the fixing commit.

Convention: also drop a `# TODO(name, YYYY-MM-DD):` comment at the code site for in-flight items, and reconcile this file against `grep -rn TODO` when reviewing.

---

## Next up

*Updated 2026-11-12 by the product lane. Re-rank if this date is more than 14 days old.*

0. **B32** — two Claude reply bots and an automatic PR review. Owner, 2026-11-05: "yes, turn off the extra reply bot and Turn off the automatic review on every PR". Done 2026-11-05: both workflows are disabled in the Actions tab, at the owner's request. Their files stay in `.github/workflows/`; deleting them needs a session the owner runs.
1. **B88** — a proper Excel download for the budget, with tabs (PD-019, ratified). `merged` (#110); close once the owner has opened a download in Excel or Google Sheets
2. **B91** — remove the "Download CSV" button once the Excel download is in (PD-019 follow-up). `ready` (after the owner confirms the Excel file opens properly)
3. **B90** — check the workspace catches up by itself after a Pull (seen failing on the first publish after #105). `ready`
4. **B19** — guest planning: list, food, seating (must-have 3). `on hold` (owner, 2026-11-12: "no need to start on guest planning yet")
5. **B89** — send the budget straight to Google Sheets (PD-019 option C). `on hold` (owner: "maybe c later"; needs its own PD)
6. **B55** — the Wildman BT contract: questions for the venue before signing; the $6,000 deposit is due Wed 11 Nov 2026. The owner is handling the contract herself: "dont worry about #1" (2026-11-09). `owner-handling`
7. **B41** — small follow-ups from the B39 review (one tool fix, two tests, one message). `ready`
8. **B40** — remove past sales prospects' first names from `docs/runway.md`, `scripts/build_tracker.py` and `runway-tracker.xlsx` (PD-005, extended again). `ready`
9. **B14** — host the app on Replit (PD-008, ratified: free AI tier, $50 spending alert, US data location, free `.replit.app` address). `ready` (after B46 and B47).
10. **B33** — stop the backend accepting calls from the original VenueFlow author's website. `ready`
11. **B34** — database-level guard against the same email being added twice. `ready`
12. **B35** — add Firebase's email-enumeration protection to the sign-in setup guide. `ready`
13. **B8** — record missing token counts as empty, not 0. `ready`
14. **B17** — stop tracking the test database files. `ready`
15. **B36** — refresh "What's actually there today" in `.agents/AGENTS.md` and its AI Studio copy, plus the B48 date switch, the B49 check-before-sending rule, Aurelia off (PD-010) the in-app checklist load (PD-011), the new `db_status.py` check (#58) and the Vendors page as the couple's own sections (PD-012), and the B60 migration rule (`migrations/safe_ops.py`), the budget's new expense and payment fields (PD-013, #72) (also the `agent-features` skill; wording suggested in #44); and a frontend-traps line: gold text uses the darker text token from #102, never `--primary` (B83), and clay text uses `text-soft-clay-text` (B85, #104). `needs-owner: guardrail files need a session the owner runs`
16. **B52** — move Replit and the automatic checks from Node 20 to Node 22. `ready`
17. **B77** — an older test fails by chance (looks for "555" among random IDs). `ready`

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
- **B20 — The catalogue and its docstring overstate what's verified.** In `backend/app/db/seed_data_real.py`, 10 of 26 suppliers are unchecked (`_verify: True`) and 3 are `_template` placeholders with made-up names (lines 340–361). The docstring (lines 26–28) promises that inquiries route through `agents.resolve_inquiry_recipient` to an owner-controlled inbox, but no such function exists. *Fix:* check or remove the unchecked rows (`add-vendors` skill), keep templates out of recommendations, and correct the docstring.

### Making it fit this wedding

- **B55 — Questions for Wildman BT before signing.** From the product lane's review of the draft contract (2026-11-09; facts in `wedding.md`). The deposit ($6,000, non-refundable) is due Wed 11 Nov 2026, and once signed the date can't move except for events like storms or a pandemic, and then only once. Questions, most urgent first: (1) hold the date a few more days while we review? (2) a full refund if Wildman BT cancels, closes or can't host, in writing; (3) add the groom as a second Contracting Party (only the owner is named, so only she is liable); (4) pay by check to avoid the 3% card fee; (5) how many extra valet attendants for 220 guests, and the cost (60 cars included); (6) chuppah set-up and attaching to the beams or floor; (7) how the ceremony-to-reception flip works and whether it counts toward the 7 live hours; (8) rehearsal time and wedding-suite access; (9) is event insurance required, and how much; (10) opt out of the venue's photos, or no guests' faces; (11) how security deposit deductions are decided, with a walkthrough before and after; (12) bringing our own alcohol through an approved caterer, and any fees. Also for later: whether to buy the $1,500 day-of coordinator package; the contract asks for a named day-of contact either way. *Fix:* the couple send the questions (people send, never the app: rule 1). *Depends on:* the owner.

- **B11 — Ireland-only catalogue, but the wedding is in the US.** The regions (`utils/constants.py`), EUR and the vendor catalogue (`seed_data_real.py`) are all Irish. `wedding.md` now puts the wedding in Chicago, IL, United States (owner, 2026-11-04), so none of the 25 venues or 26 suppliers, and none of the regions, apply. The intake planner's budget logic assumes Irish pricing. *Why it matters:* venue and supplier matching can't recommend anything usable for this wedding. If it ran as it is, it would suggest Irish vendors. *Fix:* engineering change to raise, approach not yet decided. Covers regions, catalogue (cited Chicago-area vendors via `add-vendors`), and currency. The app currently assumes EUR everywhere, but the couple want amounts in US dollars (`wedding.md`, owner, 2026-11-04). Any new money fields use integer cents or `Decimal` (AGENTS.md rule 4). The couple prefer Chicago vendors, and don't want euro quotes converted (owner, 2026-11-05: "no need for the conversion as chicago vendors would be preferred"). *Depends on:* a product decision on how to handle the catalogue, to be proposed. The venue status (shortlist being visited, not booked) suggests Chicago suppliers matter more than venues. *Ranking:* the currency part ranks with B23 (budgeting is must-have 1). The catalogue part ranks below the must-haves. *Follow-up from #39 (B51):* the AI budget check is built on Irish euro prices, so it's switched off for this wedding until it has US price rules. *Note (#83, B74):* if the supplier matcher comes back, it should use the couple\'s Food & Drink target rather than a share of the total.

- **B58 — The RUNBOOK backup step doesn't work on Replit.** Found while writing the B53 steps (2026-11-09): the RUNBOOK's checklist-import backup uses `SYNC_DATABASE_URL`, which Replit's Shell doesn't set; there `DATABASE_URL` works, and the Shell always reaches the development database, not the published app's production one. *Fix:* update RUNBOOK for Replit. *Also for B14:* when the app is published, Replit offers to copy development data into production; that is when the imported checklist would carry over, and the publishing plan should cover it. If the wedding is already in production, the Shell can't reach it without pasting a secret, so a safe import route is needed first. *Depends on:* nothing. *#58 (B59):* the backup command now works in Replit's Shell; the publishing note remains.

- **B88 — A proper Excel download for the budget.** Owner, 2026-11-12: "lets next work on the excel export" / "a for now and maybe c later". *Fix:* PD-019 (ratified): an .xlsx with tabs, alongside the CSV. *Depends on:* nothing.
- **B91 — Remove the "Download CSV" button.** Owner, 2026-11-12: "we can remove the download .csv button when we have the download excel" (PD-019 follow-up, ratified). *Fix:* remove the button and the CSV route, unless something else uses it; keep "Print / save as PDF". *Depends on:* B88 merged.
- **B89 — Send the budget straight to Google Sheets.** PD-019 option C, "maybe c later" (owner, 2026-11-12). Needs its own PD: the app getting permission to write to the couple's Google Drive is an access and data-location call. *Depends on:* the owner asking for it.
- **B90 — The workspace didn't catch up by itself after a Pull.** Found on the first publish after #105 (2026-11-12): Publish still offered the who-paid DROP. The owner had to run `python db_status.py upgrade` in the Shell, which took the workspace from 0011 to 0013; Publish then showed only the four tip additions. #105 said the running workspace would catch up within about ten seconds of a Pull. `[ASSUMPTION]` the running app started before #105's code arrived, so it had no catch-up yet. *Fix:* check whether the catch-up works on the next Pull that brings a new migration; if not, fix it or drop the claim from `replit.md`. Until then, the one Shell command before every publish stays in the steps. *Depends on:* nothing.
- **B77 — An older test fails by chance.** Found while building B76 (#89): a check looks for the text "555" in output that is full of random IDs, so now and then a random ID contains "555" and the run fails. The test was left as it is (rule 8). *Fix:* make the check look for the number where it's meant to be, not anywhere in the output. Seen again in #110 (`verify_endpoints.py`, around line 824). *Depends on:* nothing; small.

- **B73 — A test fails now and then.** Found in #78 (B68): one existing check fails at random when a generated id contains "555" (it looks like a phone number to the privacy filter). Not caused by #78. *Fix:* make the test ids fixed, or teach the check to ignore ids. *Depends on:* nothing; small.


### Housekeeping

- **B13 — Stale material from the XPRIZE.** The prototype and both sales lists are gone (B6, PR #15; B37, PR #20). Left: the `.xlsx` trackers and the XPRIZE framing in `README.md`, `docs/runway.md`, `docs/strategic-memo.md` and `docs/reviews/`. *Fix:* archive or delete them (owner's call). See B40 for the prospects' first names.
- **B40 — Past sales prospects' first names remain.** Found in PR #20. Four first names, one linked to a business, in `docs/runway.md`, `scripts/build_tracker.py` and probably `runway-tracker.xlsx` (rule 3). *Fix:* remove or replace them with roles. *Depends on:* PD-005, extended again 2026-11-05 (ratified).
- **B41 — Small follow-ups from the B39 review (PR #23).** The independent review found nothing blocking, plus three should-fix items: (1) `manage_access.py` flags access-list rows that contain look-alike letters but can't remove them, because `remove` refuses non-ASCII input; let `remove` take a row id. (2) No test proves an existing, linked member keeps access if their sign-in address has a look-alike letter (`auth.py:141-143`). (3) The refusal in wedding creation (`weddings.py:58-61`) is untested. Copy (decided-by-agent, reversible): the refusal message should tell people to ask the couple to add a different address, not to "type in plain letters". *Depends on:* PD-002 note, 2026-11-05 (ratified).
- **B52 — Node 20 is past upstream support.** Found in PR #42 (B47): Replit and CI run Node 20. *Fix:* move both to Node 22, then run the verify gate and a build on Replit. *Depends on:* nothing; low priority.
- **B50 — Incoming supplier emails can't be read.** Found in PR #34 (B46): the inbound-email path fails on `main` too, so vendor replies never reach the app. *Why it matters:* only if the couple want vendor replies in the app; today they send and read inquiries from their own email. *Fix:* engineering, once the couple want the feature. Vendor emails may name guests, so B49 applies. *Depends on:* the couple wanting it. *Since #44 (B49):* emails that reach the app inbox are skipped, not stored or sent to the AI; vendor replies are pasted on the Vendors screen instead.
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
| 2026-11-12 | **B87** — faded grey text deepened to at least 4.5:1 on every page (about 20 failures before, none after) | #108 |
| 2026-11-12 | **B86** — publish build fails when the workspace database is behind; one Shell command brings it up to date. First publish after merge passed (owner, 2026-11-12: "it worked!") after she ran `python db_status.py upgrade` by hand | #105 |
| 2026-11-12 | **B85** — a deeper clay for text and icons (about 5.5:1, was 2.6:1); clay fills unchanged | #104 |
| 2026-11-12 | **B83** — a deeper antique gold for text and icons on light backgrounds (about 5.3:1, was 2:1); gold buttons unchanged | #102 |
| 2026-11-12 | **B82** — rename a tip from its Edit form; the over-budget note covers tips and says a percentage tip moves with the cost | #101 |
| 2026-11-12 | **B81** — a percentage tip's one unpaid full-amount payment follows the tip; otherwise a note shows the gap (PD-018). No database change | #101 |
| 2026-11-12 | **B80** — about 44 px tap areas on the Checklist and Vendors pages on a phone; Cancel lines up with Save | #99 |
| 2026-11-12 | **B84** — Vendors "Still to do" badges no longer cover section names at desktop widths | #99 |
| 2026-11-12 | **B79** — tips as their own expense lines, by percentage or amount, in the expense's category; follow the cost until paid; ask before archiving or removing; Tips filter and total (PD-017). Publish adds four columns | #94 |
| 2026-11-12 | **B72** — dark text on the gold buttons, tabs, chips and badges; the gold is unchanged (5.9:1 and 8.2:1, was 2.7:1 and 2.1:1) | #96 |
| 2026-11-12 | **B78** — the Budget page fits a phone (360–430 px): forms stack, about 44 px taps, wide tables scroll in their own box. No database change | #93 |
| 2026-11-12 | **B43** — the AI split's price filter catches bare amounts; one note when a reason is hidden; renaming no longer clashes when the name is unchanged; "over budget" shows once | #93 |
| 2026-11-12 | **B29** — no code needed: Budget and Checklist already show a loading placeholder, not sample content | #93 (checked) |
| 2026-11-12 | **B76** — Add expense takes type, payment amount, due date, who paid and comments in one step; one estimate-or-quote box; "Actual cost"; a "People who pay" list kept in the app; who paid on every payment; a "Who paid" chart; payer in export and print (PD-016). Publish adds one table and one optional column | #89 |
| 2026-11-12 | **B70** — a "DROP means Cancel" warning at the top of the Replit publish steps; the run-script and `db_status.py` checks already existed | #87 |
| 2026-11-10 | **B75** — fold and unfold the seven Vendors sections, Expand all / Collapse all, remembered per device (PD-015 follow-up). No database change | #85 |
| 2026-11-10 | **B74** — Budget page (PD-015): Food & Drink suggested category (Venue & Catering becomes Venue; one-click "Rename to Venue"), Add expense on every category and at the top, sticky jump bar, fold and unfold every section. No database change | #83 |
| 2026-11-10 | **B69** — budget step 5 (PD-013): Export box with "Download CSV" (opens in Google Sheets; archived and vendor contacts only if ticked; formula guard) and "Print / save as PDF". No database change. Completes the budget tracker from the owner's brief (B65–B69) | #81 |
| 2026-11-10 | **B71** — a suggested budget category the couple delete isn't offered again; "Show suggestions you removed" brings them back to the list. Publish adds `declined_budget_defaults` to `weddings` | #80 |
| 2026-11-10 | **B68** — budget step 4 (PD-013): Upcoming payments (overdue, 7 days, 8–30 days, later; Chicago date; deposit / payment / final balance / refundable tags) and a hideable Charts section (spending by category, target vs committed, payments made), each readable as a table; clicking a category opens its expenses. No database change | #78 |
| 2026-11-10 | **B67** — budget step 3 (PD-013): the ten suggested categories on the couple's click, one-tap expense ideas (ketubah, chuppah, rabbi's fee under Ceremony & Legal), reorder, duplicate (no payments copied), delete only after moving expenses, and a sortable, filterable, searchable "All expenses" list. Publish adds `sort_order` to `budget_categories` | #76 |
| 2026-11-10 | **B66** — budget step 2 (PD-013): the dashboard's six questions with explanations, progress bars, category targets with share and status, over-budget heads-ups, moving money between categories, Contingency on the couple's click. No database change | #74 |
| 2026-11-09 | **B65** — budget step 1 (PD-013): estimated, quoted and final cost, contract status, method, notes, Drive link and vendor link per expense; method, reference, date paid and refundable per payment; unpaid / partly paid / paid / overdue on Chicago's date; overpay warning. Wildman BT entered by a one-time data step, nothing paid. Published 2026-11-09 with no Replit database step; the live app applied it on start. Also closes B44 (agents and Dashboard read the new budget), B45 (Chicago date) and B56 (budget half) | #72 |
| 2026-11-09 | **B64** — "Not selected" vendor status: muted red, faded, at the bottom of its section; ignored by the section summary. Stored as a new yes/no column, so publishing added a column and dropped nothing | #69 |
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
