"""Email triage: IMAP polling (strictly read-only) -> AI summary -> JEV urgency.

Pipeline per new message (mirrors PR intelligence):
1. Fetch UNSEEN (or recent) messages from the configured mailbox.
2. Summarize via the Bedrock/Groq stack with the email system prompt.
3. Score reply-urgency 1-10 via the JEV decision model -> urgency tier.
4. Upsert into the `emails` table (dedupe by Message-ID; never re-pay for
   already-summarized mail).

The mailbox is opened IMAP ``readonly=True``: nothing is ever marked read,
moved, or deleted by this service.
"""
import asyncio
import email as email_pkg
import imaplib
import logging
from datetime import datetime, timezone
from email.header import decode_header
from email.utils import parsedate_to_datetime
from typing import Any, Dict, List, Optional

from app.core.config import settings
from app.core.enums import SystemPrompt

logger = logging.getLogger("cto-copilot.email")


def urgency_tier_for(score: Optional[float]) -> str:
    """Urgency label shared by email rows (mirrors impact_tier_for)."""
    if score is None:
        return "FYI / Soon"
    if score >= 8.0:
        return "Reply Now"
    if score >= 6.5:
        return "Reply Today"
    if score >= 5.0:
        return "FYI / Soon"
    return "Archive"


def _decode_header_value(raw: Optional[str]) -> str:
    if not raw:
        return ""
    parts = []
    for chunk, charset in decode_header(raw):
        if isinstance(chunk, bytes):
            try:
                parts.append(chunk.decode(charset or "utf-8", errors="replace"))
            except Exception:
                parts.append(chunk.decode("utf-8", errors="replace"))
        else:
            parts.append(chunk)
    return "".join(parts).strip()


def _extract_plain_body(msg: Any, max_chars: int) -> str:
    """Best-effort text/plain extraction (multipart walked, HTML ignored)."""
    chunks: List[str] = []
    try:
        if msg.is_multipart():
            for part in msg.walk():
                if part.get_content_maintype() != "text":
                    continue
                if part.get_content_subtype() != "plain":
                    continue
                if part.get_filename():
                    continue  # attachment with text type
                payload = part.get_payload(decode=True)
                if not payload:
                    continue
                charset = part.get_content_charset() or "utf-8"
                try:
                    chunks.append(payload.decode(charset, errors="replace"))
                except Exception:
                    chunks.append(payload.decode("utf-8", errors="replace"))
        else:
            payload = msg.get_payload(decode=True)
            if isinstance(payload, bytes):
                chunks.append(payload.decode(msg.get_content_charset() or "utf-8", errors="replace"))
            elif isinstance(payload, str):
                chunks.append(payload)
    except Exception as e:
        logger.debug(f"Body extraction failed: {e}")
    text = "\n".join(c.strip() for c in chunks if c and c.strip())
    return text[:max_chars]


def _parse_email_date(value: Optional[str]) -> Optional[datetime]:
    """Email Date header -> naive UTC datetime (same convention as PR dates)."""
    if not value:
        return None
    try:
        dt = parsedate_to_datetime(value)
        if dt is None:
            return None
        if dt.tzinfo is not None:
            dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
        return dt
    except Exception:
        return None


def parse_email_bytes(raw: bytes, max_chars: int) -> Dict[str, Any]:
    """Parse one RFC822 message into a plain dict (pure function, testable)."""
    msg = email_pkg.message_from_bytes(raw)
    message_id = (msg.get("Message-ID") or "").strip()
    sender = _decode_header_value(msg.get("From"))
    subject = _decode_header_value(msg.get("Subject"))
    sent_at = _parse_email_date(msg.get("Date"))
    body = _extract_plain_body(msg, max_chars)
    snippet = " ".join(body.split())[:200] if body else _decode_header_value(msg.get("Subject"))[:200]
    return {
        "message_id": message_id,
        "sender": sender or "unknown",
        "subject": subject or "(no subject)",
        "sent_at": sent_at,
        "snippet": snippet,
        "body": body,
    }


