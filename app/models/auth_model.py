from datetime import datetime
from typing import Optional
from sqlalchemy import String, Integer, Boolean, Text, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base

class AuthState(Base):
    """Single-row table (id=1) holding the TOTP enrollment state.

    The secret is stored Fernet-encrypted (key derived from SESSION_SECRET),
    never in plaintext.
    """
    __tablename__ = "auth_state"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    totp_secret_encrypted: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    totp_enrolled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)
