from pydantic_settings import BaseSettings
from typing import Optional

class Settings(BaseSettings):
    # Databases: async for FastAPI, sync for Alembic/seeding
    DATABASE_URL: str = "postgresql+asyncpg://venueflow:venueflow_pass@db/venueflow"
    SYNC_DATABASE_URL: str = "postgresql+psycopg2://venueflow:venueflow_pass@db/venueflow"
    
    # API Keys & Auth
    GEMINI_API_KEY: Optional[str] = None
    JWT_SECRET: Optional[str] = "dev-jwt-secret-key-change-me-in-production"
    FIREBASE_PROJECT_ID: str = "venueflow-dev"

    # ElevenLabs Conversational AI (the "Aurelia" voice agent). The key is a
    # server-side secret and must never reach the browser; the frontend instead
    # fetches a short-lived WebRTC conversation token from /api/v1/voice/token.
    ELEVENLABS_API_KEY: Optional[str] = None
    ELEVENLABS_AGENT_ID: str = "agent_3801ktczgph3ep3bpr0rp9jgvzqc"
    
    # Dev settings
    DEVELOPMENT_MODE: bool = True
    ALLOW_MOCK_AUTH: bool = True
    
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

    # Payments
    # PAYMENTS_PROVIDER selects how /payments/checkout behaves:
    #   "mock"   -> no real charge; records a mock Payment + starts planning instantly (demo/pitch path)
    #   "stripe" -> creates a real Stripe Checkout Session (test or live keys)
    # Flipping demo -> real payments is a single env change (set this to "stripe"
    # + STRIPE_SECRET_KEY); no code change required.
    PAYMENTS_PROVIDER: str = "mock"
    # When True, AI planning is gated behind a completed payment: a new wedding
    # stays in 'intake' until checkout succeeds (which is what enqueues the planner).
    # Set False for payment-free demos and the verification scripts.
    REQUIRE_PAYMENT: bool = True
    # One-time coordinator fee shown at the couple-facing checkout (EUR).
    COUPLE_PRICE_EUR: float = 299.0
    STRIPE_SECRET_KEY: Optional[str] = None
    STRIPE_PUBLISHABLE_KEY: Optional[str] = None
    # Optional pre-created Stripe Price id; if unset, an inline price_data is used.
    STRIPE_PRICE_ID: Optional[str] = None
    # Where Stripe redirects back to after hosted checkout.
    FRONTEND_BASE_URL: str = "http://localhost:5173"

    class Config:
        env_file = ".env"
        extra = "ignore"

settings = Settings()