def fetch_recent_emails(
    host: str,
    port: int,
    address: str,
    password: str,
    mailbox: str,
    unread_only: bool,
    limit: int,
    max_chars: int,
) -> List[Dict[str, Any]]:
    """Blocking IMAP fetch (run inside a thread). Read-only mailbox."""
    conn = imaplib.IMAP4_SSL(host, port)
    try:
        conn.login(address, password)
        typ, _ = conn.select(mailbox, readonly=True)
        if typ != "OK":
            raise ConnectionError(f"Cannot open mailbox '{mailbox}'.")
        criterion = "(UNSEEN)" if unread_only else "ALL"
        typ, data = conn.search(None, criterion)
        if typ != "OK":
            raise ConnectionError("IMAP search failed.")
        ids = data[0].split()
        ids = ids[-max(1, limit):]
        out: List[Dict[str, Any]] = []
        for num in reversed(ids):  # newest first
            typ, msg_data = conn.fetch(num, "(RFC822)")
            if typ != "OK" or not msg_data or not isinstance(msg_data[0], tuple):
                continue
            parsed = parse_email_bytes(msg_data[0][1], max_chars)
            if not parsed["message_id"]:
                parsed["message_id"] = f"{mailbox}-{num.decode(errors='replace')}"
            out.append(parsed)
        return out
    finally:
        try:
            conn.close()
        except Exception:
            pass
        try:
            conn.logout()
        except Exception:
            pass


def build_email_prompt(parsed: Dict[str, Any]) -> str:
    sent = parsed["sent_at"].isoformat() if parsed.get("sent_at") else "unknown date"
    return (
        f"From: {parsed.get('sender', 'unknown')}\n"
        f"Subject: {parsed.get('subject', '(no subject)')}\n"
        f"Date: {sent}\n\n"
        f"{parsed.get('body') or '(empty body)'}"
    )


class EmailService:
    async def poll_inbox(self, limit: int = 25) -> Dict[str, Any]:
        """One polling round: fetch -> summarize new -> score -> store.

        Returns counts. Raises ConnectionError when the mailbox is unreachable
        (API layer maps it to 503; the beat task retries it).
        """
        if not settings.email_enabled:
            return {"status": "disabled", "fetched": 0, "new": 0, "summarized": 0}
        if not settings.email_address or not settings.email_password:
            return {"status": "unconfigured", "fetched": 0, "new": 0, "summarized": 0}

        from app.services.db_service import db_service
        from app.services.jev_service import jev_service
        from app.services.llm_service import llm_service

        try:
            fetched = await asyncio.to_thread(
                fetch_recent_emails,
                settings.email_imap_host,
                settings.email_imap_port,
                settings.email_address,
                settings.email_password,
                settings.email_mailbox,
                settings.email_unread_only,
                limit,
                settings.email_max_body_chars,
            )
        except (imaplib.IMAP4.error, OSError, ConnectionError) as e:
            raise ConnectionError(f"Mailbox unreachable: {e}")

        new_count = 0
        summarized_count = 0
        for item in fetched:
            try:
                existing = await db_service.get_email_by_message_id(item["message_id"])
            except Exception as e:
                logger.debug(f"DB lookup bypassed: {e}")
                existing = None
            if existing and existing.get("summary_text"):
                continue  # already triaged — never re-pay
            new_count += 1
            try:
                summary_text, provider, _ = llm_service.generate_pr_summary(
                    build_email_prompt(item),
                    system_prompt=SystemPrompt.EMAIL_SUMMARIZER.value,
                )
            except Exception as e:
                logger.warning(f"Email summarization failed ({item['message_id']}): {e}")
                continue
            try:
                urgency = await jev_service.evaluate_urgency(summary_text)
            except Exception as e:
                logger.warning(f"Urgency scoring failed ({item['message_id']}): {e}")
                urgency = 5.0
            provider_name = provider.value if hasattr(provider, "value") else str(provider)
            try:
                await db_service.save_or_update_email(
                    message_id=item["message_id"],
                    sender=item["sender"],
                    subject=item["subject"],
                    sent_at=item["sent_at"],
                    snippet=item["snippet"],
                    body_excerpt=item["body"] or None,
                    summary_text=summary_text,
                    summary_provider=provider_name,
                    urgency_score=urgency,
                    urgency_tier=urgency_tier_for(urgency),
                )
                summarized_count += 1
            except Exception as e:
                logger.debug(f"DB email save bypassed: {e}")
        return {
            "status": "completed",
            "fetched": len(fetched),
            "new": new_count,
            "summarized": summarized_count,
        }


email_service = EmailService()


async def poll_inbox(limit: int = 25) -> Dict[str, Any]:
    """Module entrypoint (beat task + API share it)."""
    return await email_service.poll_inbox(limit=limit)
