"""Unit tests for the LLM-as-a-Judge grounding gate.

Covers: deterministic PR-reference gate, JSON verdict parsing, judge-error
fail-open, smalltalk skip, safe-fallback language, and the generate -> judge ->
retry -> fallback orchestration in ChatService._generate_with_judge.

Run from the repo root:
    python -m pytest tests/test_judge.py -v
"""
import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from app.services import judge_service as judge_module
from app.services.judge_service import JudgeService
from app.services import chat_service as chat_module


def run(coro):
    return asyncio.run(coro)


OBS_5 = ['[{"number": 5, "title": "Merge pull request #4", "state": "open"}]']

FABRICATED_REPLY = (
    "فيه 2 PRs متأخرة: #1 feat: add user authentication system "
    "(6 أيام) و #2 fix: resolve login redirect loop (4 أيام)."
)


def test_gate_rejects_fabricated_pr_table():
    # The live incident shape: #1/#2 cited, only #5 in tool output.
    svc = JudgeService()
    res = svc.deterministic_gate(FABRICATED_REPLY, OBS_5)
    assert res["verdict"] == "FAIL"
    assert "PR #1" in res["bad_claims"] and "PR #2" in res["bad_claims"]


def test_gate_passes_grounded_reply():
    svc = JudgeService()
    res = svc.deterministic_gate("الـ PR المفتوح هو #5.", OBS_5)
    assert res["verdict"] == "PASS"


def test_gate_passes_when_no_refs():
    svc = JudgeService()
    res = svc.deterministic_gate("أهلا بيك! اسألني عن الـ PRs.", OBS_5)
    assert res["verdict"] == "PASS"


def test_gate_rejects_refs_with_zero_observations():
    svc = JudgeService()
    res = svc.deterministic_gate("التفاصيل في PR #7.", [])
    assert res["verdict"] == "FAIL"
    assert "PR #7" in res["bad_claims"]


def _mock_client(content=None, boom=False):
    client = Mock()
    if boom:
        client.chat.completions.create = Mock(side_effect=RuntimeError("judge down"))
    else:
        client.chat.completions.create = Mock(
            return_value=SimpleNamespace(
                choices=[SimpleNamespace(message=SimpleNamespace(content=content))]
            )
        )
    return client


def _inject(svc, client):
    """Inject a mock into BOTH provider clients (Bedrock + Groq) so tests
    stay hermetic regardless of which model the fallback routes to."""
    svc._client = client
    svc._groq_client = client
    return svc


def test_llm_judge_parses_fail_verdict():
    svc = JudgeService()
    _inject(svc, _mock_client('{"verdict": "FAIL", "reason": "count unsupported", "bad_claims": ["5 PRs"]}'))
    res = svc.llm_judge("عندنا كام PR؟", "عندنا 5 PRs.", OBS_5)
    assert res["verdict"] == "FAIL"
    assert res["bad_claims"] == ["5 PRs"]


def test_llm_judge_error_fails_open():
    svc = JudgeService()
    _inject(svc, _mock_client(boom=True))
    res = svc.llm_judge("hi", "hello", [])
    assert res["verdict"] == "ERROR"


def _scripted_client(responses, calls):
    client = Mock()
    it = iter(responses)

    def create(*a, **k):
        calls.append(k.get("model"))
        item = next(it)
        if isinstance(item, Exception):
            raise item
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=item))])

    client.chat.completions.create = create
    return client


def _judge_settings(monkeypatch, retries=1):
    from app.core.config import settings

    monkeypatch.setattr(settings, "judge_model", "judge-m")
    monkeypatch.setattr(settings, "judge_fallback_model", "fallback-m")
    monkeypatch.setattr(settings, "judge_retries", retries)
    monkeypatch.setattr(settings, "judge_max_tokens", 50)


def test_llm_judge_retries_empty_then_passes(monkeypatch):
    svc = JudgeService()
    calls = []
    _inject(svc, _scripted_client(["", '{"verdict": "PASS", "reason": "ok"}'], calls))
    _judge_settings(monkeypatch)
    res = svc.llm_judge("q?", "There are 5 PRs.", ['[{"number": 5}]'])
    assert res["verdict"] == "PASS"
    assert calls == ["judge-m", "judge-m"]  # same model retried first


