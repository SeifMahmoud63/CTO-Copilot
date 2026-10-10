import logging
import re
import json
import uuid
from datetime import datetime, timezone
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

Guidelines:
- When the user asks about pull requests, authors, stats, overdue items, scores, or repository metrics, ALWAYS use the `execute_readonly_query` tool to inspect the real data before answering.
- You can chat casually and offer strategic, architectural, and engineering leadership insights.
- Provide clear, well-formatted markdown responses (tables, bullet points, code blocks where appropriate).
"""

# Read-only SQL safety regex
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
    )

@tool
async def execute_readonly_query(sql_query: str) -> str:
    """Executes a strictly READ-ONLY SQL query (SELECT, SHOW, DESCRIBE, EXPLAIN) on the MySQL database and returns the results.
    
    Args:
        sql_query: The SQL query to execute. Must only be a SELECT or read query.
    """
    # Clean markdown fences if model wrapped query in ```sql ... ```
    clean_sql = re.sub(r"^```(?:sql)?\s*", "", sql_query.strip(), flags=re.IGNORECASE)
    clean_sql = re.sub(r"\s*```$", "", clean_sql).strip().rstrip(";")
    
    # Validation
    if not re.match(r"^\s*(SELECT|SHOW|DESCRIBE|EXPLAIN)\b", clean_sql, re.IGNORECASE):
        return "Error: Only read-only queries (SELECT, SHOW, DESCRIBE, EXPLAIN) are permitted."
    
    if FORBIDDEN_SQL_PATTERN.search(clean_sql):
        return "Error: Write, alter, or administrative operations are strictly blocked by read-only enforcement."
    
    try:
        async with AsyncSessionLocal() as session:
            # Enforce read-only transaction on connection level
            await session.execute(text("SET TRANSACTION READ ONLY"))
            result = await session.execute(text(clean_sql))
            rows = result.mappings().all()
            
            if not rows:
                return "Query executed successfully. Result: 0 rows returned."
            
            # Format rows as JSON string
            serializable_rows = []
            for row in rows[:50]:  # limit to 50 rows for safety
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

# Define Agent State
class AgentState(TypedDict):
    messages: Annotated[Sequence[BaseMessage], add_messages]

class ChatService:
    def __init__(self):
        self.llm = ChatOpenAI(
            base_url=settings.bedrock_base_url_qwen,
            api_key=settings.bedrock_api_key,
            model=settings.bedrock_model,
            temperature=settings.llm_temperature
        )
        self.tools = [get_database_schema, execute_readonly_query]
        self.tools_by_name = {t.name: t for t in self.tools}
        self.llm_with_tools = self.llm.bind_tools(self.tools)
        
        # Build LangGraph StateGraph
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
        
        # 1. Fetch existing session & historical messages
        async with AsyncSessionLocal() as db_session:
            sess_stmt = select(ChatSession).where(ChatSession.id == session_id)
            sess_res = await db_session.execute(sess_stmt)
            session_obj = sess_res.scalar_one_or_none()
            if not session_obj:
                # Auto-create if not exists
                session_obj = ChatSession(
                    id=session_id,
                    title=user_content[:40] + ("..." if len(user_content) > 40 else ""),
                    created_at=now,
                    updated_at=now
                )
                db_session.add(session_obj)
                await db_session.commit()
                await db_session.refresh(session_obj)

            # Save user message to database
            user_msg_db = ChatMessage(session_id=session_id, role="user", content=user_content, created_at=now)
            db_session.add(user_msg_db)
            
            # Fetch message history
            hist_stmt = select(ChatMessage).where(ChatMessage.session_id == session_id).order_by(ChatMessage.id.asc())
            hist_res = await db_session.execute(hist_stmt)
            history_rows = hist_res.scalars().all()
            
            # Update session title if default
            if session_obj.title == "New Conversation" or not session_obj.title:
                clean_title = user_content.strip()[:45]
                session_obj.title = clean_title + ("..." if len(user_content) > 45 else "")
            session_obj.updated_at = now
            await db_session.commit()

        # 2. Build LangGraph message array
        lang_messages: List[BaseMessage] = []
        for m in history_rows:
            if m.role == "user":
                lang_messages.append(HumanMessage(content=m.content))
            elif m.role == "assistant":
                lang_messages.append(AIMessage(content=m.content))

        # Ensure current user message is included
        lang_messages.append(HumanMessage(content=user_content))

        # 3. Invoke LangGraph agent workflow
        try:
            final_state = await self.graph.ainvoke({"messages": lang_messages})
            final_ai_message = final_state["messages"][-1]
            assistant_reply = final_ai_message.content or "Done."
        except Exception as e:
            logger.error(f"LangGraph execution failed: {e}")
            assistant_reply = f"Apologies, an error occurred while processing your request: {e}"

        # 4. Save assistant response to database
        async with AsyncSessionLocal() as db_session:
            asst_now = datetime.now(timezone.utc).replace(tzinfo=None)
            asst_msg_db = ChatMessage(session_id=session_id, role="assistant", content=assistant_reply, created_at=asst_now)
            db_session.add(asst_msg_db)
            
            # Update session updated_at
            upd_stmt = select(ChatSession).where(ChatSession.id == session_id)
            upd_res = await db_session.execute(upd_stmt)
            curr_sess = upd_res.scalar_one_or_none()
            if curr_sess:
                curr_sess.updated_at = asst_now
            await db_session.commit()

        return {
            "session_id": session_id,
            "reply": assistant_reply,
            "created_at": now.isoformat()
        }

chat_service = ChatService()
