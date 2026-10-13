import logging
import os
from fastapi import APIRouter, HTTPException, Query, Request
from app.core.config import settings
from app.core.enums import AppMessage
from app.schemas.pr_schema import PRListResponse, PRItem, CircuitBreakerStatus, DashboardLeaderboardResponse
from app.services.github_service import github_service
from app.services.circuit_breaker import circuit_breaker
from app.services.llm_service import llm_service
from app.services.db_service import db_service

logger = logging.getLogger("cto-copilot.api")

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
    try:
        return await chat_service.send_message(session_id, payload.message.strip())
    except Exception:
        # Internal details stay in logs; the site sees "Error" only.
        logger.error("Chat message failed.", exc_info=True)
        raise HTTPException(status_code=500, detail="Error")


# ----------------- SSE Streaming (Server-Sent Events) ----------------- #

class SSEConfigRequest(BaseModel):
    enabled: bool


@router.get("/chat/sse")
async def get_sse_config():
    """Whether SSE token streaming is currently enabled (Eval Lab toggle)."""
    return {"enabled": bool(settings.chat_sse_enabled)}


@router.post("/chat/sse")
async def set_sse_config(payload: SSEConfigRequest):
    """Enable/disable SSE token streaming at runtime (resets on restart).

    Lets the CTO feel the TTFT-vs-latency gap live in the Chatbot view:
    with SSE on, first tokens render as generated instead of after the
    full reply (judge gate + retries still apply before delivery).
    """
    settings.chat_sse_enabled = bool(payload.enabled)
    return {"enabled": bool(settings.chat_sse_enabled), "persistent": False}


@router.post("/chat/sessions/{session_id}/message/stream")
async def stream_chat_message(session_id: str, payload: SendMessageRequest):
    """SSE token stream for one chat turn (requires SSE enabled).

    Frames are `data: <json>\\n\\n` with {"type": "token", "delta": ...}
    live, then a terminal {"type": "done", ...} (or {"type": "error"}).
    """
    from fastapi.responses import StreamingResponse

    import json as _json

    if not payload.message.strip():
        raise HTTPException(status_code=400, detail="Message cannot be empty.")
    if not settings.chat_sse_enabled:
        raise HTTPException(
            status_code=403,
            detail="SSE streaming is disabled. Enable it via POST /api/chat/sse.",
        )

    async def event_gen():
        async for event in chat_service.send_message_stream(
            session_id, payload.message.strip()
        ):
            yield f"data: {_json.dumps(event, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        event_gen(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


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
        logger.warning(f"Report queue failed, generating inline: {e}", exc_info=True)
        from app.services.report_service import generate_daily_report

        try:
            record = await generate_daily_report(report_date)
        except Exception:
            logger.error("Inline report generation failed.", exc_info=True)
            raise HTTPException(status_code=500, detail="Error")
        return {"status": "completed_inline", "report": record, "detail": "Error"}


@router.get("/reports/tasks/{task_id}")
async def report_task_status(task_id: str):
    """Poll a queued generation task (PENDING / SUCCESS / FAILURE)."""
    from celery.result import AsyncResult

    from app.services.celery_app import celery

    res = AsyncResult(task_id, app=celery)
    payload: dict = {"task_id": task_id, "status": res.status}
    if res.ready():
        if res.successful():
            payload["result"] = res.result
        else:
            logger.error(f"Report task {task_id} failed: {res.result}", exc_info=True)
            payload["result"] = "Error"
    return payload


