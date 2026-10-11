import logging
import re
import json
import uuid
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Any, Optional, Sequence, Annotated, TypedDict

from sqlalchemy import select, delete, text
from sqlalchemy.ext.asyncio import AsyncSession
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage, ToolMessage
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages

from app.core.config import settings
from app.db.session import AsyncSessionLocal, engine
from app.models.chat_model import ChatSession, ChatMessage

logger = logging.getLogger("cto-copilot.chat")

SYSTEM_PROMPT = """You are the CTO Copilot AI Assistant, an engineering management advisor.
You have direct read-only access to the engineering team's live MySQL database (`cto_copilot_db`).

Available database tables and schema:
1. `pull_requests`:
   - `id` (int): Internal ID
   - `number` (int): GitHub PR number (e.g. 1, 2, 3, 4)
   - `title` (str): Pull request title
   - `author` (str): GitHub username (e.g. 'SeifMahmoud63')
   - `author_avatar` (str): URL of user's GitHub avatar
   - `state` (str): 'open', 'merged', or 'closed'
   - `head_branch` (str), `base_branch` (str)
   - `created_at` (datetime), `updated_at` (datetime)
   - `html_url` (str): Link to GitHub PR
   - `is_overdue` (bool): 1 if PR is open and exceeded SLA threshold, else 0
   - `overdue_days` (int): Number of days PR has been open past threshold
   - `summary_text` (text): Executive AI summary of code changes
   - `impact_score` (float): Architectural impact score (0 to 10)
   - `impact_tier` (str): 'Critical Driver', 'High Impact', 'Solid Contributor', 'Routine Support'

 2. `engineers`:
    - `id` (int): Internal ID
    - `author` (str): Contributor username (e.g. 'SeifMahmoud63')
    - `author_avatar` (str): Avatar URL
    - `pr_count` (int): Total pull request count
    - `total_score` (float): Sum of impact scores
    - `avg_score` (float): Average impact score (0 to 10)
    - `tier` (str): Current tier ('Critical Driver', 'High Impact', 'Solid Contributor', 'Routine Support')
    - `updated_at` (datetime)

 3. `daily_reports`:
    - `id` (int), `report_date` (date), `title` (str)
    - `executive_summary` (text): the day's AI executive analysis
    - `prs_opened/prs_merged/prs_closed/overdue_count` (int)
    - For "today's report" questions: SELECT title, executive_summary FROM daily_reports ORDER BY report_date DESC LIMIT 1.

 Tool routing:
- DB questions (PRs, authors, scores, overdue, reports) -> `execute_readonly_query` (tables: pull_requests, engineers, daily_reports).
- Report summaries by day ("لخص ريبورت النهاردة", "summarize yesterday's report") -> `summarize_report` (NOT SQL — it resolves today/انهارده/dates itself).
- Time/date questions ("الساعة كام", "what time is it") -> `get_current_datetime` (Africa/Cairo).
- General/external questions (news, facts, definitions outside the DB) -> `web_search`.

Guidelines:
- When the user asks about pull requests, authors, stats, overdue items, scores, or repository metrics, ALWAYS use the `execute_readonly_query` tool to inspect the real data before answering.
- You can chat casually and offer strategic, architectural, and engineering leadership insights.
- Provide clear, well-formatted markdown responses (tables, bullet points, code blocks where appropriate).

Response discipline (IMPORTANT — answer ONLY what was asked):
- SHORT first: 1-3 sentences for simple questions, a compact list for listings. Expand ONLY if the user explicitly asks for details.
- Never volunteer unrequested extras: no background lessons, no related trivia, no "did you know".
- No fluff openers ("بالتأكيد!", "سؤال ممتاز") and no meta-talk about tools/queries ("I queried the database...") — just deliver the answer.
- No generic closing offers. Exception: after a LIST, end with one short question naming the next step ("عايز تفاصيل أنهي واحد؟").
- Default to COMPACT lists: PR number + title + author + state, max ~10 items.
- Full details ONLY for a single explicitly requested PR — even if the DB returned many rows, never paste details of many PRs in one reply.
- If results exceed ~10 items, report counts + show the top few, and offer to narrow down.
- Tables ONLY when comparing 3+ items side by side; otherwise plain short lines.
- Format timestamps nicely for humans ("10 أكتوبر، 13:09" / "Oct 10, 13:09") — never paste raw ISO datetimes with T.

Language (strict):
- ALWAYS reply in the same language the user used in their latest message.
- If the user writes in Arabic (including Egyptian dialect), reply in Arabic — same dialect when recognizable, otherwise Modern Standard Arabic.
- If the user writes in English, reply in English.
- One reply = one language; do not mix Arabic and English sentences.
- NEVER translate technical identifiers: keep table/column names, usernames, branch names, URLs, numbers, dates, PR numbers, and code exactly as-is in Latin script (they render isolated via bidi handling on the client).
"""

