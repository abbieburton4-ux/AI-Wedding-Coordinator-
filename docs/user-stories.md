# VenueFlow — MVP User Stories (Prioritized, AI Wedding Coordinator)

Personas:
- **Couple** — B2C customer, pays one-time coordinator fee (€299–€999) per wedding.
- **Planner** — B2B customer, pays monthly subscription (€199–€499/mo), manages multiple client weddings.
- **Founder / Admin** — internal, runs ops and assembles the XPRIZE submission package.

Epics: Onboarding & Billing, Agent-driven Planning, Contracts & Tracked Payments, Agent Execution Logs, RSVPs & Day-of, Planner Workflow, Reporting & Submission.

Priority: **P0** = must-have for Day-90 XPRIZE submission. **P1** = important but cuttable if behind. **P2** = nice-to-have.

Entity names below refer to [ERD.md](./ERD.md).

---

## P0 — Onboarding & Billing

**1. As a couple, I want to create my wedding profile (date or date range, region, guest count, budget, style) so the agent can build a tailored plan.**
- Acceptance: `User` (role=couple) and `Wedding` (status=`intake`) created. `BudgetLine` rows seeded across all categories using a default split scaled to `budget_total`. `TimelineItem` rows of `kind=planning` seeded by the agent for the standard pre-wedding milestones, each with `generated_by_agent_id` set. An `AgentDecisionLog` row records the kickoff with `decision_type=timeline_generate`.

**2. As a couple, I want to pay a one-time coordinator fee so the agent starts working on my wedding.**
- Acceptance: `Payment` recorded with `payment_type=coordinator_fee`, `stripe_payment_id` set, `status=succeeded`. `Wedding.status` transitions `intake → planning`. The agent runs initial supplier sourcing within 24h of payment success (see story 4).

**3. As a planner, I want to subscribe to a monthly plan and create weddings on behalf of clients so I can run my book of business through VenueFlow.**
- Acceptance: `Subscription` created with `stripe_subscription_id`, `status=active`. Planner can create `Wedding` rows with `planner_user_id=self`; a stub `User` (role=couple) is created for each client and linked via `couple_user_id`. Planner can invite the couple to claim the stub account later (out of scope for the auth flow itself).

---

## P0 — Agent-driven Planning

**4. As a couple (or planner-on-behalf), I want the agent to shortlist a venue and at least 3 other supplier categories within 24h of intake so I have concrete options to react to.**
- Acceptance: `Booking` rows with `status=shortlisted` created for ≥1 venue category and ≥3 other categories. Each shortlist entry has `sourced_by_agent_id` set. Per shortlist run, `AgentDecisionLog` entries with `decision_type ∈ {venue_match, supplier_match}` include rationale and the matching criteria in `input_payload`. The agent also drafts a vendor inquiry message per shortlisted booking, stored in the log's `output_payload` (no separate Message table) and surfaced for the couple to approve/edit before send.

**5. As a couple, I want the agent to review every supplier or venue contract and flag risky terms before I sign, so I don't get caught by a clause I didn't notice.**
- Acceptance: When a `Contract` is created, `risk_flags` is populated (JSON array of `{clause, severity, note, suggested_action}`) and `reviewed_by_agent_id` is set. An `AgentDecisionLog` entry with `decision_type=contract_review` is written linking `booking_id` and the input contract text. Signing is gated on the couple acknowledging the flags.

---

## P0 — Contracts & Tracked Payments

**6. As a couple, I want to sign a supplier contract and record the deposit I paid the supplier directly, so my budget reflects reality and the agent can keep coordinating.**
- Acceptance: `Contract.signed_by` updated with user ids + timestamps. A `SupplierPayment` row is created (`kind=deposit`, `external_reference` for the receipt). The related `BudgetLine.spent_amount` for the supplier's category is incremented. `Booking.status` transitions to `booked`; if the supplier is a venue, `Wedding.venue_id` is set (and `Wedding.status` transitions to `booked` on the first venue booking).

---

## P0 — Agent Execution Logs (XPRIZE-critical)

**7. As the system, I want to record every autonomous agent action — including failures — as a timestamped, reproducible log entry so we can export production-grade proof for the XPRIZE submission.**
- Acceptance: For every agent action (matching, drafting, reviewing, alerting, scheduling, rescheduling, post-event follow-up), an `AgentDecisionLog` row is written with: `agent_id`, `model_id`, `prompt_version`, `decision_type`, `status` (including `error`/`blocked_by_guardrail` paths, not only `success`), `trigger`, `rationale_summary`, `input_payload`, `output_payload`, `confidence_score`, `latency_ms`, `tokens_input`, `tokens_output`, `external_api_calls`, and `follow_up_actions`. Chained decisions set `parent_decision_id`. CSV export endpoint returns the full log filtered by date range and (optionally) `wedding_id`, `decision_type`, or `status`, with PII redaction applied at export time.

