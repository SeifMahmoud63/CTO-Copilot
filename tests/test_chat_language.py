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
