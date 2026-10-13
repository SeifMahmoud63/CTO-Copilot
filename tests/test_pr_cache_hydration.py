"""Unit tests for DB-backed summary cache hydration (no LLM cost after restarts).

Covers `GitHubService.summarize_pr` second-chance lookup:
1. Empty memory cache + stored MySQL row  -> summary/score reused, LLM never called.
2. Empty memory cache + no stored row      -> falls through to the LLM path.
3. force_refresh=True + stored row present -> hydration skipped, LLM used.

Run from the repo root:
    python -m pytest tests/test_pr_cache_hydration.py -v
"""
import asyncio
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, Mock

import httpx

from app.core.enums import LLMProvider
from app.services import github_service as gh_mod
from app.services.github_service import GitHubService


def run(coro):
    return asyncio.run(coro)


NOW = datetime.now(timezone.utc)

PR_DATA = {
    "id": 999001,
    "number": 7,
    "title": "Add semantic cache layer",
    "user": {"login": "SeifMahmoud63", "avatar_url": "http://x/avatar.png"},
    "state": "open",
    "merged_at": None,
    "created_at": (NOW - timedelta(days=2)).isoformat().replace("+00:00", "Z"),
    "updated_at": NOW.isoformat().replace("+00:00", "Z"),
    "html_url": "http://x/pr/7",
    "head": {"ref": "feat/cache"},
    "base": {"ref": "main"},
    "body": "Adds caching.",
}

STORED_ROW = {
    "number": 7,
    "github_pr_id": 999001,
    "summary_text": "Stored executive summary from a previous run.",
    "summary_provider": LLMProvider.BEDROCK_QWEN.value,
    "summary_timestamp": (NOW - timedelta(days=1)).isoformat(),
    "impact_score": 7.5,
    "impact_tier": "High Impact",
}


def _patch_github_details(monkeypatch, payload):
    """Fake the single-PR GitHub details GET (no network)."""

    async def fake_get(self, url, **kwargs):
        class FakeResponse:
            status_code = 200
            text = "ok"

            def json(self):
                return dict(payload)

        return FakeResponse()

    monkeypatch.setattr(httpx.AsyncClient, "get", fake_get)


def _forbid_llm(monkeypatch, svc):
    """Fail loudly if the test path touches paid LLM/JEV calls."""
    monkeypatch.setattr(
        svc, "generate_pr_summary",
        Mock(side_effect=AssertionError("LLM must NOT be called on hydration path")),
    )
    return svc


def test_hydrates_from_db_without_llm(monkeypatch):
    svc = GitHubService()
    assert svc.summary_cache == {}

    _patch_github_details(monkeypatch, PR_DATA)
    monkeypatch.setattr(
        gh_mod.db_service, "get_pr_by_number", AsyncMock(return_value=dict(STORED_ROW))
    )
    monkeypatch.setattr(
        gh_mod.db_service, "save_or_update_pr", AsyncMock(return_value=None)
    )
    _forbid_llm(monkeypatch, gh_mod.llm_service)
    monkeypatch.setattr(
        gh_mod.jev_service, "evaluate_impact",
        AsyncMock(side_effect=AssertionError("JEV must NOT be called on hydration path")),
    )

    item = run(svc.summarize_pr(7))

    assert item is not None
    assert item.summary == STORED_ROW["summary_text"]
    assert item.impact_score == STORED_ROW["impact_score"]
    assert item.summary_provider == LLMProvider.BEDROCK_QWEN
    # Fresh GitHub metadata still wins over anything stale.
    assert item.title == PR_DATA["title"]
    assert item.author == "SeifMahmoud63"
    assert item.state.value == "open"
    assert item.is_overdue is False
    # Memory cache re-armed for subsequent list calls (zero extra cost).
    assert svc.summary_cache[PR_DATA["id"]]["summary"] == STORED_ROW["summary_text"]


