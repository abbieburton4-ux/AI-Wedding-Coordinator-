#!/usr/bin/env python3
"""PreToolUse guard for Bash: block commands that bypass this repo's safety gates.

Permission deny rules match only the literal command text, so they miss forms like
`git -C . push --force`. This hook normalizes and checks the command instead.
Exit 2 blocks the call and shows stderr to Claude; exit 0 lets it through.
"""
import json
import re
import sys

try:
    cmd = json.load(sys.stdin).get("tool_input", {}).get("command", "")
except Exception:
    sys.exit(0)

# Drop quoted strings (commit messages etc.) so their text can't trigger a match,
# then collapse `git -C <path>` / `git -c k=v` so the subcommand is matched reliably.
norm = re.sub(r"\"(\\.|[^\"\\])*\"|'[^']*'", "''", cmd)
norm = re.sub(r"\bgit(\s+-[Cc]\s+\S+)+", "git", norm)

checks = [
    (r"\bgit\b.*\s--no-verify\b", "--no-verify skips the gitleaks secret scan (AGENTS.md rule 5)."),
    (r"\bgit\s+commit\b.*\s-n(\s|$)", "-n is --no-verify; it skips the gitleaks secret scan."),
    (r"\bgit\s+push\b.*(\s--force\b|\s--force-with-lease\b|\s-f(\s|$)|\s\+\S)", "Force-push rewrites history; ask the user to do it if truly needed."),
    (r"\bgit\s+push\b.*(\s|:)(refs/heads/)?main(\s|$)", "Never push to main directly; push a branch and open a PR."),
    (r"(^|[\s/<])\.env(\.local|\.production|\.development|\.[\w-]+\.local)?(\s|$|[;|&>])", "Don't read or write real .env files; they hold secrets. Use .env.example."),
]
for pattern, reason in checks:
    if re.search(pattern, norm):
        print(f"Blocked by .claude/hooks/guard-bash.py: {reason}", file=sys.stderr)
        sys.exit(2)
sys.exit(0)
