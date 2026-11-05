# Product decisions

Settled and proposed product decisions, one entry per decision, newest at the bottom. The highest `PD-NNN` is current; superseding a decision takes a new entry, not an edit. Only the product lane edits this file, through the `product-call` skill, which also defines the format and statuses.

---

## PD-001 — This app plans one wedding, for the couple and their wedding party

**Date:** 2026-11-04 · **Status:** ratified (by the owner, one of the couple, 2026-11-04: "yes, just for our own wedding")
**Context:** This app is VenueFlow (AI Wedding Coordinator is the same app), built for the XPRIZE as a SaaS for many couples (paid checkout) and planners (subscriptions). A friend's agent-setup audit (2026-11-04) described this repo as meant for one wedding, used by the people planning it. The owner, who is one of the couple and makes decisions for the app (`wedding.md`), confirmed it on 2026-11-04.
**Options:** A: keep the multi-customer SaaS shape. B: run it as a private single-wedding app.
**Decision:** B. This is a private app for the couple's own wedding. Agents treat checkout, planner, admin, subscriptions and the marketing landing as legacy: they don't extend those surfaces and don't remove them either. Removing them is a separate decision (backlog B12).
**Rejected because:** A has no customers to serve here, and it adds payment, tenancy and marketing work that does nothing for this wedding.
**Note (2026-11-04):** the owner said who uses the app. For now: the couple and family of the couple, not wedding party members who aren't family ("no, just family for now but in the future yes"). The wedding party gets access later, when the owner adds them (backlog B22). This decision is unchanged. Current access levels are in `wedding.md`.

---

## PD-002 — Who can sign in, and how the owner manages access

