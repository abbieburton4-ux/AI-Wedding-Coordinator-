"""Say whether the app's database is at the latest migration, or bring it there.

Replit's Publish compares the development database with production and offers to
make production match. If development is behind the code's migrations, that offer
undoes them (B59), so the workspace database has to be at head before publishing.

    python db_status.py check     # exit 0 at head, 1 behind, 2 anything else
    python db_status.py upgrade   # apply the migrations, then check

Run from backend/ against the app's own database (DATABASE_URL). It never prints
the connection URL. `check` changes nothing; `upgrade` only runs the migrations.
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.realpath(os.path.dirname(__file__)))

from alembic.config import Config  # noqa: E402
from alembic.migration import MigrationContext  # noqa: E402
from alembic.script import ScriptDirectory  # noqa: E402
from sqlalchemy.engine import make_url  # noqa: E402

from app.config import settings  # noqa: E402

AT_HEAD, BEHIND, OTHER = 0, 1, 2


def _scripts() -> ScriptDirectory:
    here = os.path.realpath(os.path.dirname(__file__))
    cfg = Config(os.path.join(here, "alembic.ini"))
    cfg.set_main_option("script_location", os.path.join(here, "migrations"))
    return ScriptDirectory.from_config(cfg)


def same_database() -> bool:
    """The app reads through DATABASE_URL but migrates through SYNC_DATABASE_URL.

    A stray SYNC_DATABASE_URL (for example from a copied backend/.env) would send
    the migrations to a different database from the one the app serves.
    """
    def target(url: str) -> tuple:
        u = make_url(url)
        backend = "postgresql" if u.get_backend_name() == "postgres" else u.get_backend_name()
        port = u.port or (5432 if backend == "postgresql" else None)
        return backend, u.host, port, u.database

    return target(settings.DATABASE_URL) == target(settings.SYNC_DATABASE_URL)


def database_status(engine=None) -> tuple[int, str]:
    if engine is None:
        from app.db.session import sync_engine as engine
    if not same_database():
        return OTHER, (
            "SYNC_DATABASE_URL points at a different database from DATABASE_URL, so "
            "migrations would not reach the app's database. Remove SYNC_DATABASE_URL "
            "(and any backend/.env) on Replit; the app derives it."
        )
    scripts = _scripts()
    head = scripts.get_current_head()
    with engine.connect() as conn:
        current = MigrationContext.configure(conn).get_current_revision()
    if current == head:
        return AT_HEAD, f"Database is up to date (migration {head})."
    if current is None:
        return OTHER, (
            f"Database has no migration record; the code is at {head}. "
            "Don't publish. Ask the team."
        )
    known = {rev.revision for rev in scripts.walk_revisions()}
    if current not in known:
        return OTHER, (
            f"Database is at {current}, which this code doesn't know (the code is "
            f"at {head}). Pull the latest code. Don't publish."
        )
    return BEHIND, (
        f"Database is behind: at {current}, the code is at {head}. Don't publish. "
        "Run `alembic upgrade head` from backend/, or stop and press Run again."
    )


def upgrade() -> tuple[int, str]:
    if not same_database():
        return database_status()
    from app.main import apply_migrations

    apply_migrations()
    return database_status()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("action", choices=["check", "upgrade"])
    args = parser.parse_args()
    try:
        code, message = database_status() if args.action == "check" else upgrade()
    except RuntimeError as exc:
        # apply_migrations refused (no Alembic record, or a migration failed).
        # The cause (e.g. "column already exists") names no password, and the
        # deploy log is the only place anyone can see why the start was refused.
        cause = exc.__cause__
        detail = f" Cause: {type(cause).__name__}: {cause}" if cause else ""
        code, message = OTHER, f"{exc}{detail} Don't publish."
    print(message)
    sys.exit(code)


if __name__ == "__main__":
    main()
