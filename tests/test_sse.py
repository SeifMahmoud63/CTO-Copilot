"""Unit tests for Eval Lab TTFT + SSE streaming (no LLM, no network, no DB).

Covers: _TokenTap assembly/timing/fallback, _agent_step tap wiring,
send_message_stream event framing, and the /api/chat/sse toggle +
stream endpoints (called directly, no TestClient/auth needed).

Run from the repo root:
    python -m pytest tests/test_sse.py -v
"""
import asyncio

import pytest
from fastapi import HTTPException
from langchain_core.messages import AIMessage, AIMessageChunk, HumanMessage

from app.services import chat_service as chat_module


class FakeLLM:
    """Stands in for the bound runnable (llm_with_tools)."""

    def __init__(self, chunks=None, fail_stream=False):
        self._chunks = chunks or []
        self._fail = fail_stream

    async def astream(self, messages):
        if self._fail:
            raise RuntimeError("stream boom")
        for c in self._chunks:
            yield c

    async def ainvoke(self, messages):
        return AIMessage(content="fallback-full")


def test_token_tap_assembles_and_times():
    tap_holder = {}
    seen = []
    tap = chat_module._TokenTap(
        FakeLLM(chunks=[AIMessageChunk(content="Hel"),
                        AIMessageChunk(content="lo")]),
        on_token=seen.append,
        holder=tap_holder,
        t0=__import__("time").perf_counter(),
    )
    out = asyncio.run(tap.ainvoke([HumanMessage(content="hi")]))
    assert out.content == "Hello"
    assert seen == ["Hel", "lo"]
    assert isinstance(tap_holder.get("ttft_s"), float)
    assert tap_holder["ttft_s"] >= 0


def test_token_tap_falls_back_to_invoke():
    tap_holder = {}
    tap = chat_module._TokenTap(
        FakeLLM(fail_stream=True), holder=tap_holder)
    out = asyncio.run(tap.ainvoke([HumanMessage(content="hi")]))
    assert out.content == "fallback-full"
    assert tap_holder.get("ttft_s") is None


def test_agent_step_uses_tap_when_set():
    service = chat_module.ChatService.__new__(chat_module.ChatService)
    service.llm_with_tools = FakeLLM(
        chunks=[AIMessageChunk(content="streamed")])
    seen = []
    holder = {}
    tap = chat_module._TokenTap(
        service.llm_with_tools, on_token=seen.append, holder=holder)
    token = chat_module._token_tap.set(tap)
    try:
        out = asyncio.run(
            service._agent_step({"messages": [HumanMessage(content="hi")]})
        )
    finally:
        chat_module._token_tap.reset(token)
    assert out["messages"][0].content == "streamed"
    assert seen == ["streamed"]
    assert holder.get("ttft_s") is not None


def test_send_message_stream_framing():
    service = chat_module.ChatService.__new__(chat_module.ChatService)

    async def fake_run_turn(session_id, user_content, on_token=None):
        assert session_id == "sid"
        if on_token is not None:
            on_token("Hi")
            on_token(" there")
        return {"reply": "Hi there", "verdict": "PASS",
                "ttft_s": 0.1, "latency_s": 0.5}

    service._run_turn = fake_run_turn

    async def collect():
        return [e async for e in service.send_message_stream("sid", "q")]

    events = asyncio.run(collect())
    assert events[0] == {"type": "token", "delta": "Hi"}
    assert events[1] == {"type": "token", "delta": " there"}
    done = events[-1]
    assert done["type"] == "done"
    assert done["reply"] == "Hi there"
    assert done["ttft_s"] == 0.1
    assert done["latency_s"] == 0.5


def test_send_message_stream_error_event():
    service = chat_module.ChatService.__new__(chat_module.ChatService)

    async def boom(session_id, user_content, on_token=None):
        raise RuntimeError("db down")

    service._run_turn = boom

    async def collect():
        return [e async for e in service.send_message_stream("sid", "q")]

    events = asyncio.run(collect())
    assert len(events) == 1 and events[0]["type"] == "error"
    # Internal details stay in logs; the site sees "Error" only.
    assert events[0]["message"] == "Error"


def test_sse_config_defaults_off():
    from app.core.config import Settings

    assert Settings().chat_sse_enabled is False


def test_sse_config_roundtrip(monkeypatch):
    from app.api import routes
    from app.core.config import settings

    monkeypatch.setattr(settings, "chat_sse_enabled", False)
    assert asyncio.run(routes.get_sse_config()) == {"enabled": False}
    out = asyncio.run(
        routes.set_sse_config(routes.SSEConfigRequest(enabled=True)))
    assert out == {"enabled": True, "persistent": False}
    assert settings.chat_sse_enabled is True
    assert asyncio.run(routes.get_sse_config()) == {"enabled": True}


def test_stream_endpoint_403_when_disabled(monkeypatch):
    from app.api import routes
    from app.core.config import settings

    monkeypatch.setattr(settings, "chat_sse_enabled", False)
    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(routes.stream_chat_message(
            "sid", routes.SendMessageRequest(message="hi")))
    assert exc_info.value.status_code == 403


def test_stream_endpoint_empty_message_400(monkeypatch):
    from app.api import routes
    from app.core.config import settings

    monkeypatch.setattr(settings, "chat_sse_enabled", True)
    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(routes.stream_chat_message(
            "sid", routes.SendMessageRequest(message="   ")))
    assert exc_info.value.status_code == 400


def test_stream_endpoint_sse_frames(monkeypatch):
    from app.api import routes
    from app.core.config import settings

    monkeypatch.setattr(settings, "chat_sse_enabled", True)

    async def fake_stream(session_id, message):
        yield {"type": "token", "delta": "Hello"}
        yield {"type": "done", "reply": "Hello", "verdict": "PASS",
               "ttft_s": 0.2, "latency_s": 1.0}

    monkeypatch.setattr(
        routes.chat_service, "send_message_stream", fake_stream)
    resp = asyncio.run(routes.stream_chat_message(
        "sid", routes.SendMessageRequest(message="hi")))
    assert resp.media_type == "text/event-stream"

    async def read_body():
        chunks = [c async for c in resp.body_iterator]
        return b"".join(
            c.encode("utf-8") if isinstance(c, str) else c for c in chunks
        )

    body = asyncio.run(read_body()).decode("utf-8")
    assert 'data: {"type": "token", "delta": "Hello"}\n\n' in body
    assert '"type": "done"' in body
    assert '"ttft_s": 0.2' in body
