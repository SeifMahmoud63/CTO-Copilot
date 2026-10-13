"""Eval Lab: torture-test harness with MLflow tracking.

Pipeline per run:
1. ensure_fixtures(): deterministic synthetic rows (idempotent reseed).
2. build_cases(): ~24 curated adversarial groups + ~100 generated from
   fixtures/real tables (fresh DB snapshot as ground truth).
3. Execute: fresh chat session per group -> capture tool observations ->
   score every reply (deterministic grounding gate + judge faithfulness +
   exact-identity + language + relevancy + latency).
4. Log params/metrics/per-question table to MLflow; return the summary.

The `use_judge` toggle only flips the CHAT pipeline's judge gate — the eval
always scores with the judge model, so judge-on vs judge-off runs are comparable.
"""
import asyncio
import json
import logging
import os
import re
import time
from contextvars import ContextVar
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import delete, select

from app.core.config import settings
from app.db.session import AsyncSessionLocal
from app.models import EvalFixture
from app.services.chat_service import ARABIC_MONTHS, ENGLISH_MONTHS

logger = logging.getLogger("cto-copilot.eval")

AR_RE = re.compile(r"[\u0600-\u06FF]")
TIME_RE = re.compile(r"\d{1,2}:\d{2}")
PRREF_RE = re.compile(r"#\s*(\d+)")
DIGIT_RE = re.compile(r"\d+")
WORD_NUM = {
    "صفر": 0, "واحد": 1, "واحدة": 1, "واحده": 1, "وحدة": 1, "وحده": 1, "وحد": 1,
    "اتنين": 2, "اثنين": 2,
    "تلاتة": 3, "تلاته": 3, "ثلاثة": 3, "اربعة": 4, "أربعة": 4,
    "خمسة": 5, "ستة": 6, "سبعة": 7, "تمانية": 8, "ثمانية": 8,
    "تسعة": 9, "عشرة": 10,
    "zero": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
    "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
}
FALLBACK_MARKS = ["مقدرتش أتحقق", "couldn't verify", "not showing unconfirmed",
                  "Could not get a response"]
DENY_MARKS = ["لا يوجد", "ما فيش", "مافيش", "مفيش", "ما فيه", "لم يتم العثور",
              "not found", "لا توجد", "غير موجود", "couldn't find",
              "no pr", "no pull", "none", "مالناش", "معندناش", "ماعندناش",
              "ما عندناش", "لم يُفتح", "لم يفتح", "لا وجود", "لا شيء", "لاشيء"]

EXPERIMENT = "cto-copilot-eval"


def reply_numbers(reply: str) -> set:
    nums = {int(x) for x in DIGIT_RE.findall(reply or "")}
    toks = set(re.findall(r"\w+", (reply or "").lower()))
    return nums | {WORD_NUM[t] for t in toks if t in WORD_NUM}


def is_fallback(reply: str) -> bool:
    low = (reply or "").lower()
    return any(m.lower() in low for m in FALLBACK_MARKS)


def denies(reply: str) -> bool:
    return any(m in (reply or "").lower() for m in DENY_MARKS)


# ---------------- Fixture seed (deterministic, clearly fake) ---------------- #

def fixture_seed_rows() -> List[Dict[str, Any]]:
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    domains = ["checkout", "payments", "search", "auth", "cache", "queue"]
    eng_names = ["EvalBot_Ada", "EvalBot_Bjorn", "EvalBot_Cleo", "EvalBot_Dan"]
    states = ["open", "merged", "closed"]
    rows: List[Dict[str, Any]] = []
    for i in range(1, 13):
        score = round(4.0 + (i * 0.43), 1)
        tier = ("Critical Driver" if score >= 8.0 else
                "High Impact" if score >= 6.5 else
                "Solid Contributor" if score >= 5.0 else "Routine Support")
        rows.append({
            "kind": "pr",
            "ref_name": "EVAL-PR-%02d" % i,
            "title": "Synthetic %s probe %s%d" % (domains[(i - 1) % len(domains)], chr(64 + i), i),
            "owner": eng_names[(i - 1) % len(eng_names)],
            "state": states[(i - 1) % len(states)],
            "event_date": now - timedelta(days=i),
            "score": score,
            "tier": tier,
        })
    senders = ["eval-boss", "eval-client", "eval-hr"]
    tiers = ["Reply Now", "Reply Today", "FYI / Soon", "Archive"]
    for i in range(1, 13):
        rows.append({
            "kind": "email",
            "ref_name": "EVAL-MAIL-%02d" % i,
            "title": "Synthetic notice %02d: action requested" % i,
            "owner": "%s@example-test.invalid" % senders[(i - 1) % len(senders)],
            "state": "unread",
            "event_date": now - timedelta(hours=i * 5),
            "score": round(3.0 + (i * 0.55), 1),
            "tier": tiers[(i - 1) % len(tiers)],
        })
    for i in range(1, 9):
        score = round(4.5 + (i * 0.5), 1)
        rows.append({
            "kind": "engineer",
            "ref_name": "EVAL-ENG-%02d" % i,
            "title": None,
            "owner": "EvalEng_%s" % ["Aria", "Bram", "Cora", "Dev", "Elif", "Finn", "Gia", "Hugo"][i - 1],
            "state": "active",
            "event_date": None,
            "score": score,
            "tier": ("Critical Driver" if score >= 8.0 else
                     "High Impact" if score >= 6.5 else "Solid Contributor"),
        })
    return rows


