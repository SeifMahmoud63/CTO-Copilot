from fastapi import APIRouter, HTTPException, Query, Request
from app.core.config import settings
from app.core.enums import AppMessage
from app.schemas.pr_schema import PRListResponse, PRItem, CircuitBreakerStatus, DashboardLeaderboardResponse
from app.services.github_service import github_service
from app.services.circuit_breaker import circuit_breaker
from app.services.llm_service import llm_service
from app.services.db_service import db_service

router = APIRouter(prefix="/api", tags=["PRs & AI Summary"])

@router.get("/health")
async def health():
    return {
        "status": "healthy",
        "repository": settings.github_repo,
        "circuit_breaker": circuit_breaker.get_status()
    }

@router.get("/prs", response_model=PRListResponse)
async def list_prs(state: str = Query(default="all", pattern="^(open|closed|all)$")):
    """List pull requests with author, timestamp, and AI summaries."""
    prs = await github_service.get_pull_requests(state=state)
    message = AppMessage.PR_FETCH_SUCCESS.value if prs else AppMessage.NO_PRS_FOUND.value
    return PRListResponse(
        repository=settings.github_repo,
        total_prs=len(prs),
        prs=prs,
        message=message,
        stale_threshold_days=settings.pr_stale_threshold_days
    )

@router.get("/dashboard", response_model=DashboardLeaderboardResponse)
async def get_dashboard(days: int = Query(default=30, ge=1, le=365)):
    """Retrieve team impact leaderboard and engineer metrics for a specified timeframe."""
    return await github_service.get_team_dashboard(days=days)


@router.post("/prs/{pr_number}/summarize", response_model=PRItem)
async def summarize_pr(pr_number: int, force_refresh: bool = False):
    """Trigger LLM summary generation for a specific pull request."""
    pr_item = await github_service.summarize_pr(pr_number=pr_number, force_refresh=force_refresh)
    if not pr_item:
        raise HTTPException(status_code=404, detail=f"Pull request #{pr_number} not found or inaccessible.")
    return pr_item

@router.get("/circuit-breaker", response_model=CircuitBreakerStatus)
async def get_circuit_status():
    """Retrieve the circuit breaker state and cooldown status."""
    status = circuit_breaker.get_status()
    return CircuitBreakerStatus(**status)

@router.post("/webhook/github")
async def github_webhook(request: Request):
    """Webhook endpoint receiving real-time GitHub PR events."""
    event = request.headers.get("X-GitHub-Event")
    if event == "pull_request":
        payload = await request.json()
        action = payload.get("action")
        pr_number = payload.get("pull_request", {}).get("number")
        if pr_number and action in ["opened", "synchronize", "reopened"]:
            await github_service.summarize_pr(pr_number, force_refresh=True)
            return {"status": "summarized", "pr": pr_number}
    return {"status": "ignored"}

@router.get("/db/stats")
async def get_database_stats():
    """Retrieve record counts from the 2-table MySQL schema (PRs, Engineers)."""
    return await db_service.get_db_stats()

@router.get("/engineers")
async def list_engineers():
    """List engineers with PR count, total score and average score from MySQL."""
    return {"engineers": await db_service.get_engineers()}

# Chat endpoints

from pydantic import BaseModel
from typing import Optional
from app.services.chat_service import chat_service

class CreateSessionRequest(BaseModel):
    title: Optional[str] = None

class SendMessageRequest(BaseModel):
    message: str

@router.get("/chat/sessions")
async def list_chat_sessions():
    """List all user chat sessions."""
    return {"sessions": await chat_service.list_sessions()}

@router.post("/chat/sessions")
async def create_chat_session(payload: Optional[CreateSessionRequest] = None):
    """Create a new chat session."""
    title = payload.title if payload else None
    return await chat_service.create_session(title=title)

@router.get("/chat/sessions/{session_id}/messages")
async def get_session_messages(session_id: str):
    """Get message history for a specific session."""
    return {"messages": await chat_service.get_session_messages(session_id)}

@router.delete("/chat/sessions/{session_id}")
async def delete_chat_session(session_id: str):
    """Delete a chat session."""
    success = await chat_service.delete_session(session_id)
    return {"success": success}

@router.post("/chat/sessions/{session_id}/message")
async def send_chat_message(session_id: str, payload: SendMessageRequest):
    """Send a message to the LangGraph read-only MySQL agent."""
    if not payload.message.strip():
        raise HTTPException(status_code=400, detail="Message cannot be empty.")
    return await chat_service.send_message(session_id, payload.message.strip())


# Reports endpoints

@router.get("/reports")
async def list_reports(limit: int = Query(default=30, ge=1, le=200)):
    """List daily CTO reports (title + date), newest first."""
    return {"reports": await db_service.get_reports(limit=limit)}


@router.post("/reports/generate")
async def trigger_report_generation(report_date: Optional[str] = None):
    """Enqueue a daily report generation task (manual trigger, same pipeline as Beat)."""
    try:
        from app.services.celery_app import generate_daily_task

        task = generate_daily_task.delay(report_date)
        return {"status": "queued", "task_id": task.id}
    except Exception as e:
        # Fall back to inline generation if Redis broker is down
        from app.services.report_service import generate_daily_report

        record = await generate_daily_report(report_date)
        return {"status": "completed_inline", "report": record, "detail": str(e)}


@router.get("/reports/tasks/{task_id}")
async def report_task_status(task_id: str):
    """Poll a queued generation task (PENDING / SUCCESS / FAILURE)."""
    from celery.result import AsyncResult

    from app.services.celery_app import celery

    res = AsyncResult(task_id, app=celery)
    payload: dict = {"task_id": task_id, "status": res.status}
    if res.ready():
        payload["result"] = res.result if res.successful() else str(res.result)
    return payload


@router.get("/reports/{report_id}/file")
async def report_file(
    report_id: int,
    mode: str = Query(default="preview", pattern="^(preview|download)$"),
):
    """Preview (inline) or download (attachment) a report PDF."""
    import os

    from fastapi.responses import FileResponse

    rec = await db_service.get_report(report_id)
    if not rec or not rec.get("pdf_path") or not os.path.exists(rec["pdf_path"]):
        raise HTTPException(status_code=404, detail=f"Report #{report_id} PDF not found.")
    return FileResponse(
        rec["pdf_path"],
        media_type="application/pdf",
        filename=os.path.basename(rec["pdf_path"]),
        content_disposition_type="attachment" if mode == "download" else "inline",
    )


# ----------------- Deepgram Voice Agent Endpoints ----------------- #

from fastapi import WebSocket
from app.services.voice_service import voice_service


@router.get("/voice/config")
async def get_voice_config():
    """Retrieve voice agent configuration and readiness status."""
    return {
        "configured": bool(settings.deepgram_api_key),
        "model": settings.deepgram_agent_model,
        "voice": settings.deepgram_voice_model,
    }


@router.websocket("/voice/ws")
async def voice_agent_websocket(websocket: WebSocket):
    """Bidirectional WebSocket streaming audio and tool events with Deepgram Voice Agent."""
    await voice_service.handle_client_session(websocket)




