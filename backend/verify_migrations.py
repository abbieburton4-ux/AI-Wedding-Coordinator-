"""Check that the Alembic migrations build exactly the schema the models describe.

Runs every migration on a throwaway SQLite database, then asks Alembic to compare
the result with the SQLModel metadata. Any difference means a model changed
without a migration (rule 6).
"""
import os
import sys
import tempfile

tmp_dir = tempfile.mkdtemp()
db_path = os.path.join(tmp_dir, "migrations_test.db")
os.environ["SYNC_DATABASE_URL"] = f"sqlite:///{db_path}"
os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{db_path}"
os.environ.setdefault("GEMINI_API_KEY", "dummy")

sys.path.insert(0, os.path.realpath(os.path.dirname(__file__)))

from alembic import command  # noqa: E402
from alembic.autogenerate import compare_metadata  # noqa: E402
from alembic.config import Config  # noqa: E402
from alembic.migration import MigrationContext  # noqa: E402
from sqlalchemy import create_engine, text  # noqa: E402
from sqlmodel import SQLModel  # noqa: E402

import app.db.models  # noqa: E402,F401  (registers every table on the metadata)


def main() -> None:
    here = os.path.dirname(os.path.abspath(__file__))
    cfg = Config(os.path.join(here, "alembic.ini"))
    cfg.set_main_option("script_location", os.path.join(here, "migrations"))

    print("1. Applying all migrations to an empty database...")
    command.upgrade(cfg, "head")

    print("2. Comparing the migrated schema with the models...")
    engine = create_engine(os.environ["SYNC_DATABASE_URL"])
    with engine.connect() as conn:
        diff = compare_metadata(MigrationContext.configure(conn), SQLModel.metadata)
    if diff:
        for d in diff:
            print(f"   DIFF: {d}")
        raise SystemExit("FAILED: models and migrations differ; add a migration.")

    print("3. Checking that 0002 makes each existing couple their wedding's owner...")
    command.downgrade(cfg, "0001")
    with engine.begin() as conn:
        conn.execute(text(
            "INSERT INTO users (id, role, name, email, created_at) "
            "VALUES ('u1', 'couple', 'Test', 'Couple@Example.test', '2026-01-01')"
        ))
        conn.execute(text(
            "INSERT INTO weddings (id, couple_user_id, region, ceremony_type, "
            "guest_count_estimate, budget_total, currency, status, created_at) "
            "VALUES ('w1', 'u1', 'Sligo', 'Civil', 10, 1000.0, 'EUR', 'intake', '2026-01-01')"
        ))
    command.upgrade(cfg, "head")
    with engine.connect() as conn:
        rows = conn.execute(text(
            "SELECT wedding_id, email, level, user_id FROM wedding_members"
        )).fetchall()
    assert [tuple(r) for r in rows] == [("w1", "couple@example.test", "owner", "u1")], rows

    print("4. Downgrading to the start and back up again...")
    command.downgrade(cfg, "base")
    command.upgrade(cfg, "head")

    print("--- MIGRATION VERIFICATION SUCCESS ---")


if __name__ == "__main__":
    main()
