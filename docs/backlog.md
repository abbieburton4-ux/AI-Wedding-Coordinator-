# Backlog — Known Gaps

Tracked here so debt is visible. **Each item: what, where, why deferred, when to address.** Add new entries with date + reviewer; close them by deleting the entry and referencing the fixing commit.

Convention: also drop a `# TODO(name, YYYY-MM-DD):` comment at the code site for in-flight items. The Friday review pass should reconcile this file against `grep -rn TODO`.

---

## Open

### B1 · `intake_planner` / matchers don't pre-validate `wedding_id` before pending-log INSERT
**Where:** [streamlit_mock/agents.py:118](../streamlit_mock/agents.py#L118) and equivalent in `run_venue_matcher`, `run_supplier_matcher`.
**What:** The pending-log INSERT references `wedding_id` as an FK. If the caller passes a bogus ID, the INSERT itself fails with `IntegrityError` *before* the try/except can run. Test `test_intake_planner_no_orphan_pending_on_missing_wedding` documents the invariant that no orphan rows appear, but the mechanism is "INSERT was rejected," not "row was opened and updated."
**Why deferred:** Streamlit UI only passes IDs from a dropdown of existing weddings, so the production hit-rate is near zero. `quote_extractor` already does pre-INSERT validation for missing bookings — the inconsistency is the bug, not a live failure.
**Fix shape:** Add a `SELECT 1 FROM weddings WHERE id = ?` check before the pending-log INSERT in all three agents. If missing, raise `ValueError("wedding not found")` immediately — caller gets a clean error, no log row, no FK surprise.
**Surfaced by:** Code review 2026-05-27 · commit `4c3412f6` body.

### B2 · `quote_extractor` falls through to `category="venue"` for any non-supplier booking
**Where:** [streamlit_mock/agents.py:735](../streamlit_mock/agents.py#L735)
**What:** `category = booking["supplier_category"] if booking["supplier_id"] else "venue"`. Fine today because the DB `CHECK` constraint enforces venue XOR supplier. If a future booking type lands (bundle, multi-vendor) this silently routes to "venue" budget-line lookups.
**Why deferred:** No live failure mode in the current schema. Belongs in the post-Day-30 refactor.
**Fix shape:** Add an explicit `else: raise ValueError(...)` branch, or refactor to a switch on booking type when bundles arrive.
**Surfaced by:** Code review 2026-05-27 · M3.

### B3 · Category enum still split across 3 files
**Where:** [agents.py:18](../streamlit_mock/agents.py#L18) (set + derived SUPPLIER_CATEGORIES), [db.py:178](../streamlit_mock/db.py#L178) (SQL column comment), the `INSERT` order column comment.
**What:** Down from 4 places to 3 after [`36806099`](#) made the Pydantic description derived. The remaining drift surface is just doc comments — low risk, but a clean fix would move the constant to `streamlit_mock/constants.py` and import everywhere including db.py for table-creation docstrings.
**Why deferred:** Pure refactor, no behavior change. Pick up when next touching db.py for the Postgres migration.
**Surfaced by:** Code review 2026-05-27 · M1.

### B4 · Matcher pre-filter uses string equality on region — no canonical region mapping
**Where:** [streamlit_mock/agents.py:369](../streamlit_mock/agents.py#L369) (and equivalent in `run_supplier_matcher`)
**What:** `v["region"].lower() == preferred_region.lower()` — a couple selecting "Leinster" never matches a venue tagged "Meath" (which is *in* Leinster). The C2 fix expanded the dropdown to cover the seeded counties, but there's no province→county mapping. A future couple selecting "Munster" or "Connacht" province wouldn't match any venue.
**Why deferred:** The current dropdown only offers values that have at least one matching seeded venue, so the fallback path always trips and the LLM rescues it. Not a live break.
**Fix shape:** Add an `IRISH_REGION_HIERARCHY` mapping (provinces → counties → venues), use a `region_matches()` helper for the pre-filter.
**Surfaced by:** C2 follow-through.

### B5 · 273-line refactors land in single commits — bisect-hostile
**Where:** Process, not code. See [commit 874e42ca](#).
**What:** The pending-log fix touched all four agents in one diff. If any agent's behavior regresses, a `git bisect` can't isolate which agent caused it without unpicking the commit.
**Why deferred:** Hackathon pace — acceptable trade-off when shipping fast. Worth a habit shift, not a rewrite.
**Fix shape:** **Convention to follow going forward** — refactors that touch >100 lines across multiple subjects split into one commit per subject (one per agent, one per page, etc.).
**Surfaced by:** Code review 2026-05-27 · M4.

---

## Recently closed

| Closed | Item | Resolved by |
|---|---|---|
| 2026-05-27 | Tab 1 plotly Gold crash | [`2032afa6`](#) |
| 2026-05-27 | Region dropdown vs. seed county mismatch | [`2032afa6`](#) |
| 2026-05-27 | Supplier dropdown hardcoded to 4 categories | [`2ba17b20`](#) |
| 2026-05-27 | Case-sensitive whitelist false positives | [`61f34bb2`](#) |
| 2026-05-27 | No test coverage for whitelist + missing wedding | [`4c3412f6`](#) |
| 2026-05-27 | Bare `except:` in log viewer | [`36806099`](#) |
| 2026-05-27 | Pydantic Field description hardcoded | [`36806099`](#) |

---

## Review schedule

- **Friday afternoons:** founders reconcile open items against actual commits and close anything resolved.
- **Before each pilot demo:** scan B1–B5 for anything that could surface in a live walkthrough.
- **Before submission (Aug 17):** every B-item must either be closed or have an explicit "post-submission" note.
