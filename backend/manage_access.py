"""Add, change or remove someone on a wedding's access list (PD-002).

A stop-gap for the team until the owner's settings screen exists (backlog B22).
Run it against the database the app uses (SYNC_DATABASE_URL), only when the owner
has asked for the change. It never contacts anyone; tell the person yourself.

    python manage_access.py list   --wedding <id>
    python manage_access.py set    --wedding <id> --email <email> --level viewer|editor|owner
    python manage_access.py remove --wedding <id> --email <email>
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.realpath(os.path.dirname(__file__)))

from sqlmodel import Session, select  # noqa: E402

from app.db.models import ACCESS_LEVELS, Wedding, WeddingMember  # noqa: E402
from app.db.session import sync_engine  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("action", choices=["list", "set", "remove"])
    parser.add_argument("--wedding", required=True)
    parser.add_argument("--email")
    parser.add_argument("--level", choices=ACCESS_LEVELS)
    args = parser.parse_args()

    with Session(sync_engine) as session:
        if not session.get(Wedding, args.wedding):
            raise SystemExit(f"No wedding with id {args.wedding}")

        if args.action == "list":
            rows = session.exec(
                select(WeddingMember).where(WeddingMember.wedding_id == args.wedding)
            ).all()
            for row in rows:
                state = "signed in" if row.user_id else "not signed in yet"
                print(f"{row.level:7}  {row.email}  ({state})")
            return

        if not args.email:
            raise SystemExit("--email is required")
        email = args.email.strip().lower()
        row = session.exec(
            select(WeddingMember).where(
                WeddingMember.wedding_id == args.wedding, WeddingMember.email == email
            )
        ).first()

        owners = session.exec(
            select(WeddingMember).where(
                WeddingMember.wedding_id == args.wedding, WeddingMember.level == "owner"
            )
        ).all()
        is_last_owner = row is not None and row.level == "owner" and len(owners) == 1

        if args.action == "remove":
            if not row:
                raise SystemExit(f"{email} isn't on this wedding's list")
            if is_last_owner:
                raise SystemExit("Refusing to remove the last owner")
            session.delete(row)
            session.commit()
            print(f"Removed {email}")
            return

        if not args.level:
            raise SystemExit("--level is required")
        if is_last_owner and args.level != "owner":
            raise SystemExit("Refusing to demote the last owner")
        if row:
            row.level = args.level
        else:
            # Left unlinked on purpose: the row attaches to an account only when that
            # person signs in with this email verified (app.api.v1.access.link_memberships).
            row = WeddingMember(wedding_id=args.wedding, email=email, level=args.level)
        session.add(row)
        session.commit()
        print(f"{email} is now {args.level}")


if __name__ == "__main__":
    main()
