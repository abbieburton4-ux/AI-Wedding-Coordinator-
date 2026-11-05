---
name: Gemini model availability
description: Why model discovery alone is insufficient when checking Gemini configuration
---

Validate a Gemini model with a small real generation request before claiming
that configured credentials and model selection work. A model appearing in the
provider's list is not enough.

**Why:** During production setup, model discovery advertised a model that returned
HTTP 404 on generation; a latest-model alias also failed, while a different
explicit model completed a live request.

**How to apply:** Distinguish credential errors from model-specific availability
errors, use the live provider list to choose candidates, and test the chosen
model without sending wedding or guest information. Keep selection configurable
instead of assuming an older default remains usable.
