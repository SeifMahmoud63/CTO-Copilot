"""Torture battery: drive the LIVE chat agent (judge OFF, prod-like) over
varied user-style questions, capture every tool call + SQL, and score each
reply against fresh DB ground truth. No judge, no mocks — real ReAct loop.

Run INSIDE the app container:
  docker exec -e PYTHONPATH=/app cto-copilot-app python /app/scripts/torture_chat.py [only <substr>]

Results: /tmp/torture_results.json + console table.
"""
import asyncio
import io
import json
import re
import sys
import time
from datetime import datetime, timezone

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

AR_RE = re.compile(r"[\u0600-\u06FF]")
DIG_RE = re.compile(r"\d+")
WORD_NUM = {
    "صفر": 0, "واحد": 1, "واحدة": 1, "واحده": 1, "وحدة": 1, "وحده": 1,
    "وحد": 1, "اتنين": 2, "اثنين": 2, "تلاتة": 3, "تلاته": 3, "ثلاثة": 3,
    "اربعة": 4, "أربعة": 4, "خمسة": 5, "ستة": 6, "سبعة": 7, "ثمانية": 8,
    "تمانية": 8, "تسعة": 9, "عشرة": 10,
    "zero": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
    "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
}
DENY = ["مفيش", "مافيش", "ما فيش", "لا يوجد", "لا توجد", "غير موجود",
        "not found", "no ", "none", "couldn't find", "معندناش", "مالناش",
        "لم يتم العثور", "لا وجود", "0"]


def nums(reply):
    out = {int(x) for x in DIG_RE.findall(reply or "")}
    toks = set(re.findall(r"\w+", (reply or "").lower()))
    return out | {WORD_NUM[t] for t in toks if t in WORD_NUM}


def denies(reply):
    low = (reply or "").lower()
    return any(m in low for m in DENY)


async def ground_truth():
    from sqlalchemy import text as _t
    from app.db.session import AsyncSessionLocal as _S
    from zoneinfo import ZoneInfo

    async def q(sql):
        async with _S() as s:
            return [dict(r) for r in (await s.execute(_t(sql))).mappings().all()]

    prs = await q("SELECT number, title, author, state, created_at, updated_at,"
                  " is_overdue, overdue_days FROM pull_requests")
    ems = await q("SELECT id, sender, subject, sent_at, urgency_score, urgency_tier,"
                  " is_hidden FROM emails")
    eng = await q("SELECT author, pr_count, avg_score, tier FROM engineers")
    rep = await q("SELECT report_date, title FROM daily_reports ORDER BY report_date DESC")
    now_c = datetime.now(ZoneInfo("Africa/Cairo"))
    today_c, yest_c = now_c.date().isoformat(), (now_c.date()).isoformat()

    def day(v):
        return str(v)[:10]

    from datetime import timedelta
    yest = str(now_c.date() - timedelta(days=1))

    def cairo_day(v):
        if v is None:
            return None
        dt = v if isinstance(v, datetime) else datetime.fromisoformat(str(v))
        return dt.replace(tzinfo=timezone.utc).astimezone(ZoneInfo("Africa/Cairo")).date().isoformat()

    ctx = {
        "prs": prs, "total": len(prs),
        "open": [p for p in prs if str(p["state"]).lower() == "open"],
        "merged": [p for p in prs if str(p["state"]).lower() == "merged"],
        "closed": [p for p in prs if str(p["state"]).lower() == "closed"],
        "today_prs": [p for p in prs if cairo_day(p["created_at"]) == today_c],
        "yest_prs": [p for p in prs if cairo_day(p["created_at"]) == yest],
        "od": [int(p["number"]) for p in prs if p["is_overdue"]],
        "ems_vis": [e for e in ems if not e["is_hidden"]],
        "today_ems": [e for e in ems if not e["is_hidden"] and cairo_day(e["sent_at"]) == today_c],
        "yest_ems": [e for e in ems if not e["is_hidden"] and cairo_day(e["sent_at"]) == yest],
        "eng": eng, "rep": rep, "today_c": today_c, "yest": yest,
    }
    authors = {}
    for p in prs:
        authors[p["author"]] = authors.get(p["author"], 0) + 1
    ctx["top_author"] = max(authors, key=authors.get) if authors else ""
    ctx["latest"] = max(prs, key=lambda p: str(p["created_at"])) if prs else None
    ctx["oldest"] = min(prs, key=lambda p: str(p["created_at"])) if prs else None
    return ctx


