# VenueFlow — 82-Day Runway to Aug 17 Submission

> **Note (2026-11-05):** the first prototype in `streamlit_mock/` has been deleted from the repo (PD-005). File references below point to code that no longer exists; old copies remain in git history.

**Anchored:** 2026-05-27 (Wed). **Submission deadline:** 2026-08-17 (Mon). **Judging announcement:** 2026-09-25.

> **Day numbering note.** Brief uses "Day 87 = Aug 17"; calendar math is 82 days. This doc anchors on **calendar dates** (immovable) with day-from-start in parens where helpful. If you see "Day N", read it as the named milestone, not a date.

This is a **decision artifact**, not a vision doc. Every section ends in a thing to do or a thing to measure. Update inline when reality diverges.

---

## 0. Locked Decisions (Sprint 0)

These are not up for re-debate until the Day 30 retro. If you want to revisit, write the reason in the retro file, not in this doc.

| # | Decision | Locked choice | Trigger to revisit |
|---|---|---|---|
| 1 | Pilot deployment | **Streamlit Cloud** by end of Week 1. Local + ngrok is acceptable for early discovery calls *only* (Week 2 Sat demos). | If Streamlit Cloud's free tier rate-limits Gemini calls or the auth model doesn't allow per-planner sessions, fall back to Cloud Run (~1 day work). |
| 2 | Audience sequence | **Planner-first.** Couples are batch inputs the planner manages. Couple-direct onboarding opens at Day 60 (Jul 26) at earliest, only if planner pilots are stable. | If by Day 21 no planner converts, pivot to direct-to-couple with a Google Ad spend test. |
| 3 | Revenue model | **€299/mo per planner**, billed monthly, 50% off ("Pilot Founder rate") for first 3 months. €149 effective. Couple-direct (post-Day 60) priced at €299 one-time per wedding. | If 3+ planners refuse the recurring model in onboarding calls, switch to €99/couple commission with €0 base. |
| 4 | Database | **SQLite + WAL** for pilot. Postgres migration is contingency, not roadmap. | Trigger: any "database is locked" error logged in production, OR planner #4 onboards. Then 3-day Postgres-in-container migration. |
| 5 | Agent inventory at Day 30 | **Four agents**: intake_planner, venue_matcher, supplier_matcher, quote_extractor. **timeline_builder** ships by Day 45. contract_reviewer + vendor_coordinator are post-submission. | If a pilot planner says "I won't use it without contract review" — promote contract_reviewer to Sprint 3 scope. |

**Founder agreement to ratify in the Day 1 standup.** Initial both names in commit message of this file.

---

## 1. Week-by-Week Plan

Twelve weeks. Each week has: ship list, dependencies, blockers, decision gate. Read this on Monday morning; check it on Friday afternoon.

### Week 1 — May 27 (Wed) → May 31 (Sun) | Sprint 0 partial
**Theme:** Codebase locked. Outreach pipeline armed. URL alive.

| Owner | Ship | Hours |
|---|---|---|
| Atharva | Commit `streamlit_mock/` clean (Python + README + requirements only; verify `.gitignore` excludes `.venv/`, `*.db`, `__pycache__/`). Tag `v0.1-pilot-ready`. Write `CONTRIBUTING.md`. Wire `parent_decision_id` chain in `quote_extractor` (the one audit-follow-up from prior turn). | 8 |
| Alan | Build the cold-outreach pipeline. Compile a 50-planner target list from public sources (Instagram, One Fab Day, Bridebook, Wedding Wire Ireland, Google Maps "wedding planner Dublin/Cork/Galway"). Draft 3 outreach templates (cold email, LinkedIn DM, Instagram DM) — each ≤4 sentences, personalized hook + 1 link. Record a 90-sec Loom explaining the product without jargon. Set up a tracking spreadsheet (sent / replied / call booked / signed / paid). | 8 |
| Both | Reconcile [docs/architecture.md](architecture.md) — IMPLEMENTED vs PLANNED banner already added; cross-check that no other doc claims "Postgres" or "Cloud Run" as current. | 1 |

