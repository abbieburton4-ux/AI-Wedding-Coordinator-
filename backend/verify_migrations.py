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
from sqlalchemy import create_engine, inspect, text  # noqa: E402
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

    print("2b. Checking every key, unique and check constraint has a name...")
    with engine.connect() as conn:
        insp = inspect(conn)
        unnamed = []
        for table in insp.get_table_names():
            if table == "alembic_version":
                continue
            if not insp.get_pk_constraint(table).get("name"):
                unnamed.append(f"{table} primary key")
            unnamed += [f"{table} FK {fk['constrained_columns']}"
                        for fk in insp.get_foreign_keys(table) if not fk.get("name")]
            unnamed += [f"{table} unique {uq['column_names']}"
                        for uq in insp.get_unique_constraints(table) if not uq.get("name")]
            # No "ck" convention exists, so each check constraint must be named by hand.
            unnamed += [f"{table} check {ck['sqltext']}"
                        for ck in insp.get_check_constraints(table) if not ck.get("name")]
    if unnamed:
        for u in unnamed:
            print(f"   UNNAMED: {u}")
        raise SystemExit("FAILED: constraints without a name can't be altered or dropped later.")

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

    print("3b. Checking that 0003 leaves existing weddings with no budget total set...")
    with engine.connect() as conn:
        totals = conn.execute(text("SELECT budget_total_cents FROM weddings")).fetchall()
    assert [tuple(r) for r in totals] == [(None,)], totals

    print("3c. Checking that 0004 adds the checklist and keeps the old timeline rows...")
    command.downgrade(cfg, "0003")
    with engine.begin() as conn:
        conn.execute(text(
            "INSERT INTO timeline_items (id, wedding_id, kind, title, due_at, status, "
            "created_at) VALUES ('ti1', 'w1', 'planning', 'Placeholder', '2027-01-01', "
            "'todo', '2026-01-01')"
        ))
        conn.execute(text(
            "INSERT INTO weddings (id, couple_user_id, region, ceremony_type, "
            "guest_count_estimate, budget_total, currency, status, created_at, wedding_date) "
            "VALUES ('w2', 'u1', 'Sligo', 'Civil', 10, 1000.0, 'EUR', 'intake', "
            "'2026-01-01', '2027-08-21')"
        ))
    command.upgrade(cfg, "head")
    with engine.connect() as conn:
        dates = conn.execute(text(
            "SELECT wedding_date_set_on, checklist_imported_at FROM weddings "
            "WHERE id = 'w1'")).fetchall()
        dated = conn.execute(text(
            "SELECT wedding_date_set_on FROM weddings WHERE id = 'w2'")).scalar()
        conn.execute(text("DELETE FROM weddings WHERE id = 'w2'"))
        conn.commit()
        kept = conn.execute(text("SELECT id FROM timeline_items")).fetchall()
        tasks = conn.execute(text("SELECT COUNT(*) FROM checklist_tasks")).scalar()
    assert [tuple(r) for r in dates] == [(None, None)], dates
    from app.utils.checklist import wedding_today
    assert dated == wedding_today().isoformat(), "a dated wedding counts from the migration day"
    assert [tuple(r) for r in kept] == [("ti1",)], "the import merges these, not the migration"
    assert tasks == 0, tasks

    print("3d. Checking that 0005 keeps budgets and allows a blank one (PD-009)...")
    with engine.begin() as conn:
        kept_budget = conn.execute(text(
            "SELECT budget_total FROM weddings WHERE id = 'w1'")).scalar()
        conn.execute(text(
            "INSERT INTO weddings (id, couple_user_id, region, ceremony_type, "
            "guest_count_estimate, budget_total, currency, status, created_at) "
            "VALUES ('w3', 'u1', 'Placeholder', 'Jewish', 10, NULL, 'USD', 'intake', "
            "'2026-01-01')"
        ))
    assert kept_budget == 1000.0, kept_budget
    try:
        command.downgrade(cfg, "0004")
        raise AssertionError("downgrading past 0005 must refuse while a budget is blank")
    except RuntimeError as exc:
        assert "no intake budget" in str(exc), exc
    with engine.begin() as conn:
        still_there = conn.execute(text("SELECT COUNT(*) FROM weddings")).scalar()
        conn.execute(text("DELETE FROM weddings WHERE id = 'w3'"))
    assert still_there == 2, "a refused downgrade leaves every row in place"

    print("3e. Checking that 0006 leaves every existing wedding's date unconfirmed (B48)...")
    command.downgrade(cfg, "0005")
    command.upgrade(cfg, "head")
    with engine.begin() as conn:
        confirmed = conn.execute(text(
            "SELECT id, wedding_date_confirmed FROM weddings ORDER BY id")).fetchall()
        conn.execute(text(
            "INSERT INTO weddings (id, couple_user_id, region, ceremony_type, "
            "guest_count_estimate, currency, status, created_at) "
            "VALUES ('w4', 'u1', 'Placeholder', 'Jewish', 10, 'USD', 'intake', '2026-01-01')"
        ))
        new_row = conn.execute(text(
            "SELECT wedding_date_confirmed FROM weddings WHERE id = 'w4'")).scalar()
        conn.execute(text("DELETE FROM weddings WHERE id = 'w4'"))
    assert [(r[0], bool(r[1])) for r in confirmed] == [("w1", False)], confirmed
    assert bool(new_row) is False, "a row added outside the app still starts unconfirmed"

    print("4. Downgrading to the start and back up again...")
    command.downgrade(cfg, "base")
    command.upgrade(cfg, "head")

    print("--- MIGRATION VERIFICATION SUCCESS ---")


if __name__ == "__main__":
    main()
