"""
Main FastAPI application
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import asyncio

from .config import settings
from .models.database import init_db
from .services.worker import Worker


# Global worker instance
worker_instance: Worker = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan manager - handles startup and shutdown
    """
    global worker_instance

    # Startup
    print("=" * 70)
    print(f"🚀 Starting {settings.APP_NAME} v{settings.APP_VERSION}")
    print("=" * 70)

    # Initialize database
    print("📊 Initializing database...")
    init_db()
    print("✅ Database initialized")

    # Start background worker
    if settings.WORKER_ENABLED:
        print("⚙️  Starting background worker...")
        from .services.worker import Worker
        worker_instance = Worker()
        asyncio.create_task(worker_instance.run())
        print("✅ Background worker started")
    else:
        print("⚠️  Background worker disabled")

    print("=" * 70)
    print(f"🌐 API ready at http://localhost:8000")
    print(f"📖 Docs available at http://localhost:8000/docs")
    print("=" * 70)

    yield

    # Shutdown
    print("\n" + "=" * 70)
    print("🛑 Shutting down...")
    print("=" * 70)

    if worker_instance:
        print("⏸️  Stopping background worker...")
        await worker_instance.stop()
        print("✅ Background worker stopped")

    print("👋 Shutdown complete")


# Create FastAPI app
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="Internal tool for automated brand classification",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Health check endpoint (no auth required)
@app.get("/api/health")
async def health_check():
    """Health check endpoint"""
    from .schemas.schemas import HealthResponse

    return HealthResponse(
        status="ok",
        database=True,  # TODO: Add actual database check
        worker_running=worker_instance is not None and worker_instance.is_running
    )


# Include API routers
from .api import auth_router, runs_router, records_router, usage_router

app.include_router(auth_router.router, prefix="/api/auth", tags=["Authentication"])
app.include_router(runs_router.router, prefix="/api/runs", tags=["Runs"])
app.include_router(records_router.router, prefix="/api/records", tags=["Records"])
app.include_router(usage_router.router, tags=["Usage"])


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "docs": "/docs",
        "health": "/api/health"
    }
