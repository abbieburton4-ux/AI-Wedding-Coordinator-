"""Schema operations for migrations that still work after Replit's Publish (B60).

Publish makes the production database's schema match the development database
before the new version starts. It copies the schema, not the data, so production's
`alembic_version` row stays behind and Alembic then runs the same migration on
start. A plain `op.add_column` would fail there with "already exists", and the
published app would refuse to start.

Every migration after 0006 makes its schema changes through these functions
instead of `op.*` / `batch_op.*` (`verify_migrations.py` refuses raw calls). Each
one looks first and skips work that is already done, so a migration succeeds on
both paths:

- normal: the database is at the previous revision and nothing was pre-applied;
- pre-applied: Publish already made the change, but `alembic_version` is behind.

What this means for writing a migration:

- Data steps (`op.execute`, `op.get_bind()`) run only through Alembic, after the
  schema change, on both paths. Write them to work on the new schema; never read
  a column or table the same migration drops, because Publish may have dropped it
  already. Move data in one migration and drop the old place in a later one.
- Never rename a table or column. Publish asks "rename or new?" and the owner
  can't safely answer it. Add the new name, copy the data, and drop the old one in
  a later release.
- A new required (NOT NULL) column on an existing table needs a server default,
  or Publish's own SQL fails on production's existing rows. That holds for
  making an existing column required with `alter_column` too.
- If an object is already there but doesn't match (a table with different
  columns, a column with different nullability), the migration stops rather than
  guess. A person then has to look; nothing is changed past that point on
  PostgreSQL, where the upgrade is one transaction.
- Drops and `alter_column` changes appear on the publish screen as DROP or ALTER
  COLUMN, and the owner is told to stop on those (replit.md). A release with one
  can't be published by the owner alone: someone from the team reads the SQL with
  her first. Prefer additions.

The existence checks compare names and nullability, not types, defaults or
check-constraint text, and are tested on SQLite only (`verify_migrations.py`).
[ASSUMPTION] Publish creates objects under the names the development database
has, which Alembic gave them, so name checks find them on PostgreSQL too.

Only online migrations are supported (they inspect the live database).
"""
import logging
from typing import Optional, Sequence

import sqlalchemy as sa
from alembic import op

logger = logging.getLogger("alembic.runtime.migration")


def _inspector() -> sa.engine.Inspector:
    # A fresh inspector each time: its cache would miss changes made earlier in the
    # same migration.
    return sa.inspect(op.get_bind())


def _skip(what: str) -> None:
    logger.info("%s is already there (for example, Publish applied it); skipping.", what)


def _require_name(name: Optional[str], what: str) -> str:
    if not name:
        raise ValueError(f"{what} needs an explicit name so its existence can be checked.")
    return name


def _has_table(table: str) -> bool:
    return _inspector().has_table(table)


def _columns(table: str) -> dict:
    return {c["name"]: c for c in _inspector().get_columns(table)}


def _index_names(table: str) -> set:
    insp = _inspector()
    return {i["name"] for i in insp.get_indexes(table)}


def _constraint_names(table: str) -> set:
    insp = _inspector()
    names = {fk.get("name") for fk in insp.get_foreign_keys(table)}
    names |= {uq.get("name") for uq in insp.get_unique_constraints(table)}
    names |= {ck.get("name") for ck in insp.get_check_constraints(table)}
    names.add(insp.get_pk_constraint(table).get("name"))
    # PostgreSQL lists a unique constraint's backing index as an index too.
    names |= _index_names(table)
    names.discard(None)
    return names


def create_table(name: str, *columns_and_constraints, **kw) -> None:
    """`op.create_table`, skipped when the table is already there with the same columns."""
    if _has_table(name):
        wanted = {c.name: bool(c.nullable) for c in columns_and_constraints
                  if isinstance(c, sa.Column)}
        present = {n: bool(c["nullable"]) for n, c in _columns(name).items()}
        if wanted != present:
            differ = sorted(set(wanted.items()) ^ set(present.items()))
            raise RuntimeError(
                f"Table {name} already exists with different columns "
                f"(name, nullable) {differ}. Refusing to guess; ask the team."
            )
        _skip(f"Table {name}")
        return
    op.create_table(name, *columns_and_constraints, **kw)


