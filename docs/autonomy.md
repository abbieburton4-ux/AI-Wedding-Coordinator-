# Running the agents on autopilot

The agents work on their own through GitHub Actions (`.github/workflows/claude-agents.yml`). **You don't write issues.** They pick their next task from `docs/backlog.md`, and you only see pull requests. They never merge: every change still needs your click on GitHub.

## How it works

On a schedule (weekdays by default), or whenever you press **Run workflow** in the Actions tab, the autopilot does exactly one thing:

1. **If an agent PR is already open**, it waits for you, and won't pile up work. If you've commented on that PR, it applies your feedback.
2. **If the plan is missing or stale**, it acts as the product lane. It ranks the backlog against your wedding date and must-haves, then opens a docs-only PR with the "Next up" list and **your questions at the top**.
3. **Otherwise it builds the next `ready` item.** It works on a branch, runs the verify gate (the backend verify scripts and the frontend build), has the reviewer agent check its own work, fixes serious findings, and opens one PR with the results.

Your whole job:
- **Read the PR.** Merge it if it's good. If not, comment `@claude <what to change>`.
- **Answer its questions** by commenting `@claude <answer>` on the PR, or by editing `docs/product/wedding.md` on GitHub.
- **Re-import into AI Studio** after merging, if you also edit there.

The first run will mostly ask you questions about the facts still marked `[GAP]` in `docs/product/wedding.md` (for example the exact date and the budget). Filling those in yourself first saves a round trip.

## One-time setup (repo owner; needs admin access)

1. **Merge the CI workflow first** (`.github/workflows/ci.yml`). The agents rely on it to prove their PRs build.
2. **Protect `main`.** Go to Settings → Branches → add a rule for `main`:
   - require a pull request before merging;
   - require the `CI / backend` and `CI / frontend` checks;
   - turn off force pushes.
   
   This is the hard guarantee that nothing reaches `main` without you.
3. **Connect Claude.** In Claude Code, inside this repo, run `/install-github-app`. Choose an API key (`ANTHROPIC_API_KEY`) or your Claude subscription (`CLAUDE_CODE_OAUTH_TOKEN`). If you choose the subscription, change each `anthropic_api_key:` line in the workflow to `claude_code_oauth_token: ${{ secrets.CLAUDE_CODE_OAUTH_TOKEN }}`.
4. **Pick a schedule.** Edit the `cron:` line, or delete it and use only the Run workflow button. Each run costs model usage, capped by `--max-turns` and a 45-minute timeout.
5. **Set a spending limit** in the Claude Console if you use an API key.

## Test it before trusting it

Press **Run workflow** once and check:
- [ ] The Actions log shows Claude reading `CLAUDE.md`, and the run ends with a summary.
- [ ] The plugins install without errors. If one fails, check its marketplace URL and name in the workflow.
- [ ] Any PR comes from a branch named `agent/...`, never from `main`.
- [ ] **CI runs on the agent's PR.** If it doesn't, GitHub may be ignoring pushes made with the workflow's default token. Re-run CI manually, or see "CI not running on Claude's commits" in the Claude Code GitHub Actions docs.
- [ ] A second run while that PR is still open does nothing new.
- [ ] Replying `@claude <answer>` on the PR gets your answer recorded in `docs/product/`.

## What the agents may never do

These rules come from `.agents/AGENTS.md`. Mostly they're instructions the agent follows, not hard limits. The tool list narrows what it can run, and branch protection is the one guarantee: nothing reaches `main` without your click. So read every PR's file list, and be wary of any change to `.github/`, `.claude/` or `.agents/`.
- merge, push to `main`, delete branches, or open more than one PR per run;
- change the workflows, `.claude/settings.json`, the hooks or their own instructions;
- send anything to a real person, take payments, or mark bookings and payments done;
- decide a couple's call (money, guests, vendor contact, access, storage, cutting features). They ask in the PR instead.

## Security

- **Scheduled runs need no outside trigger.** `@claude` replies run only for the repo owner's own comments; the workflow checks the commenter before starting.
- **Post all your answers in one `@claude` comment.** If you post several while a reply is still running on the same PR, GitHub keeps only the newest waiting run, and the answers in between are skipped.
- **Scheduled runs are attributed to whoever last edited the `cron` line,** so that should be a person, not a bot.
- **The plugins are third-party code** installed fresh on every autopilot run, not pinned to a version. Their hooks run outside the agent's tool list, with the job's full access. That means they can read the API key, push to any unprotected branch, and write issues and PRs. Branch protection still stops anything reaching `main` without you. If a plugin's upstream ever looks compromised, disable the workflow and remove it from the `plugins:` list.
- **Review every PR**, especially changes that touch auth, storage or anything that sends.
- Secrets live only in GitHub's repository secrets.

## Stopping it

- To stop one run, cancel it in the Actions tab.
- To pause everything, go to Actions → "Claude agents" → Disable workflow.
- On public repos, GitHub also pauses scheduled workflows after 60 days with no repo activity.