def build_cases(ctx):
    L, M = len(ctx["open"]), len(ctx["merged"])
    T, Y = len(ctx["today_prs"]), len(ctx["yest_prs"])
    TE, YE = len(ctx["today_ems"]), len(ctx["yest_ems"])
    top = ctx["top_author"]
    od = ctx["od"]
    latest = ctx["latest"] or {}
    oldest = ctx["oldest"] or {}

    def cnt(n):
        def go(reply, obs):
            if n in nums(reply):
                return True, "count present"
            if n == 0 and denies(reply):
                return True, "zero denied"
            return False, f"expected {n}, got nums={sorted(nums(reply))}"
        return go

    def has(*subs):
        def go(reply, obs):
            missing = [s for s in subs if s not in (reply or "")]
            return (not missing, "ok" if not missing else f"missing {missing}")
        return go

    cases = [
        {"id": "pr-total", "q": "عندنا كام PR؟", "lang": "ar", "check": cnt(ctx["total"])},
        {"id": "pr-open-en", "q": "How many open PRs?", "lang": "en", "check": cnt(L)},
        {"id": "pr-merged", "q": "كام PR merged؟", "lang": "ar", "check": cnt(M)},
        {"id": "pr-today", "q": "عندنا كام PR انهارده؟", "lang": "ar", "check": cnt(T)},
        {"id": "pr-yesterday", "q": "كام PR اتفتح امبارح؟", "lang": "ar", "check": cnt(Y)},
        {"id": "pr-latest", "q": "آخر PR حصلت امتي ومن مين؟", "lang": "ar",
         "check": lambda r, o: (
             (str(latest.get("created_at"))[:10] in r or
              (int(str(latest.get("created_at"))[8:10]) in nums(r))) and
             (latest.get("author", "") in r),
             "latest date+author")},
        {"id": "pr-oldest", "q": "أقدم PR عندنا رقم كام؟", "lang": "ar",
         "check": lambda r, o: (str(oldest.get("number", "?")) in r, "oldest number")},
        {"id": "pr-detail5", "q": "هات تفاصيل PR #5", "lang": "ar",
         "check": has("SeifMahmoud63", "5")},
        {"id": "trap-999", "q": "هات تفاصيل PR #999", "lang": "ar",
         "check": lambda r, o: (denies(r), "must deny")},
        {"id": "false-premise", "q": "مش الـ PR رقم 5 مقفول؟", "lang": "ar",
         "check": lambda r, o: ((("مفتوح" in r) or ("open" in r.lower())), "must correct")},
        {"id": "overdue", "q": "فيه اي PRs متعلقه؟", "lang": "ar",
         "check": lambda r, o: (
             (all(str(n) in r for n in od) or (len(od) in nums(r)))
             if od else (denies(r) or 0 in nums(r)), "overdue")},
        {"id": "top-ar", "q": "مين أكتر حد عمل PRs؟", "lang": "ar",
         "check": has(top)},
        {"id": "top-en", "q": "Who is the top contributor?", "lang": "en",
         "check": lambda r, o: ((top in r) and not AR_RE.search(r or ""), "en+exact")},
        {"id": "author-count", "q": "الـ PRs اللي عملها SeifMahmoud63 كام؟", "lang": "ar",
         "check": cnt(5) if top == "SeifMahmoud63" else (lambda r, o: (True, "skip"))},
        {"id": "em-today", "q": "جالي ايميل انهارده؟", "lang": "ar", "check": cnt(TE)},
        {"id": "em-yesterday", "q": "جالي ايميل امبارح؟", "lang": "ar", "check": cnt(YE)},
        {"id": "em-detail", "q": "عاوز تفاصيل إيميل الـ Meeting بتاع امبارح", "lang": "ar",
         "check": has("Seif", "Meeting")},
        {"id": "em-sender", "q": "مين بعتلي إيميل الـ Security alert؟", "lang": "ar",
         "check": lambda r, o: (("Google" in r or "google" in r.lower()), "sender")},
        {"id": "em-urgent", "q": "عندنا كام إيميل urgent؟", "lang": "ar",
         "check": lambda r, o: (True, "record-only")},
        {"id": "rep-count", "q": "احنا عندنا كام report؟", "lang": "ar",
         "check": cnt(len(ctx["rep"]))},
        {"id": "rep-today", "q": "لخص ريبورت النهاردة", "lang": "ar",
         "check": lambda r, o: ((len(r or "") > 80), "report body")},
        {"id": "time-now", "q": "الساعة كام؟", "lang": "ar",
         "check": lambda r, o: ((re.search(r"\d{1,2}:\d{2}", r or "") is not None), "time")},
        {"id": "date-today", "q": "وانهارده كام؟", "lang": "ar",
         "check": lambda r, o: ((ctx["today_c"] in r or int(ctx["today_c"][8:10]) in nums(r)), "today")},
        {"id": "date-yest", "q": "امبارح كان تاريخ كام؟", "lang": "ar",
         "check": lambda r, o: ((ctx["yest"] in r or int(ctx["yest"][8:10]) in nums(r)), "yest")},
        {"id": "dora", "q": "What are the 4 DORA metrics?", "lang": "en",
         "check": has("Deployment Frequency")},
        {"id": "future", "q": "كام PR هيتفتح بكرة؟", "lang": "ar", "check": cnt(0)},
        {"id": "y2020", "q": "كام PR اتفتح سنة 2020؟", "lang": "ar", "check": cnt(0)},
    ]
    if ctx["eng"]:
        e0 = ctx["eng"][0]
        cases.append({"id": "eng-tier", "q": f"التير بتاع {e0['author']} ايه؟", "lang": "ar",
                      "check": has(str(e0["tier"]))})
    cases.append({"id": "chain", "chain": [
        "هات تفاصيل PR #5",
        "من مين؟",
        "و عنوانه ايه؟",
    ], "lang": "ar", "check": None})
    return cases


