"""Unit tests for the Eval Lab harness (no LLM, no network, no mlflow needed).

Covers: deterministic fixture seed, case-builder counts, checker logic,
MLflow-absent graceful paths, and the metrics summary math.

Run from the repo root:
    python -m pytest tests/test_eval.py -v
"""
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.db.base import Base
from app.services import eval_service as eval_module
from app.services.eval_service import (
    build_curated,
    build_generated,
    ensure_fixtures,
    fixture_seed_rows,
    load_fixtures,
    reply_numbers,
)


def make_ctx():
    prs = [
        {"number": 1, "title": "T1", "author": "EvalBot_Ada",
         "state": "merged", "created_at": datetime(2026, 10, 10, 1, 0, 0)},
        {"number": 2, "title": "T2", "author": "EvalBot_Ada",
         "state": "open", "created_at": datetime(2026, 10, 11, 1, 0, 0)},
    ]
    return {
        "prs": prs, "total": 2, "n_open": 1, "n_merged": 1,
        "numbers": {1, 2}, "top_author": "EvalBot_Ada",
        "trow": prs[1], "target": 2,
        "today_n": {0}, "yest_n": {1}, "od": [],
        "rep_today": None, "n_urgent": 3,
    }


def test_fixture_seed_is_deterministic_and_distinctive():
    rows = fixture_seed_rows()
    assert len(rows) == 32
    refs = [r["ref_name"] for r in rows]
    assert len(set(refs)) == 32
    kinds = {r["kind"] for r in rows}
    assert kinds == {"pr", "email", "engineer"}
    assert all("Eval" in (r["owner"] or "") or "Synthetic" in (r["title"] or "")
               for r in rows)


def test_build_generated_counts(monkeypatch):
    from sqlalchemy.ext.asyncio import async_sessionmaker as _f
    from sqlalchemy.ext.asyncio import create_async_engine as _e

    async def go():
        engine = _e("sqlite+aiosqlite:///:memory:")
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        factory = _f(engine, expire_on_commit=False)
        from app.services import db_service as db_module
        from app.services import eval_service as eval_module

        monkeypatch.setattr(db_module, "AsyncSessionLocal", factory)
        monkeypatch.setattr(eval_module, "AsyncSessionLocal", factory)
        n = await ensure_fixtures()
        fixtures = await load_fixtures()
        return n, fixtures

    import asyncio

    n, fixtures = asyncio.run(go())
    assert n == 32
    assert len(fixtures) == 32
    groups = build_generated(fixtures)
    # 12 pr x4 + 12 email x3 + 8 engineer x2 = 100
    assert len(groups) == 100
    assert all(len(g["questions"]) == 1 for g in groups)


def test_build_curated_counts():
    groups = build_curated(make_ctx())
    n_q = sum(len(g["questions"]) for g in groups)
    assert len(groups) == 20
    assert n_q == 22


def test_reply_numbers_words():
    assert reply_numbers("PR واحد اتفتح") == {1}
    assert reply_numbers("three PRs and #5") == {3, 5}
    assert reply_numbers("someone asked") == set()
    assert reply_numbers("مفيش حاجة") == set()
    # Egyptian dialect "one" (count-yesterday replies like "PR وحدة").
    assert reply_numbers("امبارح اتفتح PR وحدة") == {1}
    assert reply_numbers("اتفتح PR وحد") == {1}


def test_curated_traps_deny_and_correct():
    groups = {g["id"]: g for g in build_curated(make_ctx())}
    trap = groups["trap-999"]["questions"][0]["check"]
    assert trap("مافيش PR برقم 999 عندنا.")[0] == "PASS"
    assert trap("لم يتم العثور على PR رقم 999 في قاعدة البيانات.")[0] == "PASS"
    assert trap("الصبح ما فيه أي PR اتفتح.")[0] == "PASS"
    assert trap("التفاصيل: عنوان وهمي للمؤلف X.")[0] == "FAIL"
    premise = groups["false-premise"]["questions"][0]["check"]
    assert premise("لا، الـ PR رقم 2 مفتوح.")[0] == "PASS"
    assert premise("أيوه مقفول.")[0] == "FAIL"


