import asyncio
import logging
import re
import json
import time
import uuid
from contextvars import ContextVar
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
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

══════════════════════════════════════════════════
 MANDATORY REASONING PROTOCOL (EVERY turn, NO exceptions)
══════════════════════════════════════════════════
BEFORE you write ANY answer about data, follow these steps IN ORDER:

Step 1 — UNDERSTAND: What EXACTLY is the user asking? Parse carefully.
Step 2 — CHECK DATE: Read the [Current time] block at the end of this prompt.
         What is today's date? What date does the question refer to?
         NEVER assume a date from memory — use the [Current time] block.
Step 3 — CHOOSE TOOL: Pick the RIGHT tool (see Tool routing below).
         If the question is about data (PRs, emails, reports, engineers),
         you MUST call a tool FIRST. NEVER answer data questions from memory.
Step 4 — READ RESULT: Look at what the tool ACTUALLY returned.
         If it returned 0 rows, empty, or "no data found", your answer
         MUST reflect that — say "مفيش" / "none" / "0".
Step 5 — ANSWER: State the answer based ONLY on the tool's output.
         Copy identifiers character-for-character. Never add extra data.

══════════════════════════════════════════════════
 CRITICAL ANTI-HALLUCINATION RULES (NEVER violate)
══════════════════════════════════════════════════
• If you haven't called a tool yet, you DON'T KNOW if data exists.
  Call the tool first, then answer.
• 0 rows = "مفيش" / "none found" / "لا".
  NEVER say "there are" / "فيه" / "أيوه" when the tool returned nothing.
  This is the #1 rule — violating it is a critical failure.
• NEVER fabricate, extrapolate, or guess numbers.
  Every single number in your answer must come from a tool result in THIS turn.
• If the tool says "No recorded emails for DATE" →
  your answer MUST be "مفيش ايميلات" / "لا مجالكش ايميل".
  NEVER say "فيه ايميلات" or "أيوه جالك".
• If the tool says "No daily report found for DATE" →
  your answer MUST be "مفيش ريبورت".
  NEVER say "فيه ريبورت" or summarize a non-existent report.
• When in doubt, call the tool AGAIN rather than answering from memory.
• NEVER answer "yes there is data" without a tool confirming it.

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

  4. `emails`:
     - `id` (int), `sender` (str), `subject` (str), `sent_at` (datetime)
     - `summary_text` (text): AI summary of the email
     - `urgency_score` (float): reply-urgency 0 to 10
     - `urgency_tier` (str): 'Reply Now', 'Reply Today', 'FYI / Soon', 'Archive'

  5. `eval_fixtures` (synthetic test data — query ONLY when the user explicitly
     asks about eval/test fixtures by ref (EVAL-PR-03) or by owner name
     (EvalEng_Aria); NEVER mix these rows into real PR/email answers):
     - `id` (int), `kind` (str): 'pr' | 'email' | 'engineer'
     - `ref_name` (str): stable test reference (e.g. 'EVAL-PR-03')
     - `title`, `owner`, `state`, `event_date`, `score`, `tier`, `notes`
     - COLUMN MAP (this table has NO `sender`/`author`/`assignee` columns):
       "who sent / who authored / who owns X" -> SELECT `owner` ... (never `sender`/`author`).
       "urgency / tier / state of X" -> SELECT `tier`, `state` ... (never `notes`).
       Asked by ref (EVAL-PR-03, EVAL-MAIL-01) -> WHERE `ref_name` = '<ref>'.
       Asked by owner name (EvalEng_Aria, eval-boss@...) -> WHERE `owner` = '<name>'.
     - SELF-CORRECT: if a query fails on a column name or returns 0 rows while
       the question names a real-looking ref/owner, RE-QUERY once using only the
       columns above (different column, not a different answer). Never tell the
       user a column is missing, and never declare "does not exist" before that
       retry — an empty first attempt means YOUR query was wrong, not the data.

 Tool routing:
- DB questions (PRs, authors, scores, overdue, reports, emails) -> `execute_readonly_query` (tables: pull_requests, engineers, daily_reports, emails).
- Eval/test questions naming a ref (EVAL-PR-03, EVAL-MAIL-01, EVAL-ENG-02) or an owner name -> `execute_readonly_query` on `eval_fixtures` ONLY (with the column map above).
 - Report summaries by day ("لخص ريبورت النهاردة", "summarize yesterday's report", "فيه ريبورت؟") -> `summarize_report` (NOT SQL — it resolves today/انهارده/dates itself).
 - Emails by day ("جالي ايميل انهارده؟", "emails yesterday", "ايميلات امبارح", "فيه ايميلات؟") -> `recent_emails` (NOT SQL — it resolves the Cairo day itself).
 - Counts/quantities ("كام report؟", "how many X", "عدد") -> ALWAYS `execute_readonly_query` with COUNT(*) FIRST — never a summary/content tool.
 - Multi-step is normal: chain tools across rounds when needed (e.g. get the date FIRST via get_current_datetime, then query) — loop until the evidence answers the question.
- Time/date questions ("الساعة كام", "what time is it") -> `get_current_datetime` (Africa/Cairo).
- General/external questions (news, facts, definitions outside the DB) -> `web_search`.

Guidelines:
- When the user asks about pull requests, authors, stats, overdue items, scores, emails, or repository metrics, ALWAYS use the appropriate tool to inspect the real data before answering. EXCEPTION: emails by day and report summaries by day go to their dedicated tools (`recent_emails` / `summarize_report`), never SQL.
- You can chat casually and offer strategic, architectural, and engineering leadership insights.
- Provide clear, well-formatted markdown responses (tables, bullet points, code blocks where appropriate).
 - Dialect glossary: "متعلقه/متعلقة" about PRs means pending/stuck past SLA (overdue) — NEVER interpret it as related-to. Answer from is_overdue/overdue_days, never from title similarity.
 - Oldest vs latest (general rule, ALL tables): "أقدم/first/oldest" -> ORDER BY <date-col> ASC LIMIT 1; "آخر/latest/most-recent" -> ORDER BY <date-col> DESC LIMIT 1, where date-col is created_at (PRs), sent_at (emails), report_date (reports). NEVER order by id/number for time questions and NEVER invert ASC/DESC — answering "oldest" with the DESC row (or vice versa) is a critical failure.
- Decisiveness: when the tool output contains the answer, state it directly with the numbers — never demur, hedge, or refuse. Refuse ONLY when the data is genuinely absent, and then say exactly what is missing (never invent it).

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
- Directness & Quantities: when asked "how many / total / كام / عدد", state the single computed number FIRST (including 0 when none exist), then optionally the breakdown. Never omit the numeric count or list parts without the total.
- Temporal Scope: Respect the exact requested timeframe (past, present, or future). If a question asks about future dates or periods, recognize that recorded database activity cannot exist in the future, so the count is 0.
- Missing / Non-existent Entities: When a specific record or identifier is queried and not found in the database, state clearly and unequivocally that it does not exist in the records. EXCEPTION on `eval_fixtures`: a 0-row result there first means retry once with the column map (ref_name vs owner, owner vs sender/author, tier vs notes) — only declare "does not exist" if the corrected query is also empty.
- Dialect: "متعلقه/متعلقة" about PRs means pending/stuck past SLA (overdue) — NOT related-to. Answer from is_overdue/overdue_days, never from title similarity.

