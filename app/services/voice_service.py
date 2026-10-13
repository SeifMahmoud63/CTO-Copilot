import asyncio
import json
import logging
import re
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple

import websockets
from fastapi import WebSocket, WebSocketDisconnect
from sqlalchemy import text

from app.core.config import settings
from app.db.session import AsyncSessionLocal

logger = logging.getLogger("cto-copilot.voice")

FORBIDDEN_SQL_PATTERN = re.compile(
    r"\b(INSERT|UPDATE|DELETE|DROP|ALTER|TRUNCATE|REPLACE|CREATE|GRANT|REVOKE|FLUSH|KILL|SET|LOCK)\b",
    re.IGNORECASE,
)


def _json_safe(value):
    """Coerce one DB cell into something json.dumps accepts.

    MySQL returns Decimal for SUM/AVG; without this the whole tool call
    collapses into an error. Mirrored in chat_service.
    """
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (bytes, bytearray)):
        return bytes(value).decode("utf-8", errors="replace")
    return value


def parse_function_calls(event: Dict[str, Any]) -> List[Tuple[Optional[str], str, str]]:
    """Extract (call_id, function_name, sql_query) from a Deepgram FunctionCallRequest.

    Per the Voice Agent API spec the request carries a `functions` ARRAY whose
    `arguments` field is a JSON-encoded STRING — not flat id/name/input keys.
    Unknown shapes yield an empty list (never crash the relay loop).
    """
    calls: List[Tuple[Optional[str], str, str]] = []
    # Deepgram passes arguments as a JSON-encoded string inside a functions array.
    try:
        functions = event.get("functions")
        if not isinstance(functions, list):
            return calls
        for func in functions:
            if not isinstance(func, dict):
                continue
            raw_args = func.get("arguments") or "{}"
            if isinstance(raw_args, str):
                try:
                    func_input = json.loads(raw_args) if raw_args.strip() else {}
                except Exception:
                    func_input = {}
            elif isinstance(raw_args, dict):
                func_input = raw_args
            else:
                func_input = {}
            sql_query = func_input.get("sql_query") or func_input.get("query") or ""
            calls.append((func.get("id"), func.get("name") or "", sql_query))
    except Exception as e:
        logger.warning(f"Failed to parse FunctionCallRequest: {e}")
    return calls


