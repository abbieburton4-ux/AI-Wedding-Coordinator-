# VenueFlow — Architecture (MVP, AI Wedding Coordinator)

## Replit real-access configuration

The Replit production entrypoint is `app.production:app`: FastAPI serves the built
React SPA and API together, using Firebase access checks and managed PostgreSQL.
Demo/mock flags are disabled and the disposable SQLite demo database is separate.
Startup runs `alembic upgrade head` on that environment's database, as every
non-development deployment does (rule 6), and refuses a schema Alembic didn't build.

With `DIRECT_AGENT_EXECUTION=True`, intake/replan/matching/extraction dispatch
awaits the existing decorated agent in an independent session within the HTTP
request. Provider failures are explicit HTTP errors with recorded decision logs;
guardrail blocks are returned as blocks, not fake queued successes. The profile
is saved before initial planning, so failed intake remains recoverable via the
existing replan flow. No external queue or worker HTTP secret is needed for this
configuration. It is request-bound execution, not a durable asynchronous queue.
The Docker emulator path remains development-only. See `replit.md`.

> [!NOTE]
> **Implementation Status**:
> - **Current Implementation**: A Vite + React frontend communicating with a **FastAPI backend** over REST endpoints. Database schemas are managed using **SQLModel** with SQLite for local development, and Postgres ready. Asynchronous agent task execution uses a Google Cloud Tasks structure, with a local Tasks Emulator and direct background invocation fallback for development.
> - **Planned Infrastructure**: Deployment to GCP Cloud Run, Cloud Tasks, Cloud Scheduler, Cloud SQL Postgres, SendGrid parse webhook, Twilio SMS, and Firebase Auth. Some third-party integrations (like full Firebase Auth, Twilio SMS sending, SendGrid parse webhooks) are mocked/simulated in the development environment.

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

> **Today (PD-008 follow-up 2):** the webhook matches the booking but doesn't enqueue the parse job, because no one is there to check the text before it goes to Gemini, and it stores nothing. The couple pasted the reply on the Vendors screen, checked the cleaned text and clicked to send; since PD-012 that screen shows only the couple's own vendor sections, and since B62 each vendor the couple add has its own "Paste a reply" (`POST /weddings/{id}/vendors/{vendor_id}/reply`, same check before sending). Holding inbound emails for review would need somewhere to keep them (B50).

### Payments — removed

The app takes no payments (PD-003). The Stripe Checkout and Billing code, the payment gate and the mock checkout were removed. Supplier deposits are still tracked only: couples pay suppliers directly (`SUPPLIER_PAYMENT`). The diagram and flows below still show the old Stripe path; they're historical.

### Auth — Firebase Auth

