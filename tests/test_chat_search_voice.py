"""Unit tests for chatbot extra tools (datetime/websearch) and voice<->reports link.

Run from the repo root:
    python -m pytest tests/test_chat_search_voice.py -v
"""
import asyncio
import json

from app.services import chat_service as chat_module
from app.services import voice_service as voice_module


def run(coro):
    return asyncio.run(coro)


def test_datetime_tool_returns_cairo_time():
    out = json.loads(chat_module.get_current_datetime.invoke({}))
    assert out["timezone"] == "Africa/Cairo"
    assert len(out["date"]) == 10 and len(out["time"]) == 5
    assert out["weekday"]


def test_chat_tools_registered():
    # Module-level tool defs + prompt wiring (constructor binds them to the LLM).
    assert chat_module.get_current_datetime.name == "get_current_datetime"
    assert chat_module.web_search.name == "web_search"
    assert "daily_reports" in chat_module.get_database_schema.invoke({})
    prompt = chat_module.SYSTEM_PROMPT
    assert "web_search" in prompt and "get_current_datetime" in prompt
    assert "daily_reports" in prompt


def test_web_search_formats_ddg_response(monkeypatch):
    import httpx

    payload = {
        "AbstractText": "Paris is the capital of France.",
        "AbstractURL": "https://example.com/paris",
        "Results": [{"Text": "Paris - Wikipedia", "FirstURL": "https://example.com/wiki"}],
        "RelatedTopics": [{"Text": "France geography"}],
    }

    class FakeResp:
        def raise_for_status(self):
            return None

        def json(self):
            return payload

    class FakeClient:
        def __init__(self, *a, **k):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def get(self, *a, **k):
            return FakeResp()

    monkeypatch.setattr(httpx, "AsyncClient", FakeClient)
    out = run(chat_module.web_search.ainvoke({"query": "capital of France"}))
    assert "Paris is the capital" in out
    assert "Wikipedia" in out


def test_web_search_failure_falls_back(monkeypatch):
    import httpx

    class DeadClient:
        def __init__(self, *a, **k):
            pass

        async def __aenter__(self):
            raise RuntimeError("no route")

        async def __aexit__(self, *a):
            return False

    monkeypatch.setattr(httpx, "AsyncClient", DeadClient)
    out = run(chat_module.web_search.ainvoke({"query": "anything"}))
    assert "unavailable" in out


def test_voice_prompt_knows_daily_reports():
    service = voice_module.VoiceAgentService.__new__(voice_module.VoiceAgentService)
    service.agent_model = "nova-3"
    service.voice_model = "aura-asteria-en"
    payload = voice_module.VoiceAgentService.build_settings_payload(service)
    prompt = payload["agent"]["think"]["prompt"]
    assert "daily_reports" in prompt
    assert "executive_summary" in prompt
    assert "ORDER BY report_date DESC LIMIT 1" in prompt
    tool_desc = payload["agent"]["think"]["functions"][0]["description"]
    assert "daily_reports" in tool_desc


def test_voice_sql_guard_allows_daily_reports_select(monkeypatch):
    """Guard must let daily_reports SELECTs through to the DB layer."""
    service = voice_module.VoiceAgentService.__new__(voice_module.VoiceAgentService)

    class DeadSession:
        async def __aenter__(self):
            raise RuntimeError("db down in test")

        async def __aexit__(self, *a):
            return False

    monkeypatch.setattr(voice_module, "AsyncSessionLocal", lambda: DeadSession())
    out = run(service.execute_readonly_sql(
        "SELECT title, executive_summary FROM daily_reports ORDER BY report_date DESC LIMIT 1"
    ))
    assert "db down in test" in out  # reached DB layer => guard passed
    assert "Only read-only" not in out and "strictly blocked" not in out
