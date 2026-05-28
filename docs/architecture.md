# VenueFlow — Architecture (MVP, AI Wedding Coordinator)

> [!WARNING]
> **Implementation Status**: This document details the planned Day-90 target architecture.
> - **Current Implementation**: A single Streamlit application backed by a local **SQLite** database, using a unified Google Gemini model set via model resolution (`gemini-2.5-pro` for reasoning, `gemini-2.5-flash` for extraction).
> - **Planned Architecture**: Cloud Run services, Cloud Tasks queues, Cloud Scheduler, Cloud SQL Postgres, SendGrid parse webhook, Twilio SMS, and Firebase Auth are currently mock-simulated in the UI code rather than running as external infra.

This document describes the planned Day-90 architecture for the AI Wedding Coordinator product. It is paired with [ERD.md](./ERD.md) (data model) and [user-stories.md](./user-stories.md) (scope). Read [CLAUDE.md](../CLAUDE.md) first for product framing.

Constraints driving the picks:
- **XPRIZE rule:** must use Gemini + at least one Google Cloud product. The picks below satisfy this several times over.
- **Day-90 budget:** small team, fixed deadline. Default to managed services and boring choices.
- **`AgentDecisionLog` is the submission artifact.** Every agent invocation writes one row. This shapes the agent layer's invocation contract.

## Service map

```mermaid
flowchart LR
  subgraph Clients
    C[Couple browser]
    P[Planner browser]
    G[Guest RSVP page]
  end

  subgraph Edge
    FE[Vite React app<br/>Firebase Hosting]
  end

  subgraph App[Cloud Run services]
    API[API service<br/>REST + webhooks]
    Worker[Agent worker<br/>job consumer]
  end

  subgraph Async[Google Cloud orchestration]
    Sched[Cloud Scheduler<br/>daily/hourly ticks]
    Q[Cloud Tasks<br/>job queue]
  end

  subgraph Agents[Gemini agent layer]
    Pro[Gemini 3 Pro<br/>reasoning agents]
    Flash[Gemini 3 Flash<br/>high-volume loops]
  end

  subgraph Data
    PG[(Cloud SQL Postgres<br/>ERD entities)]
    GCS[(Cloud Storage<br/>contracts, PDFs, exports)]
    BQ[(BigQuery<br/>AgentDecisionLog mirror)]
  end

  subgraph External
    Stripe[Stripe<br/>Checkout + Billing]
    SG[SendGrid<br/>email out + inbound parse]
    Tw[Twilio SMS<br/>RSVP reminders only]
  end

  C --> FE
  P --> FE
  G --> FE
  FE --> API
  Stripe -. webhook .-> API
  SG -. inbound parse .-> API
  API --> PG
  API --> GCS
  API --> Q
  Sched --> Q
  Q --> Worker
  Worker --> Pro
  Worker --> Flash
  Worker --> PG
  Worker --> GCS
  Worker --> SG
  Worker --> Tw
  API --> Stripe
  PG -. Datastream .-> BQ
```

## Stack choices

### Database — Cloud SQL Postgres (not Firestore)

The ERD is heavily relational: polymorphic `Booking`, planner-multi-wedding joins, `AgentDecisionLog` filtered by `decision_type` × `status` × `wedding_id`. Firestore would mean denormalizing aggressively or doing joins in app code — both burn Day-90 budget. Postgres on Cloud SQL is the honest fit, ships row-level security for couple/planner data isolation, and gives us proper check constraints for the polymorphic `Booking` XOR.

Firebase is still used for Auth and Hosting (no migration pain there), but data lives in Postgres.

### Agent orchestration — Cloud Run + Cloud Tasks + Cloud Scheduler (Antigravity as a week-1 spike)

Default to a stack we can debug: API service on Cloud Run, async work via Cloud Tasks, recurring sweeps via Cloud Scheduler. Worker is a separate Cloud Run service consuming the queue — clean scaling, separate cold-start profile from the API.

Antigravity Managed Agents may earn its place if its built-in tracing, retries, and agent-state checkpoints meaningfully beat what we'd build on top of Cloud Tasks. Decide after a one-week spike. The sponsor-stack narrative win is real but not worth a week of debugging an unfamiliar runtime if it doesn't fit.

### Voice — out for MVP

The original venue-receptionist plan had Gemini Flash voice + Twilio voice. The coordinator pivot doesn't need it: couples and planners interact via chat/web/email. Twilio stays in the stack for **outbound SMS only** (RSVP reminders, day-of nudges). Cutting inbound voice removes the highest-risk hallucination surface — the live-voice quoting failure mode flagged in [README.md](../README.md) §1.3.

