# VenueFlow — MVP User Stories (Prioritized, AI Wedding Coordinator)

> **Historical (XPRIZE SaaS era).** The billing, planner and admin personas below no longer apply: this is a private app for one wedding (PD-001), and payments, planners and admin were removed (PD-003). Current scope lives in `docs/product/`.

Personas:
- **Couple** — B2C customer, pays one-time coordinator fee (€299–€999) per wedding.
- **Planner** — B2B customer, pays monthly subscription (€199–€499/mo), manages multiple client weddings.
- **Admin** — internal, runs ops and assembles the XPRIZE submission package.

Epics: Onboarding & Billing, Agent-driven Planning, Contracts & Tracked Payments, Agent Execution Logs, RSVPs & Day-of, Planner Workflow, Reporting & Submission.

Priority: **P0** = must-have for Day-90 XPRIZE submission. **P1** = important but cuttable if behind. **P2** = nice-to-have.

Entity names below refer to [ERD.md](./ERD.md).

---

## P0 — Onboarding & Billing

**1. As a couple, I want to create my wedding profile (date or date range, region, guest count, budget, style) so the agent can build a tailored plan.**
- Acceptance: `User` (role=couple) and `Wedding` (status=`intake`) created. `BudgetLine` rows seeded across all categories using a default split scaled to `budget_total`. `TimelineItem` rows of `kind=planning` seeded by the agent for the standard pre-wedding milestones, each with `generated_by_agent_id` set. An `AgentDecisionLog` row records the kickoff with `decision_type=timeline_generate`.

**1a. As a couple, I want to specify my wedding tradition or ceremony type (e.g., Irish Catholic, Civil/Humanist, Hindu, Muslim, Multi-cultural) so the agent generates a culturally appropriate budget split and timeline.**
- Acceptance: `Wedding.ceremony_type` field populated at intake. The `intake_planner` agent uses ceremony-type-specific budget templates (e.g., Irish Traditional includes Band/DJ at ~8–10% of budget; Hindu template includes Mehndi, Sangeet, Mandap at appropriate allocations; Civil/Humanist omits church fees). `TimelineItem` rows reflect tradition-specific milestones (e.g., pre-marriage course for Catholic, Mehndi night for Hindu). A "Custom" option allows the couple to manually adjust categories. `AgentDecisionLog` captures the ceremony_type in `input_payload` and the template selection rationale.
- Edge case: Mixed-tradition weddings (e.g., Catholic + Hindu) — agent should present a merged template and let the couple adjust, rather than forcing a single tradition.
- Guardrail: Agent must never allocate budget to categories that don't exist in the Irish/UK market (e.g., "Rehearsal Dinner" is American, not Irish). Mary-Aoife to validate all default templates.

**2. As a couple, I want to pay a one-time coordinator fee so the agent starts working on my wedding.**
- Acceptance: `Payment` recorded with `payment_type=coordinator_fee`, `stripe_payment_id` set, `status=succeeded`. `Wedding.status` transitions `intake → planning`. The agent runs initial supplier sourcing within 24h of payment success (see story 4).

**3. As a planner, I want to subscribe to a monthly plan and create weddings on behalf of clients so I can run my book of business through VenueFlow.**
- Acceptance: `Subscription` created with `stripe_subscription_id`, `status=active`. Planner can create `Wedding` rows with `planner_user_id=self`; a stub `User` (role=couple) is created for each client and linked via `couple_user_id`. Planner can invite the couple to claim the stub account later (out of scope for the auth flow itself).

---

## P0 — Agent-driven Planning

**4. As a couple (or planner-on-behalf), I want the agent to shortlist a venue and at least 3 other supplier categories within 24h of intake so I have concrete options to react to.**
- Acceptance: `Booking` rows with `status=shortlisted` created for ≥1 venue category and ≥3 other categories. Each shortlist entry has `sourced_by_agent_id` set. Per shortlist run, `AgentDecisionLog` entries with `decision_type ∈ {venue_match, supplier_match}` include rationale and the matching criteria in `input_payload`. The agent also drafts a vendor inquiry message per shortlisted booking, stored in the log's `output_payload` (no separate Message table) and surfaced for the couple to approve/edit before send.

**4a. As a couple, I want to update my wedding date, guest count, budget, or region after intake and have the agent re-evaluate its recommendations, so the plan stays accurate as my situation changes.**
- Acceptance: When any core `Wedding` field (date, guest_count, budget_total, region) is updated, the system flags all `Booking` rows with `status=shortlisted` as `needs_review`. The `venue_matcher` and `supplier_matcher` agents re-run against the new parameters. An `AgentDecisionLog` entry with `decision_type=re_evaluation` is written capturing old vs. new parameters in `input_payload`. Bookings with `status=booked` are NOT automatically re-evaluated — the couple is notified that existing commitments may no longer align with updated parameters and given the choice to keep or renegotiate.
- Edge case: Couple changes guest count from 80 to 200 — the booked venue may no longer fit. Agent must surface a clear warning, not silently ignore the conflict.
- Edge case: Couple changes date to next month — timeline collapses from 12 months to 4 weeks. Agent must generate an accelerated "sprint" timeline, not a standard one.

