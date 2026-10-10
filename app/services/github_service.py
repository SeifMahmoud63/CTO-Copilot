import httpx
import logging
from typing import List, Optional, Dict
from datetime import datetime, timezone

from app.core.config import settings
from app.core.enums import PRStatus, UserPromptTemplate
from app.schemas.pr_schema import PRItem
from app.services.llm_service import llm_service

logger = logging.getLogger(__name__)

class GitHubService:
    def __init__(self):
        self.headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28"
        }
        if settings.github_token:
            self.headers["Authorization"] = f"Bearer {settings.github_token}"

        self.repo_url = f"{settings.github_api_url}/repos/{settings.github_repo}"
        # In-memory summary store: pr_id -> {summary, provider, timestamp}
        self.summary_cache: Dict[int, Dict] = {}

    async def get_pull_requests(self, state: str = "all") -> List[PRItem]:
        """Fetch pull requests from GitHub repository."""
        url = f"{self.repo_url}/pulls?state={state}&per_page=30"
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

                    cached = self.summary_cache.get(pr_id, {})
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
                        summary_timestamp=cached.get("timestamp")
                    )
                    pr_items.append(pr_item)

                return pr_items


            except Exception as e:
                logger.error(f"Failed to fetch pull requests: {e}")
                return []

    async def fetch_pr_diff(self, pr_number: int) -> str:
        """Fetch diff content for a pull request."""
        diff_url = f"{self.repo_url}/pulls/{pr_number}"
        diff_headers = {**self.headers, "Accept": "application/vnd.github.v3.diff"}
        async with httpx.AsyncClient() as client:
            try:
                res = await client.get(diff_url, headers=diff_headers, timeout=20.0)
                if res.status_code == 200:
                    # Truncate diff if very long to stay within token limits
                    diff_text = res.text
                    return diff_text[:3500] if len(diff_text) > 3500 else diff_text
                return "Diff not available."
            except Exception as e:
                logger.warning(f"Could not retrieve diff for PR #{pr_number}: {e}")
                return "Diff not available."

    async def summarize_pr(self, pr_number: int, force_refresh: bool = False) -> Optional[PRItem]:
        """Fetch PR details, diff, and generate summary via LLM."""
        url = f"{self.repo_url}/pulls/{pr_number}"
        async with httpx.AsyncClient() as client:
            res = await client.get(url, headers=self.headers, timeout=15.0)
            if res.status_code != 200:
                logger.error(f"Cannot fetch PR #{pr_number}: {res.text}")
                return None
            pr_data = res.json()

        pr_id = pr_data["id"]
        if not force_refresh and pr_id in self.summary_cache:
            cached = self.summary_cache[pr_id]
            return PRItem(
                id=pr_id,
                number=pr_data["number"],
                title=pr_data["title"] or "Untitled",
                author=pr_data.get("user", {}).get("login", "unknown"),
                author_avatar=pr_data.get("user", {}).get("avatar_url"),
                created_at=pr_data["created_at"],
                state=PRStatus(pr_data["state"]),
                html_url=pr_data["html_url"],
                head_branch=pr_data.get("head", {}).get("ref", "unknown"),
                base_branch=pr_data.get("base", {}).get("ref", "main"),
                summary=cached.get("summary"),
                summary_provider=cached.get("provider"),
                summary_timestamp=cached.get("timestamp")
            )

        # Get diff and build prompt
        diff_content = await self.fetch_pr_diff(pr_number)
        prompt = UserPromptTemplate.PR_DIFF_TEMPLATE.value.format(
            title=pr_data["title"],
            author=pr_data.get("user", {}).get("login", "unknown"),
            base_branch=pr_data.get("base", {}).get("ref", "main"),
            head_branch=pr_data.get("head", {}).get("ref", "unknown"),
            description=pr_data.get("body") or "No description provided.",
            diff_excerpt=diff_content
        )

        summary_text, provider = llm_service.generate_pr_summary(prompt)
        now_iso = datetime.now(timezone.utc).isoformat()

        self.summary_cache[pr_id] = {
            "summary": summary_text,
            "provider": provider,
            "timestamp": now_iso
        }

        return PRItem(
            id=pr_id,
            number=pr_data["number"],
            title=pr_data["title"],
            author=pr_data.get("user", {}).get("login", "unknown"),
            author_avatar=pr_data.get("user", {}).get("avatar_url"),
            created_at=pr_data["created_at"],
            state=PRStatus(pr_data["state"]),
            html_url=pr_data["html_url"],
            head_branch=pr_data.get("head", {}).get("ref", "unknown"),
            base_branch=pr_data.get("base", {}).get("ref", "main"),
            summary=summary_text,
            summary_provider=provider,
            summary_timestamp=now_iso
        )

github_service = GitHubService()