QUERY_REWRITE_PROMPT = """You are a query rewriter for a conversational engineering assistant.
You receive the recent conversation (last messages) plus the user's latest message.

Decide:
- If the latest message is a FOLLOW-UP that depends on prior context
  (pronouns like "it/that", phrases like "and what about", "the second one",
  or Arabic like "ده/دي/التاني/ومين"), rewrite it as ONE standalone question
  that embeds all needed context (names, PR numbers, entities, metrics).
- Otherwise return the latest message EXACTLY as-is.

Rules:
- Reply in the SAME language as the latest message. THIS IS MANDATORY:
  an Arabic message MUST get an Arabic rewrite, an English message an English
  rewrite — never switch languages (the few-shot examples below are illustrative only).
- Output ONLY the rewritten question: no explanations, no quotes, no preamble.
- NEVER translate technical identifiers (usernames, branches, URLs, numbers, code).

Coreference & ordinal resolution (IMPORTANT — the rewrite context ALWAYS
carries the assistant's latest answer, use it):
- Words like "التاني/التانية/ده/دي" or "second/that/it" ALWAYS refer to
  something in the assistant's previous message — resolve them to the CONCRETE entity.
- Ordinals ("first/second/third", "الأول/التاني/التالت") count items in the
  assistant's last list IN ORDER: "the second one" = the 2nd listed item.
  Output its REAL identifier (PR number, title, author name) — NEVER output a
  bare ordinal ("PR رقم 2" is WRONG unless the list literally says number 2).
- If the previous answer contains no such entity, return the message as-is.

Examples:
- assistant listed PRs [#10, #7, #3], user says "اه التانيه"
  -> "هات تفاصيل PR رقم #7 (التاني في القائمة اللي ذكرتها)".
- assistant listed [#1, #3, #2], user says "ابعتلي التاني"
  -> "هات تفاصيل PR رقم 2" (explicit numbers beat positions).
- user says "and its author?" right after PR #5 details
  -> "Who is the author of PR #5?".
"""

# Read-only guard pattern
FORBIDDEN_SQL_PATTERN = re.compile(
    r"\b(INSERT|UPDATE|DELETE|DROP|ALTER|TRUNCATE|REPLACE|CREATE|GRANT|REVOKE|FLUSH|KILL|SET|LOCK)\b",
    re.IGNORECASE
)

@tool
def get_database_schema() -> str:
    """Returns the names and schemas of all available database tables."""
    return (
        "Tables:\n"
        "- pull_requests (id, github_pr_id, number, title, author, author_avatar, state, head_branch, base_branch, html_url, diff_url, created_at, updated_at, is_overdue, overdue_days, summary_text, summary_provider, summary_timestamp, impact_score, impact_tier)\n"
        "- engineers (id, author, author_avatar, pr_count, total_score, avg_score, tier, updated_at)\n"
        "- daily_reports (id, report_date, title, executive_summary, prs_opened, prs_merged, prs_closed, overdue_count, pdf_path, created_at)\n"
    )

