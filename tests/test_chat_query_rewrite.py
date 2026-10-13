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


def test_chat_llm_wires_reasoning_effort(monkeypatch):
    from app.core.config import settings
    from langchain_openai import ChatOpenAI

    real_init = ChatOpenAI.__init__
    seen = {}

    def spy_init(self, *args, **kwargs):
        seen.update(kwargs)
        real_init(self, *args, **kwargs)

    monkeypatch.setattr(ChatOpenAI, "__init__", spy_init)
    monkeypatch.setattr(settings, "llm_reasoning_effort", "low")
    chat_module.ChatService()
    assert seen.get("extra_body") == {"reasoning_effort": "low"}

    seen.clear()
    monkeypatch.setattr(settings, "llm_reasoning_effort", "")
    chat_module.ChatService()
    assert "extra_body" not in seen

    seen.clear()
    monkeypatch.setattr(settings, "llm_reasoning_effort", "nonsense")
    chat_module.ChatService()
    assert "extra_body" not in seen


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


def test_rewrite_prompt_has_time_preservation_rule():
    prompt = chat_module.QUERY_REWRITE_PROMPT
    assert "NEVER drop time/date constraints" in prompt
    assert "انهارده" in prompt
    assert "EXACTLY" in prompt


def test_rewrite_prompt_normalizes_bare_day_kam():
    # "wa-inhardah kam?" (no countable noun) means "what DATE is today" — the
    # rule must be spelled out or the agent asks back instead of answering.
    prompt = chat_module.QUERY_REWRITE_PROMPT
    assert "تاريخ كام" in prompt
    assert "NO countable noun" in prompt


def test_rewrite_dropping_time_marker_falls_back_to_original():
    # The live incident: "andana kam PR inhardah?" rewritten to "hat adad PR"
    # answers a DIFFERENT question — the original must win.
    service = make_service("هات عدد PR اللي عندنا حاليًا.")
    out = run(service._rewrite_query(HISTORY, "عندنا كام PR انهارده؟"))
    assert out == "عندنا كام PR انهارده؟"


def test_rewrite_preserving_time_marker_is_used():
    service = make_service("كم عدد PR المنشأة اليوم؟")
    out = run(service._rewrite_query(HISTORY, "عندنا كام PR انهارده؟"))
    assert out == "كم عدد PR المنشأة اليوم؟"


def test_has_time_marker():
    assert chat_module._has_time_marker("عندنا كام PR انهارده؟") is True
    assert chat_module._has_time_marker("لخص ريبورت امبارح") is True
    assert chat_module._has_time_marker("PRs merged this week?") is True
    assert chat_module._has_time_marker("I know the author") is False  # "now" != "know"
    assert chat_module._has_time_marker("مين عمل اكتر عدد PRs؟") is False
    assert chat_module._has_time_marker("") is False


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


def test_directness_and_dialect_rules_in_prompts():
    prompt = chat_module.SYSTEM_PROMPT
    assert "state the single computed number FIRST" in prompt
    assert "متعلقه" in prompt and "overdue" in prompt


def test_oldest_latest_order_rule_in_prompt():
    # The live incident: "aqdam PR" answered with ORDER BY number DESC.
    prompt = chat_module.SYSTEM_PROMPT
    assert "Oldest vs latest" in prompt
    assert "NEVER invert ASC/DESC" in prompt
    assert "created_at" in prompt and "sent_at" in prompt


def test_language_mismatch_rule_in_prompts():
    prompt = chat_module.SYSTEM_PROMPT
    assert "Language mismatch is a critical failure" in prompt


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

    async def fake_graph(messages, config=None):
        captured["messages"] = messages["messages"]
        captured["config"] = config
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
    assert agent_msgs[-1].content.endswith("مين عمل تاني اكتر عدد PRs؟")
    # ...through the bounded ReAct loop config.
    assert (captured["config"] or {}).get("recursion_limit") == chat_module.REACT_MAX_STEPS

    # ...while the DB kept the ORIGINAL user text.
    user_rows = [o for o in fake_session.added if type(o).__name__ == "ChatMessage" and o.role == "user"]
    assert len(user_rows) == 1
    assert user_rows[0].content == "ومين التاني؟"

    assert out["reply"] == "final reply"
    assert out["rewritten_query"] == "مين عمل تاني اكتر عدد PRs؟"
