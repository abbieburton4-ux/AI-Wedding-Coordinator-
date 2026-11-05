"""Load the owner's planning checklist into a wedding, once (PD-007).

The owner's list comes from their own file, which stays outside git (its wording is
from a wedding website). The import also adds the approved Jewish traditions and
merges the AI planner's old timeline into the checklist, then removes the timeline.
Run it against the database the app uses (SYNC_DATABASE_URL), only when the owner
has asked. Without --apply it's a dry run: it does the whole import, prints what
would change, and then undoes it.

    python manage_checklist.py import --wedding <id> --file <path> [--wedding-date YYYY-MM-DD] [--apply]
"""
import argparse
import datetime
import os
import sys

sys.path.insert(0, os.path.realpath(os.path.dirname(__file__)))

from sqlmodel import Session  # noqa: E402

from app.db.models import Wedding  # noqa: E402
from app.db.session import sync_engine  # noqa: E402
from app.utils.checklist_import import ImportRefused, import_checklist, read_owner_list  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("action", choices=["import"])
    parser.add_argument("--wedding", required=True)
    parser.add_argument("--file", required=True, help="the owner's checklist file")
    parser.add_argument("--wedding-date", type=datetime.date.fromisoformat,
                        help="set the (provisional) wedding date the due dates count from")
    parser.add_argument("--apply", action="store_true", help="save the import")
    args = parser.parse_args()

    try:
        owner_list = read_owner_list(args.file)
    except (OSError, ImportRefused) as e:
        raise SystemExit(f"Refused: {e}")

    with Session(sync_engine) as session:
        wedding = session.get(Wedding, args.wedding)
        if not wedding:
            raise SystemExit(f"No wedding with id {args.wedding}")
        try:
            report = import_checklist(session, wedding, owner_list, args.wedding_date)
        except ImportRefused as e:
            session.rollback()
            raise SystemExit(f"Refused: {e}")

        print(f"Wedding date: {report.wedding_date or 'not set'}")
        print(f"Owner's list tasks added: {report.owner_tasks}")
        print(f"Jewish tradition tasks added: {report.tradition_tasks}")
        print(f"AI timeline tasks added: {len(report.ai_added)}")
        for line in report.ai_added:
            print(f"  + {line}")
        print(f"AI timeline tasks skipped as duplicates: {len(report.ai_skipped)}")
        for line in report.ai_skipped:
            print(f"  = {line}")
        print(f"Old timeline rows removed: {report.timeline_rows_removed}")

        if args.apply:
            session.commit()
            print("Saved.")
        else:
            session.rollback()
            print("Dry run: nothing was saved. Add --apply to save.")


if __name__ == "__main__":
    main()