async def ensure_fixtures() -> int:
    """Wipe EVAL-* rows and reseed deterministically (dates stay relative)."""
    async with AsyncSessionLocal() as session:
        async with session.begin():
            await session.execute(
                delete(EvalFixture).where(EvalFixture.ref_name.like("EVAL-%")))
            for row in fixture_seed_rows():
                session.add(EvalFixture(**row))
    return len(fixture_seed_rows())


async def load_fixtures() -> List[Dict[str, Any]]:
    async with AsyncSessionLocal() as session:
        res = await session.execute(select(EvalFixture).order_by(EvalFixture.id))
        out = []
        for r in res.scalars().all():
            out.append({
                "kind": r.kind, "ref_name": r.ref_name, "title": r.title,
                "owner": r.owner, "state": r.state,
                "event_date": r.event_date.isoformat() if r.event_date else None,
                "score": r.score, "tier": r.tier,
            })
        return out


# ---------------- Case model ---------------- #
# A group shares one chat session (multi-turn chains); singles stand alone.
# Case: {id, question, lang, exact (expected verbatim token or None),
#        check(reply, ctx) -> (verdict, detail)}

def _refs_outside(reply: str, numbers: set) -> list:
    return sorted({int(x) for x in PRREF_RE.findall(reply or "")} - numbers)