**Date:** 2026-11-04 · **Status:** ratified (by the owner, one of the couple, 2026-11-04: "approve, yes to (a) and (b). for c, not yet")
**Context:** Backlog B10 and B22. No real wedding details have been entered into a running copy of the app yet (answer to call (c): "not yet", owner, 2026-11-04), so there's no existing data to carry over. Migrations still come before the new tables, so that data entered later is safe (rule 6). The owner wants three access levels (`wedding.md`): the partner (the groom) edits everything; family (4 parents, 2 siblings) view only, including the budget and dietary notes; wedding party members who aren't family get no access for now, but will later. The owner wants to add people and change permissions later, with several people per role. What the code does today:
- **Open sign-in.** A `mock-<id>` token signs in as anyone and creates the account if it doesn't exist (`auth.py:49`, flags default on in `config.py:21-22`). A second path accepts HS256 tokens signed with a default secret that's committed in the repo (`config.py:11`, `auth.py:73`). It also takes the user's role from the token and auto-creates the user, so turning the mock flags off doesn't close it. Real Firebase sign-in (email and password, or Google, `frontend/src/app/auth/AuthProvider.tsx`) auto-registers any new account as a couple (`auth.py:117-124`).
- **One owner per wedding.** A wedding has one `couple_user_id` and an optional `planner_user_id` (`models.py:40-41`). Every wedding endpoint checks one of those two (11 places in `weddings.py`, plus `payments.py:60`). So the partner and family can't be given access without a schema change. `User.role` is a single legacy value (couple, planner or admin, `models.py:19`) with no view-only level.
- **Firebase.** `FIREBASE_PROJECT_ID` defaults to `venueflow-dev` (`config.py:12`). [ASSUMPTION] That's the upstream VenueFlow project, not one the couple own.
**Options:**
- **A: Personal sign-in plus a list of who's allowed in, managed by the owner in the app.** Each person signs in with their own account through a Firebase project created under the owner's Google account. Google sign-in is the main way in, with email and password as a fallback. The app keeps a list per wedding of allowed email addresses, each with a level (owner, can edit, view only). Anyone not on the list is refused; there's no self sign-up. The owner adds or removes an email and changes its level on a settings screen, and any number of people can share a level. The app never emails invitations (hard rule 1). The owner tells people themselves.
  - *Couple's cost:* the owner sets up the free Google sign-in service (Firebase) under their own Google account themselves, following a step-by-step guide the team writes for them ([ASSUMPTION] about an hour). Each family member uses their Google account, or an email and password if they don't have one. Firebase sign-in is free at this size (about 50,000 monthly users on the free plan, per [Firebase pricing](https://firebase.google.com/pricing); verify before relying on it).
  - *Build:* a new membership table, which means introducing migrations first (rule 6). Rewrite the wedding access checks to use membership and level. Block every edit, and every agent run, for view-only users in the backend, not just by hiding buttons. Add the settings screen. Turn mock sign-in off by default, remove the default-secret HS256 path, and stop auto-creating unknown users. This is the largest build of the three.
- **B: Personal sign-in, but the allowed list is in server config that engineering edits.** Same sign-in as A. The list of emails and levels sits in a backend setting, not a screen.
  - *Couple's cost:* the same Firebase setup as A. Every change of access means asking whoever maintains the app and waiting for a redeploy.
  - *Build:* smaller. The level checks and the lock-down are the same as A. No settings screen. It probably still needs a membership link, or something like it, for the partner and family to reach the wedding.
- **C: Shared logins per level.** One login for "can edit" and one shared "family" login.
  - *Couple's cost:* the least setup.
  - *Build:* small.
  - *But:* nobody can be removed without changing the password for everyone. There's no record of who changed what. A forwarded family password exposes guests' dietary notes (health data, rule 3).
**Decision:** A, built in two steps.
- *Step 1:* lock down sign-in (mock off by default, the HS256 default-secret path removed, no auto-created accounts). Add migrations, then the membership list, seeded with the owner and the groom.
- *Step 2:* the settings screen to add people and change levels.
- *Who manages access:* the owner and the groom can both add people and change access (call (a)). The groom is also a second owner of the Firebase project.
- *The owner's own level:* edit everything (call (b)).
- *Guide:* the team writes the owner a step-by-step guide to set up Firebase.
**Technical choices settled by the team** (the owner asked not to be given technical questions, `wedding.md`, 2026-11-04; they approve the recommendation as a whole):
- *Sign-in method:* Google sign-in is the main way in. It matches the owner's preference for a user-friendly app with Google suite integrations, and it's already supported by the frontend (`AuthProvider.tsx`, `signInGoogle`).
- *Fallback:* email and password stays available but secondary. We don't know whether all six family members have Google accounts, and asking them would be a technical question. It costs little: Firebase supports it and the frontend already has it (`signInEmail`). Password-reset emails are sent only when the person themselves asks, so no agent sends anything (hard rule 1).
- *Who owns the Firebase project:* the owner's own Google account, so the couple control sign-in and it isn't the upstream `venueflow-dev`. [ASSUMPTION] This is the owner's preference. They confirmed it by approving this PD.
**Couple's calls, answered 2026-11-04:**
- (a) Can the groom also add people and change access, so nobody gets locked out? *Recommended: yes.* **Answer: yes.**
- (b) Does the owner get edit-everything access, like the groom? *Recommended: yes.* **Answer: yes.**
- (c) Has anyone already put real wedding details into a running copy of the app? **Answer: "not yet".** There's no existing data to carry over.
**Rejected because:**
- B fails the owner's explicit requirement to add people and edit permissions themselves.
- C can't remove one person, can't say who did what, and puts health data behind a shareable password.
**Adversarial pass on A:**
- *Lockout:* if only the owner can manage access and they lose their account, nobody can fix it without engineering. Call (a) addresses this.
- *Family friction:* family without Google accounts fall back to email and password. That means one more password for them to remember, which the fallback accepts as the price of not excluding anyone.
- *Google dependency:* if the owner's Google account is lost or suspended, the Firebase project goes with it. Call (a) reduces the risk to who can manage access, but not to project ownership. With (a) answered yes, the groom is added as a second owner of the Firebase project during setup.
- *Depends on hosting:* Firebase's allowed sign-in domains have to match where the app runs (B14), so A can be set up locally first but not finished until hosting is decided.
- *Levels are fixed:* this covers owner, edit and view only. Finer levels, such as budget hidden for some people, aren't covered and would need a new PD.
- *Who's out of scope:* guests signing in to RSVP aren't covered.
- *Who owns sign-in:* until the couple's own Firebase project replaces `venueflow-dev`, real sign-ins would land in a project they don't control.
**Note (2026-11-04), email confirmation:** email and password sign-in (the fallback) needs a "confirm your email" step. When someone signs up with a password, Google's sign-in service (Firebase) sends them one confirmation email, and only when they ask for it. The owner approved allowing it so family without a Google account can get in: "yes, and allow the email confirmation" (owner, one of the couple, 2026-11-04). This is a couple's call because it's an email to a family member. The person triggers it themselves and Firebase sends it, so no agent sends anything (hard rule 1).
**Note (2026-11-05), the settings screen (B22, PR #14):** owner (one of the couple), 2026-11-05: "block it, keep no".
- *Can one of the couple remove the other's power to manage access?* **No: blocked on the screen.** Neither owner can remove or demote the other. If it's ever really needed, the team does it on the owner's request.
- *Can the screen make anyone else an access manager?* **No.** Only the owner and the groom manage access. Everyone else is "can edit" or "view only".
**Note (2026-11-05), look-alike emails (B39):** the security review of PR #18 found that sign-in might treat an address with a look-alike letter (for example, from another alphabet) as one of the couple's or as one on the access list. Owner (one of the couple), 2026-11-05, asked "Shall I get a fix approved and built?": "sure".
- *Decision:* an address only matches the couple's or an access-list entry if it's the same address, letter for letter. Capital letters and spaces at either end don't matter; look-alike letters never count as a match.
- *Left to the team:* how the comparison is done, and the checks that prove it.
- *Guard:* no one already on the access list may lose access because of the change. If an address can't be matched safely, sign-in refuses it with a clear message rather than guessing.

---

## PD-003 — Remove the old business screens and the payment gate

**Date:** 2026-11-04 · **Status:** ratified (by the owner, one of the couple, 2026-11-04: "approve, nothing to keep")
**Context:** Backlog B12. PD-001 makes this a private app for one wedding but left the leftover VenueFlow business features in place until the couple decide. What the code does today:
- **Payment gate.** `REQUIRE_PAYMENT` defaults to `True` (`config.py:61`).
  - After setup, the planner builds a free "preview" of the budget and timeline (`planner.py:170-172`).
  - Venue and supplier matching only runs after checkout (`weddings.py:53-59`, `payments.py:19-31`). The dashboard shows a teaser with a button to `/wedding/checkout` (`Dashboard.tsx:306-407`).
  - With the default mock provider, checkout records a €299 "succeeded" coordinator-fee `Payment` row in the couple's data (`payments.py:59-75`, `COUPLE_PRICE_EUR`). That's a payment nobody made (rules 4 and 10).
  - The Stripe path, a signed `/webhooks/stripe` webhook, and a dev-only `/webhooks/debug/stripe-mock` endpoint (`webhooks.py:19-81`) could take real money if they were configured.
- **Planner area** (`/planner`: overview, clients, tasks, subscriptions, analytics, concierge) and **admin console** (`/admin`: overview, planners, agent log) are routed in `App.tsx:67-88` for the `planner` and `admin` roles. Several views are hard-coded (`admin/views/Overview.tsx`, `AgentLog.tsx` [B9], `planner/views/Subscriptions.tsx`). They're backed by `/auth/planner` (dev-only since PR #7, `auth.py:187-225`), `/metrics` (planner and admin only, `metrics.py:16`) and `seed_pilot.py` (3 pilot planner accounts).
- **Marketing landing.** `/`, `/experience` and every unknown path show the public VenueFlow marketing site (`App.tsx:39-44`).
- **Dependants.** `verify_endpoints.py` exercises `/auth/planner`, checkout, the Stripe webhook and `/metrics` (lines 43-303). It also includes the viewer checks from PD-002. The docs that describe the gate or these screens are `RUNBOOK.md`, `README.md`, `docs/architecture.md`, `docs/ERD.md`, `docs/user-stories.md`, `backend/.env.example:37` and `.agents/AGENTS.md`. The `Payment` and `Subscription` tables are in the baseline migration.
**Options:**
- **A: Remove them.** Delete checkout and the payment gate, the Stripe and mock-payment code, the planner area, the admin console, subscriptions and the marketing landing. Opening the app goes straight to sign-in, then to the wedding.
  - *Couple's cost:* nothing to do. They lose nothing they use.
  - *Build:* medium, in two steps.
    - Step 1: turn the gate off and unroute the screens.
    - Step 2: delete the dead frontend views, backend endpoints and `seed_pilot.py`. Remove the verify checks for removed endpoints, as an explicit, reviewed part of the removal (rule 8). Update the docs.
    - Git keeps everything, so it can be brought back.
- **B: Hide them, keep the code.** Turn the gate off and unroute the screens, but leave the code and endpoints in place.
  - *Couple's cost:* nothing to do.
  - *Build:* small.
  - *But:* the checkout and Stripe endpoints stay callable. Future agents keep tripping over code that no longer matches the app, which is how the €299 fake payment and the planner auto-sign-up got this far.
- **C: Only turn the payment gate off.** Leave the screens routed.
  - *Couple's cost:* they'd still see the old checkout button and marketing pages.
  - *Build:* smallest.
**Decision:** A, in two steps.
- *Step 1:* turn the payment gate off and unroute checkout, the planner area, the admin console, subscriptions and the marketing landing, so the app opens on sign-in.
- *Step 2:* delete the dead code, `seed_pilot.py`, the verify checks for removed endpoints only (reviewed, rule 8), and update the docs.
**Technical choices settled by the team** (the owner asked not to be given technical questions, `wedding.md`):
- *No automatic vendor matching at setup.* With the gate off, setup would otherwise run venue and supplier matching straight away (`weddings.py:84`, `with_cascade`). Today that can only suggest Irish vendors (B11). Matching runs only when the couple ask for it (the existing match endpoints, `weddings.py:433`, `460`) until B11 is settled.
- *Keep the `Payment` and `Subscription` tables for now.* Dropping them is a migration with no benefit while they're empty. A later clean-up can drop them.
- *The couple's own spending is a separate thing.* Their payments to vendors belong to budgeting (B23), not to this checkout.
- *Remove the planner and admin roles* from routing and sign-in. `/metrics` goes with them, so B9 and B18 close as moot. B8 (token counts) still applies to the decision log.
**Couple's calls, answered 2026-11-04:**
- (a) Is there anything in the old screens (the planner area, the admin console, the public homepage) that you use or want to keep? *Suggested: no.* **Answer: "nothing to keep".**
**Rejected because:**
- B leaves the money-taking code reachable, and the confusion that caused real bugs.
- C leaves the couple looking at a checkout and a sales site in their own wedding app.
**Adversarial pass on A:**
- *Losing something useful:* the admin agent log was meant to show what the AI decided. It's hard-coded today (B9), so nothing real is lost. A real "what the AI did" view for the couple could be a later PD if they want one.
- *Losing the ability to sell the app:* PD-001 already rules that out. Git keeps the code if that ever changes.
- *Tests shrinking:* removing verify checks could hide a regression. Only checks for removed endpoints go, and the PD-002 access checks stay.
- *Hosting and the domain:* the marketing site lives at `venueflow.ie` (B14). Removing the landing doesn't decide hosting or the domain; that's the next PD.

## PD-004 — What "in depth budgeting" covers (must-have 1)

**Date:** 2026-11-04 · **Status:** ratified (by the owner, one of the couple, 2026-11-04: "option c"; call (b): "yes")
**Context:** Backlog B23. Budgeting is the couple's first must-have (`wedding.md`). Today the planner creates budget categories with a planned and a spent amount, but nobody can add, edit or record anything (the only budget endpoint is read-only). Live amounts show in euros, though the couple want US dollars (B11). With no live lines, the screen shows made-up dollar figures that look real (B28). The total budget is still [GAP] ("still being determined", owner, 2026-11-04). Family (view only) can see the budget.
**Options:**
- **A: Planned vs actual, plus vendor payments.** The couple add, rename and remove categories, and set a planned amount for each. Under each category they record vendor costs: the quoted price, the deposit, and the remaining payments with due dates. Each payment is ticked as paid by a person; the app never marks anything paid (hard rule 4). The screen shows totals, what's left, and the next payments due. The total budget can stay blank until the couple set it.
  - *Couple's cost:* entering each vendor's price and payment dates as they book.
  - *Build:* medium. New tables with a migration, edit screens, amounts in dollars, stored as whole cents.
- **B: Planned vs actual only.** Editable categories with a planned and a spent amount each, and totals. No payments or due dates.
  - *Couple's cost:* less typing, but payment due dates live somewhere else.
  - *Build:* small.
- **C: A, plus who's contributing.** Everything in A, and a record of who is paying for what (for example, a parent covering a category).
  - *Couple's cost:* the same as A, plus agreeing contribution amounts with family. Family can see the budget, so they'd see each other's contributions.
  - *Build:* medium-plus.
**Recommendation:** A. It covers what usually goes wrong with wedding money (missed deposit dates and creeping totals) without asking the couple to put family contributions on a screen family can see. C can be added later.
**Technical choices settled by the team:** amounts in US dollars, stored as whole cents (rule 4). A Google Sheets export is a later step, in a separate PD on Google integrations.
**Decision:** C. Planned vs actual per category, vendor prices, deposits and payment due dates, plus a record of who is contributing to what. Family (view only) can see contributions, as with the rest of the budget. The couple tick payments as paid; the app never does (rule 4). Once the couple set a total, the AI suggests a starting split across categories. It's labelled as a suggestion and the couple edit it (call (b)).
**Couple's calls:**
- (a) A, B or C? *Recommended: A.* **Answer: "option c".**
- (b) Should the AI suggest a starting split across categories once you set a total? It would be labelled as a suggestion, and you'd edit it. *Recommended: yes.* **Answer: "yes".**
**Rejected because:**
- A leaves out who is contributing, which the couple want.
- B has no payments or due dates, so deposits would be tracked somewhere else.

## PD-005 — Delete the old sales list and the real-looking contacts in the prototype

**Date:** 2026-11-05 · **Status:** ratified (by the owner, one of the couple, 2026-11-05: "yes, you can delete the contact details and ols sales spreadsheet")
**Context:** Backlog B6 and B13. `planner-targets.xlsx` is VenueFlow's old sales prospect list: named people at real planning businesses, with their contact details. `streamlit_mock/` (the first prototype) holds demo emails and Irish mobile numbers that look real (found in PR #13). Both are in this public repo, and both may be other people's personal data (rule 3).
**Options:** A: delete them. B: keep them.
**Decision:** A. Delete `planner-targets.xlsx`. Remove or replace the real-looking emails and phone numbers in `streamlit_mock/` with obviously fictional ones (for example `@example.com`, no phone numbers). The rest of the prototype folder stays: whether to archive it all is still the owner's call (B13).
**Technical choices settled by the team:** deleting a file doesn't remove it from git history, so old copies stay visible in the repo's past commits. Erasing them from history needs a force-push, which the guardrails block, and it would be a separate owner decision. It isn't part of this decision.
**Rejected because:** B keeps other people's contact details published.
**Extended (2026-11-05):** also delete `outreach-list.xlsx` (another old sales list: about 43 named people at planning businesses, with social media handles) and the whole first prototype, `streamlit_mock/`. Owner (one of the couple), 2026-11-05: "Delete the second old outreach list and the whole first prototype". This settles the prototype part of B13. Git history still keeps old copies, as above.
**Extended again (2026-11-05), past prospects' first names (B40):** PR #20 found four first names of past sales prospects, one linked to a business, in `docs/runway.md`, `scripts/build_tracker.py` and probably `runway-tracker.xlsx`. Owner (one of the couple), 2026-11-05, asked "Shall we remove those too?": "yes". Remove them or replace them with roles (for example "a planner in Dublin"), wherever they appear in the repo's current files. Git history still keeps old copies, as above.

## PD-006 — Where the app and its data live, and what that costs

**Date:** 2026-11-05 · **Status:** superseded by PD-008 (the owner chose Replit, 2026-11-05)
**Context:** Backlog B14. The app runs only on a developer's computer, so nobody can use it for real yet, and real guest details (including dietary notes, which are health data) shouldn't go in until it has a proper home. The old deploy workflow would publish only the screens, with no database, to `venueflow.ie`, the original VenueFlow author's web address. The owner wants a user-friendly setup that works with Google's tools (`wedding.md`), and sign-in is already Google's (Firebase, PD-002). The app needs four things hosted: the screens, the backend with its background worker, a database, and the Gemini AI. About 8 people use it (the couple and 6 family members). Prices below were checked on 2026-11-05. They're estimates, not quotes, and Google can change them.
**Options:**
- **A: Google Cloud, under the owner's Google account (the same account as sign-in).** Screens on Firebase Hosting. Backend and worker on Cloud Run. A small Postgres database on Cloud SQL in Google's Iowa region (`us-central1`, the nearest to Chicago) with daily automatic backups. Background jobs on Cloud Tasks. Gemini on the paid tier.
  - *Monthly cost, estimated:* database about $8–10. Google's own example for the smallest database is $9.37 a month ([Cloud SQL pricing examples](https://cloud.google.com/sql/docs/postgres/pricing-examples?hl=en)). Backend: $0 expected, because 2 million requests a month are free ([Cloud Run pricing](https://cloud.google.com/run/pricing)). Background jobs: $0, because the first million a month are free ([Cloud Tasks pricing](https://cloud.google.com/tasks/pricing)). Screens: $0, inside Firebase Hosting's free 10 GB of storage and 360 MB a day of traffic ([Firebase pricing](https://firebase.google.com/pricing)). Gemini: [ASSUMPTION] a few dollars a month or less at this use, to be measured once it runs. **Total about $10–15 a month**, plus the web address. That's roughly $120–180 from now to an October 2027 wedding.
  - *Couple's cost:* about an hour following a step-by-step guide the team writes. Turning on billing on the owner's Google account with a payment card. Setting a spending alert. The groom is added as a second owner, as with sign-in.
  - *Build:* small to medium. The app was built for Google Cloud (it already uses Cloud Tasks), so the team mostly writes deployment settings and the guide.
- **B: An all-in-one hosting service (for example Render), with Google sign-in kept.** Roughly $7 a month for the backend and $6 a month for the smallest database ([Render pricing](https://render.com/pricing)), so about $13 a month, which is about the same as A.
  - *Couple's cost:* a second account and a second bill outside Google, and the data lives with a company the couple don't otherwise use.
  - *Build:* medium. The background jobs would need reworking, because Cloud Tasks is a Google service.
- **C: Don't host yet.** $0.
  - *Couple's cost:* nobody can use the app for real, and the budget and guest lists live somewhere else until it's hosted.
**Recommendation:** A. It keeps everything in one Google account the couple already control. It's the closest fit to how the app was built, so it's the least rework. It costs about the same as B.
**Technical choices settled by the team (if A):** the database is a managed Postgres with automatic daily backups. Secrets (the Gemini key, the worker and webhook secrets) are kept in Google's secret storage, never in git or in the screens (rule 5). Dev-only settings stay off (RUNBOOK). Firebase's allowed sign-in addresses are set to match the web address (PD-002). The old deploy workflow and the `venueflow.ie` address are retired. The team writes the guide; the owner presses the buttons.
**Couple's calls:**
- (a) A, B or C? *Recommended: A.*
- (b) Where the data is stored: Google's Iowa region, in the US. *Recommended: yes.*
- (c) Gemini AI on the paid tier, so Google doesn't use your wedding details to improve its products. On the free tier Google uses what you send it to improve its products, and "human reviewers may read" it. On the paid tier Google says it doesn't use your prompts or responses for that ([Gemini API terms](https://aistudio.google.com/docs/terms)). Costs a few dollars a month at most [ASSUMPTION]. *Recommended: paid.*
- (d) A spending alert on the Google account, emailed to the owner by Google. An alert warns you; it doesn't stop spending. *Recommended: alert at $25 a month.*
- (e) The web address. The owner asked for one based on the couple's first names, "if available" (2026-11-05). A `+` isn't allowed in web addresses, so the choices are spelled with "and", a hyphen or "plus". All three `.com` versions were unregistered on 2026-11-05 (registry lookup, which doesn't guarantee a purchase will go through). A `.com` costs $12 a year through Google ([Cloud Domains pricing](https://cloud.google.com/domains/pricing)) and renews automatically. The exact address isn't written here because this repo is public: [GAP] which spelling, and whether it's fine to record it here. *Recommended: the "and" spelling, in `.com`.*
- (f) What happens after the wedding: keep it running, or export everything and shut it down. *Can wait until after the wedding.*
**Decision:** awaiting couple.
**Rejected because:** awaiting couple.

## PD-007 — What the overall planning checklist covers (must-have 2)

**Date:** 2026-11-05 · **Status:** ratified (by the owner, one of the couple, 2026-11-05; calls (a)–(e) answered the same day: "select August 21 2027, and show a 'dates are provisional' but give me the option to change it. you can combine the ones that are overdue and put it in the longest month from now. dont lable them yet as overdue, but catch up. you can draft up an intiail jewish traditions list for me to review/add to")
**Context:** Backlog B24. The checklist is the couple's second must-have (`wedding.md`). Today the AI planner makes a short timeline of tasks, but nobody can tick them off, add or edit them, and it has no Jewish ceremony rules. On 2026-11-05 the owner brought their own checklist: 19 stages from "12 months before" to "post-wedding", with about 100 tasks, plus how the screen should work. The list stays in the owner's own file for now, pending call (e) ([checklist-list.md](checklist-list.md), part 1). The wedding date isn't fixed, and counting back from August 2027, the first three stages are already past.
**Decision:**
- **The list.** The checklist starts from the owner's list ([checklist-list.md](checklist-list.md), part 1), in the order given. The couple can tick tasks done, add their own tasks to any stage, rename tasks and delete any task.
- **The date.** Due dates are counted back from a provisional wedding date of 21 August 2027. The screen says the dates are provisional, and the couple can change the date; every due date then moves with it.
- **Stages already past.** Stages whose date has already passed are combined into one "Catch up" group. Its tasks are labelled "catch up", never "overdue".
- **Jewish traditions.** The product lane drafts a list for the couple to review and add to ([checklist-list.md](checklist-list.md), part 2). It isn't added to the checklist until they approve it.
- **The screen** (from the owner's spec): stages in order with a count each ("3 / 5"), an overall progress bar, a tick box per task, stages that fold away with the current one open, and a filter for All / Not done / Overdue. It works on a phone and with a keyboard.
**Couple's calls:**
- (a) When the "Catch up" group is due. I read "put it in the longest month from now" as: the catch-up tasks join the next stage still ahead, "9 months before", due 21 Nov 2026. The other reading is a separate group due one month from today (5 Dec 2026). *Recommended: the first reading, so nothing gets a made-up date of its own.* **Answer (2026-11-05): "21 november".** Catch-up tasks join the "9 months before" stage, due 21 Nov 2026 with the provisional date.
- (b) One shared checklist for the wedding: when you or the groom tick something, you both see it. Family can see it but not change it, as with the rest of the app. The owner's spec said each person's progress is saved separately. *Recommended: shared.* **Answer (2026-11-05): "One shared checklist? yes".**
- (c) This list replaces the AI planner's generated timeline on the checklist screen. Nothing is deleted; the AI's tasks just stop showing. *Recommended: yes. The AI timeline has no Jewish rules, and two lists would be confusing.* **Answer (2026-11-05): "you can combine the AI checklist with the one uploaded and then delete the AI".** So: the AI planner's tasks that aren't already on the owner's list are added to the checklist, as ordinary tasks the couple can edit or delete. Then the AI's separate timeline is deleted, and the planner stops making one.
- (d) Which draft Jewish traditions to add ([checklist-list.md](checklist-list.md), part 2). *Doesn't block the build: they can be added after the checklist works.* **Answer (2026-11-05): "cut J6, J14, J15, J16, J19, J22, J25 but keep the rest. combine find rabbi with find officiant".** 18 of the 25 draft tasks are added (J1–J5, J7–J13, J17, J18, J20, J21, J23, J24). J2 and the owner's list's "find the right person to officiate" task become one task.
- (e) Where the list came from. This project is public. If the list is copied from a wedding website, its wording goes only into the app's own database, not into this project's files. *Question for the owner: did you write it, or is it from a website?* **Answer (2026-11-05): "i got the checklist from loverly.com".** So the list's wording stays out of git. It goes only into the app's own database, loaded from the owner's file.
**Technical choices settled by the team:** when merging, an AI task goes into the stage nearest its due date, and a task that says the same as one on the owner's list is skipped, not duplicated; the merge is checked on a copy before anything is deleted. The checklist is saved in the app's database through the backend, not in the browser (rule 11), with a migration (rule 6). Owners and editors can tick and edit; viewers can only read (PD-002). If the date changes, stages move into or out of "Catch up" to match. A stage that passes from now on, with tasks not done, shows as "overdue" ("dont lable them yet as overdue" covers the stages already past). The loverly.com list is loaded into the database by a one-off import from the owner's file, kept outside git. Seeds and tests use fictional placeholder tasks. Ticking a task never marks a payment paid or a booking confirmed (rule 4).
**Rejected because:** a separate catch-up deadline would be a date nobody chose; separate checklists per person would split what the couple share; keeping the AI timeline would mean two lists. Call (c) chose merge-then-delete over keeping the AI timeline hidden. An earlier draft of this PD (options A: the owner's list with estimated dates, B: no dates until the date is fixed, C: a plain list) was replaced by this entry the same day, after the owner chose estimated dates from a provisional date.

## PD-008 — Host the app on Replit (supersedes PD-006)

**Date:** 2026-11-05 · **Status:** ratified for the hosting choice (by the owner, one of the couple, 2026-11-05: "i am choosing replit"); calls (a)–(d) below are proposed
**Context:** Backlog B14. PD-006 proposed Google Cloud. The owner has since set the app up in Replit and pushed the changes to `agent/fix-firebase-sign-in` (latest `ea21e16c`): one Replit app serves the screens and the backend, with Replit's managed PostgreSQL database, Firebase sign-in kept (PD-002), and the AI agents run inside each request instead of Google's task queue. Prices were checked on 2026-11-05 and are estimates, not quotes. Replit's own page lists the Core plan at $20 a month, or $18 billed yearly ([Replit pricing](https://replit.com/pricing)); it doesn't publish usage rates there. Third-party guides say Replit cut its publishing and database rates on 1 August 2026, and that the database is billed by the hours it's active ([SuperApp guide](https://superapp.dev/blog/replit-pricing), [Superblocks guide](https://www.superblocks.com/blog/replit-pricing)). Replit's production databases run on Neon, with a region set per database ([Replit docs](https://docs.replit.com/references/data-and-storage/production-databases)); which region this one uses is [GAP].
**Options:** A: Google Cloud (PD-006). D: Replit. (B, a separate host such as Render, and C, don't host yet, as in PD-006.)
**Decision:** D. The app is hosted on Replit. Estimated cost: the Core plan ($20 a month) plus usage, roughly $25–40 a month in total [ASSUMPTION], to be measured once it's running.
**Technical choices settled by the team:** before the app goes live: the Replit branch passes an independent review (sign-in, secrets, data), goes through a PR with the automatic checks, and its clashes with the checklist work are fixed (B46). Real data only goes in after that. Secrets live in Replit's secret storage, never in git or the screens (rule 5). Dev-only settings stay off (the run script forces them off). Schema changes still go through Alembic migrations (rule 6). The old GitHub Pages deploy workflow and the `venueflow.ie` address are retired. Because the agents run inside each request, a long AI task makes the screen wait (up to about 90 seconds); that's fine at this size.
**Couple's calls:**
- (a) The AI on Google's paid tier, so Google doesn't use your wedding details to improve its products ([Gemini API terms](https://aistudio.google.com/docs/terms)). A few dollars a month at most [ASSUMPTION]. *Recommended: paid.*
- (b) A spending limit or alert on your Replit account. *Recommended: an alert at $50 a month.*
- (c) Where the data is stored: the database's region, which the team will read from Replit's settings and report back [GAP]. *Recommended: a US region.*
- (d) The web address: Replit's free `.replit.app` address, or your own address from your first names (about $12 a year). *Recommended: your own address, with the "and" spelling, from PD-006.*
**Rejected because:** A means a second set-up when the owner already works in Replit; the owner chose Replit.
