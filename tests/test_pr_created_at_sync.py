"""Unit tests for PR created_at re-sync (self-healing stale dates).

`save_or_update_pr` must refresh created_at from GitHub on every update —
GitHub creation timestamps are immutable, so overwriting can only repair
rows frozen with wrong dates (e.g. PR #5 stored as Oct 1 instead of Oct 11).

Uses a real in-memory SQLite DB (no MySQL needed).

Run from the repo root:
    python -m pytest tests/test_pr_created_at_sync.py -v
"""
import asyncio
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.db.base import Base
from app.models import PullRequest
from app.services import db_service as db_module


def run(coro):
    return asyncio.run(coro)


def make_sqlite_factory():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")

    async def init():
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    run(init())
    return async_sessionmaker(engine, expire_on_commit=False)


async def _seed(factory, **kwargs):
    async with factory() as session:
        async with session.begin():
            session.add(PullRequest(**kwargs))


async def _fetch(factory, number):
    async with factory() as session:
        res = await session.execute(
            select(PullRequest).where(PullRequest.number == number)
        )
        return res.scalar_one()


def test_update_refreshes_stale_created_at(monkeypatch):
    factory = make_sqlite_factory()
    monkeypatch.setattr(db_module, "AsyncSessionLocal", factory)
    stale = datetime(2026, 10, 1, 12, 0, 0)
    truth = datetime(2026, 10, 11, 13, 33, 46)
    run(_seed(factory, number=5, title="old", author="a", state="open",
               head_branch="h", base_branch="main", html_url="u",
               created_at=stale))

    async def go():
        return await db_module.db_service.save_or_update_pr(
            number=5, title="new", author="a", state="open", head_branch="h",
            base_branch="main", html_url="u", created_at=truth,
            is_overdue=False, overdue_days=0)

    run(go())
    pr = run(_fetch(factory, 5))
    assert pr.created_at == truth
    assert pr.title == "new"


def test_update_without_created_at_keeps_old_value(monkeypatch):
    factory = make_sqlite_factory()
    monkeypatch.setattr(db_module, "AsyncSessionLocal", factory)
    kept = datetime(2026, 10, 10, 11, 23, 36)
    run(_seed(factory, number=1, title="t", author="a", state="merged",
               head_branch="h", base_branch="main", html_url="u",
               created_at=kept))

    async def go():
        return await db_module.db_service.save_or_update_pr(
            number=1, title="t2", author="a", state="merged", head_branch="h",
            base_branch="main", html_url="u", created_at=None)

    run(go())
    pr = run(_fetch(factory, 1))
    assert pr.created_at == kept
    assert pr.title == "t2"