Language (strict):
- ALWAYS reply in the same language the user used in their latest message.
- If the user writes in Arabic (including Egyptian dialect), reply in Arabic — same dialect when recognizable, otherwise Modern Standard Arabic.
- If the user writes in English, reply in English.
- One reply = one language; do not mix Arabic and English sentences.
- Language mismatch is a critical failure: an English question must NEVER get
  an Arabic reply and vice versa — not even one sentence. Re-read your reply
  and fix the language before sending.
- NEVER translate technical identifiers: keep table/column names, usernames, branch names, URLs, numbers, dates, PR numbers, and code exactly as-is in Latin script (they render isolated via bidi handling on the client).
- Copy every identifier character-for-character from the tool output — never retype from memory. A single wrong letter breaks mentions: SeifMahmoud63 must never become SeifMahdoud63.

Few-shot examples (follow these answer patterns EXACTLY):

Example 1 — Count question:
  User: عندنا كام PR؟
  → Call execute_readonly_query("SELECT COUNT(*) AS c FROM pull_requests")
  → Tool returns: [{"c": 7}]
  → Reply: عندنا 7 PRs.

Example 2 — Filtered count returning zero:
  User: كام PR اتفتح سنة 2020؟
  → Call execute_readonly_query("SELECT COUNT(*) AS c FROM pull_requests WHERE YEAR(created_at) = 2020")
  → Tool returns: [{"c": 0}]
  → Reply: مفيش أي PR اتفتح سنة 2020.

Example 3 — Non-existent entity:
  User: هات تفاصيل PR #999
  → Call execute_readonly_query("SELECT * FROM pull_requests WHERE number = 999")
  → Tool returns: 0 rows returned.
  → Reply: مفيش PR رقم 999 في السيستم.

Example 4 — Detail question:
  User: Who authored PR #3?
  → Call execute_readonly_query("SELECT author FROM pull_requests WHERE number = 3")
  → Tool returns: [{"author": "SeifMahmoud63"}]
  → Reply: PR #3 was authored by SeifMahmoud63.

Example 5 — General knowledge (no tool needed):
  User: What are the 4 DORA metrics?
  → Reply directly (no tool call): The four DORA metrics are: Deployment Frequency, Lead Time for Changes, Change Failure Rate, and Mean Time to Recovery (MTTR).

Example 6 — Email existence check (CRITICAL — anti-hallucination):
  User: جالي ايميل انهارده؟
  → Call recent_emails("today")
  → Tool returns: "No recorded emails for 2026-10-12 (Cairo day)."
  → Reply: لا، مجالكش أي ايميل انهارده.
  ⚠️ WRONG answer: "أيوه جالك ايميل" — this is FABRICATION when the tool said no emails.

Example 7 — Report existence check (CRITICAL — anti-hallucination):
  User: فيه ريبورت النهارده؟
  → Call summarize_report("today")
  → Tool returns: "No daily report found for 2026-10-12. Available report dates: 2026-10-11, 2026-10-10."
  → Reply: لا، مفيش ريبورت النهارده لسه. آخر ريبورت كان يوم 2026-10-11.
  ⚠️ WRONG answer: "أيوه فيه ريبورت" — this is FABRICATION.

Example 8 — Date-aware SQL query:
  User: كام PR اتفتح انهارده؟
  → [Current time says today = 2026-10-12]
  → Call execute_readonly_query("SELECT COUNT(*) AS c FROM pull_requests WHERE DATE(created_at) = '2026-10-12'")
  → Tool returns: [{"c": 0}]
  → Reply: مفيش أي PR اتفتح انهارده.

Example 9 — Email with data:
  User: فيه ايميلات امبارح؟
  → Call recent_emails("yesterday")
  → Tool returns: "Emails for 2026-10-11 (Cairo time) — 2:\n- [2026-10-11 09:15] From boss@company.com: Meeting tomorrow (urgency 6.0 Reply Today)\n- [2026-10-11 14:30] From noreply@github.com: PR review requested (urgency 3.0 FYI / Soon)"
  → Reply: أيوه، جالك 2 ايميلات امبارح:\n- boss@company.com: Meeting tomorrow (urgency: Reply Today)\n- noreply@github.com: PR review requested (urgency: FYI / Soon)

Example 10 — Conversation context awareness:
  User: [after asking about PRs] ومين عمل آخر واحد؟
  → This is a follow-up. Resolve "آخر واحد" from previous context.
  → Call execute_readonly_query with the right PR number from context.
  → Reply with the author from tool output.
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

Time preservation (CRITICAL — dropping a time word answers a DIFFERENT question):
- NEVER drop time/date constraints across past, present, or future (e.g., today, yesterday, tomorrow, this week, next week, انهارده, امبارح, بكرة, اليوم, امس, غداً).
  "عندنا كام PR انهارده؟" MUST keep انهارده — rewriting it to "هات عدد PR"
  is strictly forbidden.
- Bare day-word + "كام" with NO countable noun ("وانهارده كام؟", "وامبارح كام؟")
  ALWAYS means "what DATE is that day" — rewrite as "انهارده تاريخ كام؟" /
  "امبارح تاريخ كام؟" (same language). Never leave them bare: a bare "كام؟"
  makes the agent ask a clarifying question instead of answering.
  (With a countable noun — "عندنا كام PR انهارده؟", "الساعة كام؟" — keep as-is.)
- If the latest message is already standalone and complete, return it EXACTLY
  as-is: copy it character-for-character, do NOT paraphrase or shorten it.

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

# eval_fixtures self-healing (general, deterministic, zero production impact).
# The LLM sometimes queries the synthetic table with a real-table column
# (sender/author/assignee/subject/created_at) or with the wrong key
# (ref_name='EvalEng_Cora' instead of owner='EvalEng_Cora'). Prompt retry
# instructions are probabilistic, so the tool itself normalizes + retries —
# gated STRICTLY to `eval_fixtures` (real tables never touched) and ONLY on
# the failure paths (unknown-column error or 0 rows). A successful first
# query returns byte-identically to before.
_EVAL_TABLE_RE = re.compile(r"\beval_fixtures\b", re.IGNORECASE)
_EVAL_WHERE_RE = re.compile(r"\bWHERE\b", re.IGNORECASE)
# Quoted literal splitter: replacements apply outside '...' / "..." only,
# so a value like 'EvalEng_Cora' is never corrupted into 'EvalEng_Cowner'.
_EVAL_QUOTE_SPLIT_RE = re.compile(r"('(?:[^']|'')*'|\"(?:[^\"]|\"\")*\")")
_EVAL_COLUMN_MAP = (
    ("assignee", "owner"),
    ("sender", "owner"),
    ("author", "owner"),
    ("subject", "title"),
    ("created_at", "event_date"),
    ("updated_at", "event_date"),
    ("sent_at", "event_date"),
)


