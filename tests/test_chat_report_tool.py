"""Unit tests for websearch fallback chain + summarize_report date tool.

Run from the repo root:
    python -m pytest tests/test_chat_report_tool.py -v
"""
import asyncio
from datetime import date
from unittest.mock import AsyncMock

from app.services import chat_service as chat_module


def run(coro):
    return asyncio.run(coro)


TODAY = date(2026, 10, 11)


def test_parse_report_date_words():
    p = chat_module.parse_report_date
    assert p("today", TODAY) == TODAY
    assert p("انهارده", TODAY) == TODAY
    assert p("النهاردة", TODAY) == TODAY
    assert p("yesterday", TODAY) == date(2026, 10, 10)
    assert p("امبارح", TODAY) == date(2026, 10, 10)


def test_parse_report_date_formats():
    p = chat_module.parse_report_date
    assert p("2026-10-09", TODAY) == date(2026, 10, 9)
    assert p("09/10/2026", TODAY) == date(2026, 10, 9)
    assert p("10 أكتوبر 2026", TODAY) == date(2026, 10, 10)
    assert p("10 اكتوبر", TODAY) == date(2026, 10, 10)
    assert p("Oct 10", TODAY) == date(2026, 10, 10)
    assert p("someday never", TODAY) is None
    assert p("2026-02-30", TODAY) is None
    assert p("", TODAY) is None


def test_summarize_report_success(monkeypatch):
    import app.services.db_service as db_module

    monkeypatch.setattr(
        db_module.db_service, "get_report_by_date",
        AsyncMock(return_value={
            "report_date": "2026-10-11", "title": "CTO Daily Report",
            "prs_opened": 3, "prs_merged": 3, "prs_closed": 0, "overdue_count": 1,
            "executive_summary": "Great day overall.",
        }),
    )
    out = run(chat_module.summarize_report.ainvoke({"report_date": "انهارده"}))
    assert "2026-10-11" in out or "CTO Daily Report" in out
    assert "Great day overall." in out
    assert "Opened: 3" in out


def test_summarize_report_missing_lists_available(monkeypatch):
    import app.services.db_service as db_module

    monkeypatch.setattr(db_module.db_service, "get_report_by_date", AsyncMock(return_value=None))
    monkeypatch.setattr(
        db_module.db_service, "get_reports",
        AsyncMock(return_value=[{"report_date": "2026-10-11"}, {"report_date": "2026-10-10"}]),
    )
    out = run(chat_module.summarize_report.ainvoke({"report_date": "2026-01-01"}))
    assert "No daily report found for 2026-01-01" in out
    assert "2026-10-11" in out


def test_summarize_report_bad_date():
    out = run(chat_module.summarize_report.ainvoke({"report_date": "whenever"}))
    assert "Could not understand that date" in out


def test_websearch_falls_back_to_html_results(monkeypatch):
    import httpx

    class FakeResp:
        def __init__(self, url):
            self.url = url

        def raise_for_status(self):
            return None

        def json(self):
            return {"AbstractText": "", "Results": [], "RelatedTopics": []}

        @property
        def text(self):
            return (
                '<a rel="nofollow" class="result__a" href="//duckduckgo.com/l/?uddg=https%3A%2F%2Fexample.com%2Fegypt">Egypt</a>'
                '<a class="result__snippet" href="x">Country in North Africa.</a>'
            )

    Rest = []

    class FakeClient:
        def __init__(self, *a, **k):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def get(self, url, *a, **k):
            Rest.append(url)
            return FakeResp(url)

        async def post(self, url, *a, **k):
            Rest.append(url)
            return FakeResp(url)

    monkeypatch.setattr(httpx, "AsyncClient", FakeClient)
    out = run(chat_module.web_search.ainvoke({"query": "egypt population"}))
    assert "https://example.com/egypt" in out
    assert "North Africa" in out
    assert any("api.duckduckgo.com" in u for u in Rest)
    assert any("html.duckduckgo.com" in u for u in Rest)


def test_prompt_routes_to_report_tool():
    assert "summarize_report" in chat_module.SYSTEM_PROMPT
    assert "web_search" in chat_module.SYSTEM_PROMPT


def test_tools_registered_on_service():
    service = chat_module.ChatService()
    assert set(service.tools_by_name) >= {
        "get_database_schema", "execute_readonly_query",
        "get_current_datetime", "web_search", "summarize_report",
    }