def test_generated_asks_modeled_fields_only():
    import asyncio

    async def go():
        from sqlalchemy.ext.asyncio import async_sessionmaker as _f
        from sqlalchemy.ext.asyncio import create_async_engine as _e
        from app.db.base import Base
        from app.services import db_service as db_module

        engine = _e("sqlite+aiosqlite:///:memory:")
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        factory = _f(engine, expire_on_commit=False)
        from app.services import eval_service as eval_module

        import unittest.mock as _m
        _m.patch.object(db_module, "AsyncSessionLocal", factory).start()
        _m.patch.object(eval_module, "AsyncSessionLocal", factory).start()
        try:
            await ensure_fixtures()
            fixtures = await load_fixtures()
        finally:
            _m.patch.stopall()
        return fixtures

    import asyncio as _a

    fixtures = _a.run(go())
    by_ref = {f["ref_name"]: f for f in fixtures}
    # Engineer rows model score/tier — questions must not ask for a PR count.
    assert by_ref["EVAL-ENG-01"]["score"] == 5.0
    eng_qs = [q["q"] for g in build_generated(fixtures)
              if g["id"].startswith("gen-EVAL-ENG-01-") for q in g["questions"]]
    assert any("impact score" in q for q in eng_qs)
    assert not any("How many PRs" in q for q in eng_qs)
    # Mail rows model title (not a separate subject column).
    mail_qs = [q["q"] for g in build_generated(fixtures)
               if g["id"].startswith("gen-EVAL-MAIL-01-") for q in g["questions"]]
    assert any("title" in q for q in mail_qs)
    assert not any("subject" in q for q in mail_qs)


def test_summarize_math():
    rows = [
        {"verdict": "PASS", "grounding": 1, "faithfulness": 1, "exact": 1,
         "language_ok": 1, "relevancy": 1, "latency_s": 5.0},
        {"verdict": "FAIL", "grounding": 0, "faithfulness": 0, "exact": 0,
         "language_ok": 1, "relevancy": 1, "latency_s": 15.0},
        {"verdict": "SAFE", "grounding": 1, "faithfulness": None, "exact": None,
         "language_ok": 1, "relevancy": 0, "latency_s": 10.0},
    ]
    s = eval_module._summarize(rows, True, 32, 30.0)
    assert s["question_count"] == 3
    assert s["pass_rate"] == round(1 / 3, 3)
    assert s["fail_rate"] == round(1 / 3, 3)
    # The single FAIL is ungrounded -> fabrication, not quality.
    assert s["fail_fabrication_rate"] == round(1 / 3, 3)
    assert s["fail_quality_rate"] == 0.0
    assert s["faithfulness_avg"] == 0.5  # None excluded
    assert s["avg_latency_s"] == 10.0
    assert s["p95_latency_s"] == 15.0
    assert s["use_judge"] is True


def test_summarize_ttft_math():
    rows = [
        {"verdict": "PASS", "grounding": 1, "faithfulness": 1, "exact": 1,
         "language_ok": 1, "relevancy": 1, "latency_s": 5.0, "ttft_s": 1.0},
        {"verdict": "FAIL", "grounding": 0, "faithfulness": 0, "exact": 0,
         "language_ok": 1, "relevancy": 1, "latency_s": 15.0, "ttft_s": 3.0},
        {"verdict": "SAFE", "grounding": 1, "faithfulness": None, "exact": None,
         "language_ok": 1, "relevancy": 0, "latency_s": 10.0, "ttft_s": None},
    ]
    s = eval_module._summarize(rows, True, 32, 30.0)
    # None TTFT (streaming miss) is excluded, not zeroed.
    assert s["avg_ttft_s"] == 2.0
    assert s["p95_ttft_s"] == 3.0
    assert s["sse_enabled"] is False


def test_summarize_ttft_absent_for_old_rows():
    rows = [
        {"verdict": "PASS", "grounding": 1, "faithfulness": 1, "exact": 1,
         "language_ok": 1, "relevancy": 1, "latency_s": 5.0},
    ]
    s = eval_module._summarize(rows, True, 32, 30.0)
    assert s["avg_ttft_s"] is None
    assert s["p95_ttft_s"] is None