**4b. As the system, when a vendor does not respond to an inquiry email within 5 business days, the agent should send one follow-up, and if still no response after 10 business days, flag the vendor as unresponsive and suggest alternatives to the couple.**
- Acceptance: `Booking` rows with `status=shortlisted` where the outbound inquiry was sent (tracked via `AgentDecisionLog` with `decision_type=inquiry_draft`) are monitored by a scheduled agent. At Day 5 with no inbound reply (no matching `quote_extractor` log entry): agent drafts a follow-up email, logged with `decision_type=inquiry_followup` and `parent_decision_id` linking to original inquiry. At Day 10 with still no reply: `Booking.status` transitions to `unresponsive`, the couple/planner is notified, and `supplier_matcher` is re-triggered to find alternatives for that category. `AgentDecisionLog` captures the full follow-up chain.
- Edge case: All vendors in a category for a specific region are unresponsive — agent should widen the search radius and inform the couple ("no photographers responded in Sligo; here are options in Galway and Donegal").

**4c. As a couple, when I have received multiple quotes for the same supplier category, I want the agent to present a side-by-side comparison with trade-off analysis so I can make an informed choice.**
- Acceptance: When ≥2 `Quote` rows exist for `Booking` rows in the same category for one `Wedding`, the agent generates a comparison. The comparison normalizes pricing to a common basis (e.g., "per head" for catering, "per hour" for DJs, total package for photographers) and highlights what's included vs. extra in each quote. An `AgentDecisionLog` entry with `decision_type=quote_comparison` captures the structured comparison in `output_payload` including: normalized price, inclusions, exclusions, value-for-money reasoning, and the agent's recommendation with rationale. The comparison is surfaced to the couple in the decision feed.
- Edge case: Quotes have completely different structures (one photographer includes an album + engagement shoot, another is ceremony-only). Agent must not compare on price alone — it must surface the scope differences clearly.

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

**13a. As a couple, I want to invite my partner to our wedding account so we can both view, approve, and override agent decisions together.**
- Acceptance: `Wedding.partner_user_id` field added. Primary couple user can send an invite (email or link). Partner creates or links a `User` account (role=couple) and gains read/write access to the same `Wedding` and all related entities. Both users can approve vendor inquiry drafts, acknowledge contract flags, and override agent decisions. All actions by either partner are attributed to their respective `user_id` in the `AgentDecisionLog`. No conflicting simultaneous approvals — if Partner A approves a vendor email, Partner B sees it as approved (not re-prompted).
- Edge case: Partners disagree — one approves a venue, the other wants to override it. System should surface the conflict and require both to confirm before proceeding with a booking (for `Booking.status` transitions to `booked` only).

---

## P2 — Reporting & Submission Readiness

**14. As the founder, I want an exportable XPRIZE submission package (revenue CSV, named customer contacts, agent log export, screenshots) so we can submit on the deadline without scrambling.**
- Acceptance: Single endpoint produces a ZIP containing: `Payment` + `Subscription` rollup CSV, `User` contacts CSV (couples + planners with consent flag), full `AgentDecisionLog` CSV, and a generated screenshot bundle of the dashboard.

**15. As the engineering lead, I want a dashboard showing one-time revenue + MRR + agent decisions per day so I can track progress against the Day-90 target.**
- Acceptance: Time-series charts for: daily new `Payment`s of `payment_type=coordinator_fee`, active `Subscription` count and MRR, daily `AgentDecisionLog` count broken down by `decision_type`.

---

## Notes / Clarifications

- **Day-90 cut line:** stories 1–8 (P0) are non-negotiable for the submission — they generate the revenue numbers, the named-customer list, and the agent execution log that the XPRIZE judges require. Stories 1a, 4a, 4b, 4c are P0 additions that address critical failure modes discovered during edge case analysis.
- **Cuttable if behind:** stories 10–13 (P1) can be partial. RSVPs and seating only matter for couples whose wedding date is within the planning window of the demo period. Story 13a (partner invite) is P1 — important for real-world usage but not required for XPRIZE submission.
- **Out of scope for MVP:** money transmission (couples pay suppliers directly per [ERD.md](./ERD.md) — VenueFlow does not hold supplier funds), supplier-side accounts (suppliers are sourced/contacted, not customers), venue admin tooling (no `venue_admin` role exists).
- **Agent capability checklist** (from [README.md](../README.md) §4.1 — every coordinator capability must be covered): vendor sourcing (story 4), timeline drafting (1, 12), budget tracking (9), contract review (5), RSVP/seating logic (10, 11), day-of run-of-show (12).

---

## Edge Cases & Failure Modes (cross-cutting, applies to all stories)