def add_column(table: str, column: sa.Column) -> None:
    """`op.add_column`, skipped when the column is already there with the same nullability."""
    if not column.nullable and column.server_default is None:
        raise ValueError(
            f"{table}.{column.name} is required but has no server_default. Publish adds "
            "it the same way and would fail on production's existing rows."
        )
    existing = _columns(table).get(column.name)
    if existing is not None:
        if bool(existing["nullable"]) != bool(column.nullable):
            raise RuntimeError(
                f"Column {table}.{column.name} already exists but its nullability differs. "
                "Refusing to guess; ask the team."
            )
        _skip(f"Column {table}.{column.name}")
        return
    with op.batch_alter_table(table) as batch_op:
        batch_op.add_column(column)


def create_index(name: str, table: str, columns: Sequence, unique: bool = False, **kw) -> None:
    """`op.create_index`, skipped when an index of that name is already on the table."""
    _require_name(name, "An index")
    if name in _index_names(table):
        _skip(f"Index {name}")
        return
    op.create_index(name, table, list(columns), unique=unique, **kw)


def create_unique_constraint(name: str, table: str, columns: Sequence) -> None:
    _require_name(name, "A unique constraint")
    if name in _constraint_names(table):
        _skip(f"Constraint {name}")
        return
    with op.batch_alter_table(table) as batch_op:
        batch_op.create_unique_constraint(name, list(columns))


def create_foreign_key(name: str, source_table: str, referent_table: str,
                       local_cols: Sequence, remote_cols: Sequence, **kw) -> None:
    _require_name(name, "A foreign key")
    if name in _constraint_names(source_table):
        _skip(f"Constraint {name}")
        return
    with op.batch_alter_table(source_table) as batch_op:
        batch_op.create_foreign_key(name, referent_table, list(local_cols),
                                    list(remote_cols), **kw)


def create_check_constraint(name: str, table: str, condition) -> None:
    _require_name(name, "A check constraint")
    if name in _constraint_names(table):
        _skip(f"Constraint {name}")
        return
    with op.batch_alter_table(table) as batch_op:
        batch_op.create_check_constraint(name, condition)


def alter_column(table: str, column: str, **kw) -> None:
    """`alter_column` for type, nullability or default. Setting the same value twice is
    harmless, so it always runs. Renames are refused (see the module docstring)."""
    if kw.get("new_column_name"):
        raise ValueError("Don't rename columns in a migration; add, copy, then drop later.")
    if kw.get("nullable") is False and kw.get("server_default") is None:
        raise ValueError(
            f"Making {table}.{column} required needs a server_default too, or Publish's "
            "own ADD COLUMN would fail on production's existing rows.")
    with op.batch_alter_table(table) as batch_op:
        batch_op.alter_column(column, **kw)


def drop_column(table: str, column: str) -> None:
    if column not in _columns(table):
        _skip(f"Removal of column {table}.{column}")
        return
    with op.batch_alter_table(table) as batch_op:
        batch_op.drop_column(column)


def drop_table(name: str) -> None:
    if not _has_table(name):
        _skip(f"Removal of table {name}")
        return
    op.drop_table(name)


def drop_index(name: str, table: str) -> None:
    if name not in _index_names(table):
        _skip(f"Removal of index {name}")
        return
    op.drop_index(name, table_name=table)


def drop_constraint(name: str, table: str, type_: str) -> None:
    if name not in _constraint_names(table):
        _skip(f"Removal of constraint {name}")
        return
    with op.batch_alter_table(table) as batch_op:
        batch_op.drop_constraint(name, type_=type_)