def test_db_miss_falls_through_to_llm(monkeypatch):
    svc = GitHubService()

    _patch_github_details(monkeypatch, PR_DATA)
    monkeypatch.setattr(
        gh_mod.db_service, "get_pr_by_number", AsyncMock(return_value=None)
    )
    monkeypatch.setattr(
        gh_mod.db_service, "save_or_update_pr", AsyncMock(return_value=None)
    )
    monkeypatch.setattr(
        gh_mod.llm_service, "generate_pr_summary",
        Mock(return_value=("Fresh executive summary.", LLMProvider.GROQ_FALLBACK, "m")),
    )
    monkeypatch.setattr(
        gh_mod.jev_service, "evaluate_impact", AsyncMock(return_value=6.0)
    )
    monkeypatch.setattr(
        svc, "fetch_pr_diff", AsyncMock(return_value=("diff excerpt", False))
    )

    item = run(svc.summarize_pr(7))

    assert item is not None
    assert item.summary == "Fresh executive summary."
    assert item.impact_score == 6.0
    assert item.summary_provider == LLMProvider.GROQ_FALLBACK


def test_force_refresh_skips_hydration(monkeypatch):
    svc = GitHubService()

    _patch_github_details(monkeypatch, PR_DATA)
    get_stored = AsyncMock(return_value=dict(STORED_ROW))
    monkeypatch.setattr(gh_mod.db_service, "get_pr_by_number", get_stored)
    monkeypatch.setattr(
        gh_mod.db_service, "save_or_update_pr", AsyncMock(return_value=None)
    )
    monkeypatch.setattr(
        gh_mod.llm_service, "generate_pr_summary",
        Mock(return_value=("Refreshed summary.", LLMProvider.BEDROCK_QWEN, "m")),
    )
    monkeypatch.setattr(
        gh_mod.jev_service, "evaluate_impact", AsyncMock(return_value=8.0)
    )
    monkeypatch.setattr(
        svc, "fetch_pr_diff", AsyncMock(return_value=("diff excerpt", False))
    )

    item = run(svc.summarize_pr(7, force_refresh=True))

    assert item is not None
    assert item.summary == "Refreshed summary."
    get_stored.assert_not_called()


def _patch_diff(monkeypatch, body, status=200):
    class FakeResp:
        status_code = status

        def __init__(self):
            self.text = body

    class FakeClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def get(self, *a, **k):
            return FakeResp()

    monkeypatch.setattr(gh_mod.httpx, "AsyncClient", FakeClient)


def test_fetch_pr_diff_no_starvation_on_normal_prs(monkeypatch):
    svc = GitHubService()
    body = "diff --git a/f.py b/f.py\n" + "+some changed line of code here\n" * 500
    assert len(body) > 3500  # would have been cut by the old cap
    _patch_diff(monkeypatch, body)
    excerpt, truncated = run(svc.fetch_pr_diff(9))
    assert truncated is False
    assert excerpt == body


def test_fetch_pr_diff_still_flags_monster_diffs(monkeypatch):
    svc = GitHubService()
    body = "x" * (GitHubService.DIFF_MAX_CHARS + 10)
    _patch_diff(monkeypatch, body)
    excerpt, truncated = run(svc.fetch_pr_diff(9))
    assert truncated is True
    assert len(excerpt) == GitHubService.DIFF_MAX_CHARS


def test_jev_scores_from_diff_plus_summary(monkeypatch):
    from app.services import jev_service as jev_module

    seen = {}
    long_diff = "diff --git a/auth.py b/auth.py\n+def login(): pass\n" * 200

    async def fake_post(self, state_text, question_key, instructions, criteria):
        seen["state"] = state_text
        seen["key"] = question_key
        return 9.0

    monkeypatch.setattr(jev_module.JevService, "_post_score", fake_post)
    score = run(jev_module.jev_service.evaluate_impact("Auth rework summary.", long_diff))
    assert score == 9.0
    assert "Auth rework summary." in seen["state"]
    assert "def login" in seen["state"]  # diff rides along, not summary-only
    assert seen["key"] == "impact_score"