def test_llm_judge_falls_back_to_second_model(monkeypatch):
    svc = JudgeService()
    calls = []
    _inject(svc, _scripted_client(
        ["", "", '{"verdict": "FAIL", "reason": "bad"}'], calls))
    _judge_settings(monkeypatch)
    res = svc.llm_judge("q?", "Claim #9.", ['[{"number": 5}]'])
    assert res["verdict"] == "FAIL"
    assert calls == ["judge-m", "judge-m", "fallback-m"]


def test_llm_judge_all_miss_returns_error(monkeypatch):
    svc = JudgeService()
    calls = []
    _inject(svc, _scripted_client(["", "", "", ""], calls))
    _judge_settings(monkeypatch)
    res = svc.llm_judge("q?", "Claim.", [])
    assert res["verdict"] == "ERROR"
    assert len(calls) == 4  # (1+1) x 2 models


def test_llm_judge_routes_groq_fallback_to_groq_client(monkeypatch):
    """Slash-style fallback ("openai/gpt-oss-20b") must hit the Groq client,
    not Bedrock — so a Bedrock outage doesn't take the fallback with it."""
    from app.core.config import settings

    svc = JudgeService()
    bedrock_calls, groq_calls = [], []
    bedrock = _scripted_client([Exception("bedrock down"), Exception("bedrock down")], bedrock_calls)
    groq = _scripted_client(['{"verdict": "PASS", "reason": "ok via groq"}'], groq_calls)
    svc._client = bedrock
    svc._groq_client = groq
    monkeypatch.setattr(settings, "judge_model", "openai.gpt-oss-20b")
    monkeypatch.setattr(settings, "judge_fallback_model", "openai/gpt-oss-20b")
    monkeypatch.setattr(settings, "judge_retries", 1)
    monkeypatch.setattr(settings, "judge_max_tokens", 50)
    res = svc.llm_judge("q?", "There are 5 PRs.", ['[{"number": 5}]'])
    assert res["verdict"] == "PASS"
    assert bedrock_calls == ["openai.gpt-oss-20b", "openai.gpt-oss-20b"]
    assert groq_calls == ["openai/gpt-oss-20b"]


def test_review_skips_judge_for_smalltalk():
    svc = JudgeService()
    _inject(svc, _mock_client(boom=True))  # must never be touched
    res = run(svc.review("ازيك؟", "أهلا بيك! عامل إيه؟", []))
    assert res["verdict"] == "PASS"


def test_review_fails_open_on_judge_error(monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "judge_enabled", True)
    svc = JudgeService()
    _inject(svc, _mock_client(boom=True))
    res = run(svc.review("عندنا كام PR؟", "عندنا 5 PRs today.", OBS_5))
    assert res["verdict"] == "PASS"
    assert "open" in res["reason"]


def test_judge_prompt_scoped_to_repo_claims():
    prompt = judge_module.JUDGE_SYSTEM_PROMPT
    assert "ONLY repository-data claims need grounding" in prompt
    assert "General knowledge" in prompt and "need NO grounding" in prompt


def test_judge_prompt_tolerates_conversational_extras():
    prompt = judge_module.JUDGE_SYSTEM_PROMPT
    assert "Conversational extras need NO grounding" in prompt
    assert "follow-up questions" in prompt


def test_judge_prompt_zero_and_denial_rules():
    prompt = judge_module.JUDGE_SYSTEM_PROMPT
    assert "never fail a correct zero" in prompt
    assert "Denials (" in prompt and "WOULD contain" in prompt


def test_gate_defers_denials_to_judge():
    svc = JudgeService()
    # Correct denial, zero tools: NOT an instant FAIL anymore (judge decides).
    res = svc.deterministic_gate("لم يتم العثور على PR رقم 999 في قاعدة البيانات.", [])
    assert res["verdict"] == "PASS"
    assert "deferred" in res["reason"]
    # Fabrication still fails instantly, even with denial words elsewhere.
    res = svc.deterministic_gate("لا يوجد PR #999. لكن PR #9 تم دمجه أمس.", [])
    assert res["verdict"] == "FAIL"
    assert "PR #9" in res["bad_claims"]


