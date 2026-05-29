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
    
    # Dev settings
    DEVELOPMENT_MODE: bool = True
    ALLOW_MOCK_AUTH: bool = True
    
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
