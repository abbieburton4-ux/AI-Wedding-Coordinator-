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
