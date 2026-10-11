"""Unit tests for chat query-rewrite (follow-ups -> standalone questions).

Run from the repo root:
    python -m pytest tests/test_chat_query_rewrite.py -v
"""
import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

from langchain_core.messages import AIMessage, HumanMessage

from app.services import chat_service as chat_module


def make_service(rewrite_reply: str | None = None, boom: bool = False):
    service = chat_module.ChatService.__new__(chat_module.ChatService)
    if boom:
        service.llm = AsyncMock()
        service.llm.ainvoke = AsyncMock(side_effect=RuntimeError("llm down"))
    else:
        service.llm = AsyncMock()
        service.llm.ainvoke = AsyncMock(return_value=AIMessage(content=rewrite_reply))
    return service


def run(coro):
    return asyncio.run(coro)


HISTORY = [
    HumanMessage(content="مين عمل اكتر عدد PRs؟"),
    AIMessage(content="SeifMahmoud63 عمل 4 PRs."),
]


def test_follow_up_is_rewritten():
    service = make_service("مين عمل تاني اكتر عدد PRs؟")
    out = run(service._rewrite_query(HISTORY, "ومين التاني؟"))
    assert out == "مين عمل تاني اكتر عدد PRs؟"
    sent = service.llm.ainvoke.call_args[0][0]
    transcript = sent[1].content
    assert "مين عمل اكتر عدد PRs؟" in transcript
    assert "ومين التاني؟" in transcript


def test_standalone_question_comes_back_unchanged():
    service = make_service("Who has the most PRs?")
    out = run(service._rewrite_query(HISTORY, "Who has the most PRs?"))
    assert out == "Who has the most PRs?"


def test_empty_history_skips_llm():
    service = make_service("should never be used")
    out = run(service._rewrite_query([], "مين عمل اكتر عدد PRs؟"))
    assert out == "مين عمل اكتر عدد PRs؟"
    service.llm.ainvoke.assert_not_called()


def test_llm_failure_falls_back_to_original():
    service = make_service(boom=True)
    out = run(service._rewrite_query(HISTORY, "ومين التاني؟"))
    assert out == "ومين التاني؟"


def test_rewrite_window_from_env(monkeypatch):
    from app.core.config import Settings

    monkeypatch.setenv("CHAT_QUERY_REWRITE_WINDOW_SIZE", "7")
    assert Settings().chat_query_rewrite_window_size == 7
    # Code-level default (whatever .env currently sets, the field default is 2).
    assert Settings.model_fields["chat_query_rewrite_window_size"].default == 2


def test_rewrite_context_keeps_tail_with_answer():
    from langchain_core.messages import AIMessage, HumanMessage

    history = [
        HumanMessage(content="q1"),
        AIMessage(content="a1"),
        HumanMessage(content="q2"),
        AIMessage(content="a2"),
    ]
    tail = chat_module._rewrite_context(history, 2)
    assert [m.content for m in tail] == ["q2", "a2"]


def test_rewrite_context_prepends_latest_answer():
    from langchain_core.messages import AIMessage, HumanMessage

    history = [
        HumanMessage(content="q1"),
        AIMessage(content="THE LIST: #10, #7, #3"),
        HumanMessage(content="q2"),
        HumanMessage(content="q3"),
    ]
    tail = chat_module._rewrite_context(history, 2)
    assert [m.content for m in tail] == ["THE LIST: #10, #7, #3", "q2", "q3"]


def test_rewrite_context_edge_cases():
    from langchain_core.messages import HumanMessage

    assert chat_module._rewrite_context([], 2) == []
    assert chat_module._rewrite_context([HumanMessage(content="q")], 0) == []
    # No assistant message anywhere -> tail unchanged, no invention.
    history = [HumanMessage(content="q1"), HumanMessage(content="q2")]
    assert [m.content for m in chat_module._rewrite_context(history, 2)] == ["q1", "q2"]


def test_rewrite_prompt_has_ordinal_resolution_rule():
    prompt = chat_module.QUERY_REWRITE_PROMPT
    assert "Ordinal" in prompt or "ordinal" in prompt
    assert "التاني" in prompt
    assert "NEVER output a" in prompt and "bare ordinal" in prompt


def test_ordinal_resolves_to_concrete_item_arabic():
    last_answer = "الـ PRs:\n- PR #10 عنوان أول\n- PR #7 عنوان تاني\n- PR #3 عنوان تالت"
    out = chat_module._resolve_ordinal_reference("اه التانيه", last_answer)
    assert out is not None
    assert "#7" in out and "عنوان تاني" in out
    assert "التانيه" not in out  # no bare ordinal left
    assert "هات كل التفاصيل" in out  # user's own language (Arabic)


def test_ordinal_resolves_english():
    last_answer = "- PR #10 first\n- PR #7 second"
    out = chat_module._resolve_ordinal_reference("the second one please", last_answer)
    assert out is not None and "#7" in out and "Give full details" in out


def test_ordinal_returns_none_when_not_applicable():
    last_answer = "- PR #10 first\n- PR #7 second"
    assert chat_module._resolve_ordinal_reference("ومين التاني عمل ايه كمان؟", last_answer) is None  # extra content
    assert chat_module._resolve_ordinal_reference("اه الرابعه", last_answer) is None  # out of range
    assert chat_module._resolve_ordinal_reference("اه التانيه", "") is None  # no answer
    assert chat_module._resolve_ordinal_reference("ازيك عامل ايه", last_answer) is None  # no ordinal