Personal sign-in through the couple's own Firebase project (PD-002): Google, with email and password as a fallback. A password account is let in only once its email is confirmed; the person asks Firebase for the confirmation email with their own click (`sendEmailVerification`), and the app never sends it. There's no self sign-up. A new account is created only for a verified email on the wedding's access list (`wedding_members`), or in `ACCESS_BOOTSTRAP_EMAILS`, the couple's own emails. Those are the only ones that may create the wedding, and both become owners. Access levels (viewer, editor, owner) are enforced in the API (`app/api/v1/access.py`), not in Postgres. Only owners can read or change the access list (`endpoints/members.py`, the **Who has access** screen). They add people as editor or viewer. Owner rows can't be removed or changed through the API or the screen, not even your own; the team changes them with `manage_access.py` on the couple's request (PD-002 note, 2026-11-05). Adding someone sends nothing. Worker `/tasks/*` routes need `X-Internal-Token: INTERNAL_TASKS_SECRET`, and the inbound-email webhook needs `?token=INBOUND_EMAIL_SECRET`. Outside `DEVELOPMENT_MODE`, both refuse every call when their secret isn't set. The SaaS-era planner sign-in and roles were removed (PD-003).

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
2. Record `model_id`, `prompt_version`, `agent_id`, `trigger`, `parent_decision_id` (if chained), `input_payload` (with the same personal details removed).
3. Call Gemini only through `app/agents/privacy.send_prompt` (PD-008). It removes the names, emails and phone numbers of the wedding's guests and access list and of the contact people saved on the couple's own vendors (B62), guests' dietary notes (other than plain categories), and anything shaped like an email or phone number, and refuses to send if any known detail is left. Counts and categories ("12 vegetarian") still go. Names the app doesn't hold, such as a new name in a vendor's email, can't be reliably spotted. Prompts are built with `ensure_ascii=False`, and a `\u` escape in a prompt is refused, so accented names can't slip past. `verify_agents.py` fails if any other file uses the Gemini client.
   **Check before send (PD-008 follow-up 2).** Because unknown names can't be spotted, nothing is sent until the person has seen the cleaned text and clicked to send. Every AI route (`/concierge`, `/inquiries/{id}/quote`, `/vendors/{id}/reply`, `/match`, `/suppliers`, `/replan`, `/budget/suggest-split`) first calls the agent with `preview_only=True`: it runs up to its model call in its own session, `send_prompt` raises `PromptNeedsReview` instead of sending, every change is rolled back, no log row is written, and the route returns `{"needs_review": true, "preview": <exact text>}`. The person's click repeats the request with `approved_prompt` set to that text. The route goes ahead only if the agent's cleaned prompt is exactly that text, and `send_prompt` checks again before the call (`PromptNotApproved` otherwise, logged as an error; nothing sent). A run with no model call (the planner's skips) needs no check. The approved text travels in the task payload to the worker. Wedding creation queues the planner only when it makes no model call; otherwise the dashboard offers "Update my plan". The inbound-email webhook has no one to check the text, so it no longer runs the quote extractor (since PD-012 no button starts `/match` or `/suppliers`, and `/inquiries/{id}/quote` has no paste box; those routes stay, unused. Pasting now goes through the couple's own vendors, B62). Queries that feed a prompt are ordered and the privacy patterns sorted, so the same data gives the same text in any process; if the data does change between the check and the click (a task ticked, a worker running later), nothing is sent and the person sees the new text, or the run is logged as `PromptNotApproved`. Each agent run may make one model call, since a second, different text wouldn't match the approval. The server enforces "exactly this text"; the click itself is the browser's. The app's fixed instructions are checked for whole names, contacts and dietary notes, not single name parts, which are often ordinary words there ("Mark", "Irish").

   **Aurelia is off (PD-010).** `/concierge` and `/voice/token` refuse every call (403, "Aurelia, the assistant, is turned off for this wedding.") after the access check and before anything reaches Gemini or ElevenLabs, unless the backend setting `ASSISTANT_ENABLED` is `True`; it defaults to `False`. The screens hide the assistant unless `AURELIA_ENABLED` in `frontend/src/app/wedding/features.ts` is true, so bringing it back means turning on both. Past concierge log rows are kept.
   Capture `latency_ms`, `tokens_input`, `tokens_output`, and any `external_api_calls`.
4. Validate the output against the agent's output schema (Zod/Pydantic). Schema failure → `status='error'`, `error_kind='schema_violation'`.
5. Apply guardrails (price ceilings, PII filters, hallucination checks). Block → `status='blocked_by_guardrail'`.
6. On success: write `output_payload`, `rationale_summary`, `confidence_score`; mutate domain entities (`Booking`, `Contract`, etc.) in the same DB transaction. Flip `status='success'`.
7. Enqueue any `follow_up_actions`.

This logic lives in a single `runAgent()` helper. Agents themselves are just `{ name, model, promptTemplate, outputSchema, guardrails, mutate }` configs.

### Agent inventory

| Agent | Model | Trigger | `decision_type` writes | Story |
|---|---|---|---|---|
| `intake_planner` | Pro | Stripe webhook → `Wedding.status=planning` | `intake_plan` (draft budget split in the log; the timeline was replaced by the checklist, PD-007. Skips the model, and moves the wedding to planning, when the budget is blank or not in euros, PD-009) | 1, 2 |
| `venue_matcher` | Pro | Wedding planning starts | `venue_match`, then N `inquiry_draft` | 4 |
| `supplier_matcher` | Pro | Same as above, per category | `supplier_match`, `inquiry_draft` | 4 |
| `quote_extractor` | Flash | A reply the couple paste and approve (the SendGrid inbound parse no longer runs it, PD-008). Since B62 the Vendors screen runs `run_vendor_reply_reader` on one of the couple's own vendors: only the pasted text is sent, the result is saved as a `CoupleVendorQuote` in integer cents with no currency guessed, and the vendor's status and the budget are never changed. Blocks (saves nothing) on a total that's negative, unreadable or over $1,000,000 (`implausible_total`) or a reply with neither a price nor availability (`nothing_found`) | `quote_draft` (chained to `inquiry_draft` for catalogue bookings) | 4 |
| `quote_negotiator` | Pro | Quote extracted, over budget | `quote_negotiate` | 4, 9 |
| `contract_reviewer` | Pro | Contract uploaded to GCS | `contract_review` | 5 |
| `budget_monitor` | Flash | `Quote.status='accepted'` or `SupplierPayment` insert. Today the only `budget_alert` rows are written by `quote_extractor` on a catalogue booking: an available quote in USD over the `planned_cents` of the couple's budget category with the same name (B44, `budget_compare.compare_quote`); `input_payload` holds `planned_cents` and `quote_cents`. The extractor no longer writes any budget figure (the old `BudgetLine.spent_amount` roll-up is gone) | `budget_alert` | 9 |
| `budget_splitter` | Flash | Couple action ("Suggest a starting split", needs a total) | `budget_split`. Returns percentage shares only; amounts are worked out in cents from the couple's total. Saves nothing; the couple apply it themselves. Blocks on unknown or duplicate categories (compared ignoring case, spaces and underscores), bad shares, shares not adding to 100%, or amounts not adding to the total. Blanks any reason that states a price. Applying needs the lines to add up to the total | PD-004 |
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
  Gem-->>W: budget plan
  W->>PG: Update Wedding.status, AgentDecisionLog (draft budget split stays in the log, B42)
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
