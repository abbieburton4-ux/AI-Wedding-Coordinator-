import sys
import os
from logging.config import fileConfig

from sqlalchemy import engine_from_config
from sqlalchemy import pool
from alembic import context

# Add app to path so we can import app config and db models
sys.path.insert(0, os.path.realpath(os.path.join(os.path.dirname(__file__), "..")))

# this is the Alembic Config object
config = context.config

# Interpret the config file for Python logging
if config.config_file_name is not None:
    fileConfig(config.config_file_name, disable_existing_loggers=False)

# Import SQLModel and all model classes so they register on metadata
from sqlmodel import SQLModel
from app.db.models import (
    User, Wedding, Venue, Supplier, VenueAvailability, SupplierAvailability,
    Booking, Quote, Contract, Payment, Subscription, SupplierPayment,
    BudgetLine, TimelineItem, Guest, AgentDecisionLog, WeddingMember
)
from app.config import settings

# Target metadata for autogenerate support
target_metadata = SQLModel.metadata

# Overwrite the ini file connection URL with our dynamic sync database URL
# Escape % so configparser interpolation leaves URL-encoded passwords alone.
config.set_main_option("sqlalchemy.url", settings.SYNC_DATABASE_URL.replace("%", "%%"))


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "pyformat"},
        # SQLite can't ALTER most columns or constraints; batch mode copies the table.
        render_as_batch=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        if connection.dialect.name == "postgresql":
            # Every app process runs migrations at startup; this lock makes the
            # others wait instead of racing to create the same tables.
            connection.exec_driver_sql("SELECT pg_advisory_lock(727304201)")
            connection.commit()
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            render_as_batch=True,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
