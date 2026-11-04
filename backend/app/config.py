from pydantic_settings import BaseSettings
from typing import Optional

class Settings(BaseSettings):
    # Databases: async for FastAPI, sync for Alembic/seeding
    DATABASE_URL: str = "postgresql+asyncpg://venueflow:venueflow_pass@db/venueflow"
    SYNC_DATABASE_URL: str = "postgresql+psycopg2://venueflow:venueflow_pass@db/venueflow"
    
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

    class Config:
        env_file = ".env"
        extra = "ignore"

settings = Settings()
