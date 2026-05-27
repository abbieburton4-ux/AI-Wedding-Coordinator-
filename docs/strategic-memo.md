> **Historical document — May 2026.**
> This memo was written 3 days into the build window and shaped the Option A pivot to the AI Wedding Coordinator framing. Some references (e.g., specific advisor names, "Mary-Aoife") describe the thinking at the time rather than current commitments. Treat as the **reasoning record**, not the live plan. The live plan is [runway.md](runway.md).

---

# VenueFlow.ie vs. the Build with Gemini XPRIZE Field — A Brutally Fair Strategic Memo

**Author:** Lead research desk
**Date:** 22 May 2026 (3 days into the build window)
**Audience:** VenueFlow.ie founder + prospective ML engineering co-founder

---

## TL;DR

- **Honest ranking with current scope: bottom three-quarters of submissions, realistic landing zone is "no prize" or, at best, the $50,000 Small Business Services category prize.** A top-5 finish ($100K+) on the current ICP, geography and team is highly unlikely.
- **The single biggest problem is not the idea — it's that an almost identical company (Mikla.ai) is already 4x ahead of VenueFlow's Day-90 target and is the natural front-runner for the Small Business Services category.** Mikla is at 200+ venues across 29 venue types with $249–$499/mo SMB pricing, and matching that scale in 90 days from a standing start in Wicklow is implausible.
- **A top-5 finish is reachable, but only with a category re-pitch (move to Professional Services Access), a 10x ACV pivot (replace the €4,000–€8,500 wedding coordinator, not the venue receptionist), aggressive distribution via wedding-planner ICPs in the UK/Ireland, and an ML co-founder who can stand up agent execution logs that prove "AI runs the business" — not just "AI answers the phone."**

---

## 1. The Competition: What Actually Wins This

### 1.1 Prize structure & the real bar

- $2M across 25 winners: $500K (1) / $200K (1) / $100K × 3 / $50K × 15 runner-ups / $50K × 5 category prizes.
- Judging is three equally-weighted criteria — **Business Viability, AI-Native Operations, Category Impact** — with the tiebreaker order indicating real priority (viability first, AI-native second, impact third). Submissions must show monthly revenue, named customer contact info, and **agent execution logs / API usage records / dashboards that prove "AI is running in production continuously."**
- Hacker Fund screens; five live finalists pitch in Los Angeles on Sep 25, 2026 at the Moonshot Gathering.

### 1.2 Participation signal (3 days in)

- Devpost shows **1,966 participants** as of 22 May 2026 (3 days after launch).
- Comparable benchmark: the Gemini 3 Hackathon (Jan–Feb 2026, $100K pool, *no* revenue requirement) hit ~35,616 participants and ~4,500 submissions — i.e., ~13% submission conversion.
- Bolt's "World's Largest Hackathon" (May–June 2025, $1M+ prize pool) registered **131,307 total participants, 67% of them solo** (per the DEV Community post-hackathon analysis, Jul 2, 2025).
- **Forecast:** the real-revenue requirement will suppress raw signups but pull a more committed cohort. Realistic registered participant range: 15,000–35,000. Realistic *submission* range: 1,500–4,000. So winning anything = ~top 1% of submissions; top-5 = ~top 0.2%.

### 1.3 Likely winner archetype — from Diamandis's own pitch deck

Peter Diamandis explicitly cited Matthew Gallagher's **Medvi** as the archetype. Per the New York Times (Apr 2, 2026), which first reported the numbers: *"In its first full year, 2025, the company generated $401 million in revenue and $65 million in net profit, a 16.2% margin. It is now on track for $1.8 billion in sales in 2026."* Built with $20K starting capital, two people (Gallagher and his brother Elliot), and ~12 AI tools (ChatGPT/Claude/Grok for code and copy, Midjourney/Runway for ad creative, ElevenLabs for voice cloning, custom GPT chatbots for CX) sitting on top of CareValidate/OpenLoop's prescription-fulfillment back-end.

