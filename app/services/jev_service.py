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

    async def evaluate_impact(self, summary_text: str) -> float:
        """
        Uses TypeSafe AI Jev System One decision model to rate PR impact on a 1.0 to 10.0 scale.
        """
        if not self.api_key or not summary_text:
            return 5.0

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

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

        payload = {
            "model": self.model,
            "state": summary_text,
            "questions": {
                "impact_score": {
                    "type": "score",
                    "instructions": "Rate the engineering, architectural, and business impact of this pull request from 1 to 10.",
                    "criteria": criteria
                }
            }
        }

        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(self.api_url, headers=headers, json=payload, timeout=15.0)
                if response.status_code == 200:
                    data = response.json()
                    ans = data.get("answers", {}).get("impact_score", {})
                    raw_score = ans.get("score")
                    if raw_score is not None:
                        # Jev criteria indices are 0 to 9, so score + 1 gives 1.0 to 10.0 scale
                        final_score = round(float(raw_score) + 1.0, 1)
                        return min(10.0, max(1.0, final_score))
                logger.warning(f"JEV API returned status {response.status_code}: {response.text}")
                return 5.0
            except Exception as e:
                logger.error(f"Failed to evaluate PR impact via Jev: {e}")
                return 5.0

jev_service = JevService()
