from pydantic_settings import BaseSettings
from typing import Optional
from pydantic import model_validator
from sqlalchemy.engine import make_url

class Settings(BaseSettings):
    # Databases: async for FastAPI, sync for Alembic/seeding
    DATABASE_URL: str = "postgresql+asyncpg://venueflow:venueflow_pass@db/venueflow"
    SYNC_DATABASE_URL: Optional[str] = None
    # Set by the Replit run script: real data, so demo flags are refused at startup.
    REPLIT_MANAGED_DATABASE: bool = False
    FRONTEND_DIST_DIR: Optional[str] = None
    # Request-bound execution requires no external queue and never acknowledges
    # work before it runs. The Docker development emulator remains available.
    DIRECT_AGENT_EXECUTION: bool = False
    
    # API Keys & Auth
    GEMINI_API_KEY: Optional[str] = None
    # Only set this if something mints HS256 tokens (the legacy pilot script). No default:
    # a committed default would let anyone sign tokens (PD-002).
    JWT_SECRET: Optional[str] = None
    # The couple's own Firebase project. No default: an unset value refuses Firebase
    # sign-in instead of trusting someone else's project (PD-002).
    FIREBASE_PROJECT_ID: Optional[str] = None

    # Shared secrets for routes only our services or providers call. Unset means those
    # routes refuse every call outside DEVELOPMENT_MODE. Set them in the environment.
    INTERNAL_TASKS_SECRET: Optional[str] = None   # dispatcher -> /tasks worker routes
    INBOUND_EMAIL_SECRET: Optional[str] = None    # ?token= on the inbound-email webhook

    # ElevenLabs Conversational AI (the "Aurelia" voice agent). The key is a
    # server-side secret and must never reach the browser; the frontend instead
    # fetches a short-lived WebRTC conversation token from /api/v1/voice/token.
    ELEVENLABS_API_KEY: Optional[str] = None
    ELEVENLABS_AGENT_ID: str = "agent_3801ktczgph3ep3bpr0rp9jgvzqc"
    
    # Dev settings. Off by default so a deployment that forgets them is locked down;
    # backend/.env.example and docker-compose turn them on for local work.
    DEVELOPMENT_MODE: bool = False
    ALLOW_MOCK_AUTH: bool = False

    # Comma-separated emails that may create an account before any access list
    # exists (first sign-in of the couple). Set in the environment, never in git.
    ACCESS_BOOTSTRAP_EMAILS: str = ""
    
    # Base URL the task dispatcher posts agent jobs to. Defaults to the Docker
    # Compose service name; for a non-Docker local run set this to the single
    # backend process, e.g. WORKER_BASE_URL=http://localhost:8000.
    WORKER_BASE_URL: str = "http://worker:8001"

    # Cloud Tasks
    TASKS_EMULATOR_HOST: str = "tasks-emulator"
    TASKS_EMULATOR_PORT: int = 8123
    PROJECT_ID: str = "venueflow-dev"
    LOCATION: str = "europe-west1"
    QUEUE_ID: str = "agent-tasks"

    @model_validator(mode="after")
    def configure_database_drivers(self):
        url = make_url(self.DATABASE_URL)
        if url.get_backend_name() in ("postgres", "postgresql"):
            sync_url = url.set(drivername="postgresql+psycopg2")
            async_url = url.set(drivername="postgresql+asyncpg")
            query = dict(async_url.query)
            # asyncpg accepts ssl, not libpq's sslmode/channel_binding arguments.
            if "sslmode" in query:
                query["ssl"] = query.pop("sslmode")
            query.pop("channel_binding", None)
            self.DATABASE_URL = async_url.set(query=query).render_as_string(hide_password=False)
            if not self.SYNC_DATABASE_URL:
                self.SYNC_DATABASE_URL = sync_url.render_as_string(hide_password=False)
        elif not self.SYNC_DATABASE_URL:
            self.SYNC_DATABASE_URL = self.DATABASE_URL.replace("sqlite+aiosqlite:", "sqlite:")
        return self

    class Config:
        env_file = ".env"
        extra = "ignore"

settings = Settings()
