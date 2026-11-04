# CLAUDE.md

@.agents/AGENTS.md

## Claude Code specifics

The shared instructions above apply in full. This section only adds what is particular to Claude Code. Shared skills live in `.agents/skills/` and are symlinked into `.claude/skills/`. Edit the originals, never the links.

- **Independent review before "done".** For any change beyond a typo, run the `reviewer` subagent on the diff before reporting completion, and fix or report its blocking findings. It applies the `review` skill with a fresh context, so you don't grade your own work. Add specialist reviewers from the table below when the diff touches their area; they run in parallel with `reviewer`. Subagents can't spawn subagents, so you orchestrate them.
- **Product questions go to the `product-lead` subagent** (or the `product-call` skill when you're already in the product lane). Engineering sessions don't edit `docs/product/`.
- **Default session: the product lead.** Plain `claude` opens as the `product-lead` agent (the `agent` setting in `.claude/settings.json`). The owner talks product, and the product lead hands ratified items to the `engineer`, which builds in the background in its own worktree and returns a summary and a PR link. For a hands-on coding session, start one explicitly with `claude --agent engineer`, or remove the `agent` setting.
- **Who runs git.** The `engineer` commits and pushes only its own `agent/...` branch, inside its worktree. The product lead commits only `docs/product/**` and `docs/backlog.md`, on a `product/...` branch. Other subagents do no git. Nobody merges or pushes to `main`.
- **The Bash guard.** `.claude/hooks/guard-bash.py` blocks force-pushes, pushes to `main`, `--no-verify` and `.env` access. If it blocks something the owner really wants, ask them to run it themselves with `!`.
- **Memory**: save the user's preferences and feedback to Claude's memory. Project facts belong in the repo (`docs/product/wedding.md`, decisions, backlog), where every agent, including the AI Studio one, can read them.

## Using installed plugins

The installed plugins supply the **method**; this repo's rules decide **what must be true**. When they conflict, the order is `.agents/AGENTS.md`, then the repo's own skills, then plugin skills. For example:
- a plugin flow that merges, pushes to `main`, sends anything, or commits without the owner's go-ahead (outside autopilot) is overridden;
- when `superpowers:finishing-a-development-branch` asks, choose "open a PR";
- `compound-engineering:lfg` runs only within "Working unattended".

**For multi-step work, check the live `Skill` and `Agent` inventory first.** The names below are current examples, not a fixed roster. If one is missing, use the fallback, and never fake its output.

| Capability | Reach for | Fallback |
|---|---|---|
| Shape a vague request | `superpowers:brainstorming` or `ce-brainstorm`, then `product-call` for any couple's call | `product-call` |
| Plan multi-step work | `superpowers:writing-plans` or `ce-plan`; execute with `ce-work` or `superpowers:executing-plans` | a plan in the PR description |
| Debug | `superpowers:systematic-debugging` or `ce-debug` | — |
| UI design and polish | `impeccable` (`audit`, `critique`, `polish`) and `frontend-design`; reference screens via the mobbin MCP if connected | AGENTS.md frontend traps |
| A visual mock of a proposed feature, so the couple can see it before deciding | `stageshow` (installed in this repo). The engineer builds it on a throwaway `agent/mock-B<n>` branch, outside `frontend/src/`, labelled as a mock, and returns a still image. Never merged, and never shown as the real app or real data | a written description in the PD |
| Accessibility, forms, microcopy | `critique-accessibility`, `critique-forms`, `critique-microcopy` | `review` step 4 |
| Browser check of UI changes (there's no test runner) | `ce-dogfood` or `ce-test-browser` on the changed routes | `verify` step 6 by hand |
| Specialist review, alongside `reviewer` | sign-in, access, keys or anything client-exposed: `security-reviewer` / `security-sentinel` (compound-engineering). Storage, schema or migrations: `data-integrity-guardian`. User flows: `spec-flow-analyzer`. General diff: `ce-code-review` or `pr-review-toolkit` | `review` |
| Before claiming done | `superpowers:verification-before-completion`, plus the repo's `verify` | `verify` |
| Product decisions and backlog | `pm-skills` (`define-problem-statement`, `define-prioritization-framework`, `deliver-acceptance-criteria`, `deliver-edge-cases`); `utility-pm-critic` adversarial pass on any `proposed` PD; `ce-doc-review` on decision docs | `product-call` |
| Vendor research | `web-researcher` (compound-engineering). Run WebSearch in the main thread if a subagent lacks it; cite everything per `add-vendors` | WebSearch + `add-vendors` |
| Capture a lesson so it sticks | `ce-compound`: turn it into a rule here, a check, or a skill edit | a note in the PR |
| Prose the couple will read | `ce-noslop`, `critique-clarity` | — |

- **Not routed:** `marketing-skills`, because a private wedding app has no marketing, SEO or growth work. `stageshow` is also not for the landing or hero pages, which are legacy surfaces under PD-001, unless the owner asks. `rampstack-*` overlaps the above; use it only when the owner asks.
- **Name the skills and agents you used** in the PR description, so the owner can see what shaped the change. There's no quota: use one skill when one fits.
