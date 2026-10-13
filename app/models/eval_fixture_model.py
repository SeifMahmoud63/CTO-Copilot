from datetime import datetime
from typing import Optional
from sqlalchemy import String, Integer, DateTime, Text, Float, func
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base

class EvalFixture(Base):
    """Synthetic eval rows: clearly-fake PR/email/engineer facts for torture tests.

    Lives in the same DB so the chatbot can query it, but NEVER feeds real
    dashboards (queries must scope `kind`). Values are deliberately distinctive
    (EvalBot_*, Synthetic *, *-eval.invalid) to separate signal from leakage.
    """
    __tablename__ = "eval_fixtures"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    kind: Mapped[str] = mapped_column(String(20), index=True, nullable=False)
    ref_name: Mapped[str] = mapped_column(String(100), unique=True, index=True, nullable=False)
    title: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    owner: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    state: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    event_date: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    tier: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