def test_verify_authors_typo_and_exact():
    from app.services.judge_service import verify_authors

    roster = {"SeifMahmoud63"}
    bad = verify_authors("المؤلف هو SeifMahdoud63.", roster)
    assert bad["verdict"] == "FAIL"
    assert bad["bad_claims"] == ["SeifMahdoud63"]
    assert verify_authors("المؤلف هو SeifMahmoud63.", roster)["verdict"] == "PASS"
    # Unknown words and short tokens never fail (judge decides semantics).
    assert verify_authors("Merge the staging branch today.", roster)["verdict"] == "PASS"
    assert verify_authors("PR #5, ok?", roster)["verdict"] == "PASS"
    assert verify_authors("", set())["verdict"] == "PASS"


def test_candidate_usernames_no_hardcoded_lists():
    from app.services.judge_service import _candidate_usernames

    assert _candidate_usernames("PR #5 من SeifMahmoud63.") == ["SeifMahmoud63"]
    assert _candidate_usernames("ازيك عامل ايه؟ 123") == []
    assert _candidate_usernames("") == []


def test_general_answer_with_numbers_not_preblocked_by_gate():
    # No PR refs -> gate passes; semantic call is the judge's job (mocked PASS).
    svc = JudgeService()
    _inject(svc, _mock_client('{"verdict": "PASS", "reason": "general knowledge, no repo claims"}'))
    res = run(
        svc.review(
            "What are the DORA metrics?",
            "The 4 DORA metrics date back to research published in 2013.",
            [],
        )
    )
    assert res["verdict"] == "PASS"


def test_has_number_claim():
    from app.services.judge_service import _has_number_claim

    assert _has_number_claim("PR واحد اتفتح امبارح") is True  # the live hole
    assert _has_number_claim("one PR was opened") is True
    assert _has_number_claim("عندنا 5 PRs") is True
    assert _has_number_claim("شوف PR #7") is True
    assert _has_number_claim("أهلا بيك! عامل إيه؟") is False
    assert _has_number_claim("someone asked about reviews") is False  # no substring trap
    assert _has_number_claim("") is False


def test_spelled_out_number_forces_judge_review(monkeypatch):
    # "wahed" with zero observations must reach the judge (mocked PASS here) —
    # previously it skipped review entirely and a guessed reply went through.
    from app.core.config import settings

    monkeypatch.setattr(settings, "judge_enabled", True)
    svc = JudgeService()
    client = _mock_client('{"verdict": "PASS", "reason": "ok"}')
    _inject(svc, client)
    res = run(svc.review("كام PR اتفتح امبارح؟", "PR واحد اتفتح امبارح.", []))
    assert res["verdict"] == "PASS"
    assert client.chat.completions.create.call_count == 1


def test_retry_nudge_orders_conditional_tool_use():
    svc = JudgeService()
    n = svc.retry_nudge(
        "عندنا كام PR؟", "bad reply", [],
        {"verdict": "FAIL", "reason": "r", "bad_claims": ["PR #9"]})
    # Data questions: mandatory fresh tool call...
    assert "MUST call execute_readonly_query" in n
    assert "Never answer repo questions from memory" in n
    # ...but no-tool questions must NOT be forced into pointless queries.
    assert "smalltalk or general knowledge" in n
    assert "do NOT include any repo-specific facts" in n
    assert "PR #9" in n  # bad claims carried for correction


def test_safe_fallback_language():
    svc = JudgeService()
    assert "PRs" in svc.safe_fallback("عندنا كام PR؟")  # Arabic in, Arabic out
    assert "verify" in svc.safe_fallback("How many PRs?")  # English in, English out


def _graph_state(reply, with_tool=True):
    msgs = [HumanMessage(content="q")]
    if with_tool:
        msgs.append(
            ToolMessage(content='[{"number": 5}]', tool_call_id="t1", name="execute_readonly_query")
        )
    msgs.append(AIMessage(content=reply))
    return {"messages": msgs}


def _service_with_graph(responses):
    service = chat_module.ChatService.__new__(chat_module.ChatService)
    service.graph = SimpleNamespace(ainvoke=AsyncMock(side_effect=responses))
    return service


