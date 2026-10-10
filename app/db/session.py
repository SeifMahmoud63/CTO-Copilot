import logging
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
    """Create the 2-table schema (pull_requests, engineers), migrate old DBs, drop legacy tables."""
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
            from sqlalchemy import text
            # Migrate existing pull_requests tables to the 2-table schema
            for ddl in (
                "ALTER TABLE pull_requests ADD COLUMN is_overdue BOOLEAN DEFAULT FALSE",
                "ALTER TABLE pull_requests ADD COLUMN overdue_days INT DEFAULT 0",
                "ALTER TABLE pull_requests ADD COLUMN summary_text TEXT NULL",
                "ALTER TABLE pull_requests ADD COLUMN summary_provider VARCHAR(50) NULL",
                "ALTER TABLE pull_requests ADD COLUMN summary_timestamp DATETIME NULL",
                "ALTER TABLE pull_requests ADD COLUMN impact_score FLOAT NULL",
                "ALTER TABLE pull_requests ADD COLUMN impact_tier VARCHAR(50) NULL",
            ):
                try:
                    await conn.execute(text(ddl))
                except Exception:
                    pass  # column already exists
            # Drop legacy tables from the old 5-table schema
            for legacy in ("pr_summaries", "pr_impact_scores", "pr_approvals", "audit_logs"):
                try:
                    await conn.execute(text(f"DROP TABLE IF EXISTS {legacy}"))
                except Exception:
                    pass
        logger.info("MySQL async database tables initialized successfully.")
        return True
    except Exception as e:
        logger.warning(f"Could not connect to MySQL async database during init_db: {e}")
        return False