**Dependency chain:** Target list → templates → Loom asset → ready to fire Wave 1 on Mon Jun 1. Codebase work runs parallel.
**Blocker:** List research takes longer than estimated (planner contact info is fragmented across Instagram bios and directory sites). Action: Alan caps research at 8 hours; whatever list exists by Friday is the Wave 1 cohort.
**Gate (Sun EOD):** ☐ git tag pushed ☐ 50-planner list with contact handle + 1 personal hook per row ☐ 90-sec Loom recorded ☐ 3 outreach templates drafted ☐ Streamlit Cloud account provisioned.

---

### Week 2 — Jun 1 (Mon) → Jun 7 (Sun) | Sprint 0 close + Sprint 1 ramp
**Theme:** Deployed. First planner walkthrough. Stripe Checkout stub.

| Owner | Ship | Hours |
|---|---|---|
| Atharva | Deploy `streamlit_mock` to Streamlit Cloud at a stable URL. Add session-based role selector (planner vs couple) with at least URL-param gating. **Build Stripe Checkout integration** — even just a test-mode €149 charge that writes a real `PAYMENT` row. This is the "revenue" critical path. | 22 |
| Alan | Send Wave 1: 25 cold outreaches Mon, 25 more Wed (mix across email/LinkedIn/Instagram to A/B-test channel and message). Reply to any inbound within 2 hours. Goal by Sun: ≥3 discovery calls booked, ≥8% reply rate. Sat: run whichever calls landed — record (with consent) 10 min of each for usability feedback later. | 14 |
| Both | Day 6 retro: based on first discovery calls + reply-rate data, decide #1 thing to fix in Week 3 (could be product, could be the outreach message). Write it down. | 1 |

**Dependency chain:** Streamlit deploy → discovery calls → first usability signal → Week 3 priorities.
**Blocker:** Streamlit Cloud blocks Gemini outbound or session state doesn't persist. Action: switch to Cloud Run by Wed EOD (Atharva must have a Dockerfile ready as a contingency by Tue).
**Gate (Sun EOD):** ☐ public URL live ☐ Stripe Checkout produces a real test charge ☐ ≥50 outreaches sent ☐ ≥3 discovery calls booked.

**SMART milestone — Day 7 (Jun 2):**
- ≥25 cold outreaches sent (Wave 1 partial)
- 1 deploy URL accessible from non-dev machine
- 1 Stripe test transaction in dashboard
- ≥1 discovery call booked from cold outreach

---

### Week 3 — Jun 8 (Mon) → Jun 14 (Sun) | Sprint 1: Planner #1 live
**Theme:** First planner runs a real couple end-to-end.

| Owner | Ship | Hours |
|---|---|---|
| Atharva | Bug fixes from Wave 1 discovery-call feedback (top 2 only — resist scope creep). Add Gemini API spend dashboard (daily €). Wire `external_api_calls` payload audit so every log row is complete. Attend the planner #1 onboarding call silently. | 28 |
| Alan | Send Wave 2 (25–50 contacts, with whatever message tweaks came from Week 2). Convert the highest-intent Wave-1 calls to paid pilots — target 2 paid, 1 deferred. Onboard planner #1 in 30-min Zoom: walk through intake, run a real couple, export logs. Capture screen recording (asset for video later). Set up daily WhatsApp standup channel with the pilot planners. | 26 |

**Dependency chain:** Bug fixes → planner #1 onboarding → first real-couple workflow. If bugs break onboarding, Atharva war-rooms by Friday.
**Blocker:** No planner converts on the discovery calls. Action: Alan reviews call notes by Friday EOD — is the friction price, product, or pitch? Rewrite the offer or script before Wave 3.
**Gate (Sun EOD):** ☐ 2 planners paid (even pilot rate) ☐ 1 real couple has submitted an intake ☐ Gemini spend tracked daily ☐ no NULL columns in `agent_decision_logs` from new runs.