@router.get("/reports/{report_id}/file")
async def report_file(
    report_id: int,
    mode: str = Query(default="preview", pattern="^(preview|download)$"),
):
    """Preview (inline) or download (attachment) a report PDF (streams from MinIO with multi-tier fallback)."""
    import os
    import json
    from fastapi.responses import StreamingResponse

    rec = await db_service.get_report(report_id)
    if not rec:
        raise HTTPException(status_code=404, detail=f"Report #{report_id} not found.")

    pdf_ref = rec.get("pdf_path")
    from app.services.storage_service import storage_service

    data = None
    day_str = str(rec.get("report_date") or "")
    filename = f"daily-report-{day_str}.pdf" if day_str else f"daily-report-{report_id}.pdf"

    # 1. Try MinIO via pdf_ref if it's an s3 URI
    if pdf_ref and str(pdf_ref).startswith("s3://"):
        try:
            data = storage_service.download_uri(str(pdf_ref))
            filename = str(pdf_ref).rsplit("/", 1)[-1]
        except Exception as e:
            logger.warning(f"MinIO download_uri failed for {pdf_ref}: {e}")
            data = None

    # 2. Try MinIO via standard key if not found yet
    if data is None and day_str:
        std_key = storage_service.report_key(day_str)
        try:
            data = storage_service.download_bytes(settings.minio_bucket_reports, std_key)
            filename = std_key
        except Exception:
            data = None

    # 3. Try local filesystem (legacy files)
    if data is None and pdf_ref:
        local_candidates = [
            str(pdf_ref),
            os.path.join(settings.reports_dir, os.path.basename(str(pdf_ref))),
            os.path.join("/app/reports", os.path.basename(str(pdf_ref))),
            os.path.join("reports", os.path.basename(str(pdf_ref))),
        ]
        if day_str:
            local_candidates.append(os.path.join(settings.reports_dir, f"daily-report-{day_str}.pdf"))
            local_candidates.append(os.path.join("reports", f"daily-report-{day_str}.pdf"))
        for candidate in local_candidates:
            if os.path.exists(candidate) and os.path.isfile(candidate):
                try:
                    with open(candidate, "rb") as f:
                        data = f.read()
                    filename = os.path.basename(candidate)
                    # Opportunistically sync to MinIO
                    try:
                        storage_service.upload_bytes(settings.minio_bucket_reports, filename, data)
                    except Exception:
                        pass
                    break
                except Exception:
                    pass

    # 4. Dynamic fallback: re-render PDF if metrics exist
    if data is None and day_str:
        try:
            from app.services.report_service import build_pdf_bytes
            metrics = json.loads(rec.get("metrics_json") or "{}") if rec.get("metrics_json") else {}
            data = build_pdf_bytes(
                day_str,
                rec.get("title") or f"CTO Daily Report — {day_str}",
                metrics,
                rec.get("executive_summary") or "",
            )
            filename = f"daily-report-{day_str}.pdf"
            try:
                storage_service.upload_bytes(settings.minio_bucket_reports, filename, data)
            except Exception:
                pass
        except Exception as e:
            logger.warning(f"Dynamic PDF generation failed for report #{report_id}: {e}")

    if data is None:
        raise HTTPException(status_code=404, detail=f"Report #{report_id} PDF not found.")

    return StreamingResponse(
        iter([data]),
        media_type="application/pdf",
        headers={
            "Content-Disposition": (
                f'attachment; filename="{filename}"' if mode == "download"
                else f'inline; filename="{filename}"'
            )
        },
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


# ----------------- Email Triage Endpoints ----------------- #

@router.get("/emails")
async def list_emails(
    limit: int = Query(default=30, ge=1, le=200),
    days: int = Query(default=3, ge=1, le=365),
):
    """List triaged emails from the last `days` days, newest first."""
    return {"emails": await db_service.get_emails(limit=limit, days=days)}


@router.post("/emails/sync")
async def sync_emails():
    """Run one inbox polling round now (same pipeline as the beat schedule)."""
    from app.services.email_service import poll_inbox

    try:
        result = await poll_inbox()
        return {"status": "completed", **result}
    except ConnectionError:
        logger.error("Inbox sync connection failed.", exc_info=True)
        raise HTTPException(status_code=503, detail="Error")
    except Exception:
        logger.error("Inbox sync failed.", exc_info=True)
        raise HTTPException(status_code=500, detail="Error")


@router.delete("/emails/{email_id}")
async def dismiss_email(email_id: int):
    """Dismiss an email from the list (soft-hide; polling will not resurrect it)."""
    ok = await db_service.hide_email(email_id)
    if not ok:
        raise HTTPException(status_code=404, detail=f"Email #{email_id} not found.")
    return {"ok": True}


# ----------------- Eval Lab Endpoints ----------------- #

class EvalRunRequest(BaseModel):
    use_judge: bool = True
    max_questions: Optional[int] = None
    sse_enabled: Optional[bool] = None


@router.post("/eval/run")
async def start_eval_run(payload: Optional[EvalRunRequest] = None):
    """Queue a full torture-test run (background Celery task, results to MLflow)."""
    from app.services.celery_app import run_eval_task

    task = run_eval_task.delay(
        use_judge=(payload.use_judge if payload else True),
        max_questions=(payload.max_questions if payload else None),
        sse_enabled=(payload.sse_enabled if payload and payload.sse_enabled is not None
                     else settings.chat_sse_enabled),
    )
    return {"status": "queued", "task_id": task.id}


@router.get("/eval/recent")
async def recent_eval_runs(limit: int = Query(default=10, ge=1, le=50)):
    """Last eval runs from MLflow (for the Eval Lab UI)."""
    from app.services.eval_service import recent_runs

    return {"runs": recent_runs(limit=limit)}


@router.get("/eval/progress/{task_id}")
async def eval_progress(task_id: str):
    """Live X-of-Y progress for a running eval (Eval Lab card)."""
    from app.services.eval_service import read_eval_progress

    return read_eval_progress(task_id)


@router.get("/eval/runs/{task_id}")
async def eval_task_status(task_id: str):
    """Poll a queued eval run (PENDING / SUCCESS / FAILURE)."""
    from celery.result import AsyncResult

    from app.services.celery_app import celery

    res = AsyncResult(task_id, app=celery)
    payload: dict = {"task_id": task_id, "status": res.status}
    if res.ready():
        if res.successful():
            payload["result"] = res.result
        else:
            logger.error(f"Eval task {task_id} failed: {res.result}", exc_info=True)
            payload["result"] = "Error"
    return payload


@router.delete("/eval/runs/{run_id}")
async def delete_eval_run(run_id: str):
    """Delete an Eval Lab run from MLflow (soft-delete, hidden from lists).

    NOTE: same path shape as the task-status GET above — FastAPI routes by
    HTTP method, so GET reads Celery task state while DELETE removes the
    MLflow run. They are different id namespaces (task_id vs run_id).
    """
    from app.services.eval_service import delete_eval_run as _delete_run

    if not _delete_run(run_id):
        raise HTTPException(status_code=404, detail="Eval run not found or delete failed.")
    return {"ok": True}


# --- Slack Bot Integration Routes ---

@router.get("/slack/status")
async def get_slack_status():
    """Return Slack Bot integration status and configuration details."""
    from app.services.slack_service import slack_service

    return {
        "enabled": slack_service.is_enabled,
        "channel_id": slack_service.default_channel,
    }


@router.post("/slack/test")
async def send_slack_test():
    """Send an immediate test confirmation message to the configured Slack channel."""
    from app.services.slack_service import slack_service

    try:
        res = await slack_service.send_message(
            text=":white_check_mark: *CTO Copilot test message:* Slack Bot integration is healthy and verified."
        )
    except Exception:
        logger.error("Slack test message failed.", exc_info=True)
        raise HTTPException(status_code=502, detail="Error")
    if not res.get("ok") and not res.get("skipped"):
        logger.error(f"Slack test message failed: {res.get('error')}")
        raise HTTPException(status_code=502, detail="Error")
    return res


@router.post("/slack/notify-overdue")
async def notify_slack_overdue():
    """Scan open pull requests and send SLA breach alerts to Slack."""
    from app.services.slack_service import slack_service

    results = await slack_service.check_and_notify_overdue_prs()
    return {"alerts_sent": len(results), "details": results}


@router.post("/slack/upload-latest-report")
async def upload_latest_report_to_slack():
    """Upload the most recent daily PDF report to the configured Slack channel."""
    from app.services.slack_service import slack_service

    reports = await db_service.get_reports(limit=1)
    if not reports:
        raise HTTPException(status_code=404, detail="No daily reports found in database.")

    latest = reports[0]
    pdf_path = latest.pdf_path
    if not pdf_path:
        raise HTTPException(status_code=404, detail="Report PDF not found.")
    # Verify the object exists (MinIO URI or legacy local path).
    try:
        from app.services.storage_service import storage_service

        if not storage_service.exists_any_path(pdf_path):
            raise HTTPException(status_code=404, detail=f"Report PDF not found at {pdf_path}")
    except HTTPException:
        raise
    except Exception:
        import os as _os

        if not _os.path.exists(pdf_path):
            raise HTTPException(status_code=404, detail=f"Report PDF not found at {pdf_path}")

    try:
        res = await slack_service.upload_daily_report(
            pdf_path=pdf_path,
            title=latest.title,
            summary=latest.executive_summary,
        )
    except Exception:
        logger.error("Slack report upload failed.", exc_info=True)
        raise HTTPException(status_code=502, detail="Error")
    if not res.get("ok"):
        logger.error(f"Slack report upload failed: {res.get('error')}")
        raise HTTPException(status_code=502, detail="Error")
    return {"status": "uploaded", "report_date": latest.report_date, "result": res}




