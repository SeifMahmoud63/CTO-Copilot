"""Unit tests for the daily CTO report pipeline (hybrid: metrics + AI + PDF).

Run from the repo root:
    python -m pytest tests/test_daily_reports.py -v
"""
import asyncio
import json
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock

from app.services import report_service as reports


def run(coro):
    return asyncio.run(coro)


def pr(number, state, created_hours_ago, updated_hours_ago=None, overdue_days=0,
       author="SeifMahmoud63", score=6.0):
    now = datetime.now(timezone.utc)
    return SimpleNamespace(
        number=number,
        title=f"PR {number}",
        author=author,
        html_url=f"http://x/{number}",
        impact_score=score,
        state=state,
        created_at=(now - timedelta(hours=created_hours_ago)).isoformat(),
        updated_at=(now - timedelta(hours=updated_hours_ago if updated_hours_ago is not None else created_hours_ago)).isoformat(),
        is_overdue=overdue_days >= 5,
        overdue_days=overdue_days,
    )


NOW = datetime.now(timezone.utc)
ENGS = [
    {"author": "SeifMahmoud63", "author_avatar": None, "pr_count": 3,
     "total_score": 18.4, "avg_score": 6.1, "tier": "Solid Contributor"},
    {"author": "dev2", "author_avatar": None, "pr_count": 1,
     "total_score": 8.5, "avg_score": 8.5, "tier": "Critical Driver"},
]


def test_collect_metrics_window_and_newly_overdue():
    prs = [
        pr(1, "open", 5, overdue_days=0),        # opened in window
        pr(2, "merged", 50, 5),                  # merged in window (updated 5h ago)
        pr(3, "closed", 70, 30),                 # closed OUTSIDE window
        pr(4, "open", 24 * 6, overdue_days=5),   # crossed the 5d threshold today
        pr(5, "open", 24 * 20, overdue_days=20),  # long overdue, not new
    ]
    m = reports.collect_daily_metrics(prs, ENGS, NOW, threshold_days=5)
    assert m["counts"]["opened_24h"] == 1
    assert m["counts"]["merged_24h"] == 1
    assert m["counts"]["closed_24h"] == 0
    assert m["counts"]["newly_overdue"] == 1
    assert m["newly_overdue"][0]["number"] == 4
    assert m["counts"]["total_open"] == 3
    assert m["top_engineer"]["author"] == "dev2"
    assert m["low_engineer"]["author"] == "SeifMahmoud63"


def test_analysis_prompt_has_language_and_sections():
    prompt = reports.build_analysis_prompt({"counts": {}}, "Arabic")
    assert "Arabic" in prompt
    for section in ("Executive Summary", "Bottlenecks", "Recommendations", "Top & Low Performers"):
        assert section in prompt
    prompt_en = reports.build_analysis_prompt({"counts": {}}, "English")
    assert "English" in prompt_en
    assert "ENTIRELY in English" in prompt_en


def test_report_language_default_is_english():
    from app.core.config import Settings

    assert Settings.model_fields["report_language"].default == "English"


def test_strip_markdown_removes_markers():
    assert reports.strip_markdown("**Executive Summary**") == "Executive Summary"
    assert reports.strip_markdown("## Bottlenecks") == "Bottlenecks"
    assert reports.strip_markdown("Review `api.py` now") == "Review api.py now"
    assert reports.strip_markdown("- plain item stays") == "- plain item stays"
    assert reports.strip_markdown("") == ""


def test_format_generated_label_marks_zone():
    assert reports.format_generated_label("2026-10-11T12:54:09.897330+03:00") == "2026-10-11 12:54 (UTC+03:00)"
    assert reports.format_generated_label("2026-10-11T09:54:34+00:00") == "2026-10-11 09:54 (UTC+00:00)"
    assert reports.format_generated_label("2026-10-11T09:54:34Z") == "2026-10-11 09:54 (UTC+00:00)"
    assert reports.format_generated_label("") == ""
    assert reports.format_generated_label("not-a-date") == "not-a-date"


def test_shape_for_pdf_arabic_changes_english_untouched():
    ar = "تقرير الأداء اليومي"
    assert reports.shape_for_pdf(ar) != ar  # reshaped presentation forms
    assert reports.shape_for_pdf("Daily Report") == "Daily Report"