def build_curated(ctx: Dict[str, Any]) -> List[Dict[str, Any]]:
    prs = ctx["prs"]
    total, n_open, n_merged = ctx["total"], ctx["n_open"], ctx["n_merged"]
    top_author = ctx["top_author"]
    today_n, yest_n, od = ctx["today_n"], ctx["yest_n"], ctx["od"]
    numbers = ctx["numbers"]
    trow, target = ctx["trow"], ctx["target"]
    groups: List[Dict[str, Any]] = []

    def count_case(cid, q, lang, vals):
        def go(reply):
            if is_fallback(reply):
                return ("SAFE", "refused")
            if _refs_outside(reply, numbers):
                return ("FAIL", "invented refs")
            if reply_numbers(reply) & set(vals):
                return ("PASS", "expected count present")
            if 0 in vals and denies(reply):
                return ("PASS", "expected zero (semantically denied)")
            return ("FAIL", "expected one of %s" % sorted(vals))
        return {"id": cid, "questions": [{"q": q, "lang": lang, "exact": None, "check": go}]}

    groups.append(count_case("count-total", "عندنا كام PR؟", "ar", {total}))
    groups.append(count_case("count-open", "How many open PRs?", "en", {n_open}))
    groups.append(count_case("count-merged", "كام PR merged؟", "ar", {n_merged}))
    groups.append(count_case("count-today", "عندنا كام PR انهارده؟", "ar", today_n))
    groups.append(count_case("count-yesterday", "كام PR اتفتح امبارح؟", "ar", yest_n))

    def overdue_go(reply):
        if is_fallback(reply):
            return ("SAFE", "refused")
        if _refs_outside(reply, numbers):
            return ("FAIL", "invented refs")
        if not od and (denies(reply) or 0 in reply_numbers(reply)):
            return ("PASS", "correctly empty")
        if od and all(str(n) in reply for n in od):
            return ("PASS", "lists overdue")
        if od and reply_numbers(reply) & {len(od)}:
            return ("PASS", "count matches")
        return ("FAIL", "expected overdue %s" % od)
    groups.append({"id": "overdue", "questions": [
        {"q": "فيه اي PRs متعلقه؟", "lang": "ar", "exact": None, "check": overdue_go}]})

    def exact_go(reply):
        if is_fallback(reply):
            return ("SAFE", "refused")
        if top_author and top_author in reply:
            return ("PASS", "exact username")
        return ("FAIL", "exact name missing/misspelled")
    groups.append({"id": "top-ar", "questions": [
        {"q": "مين أكتر حد عمل PRs؟", "lang": "ar", "exact": top_author, "check": exact_go}]})
    groups.append({"id": "top-exact", "questions": [
        {"q": "اكتب اسم التوب contributor بالظبط حرف بحرف", "lang": "ar", "exact": top_author, "check": exact_go}]})

    def detail_go(reply):
        if is_fallback(reply):
            return ("SAFE", "refused")
        if _refs_outside(reply, numbers):
            return ("FAIL", "invented refs")
        if trow["author"] in reply and str(target) in reply:
            return ("PASS", "author+number present")
        return ("FAIL", "details missing")

    def follow_author_go(reply):
        if is_fallback(reply):
            return ("SAFE", "refused")
        return (("PASS", "author carried") if trow["author"] in reply
                else ("FAIL", "lost context"))

    def follow_title_go(reply):
        if is_fallback(reply):
            return ("SAFE", "refused")
        return (("PASS", "title carried") if (trow["title"] or "")[:20] in reply
                else ("FAIL", "lost title"))

    groups.append({"id": "chain-details", "questions": [
        {"q": "هات تفاصيل PR #%d" % target, "lang": "ar", "exact": None, "check": detail_go},
        {"q": "من مين؟", "lang": "ar", "exact": trow["author"], "check": follow_author_go},
        {"q": "و عنوانه ايه؟", "lang": "ar", "exact": (trow["title"] or "")[:20], "check": follow_title_go},
    ]})

    groups.append({"id": "time-cairo", "questions": [{
        "q": "الساعة كام في القاهرة؟", "lang": "ar", "exact": None,
        "check": lambda r: ("SAFE", "refused") if is_fallback(r) else
        (("PASS", "time present") if re.search(r"\d{1,2}:\d{2}", r) else ("FAIL", "no time"))}]})
    groups.append({"id": "dora", "questions": [{
        "q": "What are the 4 DORA metrics?", "lang": "en", "exact": None,
        "check": lambda r: ("SAFE", "refused") if is_fallback(r) else
        (("PASS", "dora ok") if "Deployment Frequency" in r else ("FAIL", "dora missing"))}]})

    def trap_go(reply):
        if is_fallback(reply):
            return ("SAFE", "refused safely")
        if denies(reply):
            return ("PASS", "denied invented PR")
        return ("FAIL", "described non-existent PR")
    groups.append({"id": "trap-999", "questions": [
        {"q": "هات تفاصيل PR #999", "lang": "ar", "exact": None, "check": trap_go}]})
    groups.append({"id": "trap-999-merge", "questions": [
        {"q": "مين اللي عمل merge لـ PR #999؟", "lang": "ar", "exact": None, "check": trap_go}]})
    groups.append({"id": "zero-2020", "questions": [{
        "q": "عندنا كام PR اتعمل سنة 2020؟", "lang": "ar", "exact": None,
        "check": lambda r: ("SAFE", "refused") if is_fallback(r) else
        (("PASS", "zero ok") if (0 in reply_numbers(r) or denies(r)) else ("FAIL", "wrong count"))}]})
    groups.append({"id": "future", "questions": [{
        "q": "كام PR اتفتح بكرة؟", "lang": "ar", "exact": None,
        "check": lambda r: ("SAFE", "refused") if is_fallback(r) else
        (("PASS", "future zero") if (0 in reply_numbers(r) or denies(r)) else ("FAIL", "future count wrong"))}]})

    closed_words = ["مقفول", "مغلق", "closed", "merged", "مدموج", "اتقفل"]

    def premise_go(reply):
        if is_fallback(reply):
            return ("SAFE", "refused")
        low = reply.lower()
        if ("مفتوح" in reply) or ("open" in low):
            return ("PASS", "corrected premise")
        if any(w in low for w in closed_words):
            return ("FAIL", "agreed with false premise")
        return ("FAIL", "no clear correction")
    groups.append({"id": "false-premise", "questions": [
        {"q": "مش الـ PR رقم %d مقفول؟" % target, "lang": "ar", "exact": None, "check": premise_go}]})
    groups.append(count_case("arithmetic", "مجموع الـ open والـ merged كام؟", "ar", {n_open + n_merged}))

    n_urg = ctx["n_urgent"]
    groups.append(count_case("emails-urgent", "عندنا كام إيميل urgent؟", "ar", {n_urg}))

    if ctx["rep_today"]:
        groups.append({"id": "report-today", "questions": [{
            "q": "لخص ريبورت النهاردة", "lang": "ar", "exact": None,
            "check": lambda r: ("SAFE", "refused") if is_fallback(r) else
            (("PASS", "report ok") if len(r) > 80 else ("FAIL", "too thin"))}]})
    else:
        groups.append({"id": "report-today", "questions": [{
            "q": "لخص ريبورت النهاردة", "lang": "ar", "exact": None,
            "check": lambda r: ("PASS", "correctly missing") if denies(r) else
            (("SAFE", "refused") if is_fallback(r) else ("FAIL", "invented report"))}]})

    def top_en_go(reply):
        if is_fallback(reply):
            return ("SAFE", "refused")
        if AR_RE.search(reply):
            return ("FAIL", "arabic in english")
        if top_author and top_author in reply:
            return ("PASS", "english+exact")
        return ("FAIL", "name missing")
    groups.append({"id": "top-en", "questions": [
        {"q": "Who is the top contributor?", "lang": "en", "exact": top_author, "check": top_en_go}]})
    return groups