### Supplier reply ingestion — SendGrid inbound parse + Gemini Flash extractor

The agent drafts inquiry emails to suppliers, but suppliers reply in prose. Without an ingestion path the quote funnel stalls. SendGrid inbound parse webhook → API matches the reply to a `Booking` via a tracking address (`booking-<id>@inbox.venueflow.ie`) → enqueue a parse job → Gemini Flash extracts a structured quote → write `Quote` row + `AgentDecisionLog` with `parent_decision_id` linking to the original `inquiry_draft`.

### Payments — Stripe Checkout + Stripe Billing

Stripe Checkout for the one-time couple coordinator fee. Stripe Billing for planner subscriptions. No Stripe Connect needed because supplier deposits are tracked-only — couples pay suppliers directly (see [ERD.md](./ERD.md) `SUPPLIER_PAYMENT`).

### Auth — Firebase Auth

Email + social for couples. Email + invite codes for planners onboarded by sales. Row-level security in Postgres keys off the Firebase user id.

### Frontend hosting — Firebase Hosting

Already wired to the build output of the Vite app in [frontend/](../frontend/). Keep it.

### Storage — Cloud Storage

Contract PDFs, exported submission ZIPs, agent-generated artifacts (e.g., run-of-show PDF). Lifecycle rules for old exports.

### Analytics + submission export — BigQuery

`AgentDecisionLog` lives in Postgres for transactional consistency, mirrored to BigQuery via Datastream. The XPRIZE CSV export and the MRR/agent-activity dashboard read from BigQuery, not the OLTP DB. Keeps long-running OLAP queries off the path of live agent writes.

### Secrets — Secret Manager

Stripe, Gemini, SendGrid, Twilio keys. Mounted as env vars at Cloud Run deploy time.

## Agent layer

Every agent is a function: `(input_payload) → (output_payload, AgentDecisionLog row)`. The Worker is the only thing that calls Gemini directly; the API enqueues jobs and reads results. This gives one place to enforce the invocation contract.

### Invocation contract

Every agent call must:
1. Open an `AgentDecisionLog` row with `status='pending'` before the Gemini call.
2. Record `model_id`, `prompt_version`, `agent_id`, `trigger`, `parent_decision_id` (if chained), `input_payload`.
3. Call Gemini, capturing `latency_ms`, `tokens_input`, `tokens_output`, and any `external_api_calls`.
4. Validate the output against the agent's output schema (Zod/Pydantic). Schema failure → `status='error'`, `error_kind='schema_violation'`.
5. Apply guardrails (price ceilings, PII filters, hallucination checks). Block → `status='blocked_by_guardrail'`.
6. On success: write `output_payload`, `rationale_summary`, `confidence_score`; mutate domain entities (`Booking`, `Contract`, etc.) in the same DB transaction. Flip `status='success'`.
7. Enqueue any `follow_up_actions`.

This logic lives in a single `runAgent()` helper. Agents themselves are just `{ name, model, promptTemplate, outputSchema, guardrails, mutate }` configs.

### Agent inventory

| Agent | Model | Trigger | `decision_type` writes | Story |
|---|---|---|---|---|
| `intake_planner` | Pro | Stripe webhook → `Wedding.status=planning` | `timeline_generate`, `budget_alert` (seed) | 1, 2 |
| `venue_matcher` | Pro | Wedding planning starts | `venue_match`, then N `inquiry_draft` | 4 |
| `supplier_matcher` | Pro | Same as above, per category | `supplier_match`, `inquiry_draft` | 4 |
| `quote_extractor` | Flash | SendGrid inbound parse | `quote_draft` (chained to `inquiry_draft`) | 4 |
| `quote_negotiator` | Pro | Quote extracted, over budget | `quote_negotiate` | 4, 9 |
| `contract_reviewer` | Pro | Contract uploaded to GCS | `contract_review` | 5 |
| `budget_monitor` | Flash | `Quote.status='accepted'` or `SupplierPayment` insert | `budget_alert` | 9 |
| `rsvp_follower` | Flash | Cloud Scheduler daily | `rsvp_followup` | 10 |
| `seating_assigner` | Pro | Couple action ("draft seating") | `seating_assign` | 11 |
| `runofshow_updater` | Pro | `Booking`/`Quote` change near wedding date | `timeline_update`, `runofshow_update` | 12 |
| `reschedule_handler` | Pro | Supplier cancellation event | `reschedule` | cross-cutting |
| `post_event_followup` | Flash | Cloud Scheduler post-wedding | `post_event_review_request` | P2 |

Gemini 3 Pro for anything that reasons over structured context (matching, review, negotiation, planning). Gemini 3 Flash for high-volume drafting and extraction where Pro is overkill.

