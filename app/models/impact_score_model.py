from datetime import datetime
from typing import Optional
from sqlalchemy import String, Integer, Float, Text, DateTime, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base

class ImpactScore(Base):
    __tablename__ = "pr_impact_scores"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    pr_id: Mapped[int] = mapped_column(Integer, ForeignKey("pull_requests.id", ondelete="CASCADE"), index=True, nullable=False)
    pr_number: Mapped[int] = mapped_column(Integer, index=True, nullable=False)
    score: Mapped[float] = mapped_column(Float, nullable=False)
    tier: Mapped[str] = mapped_column(String(50), default="Solid Contributor", nullable=False)
    model_name: Mapped[str] = mapped_column(String(100), default="jev-latest", nullable=False)
    criteria_details: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())

    pull_request = relationship("PullRequest", back_populates="impact_scores")
