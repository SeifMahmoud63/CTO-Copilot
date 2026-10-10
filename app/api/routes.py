from fastapi import APIRouter, HTTPException, Query, Request
from typing import Optional
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
        message=message
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
    """Retrieve record counts from MySQL async tables (PRs, Summaries, Scores, Approvals, Audit Logs)."""
    return await db_service.get_db_stats()

@router.get("/db/audit-logs")
async def get_audit_logs(limit: int = Query(default=50, ge=1, le=200)):
    """Retrieve the recent audit log trail from MySQL."""
    return await db_service.get_audit_logs(limit=limit)

@router.post("/prs/{pr_number}/decision")
async def record_pr_decision(
    pr_number: int,
    status: str = Query(..., pattern="^(APPROVED|CHANGES_REQUESTED|REJECTED|PENDING)$"),
    decision_by: str = Query(default="CTO"),
    review_comment: Optional[str] = None
):
    """Register an approval or review decision in MySQL."""
    record = await db_service.save_approval(
        pr_number=pr_number,
        status=status,
        decision_by=decision_by,
        review_comment=review_comment
    )
    if not record:
        raise HTTPException(status_code=400, detail=f"Failed to record decision for PR #{pr_number}")
    return {"status": "success", "decision": status, "pr_number": pr_number, "by": decision_by}


