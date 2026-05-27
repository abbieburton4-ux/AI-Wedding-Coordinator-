# VenueFlow

> An AI Wedding Coordinator for couples and independent planners.
> Built on Gemini. Submitted to the Build with Gemini XPRIZE (deadline: **17 August 2026**).

[**Live marketing site**](https://alanmaizon.github.io/VenueFlow/) · [Pilot app (Streamlit)](./streamlit_mock/) · [Strategic memo](docs/strategic-memo.md) · [Runway plan](docs/runway.md)

---

## 1 · The Pitch

The average Irish wedding costs €33,000 and takes 250+ planning hours. A human coordinator charges €4,000–€8,500 — and **80% of couples can't afford one.** VenueFlow puts a wedding coordinator in every couple's pocket for **€299–€999 one-time**, and gives independent planners a way to clone themselves and serve 5× more clients for **€199–€499/mo.**

The product is an autonomous Gemini agent layer that does the work of a planner: vendor sourcing, budget allocation, timeline drafting, quote extraction, contract review, RSVP/seating, day-of run-of-show.

## 2 · The Problem

- Couples spend ~250 hours per wedding on coordination work that is **structurally repeatable** (vendor sourcing, quote chasing, budget tracking).
- The €4–8K coordinator price excludes most couples — yet the work still has to happen, so it falls on a partner or parent who is doing it as an unpaid second job.
- Independent wedding planners are capacity-bound. Most can handle 8–12 weddings/year. There is no "leverage layer" between the spreadsheet and a full-time assistant.

## 3 · The Solution — Four Agents That Do The Work

| Agent | Decision | Model |
|---|---|---|
| **intake_planner** | Validates budget realism, seeds budget allocations + timeline | Gemini 2.5 Pro |
| **venue_matcher** | Ranks venues by region, capacity, style, budget; drafts inquiry email | Gemini 2.5 Pro |
| **supplier_matcher** | Same for photographers, florists, music, catering | Gemini 2.5 Pro |
| **quote_extractor** | Parses supplier email replies → structured quote + budget alert | Gemini 2.5 Flash |

Each decision is logged with full input/output payload, latency, tokens, confidence score, and `parent_decision_id` linking — exportable as CSV. See [docs/agent-decision-log.md](docs/agent-decision-log.md).

## 4 · How It Works (Workflow)

```
Couple intake → intake_planner (budget guardrail + plan seed)
              → venue_matcher (3 shortlisted venues + inquiry drafts)
              → supplier_matcher × N categories (photo, florals, music, catering)
              → couple/planner sends inquiries
              → quote_extractor (parses replies → structured quotes)
              → budget_monitor (chained alert if over-allocation)
              → couple/planner books; contracts + payments tracked
```

Every step writes an `AgentDecisionLog` row. Every log row is reviewable in the UI and exportable as a CSV bundle for submission.

## 5 · The Tech

- **AI:** Gemini 2.5 Pro (reasoning) + Gemini 2.5 Flash (extraction), routed via a `model_for(agent_name)` resolver
- **Backend:** Python + SQLite (pilot) → Postgres (production-ready, migration triggered by load)
- **Frontend (pilot):** Streamlit with role-based session (couple vs. planner)
- **Frontend (marketing):** Vite + React 18 + Tailwind v4
- **Payments:** Stripe Checkout (planner subscriptions) + Stripe Billing
- **Planned production:** Cloud Run · Cloud Tasks · Cloud SQL · SendGrid Inbound Parse · Firebase Auth — see [docs/architecture.md](docs/architecture.md)

## 6 · Status

| Layer | Built | Planned |
|---|---|---|
| Agent layer (4 agents, structured outputs, guardrails, decision logs) | ✅ | timeline_builder by Day 45; contract_reviewer post-submission |
| Hallucination + budget guardrails | ✅ | More categories of guardrail as edge cases land |
| SQLite + WAL + idempotency | ✅ | Postgres migration if pilot load triggers it |
| Stripe Checkout (test mode) | 🔄 W2 | Live charges by Day 14 |
| Auth (role-based session) | ✅ | Firebase Auth before public couple-direct |
| Marketing site | ✅ | Pricing reconciled with coordinator-fee positioning |
| Cloud Run / Cloud Tasks / SendGrid / Twilio | ⛔ | Post-Day-30 if pilot demand warrants |

## 7 · Run It Locally

```bash
# Pilot app (the AI wedding coordinator)
cd streamlit_mock
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
export GEMINI_API_KEY=...
streamlit run app.py

# Marketing site
cd frontend
npm i
npm run dev
```

See [CONTRIBUTING.md](CONTRIBUTING.md) for the full local dev guide.

## 8 · The Team

- **Alan Maizon** — founder/product. Distribution, planner outreach, pilot operations, narrative.
- **Atharva** — ML engineer. Agent layer, Gemini integration, guardrails, decision logs.

## 9 · Documentation

| File | What it is |
|---|---|
| [docs/strategic-memo.md](docs/strategic-memo.md) | Why we pivoted to "AI Wedding Coordinator" (Option A) and why Professional Services Access is the category |
| [docs/architecture.md](docs/architecture.md) | Service map, agent invocation contract, key flows. Implementation vs. planned target. |
| [docs/ERD.md](docs/ERD.md) | Data model (Postgres-shaped; SQLite is the pilot implementation) |
| [docs/agent-decision-log.md](docs/agent-decision-log.md) | The submission-critical artifact: schema + CSV export spec |
| [docs/user-stories.md](docs/user-stories.md) | P0/P1/P2 MVP scope |
| [docs/runway.md](docs/runway.md) | 12-week day-by-day plan to the Aug 17 submission |
| [CONTRIBUTING.md](CONTRIBUTING.md) | Local dev + how to add an agent + commit conventions |
| [runway-tracker.xlsx](runway-tracker.xlsx) | Live execution tracker (milestones, weekly plan, outreach, risks) |

## 10 · Submission Status — Build with Gemini XPRIZE

- **Category:** Professional Services Access
- **Submission deadline:** 17 Aug 2026 · **Finalists pitch:** 25 Sep 2026, Moonshot Gathering, LA
- **Required artifacts (status):**
  - [ ] GitHub repo polished
  - [ ] 3-min video demo
  - [ ] 500–1000 word narrative
  - [ ] Stripe dashboard / bank statement (revenue proof)
  - [ ] Marketing spend disclosure
  - [ ] Agent execution logs (CSV)
  - [ ] Named customer contact info (reference-consented)
