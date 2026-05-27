# Backlog — Known Gaps

Tracked here so debt is visible. **Each item: what, where, why deferred, when to address.** Add new entries with date + reviewer; close them by deleting the entry and referencing the fixing commit.

Convention: also drop a `# TODO(name, YYYY-MM-DD):` comment at the code site for in-flight items. The Friday review pass should reconcile this file against `grep -rn TODO`.

---

## Open

*(nothing currently — last sweep closed B1–B5 on 2026-05-27)*

---

## Recently closed

| Closed | Item | Resolved by |
|---|---|---|
| 2026-05-27 | Tab 1 plotly Gold crash | `2032afa6` |
| 2026-05-27 | Region dropdown vs. seed county mismatch | `2032afa6` |
| 2026-05-27 | Supplier dropdown hardcoded to 4 categories | `2ba17b20` |
| 2026-05-27 | Case-sensitive whitelist false positives | `61f34bb2` |
| 2026-05-27 | No test coverage for whitelist + missing wedding | `4c3412f6` |
| 2026-05-27 | Bare `except:` in log viewer | `36806099` |
| 2026-05-27 | Pydantic Field description hardcoded | `36806099` |
| 2026-05-27 | **B3** — category enum in 3 places | `8911810a` |
| 2026-05-27 | **B4** — no Irish region hierarchy for matcher pre-filter | `c42db925` |
| 2026-05-27 | **B1** — agents don't pre-validate `wedding_id` | `b02dbde1` |
| 2026-05-27 | **B2** — `quote_extractor` category fallthrough to 'venue' | `1eab8426` |
| 2026-05-27 | **B5** — refactor commit hygiene (convention codified) | `af97128b` |

---

## Review schedule

- **Friday afternoons:** founders reconcile open items against actual commits and close anything resolved.
- **Before each pilot demo:** scan open items for anything that could surface in a live walkthrough.
- **Before submission (Aug 17):** every open item must either be closed or have an explicit "post-submission" note.
