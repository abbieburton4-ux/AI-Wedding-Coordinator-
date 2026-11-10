"""Check that the Alembic migrations build exactly the schema the models describe.

Runs every migration on a throwaway SQLite database, then asks Alembic to compare
the result with the SQLModel metadata. Any difference means a model changed
without a migration (rule 6).

It also checks that migrations still succeed after Replit's Publish has already
made their schema change in production (B60): migrations after 0006 must use
`migrations/safe_ops.py`, and both the real migrations and a throwaway fixture
migration are run on the normal path and on the "Publish got there first" path.
"""
import ast
import os
import re
import sys
import tempfile
import textwrap

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
from alembic.operations import Operations  # noqa: E402
from alembic.script import ScriptDirectory  # noqa: E402
import sqlalchemy as sa  # noqa: E402
from sqlalchemy import create_engine, inspect, text  # noqa: E402
from sqlmodel import SQLModel  # noqa: E402

import app.db.models  # noqa: E402,F401  (registers every table on the metadata)
from app.config import settings  # noqa: E402
from migrations import safe_ops as safe  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
REPLIT_MD = os.path.join(os.path.dirname(HERE), "replit.md")
# 0001-0006 were written before Publish could run ahead of Alembic and are already
# applied in production; they use op.* directly. Everything after must use safe_ops.
LAST_UNGUARDED = "0006"
# Calls on op / batch_op that a later migration may still make: data steps and
# helpers that change no schema.
ALLOWED_OP_CALLS = {"execute", "get_bind", "get_context", "bulk_insert", "f",
                    "inline_literal"}
RAW_DDL = re.compile(
    r"\b(CREATE|ALTER|DROP)\s+(UNIQUE\s+)?(TABLE|COLUMN|INDEX|CONSTRAINT|TYPE|SEQUENCE"
    r"|VIEW|SCHEMA|DOMAIN|EXTENSION|TRIGGER|FUNCTION)\b|\bRENAME\b"
    r"|\bADD\s+(COLUMN|CONSTRAINT|PRIMARY|FOREIGN|UNIQUE|CHECK)\b",
    re.IGNORECASE)
# SQLAlchemy's own ways to emit DDL, which would also bypass the existence checks.
DDL_NAMES = {"CreateTable", "DropTable", "CreateIndex", "DropIndex", "AddConstraint",
             "DropConstraint", "CreateColumn", "CreateSchema", "DropSchema",
             "CreateSequence", "DropSequence", "DDL"}
DDL_METHODS = {"create", "create_all", "drop", "drop_all"}


def unsafe_calls(source: str) -> list:
    """Schema changes anywhere in a migration module that bypass safe_ops.

    A guard against the usual slips (autogenerate's op.* output, raw DDL in SQL
    text), not proof: review still reads every migration.
    """
    found = []
    tree = ast.parse(source)
    docstrings = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            doc = ast.get_docstring(node, clean=False)
            if doc is not None:
                docstrings.add(doc)
    for node in ast.walk(tree):
        line = getattr(node, "lineno", "?")
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            owner, attr = node.func.value, node.func.attr
            if (isinstance(owner, ast.Name) and owner.id in ("op", "batch_op")
                    and attr not in ALLOWED_OP_CALLS):
                hint = ("call safe.<op> for each change inside it"
                        if attr == "batch_alter_table" else f"use safe.{attr}")
                found.append(f"{owner.id}.{attr} (line {line}); {hint}")
            elif attr in DDL_METHODS and not (isinstance(owner, ast.Name)
                                              and owner.id == "safe"):
                found.append(f".{attr}() (line {line}) emits DDL; use safe_ops")
        if isinstance(node, (ast.Name, ast.Attribute)):
            name = node.id if isinstance(node, ast.Name) else node.attr
            if name in DDL_NAMES:
                found.append(f"{name} (line {line}) emits DDL; use safe_ops")
        if (isinstance(node, ast.Assign) and isinstance(node.value, ast.Name)
                and node.value.id in ("op", "batch_op")):
            found.append(f"alias of {node.value.id} (line {line}) hides its calls")
        if (isinstance(node, ast.Constant) and isinstance(node.value, str)
                and node.value not in docstrings and RAW_DDL.search(node.value)):
            found.append(f"schema change in SQL text (line {line}); use safe_ops")
    return found


def config_for(url: str, extra_versions: str = "") -> Config:
    """An Alembic config aimed at its own database (env.py reads settings at run time)."""
    settings.SYNC_DATABASE_URL = url
    cfg = Config(os.path.join(HERE, "alembic.ini"))
    cfg.set_main_option("script_location", os.path.join(HERE, "migrations"))
    if extra_versions:
        cfg.set_main_option("path_separator", "os")
        cfg.set_main_option("version_locations", os.pathsep.join(
            [os.path.join(HERE, "migrations", "versions"), extra_versions]))
    return cfg


