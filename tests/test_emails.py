"""Unit tests for email triage (IMAP parsing, urgency tiers, DB, poll flow).

No network needed: MIME parsing is offline, DB runs on SQLite, LLM/JEV/IMAP
are mocked.

Run from the repo root:
    python -m pytest tests/test_emails.py -v
"""
import asyncio
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.db.base import Base
from app.models import Email
from app.services import db_service as db_module
from app.services import email_service as mail_module
from app.services.email_service import (
    build_email_prompt,
    parse_email_bytes,
    urgency_tier_for,
)


def run(coro):
    return asyncio.run(coro)


def make_sqlite_factory():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")

    async def init():
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    run(init())
    return async_sessionmaker(engine, expire_on_commit=False)


def sample_raw_email() -> bytes:
    msg = EmailMessage()
    msg["From"] = "Boss <boss@company.com>"
    msg["To"] = "cto@company.com"
    msg["Subject"] = "Production is down, need you now"
    msg["Date"] = "Sat, 11 Oct 2026 10:00:00 +0300"
    msg["Message-ID"] = "<abc123@company.com>"
    msg.set_content("The checkout API returns 500 for all requests. Customers waiting.")
    msg.add_alternative("<p>HTML version ignored</p>", subtype="html")
    return msg.as_bytes()


def test_parse_multipart_email_prefers_plain():
    parsed = parse_email_bytes(sample_raw_email(), max_chars=4000)
    assert parsed["message_id"] == "<abc123@company.com>"
    assert "boss@company.com" in parsed["sender"]
    assert parsed["subject"] == "Production is down, need you now"
    assert parsed["sent_at"] == datetime(2026, 10, 11, 7, 0, 0)  # +0300 -> naive UTC
    assert "checkout API returns 500" in parsed["body"]
    assert "HTML version" not in parsed["body"]
    assert len(parsed["snippet"]) <= 200


def test_urgency_tier_boundaries():
    assert urgency_tier_for(9.5) == "Reply Now"
    assert urgency_tier_for(8.0) == "Reply Now"
    assert urgency_tier_for(7.0) == "Reply Today"
    assert urgency_tier_for(6.5) == "Reply Today"
    assert urgency_tier_for(5.0) == "FYI / Soon"
    assert urgency_tier_for(None) == "FYI / Soon"
    assert urgency_tier_for(2.0) == "Archive"


def test_email_prompt_contains_metadata():
    parsed = parse_email_bytes(sample_raw_email(), max_chars=4000)
    prompt = build_email_prompt(parsed)
    assert "boss@company.com" in prompt
    assert "Production is down" in prompt
    assert "checkout API" in prompt


def test_email_db_roundtrip(monkeypatch):
    factory = make_sqlite_factory()
    monkeypatch.setattr(db_module, "AsyncSessionLocal", factory)

    async def go():
        saved = await db_module.db_service.save_or_update_email(
            message_id="<abc123@company.com>",
            sender="Boss <boss@company.com>",
            subject="Production is down",
            sent_at=datetime(2026, 10, 11, 7, 0, 0),
            snippet="checkout API 500",
            summary_text="Checkout down, CTO needed now.",
            summary_provider="bedrock_qwen",
            urgency_score=9.0,
            urgency_tier="Reply Now",
        )
        assert saved is not None
        one = await db_module.db_service.get_email_by_message_id("<abc123@company.com>")
        assert one["summary_text"].startswith("Checkout down")
        assert one["urgency_tier"] == "Reply Now"
        all_rows = await db_module.db_service.get_emails(limit=10, days=None)
        assert len(all_rows) == 1
        assert all_rows[0]["urgency_score"] == 9.0
        # Re-save without summary must NOT wipe the stored summary.
        await db_module.db_service.save_or_update_email(
            message_id="<abc123@company.com>", sender="x", subject="y")
        kept = await db_module.db_service.get_email_by_message_id("<abc123@company.com>")
        assert kept["summary_text"].startswith("Checkout down")

    run(go())


def test_poll_skips_when_disabled(monkeypatch):
    monkeypatch.setattr(mail_module.settings, "email_enabled", False)
    out = run(mail_module.email_service.poll_inbox())
    assert out["status"] == "disabled"
    assert out["summarized"] == 0


