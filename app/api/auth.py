"""Access-gate endpoints: status, TOTP enrollment (QR), login, logout, reset."""
from typing import Optional

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from app.core.auth_gate import is_authed
from app.core.config import settings
from app.services import auth_service

router = APIRouter(prefix="/api/auth", tags=["Access Gate"])

SESSION_COOKIE = "cto_session"
REMEMBER_COOKIE = "cto_remember"


class SetupRequest(BaseModel):
    password: str


class VerifyRequest(BaseModel):
    password: str
    code: str


class LoginRequest(BaseModel):
    password: str
    code: Optional[str] = None
    remember: bool = False


def _client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def _session_response(payload: dict, remember: bool = False) -> JSONResponse:
    resp = JSONResponse(payload)
    session_cookie = auth_service.make_session_cookie()
    if session_cookie:
        resp.set_cookie(
            SESSION_COOKIE, session_cookie, httponly=True, samesite="lax", path="/",
            max_age=settings.session_max_age_hours * 3600,
        )
    if remember:
        remember_cookie = auth_service.make_remember_cookie()
        if remember_cookie:
            resp.set_cookie(
                REMEMBER_COOKIE, remember_cookie, httponly=True, samesite="lax", path="/",
                max_age=settings.remember_me_days * 86400,
            )
    return resp


@router.get("/status")
async def auth_status():
    """{enrolled, configured} — drives the login page steps."""
    return await auth_service.get_totp_status()


@router.post("/setup")
async def auth_setup(payload: SetupRequest):
    """Start TOTP enrollment (password-gated, only before first enrollment)."""
    import logging as _logging
    try:
        return await auth_service.begin_enrollment(payload.password)
    except PermissionError as e:
        _logging.getLogger("cto-copilot.api").warning(f"Auth enrollment forbidden: {e}")
        raise HTTPException(status_code=403, detail="Error")
    except RuntimeError:
        _logging.getLogger("cto-copilot.api").error("Auth enrollment failed.", exc_info=True)
        raise HTTPException(status_code=500, detail="Error")


@router.post("/verify")
async def auth_verify(payload: VerifyRequest):
    """Confirm the authenticator code, finish enrollment, and log in."""
    ok = await auth_service.verify_enrollment(payload.password, payload.code)
    if not ok:
        raise HTTPException(status_code=401, detail="Invalid password or code.")
    return _session_response({"ok": True, "enrolled": True})


@router.post("/login")
async def auth_login(payload: LoginRequest, request: Request):
    """Password (+ TOTP code when enrolled). Optional 7-day remember-me."""
    ip = _client_ip(request)
    wait = auth_service.check_rate_limit(ip)
    if wait is not None:
        human = f"{int(wait // 60)}m {int(wait % 60)}s" if wait >= 90 else f"{int(wait)}s"
        raise HTTPException(status_code=429, detail=f"Too many attempts. IP blocked, retry in {human}.")
    ok, reason = await auth_service.verify_login(payload.password, payload.code)
    if not ok:
        auth_service.record_auth_failure(ip)
        raise HTTPException(status_code=401, detail=reason)
    auth_service.record_auth_success(ip)
    return _session_response({"ok": True}, remember=payload.remember)


@router.post("/logout")
async def auth_logout():
    """Clear both cookies (this browser only)."""
    resp = JSONResponse({"ok": True})
    resp.delete_cookie(SESSION_COOKIE, path="/")
    resp.delete_cookie(REMEMBER_COOKIE, path="/")
    return resp


@router.post("/totp/reset")
async def auth_totp_reset(request: Request):
    """Wipe enrollment so a fresh QR can be issued (must already be logged in)."""
    if not is_authed(request):
        raise HTTPException(status_code=401, detail="Authentication required.")
    await auth_service.reset_enrollment()
    return {"ok": True, "enrolled": False}
