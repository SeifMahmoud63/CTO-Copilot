import asyncio
import logging
import os
from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from app.core.config import settings
from app.models import Base

logger = logging.getLogger("cto-copilot.db")

# Create async engine with pool recycling and health ping
engine = create_async_engine(
    settings.async_database_url,
    echo=False,
    pool_pre_ping=True,
    pool_recycle=3600
)

# Async session factory
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False
)

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency for FastAPI routes to yield an async database session."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()

async def init_db() -> bool:
    """Bring the database to Alembic `head` (creates/migrates the 2-table schema)."""
    try:
        from alembic.config import Config as AlembicConfig
        from alembic import command as alembic_command

        project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
        cfg = AlembicConfig(os.path.join(project_root, "alembic.ini"))
        cfg.set_main_option("script_location", os.path.join(project_root, "alembic"))
        await asyncio.to_thread(alembic_command.upgrade, cfg, "head")
        logger.info("Alembic migrations applied successfully (head).")
    except Exception as e:
        logger.warning(f"Alembic upgrade failed, falling back to create_all: {e}")
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("MySQL async database tables initialized successfully.")
        return True
    except Exception as e:
        logger.warning(f"Could not connect to MySQL async database during init_db: {e}")
        return False
