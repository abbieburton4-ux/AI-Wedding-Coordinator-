import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from app.config import settings

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Any number that is unique to this app; it serialises migrations across instances.
_MIGRATION_LOCK_ID = 7_340_211


def _refuse_unversioned_schema(engine) -> None:
    """Stop if app tables exist that Alembic has no record of.

    That happens when something other than Alembic built the schema, such as a
    publish-time schema sync. Upgrading from scratch would fail half way, and
    guessing a revision could skip a data step, so a person has to look.
    """
    from sqlalchemy import inspect, text
    from sqlmodel import SQLModel

    tables = set(inspect(engine).get_table_names())
    if not tables & set(SQLModel.metadata.tables):
        return
    version = None
    if "alembic_version" in tables:
        with engine.connect() as conn:
            version = conn.execute(text("SELECT version_num FROM alembic_version")).scalar()
    if version is None:
        raise RuntimeError(
            "The database has app tables but no Alembic migration record, so it wasn't "
            "built by the migrations. Refusing to start. See replit.md, 'Database schema'."
        )


def apply_migrations() -> None:
    """Bring the schema to the latest Alembic revision (rule 6).

    Alembic's env.py connects through settings.SYNC_DATABASE_URL, the same URL
    sync_engine is built from, so the checks and the lock see the same database.
    """
    import os
    from alembic import command
    from alembic.config import Config
    from sqlalchemy import text
    from app.db.session import sync_engine as engine

    _refuse_unversioned_schema(engine)
    backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    alembic_cfg = Config(os.path.join(backend_dir, "alembic.ini"))
    alembic_cfg.set_main_option("script_location", os.path.join(backend_dir, "migrations"))

    def upgrade() -> None:
        try:
            command.upgrade(alembic_cfg, "head")
        except Exception as exc:
            # Typically "already exists": something other than Alembic changed the
            # schema. On PostgreSQL the upgrade is one transaction, so nothing half-applies.
            raise RuntimeError(
                "Database migration failed; the app will not start on a schema it "
                "can't vouch for. See replit.md, 'Database schema'."
            ) from exc

    logger.info("Applying database migrations...")
    if engine.dialect.name != "postgresql":
        upgrade()
        return
    # Autoscale can start several instances at once; only one may migrate.
    with engine.connect() as lock_conn:
        lock_conn.execute(text("SELECT pg_advisory_lock(:id)"), {"id": _MIGRATION_LOCK_ID})
        try:
            upgrade()
        finally:
            lock_conn.execute(text("SELECT pg_advisory_unlock(:id)"), {"id": _MIGRATION_LOCK_ID})


def on_startup():
    """DB initialisation and seeding of the vendor catalogue."""
    from sqlmodel import SQLModel
    from app.db.session import sync_engine
    from app.db.seed import seed_database

    if settings.REPLIT_MANAGED_DATABASE and (
        settings.DEVELOPMENT_MODE or settings.ALLOW_MOCK_AUTH
    ):
        raise RuntimeError("Managed real-access databases must not enable demo flags.")

    if settings.DEVELOPMENT_MODE and settings.FIREBASE_PROJECT_ID:
        # Dev mode switches off every secret check (worker routes, webhooks, wedding
        # creation). Pointing it at a real sign-in project is almost always a mistake.
        logger.warning(
            "DEVELOPMENT_MODE is on with a real FIREBASE_PROJECT_ID. Worker routes, "
            "webhooks and wedding creation are unprotected. Never run this way with real data."
        )
    if settings.DEVELOPMENT_MODE:
        # Local throwaway databases: build tables straight from the models.
        logger.info("Development mode: creating tables from models...")
        SQLModel.metadata.create_all(sync_engine)
    else:
        # Anywhere real data lives, Replit included, the schema only changes
        # through migrations (rule 6).
        apply_migrations()
    logger.info("Database schema ready.")

    # Automatically seed if database is empty
    try:
        seed_database()
    except Exception as e:
        logger.error(f"Error during startup database seeding: {e}")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    # on_event is deprecated in the FastAPI/Starlette versions Replit installs.
    on_startup()
    yield


app = FastAPI(
    title="VenueFlow API",
    description="Backend API and Agent Worker for VenueFlow - AI Wedding Coordinator",
    version="1.0.0",
    lifespan=lifespan,
)

# Configure CORS dynamically for local Vite development and deployed GitHub Pages
app.add_middleware(
    CORSMiddleware,
    allow_origins=[] if settings.FRONTEND_DIST_DIR else [
        "https://alanmaizon.github.io",
        "http://localhost:5173",
        "http://127.0.0.1:5173"
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=[
        "Content-Type", 
        "Authorization", 
        "X-Idempotency-Key", 
        "X-Requested-With",
        "Accept"
    ],
)

# Include Routers
from app.api.v1.endpoints import weddings, webhooks, auth, inquiries, voice, members, budget
from app.worker import tasks

app.include_router(auth.router, prefix="/api/v1/auth", tags=["Auth"])
app.include_router(weddings.router, prefix="/api/v1/weddings", tags=["Weddings"])
app.include_router(members.router, prefix="/api/v1/weddings", tags=["Access"])
app.include_router(budget.router, prefix="/api/v1/weddings", tags=["Budget"])
app.include_router(inquiries.router, prefix="/api/v1/inquiries", tags=["Inquiries"])
app.include_router(voice.router, prefix="/api/v1/voice", tags=["Voice"])
app.include_router(webhooks.router, prefix="/api/v1/webhooks", tags=["Webhooks"])
app.include_router(tasks.router, prefix="/tasks", tags=["Worker Tasks"])

@app.get("/")
def read_root():
    if settings.FRONTEND_DIST_DIR:
        from pathlib import Path
        return FileResponse(Path(settings.FRONTEND_DIST_DIR) / "index.html")
    return {
        "status": "healthy",
        "service": "VenueFlow Backend",
        "environment": "development" if settings.DEVELOPMENT_MODE else "production"
    }

@app.get("/api/v1/health")
@app.get("/api/health")
@app.get("/health")
def read_health():
    return {
        "status": "healthy",
        "service": "VenueFlow Backend",
        "environment": "development" if settings.DEVELOPMENT_MODE else "production"
    }
