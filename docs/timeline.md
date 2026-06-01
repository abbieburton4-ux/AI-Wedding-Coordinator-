# Timeline — Revenue-First Critical Path

**Re-based:** 2026-06-01 · **Submission:** 2026-08-17 · **Finalists pitch:** 2026-09-25

This is the *operating* timeline — the short, decision-focused view of what actually
moves us toward **paying customers + revenue proof**. The exhaustive week-by-week
plan, risks, and resource split live in [runway.md](runway.md); this file is the
filter we read each morning. When the two disagree, fix one deliberately — don't drift.

> **The one-question test:** *Is what I'm about to spend the next hours on on the
> critical path to a customer paying us?* If not clearly yes, switch.

---

## The critical path (in order)

1. **Take money** — Stripe Checkout working (test mode is free). ✅ *mock path live
   2026-06-01; flip to Stripe test mode is a one env change — see [worklog](worklog.md).*
2. **Be reachable** — one app deployed to a public URL a planner can click. ⬜
3. **One clean demo path** — intake → pay → AI plan → decision-log export, on a clean DB. ⬜
4. **One paying customer** — a single real planner/couple beats five more features. ⬜
5. *Then* polish UI / add agents. Not before.

---

## Technical track (owner: Atharva)

| Window | Ship | Status |
|---|---|---|
| **Jun 1–7** | Rotate leaked Gemini key. Payment gate + Checkout (mock). **Deploy backend + frontend to a public URL.** Stripe test-mode charge visible in dashboard. | 🔄 payment gate done; key + deploy + Stripe charge pending |
| Jun 8–21 | Stripe **live** mode ready. Reconcile Pro/Flash story (paid key or reword). Per-wedding "workflow status" view. Fix only the top-2 bugs from first calls. | ⬜ |
| Jun 22–Jul 5 | `timeline_builder` agent (template-driven). CSV "narrative export" for judges. **Feature freeze on new agents after this.** | ⬜ |
| Jul 6–26 | Judge-facing demo polish, sample log bundle, perf/cost pass, PII-redaction check. | ⬜ |
| Aug | Git hygiene, secret scan, asset freeze, submit. | ⬜ |

## Business track (owner: Alan, Atharva supporting)

| Window | Goal | Status |
|---|---|---|
| Jun 1–7 | 50 outreaches sent, ≥8% reply, ≥3 discovery calls booked, 90-sec Loom live. | ⬜ |
| Jun 8–21 | **1–2 paying planners.** 5 couples in workflow. | ⬜ |
| Jun 22–Jul 11 | 3–5 planners, ~€600–€1,000 MRR, 1 audio testimonial captured. | ⬜ |
| Jul 12–26 | Demo + case-study filmed, ≥€1,500 MRR, 1 reference-consent signed. | ⬜ |
| Aug | Submission kit, Stripe screenshot (revenue proof), narrative ≤1000 words. | ⬜ |

---

## Marketing channels (priority order)

1. **Instagram DMs** — where Irish wedding planners actually live. Personalize on a
   specific recent post. Offer Founder pilot rate + 90-sec Loom + one link. ≤4 sentences.
2. **LinkedIn** — the "serve 5× more clients" business pitch + build-in-public posts
   (1–2/week; a real redacted decision log is great content *and* submission proof).
3. **Directories as a lead list** (not a channel): One Fab Day, Bridebook,
   WeddingsOnline.ie, Google Maps "wedding planner Dublin/Cork/Galway".
4. **Fallback only if cold stalls by Jun 16:** €200 Meta/Insta test ad → email capture
   → Alan calls every signup.

> Stage rule: **20 personalized DMs > 1 viral post.** We need 5 planners, not 5,000 impressions.

---

## Submission artifacts (Aug 17) — status

- [ ] GitHub repo polished
- [ ] 3-min video demo
- [ ] 500–1000 word narrative
- [ ] Stripe dashboard / bank statement (revenue proof — **real** charge required)
- [ ] Marketing spend disclosure
- [ ] Agent execution logs (CSV)
- [ ] Named customer contact info (reference-consented)

**Verification rule (from runway.md):** if it can't be queried or screenshotted, it
doesn't count.