@tool
async def execute_readonly_query(sql_query: str) -> str:
    """Executes a strictly READ-ONLY SQL query (SELECT, SHOW, DESCRIBE, EXPLAIN) on the MySQL database and returns the results.
    
    Args:
        sql_query: The SQL query to execute. Must only be a SELECT or read query.
    """
    clean_sql = re.sub(r"^```(?:sql)?\s*", "", sql_query.strip(), flags=re.IGNORECASE)
    clean_sql = re.sub(r"\s*```$", "", clean_sql).strip().rstrip(";")
    
    if not re.match(r"^\s*(SELECT|SHOW|DESCRIBE|EXPLAIN)\b", clean_sql, re.IGNORECASE):
        return "Error: Only read-only queries (SELECT, SHOW, DESCRIBE, EXPLAIN) are permitted."
    
    if FORBIDDEN_SQL_PATTERN.search(clean_sql):
        return "Error: Write, alter, or administrative operations are strictly blocked by read-only enforcement."
    
    try:
        async with AsyncSessionLocal() as session:
            await session.execute(text("SET TRANSACTION READ ONLY"))
            result = await session.execute(text(clean_sql))
            rows = result.mappings().all()
            
            if not rows:
                return "Query executed successfully. Result: 0 rows returned."
            
            serializable_rows = []
            for row in rows[:50]:  # safety cap at 50 rows
                row_dict = {}
                for k, v in row.items():
                    if isinstance(v, (datetime,)):
                        row_dict[k] = v.isoformat()
                    else:
                        row_dict[k] = v
                serializable_rows.append(row_dict)
                
            return json.dumps(serializable_rows, indent=2, ensure_ascii=False)
    except Exception as e:
        logger.error(f"SQL execution error for '{clean_sql}': {e}")
        return f"Database Error: {str(e)}"

class AgentState(TypedDict):
    messages: Annotated[Sequence[BaseMessage], add_messages]

CAIRO_TZ = "Africa/Cairo"


@tool
def get_current_datetime() -> str:
    """Returns the current date and time in Africa/Cairo timezone.

    Use for any time/date question ("الساعة كام", "what time is it", today's date).
    """
    try:
        from zoneinfo import ZoneInfo

        now = datetime.now(ZoneInfo(CAIRO_TZ))
    except Exception:
        now = datetime.now(timezone.utc)
    return json.dumps({
        "datetime": now.isoformat(),
        "date": now.date().isoformat(),
        "time": now.strftime("%H:%M"),
        "weekday": now.strftime("%A"),
        "timezone": CAIRO_TZ,
    }, ensure_ascii=False)


async def _ddg_instant_search(query: str) -> str:
    """Query DuckDuckGo Instant Answer API (no key needed), formatted for the model."""
    import httpx

    async with httpx.AsyncClient(timeout=10.0) as client:
        res = await client.get(
            "https://api.duckduckgo.com/",
            params={"q": query, "format": "json", "no_html": "1", "skip_disambig": "1"},
            headers={"User-Agent": "Mozilla/5.0"},
        )
        res.raise_for_status()
        data = res.json()
    parts = []
    if data.get("AbstractText"):
        parts.append(f"Summary: {data['AbstractText']} (Source: {data.get('AbstractURL', '')})")
    for r in (data.get("Results") or [])[:3]:
        if isinstance(r, dict) and r.get("Text"):
            parts.append(f"- {r['Text']} ({r.get('FirstURL', '')})")
    for t in (data.get("RelatedTopics") or [])[:5]:
        if isinstance(t, dict) and t.get("Text"):
            parts.append(f"- {t['Text']}")
    return "\n".join(parts) if parts else "No instant answer found for this query."


