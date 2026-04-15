"""
app/database.py
─────────────────────────────────────────────────────────────
Async SQLAlchemy engine, session factory, and FastAPI
dependency for database access.

Uses asyncpg as the PostgreSQL driver for non-blocking I/O.
"""

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.config import settings


# ── Declarative base shared by all ORM models ─────────────
class Base(DeclarativeBase):
    pass


# ── Engine ────────────────────────────────────────────────
# pool_pre_ping: validate connections before checkout (handles DB restarts)
# echo: log SQL in debug mode only
engine = create_async_engine(
    settings.database_url,
    pool_pre_ping=True,
    echo=settings.debug,
    pool_size=10,
    max_overflow=20,
)

# ── Async session factory ────────────────────────────────
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,  # avoid lazy-load issues after commit
    autoflush=False,
    autocommit=False,
)


# ── FastAPI dependency ───────────────────────────────────
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Yield an async DB session for use in FastAPI route handlers.
    Rolls back on any unhandled exception, then closes the session.

    Usage:
        @router.post("/...")
        async def endpoint(db: AsyncSession = Depends(get_db)):
            ...
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


# ── DB initialisation ────────────────────────────────────
async def init_db() -> None:
    """
    Create all tables defined via ORM models.
    Called once during application startup (lifespan).

    Note: For production, prefer Alembic migrations over create_all().
    create_all() is safe here because it is idempotent (checkfirst=True).
    """
    # Import models here so Base.metadata is populated before create_all
    from app.models import recipe  # noqa: F401

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


@asynccontextmanager
async def lifespan_db():
    """
    Async context manager for use in application lifespan.
    Initialises the DB on enter, disposes the engine on exit.
    """
    await init_db()
    try:
        yield
    finally:
        await engine.dispose()