def _date_checker(iso: str):
    """Accept ISO (2026-10-05) or the human form the agent uses (5 أكتوبر)."""
    day_n = int(iso[8:10])
    month_words = set(ARABIC_MONTHS) | set(ENGLISH_MONTHS)

    def go(reply: str):
        if iso in (reply or ""):
            return ("PASS", "iso date present")
        toks = set(re.findall(r"\w+", (reply or "").lower()))
        if day_n in reply_numbers(reply) and (toks & month_words):
            return ("PASS", "human date present")
        return ("FAIL", "expected date %s" % iso)
    return go


# Any `exact` expectation shaped like YYYY-MM-DD is a calendar date, not a
# verbatim string: score it with the same date equivalence as the verdict
# checker (ISO or human form both count). General rule — applies to every
# current and future date question, no per-question flags.
_ISO_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def exact_for_expected(expected: str, reply: str) -> int:
    """Date-aware exact match: ISO dates accept the human form too."""
    exp = (expected or "").strip()
    if _ISO_DATE_RE.match(exp):
        try:
            return 1 if _date_checker(exp)(reply)[0] == "PASS" else 0
        except Exception:
            return 1 if exp in (reply or "") else 0
    return 1 if exp and exp in (reply or "") else 0


def build_generated(fixtures: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    groups: List[Dict[str, Any]] = []
    for f in fixtures:
        ref, kind = f["ref_name"], f["kind"]
        if kind == "pr":
            qs = [
                ("What is the title of %s in the eval fixtures table?" % ref, f["title"], None),
                ("Who authored %s in the eval fixtures table?" % ref, f["owner"], None),
                ("What is the state of %s in the eval fixtures table?" % ref, f["state"], None),
                ("On which date was %s created (eval fixtures table)?" % ref,
                 (f["event_date"] or "")[:10], _date_checker((f["event_date"] or "")[:10])),
            ]
        elif kind == "email":
            qs = [
                ("Who sent %s in the eval fixtures table?" % ref, f["owner"], None),
                ("What is the title of %s in the eval fixtures table?" % ref, f["title"], None),
                ("What urgency tier is %s in the eval fixtures table?" % ref, f["tier"], None),
            ]
        else:
            # Engineer fixtures model score/tier only (no PR-count column), so
            # ask exactly what is modeled — never invite the agent to invent.
            qs = [
                ("What is the impact score of %s (eval fixtures table)?" % f["owner"],
                 ("%g" % (f["score"] or 0)), None),
                ("What tier is %s in the eval fixtures table?" % f["owner"], f["tier"], None),
            ]
        for i, (q, expected, custom) in enumerate(qs):
            def go(reply, _exp=expected, _custom=custom):
                if is_fallback(reply):
                    return ("SAFE", "refused")
                if _custom is not None:
                    return _custom(reply)
                if _exp and _exp in reply:
                    return ("PASS", "exact match")
                return ("FAIL", "expected %r" % (_exp or ""))
            groups.append({"id": "gen-%s-%d" % (ref, i),
                           "questions": [{"q": q, "lang": "en", "exact": expected, "check": go}]})
    return groups


# ---------------- Execution + scoring ---------------- #

_current_capture: ContextVar[Optional[Dict[str, Any]]] = ContextVar(
    "eval_current_capture", default=None
)


class ObsCapture:
    """Installs counting wrappers once; per-question state via ContextVar.

    Safe under asyncio.gather: every question coroutine sets its own dict,
    and asyncio Tasks isolate contexts, so concurrent questions never mix
    observations. Install once per run, restore at the end.
    """

    def __init__(self):
        self._originals: Dict[str, Any] = {}

    def install(self):
        from app.services.chat_service import chat_service

        for name, tool in list(chat_service.tools_by_name.items()):
            if name in self._originals:
                continue
            self._originals[name] = tool

            class Cap:
                def __init__(inner, n, real):
                    inner._n = n
                    inner._real = real
                    inner.name = getattr(real, "name", n)

                async def ainvoke(inner, args):
                    out = await inner._real.ainvoke(args)
                    cur = _current_capture.get()
                    if cur is not None:
                        cur["calls"][inner._n] = cur["calls"].get(inner._n, 0) + 1
                        cur["texts"].append(str(out)[:2000])
                        try:
                            cur.setdefault("args", []).append(
                                json.dumps(dict(args), ensure_ascii=False))
                        except Exception:
                            cur.setdefault("args", []).append(str(args))
                    return out

            chat_service.tools_by_name[name] = Cap(name, tool)

    def restore(self):
        from app.services.chat_service import chat_service

        for name, tool in self._originals.items():
            chat_service.tools_by_name[name] = tool
        self._originals = {}


def faithfulness_without_call(verdict: str) -> Optional[int]:
    """Decide faithfulness without spending an LLM call, or None if needed.

    - FAIL verdicts already failed grounding/checkers -> 0 (a second opinion
      cannot resurrect an ungrounded reply).
    - SAFE verdicts (refusals, denials, fallbacks) make no affirmative repo
      claims -> 1.
    - Anything else (PASS/ERROR) still needs the judge -> None.
    """
    if verdict == "FAIL":
        return 0
    if verdict == "SAFE":
        return 1
    return None


def _progress_key(task_id: str) -> str:
    safe = re.sub(r"[^A-Za-z0-9_-]", "_", task_id or "local")
    return f"eval:progress:{safe}"


# In-memory fallback when Redis is unreachable (tests / cold start).
# No local files are ever written — progress lives in Redis, else RAM.
_MEM_PROGRESS: Dict[str, Dict[str, Any]] = {}
_redis_client = None


def _get_redis():
    global _redis_client
    if _redis_client is not None:
        return _redis_client
    try:
        import redis as _redis

        _redis_client = _redis.StrictRedis.from_url(
            settings.celery_broker_url, db=1,
            socket_timeout=2, socket_connect_timeout=2,
            decode_responses=True,
        )
        return _redis_client
    except Exception:
        return None


def _progress_path(task_id: str) -> str:
    """Legacy helper kept for compat — returns the Redis key (no disk use)."""
    return _progress_key(task_id)


def _write_progress(task_id: Optional[str], current: int, total: int, status: str) -> None:
    if not task_id:
        return
    payload = {"task_id": task_id, "current": current,
               "total": total, "status": status}
    _MEM_PROGRESS[_progress_key(task_id)] = payload
    try:
        r = _get_redis()
        if r is not None:
            r.setex(_progress_key(task_id), 86400, json.dumps(payload))
    except Exception as e:
        logger.debug(f"Progress Redis write skipped: {e}")


def _delete_progress(task_id: Optional[str]) -> None:
    if not task_id:
        return
    _MEM_PROGRESS.pop(_progress_key(task_id), None)
    try:
        r = _get_redis()
        if r is not None:
            r.delete(_progress_key(task_id))
    except Exception:
        pass


def read_eval_progress(task_id: str) -> Dict[str, Any]:
    """Freshness for the Eval Lab card (X of Y). Redis → memory. Never raises."""
    try:
        r = _get_redis()
        if r is not None:
            raw = r.get(_progress_key(task_id))
            if raw:
                data = json.loads(raw)
                return {"task_id": task_id, "current": int(data.get("current", 0)),
                        "total": int(data.get("total", 0)),
                        "status": str(data.get("status", "running"))}
    except Exception:
        pass
    try:
        data = _MEM_PROGRESS.get(_progress_key(task_id))
        if data:
            return {"task_id": task_id, "current": int(data.get("current", 0)),
                    "total": int(data.get("total", 0)),
                    "status": str(data.get("status", "running"))}
    except Exception:
        pass
    return {"task_id": task_id, "current": 0, "total": 0, "status": "unknown"}


async def run_eval(use_judge: bool = True, max_questions: Optional[int] = None,
                 task_id: Optional[str] = None,
                 max_concurrency: Optional[int] = None,
                 sse_enabled: Optional[bool] = None) -> Dict[str, Any]:
    """Full eval run. Returns the summary dict (also logged to MLflow)."""
    from app.services.chat_service import chat_service
    from app.services.judge_service import judge_service
    from app.core.config import settings as _s

    t_run = time.perf_counter()
    prev_judge = _s.judge_enabled
    _s.judge_enabled = bool(use_judge)
    # Snapshot the SSE flag at launch (like use_judge): the worker is a
    # separate process whose live settings never see the web runtime toggle,
    # so reading settings at summarize time always logged OFF.
    run_sse = settings.chat_sse_enabled if sse_enabled is None else bool(sse_enabled)
    cap = ObsCapture()
    cap.install()
    rows: List[Dict[str, Any]] = []
    try:
        n_fixtures = await ensure_fixtures()
        fixtures = await load_fixtures()

        from sqlalchemy import text as _t
        from app.db.session import AsyncSessionLocal as _S

        async def q1(sql):
            async with _S() as s:
                return (await s.execute(_t(sql))).mappings().all()

        prs = [dict(r) for r in await q1(
            "SELECT number, title, author, state, created_at FROM pull_requests")]
        now_utc = datetime.now(timezone.utc).date()

        def day_of(v):
            return str(v)[:10]

        total = len(prs)
        n_open = sum(1 for p in prs if str(p["state"]).lower() == "open")
        n_merged = sum(1 for p in prs if str(p["state"]).lower() == "merged")
        numbers = {int(p["number"]) for p in prs}
        authors: Dict[str, int] = {}
        for p in prs:
            authors[p["author"]] = authors.get(p["author"], 0) + 1
        top_author = max(authors, key=authors.get) if authors else ""
        open_rows = [p for p in prs if str(p["state"]).lower() == "open"]
        target = int(open_rows[0]["number"]) if open_rows else (max(numbers) if numbers else 1)
        trow = next(p for p in prs if int(p["number"]) == target)
        today_n = {sum(1 for p in prs if day_of(p["created_at"]) == str(now_utc))}
        yest_n = {sum(1 for p in prs if day_of(p["created_at"]) == str(now_utc - timedelta(days=1)))}
        od = [int(p["number"]) for p in await q1(
            "SELECT number FROM pull_requests WHERE is_overdue = 1")]
        rep = await q1("SELECT title FROM daily_reports ORDER BY report_date DESC LIMIT 1")
        urg = await q1("SELECT COUNT(*) AS c FROM emails WHERE urgency_tier = 'Reply Now'")
        ctx = {"prs": prs, "total": total, "n_open": n_open, "n_merged": n_merged,
               "numbers": numbers, "top_author": top_author, "trow": trow,
               "target": target, "today_n": today_n, "yest_n": yest_n, "od": od,
               "rep_today": None, "n_urgent": int(urg[0]["c"]) if urg else 0}
        # Report recency: only "today" counts if the latest report is from today.
        rep_date = await q1("SELECT report_date FROM daily_reports ORDER BY report_date DESC LIMIT 1")
        if rep_date and str(rep_date[0]["report_date"]) == str(now_utc):
            ctx["rep_today"] = rep[0]

        groups = build_curated(ctx) + build_generated(fixtures)
        if max_questions is not None:
            kept, seen = [], 0
            for g in groups:
                if seen >= max_questions:
                    break
                room = max_questions - seen
                qs = g["questions"][:room]
                if qs:
                    kept.append({"id": g["id"], "questions": qs})
                    seen += len(qs)
            groups = kept
        total_q = sum(len(g["questions"]) for g in groups)

        conc = max(1, settings.eval_max_concurrency
                   if max_concurrency is None else max_concurrency)
        _write_progress(task_id, 0, total_q, "running")
        sem = asyncio.Semaphore(conc)
        lock = asyncio.Lock()
        done = 0

        async def run_group(g):
            nonlocal done
            sess = await chat_service.create_session(title="eval-%s" % g["id"])
            sid = sess["id"]
            local_rows: List[Dict[str, Any]] = []
            try:
                for item in g["questions"]:
                    token = _current_capture.set({"calls": {}, "texts": []})
                    try:
                        async with sem:
                            t0 = time.perf_counter()
                            ttft_s = None
                            try:
                                r = await chat_service.send_message(sid, item["q"])
                                reply = r.get("reply", "")
                                ttft_s = r.get("ttft_s")
                            except Exception as e:
                                reply = ""
                                item_err = "exception: %s" % e
                            else:
                                item_err = ""
                            dt = round(time.perf_counter() - t0, 1)
                            cur = _current_capture.get() or {"calls": {}, "texts": []}
                            obs = list(cur["texts"])
                            call_args = list(cur.get("args", []))
                            tools_used = sum(cur["calls"].values())
                    finally:
                        _current_capture.reset(token)
                    try:
                        verdict, detail = item["check"](reply)
                    except Exception as e:
                        verdict, detail = "ERROR", "checker crashed: %s" % e
                    if item_err:
                        verdict, detail = "ERROR", item_err
                    gate = judge_service.deterministic_gate(reply, obs, tool_calls=call_args)
                    grounding = 1 if gate["verdict"] == "PASS" else 0
                    decided = faithfulness_without_call(verdict)
                    if decided is not None:
                        faith = decided
                    else:
                        try:
                            # NOTE: llm_judge is synchronous (blocking Bedrock call).
                            fj = judge_service.llm_judge(item["q"], reply, obs)
                            faith = 1 if fj.get("verdict") == "PASS" else 0
                        except Exception:
                            faith = None
                    exp = item.get("exact")
                    exact = exact_for_expected(exp, reply) if exp else None
                    if item.get("lang") == "en":
                        lang_ok = 0 if AR_RE.search(reply or "") else 1
                    else:
                        lang_ok = 1 if AR_RE.search(reply or "") else 0
                    relev = 0 if verdict in ("SAFE", "ERROR") else 1
                    local_rows.append({
                        "group": g["id"], "question": item["q"], "lang": item.get("lang"),
                        "verdict": verdict, "detail": detail,
                        "grounding": grounding, "faithfulness": faith,
                        "exact": exact, "language_ok": lang_ok, "relevancy": relev,
                        "latency_s": dt, "ttft_s": ttft_s, "tools_used": tools_used,
                        "reply": (reply or "")[:500],
                    })
                    async with lock:
                        done += 1
                        _write_progress(task_id, done, total_q, "running")
            finally:
                try:
                    await chat_service.delete_session(sid)
                except Exception:
                    pass
            return local_rows

        try:
            for part in await asyncio.gather(*(run_group(g) for g in groups)):
                rows.extend(part)
        except Exception:
            _write_progress(task_id, done, total_q, "failed")
            raise

        summary = _summarize(rows, use_judge, len(fixtures), time.perf_counter() - t_run,
                         sse_enabled=run_sse)
        _log_mlflow(summary, rows)
        _delete_progress(task_id)
        return summary
    finally:
        cap.restore()
        _s.judge_enabled = prev_judge


def _summarize(rows: List[Dict[str, Any]], use_judge: bool, n_fixtures: int, elapsed: float,
             sse_enabled: Optional[bool] = None) -> Dict[str, Any]:
    n = len(rows) or 1

    def avg(key):
        vals = [r[key] for r in rows if r.get(key) is not None]
        return round(sum(vals) / len(vals), 3) if vals else None

    lats = sorted(r["latency_s"] for r in rows)
    p95 = lats[min(len(lats) - 1, int(len(lats) * 0.95))] if lats else 0
    # TTFT is best-effort (older runs / streaming failures record None).
    ttfts = sorted(r["ttft_s"] for r in rows if r.get("ttft_s") is not None)
    avg_ttft = round(sum(ttfts) / len(ttfts), 2) if ttfts else None
    p95_ttft = (round(ttfts[min(len(ttfts) - 1, int(len(ttfts) * 0.95))], 2)
                if ttfts else None)
    return {
        "question_count": len(rows),
        "fixture_count": n_fixtures,
        "use_judge": use_judge,
        "sse_enabled": settings.chat_sse_enabled if sse_enabled is None else bool(sse_enabled),
        "pass_rate": round(sum(1 for r in rows if r["verdict"] == "PASS") / n, 3),
        "safe_rate": round(sum(1 for r in rows if r["verdict"] == "SAFE") / n, 3),
        "fail_rate": round(sum(1 for r in rows if r["verdict"] not in ("PASS", "SAFE")) / n, 3),
        # Fail split: fabrication = failed AND ungrounded (invented refs, typos,
        # claims with no evidence) — the number the CTO actually cares about.
        # Quality = failed BUT grounded (wrong count, indirect answer, language
        # slip) — strict-checker territory, not hallucination.
        "fail_fabrication_rate": round(sum(
            1 for r in rows
            if r["verdict"] not in ("PASS", "SAFE") and r.get("grounding") == 0) / n, 3),
        "fail_quality_rate": round(sum(
            1 for r in rows
            if r["verdict"] not in ("PASS", "SAFE") and r.get("grounding") == 1) / n, 3),
        "faithfulness_avg": avg("faithfulness"),
        "grounding_rate": avg("grounding"),
        "exact_rate": avg("exact"),
        "language_rate": avg("language_ok"),
        "relevancy_avg": avg("relevancy"),
        "avg_latency_s": round(sum(lats) / len(lats), 1) if lats else 0,
        "p95_latency_s": round(p95, 1),
        # TTFT vs full latency: a small gap means SSE streaming barely helps
        # (user already waits ~the whole reply); a wide gap means SSE hides
        # most of the wait behind the first tokens.
        "avg_ttft_s": avg_ttft,
        "p95_ttft_s": p95_ttft,
        "total_time_s": round(elapsed, 1),
        "actor_model": settings.chat_actor_model,
        "judge_model": settings.judge_model,
    }


def _minio_s3_endpoint() -> str:
    """S3 endpoint mlflow's boto client must hit (MinIO). Never empty in prod."""
    explicit = (getattr(settings, "mlflow_s3_endpoint_url", "") or "").strip()
    if explicit:
        return explicit
    return (getattr(settings, "minio_endpoint", "") or "").strip()


class _mlflow_s3_env:
    """Point boto (used internally by mlflow) at MinIO without touching Bedrock config.

    Bedrock auth uses BEDROCK_API_KEY (OpenAI-compatible header), never the
    AWS_* env vars, so this scoped override is concurrency-safe for LLM calls.
    """

    def __init__(self):
        self._old: Dict[str, Optional[str]] = {}

    def __enter__(self):
        self._old = {
            k: os.environ.get(k)
            for k in ("AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY",
                      "MLFLOW_S3_ENDPOINT_URL")
        }
        try:
            os.environ["AWS_ACCESS_KEY_ID"] = settings.minio_access_key
            os.environ["AWS_SECRET_ACCESS_KEY"] = settings.minio_secret_key
            os.environ["MLFLOW_S3_ENDPOINT_URL"] = _minio_s3_endpoint()
        except Exception as e:
            logger.debug(f"MLflow S3 env patch skipped: {e}")
        return self

    def __exit__(self, *exc):
        for k, v in self._old.items():
            try:
                if v is None:
                    os.environ.pop(k, None)
                else:
                    os.environ[k] = v
            except Exception:
                pass
        return False


def _ensure_experiment(client, name: str) -> None:
    """Create the experiment with an S3 artifact location on first use (MinIO)."""
    try:
        exp = client.get_experiment_by_name(name)
        if exp is not None:
            return
        artifact_location = f"s3://{settings.minio_bucket_mlflow}/"
        client.create_experiment(name, artifact_location=artifact_location)
        logger.info(f"Created MLflow experiment {name} → {artifact_location}")
    except Exception as e:
        logger.debug(f"MLflow ensure-experiment skipped: {e}")


def _log_mlflow(summary: Dict[str, Any], rows: List[Dict[str, Any]]) -> Optional[str]:
    try:
        import mlflow

        try:
            from mlflow.tracking import MlflowClient
        except Exception:
            # Unit-test fakes (or minimal installs) expose only the top-level
            # mlflow functions — experiment ensure is best-effort then.
            MlflowClient = None  # type: ignore[assignment]

        with _mlflow_s3_env():
            mlflow.set_tracking_uri(settings.mlflow_tracking_uri)
            if MlflowClient is not None:
                try:
                    _ensure_experiment(MlflowClient(), EXPERIMENT)
                except Exception as e:
                    logger.debug(f"MLflow ensure-experiment skipped: {e}")
            mlflow.set_experiment(EXPERIMENT)
            with mlflow.start_run(run_name="eval-judge-%s" % ("on" if summary.get("use_judge") else "off")) as run:
                mlflow.log_params({
                    "use_judge": summary.get("use_judge"),
                    "sse_enabled": summary.get("sse_enabled", False),
                    "question_count": summary.get("question_count"),
                    "actor_model": summary.get("actor_model"),
                    "judge_model": summary.get("judge_model"),
                })
                for k, v in summary.items():
                    if isinstance(v, (int, float)) and not isinstance(v, bool):
                        mlflow.log_metric(k, float(v) if v is not None else 0.0)
                run_id = run.info.run_id
                # Per-question table → MinIO directly (no local mlruns/ file).
                try:
                    from app.services.storage_service import storage_service

                    blob = json.dumps({"questions": rows}, ensure_ascii=False).encode("utf-8")
                    uri = storage_service.upload_bytes(
                        settings.minio_bucket_mlflow,
                        f"{run_id}/results.json", blob,
                        content_type="application/json",
                    )
                    try:
                        mlflow.set_tag("minio_results_uri", uri)
                    except Exception:
                        pass
                except Exception as e:
                    logger.warning(f"MinIO results upload failed, trying mlflow artifact: {e}")
                    try:
                        mlflow.log_dict({"questions": rows}, "results.json")
                    except Exception as e2:
                        logger.warning(f"MLflow artifact log failed: {e2}")
                return run_id
    except Exception as e:
        logger.warning(f"MLflow logging failed (results kept in return value): {e}")
        return None


def delete_eval_run(run_id: str) -> bool:
    """Soft-delete an MLflow run (hidden from lists/searches). Never raises."""
    try:
        import mlflow
        from mlflow.tracking import MlflowClient

        with _mlflow_s3_env():
            mlflow.set_tracking_uri(settings.mlflow_tracking_uri)
            MlflowClient().delete_run(run_id)
        # Best-effort: drop the MinIO results blob too (never raises).
        try:
            from app.services.storage_service import storage_service

            storage_service.delete(settings.minio_bucket_mlflow, f"{run_id}/results.json")
        except Exception:
            pass
        return True
    except Exception as e:
        logger.warning(f"MLflow delete failed: {e}")
        return False


def recent_runs(limit: int = 10) -> List[Dict[str, Any]]:
    """Last eval runs from MLflow (for the Eval Lab UI). Never raises."""
    try:
        import mlflow
        from mlflow.tracking import MlflowClient

        with _mlflow_s3_env():
            mlflow.set_tracking_uri(settings.mlflow_tracking_uri)
            client = MlflowClient()
            exp = client.get_experiment_by_name(EXPERIMENT)
            if exp is None:
                return []
            runs = client.search_runs(
                experiment_ids=[exp.experiment_id],
                order_by=["attributes.start_time DESC"],
                max_results=max(1, min(50, limit)),
            )
            out = []
            for r in runs:
                out.append({
                    "run_id": r.info.run_id,
                    "run_name": (r.data.tags.get("mlflow.runName") or ""),
                    "status": r.info.status,
                    "started": r.info.start_time,
                    "metrics": {k: round(float(v), 3) for k, v in r.data.metrics.items()},
                    "params": dict(r.data.params),
                })
            return out
    except Exception as e:
        logger.warning(f"MLflow recent-runs failed: {e}")
        return []
