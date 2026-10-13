"""Unit tests for Slack Bot integration (SLA alerts, modern PDF file uploads, API routes)."""
import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.core import config as config_module
from app.main import app
from app.services.slack_service import SlackService, slack_service


class DummyPR:
    def __init__(self, number=10, title="Fix Redis TTL", author="seif", is_overdue=True, overdue_days=9):
        self.number = number
        self.title = title
        self.author = author
        self.html_url = f"https://github.com/org/repo/pull/{number}"
        self.base_branch = "main"
        self.is_overdue = is_overdue
        self.overdue_days = overdue_days


@pytest.mark.asyncio
async def test_slack_disabled_skips_gracefully():
    service = SlackService()
    with patch.object(config_module.settings, "slack_enabled", False):
        res1 = await service.send_message("test")
        assert res1["ok"] is False
        assert res1["skipped"] is True

        res2 = await service.send_sla_alert(DummyPR())
        assert res2["ok"] is False
        assert res2["skipped"] is True

        res3 = await service.upload_daily_report("nonexistent.pdf")
        assert res3["ok"] is False
        assert res3["skipped"] is True

        res4 = await service.check_and_notify_overdue_prs([DummyPR()])
        assert res4 == []


@pytest.mark.asyncio
async def test_slack_send_message_success():
    service = SlackService()
    fake_response = MagicMock()
    fake_response.json.return_value = {"ok": True, "ts": "123.456"}

    with patch.object(config_module.settings, "slack_enabled", True), \
         patch.object(config_module.settings, "slack_bot_token", "xoxb-test-token"), \
         patch.object(config_module.settings, "slack_channel_id", "C123456"), \
         patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = fake_response

        result = await service.send_message("Hello CTO Copilot", channel="C123456")
        assert result["ok"] is True
        mock_post.assert_called_once()
        call_kwargs = mock_post.call_args[1]
        assert call_kwargs["json"]["channel"] == "C123456"
        assert call_kwargs["json"]["text"] == "Hello CTO Copilot"
        assert "Bearer xoxb-test-token" in call_kwargs["headers"]["Authorization"]


@pytest.mark.asyncio
async def test_slack_send_sla_alert_blocks():
    service = SlackService()
    fake_response = MagicMock()
    fake_response.json.return_value = {"ok": True, "ts": "123.456"}

    pr = DummyPR(number=77, title="Add Circuit Breaker", author="dev_lead", is_overdue=True, overdue_days=12)

    with patch.object(config_module.settings, "slack_enabled", True), \
         patch.object(config_module.settings, "slack_bot_token", "xoxb-test-token"), \
         patch.object(config_module.settings, "slack_channel_id", "C123456"), \
         patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = fake_response

        result = await service.send_sla_alert(pr)
        assert result["ok"] is True
        call_kwargs = mock_post.call_args[1]
        blocks = call_kwargs["json"]["blocks"]
        assert len(blocks) >= 3
        # Check header
        assert "SLA Breach Detected" in blocks[0]["text"]["text"]
        # Check section details
        assert "#77 Add Circuit Breaker" in blocks[1]["text"]["text"]
        assert "12 days" in blocks[1]["text"]["text"]
        assert "@dev_lead" in blocks[1]["text"]["text"]


@pytest.mark.asyncio
async def test_slack_upload_daily_report_workflow(tmp_path):
    service = SlackService()
    test_pdf = tmp_path / "daily-report-test.pdf"
    test_pdf.write_bytes(b"%PDF-1.4 test binary data")

    step1_resp = MagicMock()
    step1_resp.json.return_value = {
        "ok": True,
        "upload_url": "https://files.slack.com/upload/v1/test",
        "file_id": "F_TEST_123",
    }

    step2_resp = MagicMock()
    step2_resp.status_code = 200

    step3_resp = MagicMock()
    step3_resp.json.return_value = {"ok": True, "files": [{"id": "F_TEST_123"}]}

    with patch.object(config_module.settings, "slack_enabled", True), \
         patch.object(config_module.settings, "slack_bot_token", "xoxb-test-token"), \
         patch.object(config_module.settings, "slack_channel_id", "C123456"), \
         patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get, \
         patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_get.return_value = step1_resp
        mock_post.side_effect = [step2_resp, step3_resp]

        res = await service.upload_daily_report(
            pdf_path=str(test_pdf),
            title="CTO Daily Report — Test",
            summary="All systems nominal.",
            channel="C123456",
        )
        assert res["ok"] is True
        mock_get.assert_called_once()
        assert mock_post.call_count == 2


@pytest.mark.asyncio
async def test_slack_upload_daily_report_missing_file():
    service = SlackService()
    with patch.object(config_module.settings, "slack_enabled", True), \
         patch.object(config_module.settings, "slack_bot_token", "xoxb-test-token"), \
         patch.object(config_module.settings, "slack_channel_id", "C123456"):
        res = await service.upload_daily_report(pdf_path="/path/to/missing_file.pdf")
        assert res["ok"] is False
        assert "File not found" in res["error"]


@pytest.mark.asyncio
async def test_slack_check_and_notify_overdue_prs():
    service = SlackService()
    prs = [
        DummyPR(number=1, is_overdue=False),
        DummyPR(number=2, is_overdue=True, overdue_days=10),
        DummyPR(number=3, is_overdue=False),
        DummyPR(number=4, is_overdue=True, overdue_days=8),
    ]

    with patch.object(config_module.settings, "slack_enabled", True), \
         patch.object(config_module.settings, "slack_bot_token", "xoxb-test"), \
         patch.object(service, "send_sla_alert", new_callable=AsyncMock) as mock_alert:
        mock_alert.return_value = {"ok": True}
        results = await service.check_and_notify_overdue_prs(prs)
        assert len(results) == 2
        assert mock_alert.call_count == 2


def test_slack_api_routes():
    client = TestClient(app)

    with patch("app.services.auth_service.verify_session_cookie", return_value=True), \
         patch.object(config_module.settings, "slack_enabled", True), \
         patch.object(config_module.settings, "slack_bot_token", "xoxb-test"), \
         patch.object(config_module.settings, "slack_channel_id", "C_TEST"):

        # 1. Status route
        res = client.get("/api/slack/status")
        assert res.status_code == 200
        data = res.json()
        assert data["enabled"] is True
        assert data["channel_id"] == "C_TEST"

        # 2. Test send route
        with patch.object(slack_service, "send_message", new_callable=AsyncMock) as mock_send:
            mock_send.return_value = {"ok": True, "ts": "111"}
            res = client.post("/api/slack/test")
            assert res.status_code == 200
            assert res.json()["ok"] is True

        # 3. Notify overdue route
        with patch.object(slack_service, "check_and_notify_overdue_prs", new_callable=AsyncMock) as mock_notify:
            mock_notify.return_value = [{"ok": True}]
            res = client.post("/api/slack/notify-overdue")
            assert res.status_code == 200
            assert res.json()["alerts_sent"] == 1
