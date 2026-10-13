"""Unit tests for the Cairo-day emails tool + UTC range helper.

Covers: DST-aware day bounds (the "galy email inhardah?" incident class),
day-filtered email fetch on sqlite (boundary + hidden + undated rows),
and the recent_emails tool wiring (mirrors test_chat_report_tool.py).

Run from the repo root:
    python -m pytest tests/test_chat_emails_tool.py -v
"""
import asyncio
from datetime import datetime
from unittest.mock import AsyncMock

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.db.base import Base
from app.models import Email
from app.services import chat_service as chat_module
from app.services.db_service import cairo_day_utc_range


def run(coro):
    return asyncio.run(coro)


def test_cairo_day_range_dst():
    # 2026-10-12: Egypt DST (UTC+3) -> 21:00Z previous day .. 21:00Z.
    start, end = cairo_day_utc_range("2026-10-12")
    assert start == datetime(2026, 10, 11, 21, 0, 0)
    assert end == datetime(2026, 10, 12, 21, 0, 0)


def test_cairo_day_range_standard_time():
    # 2026-01-12: standard time (UTC+2) -> 22:00Z previous day .. 22:00Z.
    start, end = cairo_day_utc_range("2026-01-12")
    assert start == datetime(2026, 1, 11, 22, 0, 0)
    assert end == datetime(2026, 1, 12, 22, 0, 0)


def test_cairo_day_range_invalid():
    assert cairo_day_utc_range("not-a-date") is None
    assert cairo_day_utc_range("") is None
    assert cairo_day_utc_range("2026-02-30") is None


def test_utc_naive_to_cairo_str():
    f = chat_module._utc_naive_to_cairo_str
    assert f("2026-10-12T06:07:00") == "2026-10-12 09:07"  # DST +3
    assert f("2026-01-12T06:07:00") == "2026-01-12 08:07"  # STD +2
    assert f(None) == "?"
    assert f("garbage") == "garbage"


def _seeded_factory():
    async def go():
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        factory = async_sessionmaker(engine, expire_on_commit=False)
        async with factory() as s:
            s.add_all([
                # 00:30 Cairo Oct 12 -> stored 21:30Z Oct 11 (the dropped class).
                Email(message_id="m-boundary", sender="a@x", subject="Boundary",
                      sent_at=datetime(2026, 10, 11, 21, 30, 0)),
                Email(message_id="m-morning", sender="b@x", subject="Morning",
                      sent_at=datetime(2026, 10, 12, 6, 7, 0)),
                Email(message_id="m-old", sender="c@x", subject="Old",
                      sent_at=datetime(2026, 10, 10, 12, 0, 0)),
                Email(message_id="m-hidden", sender="d@x", subject="Hidden",
                      sent_at=datetime(2026, 10, 12, 9, 0, 0), is_hidden=True),
                Email(message_id="m-undated", sender="e@x", subject="Undated",
                      sent_at=None),
            ])
            await s.commit()
        return factory

    return asyncio.run(go())


def test_get_emails_for_day_boundary(monkeypatch):
    from app.services import db_service as db_module

    factory = _seeded_factory()
    monkeypatch.setattr(db_module, "AsyncSessionLocal", factory)
    out = run(db_module.db_service.get_emails_for_day("2026-10-12"))
    subjects = {r["subject"] for r in out}
    # Boundary (00:30 Cairo) + morning match; old/hidden/undated excluded.
    assert subjects == {"Boundary", "Morning"}
    assert out[0]["subject"] == "Morning"  # newest first


def test_get_emails_for_day_empty(monkeypatch):
    from app.services import db_service as db_module

    factory = _seeded_factory()
    monkeypatch.setattr(db_module, "AsyncSessionLocal", factory)
    assert run(db_module.db_service.get_emails_for_day("2026-10-09")) == []
    assert run(db_module.db_service.get_emails_for_day("junk")) == []


def test_recent_emails_success(monkeypatch):
    import app.services.db_service as db_module

    seen = {}

    async def fake(day_iso):
        seen["day"] = day_iso
        return [{"sender": "Seif", "subject": "Hi",
                 "sent_at": "2026-10-12T06:07:00",
                 "urgency_score": 5.3, "urgency_tier": "FYI / Soon"}]

    monkeypatch.setattr(db_module.db_service, "get_emails_for_day", fake)
    out = run(chat_module.recent_emails.ainvoke({"day_ref": "2026-10-12"}))
    assert seen["day"] == "2026-10-12"
    assert "Seif" in out and "Hi" in out
    assert "09:07" in out  # Cairo wall time, no mental +3


def test_recent_emails_empty_today_hints_sync(monkeypatch):
    import app.services.db_service as db_module

    monkeypatch.setattr(
        db_module.db_service, "get_emails_for_day", AsyncMock(return_value=[]))
    out = run(chat_module.recent_emails.ainvoke({"day_ref": "today"}))
    assert "No recorded emails" in out
    assert "Sync Inbox" in out


def test_recent_emails_empty_past_day_no_hint(monkeypatch):
    import app.services.db_service as db_module

    monkeypatch.setattr(
        db_module.db_service, "get_emails_for_day", AsyncMock(return_value=[]))
    out = run(chat_module.recent_emails.ainvoke({"day_ref": "2026-01-01"}))
    assert "No recorded emails for 2026-01-01" in out
    assert "Sync Inbox" not in out


def test_recent_emails_bad_date():
    out = run(chat_module.recent_emails.ainvoke({"day_ref": "whenever"}))
    assert "Could not understand that date" in out


def test_prompt_routes_to_emails_tool():
    assert "recent_emails" in chat_module.SYSTEM_PROMPT


def test_tools_registered_on_service():
    service = chat_module.ChatService()
    assert set(service.tools_by_name) >= {
        "get_database_schema", "execute_readonly_query",
        "get_current_datetime", "web_search", "summarize_report",
        "recent_emails",
    }
