from datetime import datetime
from typing import Optional
from sqlalchemy import String, Integer, Text, DateTime, ForeignKey, Boolean, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base

class PRSummary(Base):
    __tablename__ = "pr_summaries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    pr_id: Mapped[int] = mapped_column(Integer, ForeignKey("pull_requests.id", ondelete="CASCADE"), index=True, nullable=False)
    pr_number: Mapped[int] = mapped_column(Integer, index=True, nullable=False)
    summary_text: Mapped[str] = mapped_column(Text, nullable=False)
    provider: Mapped[str] = mapped_column(String(50), default="BEDROCK", nullable=False)
    model_name: Mapped[str] = mapped_column(String(100), nullable=False)
    is_cached: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())

    pull_request = relationship("PullRequest", back_populates="summaries")