**Critically:** Medvi works because it sits on top of (a) a 9-figure-TAM consumer demand wave (GLP-1), (b) a fulfillment back-end Gallagher did not have to build, and (c) high LTV per customer (telehealth subscription with auto-refill).

**Important caveat:** the FDA issued Medvi a formal warning letter on Feb 20, 2026 (FDA document #721455-02202026), and the same NYT piece confirmed Medvi's AI chatbot *"fabricated drug prices"* and *"hallucinated product lines that did not exist,"* with Gallagher honoring the hallucinated prices out of pocket. The archetype Diamandis cites is itself contested. Judges may reward the trajectory; they will probably *not* reward unsafe AI in production.

**Lesson for hackathon judges:** "AI-native ops" = AI is generating *and* executing — code, creative, ads, voice, scheduling, lead-qual decisions — not just answering a phone. But it must be **trustworthy** in production.

### 1.4 Comparable solo/duo AI-native breakouts (2024–2026)

| Company | Founders | Time-to-$X | Vertical | What AI actually does |
|---|---|---|---|---|
| Medvi | 2 | $401M Y1 (per NYT) | GLP-1 telehealth | Code, ads, voice, CX, copy |
| Cluely | Founders Roy Lee + Neel Shanmugam, ~11–22 employees | ~$5.2M total (~$2.7M consumer + ~$2.5M enterprise) in ~6 months — peaked and publicly contested; CEO Roy Lee admitted on X (Mar 5, 2026) "*got a random cold call from some woman asking about numbers and told her some bs*," and TechCrunch confirmed his own PR team had proactively arranged the interview in which the fabricated $7M figure was given | Meeting overlay | Real-time LLM inference |
| Cursor | small team | $100M ARR | Dev tools | AI is the product |
| Lovable | small team | $100M ARR via vibe-coding | Dev tools | AI builds apps |
| Base44 / Maor Shlomo | 1 (solo) | $3.5M ARR, sold to Wix $80M cash in 6 mo | Vibe-coding | AI builds apps |
| HeadshotPro / Danny Postma | 1 (solo) | $300K/mo | AI headshots | AI generates product |
| Beside (ex-M1) | 5-person founding team — CEO Maxime Germain plus co-founders Bobby Giangeruso, Aymeric Beaumet, Justin Bureau, and Hélène Blonz (all former Jour colleagues; per Index Ventures' Nov 11, 2025 Series A announcement) | $4M ARR, 20K customers, $32M Series A | AI receptionist for SMBs | AI runs CX/booking |
| **Mikla.ai** | small team | 200+ venues, ~$600K–$1.2M ARR run-rate | **AI sales assistant for wedding venues** | **Same wedge as VenueFlow** |

The pattern: vertical AI businesses where AI executes meaningful production decisions are the favored archetype. Distribution + a real fulfillment partner + a clear "AI replaces N hours of human work" story wins.

### 1.5 Category economics — where the $100K+ tier lives

| Category | ACV ceiling | Sales cycle | 90-day revenue plausibility | Judge "Impact" appeal |
|---|---|---|---|---|
| Education & Human Potential | Low ($10–$30/mo per user) | Short, but consumer churn brutal | Medium | Very high — emotional |
| Entrepreneurship & Job Creation | Medium | Variable | Medium | High |
| **Small Business Services** | **$50–$500/mo per SMB** | **Short B2B** | **Medium** | **Medium — feels incremental** |
| Money & Financial Access | High (often per-transaction) | Heavy regulatory | Low (regs) | Very high — populist |
| Professional Services Access | High ($300–$3,000/mo) | Short prosumer | High | Very high — replaces white-collar labor |

**The structural bias:** Money & Financial Access and Professional Services Access have higher ACVs and stronger "impact" narratives (replacing $50K/year lawyers, $35K/year coordinators, $250+/visit professionals). Small Business Services has the most submissions chasing the lowest revenue ceilings — it's the most crowded, least-rewarded category to enter.

**Implication for VenueFlow:** Small Business Services is structurally the *worst* category for a top-5 finish unless you have unusual distribution (Mikla scale or better).

---

## 2. The Competitive Landscape Inside the Venue Vertical

### 2.1 Mikla.ai — the existential threat

Mikla is **the same product VenueFlow is proposing**, already at production scale and aggressively scaling US-first:

- Tagline: "The #1 AI sales assistant for venues, hotels, and restaurants."
- **200+ venues worldwide** (up from "50+ wedding venues" earlier in 2026 — a ~4x in months).
- **29 venue types** including pubs, breweries, farms, golf clubs, conference centers, rooftop venues, historic estates, restaurants — VenueFlow's "mixed-use" angle is already covered.
- Pricing: **Starter $249/mo · Growth $499/mo · Enterprise custom**, 90-day money-back guarantee, no setup fees.
- Channels covered: phone, email, web forms, The Knot, WeddingWire, Instagram DM.
- Stack: "Advanced language understanding powered by OpenAI, Anthropic, and Google AI."
- Case studies: Box House Hotel Brooklyn ($2M+ tours scheduled in 1 month), Vesper Brooklyn ($450K+ bookings), Sunflower Hill Farm Augusta MO (+125% booking rate).
- 12-minute self-serve onboarding.

**At ~200 venues × ~$375 blended ARPU ≈ ~$75K MRR / ~$900K ARR run-rate today.** This is already ~3–5x VenueFlow's stated Day-90 target (€15–25K MRR).

If Mikla submits to the Build with Gemini XPRIZE in Small Business Services with verifiable revenue, agent execution logs across 29 venue types, and a clear "AI sales agent" narrative, they are the structural favorite for either the **category prize or a runner-up slot**, and a plausible top-5 contender.

### 2.2 Other entrants in this lane

- **Frontdesk / My AI Front Desk** — has a dedicated "Event Venues & Banquet Halls" vertical page; 24/7 inbound, calendar booking, tour scheduling.
- **Goodcall** — integrates with Tripleseat (the dominant event-management software with 20,000+ venues), positioning as an AI phone agent layer.
- **Tripleseat Intelligence** (launched 2025) — an agentic suite built on a unified data layer from millions of events across 20,000+ venues. Drafts contracts, manages real-time changes, nurtures long-cycle deals. This is the incumbent fighting back, not a hackathon entrant — but it's evidence that the venue-AI category is being commoditized fast.
- **Beside (ex-M1)** — $4M ARR, 20K paying SMB customers, $32M Series A from EQT + Index in Nov 2025. Horizontal across plumbers, contractors, realtors, hair salons — actively expanding into hospitality.
- **VenueAI, VenueBot, VenueX AI, AgentiveAIQ** — multiple venue-specific AI chat platforms already in market.
- **CloudTalk, Smith.ai, Retell AI, Vapi, Bland AI ($0.09/min base), Synthflow** — horizontal AI voice receptionist platforms. Wedding venues are already an advertised vertical for several.

**Conclusion:** the "AI receptionist for venues" wedge is one of the **most crowded vertical AI niches of 2026.** VenueFlow's differentiation cannot be the product. It has to be ICP focus, geography, or a labor-replacement narrative the incumbents don't tell.

### 2.3 Likely "frontrunner" hackathon entrants in Small Business Services

Even if Mikla doesn't formally enter, the Small Business Services category will likely include:
- AI receptionist / scheduler vertical entrants (legal intake, dental, HVAC, real estate, salons).
- AI bookkeeping / AR-collection agents.
- AI marketing-ops shops for local SMBs.
- AI hiring agents for SMB retail/hospitality.

These are crowded spaces with proven revenue templates. Several teams entering this hackathon will have pre-existing customers from prior 2024–2026 launches that they can "fold into" the 90-day window narrative (rules permit launching during the window; the spirit favors fresh launches, but enforcement is fuzzy and last year's Devpost AI competitions saw widespread "pre-built shell, accelerated during window" tactics).

---

## 3. Honest Ranking of VenueFlow.ie As Currently Scoped

### 3.1 The 90-day revenue model — show the working

Assumptions (charitable but realistic):
- Solo founder ± 1 ML engineer; founder has never shipped a production app solo before.
- Ireland-only ICP across 4 segments: pub function rooms (~2,000), small wedding venues (~400), GAA/community halls (~3,000 — defensible: the GAA reports ~1,383 clubhouses across ~1,600–2,300 clubs; adding parish halls and community centres gets near 3,000), mixed-use (churches, residential).
- Pricing: €79–€349/mo blended ~ €160 ARPU.
- Outbound + founder-led sales (no pre-existing distribution).

| Week | Activity | Plausible paying customers added |
|---|---|---|
| 1–2 | Build MVP (voice intake, quote generator, calendar) | 0 |
| 3–4 | First 5 design partners (free or €1) | 0 paying |
| 5–6 | Convert design partners to paid; founder-led outbound | 3–8 |
| 7–9 | Inbound starts; word-of-mouth in Wicklow/Dublin | +10–20 |
| 10–13 | Outbound campaign nationally | +15–30 |
| **Day 90 realistic** | | **28–58 paying customers** |

At ~€160 ARPU: **€4.5K–€9.3K MRR. Roughly €55K–€110K ARR.**

The founder's stated target (€15–25K MRR / 100–150 venues) is plausible only with (a) the ML co-founder committed full-time, (b) a viral channel hit early, or (c) heavy paid-acquisition spend. Hitting it solo from Enniskerry is **possible but optimistic.**

### 3.2 Where €5–10K MRR plus a polished AI-native ops narrative actually places

**Tiebreaker order matters:** Business Viability is the first tiebreaker. €5–10K MRR (~$5.4K–$10.8K) at Day 90 is real revenue, but in a global pool of 1,500–4,000 submissions, where the top of the field will include teams with $50K+ MRR (Medvi-style supply-chain plug-ins, AI consulting/services arbitrage, vertical agents with high ACVs), VenueFlow's revenue is **below the top quintile.**

| Prize tier | Approximate revenue floor (best guess) | VenueFlow likelihood |
|---|---|---|
| 1st ($500K) | $100K+ MRR with compelling impact + scalability narrative | <1% |
| 2nd ($200K) | $50K+ MRR | <2% |
| Top 5 ($100K) | $25K+ MRR with strong AI-native story | ~3–8% |
| Runner-up ($50K) | $10K+ MRR or breakout impact story | ~10–20% |
| Category prize Small Business Services ($50K) | Best-in-category, may have lower revenue if AI-native narrative is exceptional | ~10–25% |
| No prize | — | ~50–70% |

**Expected value of a prize:** roughly $8K–$22K weighted across outcomes — well below the opportunity cost of 90 days of full-time solo founder work unless there is a real business at the end of it.

### 3.3 Structural disadvantages

1. **Ireland market is small.** TAM at proposed pricing × all-Irish-venues ceiling ≈ ~€10–15M ARR. Judges asking "is widespread adoption credible at scale?" see Ireland as a market test, not a market.
2. **ACV ceiling is low.** €79–€349/mo per venue caps the business viability story at a level several other categories will dwarf.
3. **No pre-existing distribution.** Founder is in Enniskerry, not embedded in The Knot / WeddingWire / Tripleseat ecosystem. Mikla has US wedding-blog and marketplace integrations already.
4. **Solo/duo with no production ship history.** Day-90 evidence (agent logs, dashboards) requires senior engineering execution. ML friend is *uncommitted* — single biggest risk.
5. **Direct competitor 4x ahead.** Mikla.ai is *already* the SaaS this concept describes — same channels, same 29-venue-type scope, same OpenAI/Anthropic/Google stack — at 200+ paying venues.
6. **Category is the most crowded.** Small Business Services will likely have the most submissions and lowest revenue ceilings per submission.

### 3.4 Structural advantages

1. **Local validation is real.** Founder is in Wicklow — Ireland's wedding/events heartland. Mary-Aoife is a real event manager who has shaped thesis; that founder-market fit is rare.
2. **AI-native ops architecture is technically credible.** Gemini 3.5 Flash voice intake + Gemini 3.5 Pro quote generation + Antigravity managed agents + Cloud Run + Firestore + Stripe + Twilio is a clean stack the judges will *recognize* (it's literally the Google sponsor stack — major narrative tailwind).
3. **Submission requires Gemini + at least one Google Cloud product.** A team that builds natively on the sponsor stack with Antigravity agent execution logs will score well on AI-Native Operations vs. teams retrofitting OpenAI calls.
4. **Mixed-use / underserved verticals (churches, community halls, GAA) is a fresh angle** Mikla hasn't yet pushed in the US.
5. **Mary-Aoife's redirect — supplier marketplace + central database** — is a stronger "Category Impact" story than "AI receptionist" if pursued.

---

## 4. What It Would Take to Break Into Top 5 ($100K+)

The fundamental insight: **VenueFlow as currently scoped is competing against Mikla in Mikla's strongest moat (US wedding venues). To win, you must change the game.**

### 4.1 Strategic pivot options, ranked

**Option A (recommended) — Re-pitch as Professional Services Access: "The AI Wedding Coordinator"**

- Reframe from "AI receptionist for venues" to **"AI replaces the €4,000–€8,500 wedding coordinator"** — i.e., the white-collar labor that ~80% of couples currently can't afford.
- Sell to **couples directly** (B2C, €299–€999 one-time fee per wedding) and to **independent wedding planners** (B2B, €199–€499/mo to clone themselves and serve 5x more clients).
- ACV: Couples ≈ €500 one-time × 100 couples = €50K cash in 90 days. Planners ≈ €350 × 30 = €10.5K MRR.
- Category: **Professional Services Access** — far less crowded, much stronger impact narrative ("we put a wedding coordinator in every couple's pocket for €500 instead of €5,000"), and aligns with Diamandis's stated thesis ("solve a real problem that impacts 100,000 people").
- AI must execute *the work of a planner*: vendor sourcing, timeline drafting, budget tracking, contract review, RSVP/seating logic, day-of run-of-show. This is genuinely AI-native ops in production — agent execution logs are a strong story.

**Option B — Stay in Small Business Services but 10x the ICP**

- Move from "small Irish venues" to **UK + Ireland mid-market venues** (hotels with function rooms, country house hotels, larger wedding venues). Mikla's case studies skew US/farm/Brooklyn; UK/Ireland is uncontested.
- Raise pricing to £499–£1,499/mo by including contract drafting, deposit chasing, post-event review-collection, and KPI dashboards — i.e., "AI sales + ops department" rather than receptionist.
- Target: 40 venues × £900 = ~£36K MRR / ~£430K ARR run-rate at Day 90.
- This pushes you into the top quartile of business viability, with a defensible "regional dominance + premium tier" story.

**Option C — Supplier marketplace + venue discovery agent (Mary-Aoife's redirect)**

- Build a Gemini-powered supplier discovery agent that helps couples and planners find DJs, florists, photographers, caterers in mixed-use and rural Irish venues.
- Monetize via supplier subscriptions (€49–€199/mo) and booking referral fees (5–10%).
- "Category Impact" story is strong (solves a structural pain point Mary-Aoife flagged: hard-to-find suppliers + no central database). Business viability is the weakest of the three (low ACV, two-sided cold-start problem).
- **Not recommended in 90 days** — marketplaces need both sides, hard to ignite cold from Enniskerry alone.

### 4.2 Distribution levers that move the needle

To plausibly hit the top 5, VenueFlow needs to activate at least 2 of these:
1. **A wedding-planner influencer partnership** (One Fab Day, Confetti.co.uk, RSVP, or a high-Instagram-following planner) who endorses or co-launches.
2. **A Knot / WeddingWire / Bridebook integration** that puts the agent in front of every couple inquiring at participating venues.
3. **An Irish hotels group deal** (Dalata, Talbot Collection, Choice Hotels Ireland) — even a 5-venue pilot gives credibility + revenue.
4. **A PR moment** tied to a uniquely Irish story (an underserved community hall booking weddings again because of AI). Diamandis's narrative loves "unexpected heroes."

### 4.3 Team additions needed

- **ML/backend engineer** committed full-time. The current "interested but uncommitted" status is the single point of failure. Without an engineer who has shipped agents to production, the agent execution log requirement is the killer.
- **Mary-Aoife (or a real venue operator) as part-time advisor or co-founder.** Judges will look for domain proof in the 500–1000 word written narrative; her presence transforms the founder-market-fit story.
- Optional: **A growth/content person.** The hackathon rewards storytelling — a polished demo video, a clear narrative, a real-time MRR chart all count.

### 4.4 AI architecture upgrades to actually be "AI-native"

Current architecture (Gemini 3.5 Flash voice + Pro quote gen + Antigravity agents + Cloud Run + Firestore + Stripe + Twilio) is *good*. To win, every one of these decisions must demonstrably be made *by the agent*, not by templates:

| Decision | Owner today (typical SaaS) | Owner in winning AI-native version |
|---|---|---|
| Qualify lead? | Rules engine | Gemini Pro agent decides + writes reasoning |
| Quote price? | Pricing table lookup | Gemini Pro agent generates contextual quote, justifies it |
| When to follow up? | Cron job | Antigravity scheduled agent decides cadence per lead |
| Send contract? | Template | Agent drafts custom contract, flags risks |
| Collect deposit? | Stripe link | Agent decides timing + amount per risk profile |
| Reschedule on conflict? | Manual | Agent autonomously rebooks |
| Post-event review request? | Drip sequence | Agent personalizes ask per event quality |

Each row above is a candidate for an **agent execution log entry** to put in the submission. Judges want to see *decisions in production* — this is where Antigravity Managed Agents earn their place in the architecture. Lessons from Medvi: log everything, and put guardrails on price-quoting agents so they don't hallucinate a quote you have to honor out of pocket.

---

## 5. Hard Question: Is This The Right Swing At All?

There are three honest framings:

**Framing 1 — Hackathon as a forcing function for a real business.**
If VenueFlow.ie becomes a real SaaS that does €10K+ MRR in Ireland by Day 90, that's a viable bootstrapped business worth €120K+ ARR — regardless of prize money. The hackathon is a deadline and free Google credits. **Expected value: positive even with no prize.**

**Framing 2 — Hackathon as lottery ticket.**
Going for top-5 ($100K+) requires the pivots in Section 4. Without them, EV of a prize is ~$8–22K. Better risk-reward than most lotteries, but the founder is paying with 90 days of focused work.

**Framing 3 — Wrong battlefield entirely.**
The same founder, with the same ML engineer, could pick a less-crowded vertical (e.g., AI for Irish independent law firms, Irish independent veterinary practices, Irish independent property managers) where there is no Mikla equivalent, and a single anchor customer at €500–€2,000/mo could anchor the whole submission. Same architecture, less crowded category, higher ACV. **For top-5 probability, this is the highest-EV path.**

---

## 6. Recommendation

**The realistic prize tier attainable with VenueFlow.ie as currently scoped is: no prize ~60% / Small Business Services category prize $50K ~15–20% / runner-up $50K ~10–15% / top 5 $100K+ ~5–8% / top 2 ~1–2%.**

To meaningfully move into top-5 territory ($100K+), pursue **Option A (re-pitch as "AI Wedding Coordinator" in Professional Services Access)**, with the following non-negotiables:
1. Commit Mary-Aoife as advisor or co-founder by Day 7. No event-industry domain proof = no top 5.
2. Get the ML engineer signed up by Day 14 with a clear "I will build agent infrastructure in production" mandate. If he says no, replace him before Day 21 or seriously reconsider entering.
3. Lock the first 5 paying customers (couples + planners) by Day 30. If you cannot get 5 paying customers in 30 days, the business viability story will not improve in the remaining 60.
4. Build the agent execution log infrastructure from Day 1 — every decision the system makes must be logged, timestamped, and exportable as a CSV/screenshot for the submission.
5. Pick *one* PR/distribution channel and own it (recommend: Irish wedding planner Instagram partnership + a "we put a wedding coordinator in every couple's pocket" story angle).

**Benchmarks that would change this recommendation:**
- If you cross **€15K MRR by Day 60**, hold scope and push for top-5 in Small Business Services — you're outperforming the model.
- If you sign **a Dalata / Talbot Collection / Choice Hotels Ireland multi-venue deal**, hold scope; the distribution moat matters more than the category re-pitch.
- If by **Day 21 the ML engineer hasn't committed and no replacement is signed**, stop; either spend the remaining 70 days on a less-crowded vertical (Framing 3) or treat this purely as a bootstrapped business build (Framing 1) and skip the submission.
- If **Mikla.ai publicly announces it is entering the Build with Gemini XPRIZE**, immediately re-categorize to Professional Services Access — Small Business Services becomes unwinnable.

**Tradeoffs the founder is accepting by entering vs. alternatives:**
- 90 days of focus on a crowded vertical with a 4x-ahead competitor instead of a less-crowded one.
- Optimization for a prize-pool outcome with ~5–8% top-5 odds, vs. optimization for a small but real lifestyle business.
- Implicit bet that the ML engineer commits — this is the single most leveraged decision.

**Use this memo to recruit the ML engineer, not to pump him up.** The honest pitch is: "This is a 5–8% shot at $100K+, a 25–35% shot at $50K, and a 50–70% shot at building a real €120K ARR business with no prize. The math gets dramatically better if you join, because the agent execution log is the difference between top-25 and top-5. Are you in?"

---

## 7. Caveats

- Mikla.ai customer counts and revenue are inferred from website claims and pricing — they have not publicly disclosed funding, so the competitive threat is calibrated from product/marketing evidence, not from a funded-runway model.
- Devpost participant counts are early-window data (3 days in); final submission counts and category distribution are unknown until August 17.
- Several "solo AI founder" revenue figures (Sarah Chen, Senja, Vincent Jong, and parts of the Cluely trajectory) come from aggregator content or contested founder statements — they are directional, not load-bearing.
- The Cluely revenue trajectory has been explicitly contested by Roy Lee himself (admitted on X, Mar 5, 2026 that the $7M ARR figure was fabricated to a journalist his own PR team had arranged). Treat $5.2M as the better-supported figure.
- Medvi has received an FDA warning letter (Feb 20, 2026) and the NYT confirmed AI hallucinations in its production CX. The archetype Diamandis cites is itself under regulatory and reputational scrutiny — judges may quietly mark down submissions that visibly replicate its weakest patterns.
- Judging criteria interpretation (especially how heavily "agent execution logs" weight) is inferred from the submission requirements; actual judge weighting is unknown.
- The €/$ conversion and EU vs US wedding-coordinator price points are approximate; verify for the final pitch.
- Irish market sizing figures (~2,000 pub function rooms, ~400 small wedding venues, ~3,000 community/GAA halls) are estimates synthesized from IBISWorld (6,793 pub-and-nightclub enterprises in Ireland 2026), CSO Ireland (~700 civil-ceremony-licensed venues), and GAA self-reported inventories (~1,383 clubhouses across ~1,600–2,300 clubs); they are defensible but should be re-validated before being used in pitch materials.
