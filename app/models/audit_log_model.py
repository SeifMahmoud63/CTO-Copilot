from datetime import datetime
from typing import Optional
from sqlalchemy import String, Integer, Text, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base

class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    action: Mapped[str] = mapped_column(String(100), index=True, nullable=False)  # PR_SYNCED, SUMMARY_GENERATED, IMPACT_SCORED, etc.
    entity_type: Mapped[str] = mapped_column(String(50), nullable=False)          # PULL_REQUEST, SUMMARY, APPROVAL, SYSTEM
    entity_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    actor: Mapped[str] = mapped_column(String(100), default="SYSTEM", nullable=False)
    details: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), index=True)
