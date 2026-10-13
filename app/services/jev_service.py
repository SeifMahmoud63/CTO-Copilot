import httpx
import logging
from typing import Optional
from app.core.config import settings

logger = logging.getLogger(__name__)

class JevService:
    def __init__(self):
        self.api_url = settings.jev_api_url
        self.api_key = settings.jev_api_key
        self.model = settings.jev_model

    async def _post_score(
        self, state_text: str, question_key: str, instructions: str, criteria: list
    ) -> Optional[float]:
        """Shared TypeSafe SystemOne scoring call (criteria indices 0-9 -> 1.0-10.0)."""
        if not self.api_key or not state_text:
            return None
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": self.model,
            "state": state_text,
            "questions": {
                question_key: {
                    "type": "score",
                    "instructions": instructions,
                    "criteria": criteria
                }
            }
        }
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(self.api_url, headers=headers, json=payload, timeout=15.0)
                if response.status_code == 200:
                    data = response.json()
                    ans = data.get("answers", {}).get(question_key, {})
                    raw_score = ans.get("score")
                    if raw_score is not None:
                        # JEV returns 0-9 index; map to 1.0-10.0 scale
                        final_score = round(float(raw_score) + 1.0, 1)
                        return min(10.0, max(1.0, final_score))
                logger.warning(f"JEV API returned status {response.status_code}: {response.text}")
                return None
            except Exception as e:
                logger.error(f"Failed to evaluate via Jev: {e}")
                return None

    # JEV payload guard: the decision API is not the 1M-context LLM, so the
    # diff rides along capped while the summary carries the full narrative.
    JEV_DIFF_MAX_CHARS = 12_000

    async def evaluate_impact(self, summary_text: str, diff_excerpt: str = "") -> float:
        """Score PR impact 1.0-10.0 from the diff first, summary as context."""
        state = (summary_text or "").strip()
        diff = (diff_excerpt or "").strip()
        if diff and diff != "Diff not available.":
            state += "\n\n<diff>\n" + diff[:self.JEV_DIFF_MAX_CHARS] + "\n</diff>"
        criteria = [
            "1 - Trivial typo, cosmetic comment, or minor linting tweak",
            "2 - Minor documentation or simple single-line test fix",
            "3 - Small non-critical bug fix or minor UI styling adjustment",
            "4 - Modest utility function, helper addition, or localized component tweak",
            "5 - Moderate feature addition, unit test suite expansion, or medium refactor",
            "6 - Substantial feature addition, new integration service, or component redesign",
            "7 - Significant backend logic, API contract addition, or performance optimization",
            "8 - Major architectural change, authentication update, or database migration",
            "9 - Critical infrastructure overhaul, payment system, or core engine modification",
            "10 - Transformative platform upgrade, critical security vulnerability fix, or high-blast-radius breaking change"
        ]
        score = await self._post_score(
            state,
            "impact_score",
            "Rate the engineering, architectural, and business impact of this pull request from 1 to 10.",
            criteria,
        )
        return score if score is not None else 5.0

    async def evaluate_urgency(self, summary_text: str) -> float:
        """Score how urgently an email needs the CTO's reply (1.0-10.0)."""
        criteria = [
            "1 - Spam, newsletter, or automated notification needing no action",
            "2 - Pure FYI with no reply expected",
            "3 - FYI with light context worth skimming",
            "4 - Routine request with no deadline",
            "5 - Normal request, reply within a few days is fine",
            "6 - Important request with a near deadline",
            "7 - Time-sensitive message, reply today",
            "8 - Urgent blocker or escalation, reply as soon as possible",
            "9 - Critical incident involving the CTO directly",
            "10 - Emergency requiring immediate action"
        ]
        score = await self._post_score(
            summary_text,
            "urgency_score",
            "Rate how urgently this email needs the CTO's reply from 1 to 10.",
            criteria,
        )
        return score if score is not None else 5.0

jev_service = JevService()
