"""
app/main.py
─────────────────────────────────────────────────────────────
FastAPI application entry point.

Responsibilities:
  - Create the FastAPI app instance with OpenAPI metadata.
  - Register middleware (CORS).
  - Register custom exception handlers.
  - Register API routers with versioned prefix.
  - Define startup/shutdown lifespan (DB initialisation).

Run with:
  uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
"""

import logging
import logging.config
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import lifespan_db
from app.middleware.error_handler import register_exception_handlers
from app.routes import recipe as recipe_router

# ── Logging configuration ────────────────────────────────────
logging.config.dictConfig({
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "default": {
            "format": "%(asctime)s | %(levelname)-8s | %(name)s — %(message)s",
            "datefmt": "%Y-%m-%d %H:%M:%S",
        }
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "default",
        }
    },
    "root": {
        "level": "DEBUG" if settings.debug else "INFO",
        "handlers": ["console"],
    },
})

logger = logging.getLogger(__name__)


# ════════════════════════════════════════════════════════════
# Application lifespan
# ════════════════════════════════════════════════════════════

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Manage startup and shutdown events.

    On startup:
      - Initialises the database (creates tables if they don't exist).
    On shutdown:
      - Disposes the async engine (closes all connection pool connections).
    """
    logger.info("Starting %s v%s", settings.app_title, settings.app_version)
    async with lifespan_db():
        logger.info("Database initialised successfully.")
        yield
    logger.info("Application shut down cleanly.")


# ════════════════════════════════════════════════════════════
# FastAPI application
# ════════════════════════════════════════════════════════════

app = FastAPI(
    title=settings.app_title,
    version=settings.app_version,
    description=(
        "API for extracting structured recipe data from blog URLs using "
        "LLM-powered scraping. Supports recipe extraction, nutritional "
        "estimation, ingredient substitutions, shopping lists, and recipe history."
    ),
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
)

# ── CORS middleware ──────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Exception handlers ───────────────────────────────────────
register_exception_handlers(app)

# ── Routers ──────────────────────────────────────────────────
app.include_router(recipe_router.router, prefix="/api/v1")


# ════════════════════════════════════════════════════════════
# Health check
# ════════════════════════════════════════════════════════════

@app.get("/health", tags=["Health"], summary="Health check")
async def health_check():
    """
    Simple health check endpoint.
    Used by Docker Compose, load balancers, and CI/CD pipelines.
    """
    return {
        "status": "ok",
        "service": settings.app_title,
        "version": settings.app_version,
    }