def _is_eval_query(sql: str) -> bool:
    return bool(_EVAL_TABLE_RE.search(sql or ""))


def _replace_ident_outside_literals(sql: str, old: str, new: str) -> str:
    """Whole-word identifier swap outside string literals (backticks kept)."""
    pat = re.compile(r"`?\b%s\b`?" % re.escape(old), re.IGNORECASE)

    def _sub(m):
        s = m.group(0)
        if s[:1] == "`" and s[-1:] == "`":
            return "`%s`" % new
        return new

    parts = _EVAL_QUOTE_SPLIT_RE.split(sql)
    for i in range(0, len(parts), 2):
        parts[i] = pat.sub(_sub, parts[i])
    return "".join(parts)


def _normalize_eval_columns(sql: str) -> str:
    # Defense in depth: never touch real tables even if a future caller
    # forgets the gate — the map applies to the synthetic table only.
    if not _is_eval_query(sql):
        return sql
    for old, new in _EVAL_COLUMN_MAP:
        sql = _replace_ident_outside_literals(sql, old, new)
    return sql


def _swap_eval_key_variant(sql: str, frm: str, to: str) -> Optional[str]:
    """Swap one key column inside the WHERE clause only (SELECT shape kept)."""
    m = _EVAL_WHERE_RE.search(sql)
    if not m:
        return None
    head, tail = sql[:m.start()], sql[m.start():]
    swapped = _replace_ident_outside_literals(tail, frm, to)
    return head + swapped if swapped != tail else None


def _serialize_eval_rows(rows) -> str:
    serializable_rows = []
    for row in rows[:50]:  # safety cap at 50 rows
        row_dict = {}
        for k, v in row.items():
            row_dict[k] = _json_safe(v)
        serializable_rows.append(row_dict)
    return json.dumps(serializable_rows, indent=2, ensure_ascii=False)


def _message_text(msg: Any) -> str:
    """Plain text from a message whose content may be str or blocks.

    Some providers (Gemini native SDK) return AIMessage content as a LIST of
    blocks (text / thinking / function parts). Every downstream consumer
    (gate regexes, judge prompt, DB persist, SSE) needs a plain string —
    thinking blocks are deliberately skipped, never leaked to the user.
    """
    content = getattr(msg, "content", "")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, str):
                parts.append(block)
            elif isinstance(block, dict):
                for key in ("text", "content"):
                    val = block.get(key)
                    if isinstance(val, str):
                        parts.append(val)
                        break
        return "".join(parts)
    return str(content or "")


def _json_safe(value):
    """Coerce one DB cell into something json.dumps accepts.

    MySQL returns Decimal for SUM/AVG (and date objects for DATE columns);
    without this the whole tool call collapses into "Database Error".
    Mirrored in voice_service (same guard style as FORBIDDEN_SQL_PATTERN).
    """
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (bytes, bytearray)):
        return bytes(value).decode("utf-8", errors="replace")
    return value

