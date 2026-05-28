import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="VenueFlow API",
    description="Backend API and Agent Worker for VenueFlow - AI Wedding Coordinator",
    version="1.0.0"
)

# Configure CORS for local React/Vite development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Adjust in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Startup Event: DB Initialization and Automatic Seeding
@app.on_event("startup")
def on_startup():
    from sqlmodel import SQLModel
    from app.db.session import sync_engine
    from app.db.seed import seed_database
    
    logger.info("Initializing database schemas...")
    # Automatically creates all tables if they do not exist
    SQLModel.metadata.create_all(sync_engine)
    logger.info("Database schema initialization complete.")
    
    # Automatically seed if database is empty
    try:
        seed_database()
    except Exception as e:
        logger.error(f"Error during startup database seeding: {e}")

# Include Routers
from app.api.v1.endpoints import weddings, webhooks
from app.worker import tasks

app.include_router(weddings.router, prefix="/api/v1/weddings", tags=["Weddings"])
app.include_router(webhooks.router, prefix="/api/v1/webhooks", tags=["Webhooks"])
app.include_router(tasks.router, prefix="/tasks", tags=["Worker Tasks"])

@app.get("/")
def read_root():
    return {
        "status": "healthy",
        "service": "VenueFlow Backend",
        "environment": "development" if settings.DEVELOPMENT_MODE else "production"
    }
