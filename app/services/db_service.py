import logging
from typing import Optional, List, Dict, Any
from datetime import datetime, date
from sqlalchemy import select, func, desc

from app.db.session import AsyncSessionLocal, init_db as _init_db
from app.models import PullRequest, Engineer, DailyReport

logger = logging.getLogger("cto-copilot.db_service")

LEGACY_TABLES = ("pr_summaries", "pr_impact_scores", "pr_approvals", "audit_logs")


def impact_tier_for(score: Optional[float]) -> str:
    """Tier label shared by PR rows and engineer aggregates."""
    if score is None:
        return "Routine Support"
    if score >= 8.0:
        return "Critical Driver"
    if score >= 6.5:
        return "High Impact"
    if score >= 5.0:
        return "Solid Contributor"
    return "Routine Support"


class DatabaseService:
    """Database layer for pull requests, engineers, and daily reports."""

    async def init_db(self) -> bool:
        return await _init_db()

    async def save_or_update_pr(
        self,
        number: int,
        title: str,
        author: str,
        state: str,
        head_branch: str,
        base_branch: str,
        html_url: str,
        diff_url: Optional[str] = None,
        author_avatar: Optional[str] = None,
        github_pr_id: Optional[int] = None,
        created_at: Optional[datetime] = None,
        updated_at: Optional[datetime] = None,
        is_overdue: bool = False,
        overdue_days: int = 0,
        summary_text: Optional[str] = None,
        summary_provider: Optional[str] = None,
        summary_timestamp: Optional[datetime] = None,
        impact_score: Optional[float] = None,
        impact_tier: Optional[str] = None,
    ) -> Optional[PullRequest]:
        """Insert or update a PR record (summary + score stored inline)."""
        try:
            async with AsyncSessionLocal() as session:
                async with session.begin():
                    stmt = select(PullRequest).where(PullRequest.number == number)
                    res = await session.execute(stmt)
                    pr = res.scalar_one_or_none()

                    if pr:
                        pr.title = title
                        pr.author = author
                        pr.state = state
                        pr.head_branch = head_branch
                        pr.base_branch = base_branch
                        pr.html_url = html_url
                        pr.is_overdue = is_overdue
                        pr.overdue_days = overdue_days
                        if diff_url:
                            pr.diff_url = diff_url
                        if author_avatar:
                            pr.author_avatar = author_avatar
                        if updated_at:
                            pr.updated_at = updated_at
                        if summary_text:
                            pr.summary_text = summary_text
                        if summary_provider:
                            pr.summary_provider = summary_provider
                        if summary_timestamp:
                            pr.summary_timestamp = summary_timestamp
                        if impact_score is not None:
                            pr.impact_score = impact_score
                            pr.impact_tier = impact_tier or impact_tier_for(impact_score)
                    else:
                        pr = PullRequest(
                            number=number,
                            github_pr_id=github_pr_id,
                            title=title,
                            author=author,
                            author_avatar=author_avatar,
                            state=state,
                            head_branch=head_branch,
                            base_branch=base_branch,
                            html_url=html_url,
                            diff_url=diff_url,
                            is_overdue=is_overdue,
                            overdue_days=overdue_days,
                            summary_text=summary_text,
                            summary_provider=summary_provider,
                            summary_timestamp=summary_timestamp,
                            impact_score=impact_score,
                            impact_tier=impact_tier or (impact_tier_for(impact_score) if impact_score is not None else None),
                            created_at=created_at or datetime.utcnow(),
                            updated_at=updated_at
                        )
                        session.add(pr)

                    await session.flush()
                    return pr
        except Exception as e:
            logger.warning(f"Error saving PR #{number} to MySQL: {e}")
            return None

    async def get_pr_by_number(self, number: int) -> Optional[Dict[str, Any]]:
        """Fetch one stored PR row by GitHub number (summary + score).

        Used to re-hydrate the in-memory summary cache after restarts so
        already-summarized PRs don't cost fresh LLM calls. Fail-open: any
        DB error returns None and the caller falls through to the LLM path.
        """
        try:
            async with AsyncSessionLocal() as session:
                stmt = select(PullRequest).where(PullRequest.number == number)
                res = await session.execute(stmt)
                pr = res.scalar_one_or_none()
                if not pr:
                    return None
                return {
                    "number": pr.number,
                    "github_pr_id": pr.github_pr_id,
                    "summary_text": pr.summary_text,
                    "summary_provider": pr.summary_provider,
                    "summary_timestamp": pr.summary_timestamp.isoformat() if pr.summary_timestamp else None,
                    "impact_score": pr.impact_score,
                    "impact_tier": pr.impact_tier,
                }
        except Exception as e:
            logger.warning(f"Error fetching PR #{number} from MySQL: {e}")
            return None

    async def rebuild_engineers(self, pr_items: List[Any]) -> int:
        """Recompute the engineers table from a list of PR items (author, impact_score, avatar)."""
        try:
            aggregates: Dict[str, Dict[str, Any]] = {}
            for pr in pr_items:
                author = getattr(pr, "author", None) or "unknown"
                score = getattr(pr, "impact_score", None)
                entry = aggregates.setdefault(author, {"count": 0, "total": 0.0, "scored": 0, "avatar": None})
                entry["count"] += 1
                if score is not None:
                    entry["total"] += float(score)
                    entry["scored"] += 1
                if not entry["avatar"]:
                    entry["avatar"] = getattr(pr, "author_avatar", None)

            async with AsyncSessionLocal() as session:
                async with session.begin():
                    for author, data in aggregates.items():
                        total = round(data["total"], 1)
                        avg = round(data["total"] / data["scored"], 1) if data["scored"] else 0.0
                        stmt = select(Engineer).where(Engineer.author == author)
                        res = await session.execute(stmt)
                        eng = res.scalar_one_or_none()
                        if eng:
                            eng.pr_count = data["count"]
                            eng.total_score = total
                            eng.avg_score = avg
                            eng.tier = impact_tier_for(avg if data["scored"] else None)
                            if data["avatar"]:
                                eng.author_avatar = data["avatar"]
                        else:
                            session.add(Engineer(
                                author=author,
                                author_avatar=data["avatar"],
                                pr_count=data["count"],
                                total_score=total,
                                avg_score=avg,
                                tier=impact_tier_for(avg if data["scored"] else None),
                            ))
            return len(aggregates)
        except Exception as e:
            logger.warning(f"Error rebuilding engineers table: {e}")
            return 0

    async def get_engineers(self) -> List[Dict[str, Any]]:
        """Return all engineers ordered by total score (mirrors the dashboard leaderboard)."""
        try:
            async with AsyncSessionLocal() as session:
                stmt = select(Engineer).order_by(desc(Engineer.total_score), desc(Engineer.avg_score))
                res = await session.execute(stmt)
                rows = res.scalars().all()
                return [
                    {
                        "author": e.author,
                        "author_avatar": e.author_avatar,
                        "pr_count": e.pr_count,
                        "total_score": e.total_score,
                        "avg_score": e.avg_score,
                        "tier": e.tier,
                        "updated_at": e.updated_at.isoformat() if e.updated_at else None,
                    }
                    for e in rows
                ]
        except Exception as e:
            logger.warning(f"Error fetching engineers: {e}")
            return []

    async def save_report(
        self,
        report_date: Any,
        title: str,
        executive_summary: Optional[str] = None,
        metrics_json: Optional[str] = None,
        pdf_path: Optional[str] = None,
        prs_opened: int = 0,
        prs_merged: int = 0,
        prs_closed: int = 0,
        overdue_count: int = 0,
    ) -> Optional[DailyReport]:
        """Upsert a daily report by report_date (idempotent re-runs)."""
        try:
            day = report_date
            if isinstance(day, str):
                day = date.fromisoformat(day)
            async with AsyncSessionLocal() as session:
                async with session.begin():
                    stmt = select(DailyReport).where(DailyReport.report_date == day)
                    res = await session.execute(stmt)
                    rep = res.scalar_one_or_none()
                    if rep:
                        rep.title = title
                        rep.executive_summary = executive_summary
                        rep.metrics_json = metrics_json
                        rep.pdf_path = pdf_path
                        rep.prs_opened = prs_opened
                        rep.prs_merged = prs_merged
                        rep.prs_closed = prs_closed
                        rep.overdue_count = overdue_count
                    else:
                        rep = DailyReport(
                            report_date=day,
                            title=title,
                            executive_summary=executive_summary,
                            metrics_json=metrics_json,
                            pdf_path=pdf_path,
                            prs_opened=prs_opened,
                            prs_merged=prs_merged,
                            prs_closed=prs_closed,
                            overdue_count=overdue_count,
                        )
                        session.add(rep)
                    await session.flush()
                    return rep
        except Exception as e:
            logger.warning(f"Error saving daily report {report_date}: {e}")
            return None

    async def get_reports(self, limit: int = 30) -> List[Dict[str, Any]]:
        """List daily reports newest-first (title + date for the UI)."""
        try:
            async with AsyncSessionLocal() as session:
                stmt = select(DailyReport).order_by(desc(DailyReport.report_date)).limit(limit)
                res = await session.execute(stmt)
                rows = res.scalars().all()
                return [
                    {
                        "id": r.id,
                        "report_date": r.report_date.isoformat() if r.report_date else None,
                        "title": r.title,
                        "prs_opened": r.prs_opened,
                        "prs_merged": r.prs_merged,
                        "prs_closed": r.prs_closed,
                        "overdue_count": r.overdue_count,
                        "created_at": r.created_at.isoformat() if r.created_at else None,
                    }
                    for r in rows
                ]
        except Exception as e:
            logger.warning(f"Error fetching daily reports: {e}")
            return []

    async def get_report_by_date(self, report_date: Any) -> Optional[Dict[str, Any]]:
        """Fetch one daily report by date (YYYY-MM-DD string or date object)."""
        try:
            day = report_date
            if isinstance(day, str):
                day = date.fromisoformat(day)
            async with AsyncSessionLocal() as session:
                res = await session.execute(select(DailyReport).where(DailyReport.report_date == day))
                r = res.scalar_one_or_none()
                if not r:
                    return None
                return {
                    "id": r.id,
                    "report_date": r.report_date.isoformat() if r.report_date else None,
                    "title": r.title,
                    "executive_summary": r.executive_summary,
                    "pdf_path": r.pdf_path,
                    "prs_opened": r.prs_opened,
                    "prs_merged": r.prs_merged,
                    "prs_closed": r.prs_closed,
                    "overdue_count": r.overdue_count,
                    "created_at": r.created_at.isoformat() if r.created_at else None,
                }
        except Exception as e:
            logger.warning(f"Error fetching daily report {report_date}: {e}")
            return None

    async def get_report(self, report_id: int) -> Optional[Dict[str, Any]]:
        """Full record including pdf_path + summary (for preview/download)."""
        try:
            async with AsyncSessionLocal() as session:
                res = await session.execute(select(DailyReport).where(DailyReport.id == report_id))
                r = res.scalar_one_or_none()
                if not r:
                    return None
                return {
                    "id": r.id,
                    "report_date": r.report_date.isoformat() if r.report_date else None,
                    "title": r.title,
                    "executive_summary": r.executive_summary,
                    "pdf_path": r.pdf_path,
                    "prs_opened": r.prs_opened,
                    "prs_merged": r.prs_merged,
                    "prs_closed": r.prs_closed,
                    "overdue_count": r.overdue_count,
                    "created_at": r.created_at.isoformat() if r.created_at else None,
                }
        except Exception as e:
            logger.warning(f"Error fetching daily report {report_id}: {e}")
            return None

    async def get_db_stats(self) -> Dict[str, int]:
        """Record counts for the schema (PRs, Engineers, Daily Reports)."""
        try:
            async with AsyncSessionLocal() as session:
                prs_cnt = (await session.execute(select(func.count(PullRequest.id)))).scalar() or 0
                engs_cnt = (await session.execute(select(func.count(Engineer.id)))).scalar() or 0
                reps_cnt = (await session.execute(select(func.count(DailyReport.id)))).scalar() or 0
                return {"total_prs": prs_cnt, "total_engineers": engs_cnt, "total_reports": reps_cnt}
        except Exception as e:
            logger.warning(f"Error fetching DB stats: {e}")
            return {"total_prs": 0, "total_engineers": 0, "total_reports": 0}


db_service = DatabaseService()