@tool
def get_database_schema() -> str:
    """Returns the names and schemas of all available database tables."""
    return (
        "Tables:\n"
        "- pull_requests (id, github_pr_id, number, title, author, author_avatar, state, head_branch, base_branch, html_url, diff_url, created_at, updated_at, is_overdue, overdue_days, summary_text, summary_provider, summary_timestamp, impact_score, impact_tier)\n"
        "- engineers (id, author, author_avatar, pr_count, total_score, avg_score, tier, updated_at)\n"
        "- daily_reports (id, report_date, title, executive_summary, prs_opened, prs_merged, prs_closed, overdue_count, pdf_path, created_at)\n"
        "- emails (id, message_id, sender, subject, sent_at, snippet, summary_text, summary_provider, urgency_score, urgency_tier, created_at)\n"
        "- eval_fixtures (id, kind, ref_name, title, owner, state, event_date, score, tier, notes) — synthetic test rows, query only when asked by ref\n"
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

    is_eval = _is_eval_query(clean_sql)
    exec_sql = _normalize_eval_columns(clean_sql) if is_eval else clean_sql

    try:
        async with AsyncSessionLocal() as session:
            await session.execute(text("SET TRANSACTION READ ONLY"))

            async def _fetch(q: str):
                result = await session.execute(text(q))
                return result.mappings().all()

            try:
                rows = await _fetch(exec_sql)
            except Exception as e:
                # Never leak DB internals to the model/user — full detail goes to logs only.
                logger.error(f"SQL execution error for '{exec_sql}': {e}", exc_info=True)
                return "Error"

            if rows:
                return _serialize_eval_rows(rows)

            # 0 rows on the synthetic table: the key was almost certainly
            # swapped (ref_name <-> owner). Retry each direction once, first
            # non-empty result wins; otherwise report the original empty.
            if is_eval:
                for frm, to in (("ref_name", "owner"), ("owner", "ref_name")):
                    variant = _swap_eval_key_variant(exec_sql, frm, to)
                    if not variant or variant == exec_sql:
                        continue
                    try:
                        retry_rows = await _fetch(variant)
                    except Exception:
                        continue
                    if retry_rows:
                        logger.info(
                            "eval_fixtures key auto-corrected (%s -> %s).", frm, to)
                        return _serialize_eval_rows(retry_rows)
            return "Query executed successfully. Result: 0 rows returned."
    except Exception as e:
        logger.error(f"SQL execution error for '{exec_sql}': {e}", exc_info=True)
        return "Error"

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
        "yesterday": (now.date() - timedelta(days=1)).isoformat(),
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

# Time markers that must survive a query rewrite: dropping them changes the
# question ("andana kam PR inhardah?" -> "hat adad PR" is a DIFFERENT question).
# Token-based matching (not substring) so "now" never matches "know".
TIME_MARKER_TOKENS = set(TODAY_WORDS) | set(YESTERDAY_WORDS) | {
    "week", "month", "year", "الأسبوع", "الاسبوع", "الشهر", "شهر",
    "السنة", "السنه", "سنة", "سنه",
}
TIME_MARKER_PHRASES = ("this week", "this month", "this year")


def _has_time_marker(text: str) -> bool:
    """True if the text carries an explicit time/date constraint."""
    if not text:
        return False
    lowered = text.strip().lower()
    # \w = Unicode letters/digits/underscore only — Arabic punctuation (U+061F "?", U+060C ",")
    # must NOT glue itself to the word ("inhardah?" -> "inhardah").
    tokens = set(re.findall(r"\w+", lowered))
    if tokens & TIME_MARKER_TOKENS:
        return True
    return any(p in lowered for p in TIME_MARKER_PHRASES)


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


def _utc_naive_to_cairo_str(iso_val: Optional[str]) -> str:
    """Stored naive-UTC timestamp -> 'YYYY-MM-DD HH:MM' Cairo wall time.

    Displayed everywhere humans read times, so nobody does mental +2/+3 math
    (and DST changes can't silently shift every answer twice a year).
    Falls back to the raw value when unparseable.
    """
    if not iso_val:
        return "?"
    try:
        from zoneinfo import ZoneInfo

        dt = datetime.fromisoformat(str(iso_val))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(ZoneInfo(CAIRO_TZ)).strftime("%Y-%m-%d %H:%M")
    except Exception:
        return str(iso_val)


@tool
async def recent_emails(day_ref: str) -> str:
    """List triaged emails received on one calendar day (Cairo time).

    `day_ref` accepts: 'today'/'انهارده', 'yesterday'/'امبارح',
    'YYYY-MM-DD', 'DD/MM/YYYY', or 'DD month [YYYY]' (Arabic or English).
    Use this (NOT SQL) whenever the user asks about emails by day
    ("جالي ايميل انهارده؟", "emails yesterday") — it resolves the Cairo day
    itself and matches stored UTC timestamps DST-correctly.
    """
    from zoneinfo import ZoneInfo

    from app.services.db_service import db_service

    try:
        today = datetime.now(ZoneInfo(CAIRO_TZ)).date()
    except Exception:
        today = datetime.now(timezone.utc).date()
    day = parse_report_date(day_ref, today)
    if day is None:
        return (
            "Could not understand that date. Ask for 'today'/'انهارده', "
            "'yesterday'/'امبارح', 'YYYY-MM-DD', or e.g. '12 أكتوبر 2026'."
        )
    try:
        recs = await db_service.get_emails_for_day(day.isoformat())
        if not recs:
            hint = (" If more were expected, press Sync Inbox "
                    "— the inbox may not have been polled yet.")
            return (f"No recorded emails for {day.isoformat()} (Cairo day)." +
                    (hint if day == today else ""))
        lines = [f"Emails for {day.isoformat()} (Cairo time). "
                 f"Total: {len(recs)} / العدد: {len(recs)}:"]
        for r in recs[:10]:
            when = _utc_naive_to_cairo_str(r.get("sent_at"))
            score = r.get("urgency_score")
            score_s = ("%.1f" % score) if isinstance(score, (int, float)) else "?"
            lines.append(
                f"- [{when}] From {r.get('sender') or 'unknown'}: "
                f"{r.get('subject') or '(no subject)'} "
                f"(الأهمية / urgency {score_s} {r.get('urgency_tier') or ''})".rstrip())
        if len(recs) > 10:
            lines.append(f"…and {len(recs) - 10} more.")
        return "\n".join(lines)
    except Exception as e:
        logger.warning(f"Recent emails failed for '{day_ref}': {e}")
        return "Could not load those emails right now."


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


def _rewrite_context(lang_messages: List[BaseMessage], window: int) -> List[BaseMessage]:
    """Tail of `window` messages, guaranteed to include the latest assistant answer.

    Follow-ups ("من مين؟"/"and its author?") can only resolve against the
    assistant's last message, so if the plain tail has no assistant message we
    prepend the most recent one. Never invents content — only reuses history.
    """
    tail = list(lang_messages[-window:]) if window else []
    if tail and not any(isinstance(m, AIMessage) for m in tail):
        for m in reversed(lang_messages):
            if isinstance(m, AIMessage):
                tail = [m] + tail
                break
    return tail


_token_tap: ContextVar[Optional["_TokenTap"]] = ContextVar(
    "chat_token_tap", default=None
)


class _TokenTap:
    """Per-turn token tap: streams the bound LLM internally, forwards text.

    Installed via the `_token_tap` ContextVar for exactly one turn, so the
    LangGraph path (agent -> tools -> judge -> retry) runs UNCHANGED — only
    the raw LLM call inside `_agent_step` switches from `ainvoke` to
    `astream`, and the assembled message returned is identical.

    Records turn-level TTFT (time-to-first-token, seconds from turn entry to
    the first LLM token — including history load, query rewrite and tool
    calls before it, i.e. exactly what SSE streaming hides from the user)
    into `holder["ttft_s"]`, and optionally forwards text deltas to a sync
    `on_token` callback (SSE chat live feed).

    Never raises: any streaming failure falls back to a plain `ainvoke`
    (ttft stays None, correctness preserved).
    """

    def __init__(self, llm, on_token=None, holder=None, t0=None):
        self._llm = llm
        self._on_token = on_token
        self._holder = holder if holder is not None else {}
        self._t0 = t0 if t0 is not None else time.perf_counter()

    @staticmethod
    def _text_of(chunk) -> str:
        content = getattr(chunk, "content", "")
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            parts = []
            for block in content:
                if isinstance(block, str):
                    parts.append(block)
                elif isinstance(block, dict):
                    text = block.get("text") or block.get("content") or ""
                    if isinstance(text, str):
                        parts.append(text)
            return "".join(parts)
        return ""

    async def ainvoke(self, messages):
        full = None
        try:
            async for chunk in self._llm.astream(messages):
                full = chunk if full is None else full + chunk
                text = self._text_of(chunk)
                if text:
                    if self._holder.get("ttft_s") is None:
                        self._holder["ttft_s"] = round(
                            time.perf_counter() - self._t0, 2)
                    if self._on_token is not None:
                        try:
                            self._on_token(text)
                        except Exception:
                            pass
            if full is None:
                raise ValueError("empty LLM stream")
            return full
        except Exception as e:
            logger.warning(f"Token-tap stream failed, falling back to invoke: {e}")
            if full is not None and self._text_of(full):
                return full
            return await self._llm.ainvoke(messages)


def _current_time_context() -> str:
    """Current Cairo wall-clock, injected into every agent turn.

    Without this the model answers date questions ("wa-inhardah kam?", "what date is today") from
    training memory (stale year 2023) instead of calling a tool — and no
    judge gate catches it, because dateless prose has no PR refs to verify.
    Deterministic per turn and DST-aware via ZoneInfo: no external calendar
    API needed, the server clock is already the right source.
    """
    try:
        from zoneinfo import ZoneInfo

        now = datetime.now(ZoneInfo(CAIRO_TZ))
    except Exception:
        now = datetime.now(timezone.utc)
    return (
        "[Current time: %s (%s, %s). Today is %s, yesterday was %s. "
        "Use this for ALL relative dates (انهارده/امبارح/today/yesterday) "
        "and never state a date from memory.]"
        % (now.strftime("%Y-%m-%d %H:%M"), now.strftime("%A"), CAIRO_TZ,
           now.date().isoformat(),
           (now.date() - timedelta(days=1)).isoformat())
    )


def _build_system_message() -> SystemMessage:
    """System prompt + fresh timestamp (message[0] of every turn)."""
    return SystemMessage(content=SYSTEM_PROMPT + "\n\n" + _current_time_context())


# ReAct loop cap: max LangGraph steps per model call (agent->tools->agent is
# 2 steps, so ~5-6 full tool rounds). The library default (25) is needlessly
# high for our tools; an explicit bound keeps runaway loops impossible while
# multi-step chaining (date first, then query) stays fully allowed.
REACT_MAX_STEPS = 12

PREV_OBS_MARK = "[PREVIOUS TURN DATA]"
_PREV_OBS_SESSION_CAP = 100

# One reply = one language (mirrors the eval language_rate rule). Short
# replies (identifiers, "Done.") are exempt — there is nothing to mismatch.
AR_SCRIPT_RE = re.compile(r"[\u0600-\u06FF]")


def _language_mismatch(user_content: str, reply: str) -> Optional[str]:
    """'English'/'Arabic' when the reply breaks the one-language rule."""
    if not reply or len(reply) < 10:
        return None
    want_ar = bool(AR_SCRIPT_RE.search(user_content or ""))
    has_ar = bool(AR_SCRIPT_RE.search(reply))
    if not want_ar and has_ar:
        return "English"
    if want_ar and not has_ar and len(reply) > 20:
        return "Arabic"
    return None


def _prev_obs_context(prev_obs: List[str]) -> str:
    """Labelled previous-turn evidence for follow-up questions."""
    joined = "\n".join(prev_obs or [])[:4000]
    return (
        f"{PREV_OBS_MARK} — verified tool outputs from the previous turn in "
        f"this conversation. You MAY reuse these facts directly (no re-query "
        f"needed). Anything NOT listed here still requires a fresh tool call.\n"
        f"{joined}"
    )


def _tool_call_texts(state: Any) -> List[str]:
    """This turn's tool-call ARGUMENTS as strings (SQL text, day refs...).

    Grounding evidence alongside outputs: `WHERE number = 5` proves PR #5
    was fetched even when the SELECT list omits the key.
    """
    out: List[str] = []
    try:
        msgs = state.get("messages", []) if isinstance(state, dict) else []
        for m in msgs:
            for call in (getattr(m, "tool_calls", None) or []):
                try:
                    out.append(json.dumps(call.get("args", {}), ensure_ascii=False))
                except Exception:
                    out.append(str(call.get("args", "")))
    except Exception:
        pass
    return out


class ChatService:
    def __init__(self):
        # reasoning_effort=low cuts thinking tokens on reasoning models
        # (measured ~3x faster, quality intact); empty = endpoint default.
        # Bedrock path only — Gemini uses its own thinking defaults.
        _effort = (settings.llm_reasoning_effort or "").strip().lower()
        _extra = {"reasoning_effort": _effort} if _effort in ("low", "medium", "high") else None
        # Chatbot backend switch (CHAT_PROVIDER): "gemini" serves chat via the
        # Gemini native SDK with Bedrock as circuit-breaker fallback; anything
        # else stays on Bedrock directly.
        # Judge, summaries and voice are untouched by this switch.
        # Missing-key failsafe: never crash the boot when gemini is selected
        # without a key (e.g. stale container env) — fall back to Bedrock.
        _provider = (settings.chat_provider or "").strip().lower()
        if _provider == "gemini" and not (settings.gemini_api_key or "").strip():
            logger.warning(
                "CHAT_PROVIDER=gemini but GEMINI_API_KEY is empty — falling back to Bedrock.")
            _provider = "bedrock"

        def _bedrock_llm():
            _kwargs = dict(
                base_url=settings.bedrock_base_url_qwen,
                api_key=settings.bedrock_api_key,
                model=settings.bedrock_model,
                temperature=settings.llm_temperature,
            )
            if _extra is not None:
                _kwargs["extra_body"] = _extra
            return ChatOpenAI(**_kwargs)

        # Always build the Bedrock client: it is the Gemini fallback path.
        self._bedrock_llm = _bedrock_llm()
        self._bedrock_with_tools = None
        self._gemini_llm = None
        self._gemini_with_tools = None
        self._chat_use_gemini = False

        if _provider == "gemini":
            # Native GenAI SDK (NOT the OpenAI-compatible endpoint): Gemini 3
            # requires thought_signature round-tripping for tool calls, which
            # the OpenAI-compat layer drops -> hard 400s. The official SDK
            # handles signatures automatically.
            try:
                from langchain_google_genai import ChatGoogleGenerativeAI

                self._gemini_llm = ChatGoogleGenerativeAI(
                    model=settings.gemini_chat_model,
                    google_api_key=settings.gemini_api_key,
                    temperature=settings.llm_temperature,
                )
                self._chat_use_gemini = True
            except Exception as e:
                logger.warning(
                    "Gemini native client unavailable — falling back to Bedrock.",
                    exc_info=True)
                self._gemini_llm = None
                self._chat_use_gemini = False

        self.tools = [get_database_schema, execute_readonly_query, get_current_datetime, web_search, summarize_report, recent_emails]
        self.tools_by_name = {t.name: t for t in self.tools}
        if self._gemini_llm is not None:
            self._gemini_with_tools = self._gemini_llm.bind_tools(self.tools)
        self._bedrock_with_tools = self._bedrock_llm.bind_tools(self.tools)

        # Back-compat: self.llm / self.llm_with_tools always point at the
        # currently-preferred backend (Gemini when enabled, else Bedrock).
        if self._chat_use_gemini and self._gemini_with_tools is not None:
            self.llm = self._gemini_llm
            self.llm_with_tools = self._gemini_with_tools
        else:
            self.llm = self._bedrock_llm
            self.llm_with_tools = self._bedrock_with_tools

        # Model actually serving the current turn (settings value, never
        # hardcoded) — updated on every backend switch for per-turn logging.
        self._current_model = (
            settings.gemini_chat_model
            if (self._chat_use_gemini and self._gemini_with_tools is not None)
            else settings.bedrock_model
        )
        # Important-only boot line: which backend + which .env model is live.
        if self._chat_use_gemini:
            logger.info(
                "Chat backend: gemini primary (model '%s') with bedrock fallback (model '%s').",
                settings.gemini_chat_model, settings.bedrock_model)
        else:
            logger.info(
                "Chat backend: bedrock (model '%s').", settings.bedrock_model)
        # Previous-turn verified tool outputs per session (chat awareness for
        # follow-ups). In-memory, capped; chat is served by this process.
        self._prev_obs: Dict[str, List[str]] = {}
        
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

    def _first_backend_for_turn(self) -> str:
        """'gemini' or 'bedrock' — honors the chat circuit breaker.

        OPEN means Gemini is cooling down: go straight to Bedrock (the
        fallback model from .env) without touching Gemini. CLOSED/HALF_OPEN
        means Gemini may be attempted (the attempt itself is the probe).
        """
        if not getattr(self, "_chat_use_gemini", False) or getattr(
                self, "_gemini_with_tools", None) is None:
            return "bedrock"
        from app.services.circuit_breaker import chat_circuit_breaker

        if not chat_circuit_breaker.can_attempt_primary():
            return "bedrock"
        return "gemini"

    async def _agent_step(self, state: AgentState) -> Dict[str, Any]:
        from app.services.circuit_breaker import chat_circuit_breaker

        messages = list(state["messages"])
        if (not messages or not isinstance(messages[0], SystemMessage)
                or PREV_OBS_MARK in messages[0].content):
            # Previous-turn data may sit at [0]; the base prompt always leads.
            messages.insert(0, _build_system_message())

        # Backend order: Gemini first when the breaker allows it, else
        # straight to Bedrock. A Gemini failure trips the breaker and retries
        # the SAME step on Bedrock — the user never sees the error.
        # getattr defaults keep bare test doubles (llm only) working.
        _use_gemini = getattr(self, "_chat_use_gemini", False)
        _gem_with = getattr(self, "_gemini_with_tools", None)
        _bed_with = getattr(self, "_bedrock_with_tools", None)
        _legacy_with = getattr(self, "llm_with_tools", None)
        if _use_gemini and _gem_with is not None:
            if chat_circuit_breaker.can_attempt_primary():
                order = ["gemini", "bedrock"]
            else:
                order = ["bedrock"]
        elif _bed_with is not None or _gem_with is not None:
            order = ["bedrock"]
        elif _legacy_with is not None:
            order = ["legacy"]
        else:
            order = ["bedrock"]

        last_err: Optional[Exception] = None
        for idx, backend in enumerate(order):
            if backend == "gemini":
                bound = _gem_with
                model_name = settings.gemini_chat_model
            elif backend == "legacy":
                bound = _legacy_with
                model_name = getattr(settings, "gemini_chat_model", "test-model")
            else:
                bound = _bed_with if _bed_with is not None else _legacy_with
                model_name = settings.bedrock_model
            if bound is None:
                continue
            try:
                tap = _token_tap.get()
                if tap is not None and idx == 0:
                    # Streamed turn: the tap was built for this backend in
                    # _run_turn, so its tokens flow live to the client.
                    response = await tap.ainvoke(messages)
                else:
                    response = await bound.ainvoke(messages)
                if backend == "gemini" and _use_gemini:
                    chat_circuit_breaker.record_primary_success()
                try:
                    self._current_model = model_name
                except Exception:
                    pass
                return {"messages": [response]}
            except Exception as e:
                last_err = e
                if backend == "gemini":
                    chat_circuit_breaker.record_primary_failure(e)
                    logger.warning(
                        "Gemini model '%s' failed, falling back to Bedrock model '%s' "
                        "via circuit breaker (state=%s).",
                        settings.gemini_chat_model, settings.bedrock_model,
                        chat_circuit_breaker.state.value)
                    continue
                logger.error(
                    "Chat model '%s' failed.", model_name, exc_info=True)
                raise
        assert last_err is not None
        raise last_err

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
                        # Tool internals stay in logs; the model/user see "Error" only.
                        logger.error(
                            f"Tool '{tool_name}' execution failed.", exc_info=True)
                        output = "Error"
                else:
                    logger.warning(f"Tool {tool_name} not found.")
                    output = "Error"
                    
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

    async def _generate_with_judge(
        self, lang_messages: List[BaseMessage], user_content: str,
        prev_obs: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Run the agent, verify grounding via the judge, retry once, else fallback.

        Intent-aware: the JEV-based intent classifier decides whether to run
        the full judge pipeline ('data' queries) or just the deterministic
        gate ('general' queries — smalltalk, definitions, advice).

        `prev_obs` carries the previous turn's VERIFIED tool outputs, so
        follow-ups ("men mein?", "from whom?") stay grounded without forcing a redundant
        re-query every turn. The gate sees previous + current evidence.

        Returns {"reply": ..., "verdict": PASS | PASS_AFTER_RETRY | FALLBACK,
        "obs": [...]}. Raises only when the agent itself crashes (handled by
        the caller).
        """
        from app.services.judge_service import judge_service

        def _observations(state: Any) -> List[str]:
            try:
                return [
                    str(m.content)
                    for m in (state.get("messages", []) if isinstance(state, dict) else [])
                    if isinstance(m, ToolMessage)
                ]
            except Exception:
                return []

        messages = list(lang_messages)
        if prev_obs:
            messages.insert(0, SystemMessage(
                content=_prev_obs_context(prev_obs)))

        # Step 0: classify intent via JEV (model-based, not regex)
        intent = await judge_service.classify_query_intent_jev(user_content)
        logger.info(f"Query intent classified as '{intent}' for: {user_content[:80]}")

        try:
            final_state = await self.graph.ainvoke(
                {"messages": messages}, config={"recursion_limit": REACT_MAX_STEPS})
        except Exception as e:
            if "recursion" in type(e).__name__.lower() or "recursion" in str(e).lower():
                logger.warning(f"ReAct loop hit max steps ({REACT_MAX_STEPS}); using safe fallback.")
                return {"reply": judge_service.safe_fallback(user_content),
                        "verdict": "FALLBACK", "obs": []}
            raise
        msgs = final_state.get("messages", []) if isinstance(final_state, dict) else []
        reply = (_message_text(msgs[-1]) if msgs else "") or "Done."

        # Step 0.5: For data queries, verify the agent actually called a tool.
        # If it answered from memory without calling any tool, force a retry
        # with explicit tool-call instruction.
        obs = _observations(final_state)
        calls = _tool_call_texts(final_state)
        gate_obs = list(prev_obs or []) + obs
        if intent == "data" and not obs and not prev_obs:
            logger.warning("Data query answered without any tool call — forcing tool-call retry.")
            force_nudge = (
                "[SYSTEM OVERRIDE] Your previous answer was rejected because you "
                "answered a DATA question without calling any tool. This is "
                "FORBIDDEN. You MUST call the appropriate tool (execute_readonly_query, "
                "recent_emails, or summarize_report) FIRST, then answer ONLY from "
                "its output. If the tool returns 0 rows or 'no data', say so clearly. "
                "NEVER say data exists without a tool confirming it.\n\n"
                f"Original question: {user_content}"
            )
            try:
                retry_state = await self.graph.ainvoke(
                    {"messages": messages + [HumanMessage(content=force_nudge)]},
                    config={"recursion_limit": REACT_MAX_STEPS},
                )
                retry_msgs = retry_state.get("messages", []) if isinstance(retry_state, dict) else []
                reply = (_message_text(retry_msgs[-1]) if retry_msgs else "") or "Done."
                obs = _observations(retry_state)
                calls = _tool_call_texts(retry_state)
                gate_obs = list(prev_obs or []) + obs
                final_state = retry_state
            except Exception as e:
                logger.error(f"Forced tool-call retry failed: {e}")

        # Step 1: For general queries, only run deterministic gate (fast, no LLM)
        if intent == "general":
            gate = judge_service.deterministic_gate(
                reply, gate_obs,
                await judge_service._author_roster(),
                user_content=user_content,
                tool_calls=calls,
            )
            if gate["verdict"] == "FAIL":
                logger.warning(f"Deterministic gate caught fabrication in general query: {gate['reason']}")
                return {"reply": judge_service.safe_fallback(user_content),
                        "verdict": "FALLBACK", "obs": obs}
            return await self._ensure_language(
                messages, user_content, reply, "PASS", obs)

        # Step 2: Data queries — full judge pipeline
        verdict = await judge_service.review(user_content, reply, gate_obs, tool_calls=calls)
        if verdict.get("verdict") == "PASS":
            return await self._ensure_language(
                messages, user_content, reply, "PASS", obs)

        logger.warning(f"Judge rejected reply ({verdict.get('reason')}); retrying with surgical nudge.")
        nudge = judge_service.retry_nudge(
            user_content, reply, gate_obs, verdict
        )
        try:
            retry_state = await self.graph.ainvoke(
                {"messages": messages + [HumanMessage(content=nudge)]},
                config={"recursion_limit": REACT_MAX_STEPS},
            )
            retry_msgs = retry_state.get("messages", []) if isinstance(retry_state, dict) else []
            retry_reply = (_message_text(retry_msgs[-1]) if retry_msgs else "") or "Done."
            retry_obs = _observations(retry_state)
            retry_calls = _tool_call_texts(retry_state)
            verdict2 = await judge_service.review(
                user_content, retry_reply, list(prev_obs or []) + retry_obs,
                tool_calls=retry_calls,
            )
            if verdict2.get("verdict") == "PASS":
                return {"reply": retry_reply, "verdict": "PASS_AFTER_RETRY", "obs": retry_obs}
            logger.warning(
                f"Judge rejected retry ({verdict2.get('reason')}); using safe fallback."
            )
        except Exception as e:
            logger.error(f"Grounded retry failed: {e}")
        return {"reply": judge_service.safe_fallback(user_content),
                "verdict": "FALLBACK", "obs": obs}

    async def _ensure_language(
        self, messages: List[BaseMessage], user_content: str,
        reply: str, verdict: str, obs: List[str],
    ) -> Dict[str, Any]:
        """One last deterministic pass: reply must match the user's language.

        A language mismatch triggers exactly ONE restatement round (facts
        frozen by instruction). If it still mismatches, the ORIGINAL reply
        stands — a correct answer in the wrong language beats a fallback.
        """
        from app.services.judge_service import judge_service

        need = _language_mismatch(user_content, reply)
        if not need:
            return {"reply": reply, "verdict": verdict, "obs": obs}
        logger.warning(f"Language mismatch (need {need}) — restating once.")
        nudge = (
            f"[LANGUAGE OVERRIDE] Restate your previous answer in {need} ONLY "
            f"(one language, no mixed sentences), keeping every fact, number "
            f"and name character-for-character identical. Do not add or drop "
            f"any information.\n\nOriginal question: {user_content}"
        )
        try:
            st = await self.graph.ainvoke(
                {"messages": list(messages) + [HumanMessage(content=nudge)]},
                config={"recursion_limit": REACT_MAX_STEPS},
            )
            msgs = st.get("messages", []) if isinstance(st, dict) else []
            retry_reply = (_message_text(msgs[-1]) if msgs else "") or ""
            if retry_reply and not _language_mismatch(user_content, retry_reply):
                return {"reply": retry_reply, "verdict": "PASS_AFTER_RETRY",
                        "obs": obs}
            logger.warning("Language restatement still mismatched; keeping original.")
        except Exception as e:
            logger.error(f"Language restatement failed: {e}")
        return {"reply": reply, "verdict": verdict, "obs": obs}

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
        transcript = "\n".join(
            f"{'user' if isinstance(m, HumanMessage) else 'assistant'}: {_message_text(m)}"
            for m in history_tail
        )
        rewrite_messages = [
            SystemMessage(content=QUERY_REWRITE_PROMPT),
            HumanMessage(
                content=f"<conversation>\n{transcript}\n</conversation>\n"
                f"<latest_message>\n{current_query}\n</latest_message>"
            ),
        ]
        # Gemini first, Bedrock on failure (same circuit breaker as chat).
        # Model names come from settings (.env), never hardcoded.
        # getattr defaults keep bare test doubles (llm only) working.
        candidates = []
        _gem = getattr(self, "_gemini_llm", None)
        _bed = getattr(self, "_bedrock_llm", None)
        _legacy = getattr(self, "llm", None)
        if getattr(self, "_chat_use_gemini", False) and _gem is not None:
            candidates.append(("gemini", _gem, settings.gemini_chat_model))
        if _bed is not None:
            candidates.append(("bedrock", _bed, settings.bedrock_model))
        if not candidates and _legacy is not None:
            candidates.append(("legacy", _legacy, "test-model"))
        last_err: Optional[Exception] = None
        for name, llm, model_name in candidates:
            try:
                response = await llm.ainvoke(rewrite_messages)
                rewritten = ((_message_text(response)) or "").strip().strip("\"'")
                if not rewritten:
                    return current_query
                # Guard: the rewrite must not silently drop time constraints —
                # the original standalone question is always safe for the agent.
                if _has_time_marker(current_query) and not _has_time_marker(rewritten):
                    logger.warning(
                        "Rewrite dropped time constraint; keeping original query."
                    )
                    return current_query
                return rewritten
            except Exception as e:
                last_err = e
                if name == "gemini":
                    from app.services.circuit_breaker import chat_circuit_breaker

                    chat_circuit_breaker.record_primary_failure(e)
                    logger.warning(
                        "Query rewrite via Gemini model '%s' failed, falling back to "
                        "Bedrock model '%s' via circuit breaker (state=%s).",
                        settings.gemini_chat_model, settings.bedrock_model,
                        chat_circuit_breaker.state.value)
                    continue
                logger.warning("Query rewrite failed, using original.", exc_info=True)
                return current_query
        logger.warning("Query rewrite failed, using original.", exc_info=True)
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

    def _remember_obs(self, session_id: str, obs: List[str]) -> None:
        """Store this turn's tool outputs for the next turn's follow-ups."""
        try:
            store = getattr(self, "_prev_obs", None)
            if store is None:
                self._prev_obs = store = {}
            if obs:
                store[session_id] = [str(o)[:2000] for o in obs][:5]
            else:
                store.pop(session_id, None)
            while len(store) > _PREV_OBS_SESSION_CAP:
                store.pop(next(iter(store)))
        except Exception:
            pass

    async def _run_turn(self, session_id: str, user_content: str,
                      on_token=None) -> Dict[str, Any]:
        """Shared single-turn pipeline: prepare -> generate+judge -> persist.

        Returns {"session_id", "reply", "verdict", "ttft_s", "latency_s",
        "rewritten_query", "created_at"}. When `on_token` is given,
        first-pass (and retry) tokens stream to it live; otherwise the turn
        still records TTFT silently (used by `send_message` + Eval Lab).
        """
        t0 = time.perf_counter()
        holder: Dict[str, Any] = {"ttft_s": None}
        now = datetime.now(timezone.utc).replace(tzinfo=None)

        # Pick the backend for this turn BEFORE the tap is built, so streamed
        # tokens and the graph steps use the same LLM. Model names come from
        # settings (.env) — never hardcoded.
        try:
            first_backend = self._first_backend_for_turn()
        except Exception:
            first_backend = "bedrock"
        if first_backend == "gemini":
            self._current_model = settings.gemini_chat_model
            if logger.isEnabledFor(logging.INFO):
                from app.services.circuit_breaker import chat_circuit_breaker as _cb

                if _cb.state.value != "CLOSED":
                    logger.info(
                        "Chat turn using Gemini model '%s' (breaker probing, state=%s).",
                        settings.gemini_chat_model, _cb.state.value)
        else:
            try:
                self._current_model = settings.bedrock_model
            except Exception:
                pass
            if getattr(self, "_chat_use_gemini", False):
                logger.info(
                    "Chat turn using Bedrock fallback model '%s' (Gemini cooling down).",
                    settings.bedrock_model)

        try:
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

            # JEV-based memory decision: should this query use tools or can it
            # rely on conversation memory? Injects a reminder for data queries.
            from app.services.judge_service import judge_service
            needs_tools = await judge_service.classify_query_intent_jev(rewritten_query)
            if needs_tools == "data":
                # Inject a subtle system-level reminder before the user message
                # so the agent "remembers" it must call a tool for this query.
                lang_messages.append(AIMessage(content=""))
                lang_messages.pop()  # clean slate
                data_reminder = (
                    f"[IMPORTANT: This is a DATA question. You MUST call a tool "
                    f"(execute_readonly_query, recent_emails, or summarize_report) "
                    f"BEFORE answering. Do NOT answer from memory or guess. "
                    f"If the tool returns 0 results, say there is nothing.]\n\n"
                    f"{rewritten_query}"
                )
                lang_messages.append(HumanMessage(content=data_reminder))
            else:
                lang_messages.append(HumanMessage(content=rewritten_query))

            # Timing tap for TTFT. The tap must wrap THIS turn's backend
            # (Gemini or the Bedrock fallback) so streamed tokens match what
            # _agent_step generates.
            if first_backend == "gemini" and getattr(self, "_gemini_with_tools", None) is not None:
                bound_llm = self._gemini_with_tools
            else:
                bound_llm = getattr(self, "_bedrock_with_tools", None) or getattr(self, "llm_with_tools", None)
            # Keep the legacy attribute in sync for test doubles that read it.
            try:
                self.llm_with_tools = bound_llm
            except Exception:
                pass
            tap = (_TokenTap(bound_llm, on_token=on_token,
                             holder=holder, t0=t0)
                   if bound_llm is not None else None)
            token = _token_tap.set(tap)
            try:
                try:
                    prev_obs = getattr(self, "_prev_obs", {}).get(session_id)
                    generated = await self._generate_with_judge(
                        lang_messages, user_content, prev_obs=prev_obs)
                    assistant_reply = generated["reply"]
                    verdict = generated.get("verdict", "PASS")
                    try:
                        self._remember_obs(session_id, generated.get("obs") or [])
                    except Exception:
                        pass
                except Exception:
                    # Full traceback stays in logs; the site shows "Error" only.
                    logger.error("LangGraph execution failed.", exc_info=True)
                    assistant_reply = "Error"
                    verdict = "ERROR"
            finally:
                _token_tap.reset(token)

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

            latency = round(time.perf_counter() - t0, 1)
            # Important-only per-turn line: which .env model actually replied.
            logger.info(
                "Chat reply via model '%s' (verdict=%s, latency=%ss).",
                getattr(self, "_current_model", settings.bedrock_model), verdict, latency)

            return {
                "session_id": session_id,
                "reply": assistant_reply,
                "verdict": verdict,
                "ttft_s": holder.get("ttft_s"),
                "latency_s": latency,
                "rewritten_query": rewritten_query,
                "created_at": now.isoformat()
            }
        except Exception:
            # Any setup/persist failure: log fully, reply generically.
            # Best-effort persist so the turn is still visible.
            logger.error("Chat turn failed.", exc_info=True)
            try:
                async with AsyncSessionLocal() as db_session:
                    asst_now = datetime.now(timezone.utc).replace(tzinfo=None)
                    db_session.add(ChatMessage(
                        session_id=session_id, role="assistant",
                        content="Error", created_at=asst_now))
                    await db_session.commit()
            except Exception:
                pass
            return {
                "session_id": session_id,
                "reply": "Error",
                "verdict": "ERROR",
                "ttft_s": holder.get("ttft_s"),
                "latency_s": round(time.perf_counter() - t0, 1),
                "rewritten_query": user_content,
                "created_at": now.isoformat()
            }

    async def send_message(self, session_id: str, user_content: str) -> Dict[str, Any]:
        """Process user message through LangGraph agent and persist interaction."""
        try:
            return await self._run_turn(session_id, user_content)
        except Exception:
            logger.error("send_message failed.", exc_info=True)
            return {
                "session_id": session_id,
                "reply": "Error",
                "verdict": "ERROR",
                "ttft_s": None,
                "latency_s": 0.0,
                "rewritten_query": user_content,
                "created_at": datetime.now(timezone.utc).isoformat(),
            }

    async def send_message_stream(self, session_id: str, user_content: str):
        """SSE event source for one turn (gated by `chat_sse_enabled`).

        Yields {"type": "token", "delta": str} live as the model generates,
        then exactly one terminal event:
        {"type": "done", "reply", "verdict", "ttft_s", "latency_s"} or
        {"type": "error", "message"} when even the pipeline setup failed.
        When the judge rejects the streamed first pass, the terminal `reply`
        is the corrected/fallback text (the client replaces the live draft).
        """
        queue: asyncio.Queue = asyncio.Queue()

        def on_token(delta: str):
            try:
                queue.put_nowait({"type": "token", "delta": delta})
            except Exception:
                pass

        async def _run():
            try:
                return await self._run_turn(
                    session_id, user_content, on_token=on_token)
            except Exception:
                logger.error("Streamed turn failed.", exc_info=True)
                return {"error": "Error"}
            finally:
                try:
                    queue.put_nowait({"type": "__end__"})
                except Exception:
                    pass

        task = asyncio.create_task(_run())
        while True:
            event = await queue.get()
            if event.get("type") == "__end__":
                break
            yield event
        result = await task
        if "error" in result:
            yield {"type": "error", "message": "Error"}
        else:
            yield {
                "type": "done",
                "reply": result["reply"],
                "verdict": result.get("verdict", "PASS"),
                "ttft_s": result.get("ttft_s"),
                "latency_s": result.get("latency_s"),
            }

chat_service = ChatService()
