# The wedding: facts

Source of truth for facts about this one wedding, for agents in Claude Code and in AI Studio. Only the product lane edits this file (see `.agents/AGENTS.md`), and only with what the couple says. Agents never infer or invent these facts. Anything unknown stays `[GAP]` until a person supplies it.

This repo is public. Keep personal details out of git: no guest names, emails, phones or addresses here.

The owner (one of the couple) is fine with the wedding date, venue and budget being visible in this public repo: "yes, thats fine" (2026-11-04). That answer covers those three facts only. A second answer covers the city (Chicago), the ceremony type (Jewish), the guest count (225 invited), the family make-up (4 parents, 2 siblings) and the partner being the groom: "having this info public is fine" (owner, 2026-11-04). Guest names, emails, phones and addresses still stay out of git.

| Fact | Value | Source / checked | Notes |
| :- | :- | :- | :- |
| Date | Provisional: Saturday 21 August 2027. Not fixed yet; months under consideration: August, September or October 2027 | Owner (one of the couple), 2026-11-04: "august, september, october 2027". Provisional date, 2026-11-05: "select August 21 2027, and show a 'dates are provisional' but give me the option to change it" | The hard deadline everything is ranked against. The app shows dates as provisional, and the couple can change the date (PD-007). Final date [GAP]. 21 Aug 2027 is a Saturday, which is Shabbat. A Saturday works: "saturday wedding works for us" (owner, 2026-11-05). The ceremony time, for example after Shabbat ends, is [GAP] for the couple and their rabbi |
| Place (city / venue) | Country: United States. City: Chicago, IL. Venue: none chosen yet (see Venue status) | Owner (one of the couple), 2026-11-04: "united states, chicago, IL" | The vendor catalogue and regions are Ireland-only today, so they don't cover this location (backlog B11) |
| Currency | US dollars (USD) | Owner (one of the couple), 2026-11-04: "US dollars" | The app currently assumes EUR (backlog B11) |
| Ceremony type / tradition | Jewish ceremony, at the venue (not booked yet). Traditions: "the usual jewish traditions"; the planning tasks chosen are in `checklist-list.md`, part 2 | Owner (one of the couple), 2026-11-04: "a jewish ceremony at the venue. we want the usual jewish traditions". Planning tasks, 2026-11-05: "cut J6, J14, J15, J16, J19, J22, J25 but keep the rest. combine find rabbi with find officiant" | Drives the budget split and timeline. The officiant and the denomination: [GAP], ask the couple when the plan needs them |
| Budget | [GAP] (still being decided) | Owner (one of the couple), 2026-11-04: "budget is still being determined. i will add that in later" | The owner will add it later. A range is fine. The owner has agreed it can be public |
| Guest count (estimate) | 225 invited | Owner (one of the couple), 2026-11-04: "inviting 225" | Number of people invited, not an attendance estimate. Expected attendance [GAP] |
| Venue status | Not booked. Still looking, with a shortlist; the couple are visiting the shortlisted venues the week of 2026-11-04 | Owner (one of the couple), 2026-11-04: "no venue yet, still looking but have a short list and visiting them this week. hope to have 1 booked soon" | Shortlisted venues not named. No booking or booking date yet. The couple hope to book one soon |
| Who has access (roles, not names) | The owner, the partner, and family of the couple | Owner (one of the couple), 2026-11-04: "partner and family of the couple" | Details and open gaps in "Who uses the app" below |

## Who uses the app

Roles only, no names: "roles only as long as I can assign mulitple people to 1 role" (owner, 2026-11-04). In the app, one role can hold several people (backlog B22).

| Person (role) | Access | Notes |
| :- | :- | :- |
| Owner (one of the couple) | Edit everything. Makes decisions for the app. Adds people and changes their access, shared with the groom (PD-002) | "I am part of the couple and can make the decisions" (2026-11-04). [ASSUMPTION] Their answers count as the couple ratifying, inferred from "can make the decisions". On permissions: "i should be able to add and edit permissions in the future though" (2026-11-04); see backlog B22. Edit everything: "yes to (a) and (b)", answering PD-002 call (b) (owner, 2026-11-04) |
| Partner (the groom) | Edit everything. Also adds people and changes their access | Will use the app ("partner and family of the couple", owner, 2026-11-04). Access: "partner edit everything" (owner, 2026-11-04). "groom is my partner" (owner, 2026-11-04). Manages access too: PD-002 call (a), "yes" (owner, 2026-11-04) |
| Family of the couple: parents (4), siblings (2) | View only, including the budget | Will use the app (same answer). Access: "family view only" (owner, 2026-11-04). Budget: "they can see the budget" (owner, 2026-11-04). Who: "parents 4, siblings 2" (owner, 2026-11-04), 6 people. Dietary notes: "family can see dietary notes" (owner, 2026-11-04) |
| Wedding party (not family) | None for now | "no, just family for now but in the future yes" (owner, 2026-11-04). When they get access, and at what level: [GAP]. The owner will add them later (backlog B22) |

## How the owner works with the team

Owner (one of the couple), 2026-11-04: "dont ask me technical questions as I am not technical and would prefer a user friendly backend with integrations with google suite. route the technical questions to my team but have me approve the recomendation"

- The team (engineering and product agents) settles technical choices. They're brought to the owner as one plain-English recommendation to approve, not as technical questions.
- The owner still decides couple's calls (money, guests, access, vendor contact, cutting features). Those are asked in plain language, with a recommended default where one makes sense.
- The owner prefers a user-friendly app with Google suite integrations. Which Google products, and what each integration should do: [GAP], for a later PD.

## Must-haves before the wedding

Ranked, in the couple's words.

Owner (one of the couple), 2026-11-04: "in depth budgeting, overall planning checklist, guest planning (list, food, seating)"

1. in depth budgeting
2. overall planning checklist
3. guest planning (list, food, seating)