def test_poll_happy_path_with_mocks(monkeypatch):
    factory = make_sqlite_factory()
    monkeypatch.setattr(db_module, "AsyncSessionLocal", factory)
    monkeypatch.setattr(mail_module.settings, "email_enabled", True)
    monkeypatch.setattr(mail_module.settings, "email_address", "me@x.com")
    monkeypatch.setattr(mail_module.settings, "email_password", "secret")

    parsed = parse_email_bytes(sample_raw_email(), max_chars=4000)
    monkeypatch.setattr(
        mail_module, "fetch_recent_emails", Mock(return_value=[parsed]))

    from app.services import llm_service as llm_module
    from app.services import jev_service as jev_module

    captured = {}

    def fake_gen(prompt, system_prompt=None):
        captured["system"] = system_prompt
        return ("Short summary.", SimpleNamespace(value="bedrock_qwen"), "m")

    monkeypatch.setattr(llm_module.llm_service, "generate_pr_summary", fake_gen)
    monkeypatch.setattr(
        jev_module.jev_service, "evaluate_urgency", AsyncMock(return_value=8.5))

    out = run(mail_module.email_service.poll_inbox(limit=5))
    assert out["status"] == "completed"
    assert out["fetched"] == 1 and out["summarized"] == 1
    assert "triaging inbox" in captured["system"] or "executive assistant" in captured["system"]

    # Second poll: already triaged -> skipped, never re-paid.
    out2 = run(mail_module.email_service.poll_inbox(limit=5))
    assert out2["summarized"] == 0

    rows = run(db_module.db_service.get_emails(limit=5, days=None))
    assert rows[0]["urgency_tier"] == "Reply Now"
    assert rows[0]["summary_text"] == "Short summary."


def test_get_emails_defaults_to_last_3_days(monkeypatch):
    factory = make_sqlite_factory()
    monkeypatch.setattr(db_module, "AsyncSessionLocal", factory)
    now = datetime.now(timezone.utc).replace(tzinfo=None)

    async def go():
        for mid, sent in [
            ("<fresh@x>", now - timedelta(days=1)),
            ("<old@x>", now - timedelta(days=5)),
            ("<nodate@x>", None),
        ]:
            await db_module.db_service.save_or_update_email(
                message_id=mid, sender="s", subject="t", sent_at=sent)
        default_rows = await db_module.db_service.get_emails(limit=10)
        assert [r["message_id"] for r in default_rows] == ["<fresh@x>"]
        all_rows = await db_module.db_service.get_emails(limit=10, days=None)
        # Newest first, undated sinks to the bottom.
        assert [r["message_id"] for r in all_rows] == ["<fresh@x>", "<old@x>", "<nodate@x>"]

    run(go())


def test_email_summarizer_suggests_no_reply():
    from app.core.enums import SystemPrompt

    prompt = SystemPrompt.EMAIL_SUMMARIZER.value
    assert "NEVER suggest" in prompt
    assert "you should" in prompt.lower()
    assert "whether it needs a reply" not in prompt
    assert "how fast" not in prompt


def test_dismiss_hides_but_keeps_dedupe(monkeypatch):
    factory = make_sqlite_factory()
    monkeypatch.setattr(db_module, "AsyncSessionLocal", factory)

    async def go():
        await db_module.db_service.save_or_update_email(
            message_id="<keep@x>", sender="s", subject="keep",
            sent_at=datetime.now(timezone.utc).replace(tzinfo=None))
        saved = await db_module.db_service.save_or_update_email(
            message_id="<drop@x>", sender="s", subject="drop",
            sent_at=datetime.now(timezone.utc).replace(tzinfo=None))
        assert await db_module.db_service.hide_email(saved.id) is True
        assert await db_module.db_service.hide_email(999999) is False
        visible = await db_module.db_service.get_emails(limit=10, days=None)
        assert [r["message_id"] for r in visible] == ["<keep@x>"]
        # Dismissed row still visible to dedupe: next poll must skip it.
        assert (await db_module.db_service.get_email_by_message_id("<drop@x>")) is not None

    run(go())
