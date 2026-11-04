from sqlmodel.ext.asyncio.session import AsyncSession
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy import create_engine, event
from sqlmodel import Session
from typing import AsyncGenerator, Generator
from app.config import settings

# SQLite (local dev) only allows a single writer, so the concurrent agent
# cascade (venue + supplier matchers firing at once) hits "database is locked".
# WAL mode + a generous busy_timeout makes writers wait for the lock instead of
# failing. Postgres (Docker/prod) needs none of this, so it's gated on the URL.
IS_SQLITE = settings.DATABASE_URL.startswith("sqlite")
_sqlite_connect_args = {"timeout": 30} if IS_SQLITE else {}


def _apply_sqlite_pragmas(dbapi_conn, _record):
    cur = dbapi_conn.cursor()
    cur.execute("PRAGMA journal_mode=WAL;")
    cur.execute("PRAGMA busy_timeout=30000;")
    cur.execute("PRAGMA synchronous=NORMAL;")
    cur.close()


# Async Engine and Session for FastAPI endpoints (using SQLModel's AsyncSession subclass)
async_engine = create_async_engine(
    settings.DATABASE_URL,
    echo=False,
    future=True,
    connect_args=_sqlite_connect_args,
)
if IS_SQLITE:
    event.listens_for(async_engine.sync_engine, "connect")(_apply_sqlite_pragmas)

async_session_maker = sessionmaker(
    bind=async_engine,
    class_=AsyncSession,
    expire_on_commit=False
)

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency for providing database sessions to FastAPI routes."""
    async with async_session_maker() as session:
        try:
            yield session
        finally:
            await session.close()

# Sync Engine and Session for migrations, seeding, and management scripts
sync_engine = create_engine(
    settings.SYNC_DATABASE_URL,
    echo=False,
    future=True,
    connect_args={"timeout": 30} if settings.SYNC_DATABASE_URL.startswith("sqlite") else {},
)
if settings.SYNC_DATABASE_URL.startswith("sqlite"):
    event.listens_for(sync_engine, "connect")(_apply_sqlite_pragmas)

def get_sync_db() -> Generator[Session, None, None]:
    """Dependency for synchronous database sessions (e.g. CLI operations)."""
    with Session(sync_engine) as session:
        try:
            yield session
        finally:
            session.close()