def test_generate_retries_once_then_accepts(monkeypatch):
    service = _service_with_graph([_graph_state("bad #9"), _graph_state("good #5")])
    fake_judge = SimpleNamespace(
        review=AsyncMock(
            side_effect=[
                {"verdict": "FAIL", "reason": "bad", "bad_claims": ["PR #9"]},
                {"verdict": "PASS", "reason": "ok"},
            ]
        ),
        retry_nudge=Mock(return_value="nudge"),
        safe_fallback=Mock(return_value="FALLBACK"),
        classify_query_intent_jev=AsyncMock(return_value="data"),
    )
    monkeypatch.setattr(judge_module, "judge_service", fake_judge)
    out = run(service._generate_with_judge([HumanMessage(content="q")], "q"))
    assert out["reply"] == "good #5"
    assert out["verdict"] == "PASS_AFTER_RETRY"
    assert service.graph.ainvoke.await_count == 2


def test_generate_falls_back_after_second_fail(monkeypatch):
    service = _service_with_graph([_graph_state("bad #9"), _graph_state("bad #8")])
    fake_judge = SimpleNamespace(
        review=AsyncMock(
            return_value={"verdict": "FAIL", "reason": "bad", "bad_claims": []}
        ),
        retry_nudge=Mock(return_value="nudge"),
        safe_fallback=Mock(return_value="FALLBACK"),
        classify_query_intent_jev=AsyncMock(return_value="data"),
    )
    monkeypatch.setattr(judge_module, "judge_service", fake_judge)
    out = run(service._generate_with_judge([HumanMessage(content="q")], "q"))
    assert out["reply"] == "FALLBACK"
    assert out["verdict"] == "FALLBACK"


OBS_EMAIL_1 = ['[{"sender": "Seif Mahmoud <seifmahmoud7199@gmail.com>",'
               ' "subject": "Meeting", "sent_at": "2026-10-11T16:48:03"}]']

FABRICATED_EMAIL_REPLY = (
    "هنا ايميلات امبارح (11 أكتوبر) — 2: "
    "Invitation to collaborate :<noreply@github.com> "
    "Team update :<noreply@slack.com>"
)


def test_gate_rejects_invented_email_senders():
    # The live incident: 1 real row, 2 invented senders.
    svc = JudgeService()
    res = svc.deterministic_gate(FABRICATED_EMAIL_REPLY, OBS_EMAIL_1)
    assert res["verdict"] == "FAIL"
    assert "noreply@github.com" in res["bad_claims"]
    assert "noreply@slack.com" in res["bad_claims"]


def test_gate_passes_grounded_email_sender():
    svc = JudgeService()
    res = svc.deterministic_gate(
        "From Seif Mahmoud <seifmahmoud7199@gmail.com>: Meeting.",
        OBS_EMAIL_1)
    assert res["verdict"] == "PASS"


def test_gate_exempts_user_restated_address():
    # Repeating the user's own address is not a fabrication claim.
    svc = JudgeService()
    res = svc.deterministic_gate(
        "نعم، noreply@github.com عنوان معروف.",
        [], user_content="هو noreply@github.com ده بتاعنا؟")
    assert res["verdict"] == "PASS"


def test_gate_rejects_address_claim_with_no_tools():
    svc = JudgeService()
    res = svc.deterministic_gate(
        "وصلك إيميل من boss@example.com.", [])
    assert res["verdict"] == "FAIL"
    assert "boss@example.com" in res["bad_claims"]


def test_review_enforces_gate_when_judge_disabled(monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "judge_enabled", False)
    svc = JudgeService()
    client = _mock_client(boom=True)  # LLM must never be touched
    _inject(svc, client)
    res = run(svc.review("وامبارح جالي ايميل؟", FABRICATED_EMAIL_REPLY, OBS_EMAIL_1))
    assert res["verdict"] == "FAIL"
    assert client.chat.completions.create.call_count == 0


