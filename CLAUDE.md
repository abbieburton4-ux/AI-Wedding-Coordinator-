# CLAUDE.md

@.agents/AGENTS.md

## Claude Code specifics

The shared instructions above apply in full. This section only adds what is particular to Claude Code. Shared skills live in `.agents/skills/` and are symlinked into `.claude/skills/`. Edit the originals, never the links.

- **Independent review before "done".** For any change beyond a typo, run the `reviewer` subagent on the diff before reporting completion, and fix or report its blocking findings. It applies the `review` skill with a fresh context, so you don't grade your own work.
- **Product questions go to the `product-lead` subagent** (or the `product-call` skill when you're already in the product lane). Engineering sessions don't edit `docs/product/`.
- **Parallel subagents do no git.** The main session is the only git operator. Subagents return findings or edit the files they're assigned; you stage, commit and branch.
- **Memory**: save the user's preferences and feedback to Claude's memory. Project facts belong in the repo (`docs/product/wedding.md`, decisions, backlog), where every agent, including the AI Studio one, can read them.
