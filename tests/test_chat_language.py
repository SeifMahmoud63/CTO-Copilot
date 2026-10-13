"""Unit tests locking in the chatbot same-language reply rule.

Run from the repo root:
    python -m pytest tests/test_chat_language.py -v
"""
import asyncio
from unittest.mock import AsyncMock

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from app.services import chat_service as chat_module


def test_system_prompt_has_same_language_rule():
    prompt = chat_module.SYSTEM_PROMPT
    assert "same language" in prompt
    assert "Arabic" in prompt
    assert "English" in prompt


def test_system_prompt_protects_technical_identifiers():
    prompt = chat_module.SYSTEM_PROMPT
    for keyword in ("usernames", "branch names", "URLs", "code"):
        assert keyword in prompt, f"missing identifier guard: {keyword}"


def test_agent_step_prepends_system_prompt_first():
    """The language rule must actually reach the model as message[0]."""
    service = chat_module.ChatService.__new__(chat_module.ChatService)
    fake_reply = AIMessage(content="ok")
    service.llm_with_tools = AsyncMock()
    service.llm_with_tools.ainvoke = AsyncMock(return_value=fake_reply)

    out = asyncio.run(
        service._agent_step({"messages": [HumanMessage(content="مين عمل اخر PR؟")]})
    )

    sent = service.llm_with_tools.ainvoke.call_args[0][0]
    assert isinstance(sent[0], SystemMessage)
    assert "same language" in sent[0].content
    assert sent[1].content == "مين عمل اخر PR؟"
    assert out["messages"] == [fake_reply]


def test_agent_step_injects_current_cairo_date():
    """The model must never guess 'today' from memory (the 2023 incident)."""
    from datetime import datetime
    from zoneinfo import ZoneInfo

    service = chat_module.ChatService.__new__(chat_module.ChatService)
    service.llm_with_tools = AsyncMock()
    service.llm_with_tools.ainvoke = AsyncMock(return_value=AIMessage(content="ok"))

    out = asyncio.run(
        service._agent_step({"messages": [HumanMessage(content="وانهارده كام؟")]})
    )

    sent = service.llm_with_tools.ainvoke.call_args[0][0]
    today = datetime.now(ZoneInfo("Africa/Cairo")).date().isoformat()
    assert today in sent[0].content
    assert "from memory" in sent[0].content
    assert "same language" in sent[0].content  # base prompt intact
    assert out["messages"][0].content == "ok"


def test_tool_call_texts_extracts_sql():
    from langchain_core.messages import AIMessage as _AI

    state = {"messages": [HumanMessage(content="q"), _AI(
        content="",
        tool_calls=[{"name": "execute_readonly_query", "args": {
            "sql_query": "SELECT state FROM pull_requests WHERE number = 5"},
            "id": "t1", "type": "tool_call"}])]}
    texts = chat_module._tool_call_texts(state)
    assert len(texts) == 1 and "number = 5" in texts[0]
    assert chat_module._tool_call_texts({"messages": []}) == []


def test_prev_obs_grounds_followup_without_requery(monkeypatch):
    """Follow-ups may reuse previous-turn evidence (chat awareness)."""
    from types import SimpleNamespace
    from unittest.mock import AsyncMock as _AM

    from app.core.config import settings
    from app.services import judge_service as judge_module

    monkeypatch.setattr(settings, "judge_enabled", False)
    monkeypatch.setattr(
        judge_module.judge_service, "classify_query_intent_jev",
        _AM(return_value="data"))

    service = chat_module.ChatService.__new__(chat_module.ChatService)
    prev = ['[{"number": 5, "author": "SeifMahmoud63", "state": "open"}]']
    no_tools = {"messages": [HumanMessage(content="من مين؟"),
                             AIMessage(content="PR #5 عمله SeifMahmoud63.")]}
    service.graph = SimpleNamespace(ainvoke=_AM(return_value=no_tools))

    out = asyncio.run(service._generate_with_judge(
        [HumanMessage(content="من مين؟")], "من مين؟", prev_obs=prev))
    assert out["verdict"] == "PASS"
    assert "SeifMahmoud63" in out["reply"]
    # Previous-turn data was injected ahead of the base prompt logic.
    sent = service.graph.ainvoke.call_args[0][0]["messages"]
    assert any(getattr(m, "content", "").startswith("[PREVIOUS TURN DATA]")
               for m in sent)


def test_graph_uses_explicit_react_limit(monkeypatch):
    from types import SimpleNamespace
    from unittest.mock import AsyncMock as _AM

    from app.core.config import settings
    from app.services import judge_service as judge_module

    monkeypatch.setattr(settings, "judge_enabled", False)
    monkeypatch.setattr(
        judge_module.judge_service, "classify_query_intent_jev",
        _AM(return_value="general"))

    service = chat_module.ChatService.__new__(chat_module.ChatService)
    service.graph = SimpleNamespace(
        ainvoke=_AM(return_value={"messages": [AIMessage(content="اهلا")]}))
    asyncio.run(service._generate_with_judge([HumanMessage(content="hi")], "hi"))
    _, kwargs = service.graph.ainvoke.call_args
    assert kwargs.get("config", {}).get("recursion_limit") == chat_module.REACT_MAX_STEPS


