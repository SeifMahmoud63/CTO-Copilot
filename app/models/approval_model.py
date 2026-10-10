from datetime import datetime
from typing import Optional
from sqlalchemy import String, Integer, Text, DateTime, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base

class PRApproval(Base):
    __tablename__ = "pr_approvals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    pr_id: Mapped[int] = mapped_column(Integer, ForeignKey("pull_requests.id", ondelete="CASCADE"), index=True, nullable=False)
    pr_number: Mapped[int] = mapped_column(Integer, index=True, nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="PENDING", nullable=False)  # APPROVED, CHANGES_REQUESTED, REJECTED, PENDING
    decision_by: Mapped[str] = mapped_column(String(100), default="CTO", nullable=False)
    review_comment: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    decided_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())

    pull_request = relationship("PullRequest", back_populates="approvals")