def test_mlflow_params_include_sse_flag(tmp_path, monkeypatch):
    import sys
    import types

    from app.core.config import settings

    seen = {}

    class FakeRun:
        class Info:
            run_id = "rid-1"
        info = Info()

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    fake_mlflow = types.ModuleType("mlflow")
    fake_mlflow.set_tracking_uri = lambda uri: None
    fake_mlflow.set_experiment = lambda name: None

    def fake_start_run(run_name=None):
        seen["run_name"] = run_name
        return FakeRun()

    fake_mlflow.start_run = fake_start_run
    fake_mlflow.log_params = lambda p: seen.setdefault("params", p)
    fake_mlflow.log_metric = lambda k, v: seen.setdefault(
        "metrics", {}).__setitem__(k, v)
    fake_mlflow.log_dict = lambda d, name: None
    monkeypatch.setitem(sys.modules, "mlflow", fake_mlflow)
    monkeypatch.setattr(settings, "chat_sse_enabled", True)

    rows = [
        {"verdict": "PASS", "grounding": 1, "faithfulness": 1, "exact": 1,
         "language_ok": 1, "relevancy": 1, "latency_s": 5.0, "ttft_s": 1.5,
         "group": "g", "question": "q", "lang": "en", "detail": "",
         "tools_used": 1, "reply": "r"},
    ]
    summary = eval_module._summarize(rows, True, 1, 5.0)
    eval_module._log_mlflow(summary, rows)
    assert seen["params"]["sse_enabled"] is True
    assert seen["metrics"]["avg_ttft_s"] == 1.5


def test_delete_eval_run_guarded():
    # Whatever the backend state, delete never raises (False on any failure).
    assert eval_module.delete_eval_run("does-not-exist") is False


def test_faithfulness_skip_rules():
    from app.services.eval_service import faithfulness_without_call

    # Decided without spending an LLM call...
    assert faithfulness_without_call("FAIL") == 0
    assert faithfulness_without_call("SAFE") == 1
    # ...everything else still needs the judge.
    assert faithfulness_without_call("PASS") is None
    assert faithfulness_without_call("ERROR") is None


def test_progress_roundtrip_in_tmp_cwd(tmp_path, monkeypatch):
    from app.services import eval_service as es

    monkeypatch.chdir(tmp_path)
    assert es.read_eval_progress("task-1")["status"] == "unknown"
    es._write_progress("task-1", 4, 62, "running")
    got = es.read_eval_progress("task-1")
    assert (got["current"], got["total"], got["status"]) == (4, 62, "running")
    es._delete_progress("task-1")
    assert es.read_eval_progress("task-1")["status"] == "unknown"


def test_eval_concurrency_default(monkeypatch):
    from app.core.config import settings

    assert settings.eval_max_concurrency >= 1
    monkeypatch.setattr(settings, "eval_max_concurrency", 5)
    assert settings.eval_max_concurrency == 5


def test_delete_eval_run_ok_with_mock(monkeypatch):
    import sys
    import types

    calls = {}

    class FakeClient:
        def delete_run(self, run_id):
            calls["run_id"] = run_id

    fake_tracking = types.ModuleType("mlflow.tracking")
    fake_tracking.MlflowClient = FakeClient
    fake_mlflow = types.ModuleType("mlflow")
    fake_mlflow.set_tracking_uri = lambda uri: calls.setdefault("uri", uri)
    fake_mlflow.tracking = fake_tracking
    monkeypatch.setitem(sys.modules, "mlflow", fake_mlflow)
    monkeypatch.setitem(sys.modules, "mlflow.tracking", fake_tracking)
    assert eval_module.delete_eval_run("abc123") is True
    assert calls["run_id"] == "abc123"


def test_mlflow_absent_is_safe(tmp_path, monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "mlflow_tracking_uri", str(tmp_path / "mlruns"))
    rid = eval_module._log_mlflow(
        {"use_judge": True, "question_count": 1, "actor_model": "m",
         "judge_model": "j", "pass_rate": 1.0},
        [{"group": "g", "question": "q"}],
    )
    # Either logged (mlflow present) or gracefully skipped (absent) — never raises.
    assert rid is None or isinstance(rid, str)
    assert isinstance(eval_module.recent_runs(limit=5), list)
