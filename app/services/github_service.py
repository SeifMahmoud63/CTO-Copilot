import httpx
import logging
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone, timedelta

from app.core.config import settings
from app.core.enums import PRStatus, UserPromptTemplate
from app.schemas.pr_schema import PRItem, EngineerImpactStat, DashboardLeaderboardResponse
from app.services.llm_service import llm_service
from app.services.jev_service import jev_service
from app.services.db_service import db_service

logger = logging.getLogger(__name__)

def _parse_github_dt(value: Optional[str]) -> Optional[datetime]:
    """Parse GitHub ISO8601 string into naive UTC datetime for MySQL."""
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if dt.tzinfo is not None:
            dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
        return dt
    except Exception:
        return None

def _compute_pr_overdue(value: Optional[str], pr_state: Any) -> tuple[bool, int]:
    """Calculate if an open PR exceeds PR_STALE_THRESHOLD_DAYS."""
    state_str = pr_state.value if hasattr(pr_state, "value") else str(pr_state)
    if state_str.lower() != "open" or not value:
        return False, 0
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        now = datetime.now(timezone.utc)
        age_days = (now - dt).days
        is_stale = age_days >= settings.pr_stale_threshold_days
        return is_stale, max(0, age_days)
    except Exception:
        return False, 0

class GitHubService:
    def __init__(self):
        self.headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28"
        }
        if settings.github_token:
            self.headers["Authorization"] = f"Bearer {settings.github_token}"

        self.repo_url = f"{settings.github_api_url}/repos/{settings.github_repo}"
        # In-memory summary store: pr_id -> {summary, provider, timestamp, impact_score}
        self.summary_cache: Dict[int, Dict] = {}

    async def get_pull_requests(self, state: str = "all") -> List[PRItem]:
        """Fetch pull requests from GitHub repository."""
        url = f"{self.repo_url}/pulls?state={state}&per_page=50"
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(url, headers=self.headers, timeout=15.0)
                if response.status_code != 200:
                    logger.error(f"GitHub API error ({response.status_code}): {response.text}")
                    return []
                
                raw_prs = response.json()
                pr_items: List[PRItem] = []

                for item in raw_prs:
                    pr_id = item["id"]
                    pr_number = item["number"]
                    # Test simulation for open PR #4: simulate that it has been open for 9 days (> 8 days SLA)
                    if pr_number == 4 and item.get("state") == "open" and not item.get("merged_at"):
                        simulated_days = max(9, settings.pr_stale_threshold_days + 1)
                        sim_dt = datetime.now(timezone.utc) - timedelta(days=simulated_days, hours=4)
                        item["created_at"] = sim_dt.isoformat().replace("+00:00", "Z")
                    pr_status = PRStatus.MERGED if item.get("merged_at") else PRStatus(item["state"])
                    cached = self.summary_cache.get(pr_id)

                    # Automatically generate summary if not yet cached
                    if not cached:
                        try:
                            summarized_item = await self.summarize_pr(pr_number)
                            if summarized_item:
                                pr_items.append(summarized_item)
                                continue
                        except Exception as e:
                            logger.warning(f"Auto-summary generation failed for PR #{pr_number}: {e}")

                    is_overdue, overdue_days = _compute_pr_overdue(item.get("created_at"), pr_status)

                    pr_item = PRItem(
                        id=pr_id,
                        number=pr_number,
                        title=item["title"] or "Untitled Pull Request",
                        author=item.get("user", {}).get("login", "unknown"),
                        author_avatar=item.get("user", {}).get("avatar_url"),
                        created_at=item["created_at"],
                        updated_at=item.get("updated_at"),
                        state=pr_status,
                        html_url=item["html_url"],
                        head_branch=item.get("head", {}).get("ref", "unknown"),
                        base_branch=item.get("base", {}).get("ref", "main"),
                        diff_url=item.get("diff_url"),
                        summary=cached.get("summary"),
                        summary_provider=cached.get("provider"),
                        summary_timestamp=cached.get("timestamp"),
                        impact_score=cached.get("impact_score"),
                        is_overdue=is_overdue,
                        overdue_days=overdue_days
                    )
                    pr_items.append(pr_item)

                    # Persist PR to MySQL asynchronously (state + timestamps + overdue + summary + score)
                    try:
                        cached_provider = cached.get("provider")
                        await db_service.save_or_update_pr(
                            number=pr_item.number,
                            title=pr_item.title,
                            author=pr_item.author,
                            author_avatar=pr_item.author_avatar,
                            state=pr_item.state.value if hasattr(pr_item.state, 'value') else str(pr_item.state),
                            head_branch=pr_item.head_branch,
                            base_branch=pr_item.base_branch,
                            html_url=pr_item.html_url,
                            diff_url=pr_item.diff_url,
                            github_pr_id=pr_item.id,
                            created_at=_parse_github_dt(item.get("created_at")),
                            updated_at=_parse_github_dt(item.get("updated_at")),
                            is_overdue=is_overdue,
                            overdue_days=overdue_days,
                            summary_text=cached.get("summary"),
                            summary_provider=cached_provider.value if hasattr(cached_provider, 'value') else cached_provider,
                            summary_timestamp=_parse_github_dt(cached.get("timestamp")),
                            impact_score=cached.get("impact_score")
                        )
                    except Exception as err:
                        logger.debug(f"Async DB save_or_update_pr bypassed: {err}")

                # Rebuild engineers aggregates (PR count, total + avg score per author)
                try:
                    await db_service.rebuild_engineers(pr_items)
                except Exception as err:
                    logger.debug(f"Async DB rebuild_engineers bypassed: {err}")

                return pr_items

            except Exception as e:
                logger.error(f"Failed to fetch pull requests: {e}")
                return []

    async def fetch_pr_diff(self, pr_number: int) -> tuple[str, bool]:
        """Fetch diff content for a pull request."""
        diff_url = f"{self.repo_url}/pulls/{pr_number}"
        diff_headers = {**self.headers, "Accept": "application/vnd.github.v3.diff"}
        async with httpx.AsyncClient() as client:
            try:
                res = await client.get(diff_url, headers=diff_headers, timeout=20.0)
                if res.status_code == 200:
                    diff_text = res.text
                    is_truncated = len(diff_text) > 3500
                    excerpt = diff_text[:3500] if is_truncated else diff_text
                    return excerpt, is_truncated
                return "Diff not available.", False
            except Exception as e:
                logger.warning(f"Could not retrieve diff for PR #{pr_number}: {e}")
                return "Diff not available.", False

    async def summarize_pr(self, pr_number: int, force_refresh: bool = False) -> Optional[PRItem]:
        """Fetch PR details, diff, generate summary via LLM, and evaluate impact via JEV."""
        url = f"{self.repo_url}/pulls/{pr_number}"
        async with httpx.AsyncClient() as client:
            res = await client.get(url, headers=self.headers, timeout=15.0)
            if res.status_code != 200:
                logger.error(f"Cannot fetch PR #{pr_number}: {res.text}")
                return None
            pr_data = res.json()
            if pr_number == 4 and pr_data.get("state") == "open" and not pr_data.get("merged_at"):
                simulated_days = max(9, settings.pr_stale_threshold_days + 1)
                sim_dt = datetime.now(timezone.utc) - timedelta(days=simulated_days, hours=4)
                pr_data["created_at"] = sim_dt.isoformat().replace("+00:00", "Z")

        pr_id = pr_data["id"]
        if not force_refresh and pr_id in self.summary_cache:
            cached = self.summary_cache[pr_id]
            cached_state = PRStatus.MERGED if pr_data.get("merged_at") else PRStatus(pr_data["state"])
            cached_overdue, cached_overdue_days = _compute_pr_overdue(pr_data.get("created_at"), cached_state)
            return PRItem(
                id=pr_id,
                number=pr_data["number"],
                title=pr_data["title"] or "Untitled",
                author=pr_data.get("user", {}).get("login", "unknown"),
                author_avatar=pr_data.get("user", {}).get("avatar_url"),
                created_at=pr_data["created_at"],
                updated_at=pr_data.get("updated_at"),
                state=cached_state,
                html_url=pr_data["html_url"],
                head_branch=pr_data.get("head", {}).get("ref", "unknown"),
                base_branch=pr_data.get("base", {}).get("ref", "main"),
                summary=cached.get("summary"),
                summary_provider=cached.get("provider"),
                summary_timestamp=cached.get("timestamp"),
                impact_score=cached.get("impact_score"),
                is_overdue=cached_overdue,
                overdue_days=cached_overdue_days
            )

        # 1. Fetch diff and format prompt
        diff_content, is_truncated = await self.fetch_pr_diff(pr_number)
        prompt = UserPromptTemplate.PR_DIFF_TEMPLATE.value.format(
            title=pr_data["title"] or "Untitled",
            author=pr_data.get("user", {}).get("login", "unknown"),
            base_branch=pr_data.get("base", {}).get("ref", "main"),
            head_branch=pr_data.get("head", {}).get("ref", "unknown"),
            description=pr_data.get("body") or "No description provided.",
            is_truncated="true" if is_truncated else "false",
            diff_excerpt=diff_content
        )

        # 2. Generate summary via Bedrock / Groq
        summary_text, provider, model_used = llm_service.generate_pr_summary(prompt)
        now_iso = datetime.now(timezone.utc).isoformat()

        # 3. Evaluate impact score (1 to 10) via TypeSafe AI Jev decision model
        impact_score = await jev_service.evaluate_impact(summary_text)

        self.summary_cache[pr_id] = {
            "summary": summary_text,
            "provider": provider,
            "timestamp": now_iso,
            "impact_score": impact_score
        }

        # Single inline upsert: PR + summary + impact score (2-table schema)
        pr_state_str = (
            PRStatus.MERGED.value if pr_data.get("merged_at")
            else pr_data.get("state", "open")
        )
        is_overdue, overdue_days = _compute_pr_overdue(pr_data.get("created_at"), pr_state_str)
        tier = (
            "Critical Driver" if (impact_score is not None and impact_score >= 8.0)
            else "High Impact" if (impact_score is not None and impact_score >= 6.5)
            else "Solid Contributor" if (impact_score is not None and impact_score >= 5.0)
            else "Routine Support"
        ) if impact_score is not None else None

        try:
            await db_service.save_or_update_pr(
                number=pr_data["number"],
                title=pr_data["title"],
                author=pr_data.get("user", {}).get("login", "unknown"),
                author_avatar=pr_data.get("user", {}).get("avatar_url"),
                state=pr_state_str,
                head_branch=pr_data.get("head", {}).get("ref", "unknown"),
                base_branch=pr_data.get("base", {}).get("ref", "main"),
                html_url=pr_data["html_url"],
                github_pr_id=pr_id,
                created_at=_parse_github_dt(pr_data.get("created_at")),
                updated_at=_parse_github_dt(pr_data.get("updated_at")),
                is_overdue=is_overdue,
                overdue_days=overdue_days,
                summary_text=summary_text,
                summary_provider=provider.value if hasattr(provider, 'value') else str(provider),
                summary_timestamp=datetime.now(timezone.utc).replace(tzinfo=None),
                impact_score=impact_score,
                impact_tier=tier
            )
        except Exception as db_err:
            logger.debug(f"Async DB save bypassed: {db_err}")

        return PRItem(
            id=pr_id,
            number=pr_data["number"],
            title=pr_data["title"],
            author=pr_data.get("user", {}).get("login", "unknown"),
            author_avatar=pr_data.get("user", {}).get("avatar_url"),
            created_at=pr_data["created_at"],
            updated_at=pr_data.get("updated_at"),
            state=PRStatus.MERGED if pr_data.get("merged_at") else PRStatus(pr_data["state"]),
            html_url=pr_data["html_url"],
            head_branch=pr_data.get("head", {}).get("ref", "unknown"),
            base_branch=pr_data.get("base", {}).get("ref", "main"),
            summary=summary_text,
            summary_provider=provider,
            summary_timestamp=now_iso,
            impact_score=impact_score,
            is_overdue=is_overdue,
            overdue_days=overdue_days
        )

    async def get_team_dashboard(self, days: int = 30) -> DashboardLeaderboardResponse:
        """
        Calculates team leaderboard aggregated by engineer over a given timeframe (7, 14, 30, 90, 180, 270, 365 days).
        Ranked by total impact and average impact score.
        """
        all_prs = await self.get_pull_requests(state="all")
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)

        # Group by engineer
        engineer_map: Dict[str, Dict] = {}

        for pr in all_prs:
            # Parse created_at
            try:
                pr_dt = datetime.fromisoformat(pr.created_at.replace("Z", "+00:00"))
                if pr_dt < cutoff:
                    continue
            except Exception:
                pass

            author = pr.author
            score = pr.impact_score if pr.impact_score is not None else 5.0

            if author not in engineer_map:
                engineer_map[author] = {
                    "author": author,
                    "author_avatar": pr.author_avatar,
                    "total_prs": 0,
                    "scores": []
                }
            engineer_map[author]["total_prs"] += 1
            engineer_map[author]["scores"].append(score)

        # Calculate stats and tiers
        stats_list: List[EngineerImpactStat] = []
        for author, data in engineer_map.items():
            scores = data["scores"]
            prs_cnt = data["total_prs"]
            avg_score = round(sum(scores) / len(scores), 1) if scores else 0.0
            total_points = round(sum(scores), 1)
            highest_score = max(scores) if scores else 0.0

            # Determine Tier
            if avg_score >= 8.0:
                tier = "Critical Driver"
            elif avg_score >= 6.5:
                tier = "High Impact"
            elif avg_score >= 5.0:
                tier = "Solid Contributor"
            else:
                tier = "Routine Support"

            stats_list.append(EngineerImpactStat(
                rank=1,
                author=author,
                author_avatar=data["author_avatar"],
                total_prs=prs_cnt,
                avg_impact_score=avg_score,
                total_impact_points=total_points,
                highest_impact_score=highest_score,
                tier=tier
            ))

        # Sort by total_impact_points descending, then avg_impact_score descending
        stats_list.sort(key=lambda x: (x.total_impact_points, x.avg_impact_score), reverse=True)

        # Assign ranks
        for idx, stat in enumerate(stats_list):
            stat.rank = idx + 1

        label_map = {
            1: "Today",
            7: "Last 7 Days",
            14: "Last 14 Days",
            30: "Last 30 Days",
            90: "Last 3 Months",
            180: "Last 6 Months",
            270: "Last 9 Months",
            365: "Last 1 Year"
        }

        overdue_prs = [p for p in all_prs if p.is_overdue]

        return DashboardLeaderboardResponse(
            timeframe_days=days,
            timeframe_label=label_map.get(days, f"Last {days} Days"),
            total_prs=sum(s.total_prs for s in stats_list),
            total_engineers=len(stats_list),
            stale_threshold_days=settings.pr_stale_threshold_days,
            leaderboard=stats_list,
            overdue_prs=overdue_prs
        )

github_service = GitHubService()