def test_review_passes_gate_when_judge_disabled(monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "judge_enabled", False)
    svc = JudgeService()
    client = _mock_client(boom=True)
    _inject(svc, client)
    res = run(svc.review(
        "جالي ايميل انهارده؟",
        "From Seif Mahmoud <seifmahmoud7199@gmail.com>: Meeting.",
        OBS_EMAIL_1))
    assert res["verdict"] == "PASS"
    assert client.chat.completions.create.call_count == 0


OBS_PR5 = ['[{"number": 5, "title": "Merge pull request #4", '
           '"author": "SeifMahmoud63", "created_at": "2026-10-11T13:33:46"}]']


def test_gate_rejects_misdated_latest_pr():
    # The live incident: row says 2026-10-11, reply claims 2026-10-12.
    svc = JudgeService()
    res = svc.deterministic_gate(
        "آخر PR كانت بتاريخ 2026-10-12 (النهاردة) ومن SeifMahmoud63.",
        OBS_PR5)
    assert res["verdict"] == "FAIL"
    assert "2026-10-12" in res["bad_claims"]


def test_gate_passes_grounded_iso_date():
    svc = JudgeService()
    res = svc.deterministic_gate("آخر PR #5 بتاريخ 2026-10-11.", OBS_PR5)
    assert res["verdict"] == "PASS"


def test_gate_skips_human_form_dates():
    # "11 October" is unverifiable without an LLM — never fail it here.
    svc = JudgeService()
    res = svc.deterministic_gate("آخر PR كان يوم 11 أكتوبر.", OBS_PR5)
    assert res["verdict"] == "PASS"


def test_gate_rejects_iso_date_with_no_tools():
    svc = JudgeService()
    res = svc.deterministic_gate("آخر PR بتاريخ 2026-01-01.", [])
    assert res["verdict"] == "FAIL"
    assert "2026-01-01" in res["bad_claims"]


def test_gate_exempts_user_restated_date():
    svc = JudgeService()
    res = svc.deterministic_gate(
        "يوم 2026-10-10 ماله؟", [],
        user_content="احكيلي عن يوم 2026-10-10")
    assert res["verdict"] == "PASS"


def test_gate_defers_date_denial_with_observations():
    # True negatives ("nothing on 2026-10-12" after a real query) must pass.
    svc = JudgeService()
    res = svc.deterministic_gate("مفيش PRs اتفتحت يوم 2026-10-12.", OBS_PR5)
    assert res["verdict"] == "PASS"


def test_review_catches_misdated_pr_without_judge(monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "judge_enabled", False)
    svc = JudgeService()
    client = _mock_client(boom=True)  # LLM must never be touched
    _inject(svc, client)
    res = run(svc.review(
        "اخر PR امتي؟",
        "آخر PR بتاريخ 2026-10-12 من SeifMahmoud63.", OBS_PR5))
    assert res["verdict"] == "FAIL"
    assert client.chat.completions.create.call_count == 0


def test_gate_grounds_ref_from_sql_call_args():
    # `SELECT state ... WHERE number = 5` proves PR #5 was fetched even
    # though the output row carries no "5" literal (false-premise fix).
    svc = JudgeService()
    calls = ['{"sql_query": "SELECT state FROM pull_requests WHERE number = 5"}']
    res = svc.deterministic_gate(
        "لا، الـ PR رقم 5 مفتوح.", ['[{"state": "open"}]'], tool_calls=calls)
    assert res["verdict"] == "PASS"
    # Same reply without the call evidence still fails.
    res2 = svc.deterministic_gate("لا، الـ PR رقم 5 مفتوح.", ['[{"state": "open"}]'])
    assert res2["verdict"] == "FAIL"


def test_gate_exempts_system_today_without_tools(monkeypatch):
    from datetime import datetime
    from zoneinfo import ZoneInfo

    from app.services import judge_service as js_mod

    today = datetime.now(ZoneInfo("Africa/Cairo")).date().isoformat()
    assert today in js_mod._system_dates()
    svc = JudgeService()
    assert svc.deterministic_gate(f"النهاردة {today}.", [])["verdict"] == "PASS"
    # Any other ISO date still needs tool evidence.
    assert svc.deterministic_gate("آخر PR بتاريخ 2026-01-01.", [])["verdict"] == "FAIL"
