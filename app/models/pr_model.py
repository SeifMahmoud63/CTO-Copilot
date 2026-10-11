from datetime import datetime
from typing import Optional
from sqlalchemy import String, Integer, BigInteger, DateTime, Boolean, Text, Float, func
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base

class PullRequest(Base):
    """Table 1/2: every pull request with its AI summary, impact score and SLA flags inline."""
    __tablename__ = "pull_requests"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    github_pr_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    number: Mapped[int] = mapped_column(Integer, unique=True, index=True, nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    author: Mapped[str] = mapped_column(String(100), index=True, nullable=False)
    author_avatar: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    state: Mapped[str] = mapped_column(String(50), default="open", index=True, nullable=False)
    head_branch: Mapped[str] = mapped_column(String(150), nullable=False)
    base_branch: Mapped[str] = mapped_column(String(150), nullable=False)
    html_url: Mapped[str] = mapped_column(String(500), nullable=False)
    diff_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    is_overdue: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    overdue_days: Mapped[int] = mapped_column(Integer, default=0)
    summary_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    summary_provider: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    summary_timestamp: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    impact_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    impact_tier: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True, onupdate=func.now())