**SMART milestone — Day 14 (Jun 9):**
- ≥1 planner signed Stripe subscription (€149/mo effective) — *softer than the brief's "2 by Day 14"; cold outreach math doesn't support 2 paid that fast*
- ≥75 cold outreaches sent cumulatively, ≥8% reply rate
- ≥3 discovery calls completed
- 1 real couple submission processed by the agent layer
- ≥15 decision log rows from live (non-test) usage
- 0 "database is locked" errors in production logs

---

### Week 4 — Jun 15 (Mon) → Jun 21 (Sun) | Sprint 1 close
**Theme:** Couples flow through. Metrics dashboard tells the truth.

| Owner | Ship | Hours |
|---|---|---|
| Atharva | Stress-test: simulate 3 planners × 2 couples concurrent. Confirm WAL mode + 30s timeout hold. **If lock errors appear, start Postgres migration Mon Jun 22.** Add a "Workflow Status" view per couple (intake submitted, matcher run, quotes received, vendor booked). | 28 |
| Alan | Daily standup with planners 1–2. Push: "Any other couples this week?" Goal by Sun: 5 couples total in workflow. Begin drafting the Day-30 narrative outline (problem statement + proof points stub). | 22 |

**Dependency chain:** Stress test → confidence to onboard planner #3. Don't onboard #3 until you've proven 2 work concurrently.
**Blocker:** Stress test fails. Action: switch to Postgres immediately; this is the migration trigger from Section 0 Row 4.
**Gate (Sun EOD):** ☐ 5+ couples in workflow ☐ stress test passes 3-concurrent ☐ daily Gemini spend <€10.

**SMART milestone — Day 21 (Jun 16, mid-week):**
- 2 paying planners, both active in last 72h
- 5+ couples through full intake → match → quote chain
- ≥50 decision log rows, ≥80% with non-null confidence_score
- ≥€300 collected (pilot rate × 2 × half-month)
- Avg agent decision latency <8s (P95 <15s)
- **Decision gate:** 🟢/🟡/🔴 per Section 3 of the brief. Write the call in the runway-retros.md file.

---

### Week 5 — Jun 22 (Mon) → Jun 28 (Sun) | Sprint 2 launch + Day 30 hit
**Theme:** Planner #3 onboards. Case study material captured. Day 30 lock.

| Owner | Ship | Hours |
|---|---|---|
| Atharva | Ship `timeline_builder` agent (template-driven, not full LLM reasoning — uses ceremony_type to populate a milestone tree, then LLM only fills descriptions). Add CSV export "narrative mode" — pretty-printed for judges, not raw dump. | 30 |
| Alan | Onboard planner #3. Record 15-min audio interview with planner #1: "What used to take 8 hours that now takes how long?" Lock the Day 30 metrics. Email each planner: "On track for €149 charge on first of month?" — confirm no surprise refunds incoming. | 26 |

**Blocker:** Planner #1 churns or asks to pause. Action: Alan calls within 24h to understand why (not to recover them — to learn). They're your case-study source; protect the relationship even if they leave the pilot.
**Gate (Fri Jun 26 = Day 30):** ☐ 3 paying planners ☐ 15+ couples ☐ ≥€600 MRR run rate (€450 collected this month) ☐ 100+ decision logs ☐ 1 audio interview captured ☐ narrative draft outline exists.

**SMART milestone — Day 30 (Jun 26, Fri):**
- 3 paying planners on active Stripe subscription
- 15+ couples through workflow (≥10 with quote_extracted at minimum)
- ≥€450 actually collected on Stripe (€600 MRR run rate)
- 100+ AgentDecisionLog rows, full chain traceable from intake_planner → quote_extract
- 1 planner audio testimonial captured (transcript ok if not video yet)
- Narrative outline file exists at `docs/submission/narrative-v1.md`
- **Sprint 2 gate decision** logged in retros file.

---

### Week 6 — Jun 29 (Mon) → Jul 5 (Sun) | Sprint 3 start: scale + harden
**Theme:** Expand from 3 → 5 planners. Stop building new features.

