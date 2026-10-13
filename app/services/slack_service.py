"""Slack Bot service: SLA breach alerts and daily PDF executive report uploads."""
from __future__ import annotations

import logging
import os
from typing import Any, Dict, List, Optional
from urllib.parse import urlencode

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)


class SlackService:
    """Handles communication with the Slack Web API using a Bot User OAuth Token (xoxb-...)."""

    def __init__(self):
        self.api_base = "https://slack.com/api"

    @property
    def is_enabled(self) -> bool:
        return bool(settings.slack_enabled and settings.slack_bot_token.strip())

    @property
    def default_channel(self) -> str:
        return settings.slack_channel_id.strip()

    def _get_headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {settings.slack_bot_token.strip()}",
            "Content-Type": "application/json; charset=utf-8",
        }

    async def send_message(
        self,
        text: str,
        blocks: Optional[List[Dict[str, Any]]] = None,
        channel: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Send a formatted message or Block Kit payload to a Slack channel."""
        if not self.is_enabled:
            logger.info("Slack service is disabled or token is missing; skipping send_message.")
            return {"ok": False, "skipped": True, "reason": "slack_disabled"}

        target_channel = (channel or self.default_channel).strip()
        if not target_channel:
            logger.warning("No Slack channel specified; skipping send_message.")
            return {"ok": False, "skipped": True, "reason": "missing_channel"}

        payload: Dict[str, Any] = {
            "channel": target_channel,
            "text": text,
        }
        if blocks:
            payload["blocks"] = blocks

        url = f"{self.api_base}/chat.postMessage"
        async with httpx.AsyncClient(timeout=15.0) as client:
            try:
                response = await client.post(url, json=payload, headers=self._get_headers())
                data = response.json()
                if not data.get("ok"):
                    logger.error(f"Slack postMessage failed: {data.get('error')}")
                return data
            except Exception as exc:
                logger.error(f"Network error calling Slack postMessage: {exc}")
                return {"ok": False, "error": str(exc)}

    async def send_sla_alert(
        self,
        pr: Any,
        channel: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Dispatch a high-visibility SLA breach notification for an overdue Pull Request."""
        if not self.is_enabled:
            return {"ok": False, "skipped": True, "reason": "slack_disabled"}

        # Extract attributes from PRItem or dict
        pr_number = getattr(pr, "number", None) or (pr.get("number") if isinstance(pr, dict) else "?")
        pr_title = getattr(pr, "title", None) or (pr.get("title") if isinstance(pr, dict) else "Untitled PR")
        pr_author = getattr(pr, "author", None) or (pr.get("author") if isinstance(pr, dict) else "unknown")
        pr_url = getattr(pr, "html_url", None) or (pr.get("html_url") if isinstance(pr, dict) else "")
        pr_branch = getattr(pr, "base_branch", None) or (pr.get("base_branch") if isinstance(pr, dict) else "main")
        overdue_days = getattr(pr, "overdue_days", None) or (pr.get("overdue_days") if isinstance(pr, dict) else 0)

        threshold = settings.pr_stale_threshold_days
        headline = f"🚨 *SLA Breach Alert: PR #{pr_number} is Overdue!*"
        plain_text = f"SLA Breach Alert: PR #{pr_number} '{pr_title}' by @{pr_author} is overdue ({overdue_days} days)."

        blocks: List[Dict[str, Any]] = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": "🚨 SLA Breach Detected — Action Required",
                    "emoji": True,
                },
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": (
                        f"*<{pr_url}|#{pr_number} {pr_title}>*\n"
                        f"This pull request has exceeded the engineering review SLA limit.\n"
                        f"• *Age / Overdue:* `{overdue_days} days` (Threshold: `{threshold} days`)\n"
                        f"• *Author:* `@{pr_author}`\n"
                        f"• *Base Branch:* `{pr_branch}`\n"
                        f"• *Repository:* `{settings.github_repo}`"
                    ),
                },
            },
            {
                "type": "actions",
                "elements": [
                    {
                        "type": "button",
                        "text": {
                            "type": "plain_text",
                            "text": "Review on GitHub",
                            "emoji": True,
                        },
                        "url": pr_url or f"https://github.com/{settings.github_repo}/pull/{pr_number}",
                        "style": "danger",
                    }
                ],
            },
            {
                "type": "context",
                "elements": [
                    {
                        "type": "mrkdwn",
                        "text": f"🛰️ *CTO Copilot SLA Monitor* • Alert generated automatically",
                    }
                ],
            },
        ]

        return await self.send_message(text=plain_text, blocks=blocks, channel=channel)

    async def upload_daily_report(
        self,
        pdf_path: str,
        title: Optional[str] = None,
        summary: Optional[str] = None,
        channel: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Upload a generated daily PDF report to Slack using modern files.uploadV2 external flow.

        pdf_path may be an s3:// URI (MinIO — normal path) or a legacy local path.
        """
        if not self.is_enabled:
            logger.info("Slack service disabled; skipping PDF report upload.")
            return {"ok": False, "skipped": True, "reason": "slack_disabled"}

        target_channel = (channel or self.default_channel).strip()
        if not target_channel:
            logger.warning("No target Slack channel for report upload.")
            return {"ok": False, "skipped": True, "reason": "missing_channel"}

        try:
            if pdf_path.startswith("s3://"):
                from app.services.storage_service import storage_service

                file_bytes = storage_service.download_uri(pdf_path)
                filename = pdf_path.rsplit("/", 1)[-1]
            elif os.path.exists(pdf_path):
                with open(pdf_path, "rb") as f:
                    file_bytes = f.read()
                filename = os.path.basename(pdf_path)
            else:
                logger.error(f"Cannot upload PDF report to Slack: File not found at {pdf_path}")
                return {"ok": False, "error": f"File not found: {pdf_path}"}
        except Exception as exc:
            logger.error(f"Failed reading PDF report file {pdf_path}: {exc}")
            return {"ok": False, "error": str(exc)}

        return await self.upload_report_bytes(
            file_bytes=file_bytes, filename=filename,
            title=title, summary=summary, channel=channel,
        )

    async def upload_report_bytes(
        self,
        file_bytes: bytes,
        filename: str,
        title: Optional[str] = None,
        summary: Optional[str] = None,
        channel: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Upload raw PDF bytes (already fetched from MinIO) to Slack."""
        if not self.is_enabled:
            return {"ok": False, "skipped": True, "reason": "slack_disabled"}

        target_channel = (channel or self.default_channel).strip()
        if not target_channel:
            return {"ok": False, "skipped": True, "reason": "missing_channel"}
        file_len = len(file_bytes)
        report_title = title or f"CTO Daily Executive Report — {filename}"

        comment_snippet = ""
        if summary:
            # First 350 chars of executive summary
            snippet = summary.strip().split("\n")[0]
            if len(snippet) > 350:
                snippet = snippet[:347] + "..."
            comment_snippet = f"\n> {snippet}"

        initial_comment = (
            f":bar_chart: *Executive Briefing: Daily CTO Report Ready!*\n"
            f"Attached is the comprehensive engineering health report for today.{comment_snippet}"
        )

        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                # Step 1: getUploadURLExternal
                step1_params = urlencode({"filename": filename, "length": file_len})
                step1_url = f"{self.api_base}/files.getUploadURLExternal?{step1_params}"
                step1_res = await client.get(
                    step1_url,
                    headers={"Authorization": f"Bearer {settings.slack_bot_token.strip()}"},
                )
                step1_data = step1_res.json()
                if not step1_data.get("ok"):
                    logger.error(f"files.getUploadURLExternal failed: {step1_data}")
                    return step1_data

                upload_url = step1_data["upload_url"]
                file_id = step1_data["file_id"]

                # Step 2: POST binary content to upload URL
                step2_res = await client.post(upload_url, content=file_bytes)
                if step2_res.status_code not in (200, 201):
                    logger.error(f"Slack file binary upload failed with status {step2_res.status_code}")
                    return {"ok": False, "error": f"Upload URL returned status {step2_res.status_code}"}

                # Step 3: completeUploadExternal
                complete_payload = {
                    "files": [{"id": file_id, "title": report_title}],
                    "channel_id": target_channel,
                    "initial_comment": initial_comment,
                }
                step3_res = await client.post(
                    f"{self.api_base}/files.completeUploadExternal",
                    json=complete_payload,
                    headers=self._get_headers(),
                )
                step3_data = step3_res.json()
                if step3_data.get("ok"):
                    logger.info(f"Successfully uploaded PDF report {filename} to Slack channel {target_channel}")
                else:
                    logger.error(f"files.completeUploadExternal failed: {step3_data}")
                return step3_data

            except Exception as exc:
                logger.error(f"Exception during Slack file upload: {exc}")
                return {"ok": False, "error": str(exc)}

    async def check_and_notify_overdue_prs(
        self,
        prs: Optional[List[Any]] = None,
        channel: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Scan PR items for overdue breaches and send SLA alerts."""
        if not self.is_enabled:
            return []

        if prs is None:
            from app.services.github_service import github_service
            prs = await github_service.get_pull_requests(state="open")

        results = []
        for pr in prs:
            is_overdue = bool(getattr(pr, "is_overdue", False) or (isinstance(pr, dict) and pr.get("is_overdue")))
            if is_overdue:
                res = await self.send_sla_alert(pr=pr, channel=channel)
                results.append(res)
        return results


slack_service = SlackService()
