---
name: product-call
description: Make or record a VenueFlow product decision (scope, UX, data or vendor choice) against docs/product/, then record it in docs/product/decisions.md and re-rank docs/backlog.md. Use for product-lane work, or when an engineering task needs a choice docs/product/ doesn't settle.
---

# Product call

> **Stub.** Refine as the product docs fill in.

1. **Ground it.** Read `docs/product/wedding.md` (facts) and `docs/product/decisions.md` (settled calls). If they already answer the question, cite the entry and stop.
2. **Facts aren't yours to decide.** If the call depends on a fact that is `[GAP]` or missing (date, place, budget, guest count, access), ask the couple instead of guessing.
3. **Frame it.** State the question, the options (at most three), and what each one costs the couple and the build.
4. **Decide.** Choose against what's already settled. Removing a legacy SaaS surface counts as a product decision.
5. **Record it.** Add an entry to `docs/product/decisions.md` (`YYYY-MM-DD: decision. Why: reason.`) and re-rank `docs/backlog.md` if priorities changed.
6. **Answer.** Return the decision in one or two sentences that engineering can act on, with the entry you added.

The product lane writes only `docs/product/**`, `docs/backlog.md` and GitHub issues. It never edits code.
