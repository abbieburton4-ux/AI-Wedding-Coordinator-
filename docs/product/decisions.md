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