**8. As a couple or planner, I want to see the agent's decisions and rationale for my wedding(s) and override any of them, so I stay in control.**
- Acceptance: Per-wedding decision feed lists `AgentDecisionLog` entries newest-first with `decision_type`, `rationale_summary`, `status`, and a diff/summary of `output_payload`. Override action: (a) sets `overridden_by_user_id` and flips `status` to `overridden` on the original entry, (b) writes a new follow-up `AgentDecisionLog` entry with `parent_decision_id` linking back, `trigger=couple_action` (or `planner_action`), the replacement payload in `output_payload`, and the override reason in `rationale_summary`, (c) updates downstream entities (e.g., swapped seating assignment, re-quoted booking) via the override handler.

---

## P1 — Budget, RSVPs, Day-of

**9. As a couple, I want the agent to track my budget vs. accepted quotes and tracked supplier payments and alert me when a category is at risk of going over, so I can decide before I'm stuck.**
- Acceptance: When `Quote.status` transitions to `accepted` or a `SupplierPayment` is added, `BudgetLine.spent_amount` is recomputed. If `spent_amount + outstanding_accepted_quotes > allocated_amount` for any line, an `AgentDecisionLog` entry with `decision_type=budget_alert` is written and surfaced to the couple/planner.

**10. As a couple, I want to import my guest list and have the agent run RSVP follow-ups so I don't chase responses manually.**
- Acceptance: `Guest` rows imported (CSV or manual). The agent sends/drafts RSVP requests on a cadence; each send is an `AgentDecisionLog` entry with `decision_type=rsvp_followup`. `Guest.rsvp_status` updates when a response is received (manual entry or via response link).

**11. As a couple, I want the agent to propose a seating chart that respects constraints (families, +1s, dietary, accessibility) so I have a working starting point instead of a blank canvas.**
- Acceptance: `Guest.table_number` is populated by the agent. An `AgentDecisionLog` entry with `decision_type=seating_assign` captures the constraint set in `input_payload` and the assignment in `output_payload`. Overrides are stored per story 8.

**12. As a couple, I want the agent to generate and update the day-of run-of-show and export it as a PDF/share link for vendors, so everyone knows the schedule.**
- Acceptance: `TimelineItem` rows of `kind=day_of` are generated and updatable. Export endpoint returns a PDF ordered by `due_at`. `AgentDecisionLog` entries track each generation/update with `decision_type ∈ {runofshow_update, timeline_update}`.

## P1 — Planner Workflow

**13. As a planner, I want a multi-wedding dashboard showing status, outstanding tasks, and latest agent activity per client, so I can run my book without opening each wedding individually.**
- Acceptance: Lists `Wedding` rows where `planner_user_id=self` with: `status`, days-to-`wedding_date`, count of pending `TimelineItem`s, latest `AgentDecisionLog` summary, count of unaddressed `budget_alert` entries. Sortable by upcoming date and risk.

---

## P2 — Reporting & Submission Readiness

**14. As the founder, I want an exportable XPRIZE submission package (revenue CSV, named customer contacts, agent log export, screenshots) so we can submit on the deadline without scrambling.**
- Acceptance: Single endpoint produces a ZIP containing: `Payment` + `Subscription` rollup CSV, `User` contacts CSV (couples + planners with consent flag), full `AgentDecisionLog` CSV, and a generated screenshot bundle of the dashboard.

**15. As the engineering lead, I want a dashboard showing one-time revenue + MRR + agent decisions per day so I can track progress against the Day-90 target.**
- Acceptance: Time-series charts for: daily new `Payment`s of `payment_type=coordinator_fee`, active `Subscription` count and MRR, daily `AgentDecisionLog` count broken down by `decision_type`.

---

## Notes / Clarifications

- **Day-90 cut line:** stories 1–8 (P0) are non-negotiable for the submission — they generate the revenue numbers, the named-customer list, and the agent execution log that the XPRIZE judges require.
- **Cuttable if behind:** stories 10–13 (P1) can be partial. RSVPs and seating only matter for couples whose wedding date is within the planning window of the demo period.
- **Out of scope for MVP:** money transmission (couples pay suppliers directly per [ERD.md](./ERD.md) — VenueFlow does not hold supplier funds), supplier-side accounts (suppliers are sourced/contacted, not customers), venue admin tooling (no `venue_admin` role exists).
- **Agent capability checklist** (from [README.md](../README.md) §4.1 — every coordinator capability must be covered): vendor sourcing (story 4), timeline drafting (1, 12), budget tracking (9), contract review (5), RSVP/seating logic (10, 11), day-of run-of-show (12).