def current_revision(url: str):
    with create_engine(url).connect() as conn:
        return MigrationContext.configure(conn).get_current_revision()


def seed_wedding(url: str) -> None:
    """One fictional couple and wedding, using only columns every revision has.

    Later required columns carry a server default (safe_ops insists), so this
    insert stays valid as migrations are added.
    """
    with create_engine(url).begin() as conn:
        conn.execute(text(
            "INSERT INTO users (id, role, name, email, created_at) "
            "VALUES ('u1', 'couple', 'Test', 'couple@example.test', '2026-01-01')"))
        conn.execute(text(
            "INSERT INTO weddings (id, couple_user_id, region, ceremony_type, "
            "guest_count_estimate, currency, status, created_at) "
            "VALUES ('w1', 'u1', 'Placeholder', 'Civil', 10, 'EUR', 'intake', "
            "'2026-01-01')"))


def schema_of(url: str) -> dict:
    """Tables, columns, indexes and named keys, ignoring alembic_version."""
    with create_engine(url).connect() as conn:
        insp = inspect(conn)
        out = {}
        for t in insp.get_table_names():
            if t == "alembic_version":
                continue
            out[t] = (
                tuple(sorted((c["name"], bool(c["nullable"])) for c in insp.get_columns(t))),
                tuple(sorted(str(i["name"]) for i in insp.get_indexes(t))),
                tuple(sorted(str(fk.get("name")) for fk in insp.get_foreign_keys(t))),
                tuple(sorted(str(u.get("name")) for u in insp.get_unique_constraints(t))),
            )
    return out


def publish_like_replit(dev_url: str, prod_url: str) -> list:
    """Make production's schema match development's, the way Replit's Publish does.

    Publish compares the two databases' schemas, not their data, and generates SQL
    for what production lacks. It copies no rows, so production's alembic_version
    row stays where it was. Only additions are copied: the owner never approves a
    DROP (replit.md). Returns what it added.

    [ASSUMPTION] This stands in for Replit's own SQL on PostgreSQL using Alembic on
    SQLite. It proves the look-then-skip logic and that data steps run once; it
    doesn't model check constraints, enum types, type differences or Replit's
    ordering. It also assumes Publish keeps a foreign key's ON DELETE rule, as the
    stand-in does. A PostgreSQL run is still to do.
    """
    dev_md = sa.MetaData()
    dev_md.reflect(create_engine(dev_url))
    added = []
    with create_engine(prod_url).begin() as conn:
        ops = Operations(MigrationContext.configure(conn))
        for table in dev_md.sorted_tables:
            if table.name == "alembic_version":
                continue
            insp = inspect(conn)
            if not insp.has_table(table.name):
                table.create(conn)
                added.append(f"CREATE TABLE {table.name}")
                continue
            have_cols = {c["name"] for c in insp.get_columns(table.name)}
            for col in table.columns:
                if col.name not in have_cols:
                    default = col.server_default
                    with ops.batch_alter_table(table.name) as b:
                        b.add_column(sa.Column(
                            col.name, col.type, nullable=col.nullable,
                            server_default=sa.text(str(default.arg)) if default else None))
                    added.append(f"ADD COLUMN {table.name}.{col.name}")
            insp = inspect(conn)
            have_ix = {i["name"] for i in insp.get_indexes(table.name)}
            for ix in table.indexes:
                if ix.name not in have_ix:
                    ops.create_index(ix.name, table.name, [c.name for c in ix.columns],
                                     unique=bool(ix.unique))
                    added.append(f"CREATE INDEX {ix.name}")
            have_fk = {fk.get("name") for fk in insp.get_foreign_keys(table.name)}
            have_uq = {u.get("name") for u in insp.get_unique_constraints(table.name)}
            for c in table.constraints:
                if isinstance(c, sa.ForeignKeyConstraint) and c.name not in have_fk:
                    with ops.batch_alter_table(table.name) as b:
                        b.create_foreign_key(c.name, c.referred_table.name,
                                             [x.parent.name for x in c.elements],
                                             [x.column.name for x in c.elements],
                                             ondelete=c.ondelete)
                    added.append(f"ADD CONSTRAINT {c.name}")
                elif isinstance(c, sa.UniqueConstraint) and c.name not in have_uq:
                    with ops.batch_alter_table(table.name) as b:
                        b.create_unique_constraint(c.name, [x.name for x in c.columns])
                    added.append(f"ADD CONSTRAINT {c.name}")
    return added