def test_language_mismatch_cases():
    m = chat_module._language_mismatch
    assert m("How many PRs?", "المساهم الأول هو Seif.") == "English"
    assert m("How many PRs?", "Top contributor is Seif.") is None
    assert m("مين أكتر حد؟", "Top contributor is Seif Mahmoud with five PRs.") == "Arabic"
    assert m("مين أكتر حد؟", "أكتر حد هو Seif.") is None
    assert m("hi", "ok") is None  # short replies exempt
    assert m("hi", "Done.") is None


def test_chat_provider_switch_selects_backend(monkeypatch):
    import sys
    import types

    from app.core.config import settings

    # Gemini path uses the NATIVE GenAI SDK (OpenAI-compat drops Gemini 3
    # thought signatures -> 400s). Fake the module: the dep lives in the
    # image, not necessarily in every dev/test env.
    fake_mod = types.ModuleType("langchain_google_genai")

    class FakeGemini:
        def __init__(self, **kw):
            self.model = kw.get("model")
            self.google_api_key = kw.get("google_api_key")
            self.temperature = kw.get("temperature")

        def bind_tools(self, tools):
            self._tools = list(tools)
            return self

    fake_mod.ChatGoogleGenerativeAI = FakeGemini
    monkeypatch.setitem(sys.modules, "langchain_google_genai", fake_mod)

    monkeypatch.setattr(settings, "chat_provider", "gemini")
    monkeypatch.setattr(settings, "gemini_api_key", "test-gem-key")
    monkeypatch.setattr(settings, "gemini_chat_model", "gemini-3.1-pro-preview")
    svc = chat_module.ChatService()
    assert svc.llm.model == "gemini-3.1-pro-preview"
    assert svc.llm.google_api_key == "test-gem-key"
    assert settings.chat_actor_model == "gemini-3.1-pro-preview"
    # Bedrock path.
    monkeypatch.setattr(settings, "chat_provider", "bedrock")
    svc2 = chat_module.ChatService()
    assert svc2.llm.model_name == settings.bedrock_model
    assert settings.chat_actor_model == settings.bedrock_model
    # Missing-key failsafe: gemini selected without a key boots on Bedrock.
    monkeypatch.setattr(settings, "chat_provider", "gemini")
    monkeypatch.setattr(settings, "gemini_api_key", "")
    svc3 = chat_module.ChatService()
    assert svc3.llm.model_name == settings.bedrock_model


def _gen_service(responses, intent="general"):
    from types import SimpleNamespace
    from unittest.mock import AsyncMock as _AM

    service = chat_module.ChatService.__new__(chat_module.ChatService)
    service.graph = SimpleNamespace(ainvoke=_AM(side_effect=responses))
    return service


def test_language_restatement_round(monkeypatch):
    from unittest.mock import AsyncMock as _AM

    from app.services import judge_service as judge_module

    monkeypatch.setattr(
        judge_module.judge_service, "classify_query_intent_jev",
        _AM(return_value="general"))
    svc = _gen_service([
        {"messages": [AIMessage(content="المساهم الأول هو SeifMahmoud63، عمل 5 PRs.")]},
        {"messages": [AIMessage(content="Top contributor is SeifMahmoud63 with 5 PRs.")]},
    ])
    out = asyncio.run(svc._generate_with_judge(
        [HumanMessage(content="Who is the top contributor?")],
        "Who is the top contributor?"))
    assert out["verdict"] == "PASS_AFTER_RETRY"
    assert out["reply"].startswith("Top contributor")
    assert svc.graph.ainvoke.await_count == 2


def test_language_keeps_original_when_restatement_fails(monkeypatch):
    from unittest.mock import AsyncMock as _AM

    from app.services import judge_service as judge_module

    monkeypatch.setattr(
        judge_module.judge_service, "classify_query_intent_jev",
        _AM(return_value="general"))
    first = "المساهم الأول هو SeifMahmoud63."
    svc = _gen_service([
        {"messages": [AIMessage(content=first)]},
        {"messages": [AIMessage(content="المساهم هو SeifMahmoud63 مجددا.")]},
    ])
    out = asyncio.run(svc._generate_with_judge(
        [HumanMessage(content="Who is the top contributor?")],
        "Who is the top contributor?"))
    assert out["reply"] == first  # correct content beats fallback
    assert out["verdict"] == "PASS"


def test_message_text_handles_block_content():
    # Gemini native SDK returns list-of-blocks content (text + thinking).
    m = AIMessage(content=[
        {"type": "text", "text": "عندنا 5 PRs."},
        {"type": "thinking", "thinking": "internal reasoning"},
        {"type": "text", "text": " النهاردة."},
    ])
    assert chat_module._message_text(m) == "عندنا 5 PRs. النهاردة."
    assert chat_module._message_text(AIMessage(content="plain")) == "plain"
    assert chat_module._message_text(AIMessage(content=[])) == ""
    assert chat_module._message_text(AIMessage(content=[{"type": "x"}])) == ""


def test_generate_accepts_block_content_reply(monkeypatch):
    from unittest.mock import AsyncMock as _AM

    from app.services import judge_service as judge_module

    monkeypatch.setattr(
        judge_module.judge_service, "classify_query_intent_jev",
        _AM(return_value="general"))
    svc = _gen_service([
        {"messages": [AIMessage(content=[{"type": "text", "text": "أهلا بيك!"}])]},
    ])
    out = asyncio.run(svc._generate_with_judge(
        [HumanMessage(content="ازيك؟")], "ازيك؟"))
    assert out["reply"] == "أهلا بيك!"
    assert isinstance(out["reply"], str)
