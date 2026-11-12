"""Stop a Replit publish whose workspace database is behind the code (B86).

Replit's Publish makes production's schema match the workspace's development
database. If that database is behind the code's migrations, the SQL it applies
undoes them in production, deleting what they added (B59, B70, B86). Replit runs
the publish build before it applies that SQL, so failing the build stops the
publish before production changes.

The build can't query the workspace database, so `db_status.py` records the
revision it last saw there in REVISION_FILE, and this check compares that with the
code's latest migration. Standard library only, so it runs before any install.

    python publish_guard.py    # exit 0 if the workspace database was at head
"""
import os
import re
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
VERSIONS_DIR = HERE / "migrations" / "versions"
# Written by db_status.py in the workspace; Git-ignored, so it never leaves it.
REVISION_FILE = HERE / "workspace_db_revision.txt"

_REVISION = re.compile(r"^revision\s*(?::[^=]*)?=\s*['\"]([^'\"]+)['\"]", re.M)
_DOWN = re.compile(r"^down_revision\s*(?::[^=]*)?=\s*(\([^)]*\)|.+)$", re.M)
# The watcher's catch-up may land between Replit's comparison and this build.
RECENT_AUTO_SECONDS = 15 * 60
_QUOTED = re.compile(r"['\"]([^'\"]+)['\"]")

FIX = (
    "Nothing in the published app or its database has changed. In the workspace, "
    "open the Shell and type: cd backend && python db_status.py upgrade  "
    "When it says 'Database is up to date', press Publish again."
)


def code_revisions(versions_dir: Path = VERSIONS_DIR) -> tuple[set[str], str]:
    """Every migration revision in the code, and the single head."""
    revisions, parents = set(), set()
    for path in sorted(versions_dir.glob("*.py")):
        text = path.read_text(encoding="utf-8")
        rev = _REVISION.search(text)
        if not rev:
            continue
        revisions.add(rev.group(1))
        down = _DOWN.search(text)
        if down:
            parents.update(_QUOTED.findall(down.group(1)))
    heads = revisions - parents
    if len(heads) != 1:
        raise SystemExit(f"Publish stopped: the code has {len(heads)} latest migrations, "
                         "not one. Tell the team.")
    return revisions, heads.pop()


def check(revision_file: Path = REVISION_FILE,
          versions_dir: Path = VERSIONS_DIR) -> tuple[bool, str]:
    known, head = code_revisions(versions_dir)
    if not revision_file.exists():
        return False, (
            "Publish stopped: the workspace hasn't recorded where its database is, so "
            "Replit might offer to undo changes in the published app. " + FIX
        )
    recorded = revision_file.read_text(encoding="utf-8").strip().splitlines()
    current = recorded[0].strip() if recorded else ""
    auto = recorded[1].split() if len(recorded) > 1 else []
    if current == head and len(auto) == 2 and auto[0] == "auto" and auto[1].isdigit() \
            and time.time() - int(auto[1]) < RECENT_AUTO_SECONDS:
        return False, (
            "Publish stopped: the workspace database caught up with the code by itself "
            "only minutes ago, so the changes Replit listed may have been worked out "
            "before it did. " + FIX
        )
    if current == head:
        return True, f"Workspace database is up to date (migration {head}); publishing."
    if current in known:
        return False, (
            f"Publish stopped: the workspace database is behind the code (it's at "
            f"migration {current}, the code is at {head}), so Replit would undo the "
            f"newer changes in the published app. " + FIX
        )
    return False, (
        f"Publish stopped: the workspace database is in a state the code doesn't "
        f"expect ({current or 'empty'}; the code is at {head}). Tell the team."
    )


def main() -> None:
    ok, message = check()
    print(message, file=sys.stdout if ok else sys.stderr)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    os.chdir(HERE)
    main()