## Key flows

### Couple intake → initial sourcing

```mermaid
sequenceDiagram
  participant C as Couple
  participant FE as Frontend
  participant API
  participant Stripe
  participant Q as Cloud Tasks
  participant W as Worker
  participant Gem as Gemini Pro
  participant PG as Postgres
  participant SG as SendGrid

  C->>FE: Submit wedding profile
  FE->>API: POST /weddings (intake form)
  API->>PG: Insert User, Wedding (status=intake)
  API->>FE: Stripe Checkout session
  C->>Stripe: Pay coordinator fee
  Stripe->>API: webhook payment.succeeded
  API->>PG: Insert Payment, Wedding.status=planning
  API->>Q: enqueue intake_sourcing(wedding_id)
  Q->>W: deliver job
  W->>Gem: intake_planner(wedding_id)
  Gem-->>W: timeline + budget plan
  W->>PG: Insert TimelineItem, BudgetLine, AgentDecisionLog
  W->>Gem: venue_matcher + supplier_matcher (parallel)
  Gem-->>W: ranked shortlists
  W->>PG: Insert Booking (status=shortlisted), AgentDecisionLog
  W->>Gem: inquiry_draft per shortlisted Booking
  Gem-->>W: draft messages
  W->>PG: AgentDecisionLog (parent=supplier_match)
  W->>SG: send inquiry emails (after couple approval)
  W->>SG: notify couple "your plan is ready"
```

### Contract upload → review

```mermaid
sequenceDiagram
  participant U as Couple/Planner
  participant FE as Frontend
  participant API
  participant GCS as Cloud Storage
  participant Q as Cloud Tasks
  participant W as Worker
  participant Gem as Gemini Pro
  participant PG as Postgres

  U->>FE: Upload supplier contract PDF
  FE->>API: POST /bookings/{id}/contract
  API->>GCS: store PDF
  API->>PG: Insert Contract (no risk_flags yet)
  API->>Q: enqueue contract_review(contract_id)
  Q->>W: deliver job
  W->>GCS: fetch PDF, extract text
  W->>Gem: contract_reviewer(text, booking context)
  Gem-->>W: risk_flags + rationale
  W->>PG: Update Contract.risk_flags, reviewed_by_agent_id
  W->>PG: Insert AgentDecisionLog (decision_type=contract_review)
  W->>API: notify couple (signing gated on ack)
```

### Supplier reply → quote extraction

```mermaid
sequenceDiagram
  participant Sup as Supplier
  participant SG as SendGrid
  participant API
  participant Q as Cloud Tasks
  participant W as Worker
  participant Gem as Gemini Flash
  participant PG as Postgres

  Sup->>SG: reply to booking-<id>@inbox.venueflow.ie
  SG->>API: inbound parse webhook
  API->>PG: lookup Booking by tracking address
  API->>Q: enqueue quote_extract(booking_id, email_body)
  Q->>W: deliver job
  W->>Gem: quote_extractor(email_body, booking context)
  Gem-->>W: structured Quote {line_items, total, currency}
  W->>PG: Insert Quote (status=pending), Booking.status=quoted
  W->>PG: Insert AgentDecisionLog (parent=inquiry_draft)
  alt over budget
    W->>Q: enqueue quote_negotiate(quote_id)
  end
```

RSVP follow-ups follow the same shape but triggered by Cloud Scheduler instead of a webhook: scheduler hits an API endpoint that lists weddings needing nudges and enqueues one job per guest cohort.

## Deferred / out of MVP

- **Stripe Connect / passthrough payments** — couples pay suppliers directly per chosen flow.
- **Inbound voice (Twilio Voice + Gemini live voice)** — coordinator product doesn't need it; cuts the biggest hallucination surface.
- **Multi-tenant planner branding (white-label)** — planner B2B story is "use the agent to scale your practice," not "rebrand it." Defer.
- **Mobile apps** — web responsive only.
- **Real-time collaboration on planning docs** — couples + planners can both edit, but no live cursors / OT. Optimistic last-writer-wins is fine.
- **Vendor marketplace / supplier accounts** — suppliers are sourced and contacted, not customers. No supplier login in MVP.

## Open questions

- **Antigravity vs. hand-rolled orchestrator.** Resolve via week-1 spike. The invocation contract above is portable either way.
- **BigQuery mirror cadence.** Datastream gives sub-minute lag; whether that's needed for the live dashboard or whether a 5-minute scheduled export suffices is unclear until traffic exists.
- **Guardrails authoring.** Per-agent guardrail configs (price ceilings, PII redaction, "don't promise availability without DB lookup") need an owner. Probably the prompt-engineering surface area expands fastest in weeks 4–8.
