---
name: product-call
description: Make, prepare or record a product decision for this one-wedding app (scope, UX, data or vendor choice) against docs/product/, record it in docs/product/decisions.md and re-rank docs/backlog.md. Use for product-lane work, triaging an idea, recording wedding facts, or when an engineering task needs a choice docs/product/ doesn't settle.
---

# Product call

The product lane decides *what* gets built for this one wedding. It writes only `docs/product/**`, `docs/backlog.md` and GitHub issues, never code. The couple owns every decision; the lane prepares the decision and keeps the record.

## 1. Ground it
- Read `docs/product/wedding.md` (facts) and `docs/product/decisions.md` (settled calls). The highest `PD-NNN` is the newest; later decisions supersede earlier ones. If they already answer the question, cite the entry and stop.
- Check `docs/backlog.md` for duplicates.
- Check what the app already does, and whether it's real or mocked (see "What's actually there today" in `.agents/AGENTS.md`).

## 2. Classify and act

| Kind | Example | Action |
|---|---|---|
| **Wedding fact** | date, place, budget, guest count, access | Ask the couple. Record the answer in `wedding.md`. Never infer it. |
| **Reversible build choice** | default sort order, copy wording | Decide it. Log it as `decided-by-agent` so the couple can overturn it. |
| **Couple's call** | anything about money, guests, vendor contact, who gets access, where data is stored, cutting a feature (including a legacy SaaS surface), taste or tone | Write it up as `proposed` with at most three options. Nothing gets built on it until the couple marks it `ratified`. |
| **Work item** | a gap or feature with a settled decision behind it | Add a backlog entry: B-number, what, why, fix shape, and the PD it depends on. |

**Rank against the wedding date.** Ask whether this matters before the wedding and by when. Cutting is a valid outcome. Keep the "Next up" list at the top of `docs/backlog.md` ordered, and mark each item `ready` or `needs-owner: <question>`. The autopilot builds only `ready` items.

## 3. Record
Append to `docs/product/decisions.md`. Re-check the highest number immediately before writing:

```
## PD-NNN — <decision in one line>
**Date:** YYYY-MM-DD · **Status:** proposed | ratified (by <who>) | decided-by-agent | superseded by PD-MMM
**Context:** what prompted it, with links.
**Options:** A / B (/ C), each with what it costs the couple and the build.
**Decision:** the choice, or "awaiting couple" if proposed.
**Rejected because:** one line per rejected option.
```

Re-rank `docs/backlog.md` if priorities changed.

## 4. Hand off
Return the decision (or the question) in one or two sentences that engineering can act on, the recommended option, what is blocked until the couple answers, and the entries you added.