| Owner | Ship | Hours |
|---|---|---|
| Atharva | **Feature freeze on new agents.** Only ships allowed: bug fixes, prompt iteration (track via `prompt_version` hash), log quality improvements. Run the Day 25 hallucination war-room playbook proactively: pick 20 random log rows, audit for plausibility. | 24 |
| Alan | Outreach #2 wave: contact four planners from the target list — frame as "early access, Founder rate ends Jul 15." Push for 2 more sign-ups by EOW (target: 5 planners total). | 28 |

**Blocker:** Prompt iteration breaks an existing planner's workflow. Action: keep last-known-good prompt hash in `prompt_versions.md` and revert if log confidence drops <0.7 across the cohort.
**Gate (Sun EOD):** ☐ 5 paying planners (target) ☐ 0 reverts in production prompts this week ☐ €700+ MRR.

---

### Week 7 — Jul 6 (Mon) → Jul 12 (Sun) | Sprint 3 mid: video shoot
**Theme:** Demo video filmed. Anchor case study filmed.

| Owner | Ship | Hours |
|---|---|---|
| Atharva | Polish the "judge-facing demo path": one wedding, one planner, run the full workflow start to finish in a clean DB so the screen-capture is pristine. Generate a sample log bundle (10 representative chains) in `docs/sample-logs/`. | 18 |
| Alan | **Film the 3-min demo video** (probably 2 takes + edit ~6 hrs). **Film the case-study planner** if they agreed (in-person Dublin if possible, otherwise Zoom). Target: Jul 12 = raw footage in hand. | 30 |

**Dependency chain:** Clean demo path → confident video. Don't film with a buggy build.
**Blocker:** Case study planner ghosts. Action: pivot to planner #2 or #3 testimonial; lower bar to written quote with permission to use name.
**Gate (Sun EOD):** ☐ 3-min demo footage shot ☐ ≥1 planner on-camera or named-quote in hand.

---

### Week 8 — Jul 13 (Mon) → Jul 19 (Sun) | Mid-pilot stretch
**Theme:** Push to 7 planners. Tighten the narrative.

| Owner | Ship | Hours |
|---|---|---|
| Atharva | Performance pass: query analysis, prompt cost optimization (move what you can to Flash). Begin a 1-pager "What we built (real) vs what we plan (post-submission)" for the GitHub README. | 16 |
| Alan | Outreach #3 wave + push to upgrade existing planners from "pilot rate" to "founder rate." Begin drafting Day 60 narrative: 5 paragraphs per the brief structure. Anchor on the case-study planner's quote. | 26 |

**Blocker:** Founder energy. This is week 8 of 12 — burnout zone. **Action: each founder takes Sat-Sun fully off this week (no Slack/no code).** Schedule it in calendar.
**Gate (Sun EOD):** ☐ 6+ planners ☐ €1,000+ MRR ☐ narrative-v2.md exists.

---

### Week 9 — Jul 20 (Mon) → Jul 26 (Sun) | Day 60 hit
**Theme:** Narrative locked. Video edited.