async def _ddg_html_search(query: str) -> str:
    """Fallback: scrape DuckDuckGo HTML results (works for any query).

    NOTE: must POST (the form endpoint) — plain GET is served a bot-check
    page without results.
    """
    import html as html_lib
    import urllib.parse

    import httpx

    async with httpx.AsyncClient(timeout=12.0) as client:
        res = await client.post(
            "https://html.duckduckgo.com/html/",
            data={"q": query},
            headers={"User-Agent": "Mozilla/5.0"},
        )
        res.raise_for_status()
        page = res.text
    links = re.findall(
        r'class="result__a"[^>]*href="([^"]+)"[^>]*>(.*?)</a>', page, re.DOTALL
    )
    snippets = re.findall(r'class="result__snippet"[^>]*>(.*?)</a>', page, re.DOTALL)

    def clean_link(href: str) -> str:
        # Unwrap //duckduckgo.com/l/?uddg=<encoded-target> redirects.
        m = re.search(r"uddg=([^&]+)", href)
        if m:
            try:
                return urllib.parse.unquote(m.group(1))
            except Exception:
                pass
        return href

    def clean_text(raw: str) -> str:
        no_tags = re.sub(r"<[^>]+>", "", raw)
        return html_lib.unescape(no_tags).strip()

    parts = []
    for i, (href, title) in enumerate(links[:5]):
        snippet = clean_text(snippets[i]) if i < len(snippets) else ""
        line = f"- {clean_text(title)} ({clean_link(href)})"
        if snippet:
            line += f": {snippet}"
        parts.append(line)
    return "\n".join(parts) if parts else "No web results found for this query."


ARABIC_MONTHS = {
    "يناير": 1, "فبراير": 2, "مارس": 3, "أبريل": 4, "ابريل": 4,
    "مايو": 5, "يونيو": 6, "يوليو": 7, "يوليه": 7, "أغسطس": 8, "اغسطس": 8,
    "سبتمبر": 9, "أكتوبر": 10, "اكتوبر": 10, "نوفمبر": 11, "ديسمبر": 12,
}
ENGLISH_MONTHS = {
    "january": 1, "jan": 1, "february": 2, "feb": 2, "march": 3, "mar": 3,
    "april": 4, "apr": 4, "may": 5, "june": 6, "jun": 6, "july": 7, "jul": 7,
    "august": 8, "aug": 8, "september": 9, "sep": 9, "sept": 9,
    "october": 10, "oct": 10, "november": 11, "nov": 11, "december": 12, "dec": 12,
}
TODAY_WORDS = {"today", "tonight", "now", "النهاردة", "انهارده", "النهارده", "اليوم", "نهاردة", "نهارده"}
YESTERDAY_WORDS = {"yesterday", "امبارح", "أمس", "امس"}


