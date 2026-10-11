"""Unit tests for the Deepgram live voice agent (protocol-level review).

Run from the repo root:
    python -m pytest tests/test_voice_agent.py -v
"""
import asyncio
import json

from app.services import voice_service as voice_module


def run(coro):
    return asyncio.run(coro)


def test_settings_payload_matches_agent_schema():
    service = voice_module.VoiceAgentService.__new__(voice_module.VoiceAgentService)
    service.agent_model = "nova-3"
    service.voice_model = "aura-asteria-en"
    payload = voice_module.VoiceAgentService.build_settings_payload(service)

    assert payload["type"] == "Settings"
    assert payload["audio"]["input"] == {"encoding": "linear16", "sample_rate": 16000}
    assert payload["audio"]["output"]["encoding"] == "linear16"
    assert payload["audio"]["output"]["sample_rate"] == 24000
    think = payload["agent"]["think"]
    assert think["provider"]["type"] == "open_ai"
    funcs = think["functions"]
    assert len(funcs) == 1
    assert funcs[0]["name"] == "execute_database_query"
    # Per spec there is NO `client_side` flag: omitting `endpoint` means client-side.
    assert "client_side" not in funcs[0]
    assert "endpoint" not in funcs[0]
    assert "sql_query" in funcs[0]["parameters"]["properties"]
    assert payload["agent"]["speak"]["provider"]["model"] == "aura-asteria-en"


def test_parse_function_calls_spec_shape():
    """Official spec: functions ARRAY with JSON-STRING arguments."""
    event = {
        "type": "FunctionCallRequest",
        "functions": [
            {
                "id": "call_1",
                "name": "execute_database_query",
                "arguments": json.dumps({"sql_query": "SELECT * FROM engineers"}),
                "client_side": True,
            },
            {
                "id": "call_2",
                "name": "execute_database_query",
                "arguments": {"sql_query": "SELECT 1"},
                "client_side": True,
            },
        ],
    }
    calls = voice_module.parse_function_calls(event)
    assert calls == [
        ("call_1", "execute_database_query", "SELECT * FROM engineers"),
        ("call_2", "execute_database_query", "SELECT 1"),
    ]


def test_parse_function_calls_unknown_shapes_never_crash():
    assert voice_module.parse_function_calls({"type": "FunctionCallRequest"}) == []
    assert voice_module.parse_function_calls({"type": "FunctionCallRequest", "functions": "nope"}) == []
    assert voice_module.parse_function_calls({"type": "FunctionCallRequest", "functions": [{"id": "x"}]}) == [("x", "", "")]
    # Legacy flat shape (pre-spec) yields nothing instead of a bogus empty query.
    assert voice_module.parse_function_calls(
        {"type": "FunctionCallRequest", "id": "y", "name": "f", "input": {"sql_query": "SELECT 1"}}
    ) == []
    assert voice_module.parse_function_calls({}) == []


def test_readonly_sql_guard_without_db():
    service = voice_module.VoiceAgentService.__new__(voice_module.VoiceAgentService)
    assert "Empty" in run(service.execute_readonly_sql("   "))
    assert "read-only" in run(service.execute_readonly_sql("DELETE FROM pull_requests")).lower()
    assert "blocked" in run(service.execute_readonly_sql("SELECT * FROM engineers; DROP TABLE engineers")).lower()
    assert "read-only" in run(service.execute_readonly_sql("UPDATE engineers SET tier='x'")).lower()


class FakeClientWs:
    """In-memory stand-in for FastAPI WebSocket (no network)."""

    def __init__(self):
        self.sent_json = []
        self.sent_bytes = []
        self.closed = None

    async def accept(self):
        return None

    async def send_json(self, data):
        self.sent_json.append(data)

    async def send_bytes(self, data):
        self.sent_bytes.append(data)

    async def close(self, code=1000):
        self.closed = code


def test_missing_api_key_rejected_cleanly():
    service = voice_module.VoiceAgentService.__new__(voice_module.VoiceAgentService)
    service.api_key = ""
    client = FakeClientWs()
    run(service.handle_client_session(client))
    assert client.sent_json and client.sent_json[0]["type"] == "error"
    assert "DEEPGRAM_API_KEY" in client.sent_json[0]["message"]
    assert client.closed == 1008


def test_deepgram_connect_failure_reported_to_client(monkeypatch):
    import websockets as ws_pkg

    def boom(*args, **kwargs):
        raise RuntimeError("no route to host")

    monkeypatch.setattr(ws_pkg, "connect", boom)
    service = voice_module.VoiceAgentService.__new__(voice_module.VoiceAgentService)
    service.api_key = "dummy-key"
    service.agent_url = "wss://agent.deepgram.com/v1/agent/converse"
    client = FakeClientWs()
    run(service.handle_client_session(client))
    assert client.sent_json and client.sent_json[-1]["type"] == "error"


def test_voice_view_ids_exist_in_html():
    html = open("web/index.html", encoding="utf-8").read()
    for element_id in [
        "voiceView", "voiceOrb", "voiceStatusPill", "voiceStatusText",
        "voiceDbQueryBadge", "voiceDbQueryText", "btnVoiceToggle",
        "voiceBtnLabel", "btnVoiceMute", "voiceTranscriptBox",
        "voiceInterruptionNotice", "drawerVoiceBtn",
    ]:
        assert f'id="{element_id}"' in html, f"missing #{element_id} in index.html"