async def main(only=""):
    from app.core.config import settings
    settings.judge_enabled = False
    from app.services.chat_service import chat_service

    ctx = await ground_truth()
    print(f"GT: prs={ctx['total']} open={len(ctx['open'])} merged={len(ctx['merged'])} "
          f"todayPR={len(ctx['today_prs'])} yestPR={len(ctx['yest_prs'])} od={ctx['od']} "
          f"todayEM={len(ctx['today_ems'])} yestEM={len(ctx['yest_ems'])} "
          f"reps={len(ctx['rep'])} eng={len(ctx['eng'])} top={ctx['top_author']} "
          f"latest=#{ctx['latest']['number']}@{str(ctx['latest']['created_at'])[:10]} "
          f"judge={settings.judge_enabled} model={settings.bedrock_model}", flush=True)

    logged = []

    def wrap(name):
        real = chat_service.tools_by_name[name]

        class Cap:
            def __init__(self):
                self.name = getattr(real, "name", name)

            async def ainvoke(self, args):
                out = await real.ainvoke(args)
                logged.append({"tool": name, "args": dict(args), "out": str(out)[:1500]})
                return out

        chat_service.tools_by_name[name] = Cap()
        return real

    reals = {n: wrap(n) for n in list(chat_service.tools_by_name)}
    rows = []
    try:
        for c in build_cases(ctx):
            if only and only not in c["id"]:
                continue
            t0 = time.perf_counter()
            try:
                sess = await chat_service.create_session(title="torture-" + c["id"])
                sid = sess["id"]
                try:
                    if "chain" in c:
                        outs = []
                        for q in c["chain"]:
                            del logged[:]
                            r = await chat_service.send_message(sid, q)
                            outs.append({"q": q, "reply": r.get("reply", ""),
                                         "tools": [l["tool"] for l in logged],
                                         "sqls": [l["args"].get("sql_query", l["args"])
                                                  for l in logged]})
                        ok = ("SeifMahmoud63" in outs[1]["reply"] and
                              (ctx["latest"] or {}).get("title", "")[:20] in outs[2]["reply"])
                        rows.append({"id": c["id"], "ok": ok, "detail": "chain",
                                     "turns": outs, "lat": round(time.perf_counter() - t0, 1)})
                    else:
                        del logged[:]
                        r = await chat_service.send_message(sid, c["q"])
                        reply = r.get("reply", "")
                        obs = [l["out"] for l in logged]
                        try:
                            ok, detail = c["check"](reply, obs)
                        except Exception as e:
                            ok, detail = False, f"check crash: {e}"
                        rows.append({"id": c["id"], "q": c["q"], "ok": bool(ok),
                                     "detail": detail, "reply": reply[:600],
                                     "rewritten": r.get("rewritten_query"),
                                     "verdict": r.get("verdict"),
                                     "tools": [l["tool"] for l in logged],
                                     "sqls": [l["args"].get("sql_query", l["args"])
                                              for l in logged],
                                     "lat": round(time.perf_counter() - t0, 1)})
                finally:
                    try:
                        await chat_service.delete_session(sid)
                    except Exception:
                        pass
            except Exception as e:
                rows.append({"id": c["id"], "ok": False, "detail": f"EXC: {e}"})
            done = sum(1 for r in rows if r.get("ok"))
            print(f"[{c['id']}] {'PASS' if rows[-1].get('ok') else 'FAIL'} "
                  f"({rows[-1].get('detail')}) [{rows[-1].get('lat', '?')}s] "
                  f"score={done}/{len(rows)}", flush=True)
    finally:
        for n, real in reals.items():
            chat_service.tools_by_name[n] = real

    ok = sum(1 for r in rows if r.get("ok"))
    print(f"\nTOTAL: {ok}/{len(rows)}")
    with open("/tmp/torture_results.json", "w", encoding="utf-8") as f:
        json.dump({"ctx_summary": {k: (v if not isinstance(v, list) else len(v))
                                   for k, v in ctx.items() if k != "prs"},
                   "rows": rows}, f, ensure_ascii=False, default=str)
    print("saved /tmp/torture_results.json")


if __name__ == "__main__":
    asyncio.run(main(sys.argv[2] if len(sys.argv) > 2 and sys.argv[1] == "only" else ""))