def parse_report_date(ref: str, today) -> Optional[object]:
    """Resolve a free-form day reference to a `date` (Cairo-based `today`).

    Accepts: today/انهارده, yesterday/امبارح, YYYY-MM-DD, DD/MM/YYYY,
    DD-MM-YYYY, and 'DD month [YYYY]' in Arabic or English.
    Returns None when unparseable.
    """
    from datetime import date as date_cls

    if not ref:
        return None
    s = ref.strip().lower()
    if s in TODAY_WORDS:
        return today
    if s in YESTERDAY_WORDS:
        return today - timedelta(days=1)
    m = re.match(r"^(\d{4})-(\d{1,2})-(\d{1,2})$", s)
    if m:
        try:
            return date_cls(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except ValueError:
            return None
    m = re.match(r"^(\d{1,2})[/-](\d{1,2})[/-](\d{4})$", s)
    if m:
        try:
            return date_cls(int(m.group(3)), int(m.group(2)), int(m.group(1)))
        except ValueError:
            return None
    m = re.match(r"^(\d{1,2})\s+([^\d\s]+)(?:\s+(\d{4}))?$", s)
    if m:
        month = ARABIC_MONTHS.get(m.group(2), ENGLISH_MONTHS.get(m.group(2)))
        if month:
            try:
                return date_cls(int(m.group(3)) if m.group(3) else today.year,
                                month, int(m.group(1)))
            except ValueError:
                return None
    m = re.match(r"^([^\d\s]+)\s+(\d{1,2})(?:\s+(\d{4}))?$", s)
    if m:
        month = ARABIC_MONTHS.get(m.group(1), ENGLISH_MONTHS.get(m.group(1)))
        if month:
            try:
                return date_cls(int(m.group(3)) if m.group(3) else today.year,
                                month, int(m.group(2)))
            except ValueError:
                return None
    return None


@tool
async def summarize_report(report_date: str) -> str:
    """Fetch and summarize a daily CTO report for any day you choose.

    `report_date` accepts: 'today'/'انهارده', 'yesterday'/'امبارح',
    'YYYY-MM-DD', 'DD/MM/YYYY', or 'DD month [YYYY]' (Arabic or English).
    Use this (NOT SQL) whenever the user asks to summarize a report day.
    """
    from zoneinfo import ZoneInfo

    from app.services.db_service import db_service

    try:
        today = datetime.now(ZoneInfo(CAIRO_TZ)).date()
    except Exception:
        today = datetime.now(timezone.utc).date()
    day = parse_report_date(report_date, today)
    if day is None:
        return (
            "Could not understand that date. Ask for 'today'/'انهارده', "
            "'yesterday'/'امبارح', 'YYYY-MM-DD', or e.g. '10 أكتوبر 2026'."
        )
    try:
        rec = await db_service.get_report_by_date(day.isoformat())
        if not rec:
            available = await db_service.get_reports(limit=7)
            dates = ", ".join(r.get("report_date", "?") for r in available) or "none yet"
            return f"No daily report found for {day.isoformat()}. Available report dates: {dates}."
        summary = (rec.get("executive_summary") or "").strip()
        if len(summary) > 2000:
            summary = summary[:2000].rstrip() + "…"
        return (
            f"Daily report — {rec.get('report_date')} ({rec.get('title', '')}):\n"
            f"Opened: {rec.get('prs_opened', 0)} | Merged: {rec.get('prs_merged', 0)} | "
            f"Closed: {rec.get('prs_closed', 0)} | Overdue: {rec.get('overdue_count', 0)}\n"
            f"Summary:\n{summary}"
        )
    except Exception as e:
        logger.warning(f"Report summary failed for '{report_date}': {e}")
        return "Could not load that daily report right now."


@tool
async def web_search(query: str) -> str:
    """Search the web for general/external knowledge (news, facts, definitions).

    Use ONLY when the question cannot be answered from the database, the
    current time, or your own knowledge. Do NOT use for PR/author/score data.
    """
    try:
        instant = await _ddg_instant_search(query.strip())
        if "No instant answer found" not in instant:
            return instant
        return await _ddg_html_search(query.strip())
    except Exception as e:
        logger.warning(f"Web search failed for '{query}': {e}")
        return "Web search is currently unavailable. Answer from your own knowledge and say so briefly."


ORDINAL_MAP = {
    "first": 1, "1st": 1, "الأول": 1, "الاول": 1, "الاولاني": 1, "الاوله": 1, "الأوله": 1, "الأولى": 1,
    "second": 2, "2nd": 2, "التاني": 2, "التانيه": 2, "التانية": 2, "الثاني": 2, "الثانيه": 2, "الثانية": 2,
    "third": 3, "3rd": 3, "التالت": 3, "التالته": 3, "التالتة": 3, "الثالث": 3, "الثالثه": 3, "الثالثة": 3,
}
# Content-free fillers: tokens that alone carry no meaning ("اه التانيه" -> ordinal only).
# Scope refiners (بس/فقط/مش كلو...) keep the singular intent, so they pass too.
ORDINAL_FILLERS = {
    "اه", "أيوه", "ايوه", "أيوا", "ايوا", "تمام", "طيب", "ماشي", "ها",
    "لو", "سمحت", "من", "فضلك", "please", "yes", "yeah", "ok", "okay",
    "هات", "هاتلي", "عايز", "عاوز", "تفاصيل", "ال", "the", "one", "واحد",
    "واحدة", "واحده", "pr",
    "بس", "فقط", "مش", "كلو", "كله", "كلهم", "just", "only", "بالتفصيل",
    "ابعت", "ابعتلي", "ارسل", "وريني", "قول", "قولي", "احكي",
    "send", "show", "tell", "give",
}


def _resolve_ordinal_reference(current_query: str, last_assistant_text: str) -> Optional[str]:
    """Deterministic fast-path for pure ordinal references ("اه التانيه").

    Resolution priority:
    1. EXPLICIT NUMBER wins: if the list items carry PR numbers (#N) and the
       ordinal value matches one of them, "التاني" means PR #2 — users anchor
       on printed numbers, not positions.
    2. Otherwise positional: the Nth list item in order.
    Returns a standalone instruction carrying the CONCRETE item text — in the
    user's own language. None when not a pure ordinal reference (LLM handles it).
    """
    if not current_query or not last_assistant_text:
        return None
    tokens = re.findall(r"[\w\u0590-\u08FF]+", current_query.strip().lower())
    ordinals = [ORDINAL_MAP[t] for t in tokens if t in ORDINAL_MAP]
    if len(ordinals) != 1:
        return None
    if any(t not in ORDINAL_MAP and t not in ORDINAL_FILLERS for t in tokens):
        return None
    items = []
    for line in last_assistant_text.splitlines():
        m = re.match(r"^\s*(?:[-*•]|\d+[.)])\s+(.+)$", line.strip())
        if m and m.group(1).strip():
            items.append(re.sub(r"\*\*([^*]+)\*\*", r"\1", m.group(1)).strip())
    if not items:
        return None
    numbers = []
    for item in items:
        m = re.search(r"#\s*(\d+)", item)
        numbers.append(int(m.group(1)) if m else None)
    n = ordinals[0]
    if n in numbers:
        item = items[numbers.index(n)]
        explicit = f"PR رقم {n}"
        explicit_en = f"PR #{n}"
    elif 1 <= n <= len(items):
        item = items[n - 1]
        explicit = f"العنصر رقم {n}"
        explicit_en = f"item #{n}"
    else:
        return None
    if not item:
        return None
    if re.search(r"[\u0591-\u07FF\uFB1D-\uFDFD\uFE70-\uFEFC]", current_query):
        return f"المستخدم يقصد {explicit} من ردك الأخير وهو: \"{item}\". هات كل التفاصيل عنه هو فقط."
    return f"The user means {explicit_en} from your last answer: \"{item}\". Give full details about it only."


def _rewrite_context(lang_messages: List[BaseMessage], window: int) -> List[BaseMessage]:
    """Tail of `window` messages, guaranteed to include the latest assistant answer.

    Ordinals ("التانيه"/"second") can only resolve against the assistant's last
    message, so if the plain tail has no assistant message we prepend the most
    recent one. Never invents content — only reuses history.
    """
    tail = list(lang_messages[-window:]) if window else []
    if tail and not any(isinstance(m, AIMessage) for m in tail):
        for m in reversed(lang_messages):
            if isinstance(m, AIMessage):
                tail = [m] + tail
                break
    return tail


class ChatService:
    def __init__(self):
        self.llm = ChatOpenAI(
            base_url=settings.bedrock_base_url_qwen,
            api_key=settings.bedrock_api_key,
            model=settings.bedrock_model,
            temperature=settings.llm_temperature
        )
        self.tools = [get_database_schema, execute_readonly_query, get_current_datetime, web_search, summarize_report]
        self.tools_by_name = {t.name: t for t in self.tools}
        self.llm_with_tools = self.llm.bind_tools(self.tools)
        
        # StateGraph wiring
        workflow = StateGraph(AgentState)
        workflow.add_node("agent", self._agent_step)
        workflow.add_node("tools", self._tools_step)
        
        workflow.set_entry_point("agent")
        workflow.add_conditional_edges("agent", self._should_continue, {
            "tools": "tools",
            "end": END
        })
        workflow.add_edge("tools", "agent")
        self.graph = workflow.compile()

    async def _agent_step(self, state: AgentState) -> Dict[str, Any]:
        messages = list(state["messages"])
        if not messages or not isinstance(messages[0], SystemMessage):
            messages.insert(0, SystemMessage(content=SYSTEM_PROMPT))
        response = await self.llm_with_tools.ainvoke(messages)
        return {"messages": [response]}

    async def _tools_step(self, state: AgentState) -> Dict[str, Any]:
        last_message = state["messages"][-1]
        tool_outputs = []
        if hasattr(last_message, "tool_calls") and last_message.tool_calls:
            for call in last_message.tool_calls:
                tool_name = call["name"]
                tool_args = call.get("args", {})
                call_id = call.get("id")
                
                if tool_name in self.tools_by_name:
                    selected_tool = self.tools_by_name[tool_name]
                    try:
                        if hasattr(selected_tool, "ainvoke"):
                            output = await selected_tool.ainvoke(tool_args)
                        else:
                            output = selected_tool.invoke(tool_args)
                    except Exception as err:
                        output = f"Tool execution error: {err}"
                else:
                    output = f"Tool {tool_name} not found."
                    
                tool_outputs.append(ToolMessage(
                    tool_call_id=call_id,
                    content=str(output),
                    name=tool_name
                ))
        return {"messages": tool_outputs}

    def _should_continue(self, state: AgentState) -> str:
        last_message = state["messages"][-1]
        if hasattr(last_message, "tool_calls") and last_message.tool_calls:
            return "tools"
        return "end"

    async def _rewrite_query(
        self, history_tail: List[BaseMessage], current_query: str
    ) -> str:
        """Rewrite a follow-up question into a standalone one.

        Sends the last `chat_query_rewrite_window_size` messages plus the
        current query to the model. Standalone questions (or empty history)
        come back unchanged; anything failing falls back to the original.
        """
        if not history_tail or not current_query or not current_query.strip():
            return current_query
        # Fast path for standalone ordinals (e.g. "اه التانيه") without an LLM round-trip
        last_answer = next(
            (m.content for m in reversed(history_tail) if isinstance(m, AIMessage)),
            "",
        )
        resolved = _resolve_ordinal_reference(current_query, last_answer or "")
        if resolved:
            return resolved
        try:
            transcript = "\n".join(
                f"{'user' if isinstance(m, HumanMessage) else 'assistant'}: {m.content}"
                for m in history_tail
            )
            response = await self.llm.ainvoke(
                [
                    SystemMessage(content=QUERY_REWRITE_PROMPT),
                    HumanMessage(
                        content=f"<conversation>\n{transcript}\n</conversation>\n"
                        f"<latest_message>\n{current_query}\n</latest_message>"
                    ),
                ]
            )
            rewritten = (response.content or "").strip().strip("\"'")
            return rewritten or current_query
        except Exception as e:
            logger.warning(f"Query rewrite failed, using original: {e}")
            return current_query

    # ---------------- Session & Message DB Operations ---------------- #

    async def list_sessions(self) -> List[Dict[str, Any]]:
        """Fetch all chat sessions ordered by updated_at descending."""
        async with AsyncSessionLocal() as session:
            stmt = select(ChatSession).order_by(ChatSession.updated_at.desc())
            result = await session.execute(stmt)
            sessions = result.scalars().all()
            return [
                {
                    "id": s.id,
                    "title": s.title,
                    "created_at": s.created_at.isoformat() if s.created_at else None,
                    "updated_at": s.updated_at.isoformat() if s.updated_at else None,
                }
                for s in sessions
            ]

    async def create_session(self, title: Optional[str] = None) -> Dict[str, Any]:
        """Create a new chat session."""
        session_id = str(uuid.uuid4())
        initial_title = title or "New Conversation"
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        new_session = ChatSession(id=session_id, title=initial_title, created_at=now, updated_at=now)
        
        async with AsyncSessionLocal() as session:
            session.add(new_session)
            await session.commit()
            await session.refresh(new_session)
            return {
                "id": new_session.id,
                "title": new_session.title,
                "created_at": new_session.created_at.isoformat(),
                "updated_at": new_session.updated_at.isoformat()
            }

    async def get_session_messages(self, session_id: str) -> List[Dict[str, Any]]:
        """Fetch all messages for a specific session."""
        async with AsyncSessionLocal() as session:
            stmt = (
                select(ChatMessage)
                .where(ChatMessage.session_id == session_id)
                .order_by(ChatMessage.id.asc())
            )
            result = await session.execute(stmt)
            messages = result.scalars().all()
            return [
                {
                    "id": m.id,
                    "role": m.role,
                    "content": m.content,
                    "created_at": m.created_at.isoformat() if m.created_at else None
                }
                for m in messages
            ]

    async def delete_session(self, session_id: str) -> bool:
        """Delete a chat session and all its messages."""
        async with AsyncSessionLocal() as session:
            stmt = delete(ChatSession).where(ChatSession.id == session_id)
            res = await session.execute(stmt)
            await session.commit()
            return res.rowcount > 0

    async def send_message(self, session_id: str, user_content: str) -> Dict[str, Any]:
        """Process user message through LangGraph agent and persist interaction."""
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        
        async with AsyncSessionLocal() as db_session:
            sess_stmt = select(ChatSession).where(ChatSession.id == session_id)
            sess_res = await db_session.execute(sess_stmt)
            session_obj = sess_res.scalar_one_or_none()
            if not session_obj:
                session_obj = ChatSession(
                    id=session_id,
                    title=user_content[:40] + ("..." if len(user_content) > 40 else ""),
                    created_at=now,
                    updated_at=now
                )
                db_session.add(session_obj)
                await db_session.commit()
                await db_session.refresh(session_obj)

            # Bounded recent history for short-term memory window
            window_size = max(1, settings.chat_memory_window_size)
            hist_stmt = (
                select(ChatMessage)
                .where(ChatMessage.session_id == session_id)
                .order_by(ChatMessage.id.desc())
                .limit(window_size)
            )
            hist_res = await db_session.execute(hist_stmt)
            history_rows = list(reversed(hist_res.scalars().all()))

            user_msg_db = ChatMessage(session_id=session_id, role="user", content=user_content, created_at=now)
            db_session.add(user_msg_db)
            
            if session_obj.title == "New Conversation" or not session_obj.title:
                clean_title = user_content.strip()[:45]
                session_obj.title = clean_title + ("..." if len(user_content) > 45 else "")
            session_obj.updated_at = now
            await db_session.commit()

        lang_messages: List[BaseMessage] = []
        for m in history_rows:
            if m.role == "user":
                lang_messages.append(HumanMessage(content=m.content))
            elif m.role == "assistant":
                lang_messages.append(AIMessage(content=m.content))

        # Contextual follow-up rewrite; raw message stays in DB, agent sees expanded query
        rewrite_window = max(0, settings.chat_query_rewrite_window_size)
        rewritten_query = await self._rewrite_query(
            _rewrite_context(lang_messages, rewrite_window),
            user_content,
        )

        lang_messages.append(HumanMessage(content=rewritten_query))

        try:
            final_state = await self.graph.ainvoke({"messages": lang_messages})
            final_ai_message = final_state["messages"][-1]
            assistant_reply = final_ai_message.content or "Done."
        except Exception as e:
            logger.error(f"LangGraph execution failed: {e}")
            assistant_reply = f"Apologies, an error occurred while processing your request: {e}"

        async with AsyncSessionLocal() as db_session:
            asst_now = datetime.now(timezone.utc).replace(tzinfo=None)
            asst_msg_db = ChatMessage(session_id=session_id, role="assistant", content=assistant_reply, created_at=asst_now)
            db_session.add(asst_msg_db)
            
            upd_stmt = select(ChatSession).where(ChatSession.id == session_id)
            upd_res = await db_session.execute(upd_stmt)
            curr_sess = upd_res.scalar_one_or_none()
            if curr_sess:
                curr_sess.updated_at = asst_now
            await db_session.commit()

        return {
            "session_id": session_id,
            "reply": assistant_reply,
            "rewritten_query": rewritten_query,
            "created_at": now.isoformat()
        }

chat_service = ChatService()
