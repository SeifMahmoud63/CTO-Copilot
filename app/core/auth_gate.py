"""Route guard: everything private except login/health/webhooks/static."""
from fastapi import Request
from fastapi.responses import JSONResponse, RedirectResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.services import auth_service

PUBLIC_PREFIXES = (
    "/login",
    "/api/auth/",
    "/api/health",
    "/api/webhook/",
    "/static",
    "/docs",
    "/openapi.json",
    "/redoc",
)


def is_authed(request: Request) -> bool:
    cookies = request.cookies or {}
    return auth_service.verify_session_cookie(
        cookies.get("cto_session")
    ) or auth_service.verify_remember_cookie(cookies.get("cto_remember"))


class AuthGateMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        if request.method == "OPTIONS":
            return await call_next(request)
        if path == "/login" and is_authed(request):
            return RedirectResponse("/", status_code=302)
        if any(path == p or path.startswith(p) for p in PUBLIC_PREFIXES):
            return await call_next(request)
        if is_authed(request):
            return await call_next(request)
        if path.startswith("/api/"):
            return JSONResponse({"detail": "Authentication required."}, status_code=401)
        return RedirectResponse("/login", status_code=302)
