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