def test_ordinal_prefers_explicit_pr_number_over_position():
    # The exact user complaint: list order [#1, #3, #2], "the second" = PR #2.
    last_answer = (
        "1. الريبوست #1: make the PR requests\n"
        "2. الريبوست #3: Merge pull request\n"
        "3. الريبوست #2: change in summary prompt"
    )
    out = chat_module._resolve_ordinal_reference("ابعتلي التاني بس بالتفصيل مش كلو", last_answer)
    assert out is not None
    assert "PR رقم 2" in out
    assert "change in summary prompt" in out
    assert "هو فقط" in out  # single-item scope, no dump


def test_ordinal_positional_fallback_without_numbers():
    last_answer = "- أول عنصر: ألف\n- تاني عنصر: باء"
    out = chat_module._resolve_ordinal_reference("اه التاني", last_answer)
    assert out is not None and "باء" in out


def test_response_discipline_in_prompts():
    assert "never dump" in chat_module.SYSTEM_PROMPT.lower() or "never paste details" in chat_module.SYSTEM_PROMPT
    assert "max ~10" in chat_module.SYSTEM_PROMPT or "max 10" in chat_module.SYSTEM_PROMPT
    assert "raw ISO" in chat_module.SYSTEM_PROMPT
    import app.services.voice_service as voice_module

    service = voice_module.VoiceAgentService.__new__(voice_module.VoiceAgentService)
    service.agent_model = "nova-3"
    service.voice_model = "aura-asteria-en"
    prompt = voice_module.VoiceAgentService.build_settings_payload(service)["agent"]["think"]["prompt"]
    assert "never recite long lists" in prompt


def test_conciseness_rules_in_prompts():
    prompt = chat_module.SYSTEM_PROMPT
    assert "ONLY what was asked" in prompt
    assert "No fluff openers" in prompt
    assert "no meta-talk" in prompt
    assert "Tables ONLY when comparing" in prompt


def test_rewrite_query_prefers_deterministic_ordinal_without_llm():
    from unittest.mock import AsyncMock

    from langchain_core.messages import AIMessage, HumanMessage

    service = chat_module.ChatService.__new__(chat_module.ChatService)
    service.llm = AsyncMock()
    service.llm.ainvoke = AsyncMock(side_effect=AssertionError("LLM must not be called"))
    history = [
        HumanMessage(content="لخصلي الريبورت"),
        AIMessage(content="القائمة:\n- PR #10 أول\n- PR #7 تاني"),
    ]
    out = asyncio.run(service._rewrite_query(history, "اه التانيه"))
    assert "#7" in out


class FakeScalars:
    def __init__(self, rows):
        self._rows = rows

    def all(self):
        return self._rows


class FakeResult:
    def __init__(self, scalar=None, rows=None):
        self._scalar = scalar
        self._rows = rows or []

    def scalar_one_or_none(self):
        return self._scalar

    def scalars(self):
        return FakeScalars(self._rows)


class FakeSession:
    """Minimal async stand-in for AsyncSession covering send_message's usage."""

    def __init__(self, history_rows):
        self.history_rows = history_rows
        self.added = []
        self.created_session = None
        self._calls = 0

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False

    def add(self, obj):
        self.added.append(obj)
        if type(obj).__name__ == "ChatSession" and self.created_session is None:
            self.created_session = obj

    async def commit(self):
        return None

    async def refresh(self, obj):
        return None

    async def execute(self, stmt):
        self._calls += 1
        if self._calls == 1:
            return FakeResult(scalar=None)  # session lookup -> auto-create path
        if self._calls == 2:
            return FakeResult(rows=self.history_rows)
        return FakeResult(scalar=self.created_session)


def test_send_message_uses_rewrite_window_and_keeps_original_in_db(monkeypatch):
    # DB returns newest-first (ORDER BY id DESC); send_message reverses it.
    history_rows = [
        SimpleNamespace(role="assistant", content="SeifMahmoud63 عمل 4 PRs.", id=4),
        SimpleNamespace(role="user", content="مين عمل اكتر عدد PRs؟", id=3),
        SimpleNamespace(role="assistant", content="رد قديم", id=2),
        SimpleNamespace(role="user", content="اول سؤال قديم", id=1),
    ]
    fake_session = FakeSession(history_rows)
    monkeypatch.setattr(chat_module, "AsyncSessionLocal", lambda: fake_session)
    monkeypatch.setattr(
        chat_module.settings, "chat_query_rewrite_window_size", 2
    )

    service = make_service("مين عمل تاني اكتر عدد PRs؟")
    captured = {}

    async def fake_graph(messages):
        captured["messages"] = messages["messages"]
        return {"messages": [AIMessage(content="final reply")]}

    service.graph = SimpleNamespace(ainvoke=fake_graph)

    out = run(service.send_message("sess-1", "ومين التاني؟"))

    # Rewrite saw ONLY the last 2 history messages (window=2), not the old ones.
    sent = service.llm.ainvoke.call_args[0][0]
    transcript = sent[1].content
    assert "اول سؤال قديم" not in transcript
    assert "مين عمل اكتر عدد PRs؟" in transcript

    # Agent received the rewritten standalone query...
    agent_msgs = captured["messages"]
    assert isinstance(agent_msgs[-1], HumanMessage)
    assert agent_msgs[-1].content == "مين عمل تاني اكتر عدد PRs؟"

    # ...while the DB kept the ORIGINAL user text.
    user_rows = [o for o in fake_session.added if type(o).__name__ == "ChatMessage" and o.role == "user"]
    assert len(user_rows) == 1
    assert user_rows[0].content == "ومين التاني؟"

    assert out["reply"] == "final reply"
    assert out["rewritten_query"] == "مين عمل تاني اكتر عدد PRs؟"
