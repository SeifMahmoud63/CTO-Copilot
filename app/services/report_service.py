"""Daily CTO report pipeline (hybrid): deterministic 24h metrics + AI analysis + PDF."""
import json
import logging
import os
import re
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from zoneinfo import ZoneInfo

logger = logging.getLogger("cto-copilot.reports")

RTL_RE = re.compile(r"[\u0591-\u07FF\uFB1D-\uFDFD\uFE70-\uFEFC]")


def _parse_dt(value: Any):
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        return None


def _state_of(pr: Any) -> str:
    state = getattr(pr, "state", "open")
    return (state.value if hasattr(state, "value") else str(state)).lower()


def collect_daily_metrics(
    pr_items: List[Any],
    engineers: List[Dict[str, Any]],
    now: datetime,
    threshold_days: int,
) -> Dict[str, Any]:
    """Pure 24h metrics extraction (deterministic, 100% safe, no LLM).

    - opened: created in the last 24h.
    - merged/closed in window: state matches AND updated in the last 24h
      (approximation — the list API carries no closed_at/merged_at).
    - newly_overdue: open PRs whose age exactly hit the SLA threshold today.
    """
    window_start = now - timedelta(hours=24)

    def created(p):
        return _parse_dt(getattr(p, "created_at", None))

    def updated(p):
        return _parse_dt(getattr(p, "updated_at", None)) or created(p)

    opened = [p for p in pr_items if (created(p) or now) >= window_start and created(p)]
    merged = [p for p in pr_items if _state_of(p) == "merged" and (updated(p) or now) >= window_start]
    closed = [p for p in pr_items if _state_of(p) == "closed" and (updated(p) or now) >= window_start]
    newly_overdue = [
        p for p in pr_items
        if _state_of(p) == "open"
        and bool(getattr(p, "is_overdue", False))
        and (getattr(p, "overdue_days", 0) or 0) == threshold_days
    ]

    def brief(p):
        return {
            "number": getattr(p, "number", None),
            "title": getattr(p, "title", ""),
            "author": getattr(p, "author", ""),
            "html_url": getattr(p, "html_url", ""),
            "impact_score": getattr(p, "impact_score", None),
        }

    ranked = sorted(
        [e for e in engineers if (e.get("pr_count") or 0) > 0],
        key=lambda e: (e.get("avg_score") or 0, e.get("total_score") or 0),
    )

    return {
        "generated_at": now.isoformat(),
        "window_hours": 24,
        "threshold_days": threshold_days,
        "counts": {
            "opened_24h": len(opened),
            "merged_24h": len(merged),
            "closed_24h": len(closed),
            "newly_overdue": len(newly_overdue),
            "total_open": sum(1 for p in pr_items if _state_of(p) == "open"),
            "total_merged": sum(1 for p in pr_items if _state_of(p) == "merged"),
        },
        "opened": [brief(p) for p in opened],
        "merged": [brief(p) for p in merged],
        "newly_overdue": [brief(p) for p in newly_overdue],
        "top_engineer": ranked[-1] if ranked else None,
        "low_engineer": ranked[0] if ranked else None,
        "engineers": engineers,
    }


def build_analysis_prompt(metrics: Dict[str, Any], language: str) -> str:
    """Prompt feeding deterministic metrics to the model for deep analysis."""
    return (
        "You are a CTO executive analyst. Below are DETERMINISTIC metrics for the "
        "last 24 hours (already verified — do not recompute them, analyze them).\n\n"
        f"<metrics>\n{json.dumps(metrics, indent=2, ensure_ascii=False)}\n</metrics>\n\n"
        "You may reference pull_requests / engineers tables if you need extra detail, "
        "but prefer these numbers as the source of truth.\n\n"
        f"Write a CTO executive daily report in {language} with these sections:\n"
        "1. Executive Summary (3-4 sentences: velocity, health, biggest risk).\n"
        "2. Bottlenecks (what is stuck and why, names included).\n"
        "3. Recommendations (2-4 concrete next actions for tomorrow).\n"
        "4. Top & Low Performers (who drove impact, who needs support).\n\n"
        "Rules: concise, no filler, keep usernames/branch names/numbers in Latin script, "
        "no markdown tables (plain paragraphs and short bullet lines starting with '- ')."
        "Write ENTIRELY in English: no Arabic (or other non-Latin script) characters anywhere, "
        "no markdown bold/italic markers — plain text only."
    )