FIXTURE = '''\
from alembic import op
import sqlalchemy as sa
from migrations import safe_ops as safe

revision = "zz_fixture"
down_revision = {head!r}
branch_labels = None
depends_on = None


def upgrade() -> None:
    safe.create_table(
        "zz_fixture_notes",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("wedding_id", sa.String(), nullable=False),
        sa.Column("body", sa.String(), nullable=False),
        sa.ForeignKeyConstraint(["wedding_id"], ["weddings.id"],
                                name="fk_zz_fixture_notes_wedding_id_weddings"),
        sa.PrimaryKeyConstraint("id", name="pk_zz_fixture_notes"),
    )
    safe.create_index("ix_zz_fixture_notes_wedding_id", "zz_fixture_notes", ["wedding_id"])
    safe.create_unique_constraint("uq_zz_fixture_notes_wedding_id", "zz_fixture_notes",
                                  ["wedding_id", "body"])
    safe.add_column("weddings", sa.Column("zz_fixture_count", sa.Integer(),
                                          nullable=False, server_default="0"))
    # Data steps: Publish copies no rows, so these run only here, on both paths.
    op.execute("INSERT INTO zz_fixture_notes (id, wedding_id, body) "
               "SELECT 'n-' || id, id, 'fixture' FROM weddings")
    op.execute("UPDATE weddings SET zz_fixture_count = 1")


def downgrade() -> None:
    safe.drop_index("ix_zz_fixture_notes_wedding_id", "zz_fixture_notes")
    safe.drop_table("zz_fixture_notes")
    safe.drop_column("weddings", "zz_fixture_count")
'''


def check_fixture_data(url: str) -> None:
    with create_engine(url).connect() as conn:
        notes = conn.execute(text(
            "SELECT id, wedding_id FROM zz_fixture_notes ORDER BY id")).fetchall()
        counts = conn.execute(text("SELECT zz_fixture_count FROM weddings")).fetchall()
    assert [tuple(r) for r in notes] == [("n-w1", "w1")], "the data step ran exactly once"
    assert [tuple(r) for r in counts] == [(1,)], counts


