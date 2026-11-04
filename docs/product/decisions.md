# Product decisions

Settled and proposed product decisions, one entry per decision, newest at the bottom. The highest `PD-NNN` is current; superseding a decision takes a new entry, not an edit. Only the product lane edits this file, through the `product-call` skill, which also defines the format and statuses.

---

## PD-001 — This app plans one wedding, for the couple and their wedding party

**Date:** 2026-11-04 · **Status:** proposed
**Context:** This app is VenueFlow (AI Wedding Coordinator is the same app), built for the XPRIZE as a SaaS for many couples (paid checkout) and planners (subscriptions). A friend's agent-setup audit (2026-11-04) described this repo as meant for one wedding, used by the people planning it. The couple hasn't confirmed this yet.
**Options:** A: keep the multi-customer SaaS shape. B: run it as a private single-wedding app.
**Decision:** awaiting couple; B is recommended. Until it's ratified, agents treat checkout, planner, admin, subscriptions and the marketing landing as legacy: they don't extend those surfaces and don't remove them either.
**Rejected because:** A has no customers to serve here, and it adds payment, tenancy and marketing work that does nothing for this wedding.
