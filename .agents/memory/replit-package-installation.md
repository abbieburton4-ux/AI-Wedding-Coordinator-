---
name: Replit dependency installation constraints
description: Package-security and runtime compatibility lessons for this imported project
---

For this nested frontend, evaluate package-security fixes against the existing
Node runtime rather than blindly adopting the newest Firebase major.

**Why:** During Replit setup, upgrading Firebase to its latest major still pulled
the blocked transitive packages and additionally required a newer Node engine.
Compatible patched transitive versions allowed the original frontend stack to run.

**How to apply:** Try the direct parent's maintained release first, check engine
requirements, and use narrowly scoped patched transitive overrides only when the
parent still depends on affected versions. Never bypass the package firewall.
