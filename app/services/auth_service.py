"""TOTP authentication and signed cookies."""
import base64
import hashlib
import hmac
import io
import logging
import time
from typing import Dict, Optional, Tuple

from sqlalchemy import select

from app.core.config import settings
from app.db.session import AsyncSessionLocal
from app.models import AuthState

logger = logging.getLogger("cto-copilot.auth")

SESSION_SALT = "cto-session-v1"
REMEMBER_SALT = "cto-remember-v1"
SESSION_VALUE = "session:cto"
REMEMBER_VALUE = "remember:cto"

_attempts: Dict[str, Dict[str, float]] = {}


def is_configured() -> bool:
    """Both a password and a signing secret must be set, else locked."""
    return bool(settings.cto_password) and bool(settings.session_secret)


def _fernet():
    """Fernet over SHA256(session_secret) — accepts any secret string."""
    if not settings.session_secret:
        return None
    from cryptography.fernet import Fernet

    key = base64.urlsafe_b64encode(hashlib.sha256(settings.session_secret.encode()).digest())
    return Fernet(key)


def encrypt_secret(plain: str) -> Optional[str]:
    f = _fernet()
    if f is None:
        return None
    return f.encrypt(plain.encode()).decode()


def decrypt_secret(token: Optional[str]) -> Optional[str]:
    if not token:
        return None
    f = _fernet()
    if f is None:
        return None
    try:
        return f.decrypt(token.encode()).decode()
    except Exception:
        logger.warning("TOTP secret decryption failed (SESSION_SECRET changed?)")
        return None


def verify_password(password: str) -> bool:
    if not settings.cto_password or not password:
        return False
    return hmac.compare_digest(password, settings.cto_password)


def new_totp_secret() -> str:
    import pyotp

    return pyotp.random_base32()


def provisioning_uri(secret: str, account: str = "CTO") -> str:
    import pyotp

    return pyotp.totp.TOTP(secret).provisioning_uri(name=account, issuer_name=settings.totp_issuer)


def qr_data_uri(otpauth_uri: str) -> str:
    import qrcode

    img = qrcode.make(otpauth_uri)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()


def check_totp_code(secret: str, code: str) -> bool:
    import pyotp

    if not secret or not code:
        return False
    try:
        return bool(pyotp.TOTP(secret).verify(code.strip(), valid_window=1))
    except Exception:
        return False


async def get_state_row() -> AuthState:
    """Fetch the singleton row (id=1), creating it on first use."""
    async with AsyncSessionLocal() as session:
        async with session.begin():
            res = await session.execute(select(AuthState).where(AuthState.id == 1))
            row = res.scalar_one_or_none()
            if row is None:
                row = AuthState(id=1, totp_enrolled=False)
                session.add(row)
                await session.flush()
                await session.refresh(row)
            return row


async def get_totp_status() -> Dict[str, bool]:
    row = await get_state_row()
    return {"enrolled": bool(row.totp_enrolled), "configured": is_configured()}


async def begin_enrollment(password: str) -> Dict[str, str]:
    """Create a fresh secret (enrolled=False) and return QR payload. Password-gated."""
    if not verify_password(password):
        raise PermissionError("Invalid password.")
    async with AsyncSessionLocal() as session:
        async with session.begin():
            res = await session.execute(select(AuthState).where(AuthState.id == 1))
            row = res.scalar_one_or_none()
            if row is not None and row.totp_enrolled:
                raise PermissionError("TOTP already enrolled. Reset first to re-enroll.")
            secret = new_totp_secret()
            encrypted = encrypt_secret(secret)
            if encrypted is None:
                raise RuntimeError("SESSION_SECRET is not set.")
            if row is None:
                row = AuthState(id=1, totp_secret_encrypted=encrypted, totp_enrolled=False)
                session.add(row)
            else:
                row.totp_secret_encrypted = encrypted
                row.totp_enrolled = False
            await session.flush()
    uri = provisioning_uri(secret)
    return {"otpauth_uri": uri, "qr_data_uri": qr_data_uri(uri)}


async def verify_enrollment(password: str, code: str) -> bool:
    """Confirm a code against the pending secret and mark enrolled."""
    if not verify_password(password):
        return False
    async with AsyncSessionLocal() as session:
        async with session.begin():
            res = await session.execute(select(AuthState).where(AuthState.id == 1))
            row = res.scalar_one_or_none()
            if row is None:
                return False
            secret = decrypt_secret(row.totp_secret_encrypted)
            if not secret or not check_totp_code(secret, code):
                return False
            row.totp_enrolled = True
            await session.flush()
            return True


async def verify_login(password: str, code: Optional[str] = None) -> Tuple[bool, str]:
    """Password (+ TOTP code when enrolled). Returns (ok, reason)."""
    if not is_configured():
        return False, "Auth is not configured (CTO_PASSWORD / SESSION_SECRET missing)."
    if not verify_password(password):
        return False, "Invalid password."
    row = await get_state_row()
    if row.totp_enrolled:
        secret = decrypt_secret(row.totp_secret_encrypted)
        if not secret or not check_totp_code(secret, code or ""):
            return False, "Invalid authenticator code."
    return True, "ok"


async def reset_enrollment() -> None:
    """Wipe TOTP state (fresh re-enrollment). Call only from an authed route."""
    async with AsyncSessionLocal() as session:
        async with session.begin():
            res = await session.execute(select(AuthState).where(AuthState.id == 1))
            row = res.scalar_one_or_none()
            if row is not None:
                row.totp_secret_encrypted = None
                row.totp_enrolled = False
                await session.flush()


def _signer(salt: str):
    if not settings.session_secret:
        return None
    from itsdangerous import TimestampSigner

    return TimestampSigner(settings.session_secret, salt=salt, digest_method=hashlib.sha256)


def make_session_cookie() -> Optional[str]:
    s = _signer(SESSION_SALT)
    return s.sign(SESSION_VALUE).decode() if s else None


def verify_session_cookie(value: Optional[str]) -> bool:
    if not value:
        return False
    s = _signer(SESSION_SALT)
    if s is None:
        return False
    try:
        return s.unsign(value, max_age=settings.session_max_age_hours * 3600).decode() == SESSION_VALUE
    except Exception:
        return False


def make_remember_cookie() -> Optional[str]:
    s = _signer(REMEMBER_SALT)
    return s.sign(REMEMBER_VALUE).decode() if s else None


def verify_remember_cookie(value: Optional[str]) -> bool:
    if not value:
        return False
    s = _signer(REMEMBER_SALT)
    if s is None:
        return False
    try:
        return s.unsign(value, max_age=settings.remember_me_days * 86400).decode() == REMEMBER_VALUE
    except Exception:
        return False


def check_rate_limit(ip: str) -> Optional[float]:
    """None if allowed, else seconds to wait (locked out)."""
    entry = _attempts.get(ip)
    if not entry:
        return None
    if entry.get("locked_until", 0) > time.monotonic():
        return max(0.0, entry["locked_until"] - time.monotonic())
    return None


def record_auth_failure(ip: str) -> None:
    entry = _attempts.setdefault(ip, {"fails": 0, "locked_until": 0.0})
    entry["fails"] = entry.get("fails", 0) + 1
    if entry["fails"] >= max(1, settings.auth_max_attempts):
        entry["locked_until"] = time.monotonic() + max(1, settings.auth_lockout_seconds)
        entry["fails"] = 0


def record_auth_success(ip: str) -> None:
    _attempts.pop(ip, None)


def reset_rate_limits() -> None:
    _attempts.clear()
