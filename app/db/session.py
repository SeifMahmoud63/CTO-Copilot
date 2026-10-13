import asyncio
import logging
import os
from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from app.core.config import settings
from app.models import Base

logger = logging.getLogger("cto-copilot.db")

# Async engine with connection recycling
engine = create_async_engine(
    settings.async_database_url,
    echo=False,
    pool_pre_ping=True,
    pool_recycle=3600
)

# Session factory
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False
)

async def dispose_engine() -> None:
    """Drop all pooled DB connections.

    REQUIRED at Celery task boundaries: the worker is prefork (engine + pool
    are inherited at import), while every task runs its own ``asyncio.run()``
    event loop. Pooled aiomysql connections stay bound to dead loops, so the
    next task's first checkout crashes with "Future attached to a different
    loop". Disposing forces a fresh pool on the current loop. Harmless
    everywhere else (fresh processes, tests).
    """
    try:
        await engine.dispose()
    except Exception as e:
        logger.debug(f"Engine dispose skipped: {e}")


def is_loop_teardown_noise(exc_value: BaseException, obj=None) -> bool:
    """True only for aiomysql/SQLAlchemy close-after-loop-death noise.

    Matches ALL of: a RuntimeError saying exactly "Event loop is closed",
    raised from aiomysql/sqlalchemy teardown frames (Connection.__del__,
    ensure_closed, pool _close_connection). Anything else — including the
    same message from our own code paths — returns False and stays loud.
    """
    if not isinstance(exc_value, RuntimeError):
        return False
    if "Event loop is closed" not in str(exc_value):
        return False
    parts = []
    if obj is not None:
        parts.append(type(obj).__module__ or "")
        parts.append(type(obj).__qualname__ or "")
    tb = getattr(exc_value, "__traceback__", None)
    while tb is not None:
        parts.append(tb.tb_frame.f_code.co_filename or "")
        tb = tb.tb_next
    blob = "\n".join(parts)
    return ("aiomysql" in blob) or ("sqlalchemy" in blob)


_installed_noise_filter = False


def install_loop_noise_filter() -> None:
    """Route DB-teardown interpreter noise to /dev/null (idempotent).

    Python prints "Exception ignored in ..." via sys.unraisablehook when GC
    collects pooled connections after their loop died (worker shutdown,
    interpreter exit). Real errors keep flowing to the previous hook.
    """
    global _installed_noise_filter
    if _installed_noise_filter:
        return
    import sys

    prev = sys.unraisablehook

    def _hook(unraisable):
        try:
            if is_loop_teardown_noise(
                getattr(unraisable, "exc_value", None),
                getattr(unraisable, "object", None),
            ):
                return
        except Exception:
            pass
        prev(unraisable)

    sys.unraisablehook = _hook
    _installed_noise_filter = True

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Yield an async database session per request."""
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