The following failure modes were identified during edge case analysis and apply across multiple stories. Each agent implementation must account for these:

### Input Validation Failures
| Scenario | Affected Stories | Required Handling |
|---|---|---|
| Unrealistic budget (e.g., €5,000 for 200 guests in Dublin) | 1, 1a, 4 | Agent must flag as unrealistic with market-rate context ("average cost for 200 guests in Dublin is €25,000–€35,000") and suggest adjustments rather than hallucinating an impossible plan. Log as `decision_type=intake_validation` with `status=blocked_by_guardrail`. |
| Vague or missing data (date="TBD", location blank) | 1, 4 | System must accept partial data gracefully. Agent generates a range-based plan ("assuming summer 2027, here's your timeline") and flags which fields need confirming. Do not block onboarding. |
| Wedding date too close (<4 weeks) or too far (>3 years) | 1, 1a | Agent generates an accelerated sprint timeline for short-notice weddings or a phased long-horizon plan. Never apply a standard 12-month template blindly. |
| Mismatched deposit amount vs. contract terms | 6 | System should cross-reference `SupplierPayment.amount` against `Contract` deposit terms where available and surface a warning if they don't match. Do not auto-correct — let the couple confirm. |

### External System Failures
| Scenario | Affected Stories | Required Handling |
|---|---|---|
| Gemini API timeout or error | 1, 4, 5, 9 | `AgentDecisionLog` row written with `status=error`, `error_kind=api_timeout`. Retry with exponential backoff (max 3 retries). If all retries fail, notify the couple that the action is delayed and will retry automatically. Never leave a log row stuck in `pending`. |
| Stripe webhook dropped or delayed | 2, 3 | Implement a reconciliation cron job (every 15 min) that checks for `Payment` rows with `status=succeeded` in Stripe but `Wedding.status` still at `intake`. Auto-heal by triggering the `intake → planning` transition. |
| SendGrid delivery failure or blacklisting | 4, 4b | Track email delivery status via SendGrid webhooks. If an inquiry email bounces, log as `status=error` on the `AgentDecisionLog` entry, flag the vendor's contact info as potentially invalid, and notify the couple. |
| Cloud Storage outage (contract PDF inaccessible) | 5 | Contract review must gracefully degrade — notify the couple that review is delayed, and retry when storage is available. Do not block the entire booking flow. |
| Database transaction partial failure | 6 | All state changes for a booking (Contract update + SupplierPayment insert + BudgetLine update + Booking status change) must be in a single DB transaction. If any part fails, the entire transaction rolls back. No inconsistent state. |

### Agent Decision Guardrails
| Scenario | Affected Stories | Required Handling |
|---|---|---|
| Cultural/market hallucination (American terms in Irish context) | 1, 1a, 4 | All agent prompts must include explicit Irish/UK market grounding. Guardrail check: reject any budget category or vendor type not in the approved Irish wedding category list. Log blocked outputs as `status=blocked_by_guardrail`, `error_kind=cultural_mismatch`. |
| No matching venues/suppliers in database | 4 | Agent must never hallucinate a venue or supplier. If no matches found: return an honest empty result with suggestions ("no exact matches in Sligo — closest options are in Galway, 45 min drive"). Log as `status=success` with `confidence_score` reflecting the relaxed criteria. |
| Hallucinated vendor contact info | 4 | Vendor contact info must come from the curated database only. If agent uses web search to find new vendors, contact details must be verified against the vendor's website before any outbound email is sent. Unverified contacts are flagged for manual review. |
| Missed critical contract clause | 5 | Contract reviewer must include a standard checklist of Irish-market risk clauses (cancellation terms, corkage fees, noise restrictions, overtime charges, minimum spend, wet weather policy for outdoor venues). If the agent's output doesn't address each checklist item, the system appends "not found in contract — verify with vendor" for each missing item. |
| Premature agent triggering (agent runs before prerequisite data is committed) | 2, 4 | Agent jobs must not be enqueued until the triggering transaction is fully committed. Use transactional outbox pattern or post-commit hooks — never enqueue inside an uncommitted transaction. |
| Agent ignores human override | 8, 9 | All agents must check for `status=overridden` on parent decisions before acting on their output. If a couple overrode a venue choice, `budget_monitor` must use the override data, not the original AI selection. |

### PII & Compliance
| Scenario | Affected Stories | Required Handling |
|---|---|---|
| PII in agent logs (vendor phone numbers, couple addresses in payloads) | 7 | PII redaction at export time must use both regex patterns (phone, email, Eircode) AND a Gemini Flash pass for unstructured PII in free-text fields. Over-redaction guardrail: venue names, supplier business names, and location names must be on an allowlist to prevent false redaction (e.g., "Castle Leslie" should not be redacted as a person's name). |
| GDPR data deletion request | All | Out of scope for Day-90 MVP, but the architecture must not make it impossible. Soft-delete with `deleted_at` timestamps on `User` and `Wedding` tables, with cascade logic documented for future implementation. |