def test_build_pdf_creates_valid_file(tmp_path):
    out = str(tmp_path / "daily-report-2026-10-10.pdf")
    metrics = reports.collect_daily_metrics(
        [pr(1, "open", 5)], ENGS, NOW, threshold_days=5
    )
    result = reports.build_pdf(
        "2026-10-10", "CTO Daily Report — 2026-10-10",
        metrics, "ملخص تنفيذي: الأداء جيد.\n- توصية أولى", out,
    )
    data = open(result, "rb").read()
    assert data.startswith(b"%PDF")
    assert len(data) > 2000


def test_db_report_roundtrip_sqlite(tmp_path, monkeypatch):
    """save_report/get_reports/get_report against throwaway SQLite."""
    import aiosqlite  # noqa: F401 (ensures async sqlite driver present)
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine, AsyncSession

    import app.services.db_service as db_module
    from app.models import Base

    db_file = tmp_path / "reports.db"
    engine = create_async_engine(f"sqlite+aiosqlite:///{db_file}")
    run(_create_all(engine))
    monkeypatch.setattr(
        db_module, "AsyncSessionLocal",
        async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False),
    )
    try:
        saved = run(db_module.db_service.save_report(
            report_date="2026-10-10", title="T", executive_summary="S",
            metrics_json="{}", pdf_path="/tmp/x.pdf",
            prs_opened=1, prs_merged=2, prs_closed=0, overdue_count=1,
        ))
        assert saved is not None and saved.id is not None

        # Re-save same date upserts instead of duplicating.
        run(db_module.db_service.save_report(
            report_date="2026-10-10", title="T2", executive_summary="S2",
            metrics_json="{}", pdf_path="/tmp/y.pdf",
            prs_opened=5, prs_merged=5, prs_closed=5, overdue_count=5,
        ))
        listing = run(db_module.db_service.get_reports())
        assert len(listing) == 1
        assert listing[0]["title"] == "T2"
        assert listing[0]["prs_opened"] == 5

        full = run(db_module.db_service.get_report(listing[0]["id"]))
        assert full["pdf_path"] == "/tmp/y.pdf"
        assert run(db_module.db_service.get_report(9999)) is None
    finally:
        run(engine.dispose())


async def _create_all(engine):
    from app.models import Base

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


def test_generate_daily_report_orchestration(tmp_path, monkeypatch):
    """Full hybrid pipeline with mocked IO: metrics -> AI -> PDF -> DB."""
    from app.core.config import settings
    import app.services.db_service as db_module
    import app.services.github_service as gh_module
    from app.services import llm_service as llm_module

    monkeypatch.setattr(settings, "reports_dir", str(tmp_path))
    monkeypatch.setattr(settings, "report_language", "Arabic")
    monkeypatch.setattr(settings, "pr_stale_threshold_days", 5)

    fake_prs = [pr(1, "open", 5), pr(2, "merged", 50, 5)]
    monkeypatch.setattr(gh_module.github_service, "get_pull_requests",
                        AsyncMock(return_value=fake_prs))
    monkeypatch.setattr(db_module.db_service, "get_engineers",
                        AsyncMock(return_value=ENGS))
    monkeypatch.setattr(llm_module.llm_service, "generate_pr_summary",
                        lambda prompt: ("ملخص تنفيذي مولد.", "bedrock_qwen", "Qwen3-32B"))
    saved = {}
    monkeypatch.setattr(
        db_module.db_service, "save_report", AsyncMock(side_effect=lambda **kw: saved.update(kw) or SimpleNamespace(id=7))
    )

    out = run(reports.generate_daily_report("2026-10-10"))

    assert out["id"] == 7
    assert out["report_date"] == "2026-10-10"
    assert saved["prs_opened"] == 1 and saved["prs_merged"] == 1
    assert saved["executive_summary"] == "ملخص تنفيذي مولد."
    assert json.loads(saved["metrics_json"])["counts"]["opened_24h"] == 1
    import os

    assert os.path.exists(out["pdf_path"])
    assert os.path.getsize(out["pdf_path"]) > 2000


def test_celery_beat_schedule_matches_settings():
    from app.core.config import settings
    from app.services.celery_app import celery

    entry = celery.conf.beat_schedule["daily-cto-report"]
    assert entry["task"] == "reports.generate_daily"
    sched = entry["schedule"]
    assert sched.hour == {settings.report_hour}
    assert sched.minute == {settings.report_minute}
    assert celery.conf.timezone == settings.report_timezone
