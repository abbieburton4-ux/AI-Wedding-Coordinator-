from sqlmodel.ext.asyncio.session import AsyncSession
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy import create_engine
from sqlmodel import Session
from typing import AsyncGenerator, Generator
from app.config import settings

# Async Engine and Session for FastAPI endpoints (using SQLModel's AsyncSession subclass)
async_engine = create_async_engine(
    settings.DATABASE_URL,
    echo=False,
    future=True
)

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
    future=True
)

def get_sync_db() -> Generator[Session, None, None]:
    """Dependency for synchronous database sessions (e.g. CLI operations)."""
    with Session(sync_engine) as session:
        try:
            yield session
        finally:
            session.close()