def generate_analysis(prompt: str) -> str:
    """Run the executive analysis through the Bedrock/Groq summarizer stack."""
    from app.services.llm_service import llm_service

    try:
        summary_text, _, _ = llm_service.generate_pr_summary(prompt)
        return (summary_text or "").strip()
    except Exception as e:
        logger.warning(f"Report AI analysis failed: {e}")
        return "Executive analysis unavailable (LLM error). Deterministic metrics below remain valid."


def shape_for_pdf(text: str) -> str:
    """Arabic shaping (presentation forms + visual order) for reportlab."""
    if not text or not RTL_RE.search(text):
        return text
    try:
        import arabic_reshaper
        from bidi.algorithm import get_display

        return get_display(arabic_reshaper.reshape(text))
    except Exception:
        return text


def format_generated_label(iso_value: str) -> str:
    """Human-readable generation timestamp with an explicit zone offset.

    Turns '2026-10-11T12:54:09.897330+03:00' into '2026-10-11 12:54 (UTC+03:00)'
    so the PDF never shows a naked ambiguous time. Falls back to raw input.
    """
    if not iso_value:
        return ""
    try:
        dt = datetime.fromisoformat(str(iso_value).replace("Z", "+00:00"))
        base = dt.strftime("%Y-%m-%d %H:%M")
        if dt.tzinfo is not None:
            total_min = int(dt.utcoffset().total_seconds() // 60)
            sign = "+" if total_min >= 0 else "-"
            hh, mm = divmod(abs(total_min), 60)
            return f"{base} (UTC{sign}{hh:02d}:{mm:02d})"
        return f"{base} (UTC)"
    except Exception:
        return str(iso_value)


def strip_markdown(text: str) -> str:
    """Remove leftover markdown so it never leaks literally into the PDF."""
    if not text:
        return text
    text = re.sub(r"^#{1,6}\s+", "", text, flags=re.MULTILINE)
    text = re.sub(r"\*\*([^*]+)\*\*", r"\1", text)
    text = re.sub(r"(?<!\*)\*([^*\n]+)\*(?!\*)", r"\1", text)
    text = re.sub(r"`([^`]+)`", r"\1", text)
    return text


def _register_fonts() -> Dict[str, str]:
    """Register Amiri (Arabic-capable) if bundled, else fall back to Helvetica."""
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont

    candidates = [
        os.path.join(os.path.dirname(__file__), "fonts", "Amiri-Regular.ttf"),
        "/usr/share/fonts/truetype/amiri/Amiri-Regular.ttf",
    ]
    for path in candidates:
        if os.path.exists(path):
            try:
                pdfmetrics.registerFont(TTFont("ReportFont", path))
                return {"regular": "ReportFont", "bold": "ReportFont"}
            except Exception as e:
                logger.warning(f"Could not register font {path}: {e}")
    return {"regular": "Helvetica", "bold": "Helvetica-Bold"}


def build_pdf(
    report_date_str: str,
    title: str,
    metrics: Dict[str, Any],
    analysis: str,
    out_path: str,
) -> str:
    """Render the daily report PDF (reportlab platypus). Returns out_path."""
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle

    fonts = _register_fonts()
    counts = metrics.get("counts", {})

    def para(text: str, size: int = 10, leading: int = 14, space_after: int = 6,
             text_color=colors.HexColor("#0f172a"), bold: bool = False) -> Paragraph:
        rtl = bool(text and RTL_RE.search(text))
        font = fonts["bold"] if bold else fonts["regular"]
        # Maintain logical order for shaped RTL; align right
        body = shape_for_pdf(text) if rtl else (text or "")
        style = ParagraphStyle(
            f"s_{size}_{bold}_{rtl}", fontName=font, fontSize=size, leading=leading,
            textColor=text_color, spaceAfter=space_after,
            alignment=2 if rtl else 0,
        )
        return Paragraph(body.replace("\n", "<br/>"), style)

    def cell(text: Any, header: bool = False) -> Paragraph:
        t = "" if text is None else str(text)
        rtl = bool(RTL_RE.search(t))
        font = fonts["regular"]
        body = shape_for_pdf(t) if rtl else t
        # Explicit white text on headers since Paragraph style overrides TableStyle TEXTCOLOR
        return Paragraph(
            body,
            ParagraphStyle(f"c_{rtl}_{header}", fontName=font, fontSize=9, leading=12,
                           textColor=colors.white if header else colors.HexColor("#0f172a"),
                           alignment=2 if rtl else 0),
        )

    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
    doc = SimpleDocTemplate(
        out_path, pagesize=A4,
        leftMargin=18 * mm, rightMargin=18 * mm, topMargin=16 * mm, bottomMargin=16 * mm,
        title=title, author="CTO Copilot",
    )

    story = [
        para(title, size=18, leading=22, space_after=2, bold=True),
        para(f"Date: {report_date_str}  •  Generated: {format_generated_label(metrics.get('generated_at', ''))}",
             size=9, leading=12, text_color=colors.HexColor("#64748b"), space_after=10),
    ]

    kpi_data = [
        [cell("Opened (24h)", header=True), cell("Merged (24h)", header=True),
         cell("Closed (24h)", header=True),
         cell("Newly Overdue", header=True), cell("Open Total", header=True)],
        [cell(counts.get("opened_24h", 0)), cell(counts.get("merged_24h", 0)),
         cell(counts.get("closed_24h", 0)), cell(counts.get("newly_overdue", 0)),
         cell(counts.get("total_open", 0))],
    ]
    kpi = Table(kpi_data, colWidths=[32 * mm] * 5)
    kpi.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0f172a")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f8fafc")]),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    story += [para("Key Metrics (last 24h)", size=13, leading=16, bold=True, space_after=4), kpi, Spacer(1, 8)]

    engs = metrics.get("engineers") or []
    if engs:
        rows = [[cell("Engineer", header=True), cell("PRs", header=True),
                 cell("Total", header=True), cell("Avg", header=True),
                 cell("Tier", header=True)]]
        for e in sorted(engs, key=lambda x: (x.get("total_score") or 0), reverse=True):
            rows.append([cell(e.get("author")), cell(e.get("pr_count")),
                         cell(e.get("total_score")), cell(e.get("avg_score")), cell(e.get("tier"))])
        t = Table(rows, colWidths=[52 * mm, 22 * mm, 28 * mm, 28 * mm, 44 * mm])
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1d4ed8")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#eff6ff")]),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ]))
        story += [para("Engineers", size=13, leading=16, bold=True, space_after=4), t, Spacer(1, 8)]

    overdue = metrics.get("newly_overdue") or []
    story.append(para("Newly Overdue PRs", size=13, leading=16, bold=True, space_after=4))
    if overdue:
        for p in overdue:
            story.append(para(f"- #{p.get('number')} {p.get('title', '')} — {p.get('author', '')} ({p.get('html_url', '')})",
                              size=10, leading=13, space_after=3))
    else:
        story.append(para("None — no PR crossed the SLA threshold today.", size=10, leading=13))

    story += [Spacer(1, 8), para("Executive Analysis", size=13, leading=16, bold=True, space_after=4)]
    for chunk in (analysis or "").split("\n"):
        chunk = strip_markdown(chunk.strip())
        if chunk:
            story.append(para(chunk, size=10, leading=14, space_after=5))

    doc.build(story)
    return out_path