def check_publish_safety(real_head: str, new_revisions: list) -> None:
    work = tempfile.mkdtemp()

    def url(name: str) -> str:
        return f"sqlite:///{os.path.join(work, name + '.db')}"

    print("5. Checking migrations after 0006 change the schema only through safe_ops...")
    problems = []
    for rev in new_revisions:
        with open(rev.path) as fh:
            problems += [f"{os.path.basename(rev.path)}: {p}" for p in unsafe_calls(fh.read())]
    if problems:
        for p in problems:
            print(f"   UNSAFE: {p}")
        raise SystemExit("FAILED: use migrations/safe_ops.py so a publish can't stop the "
                         "app starting (see its docstring).")
    bad = unsafe_calls(textwrap.dedent('''
        """A docstring may say ALTER TABLE."""
        SQL = "CREATE UNIQUE INDEX ix_a ON weddings (region)"

        def _helper():
            op.add_column("weddings", sa.Column("x", sa.Integer()))

        def upgrade():
            """So may this one: DROP TABLE."""
            _helper()
            with op.batch_alter_table("weddings") as batch_op:
                batch_op.drop_column("y")
            op.execute("ALTER TABLE weddings RENAME COLUMN a TO b")
            op.execute(SQL)
            o = op
            sa.Table("t", sa.MetaData()).create(op.get_bind())
            op.execute(sa.schema.CreateTable(t))
            op.execute("UPDATE weddings SET a = 1")
            safe.add_column("weddings", sa.Column("z", sa.Integer()))
    '''))
    flagged = sorted(int(re.search(r"line (\d+)", b).group(1)) for b in bad)
    # One finding per bypass; docstrings, data steps and safe.* calls pass.
    assert flagged == [3, 6, 11, 12, 13, 15, 16, 17], bad
    assert unsafe_calls(FIXTURE.format(head=real_head)) == [], "the fixture is safe"

    print("5b. Checking each migration after 0006 tells the owner what Publish shows...")
    with open(REPLIT_MD) as fh:
        parts = fh.read().split("### What Publish should show", 1)
    assert len(parts) == 2, "replit.md lost its 'What Publish should show' section"
    section = re.split(r"\n## |\n\*\*When you publish\*\*", parts[1], maxsplit=1)[0]
    missing = [r.revision for r in new_revisions if f"`{r.revision}`" not in section]
    if missing:
        raise SystemExit(f"FAILED: add {missing} to replit.md, 'What Publish should show'.")

    print("6. Real migrations: Publish adds the schema first, then the app starts...")
    dev, prod = url("dev"), url("prod")
    command.upgrade(config_for(dev), "head")
    command.upgrade(config_for(prod), LAST_UNGUARDED)
    seed_wedding(prod)
    added = publish_like_replit(dev, prod)
    assert current_revision(prod) == LAST_UNGUARDED, "Publish copies no alembic_version row"
    if not new_revisions:
        assert not added, added
        print("   (no migrations after 0006 yet; the fixture below exercises safe_ops)")
    command.upgrade(config_for(prod), "head")
    assert current_revision(prod) == real_head
    with create_engine(prod).connect() as conn:
        diff = compare_metadata(MigrationContext.configure(conn), SQLModel.metadata)
        # 0007's data step runs after Publish made the table, exactly once.
        venue_rows = conn.execute(text(
            "SELECT wedding_id, name FROM couple_vendors WHERE section = 'venue'")).fetchall()
        # 0009's data step too: the expense, linked to that vendor row, payments unpaid.
        expense = conn.execute(text(
            "SELECT k.name, c.quoted_cents, c.couple_vendor_id FROM budget_costs c "
            "JOIN budget_categories k ON k.id = c.category_id")).fetchall()
        unpaid = conn.execute(text(
            "SELECT COUNT(*) FROM budget_payments WHERE paid = 0")).scalar()
    assert not diff, diff
    assert [tuple(r) for r in venue_rows] == [("w1", "Wildman BT")], venue_rows
    assert [tuple(r) for r in expense] == [
        ("Venue & Catering", 1_200_000, "wildman-bt-w1")], expense
    assert unpaid == 3, unpaid

    print("6a. Real migrations: 0007 already published, then 0008 on its own (B64)...")
    # Development pinned at 0008, so later migrations don't change what this checks.
    dev8, prod7 = url("dev8"), url("prod7")
    command.upgrade(config_for(dev8), "0008")
    command.upgrade(config_for(prod7), LAST_UNGUARDED)
    seed_wedding(prod7)
    command.upgrade(config_for(prod7), "0007")
    added = publish_like_replit(dev8, prod7)
    assert added == ["ADD COLUMN couple_vendors.not_selected"], \
        f"0008 adds one column and nothing else: {added}"
    command.upgrade(config_for(prod7), "head")
    with create_engine(prod7).connect() as conn:
        diff = compare_metadata(MigrationContext.configure(conn), SQLModel.metadata)
        flags = conn.execute(text(
            "SELECT name, status, not_selected FROM couple_vendors")).fetchall()
    assert not diff, diff
    assert [(r[0], r[1], bool(r[2])) for r in flags] == [
        ("Wildman BT", "contacted", False)], flags

    print("6a2. Real migrations: 0008 already published, then 0009 on its own (B65)...")
    dev9, prod8 = url("dev9"), url("prod8")
    command.upgrade(config_for(dev9), "0009")
    command.upgrade(config_for(prod8), LAST_UNGUARDED)
    seed_wedding(prod8)
    command.upgrade(config_for(prod8), "0008")
    added = publish_like_replit(dev9, prod8)
    # What replit.md tells the owner to expect, less the checks this stand-in can't copy.
    assert sorted(added) == sorted(
        [f"ADD COLUMN budget_costs.{c}" for c in (
            "estimated_cents", "final_cents", "contract_status", "payment_method", "notes",
            "link_url", "couple_vendor_id", "archived")]
        + [f"ADD COLUMN budget_payments.{c}" for c in (
            "paid_on", "method", "reference", "notes", "link_url", "refundable")]
        + ["CREATE INDEX ix_budget_costs_couple_vendor_id",
           "ADD CONSTRAINT fk_budget_costs_couple_vendor_id_couple_vendors"]), added
    # The stand-in can't copy checks, so add one by hand as Publish would: the
    # migration must skip it and still add the other two.
    with create_engine(prod8).begin() as conn:
        with Operations.context(MigrationContext.configure(conn)) as ops:
            with ops.batch_alter_table("budget_costs") as b:
                b.create_check_constraint("ck_budget_cost_final",
                                          "final_cents IS NULL OR final_cents >= 0")
    command.upgrade(config_for(prod8), "head")
    with create_engine(prod8).connect() as conn:
        diff = compare_metadata(MigrationContext.configure(conn), SQLModel.metadata)
        expense = conn.execute(text(
            "SELECT vendor_name, couple_vendor_id FROM budget_costs")).fetchall()
        checks = sorted(ck["name"] for ck in inspect(conn).get_check_constraints("budget_costs"))
    assert checks == ["ck_budget_cost_contract", "ck_budget_cost_estimated",
                      "ck_budget_cost_final", "ck_budget_cost_quoted"], checks
    assert not diff, diff
    assert [tuple(r) for r in expense] == [("Wildman BT", "wildman-bt-w1")], expense

    print("6a3. Real migrations: 0009 already published, then 0010 on its own (B67)...")
    dev10, prod9 = url("dev10"), url("prod9")
    command.upgrade(config_for(dev10), "0010")
    command.upgrade(config_for(prod9), LAST_UNGUARDED)
    seed_wedding(prod9)
    command.upgrade(config_for(prod9), "0009")
    added = publish_like_replit(dev10, prod9)
    assert added == ["ADD COLUMN budget_categories.sort_order"], \
        f"0010 adds one column and nothing else: {added}"
    command.upgrade(config_for(prod9), "head")
    with create_engine(prod9).connect() as conn:
        diff = compare_metadata(MigrationContext.configure(conn), SQLModel.metadata)
        order = conn.execute(text(
            "SELECT name, sort_order FROM budget_categories")).fetchall()
    assert not diff, diff
    assert [tuple(r) for r in order] == [("Venue & Catering", 0)], \
        "the data step numbers categories after Publish added the column"

    fixture_dir = os.path.join(work, "fixture_versions")
    os.makedirs(fixture_dir)
    with open(os.path.join(fixture_dir, "zz_fixture.py"), "w") as fh:
        fh.write(FIXTURE.format(head=real_head))

    print("6b. Fixture migration, normal path: nothing pre-applied...")
    normal = url("normal")
    command.upgrade(config_for(normal, fixture_dir), real_head)
    seed_wedding(normal)
    command.upgrade(config_for(normal, fixture_dir), "head")
    assert current_revision(normal) == "zz_fixture"
    check_fixture_data(normal)

    print("6c. Fixture migration, Publish got there first and alembic_version is behind...")
    fdev, fprod = url("fixture_dev"), url("fixture_prod")
    command.upgrade(config_for(fdev, fixture_dir), "head")
    command.upgrade(config_for(fprod, fixture_dir), real_head)
    seed_wedding(fprod)
    added = publish_like_replit(fdev, fprod)
    assert "CREATE TABLE zz_fixture_notes" in added, added
    assert "ADD COLUMN weddings.zz_fixture_count" in added, added
    assert current_revision(fprod) == real_head, "Publish copies no alembic_version row"
    with create_engine(fprod).connect() as conn:
        copied = conn.execute(text("SELECT COUNT(*) FROM zz_fixture_notes")).scalar()
    assert copied == 0, "Publish copies schema, not data"
    command.upgrade(config_for(fprod, fixture_dir), "head")
    assert current_revision(fprod) == "zz_fixture", "the start ends at head"
    check_fixture_data(fprod)
    assert schema_of(fprod) == schema_of(normal) == schema_of(fdev), "same schema both ways"

    print("6d. The fixture migration downgrades cleanly...")
    command.downgrade(config_for(normal, fixture_dir), real_head)
    with create_engine(normal).connect() as conn:
        insp = inspect(conn)
        assert not insp.has_table("zz_fixture_notes")
        assert "zz_fixture_count" not in {c["name"] for c in insp.get_columns("weddings")}

    print("6e. A pre-applied table that doesn't match stops the start instead of guessing...")
    odd = url("mismatch")
    command.upgrade(config_for(odd, fixture_dir), real_head)
    with create_engine(odd).begin() as conn:
        conn.execute(text("CREATE TABLE zz_fixture_notes (id VARCHAR PRIMARY KEY)"))
    try:
        command.upgrade(config_for(odd, fixture_dir), "head")
        raise AssertionError("a mismatched table must stop the migration")
    except RuntimeError as exc:
        assert "different columns" in str(exc), exc
    assert current_revision(odd) == real_head

    # Step 6 shows the accepted case: 0007's table made by Publish with 0008's column,
    # which the models declare. An undeclared column is drift, and a declared one that's
    # required without a default would break the earlier migration's inserts: both stop.
    print("6e2. A pre-applied table with an unexplained or unfillable extra column stops...")
    for n, extra in enumerate(("zz_later INTEGER", "zz_later INTEGER NOT NULL DEFAULT 0")):
        later = url(f"later_{n}")
        command.upgrade(config_for(later, fixture_dir), real_head)
        with create_engine(later).begin() as conn:
            conn.execute(text(
                "CREATE TABLE zz_fixture_notes (id VARCHAR NOT NULL, wedding_id VARCHAR NOT "
                f"NULL, body VARCHAR NOT NULL, {extra}, CONSTRAINT pk_zz_fixture_notes "
                "PRIMARY KEY (id))"))
        try:
            command.upgrade(config_for(later, fixture_dir), "head")
            raise AssertionError(f"a column the models don't declare must stop: {extra}")
        except RuntimeError as exc:
            assert "isn't in the models" in str(exc), (extra, exc)
        assert current_revision(later) == real_head
    early = url("early_required")
    command.upgrade(config_for(early), LAST_UNGUARDED)
    with create_engine(early).begin() as conn:
        conn.execute(text(
            "CREATE TABLE couple_vendors (id VARCHAR NOT NULL, wedding_id VARCHAR NOT NULL, "
            "section VARCHAR NOT NULL, name VARCHAR NOT NULL, website VARCHAR, "
            "contact_name VARCHAR, email VARCHAR, phone VARCHAR, status VARCHAR NOT NULL, "
            "notes TEXT, created_at DATETIME NOT NULL, updated_at DATETIME NOT NULL, "
            "not_selected BOOLEAN NOT NULL, CONSTRAINT pk_couple_vendors PRIMARY KEY (id))"))
    try:
        command.upgrade(config_for(early), "head")
        raise AssertionError("a required later column without a default must stop")
    except RuntimeError as exc:
        assert "required with no default" in str(exc), exc
    assert current_revision(early) == LAST_UNGUARDED

    print("6f. safe_ops refuses changes that Publish couldn't make the same way...")
    with create_engine(odd).begin() as conn:
        with Operations.context(MigrationContext.configure(conn)):
            for attempt, expected in (
                (lambda: safe.add_column("weddings", sa.Column(
                    "zz_required", sa.Integer(), nullable=False)), "server_default"),
                (lambda: safe.alter_column("weddings", "region",
                                           new_column_name="county"), "rename"),
                (lambda: safe.create_index(None, "weddings", ["region"]), "explicit name"),
                (lambda: safe.alter_column("weddings", "budget_total",
                                           nullable=False), "server_default"),
            ):
                try:
                    attempt()
                    raise AssertionError(f"expected a refusal mentioning {expected}")
                except ValueError as exc:
                    assert expected in str(exc), exc


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

    print("3f. Checking that 0007 puts Wildman BT in the Venue section, not booked (B62)...")
    command.downgrade(cfg, "0006")
    command.upgrade(cfg, "head")
    with engine.connect() as conn:
        vendors = conn.execute(text(
            "SELECT wedding_id, section, name, website, status FROM couple_vendors")).fetchall()
    assert [tuple(r) for r in vendors] == [
        ("w1", "venue", "Wildman BT", "https://www.wildmanbt.com/", "contacted")], vendors

    print("3g. Checking that 0008 leaves every existing vendor's status as it was (B64)...")
    command.downgrade(cfg, "0007")
    command.upgrade(cfg, "head")
    with engine.connect() as conn:
        flags = conn.execute(text(
            "SELECT name, status, not_selected FROM couple_vendors")).fetchall()
    assert [(r[0], r[1], bool(r[2])) for r in flags] == [
        ("Wildman BT", "contacted", False)], flags

    print("3h. Checking that 0009 keeps existing expenses and adds Wildman BT unpaid (B65)...")
    command.downgrade(cfg, "0008")
    with engine.begin() as conn:
        # Earlier steps here already ran 0009 on w1; start from an untouched budget.
        for table in ("budget_payments", "budget_costs", "budget_categories"):
            conn.execute(text(f"DELETE FROM {table}"))
        conn.execute(text(
            "INSERT INTO budget_categories (id, wedding_id, name, planned_cents, created_at, "
            "updated_at) VALUES ('cat1', 'w1', ' venue ', 100, '2026-01-01', '2026-01-01')"))
        conn.execute(text(
            "INSERT INTO budget_costs (id, wedding_id, category_id, vendor_name, quoted_cents, "
            "created_at, updated_at) VALUES ('cost1', 'w1', 'cat1', 'Sample Hall', 5000, "
            "'2026-01-01', '2026-01-01')"))
        conn.execute(text(
            "INSERT INTO budget_payments (id, wedding_id, cost_id, kind, amount_cents, due_on, "
            "paid, created_at) VALUES ('pay1', 'w1', 'cost1', 'deposit', 2500, '2026-02-01', "
            "1, '2026-01-01')"))
        conn.execute(text(
            "INSERT INTO weddings (id, couple_user_id, region, ceremony_type, "
            "guest_count_estimate, currency, status, created_at) "
            "VALUES ('w5', 'u1', 'Placeholder', 'Jewish', 10, 'USD', 'intake', '2026-01-01')"))
        # A wedding where the couple typed the venue themselves, under another name.
        conn.execute(text(
            "INSERT INTO weddings (id, couple_user_id, region, ceremony_type, "
            "guest_count_estimate, currency, status, created_at) "
            "VALUES ('w6', 'u1', 'Placeholder', 'Jewish', 10, 'USD', 'intake', '2026-01-01')"))
        conn.execute(text(
            "INSERT INTO budget_categories (id, wedding_id, name, created_at, updated_at) "
            "VALUES ('cat6', 'w6', 'Hall', '2026-01-01', '2026-01-01')"))
        conn.execute(text(
            "INSERT INTO budget_costs (id, wedding_id, category_id, vendor_name, "
            "created_at, updated_at) VALUES ('cost6', 'w6', 'cat6', 'Wildman B.T. venue', "
            "'2026-01-01', '2026-01-01')"))
    command.upgrade(cfg, "head")
    with engine.begin() as conn:
        w6 = conn.execute(text(
            "SELECT COUNT(*) FROM budget_costs WHERE wedding_id = 'w6'")).scalar()
        w6_cats = conn.execute(text(
            "SELECT COUNT(*) FROM budget_categories WHERE wedding_id = 'w6'")).scalar()
        conn.execute(text("DELETE FROM budget_costs WHERE wedding_id = 'w6'"))
        conn.execute(text("DELETE FROM budget_categories WHERE wedding_id = 'w6'"))
        conn.execute(text("DELETE FROM weddings WHERE id = 'w6'"))
    assert (w6, w6_cats) == (1, 1), "an expense the couple typed is never doubled"

    def wildman(conn, wedding_id):
        cost = conn.execute(text(
            "SELECT c.id, k.name, c.quoted_cents, c.estimated_cents, c.final_cents, "
            "c.contract_status, c.couple_vendor_id, c.archived FROM budget_costs c "
            "JOIN budget_categories k ON k.id = c.category_id "
            "WHERE c.wedding_id = :w AND c.vendor_name = 'Wildman BT'"),
            {"w": wedding_id}).fetchall()
        assert len(cost) == 1, cost
        pays = conn.execute(text(
            "SELECT kind, amount_cents, due_on, refundable, paid, paid_at, paid_on "
            "FROM budget_payments WHERE cost_id = :c ORDER BY due_on, amount_cents DESC"),
            {"c": cost[0][0]}).fetchall()
        return tuple(cost[0][1:]), [(r[0], r[1], r[2], bool(r[3]), bool(r[4]), r[5], r[6])
                                    for r in pays]

    expected_pays = [
        ("deposit", 600_000, "2026-11-11", False, False, None, None),
        ("payment", 600_000, "2027-09-23", False, False, None, None),
        ("deposit", 200_000, "2027-09-23", True, False, None, None),
    ]
    with engine.connect() as conn:
        kept = conn.execute(text(
            "SELECT vendor_name, quoted_cents, estimated_cents, final_cents, contract_status, "
            "archived, couple_vendor_id FROM budget_costs WHERE id = 'cost1'")).fetchall()
        kept_pay = conn.execute(text(
            "SELECT amount_cents, paid, refundable, paid_on FROM budget_payments "
            "WHERE id = 'pay1'")).fetchall()
        w1_vendor = conn.execute(text(
            "SELECT id FROM couple_vendors WHERE wedding_id = 'w1' AND name = 'Wildman BT'"
        )).scalar()
        w1_cost, w1_pays = wildman(conn, "w1")
        w5_cost, w5_pays = wildman(conn, "w5")
        w5_categories = conn.execute(text(
            "SELECT name, planned_cents FROM budget_categories WHERE wedding_id = 'w5'"
        )).fetchall()
        checks = {ck["name"] for ck in inspect(conn).get_check_constraints("budget_costs")}
    assert [(r[0], r[1], r[2], r[3], r[4], bool(r[5]), r[6]) for r in kept] == [
        ("Sample Hall", 5000, None, None, "none", False, None)], kept
    assert [(r[0], bool(r[1]), bool(r[2]), r[3]) for r in kept_pay] == [
        (2500, True, False, None)], "an existing paid tick is kept, and not refundable"
    assert w1_cost == (" venue ", 1_200_000, None, None, "none", w1_vendor, 0), w1_cost
    assert w1_vendor and w1_pays == expected_pays, w1_pays
    assert w5_cost == ("Venue & Catering", 1_200_000, None, None, "none", None, 0), w5_cost
    assert w5_pays == expected_pays, w5_pays
    assert [tuple(r) for r in w5_categories] == [("Venue & Catering", None)], w5_categories
    assert {"ck_budget_cost_quoted", "ck_budget_cost_estimated", "ck_budget_cost_final",
            "ck_budget_cost_contract"} <= checks, f"checks survive the table copy: {checks}"
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "m0009", os.path.join(HERE, "migrations", "versions", "0009_budget_expenses.py"))
    m0009 = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m0009)
    with engine.begin() as conn:
        before = conn.execute(text("SELECT COUNT(*) FROM budget_payments")).scalar()
        m0009.add_wildman_bt(conn)
        after = conn.execute(text("SELECT COUNT(*) FROM budget_payments")).scalar()
    assert before == after == 7, "running the data step again adds nothing"
    try:
        with engine.begin() as conn:
            conn.execute(text("UPDATE budget_costs SET contract_status = 'accepted' "
                              "WHERE id = 'cost1'"))
        raise AssertionError("contract status is none, sent or signed")
    except sa.exc.IntegrityError:
        pass
    with engine.begin() as conn:
        conn.execute(text("DELETE FROM budget_payments WHERE wedding_id = 'w5'"))
        conn.execute(text("DELETE FROM budget_costs WHERE wedding_id = 'w5'"))
        conn.execute(text("DELETE FROM budget_categories WHERE wedding_id = 'w5'"))
        conn.execute(text("DELETE FROM weddings WHERE id = 'w5'"))

    print("3i. Checking that 0010 numbers categories in the order they were added (B67)...")
    command.downgrade(cfg, "0009")
    with engine.begin() as conn:
        # Added out of id order, so the numbering must follow created_at, not ids.
        for cid, wid, created in (("cat_c", "w1", "2026-03-01"), ("cat_b", "w1", "2026-02-01"),
                                  ("cat_z", "w7", "2026-01-05")):
            if wid == "w7" and not conn.execute(text(
                    "SELECT 1 FROM weddings WHERE id = 'w7'")).first():
                conn.execute(text(
                    "INSERT INTO weddings (id, couple_user_id, region, ceremony_type, "
                    "guest_count_estimate, currency, status, created_at) VALUES ('w7', 'u1', "
                    "'Placeholder', 'Jewish', 10, 'USD', 'intake', '2026-01-01')"))
            conn.execute(text(
                "INSERT INTO budget_categories (id, wedding_id, name, planned_cents, "
                "created_at, updated_at) VALUES (:id, :w, :id, 5, :t, :t)"),
                {"id": cid, "w": wid, "t": created})
        cats_before = conn.execute(text(
            "SELECT id, name, planned_cents FROM budget_categories ORDER BY id")).fetchall()
        costs_before = conn.execute(text(
            "SELECT id, category_id FROM budget_costs ORDER BY id")).fetchall()
    command.upgrade(cfg, "head")

    def numbered(conn):
        return [tuple(r) for r in conn.execute(text(
            "SELECT wedding_id, id, sort_order FROM budget_categories "
            "ORDER BY wedding_id, sort_order"))]
    with engine.connect() as conn:
        first = numbered(conn)
        cats_after = conn.execute(text(
            "SELECT id, name, planned_cents FROM budget_categories ORDER BY id")).fetchall()
        costs_after = conn.execute(text(
            "SELECT id, category_id FROM budget_costs ORDER BY id")).fetchall()
    assert first == [("w1", "cat1", 0), ("w1", "cat_b", 1), ("w1", "cat_c", 2),
                     ("w7", "cat_z", 0)], first
    assert cats_after == cats_before and costs_after == costs_before, \
        "names, targets and expenses stay as they are"
    spec = importlib.util.spec_from_file_location(
        "m0010", os.path.join(HERE, "migrations", "versions", "0010_budget_category_order.py"))
    m0010 = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m0010)
    with engine.begin() as conn:
        m0010.number_categories(conn)
        assert numbered(conn) == first, "running the data step again changes nothing"
        # The couple reorder, then a row arrives without a number: only it is numbered,
        # after theirs, and their order is kept.
        conn.execute(text("UPDATE budget_categories SET sort_order = 7 WHERE id = 'cat1'"))
        conn.execute(text(
            "INSERT INTO budget_categories (id, wedding_id, name, created_at, updated_at) "
            "VALUES ('cat_new', 'w1', 'New', '2026-01-01', '2026-01-01')"))
        m0010.number_categories(conn)
        assert numbered(conn) == [("w1", "cat_b", 1), ("w1", "cat_c", 2), ("w1", "cat1", 7),
                                  ("w1", "cat_new", 8), ("w7", "cat_z", 0)], numbered(conn)
        for cid in ("cat_b", "cat_c", "cat_z", "cat_new"):
            conn.execute(text("DELETE FROM budget_categories WHERE id = :c"), {"c": cid})
        conn.execute(text("DELETE FROM weddings WHERE id = 'w7'"))

    print("4. Downgrading to the start and back up again...")
    command.downgrade(cfg, "base")
    command.upgrade(cfg, "head")

    scripts = ScriptDirectory.from_config(cfg)
    real_head = scripts.get_current_head()
    new_revisions = [r for r in scripts.walk_revisions(LAST_UNGUARDED, real_head)
                     if r.revision != LAST_UNGUARDED]
    check_publish_safety(real_head, new_revisions)

    print("--- MIGRATION VERIFICATION SUCCESS ---")


if __name__ == "__main__":
    main()