class VoiceAgentService:
    def __init__(self):
        self.api_key = settings.deepgram_api_key
        self.agent_url = settings.deepgram_agent_url
        self.agent_model = settings.deepgram_agent_model
        self.voice_model = settings.deepgram_voice_model

    async def execute_readonly_sql(self, sql_query: str) -> str:
        """Execute a read-only SQL query on MySQL."""
        if not sql_query or not sql_query.strip():
            return "Error: Empty SQL query provided."

        clean_sql = re.sub(r"^```(?:sql)?\s*", "", sql_query.strip(), flags=re.IGNORECASE)
        clean_sql = re.sub(r"\s*```$", "", clean_sql).strip().rstrip(";")

        if not re.match(r"^\s*(SELECT|SHOW|DESCRIBE|EXPLAIN)\b", clean_sql, re.IGNORECASE):
            return "Error: Only read-only queries (SELECT, SHOW, DESCRIBE, EXPLAIN) are permitted."

        if FORBIDDEN_SQL_PATTERN.search(clean_sql):
            return "Error: Write, alter, or administrative operations are strictly blocked."

        try:
            async with AsyncSessionLocal() as session:
                await session.execute(text("SET TRANSACTION READ ONLY"))
                result = await session.execute(text(clean_sql))
                rows = result.mappings().all()

                if not rows:
                    return json.dumps({"result": "0 rows returned", "data": []})

                serializable_rows = []
                for row in rows[:30]:  # cap rows so audio response stays concise
                    row_dict = {}
                    for k, v in row.items():
                        row_dict[k] = _json_safe(v)
                    serializable_rows.append(row_dict)

                return json.dumps(serializable_rows, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Voice Agent SQL execution error for '{clean_sql}': {e}", exc_info=True)
            return json.dumps({"error": "Error"})

    def build_settings_payload(self) -> Dict[str, Any]:
        """Deepgram agent handshake configuration."""
        return {
            "type": "Settings",
            "audio": {
                "input": {
                    "encoding": "linear16",
                    "sample_rate": 16000,
                },
                "output": {
                    "encoding": "linear16",
                    "sample_rate": 24000,
                    "container": "none",
                },
            },
            "agent": {
                "listen": {
                    "provider": {
                        "type": "deepgram",
                        "model": self.agent_model,
                    }
                },
                "think": {
                    "provider": {
                        "type": "open_ai",
                        "model": "gpt-4o-mini",
                    },
                    "prompt": (
                        "You are CTO Copilot, a brilliant, friendly, natural engineering voice companion for the CTO. "
                        "You can chat casually and warmly (e.g. greetings, how are you doing, general small talk), "
                        "but whenever the user asks about engineering work, pull requests, authors, contributors, impact scores, "
                        "overdue items, or repository status, you MUST call the `execute_database_query` tool to inspect real MySQL data! "
                        "Database schema: "
                        "- `pull_requests`: id, number, title, author, author_avatar, state ('open'/'merged'/'closed'), "
                        "  head_branch, base_branch, created_at, updated_at, is_overdue, overdue_days, summary_text, impact_score, impact_tier. "
                        "- `engineers`: id, author, pr_count, total_score, avg_score, tier, updated_at. "
                        "- `daily_reports`: id, report_date, title, executive_summary, prs_opened, prs_merged, prs_closed, overdue_count. "
                        "When the user asks what happened in a daily report (e.g. today's report), run "
                        "`SELECT title, executive_summary, prs_opened, prs_merged, overdue_count FROM daily_reports "
                        "ORDER BY report_date DESC LIMIT 1` and speak the highlights conversationally; "
                        "tell them the full PDF is available in the Daily Reports section of the app. "
                        "Rules: "
                        "1. NEVER invent, hallucinate, or guess PR numbers, author names, branches, or statistics. "
                        "2. Keep spoken responses compact: answer ONLY what was asked in 1-2 short sentences; "
                        "highlights only (max ~5 items), never recite long lists or raw tables; "
                        "give details for one explicitly requested item, then offer more. "
                        "3. Reply in the same language the user speaks (Arabic or English). If Arabic, speak natural friendly Arabic."
                    ),
                    "functions": [
                        {
                            "name": "execute_database_query",
                            "description": (
                                "Execute a read-only SELECT SQL query on MySQL (tables: pull_requests, engineers, daily_reports) "
                                "to fetch real live metrics, PR status, author rankings, overdue items, and daily report summaries."
                            ),
                            # No endpoint defined: Deepgram delegates execution to this socket client
                            "parameters": {
                                "type": "object",
                                "properties": {
                                    "sql_query": {
                                        "type": "string",
                                        "description": "The read-only SELECT SQL query to execute.",
                                    }
                                },
                                "required": ["sql_query"],
                            },
                        }
                    ],
                },
                "speak": {
                    "provider": {
                        "type": "deepgram",
                        "model": self.voice_model,
                    }
                },
            },
        }

    async def handle_client_session(self, client_ws: WebSocket):
        await client_ws.accept()

        if not self.api_key:
            logger.error("Voice session rejected: DEEPGRAM_API_KEY is not configured.")
            await client_ws.send_json({
                "type": "error",
                "message": "Error",
            })
            await client_ws.close(code=1008)
            return

        try:
            async with websockets.connect(
                self.agent_url,
                additional_headers={"Authorization": f"Token {self.api_key}"},
                open_timeout=15,
            ) as dg_ws:
                logger.info("Successfully connected to Deepgram Voice Agent API.")

                settings_payload = self.build_settings_payload()
                await dg_ws.send(json.dumps(settings_payload))

                await client_ws.send_json({
                    "type": "Connected",
                    "message": "Voice agent connected. Ready to stream audio.",
                })

                async def client_to_deepgram():
                    try:
                        while True:
                            data = await client_ws.receive()
                            if "bytes" in data and data["bytes"]:
                                await dg_ws.send(data["bytes"])
                            elif "text" in data and data["text"]:
                                try:
                                    msg = json.loads(data["text"])
                                    if msg.get("type") == "Ping":
                                        await client_ws.send_json({"type": "Pong"})
                                except Exception:
                                    pass
                    except WebSocketDisconnect:
                        logger.info("Client browser disconnected voice session.")
                    except asyncio.CancelledError:
                        pass
                    except Exception as err:
                        logger.warning(f"client_to_deepgram loop error: {err}")

                async def deepgram_to_client():
                    try:
                        async for raw_msg in dg_ws:
                            if isinstance(raw_msg, bytes):
                                await client_ws.send_bytes(raw_msg)
                            elif isinstance(raw_msg, str):
                                try:
                                    event = json.loads(raw_msg)
                                    event_type = event.get("type")

                                    if event_type == "FunctionCallRequest":
                                        for call_id, func_name, sql_query in parse_function_calls(event):
                                            logger.info(f"Deepgram requested function: {func_name} | Query: {sql_query}")

                                            # Notify browser to display DB query badge
                                            await client_ws.send_json({
                                                "type": "AgentQueryingDatabase",
                                                "function": func_name,
                                                "query": sql_query,
                                            })

                                            db_result = await self.execute_readonly_sql(sql_query)

                                            call_resp = {
                                                "type": "FunctionCallResponse",
                                                "id": call_id,
                                                "name": func_name,
                                                "content": db_result,
                                            }
                                            await dg_ws.send(json.dumps(call_resp))
                                    else:
                                        await client_ws.send_json(event)
                                except Exception as err:
                                    logger.error(f"Error processing Deepgram message: {err}")
                    except asyncio.CancelledError:
                        pass
                    except Exception as err:
                        logger.warning(f"deepgram_to_client loop error: {err}")

                task_c2d = asyncio.create_task(client_to_deepgram())
                task_d2c = asyncio.create_task(deepgram_to_client())

                done, pending = await asyncio.wait(
                    [task_c2d, task_d2c],
                    return_when=asyncio.FIRST_COMPLETED,
                )

                for p in pending:
                    p.cancel()

        except Exception as e:
            logger.error(f"Voice Agent session exception: {e}", exc_info=True)
            try:
                await client_ws.send_json({"type": "error", "message": "Error"})
            except Exception:
                pass
        finally:
            logger.info("Voice Agent session ended.")


voice_service = VoiceAgentService()
