from datetime import datetime, date
from typing import Optional
from sqlalchemy import String, Integer, Text, Date, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base

class DailyReport(Base):
    """Daily CTO report record: metadata + executive summary + PDF path."""
    __tablename__ = "daily_reports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    report_date: Mapped[date] = mapped_column(Date, unique=True, index=True, nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    executive_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    metrics_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    pdf_path: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    prs_opened: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    prs_merged: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    prs_closed: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    overdue_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), nullable=False)
