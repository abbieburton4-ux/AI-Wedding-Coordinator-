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

# Configure CORS dynamically for local Vite development and deployed GitHub Pages
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://alanmaizon.github.io",
        "http://localhost:5173",
        "http://127.0.0.1:5173"
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=[
        "Content-Type", 
        "Authorization", 
        "X-Idempotency-Key", 
        "X-Requested-With",
        "Accept"
    ],
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
from app.api.v1.endpoints import weddings, webhooks, auth, inquiries, metrics
from app.worker import tasks

app.include_router(auth.router, prefix="/api/v1/auth", tags=["Auth"])
app.include_router(weddings.router, prefix="/api/v1/weddings", tags=["Weddings"])
app.include_router(inquiries.router, prefix="/api/v1/inquiries", tags=["Inquiries"])
app.include_router(metrics.router, prefix="/api/v1/metrics", tags=["Metrics"])
app.include_router(webhooks.router, prefix="/api/v1/webhooks", tags=["Webhooks"])
app.include_router(tasks.router, prefix="/tasks", tags=["Worker Tasks"])

@app.get("/")
def read_root():
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