| Owner | Ship | Hours |
|---|---|---|
| Atharva | Edit demo video (or hand to a freelance editor — budget €200 for this, it's worth it; founders editing video for 8 hours is a bad trade). Lock the GitHub README and "what's real" doc. Run a fresh log export — verify PII redaction holds. | 20 |
| Alan | Finalize the case study (1-page MD). Get the Stripe screenshot prepared (mask card data, show MRR + transactions). Email each planner the consent form for "submission reference contact." | 22 |

**Gate (Sun Jul 26 = Day 60):** see SMART milestone below.

**SMART milestone — Day 60 (Jul 26, Sun):**
- 5–10 paying planners (target 7)
- 20–30 couples through workflow (target 25)
- ≥€1,500 MRR (collected, on Stripe dashboard)
- 1 anchor case study published (`docs/submission/case-study-{name}.md`)
- Demo video edited to 3:00 with captions
- 1 planner has signed reference-contact consent
- Narrative v2 complete, ≥500 words
- **Decision gate:** 🟢 = proceed to submission polish. 🟡 = run an "is this enough" check with your strongest pilot planner + 1 unbiased outsider (peer founder, a judge from a prior hackathon). 🔴 = consider whether the next 22 days are best spent improving narrative or finding a different angle.

---

### Week 10 — Jul 27 (Mon) → Aug 2 (Sun) | Sprint 3 polish
**Theme:** Submission Kit assembly begins.

| Owner | Ship | Hours |
|---|---|---|
| Atharva | Clean git history if needed (squash WIP commits on feature branches; do NOT rewrite `main` if anyone else has pulled). Add `docs/sample-logs/README.md` explaining each sample chain. Run a security pass: secret scan, dependency audit. | 18 |
| Alan | Build the Submission Kit folder at `docs/submission/`: `narrative.md`, `case-study.md`, `customer-refs.md` (with permissions), placeholder for video and Stripe screenshot. Begin Devpost account setup + read the submission requirements line by line. | 18 |

**Blocker:** Devpost requires a field you didn't plan for (common: "video link" must be unlisted YouTube or Vimeo, not a file upload). Action: read Devpost requirements **this week**, not Aug 14.
**Gate (Sun EOD):** ☐ Submission Kit skeleton exists with every required field stubbed ☐ Devpost account set up ☐ planner reference contacts confirmed.

---

### Week 11 — Aug 3 (Mon) → Aug 9 (Sun) | Buffer week
**Theme:** Slack week. Anything that's late lands here.

| Owner | Ship | Hours |
|---|---|---|
| Atharva | Whatever spilled from Weeks 6–10. If nothing spilled: write the 1-pager "Why Gemini specifically" — judges in the Build with Gemini track will read this. | 14 |
| Alan | Whatever spilled. Final narrative pass — read it out loud, time it, cut to ≤1000 words. Run it past your strongest pilot planner for a "would you have signed up reading this?" check. | 16 |

**Critical:** if you're behind by Wed of this week, escalate to a founder call: cut something or move the submission lower-priority. **Don't crunch into Week 12.**
**Gate (Sun EOD):** ☐ All assets ≥90% complete ☐ no critical bugs in production ☐ Stripe export ready.

---

### Week 12 — Aug 10 (Mon) → Aug 16 (Sun) | Submission week
**Theme:** No new features. Finalize. Rest.

| Day | Action | Owner |
|---|---|---|
| Mon Aug 10 | Final narrative + video review. Both founders read+watch independently, then sync. | Both |
| Tue Aug 11 | Stripe screenshot finalized (this month's transactions, total collected, list of active subscriptions — mask anything sensitive). | Alan |
| Wed Aug 12 | GitHub final pass: README rewrite, link to runway.md as proof of execution discipline, ensure no `.env` or keys in history (`gitleaks` or equivalent). | Atharva |
| Thu Aug 13 | Customer reference list final — call each planner one more time to confirm they're OK being contacted. | Alan |
| Fri Aug 14 | **Assets frozen.** Only typo fixes allowed after this. Trial submission to Devpost (save as draft). | Both |
| Sat Aug 15 | Rest. Walk away from laptops. | Both |
| Sun Aug 16 | Re-read submission. Re-watch video. One final review with fresh eyes. | Both |

**Gate (Sun Aug 16 EOD):** ☐ Devpost draft complete with all fields ☐ all files uploaded or linked ☐ both founders have independently verified the GitHub link works from a clean browser session.

---

### Submission Day — Aug 17 (Mon)
**Morning (09:00–11:00):** Final read. Hit submit. Screenshot the confirmation.
**Afternoon:** Off. Do something that isn't this. You earned it.

---

## 2. Milestone Done Criteria (SMART)

| Date | Day | Milestone | Done means |
|---|---|---|---|
| Jun 2 | 7 | Sprint 0 close | ≥25 cold outreaches sent, 1 deploy URL live, 1 Stripe test charge in dashboard, ≥1 discovery call booked |
| Jun 9 | 14 | Sprint 1 mid | 2 planners on paid Stripe sub, 1 real couple in workflow, ≥15 logs from live use, 0 lock errors |
| Jun 16 | 21 | Sprint 1 close | 2 planners active in last 72h, 5+ couples, 50+ logs (≥80% have confidence_score), ≥€300 collected, P95 latency <15s |
| Jun 26 | 30 | Sprint 2 close | 3 planners on Stripe, 15+ couples, ≥€450 collected (€600 MRR run rate), 100+ logs with full parent_decision chains, 1 audio testimonial, narrative outline drafted |
| Jul 11 | 45 | Sprint 3 mid | 5 planners, €1,000+ MRR, demo video raw footage shot, timeline_builder shipped, 1 case study filmed or named-quote secured |
| Jul 26 | 60 | Sprint 3 close | 5–10 planners (target 7), 20–30 couples (target 25), ≥€1,500 MRR collected, case study published, video edited to 3:00, narrative ≥500 words, 1 reference-consent on file |
| Aug 17 | 82 | Submission | Devpost submitted with: GitHub link, narrative (500–1000 words), 3-min video, Stripe export, 10 sample decision-log chains, customer reference list, marketing-spend disclosure |

**Verification rule:** if the metric can't be queried/screenshotted, it doesn't count. "Felt like we had 5 planners" ≠ done. "Stripe dashboard shows 5 active subscriptions, screenshot saved to `docs/submission/`" = done.

---

## 3. Resource Allocation

### Founder split by week (parallelization map)

| Week | Atharva (hrs) | Alan (hrs) | Parallel work? | Single point of failure |
|---|---|---|---|---|
| W1 (May 27–31) | 8 (codebase) | 8 (list + templates + Loom) | ✅ Fully | None — both can fail independently |
| W2 (Jun 1–7) | 22 (deploy + Stripe) | 14 (intros) | ✅ Mostly | Deploy URL — if Atharva blocked, Alan can't onboard |
| W3 (Jun 8–14) | 28 (bugs + spend dash) | 24 (close 2 planners) | ✅ Mostly | Planner conversion — if zero, Atharva work has no audience |
| W4 (Jun 15–21) | 28 (stress + workflow view) | 22 (push 5 couples) | ✅ Fully | Concurrency bug — both must war-room if found |
| W5 (Jun 22–28) | 30 (timeline_builder) | 26 (planner #3 + testimonial) | ✅ Mostly | Planner #1 testimonial — if they ghost, narrative weakens |
| W6 (Jun 29–Jul 5) | 24 (hardening + audit) | 28 (wave-2 outreach) | ✅ Fully | None |
| W7 (Jul 6–12) | 18 (demo polish) | 30 (video shoot) | ⚠️ Coupled | Demo build quality → film quality |
| W8 (Jul 13–19) | 16 (perf + docs) | 26 (narrative draft) | ✅ Fully | Burnout — schedule rest |
| W9 (Jul 20–26) | 20 (video edit) | 22 (case study + Stripe export) | ✅ Mostly | None |
| W10 (Jul 27–Aug 2) | 18 (git hygiene) | 18 (Submission Kit) | ✅ Fully | Devpost field surprises |
| W11 (Aug 3–9) | 14 (slack) | 16 (narrative final) | ✅ Fully | Whatever slipped |
| W12 (Aug 10–16) | ~10 (review) | ~10 (review) | ⚠️ Coupled | Coordinate review on Mon and Fri |
| **Total** | **~236** | **~242** | | |

**Sustainability check:** ~5 hours/founder/day across 12 weeks is sustainable. The danger weeks are 3, 5, 7 (≥28 hrs each). Plan for those: groceries delivered, calendar blocked, no other commitments.

**Cross-training (the bus-factor mitigation):** every Friday afternoon, 30-min walkthrough where each founder explains their week's work to the other. Atharva walks Alan through what changed in the agent layer; Alan walks Atharva through who's onboarded and what they said. **If one founder goes down for a week, the other has enough context to triage.**

---

## 4. Five Additional Risks (Beyond the Brief's Table)

These are the ones the original risk table missed.

### Risk 1: Stripe Checkout is not built
**Impact:** Catastrophic for submission. No real Stripe = no revenue proof = no Business Viability category points.
**Where:** `streamlit_mock/app.py:214` currently simulates payment with `st.info("Simulating payment of €299...")`. There is no Stripe key, no Checkout session, no webhook.
**De-risk by:** Jun 7 (end of Week 2). Atharva ships a real Stripe Checkout in test mode that creates a PaymentIntent and writes a `PAYMENT` row.
**Data needed to confirm de-risked:** 1 test-mode €149 charge visible in Stripe dashboard + 1 corresponding row in the `payments` table with non-null `stripe_payment_id`.

### Risk 2: Inbound email parsing doesn't exist
**Impact:** Medium-high. The `quote_extractor` agent takes pasted-in email text. In production this means a planner has to copy supplier replies manually. If a judge asks "how does the AI actually receive supplier responses?" the answer today is "the planner pastes them in." That's a credibility hit.
**Where:** `streamlit_mock/app.py:474` — `st.text_area("Paste Supplier Email Response")`.
**De-risk by:** Jul 19 (end of Week 8). Either ship a SendGrid Inbound Parse webhook (probably 2 days work) OR pre-empt the question in the narrative: "Supplier replies are pasted by the planner today; SendGrid Inbound Parse ships post-Day-90." The narrative honesty is acceptable; pretending otherwise is not.
**Data needed:** EITHER 1 supplier reply that arrived via SendGrid → triggered quote_extractor → wrote a Quote row, OR a paragraph in the narrative that explicitly names this as planned-not-built.

### Risk 3: Cold-outreach conversion is unproven and likely <5% end-to-end
**Impact:** High. There is no warm-intro pipeline. Every pilot planner is a cold contact via email/LinkedIn/Instagram DM. Industry benchmark for cold B2B services outreach to small operators: 5–15% reply rate, 20–40% reply-to-call, 20–40% call-to-paid. Stack the worst case: 50 contacts → 3 replies → 1 call → 0.3 conversions. That sits below the Day 21 target of 2 paid planners.
**De-risk by:** Jun 9 (end of Week 2). Reply-rate signal is visible by then. If <8% reply rate, the issue is the message — change the script before sending Wave 2, not the volume.
**Data needed:** Daily tracking of `sent / replied / call_booked / signed / paid`. By Jun 9 you need ≥8% reply rate and ≥3 calls booked. If not, pause and rewrite the cold message (probably sharpen the hook — pilot pricing, specific Irish market angle, screenshot in the first message). If reply rate is healthy but call-to-paid is <10%, the friction is product/price, not outreach.
**Cold outreach hygiene:** Personalize every send with the planner's name + 1 line about a specific recent post/portfolio piece. Templates that look mass-sent get spam-filtered or ignored. Budget 3–5 min per send; 50/week per founder is the practical ceiling without burning out.
**Backup channel:** If by Jun 16 cold outreach hasn't produced 1 paid planner, run a £200 paid Instagram/Meta test ad targeted at "wedding planner Ireland" — converts on landing page email signup, then Alan calls everyone who signs up.

### Risk 4: Submission category is more crowded than estimated
**Impact:** Medium. "Professional Services Access" likely sees 50+ entries — legal AI, accounting AI, therapy AI. "Wedding coordinator" is narrow but not unique (Joy, Zola, Bridebook have AI features). Differentiation isn't "wedding," it's "Irish wedding cultural specificity + decision-log proof + real planner pilots."
**De-risk by:** Jul 11 (end of Week 7). By then the narrative must explicitly name 2–3 competitors and explain the wedge in one sentence.
**Data needed:** Competitive landscape paragraph in `docs/submission/narrative-v2.md`. Specific claim: "Joy and Zola add AI features to consumer apps; we ship an autonomous agent layer for the planner workforce with traceable decisions." Test this paragraph on a planner candidate during a discovery call — do they nod, or push back?

### Risk 5: Atharva-bus-factor (single ML/eng dev)
**Impact:** Catastrophic if it lands in Weeks 5–7. If Atharva is out for >3 days during the build, no shipped feature works for a planner — and Alan can't fix Python+Gemini code.
**De-risk by:** Jun 28 (end of Week 5). Two countermeasures:
  - Every Friday: Atharva records a 15-min Loom of "how the agent layer works this week" — keeps Alan within reach of the code mental model.
  - By end of W5, write a `docs/runbook.md` covering: how to restart Streamlit Cloud, how to reset the DB, how to revert a prompt, how to read a decision log.
**Data needed:** A `runbook.md` that Alan can execute solo to recover from a system-down incident. Test: Atharva is "out" for 24h (no Slack); Alan must triage and fix one minor bug using only the runbook. Run this drill once before Jul 1.

---

## 5. Backwards Calendar from Aug 17

Reading bottom-up. If a date slips, look at what's blocking the next-most-recent line above.

| Date | Must-be-true |
|---|---|
| **Aug 17 (Mon)** | Devpost submission uploaded by 17:00 local. Confirmation screenshot saved. |
| Aug 16 (Sun) | Final fresh-eyes review complete. Devpost draft 100% filled. |
| Aug 15 (Sat) | Rest day. No work. |
| Aug 14 (Fri) | **Asset freeze.** Trial Devpost submission saved as draft. Only typo fixes allowed past this point. |
| Aug 13 (Thu) | Customer reference list final + each planner reconfirmed by phone. |
| Aug 12 (Wed) | GitHub final pass: README, sample logs, no secrets, history clean. |
| Aug 11 (Tue) | Stripe export final (this month's transactions, MRR snapshot). |
| Aug 10 (Mon) | Narrative + video final review (independent reads, then sync). |
| Aug 9 (Sun) | All assets ≥90% complete. Buffer week ends. |
| Aug 2 (Sun) | Submission Kit skeleton exists. Devpost account active and submission requirements read line-by-line. |
| Jul 26 (Sun) | **Day 60.** Narrative v2 ≥500 words. Video edited to 3:00. Case study published. ≥€1,500 MRR collected. 1 reference-consent on file. |
| Jul 19 (Sun) | Demo + case-study raw footage in hand. SendGrid risk (Risk 2) resolved one way or the other. |
| Jul 12 (Sun) | Demo video shot. Case study planner filmed (or written quote secured). |
| Jul 5 (Sun) | 5 paying planners. Feature freeze on new agents in effect. |
| Jun 26 (Fri) | **Day 30.** 3 planners on Stripe, €450 collected, 100+ logs, audio testimonial captured, narrative outline started. |
| Jun 21 (Sun) | Stress test passes 3-concurrent. Postgres-migration go/no-go decision made. |
| Jun 16 (Mon) | **Day 21.** 2 planners paid, 5+ couples, 50+ logs. Sprint 1 retro decision logged. |
| Jun 9 (Mon) | 2 planners on paid Stripe. 1 real couple in workflow. |
| Jun 7 (Sun) | Stripe Checkout integration live with 1 test charge. URL deployed. |
| Jun 2 (Mon) | **Day 7.** Outreach Wave 1 sent (≥25 contacts). Deploy URL live. ≥1 discovery call booked. |
| May 31 (Sun) | Codebase committed (Python only). 50-planner target list + outreach templates + 90-sec Loom ready to fire Wave 1 Monday. |
| **May 27 (Wed)** | This doc ratified by both founders. Begin. |

---

## 6. Living Document Rules

1. **Update on Fridays.** Each founder edits the week-they-just-finished section with what actually happened (target vs actual). Don't rewrite history; append a "Reality:" line.
2. **Decision gates land in `docs/runway-retros.md`.** Don't bury the gate calls in this doc; this stays a forward-looking artifact. The retros file is the audit trail.
3. **The Locked Decisions table (Section 0) is sticky.** Don't edit it without explicitly invoking a revisit trigger and noting the date.
4. **If the math gets ugly, the deadline doesn't move — scope does.** When you fall behind, cut from Sprint 3 (the "expand to 7 planners" goals) first. Last to cut: Day 30 metrics and submission kit completeness.
5. **Both founders sign Friday Loom updates with a single line: 🟢/🟡/🔴 + 1 sentence.** No prose required. The cumulative pattern is the early-warning signal.

---

## 7. The One-Question Test

Each morning, look at this doc and ask: *"Is what I'm about to spend the next 8 hours on actually on the critical path to Aug 17 submission?"*

If the answer isn't clearly yes, switch to something that is.