async def generate_daily_report(report_date_str: Optional[str] = None) -> Dict[str, Any]:
    """Full pipeline: metrics -> AI analysis -> PDF -> DB upsert. Returns the record."""
    from zoneinfo import ZoneInfo

    from app.core.config import settings
    from app.services.db_service import db_service
    from app.services.github_service import github_service

    tz = ZoneInfo(settings.report_timezone)
    now = datetime.now(tz)
    day = report_date_str or now.date().isoformat()
    threshold = settings.pr_stale_threshold_days
    language = settings.report_language

    pr_items = await github_service.get_pull_requests(state="all")
    engineers = await db_service.get_engineers()

    metrics = collect_daily_metrics(pr_items, engineers, now, threshold)
    analysis = generate_analysis(build_analysis_prompt(metrics, language))

    reports_dir = settings.reports_dir
    os.makedirs(reports_dir, exist_ok=True)
    pdf_path = os.path.abspath(os.path.join(reports_dir, f"daily-report-{day}.pdf"))
    build_pdf(day, f"CTO Daily Report — {day}", metrics, analysis, pdf_path)

    record = await db_service.save_report(
        report_date=day,
        title=f"CTO Daily Report — {day}",
        executive_summary=analysis,
        metrics_json=json.dumps(metrics, ensure_ascii=False),
        pdf_path=pdf_path,
        prs_opened=metrics["counts"]["opened_24h"],
        prs_merged=metrics["counts"]["merged_24h"],
        prs_closed=metrics["counts"]["closed_24h"],
        overdue_count=metrics["counts"]["newly_overdue"],
    )
    return {
        "id": record.id if record else None,
        "report_date": day,
        "title": f"CTO Daily Report — {day}",
        "pdf_path": pdf_path,
        "metrics": metrics,
        "executive_summary": analysis,
    }
