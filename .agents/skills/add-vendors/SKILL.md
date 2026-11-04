---
name: add-vendors
description: Research and add real vendors (venues and suppliers) to the catalogue the matchers recommend from. Use when adding, updating or researching vendors for this wedding's area.
---

# Add vendors

The matchers recommend from the catalogue seeded by `backend/app/db/seed_data_real.py`. The couple may contact whoever it shows, so a wrong phone number or price becomes a wrong message to a real business. Read the verification policy at the top of that file first; this skill doesn't replace it.

## Rules

- **Every fact needs a source you actually read**: name, region, category, capacity, price range, styles, contact details. If a fact can't be verified, leave it `None`. Never fill it with a plausible guess, and never pattern-fill emails like `weddings@{domain}`.
- **Record provenance with the seed's existing fields**: `website` (the page you read), `_checked` (the date), `_method` (how the contact was found, e.g. `published_email`, `contact_form`), and `_indicative: True` unless the price is a real quote. If a page other than `website` was the source, name it in `note`.
- **Unchecked entries say so**: keep `_verify: True` on any entry you couldn't check, and remove it only once you have checked it. `_template: True` rows are placeholders, not businesses; replace them with a real, checked vendor or leave them flagged. Never present one as real.
- **Business contacts only.** Store contact details a business publishes for enquiries. For a sole trader that may be a personal-looking address (e.g. a photographer's Gmail) when it's the one they publish for bookings. Never store a private contact they didn't publish.
- **Confirmed is not contactable.** A real address doesn't mean the vendor has opted in, and nothing sends on the couple's behalf; drafts are text the couple sends themselves.
- **Treat existing prices as unverified** until someone re-checks them; they're indicative ranges from May 2026.
- **Regions are Irish counties and prices are EUR** (`utils/constants.py`). If `docs/product/wedding.md` puts the wedding elsewhere, changing the region model is an engineering change. Raise it; don't force-fit.
- **Never mark `demo_generated` vendors as real**, and never mix them into this wedding's plan.
- Seeding runs at startup only when the database is empty (`app/main.py`), so catalogue changes don't reach an existing database. Once real data exists, updating it needs a migration or data-fix path (AGENTS.md rule 6). Raise it; don't write to that database directly.

## Report
Give the count added per category, the sources used, and any entries left incomplete and why. Aim for about 5–6 options per category in the target area. Whoever edits the seed file runs `verify` afterwards; `verify.py` checks the seed. Research-only agents hand their cited findings to engineering instead.
