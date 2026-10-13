from datetime import datetime
from typing import Optional
from sqlalchemy import String, Integer, DateTime, Text, Float, Boolean, func
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base

class Email(Base):
    """Email triage record: raw metadata + AI summary + JEV urgency score."""
    __tablename__ = "emails"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    message_id: Mapped[str] = mapped_column(String(500), unique=True, index=True, nullable=False)
    sender: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    subject: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    sent_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    snippet: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    body_excerpt: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    summary_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    summary_provider: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    urgency_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    urgency_tier: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    is_hidden: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), nullable=False)
