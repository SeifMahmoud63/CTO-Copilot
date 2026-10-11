"""Unit tests for the access gate (password + Google Authenticator TOTP + remember-me).

Run from the repo root:
    python -m pytest tests/test_auth.py -v
"""
import re
from urllib.parse import parse_qs, urlparse

import pyotp
from fastapi.testclient import TestClient

from app.core import config as config_module
from app.services import auth_service


def _sqlite_factory(tmp_path):
    import aiosqlite  # noqa: F401
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

    from app.models import Base

    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path}/auth.db")

    async def _init():
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    import asyncio

    asyncio.run(_init())
    return async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)


def _settings(monkeypatch, **overrides):
    base = {
        "cto_password": "test123",
        "session_secret": "test-secret-not-real-0123456789",
        "session_max_age_hours": 12,
        "remember_me_days": 7,
        "totp_issuer": "CTO-Copilot",
        "auth_max_attempts": 5,
        "auth_lockout_seconds": 60,
    }
    base.update(overrides)
    for k, v in base.items():
        monkeypatch.setattr(config_module.settings, k, v)
    auth_service.reset_rate_limits()


def _client(monkeypatch, tmp_path, **overrides):
    _settings(monkeypatch, **overrides)
    monkeypatch.setattr(auth_service, "AsyncSessionLocal", _sqlite_factory(tmp_path))
    from app.main import app

    return TestClient(app, raise_server_exceptions=False)


def _secret_from_uri(uri: str) -> str:
    return parse_qs(urlparse(uri).query)["secret"][0]


def test_public_and_gated_routes(monkeypatch, tmp_path):
    client = _client(monkeypatch, tmp_path)
    assert client.get("/api/health").status_code == 200
    assert client.get("/login").status_code == 200
    r = client.get("/api/db/stats")
    assert r.status_code == 401
    r = client.get("/", follow_redirects=False)
    assert r.status_code == 302 and r.headers["location"] == "/login"


def test_unconfigured_auth_blocks_login(monkeypatch, tmp_path):
    client = _client(monkeypatch, tmp_path, cto_password="", session_secret="")
    r = client.post("/api/auth/login", json={"password": "x"})
    assert r.status_code == 401
    assert client.get("/api/auth/status").json() == {"enrolled": False, "configured": False}


def test_wrong_password_and_lockout(monkeypatch, tmp_path):
    from app.core import config as config_module

    client = _client(monkeypatch, tmp_path, auth_max_attempts=3, auth_lockout_seconds=1800)
    for _ in range(3):
        assert client.post("/api/auth/login", json={"password": "nope"}).status_code == 401
    r = client.post("/api/auth/login", json={"password": "nope"})
    assert r.status_code == 429
    assert "blocked" in r.json()["detail"]


def test_lockout_duration_matches_env_hyperparameters(monkeypatch):
    from app.core import config as config_module
    from app.services import auth_service as auth_module

    monkeypatch.setattr(config_module.settings, "auth_max_attempts", 3)
    monkeypatch.setattr(config_module.settings, "auth_lockout_seconds", 1800)
    auth_module.reset_rate_limits()
    assert auth_module.check_rate_limit("1.2.3.4") is None
    for _ in range(3):
        auth_module.record_auth_failure("1.2.3.4")
    wait = auth_module.check_rate_limit("1.2.3.4")
    assert wait is not None and 1790 < wait <= 1800  # ~30 minutes
    auth_module.record_auth_success("1.2.3.4")
    assert auth_module.check_rate_limit("1.2.3.4") is None


def test_full_enroll_verify_login_remember_flow(monkeypatch, tmp_path):
    client = _client(monkeypatch, tmp_path)

    assert client.get("/api/auth/status").json() == {"enrolled": False, "configured": True}

    setup = client.post("/api/auth/setup", json={"password": "test123"})
    assert setup.status_code == 200
    assert setup.json()["qr_data_uri"].startswith("data:image/png;base64,")
    secret = _secret_from_uri(setup.json()["otpauth_uri"])

    bad = client.post("/api/auth/verify", json={"password": "test123", "code": "000000"})
    assert bad.status_code == 401

    good = client.post(
        "/api/auth/verify", json={"password": "test123", "code": pyotp.TOTP(secret).now()}
    )
    assert good.status_code == 200
    assert "cto_session" in good.cookies

    assert client.get("/api/auth/status").json()["enrolled"] is True
    # Second setup must be refused once enrolled.
    assert client.post("/api/auth/setup", json={"password": "test123"}).status_code == 403

    # Wrong TOTP on login is rejected even with the right password.
    assert client.post(
        "/api/auth/login", json={"password": "test123", "code": "000000"}
    ).status_code == 401

    login = client.post(
        "/api/auth/login",
        json={"password": "test123", "code": pyotp.TOTP(secret).now(), "remember": True},
    )
    assert login.status_code == 200
    set_cookies = login.headers.get_list("set-cookie")
    remember = next(c for c in set_cookies if c.startswith("cto_remember="))
    assert "Max-Age=604800" in remember  # 7 days
    assert "HttpOnly" in remember

    # Authed browser passes the gate (route itself may 500 on real MySQL — but never 401).
    assert client.get("/api/db/stats").status_code != 401
    assert client.get("/").status_code == 200


def test_logout_clears_cookies_and_reset_needs_auth(monkeypatch, tmp_path):
    client = _client(monkeypatch, tmp_path)
    assert client.post("/api/auth/totp/reset").status_code == 401

    secret = _secret_from_uri(
        client.post("/api/auth/setup", json={"password": "test123"}).json()["otpauth_uri"]
    )
    client.post("/api/auth/verify", json={"password": "test123", "code": pyotp.TOTP(secret).now()})

    assert client.post("/api/auth/totp/reset").status_code == 200
    assert client.get("/api/auth/status").json()["enrolled"] is False

    out = client.post("/api/auth/logout")
    assert out.status_code == 200
    cleared = " ".join(out.headers.get_list("set-cookie"))
    assert "cto_session=" in cleared


def test_cookie_helpers_fail_closed_and_salts_isolated(monkeypatch, tmp_path):
    _settings(monkeypatch)
    assert auth_service.make_session_cookie() is not None
    assert auth_service.verify_session_cookie("garbage") is False
    assert auth_service.verify_remember_cookie("garbage") is False
    # Salts are not interchangeable.
    assert auth_service.verify_remember_cookie(auth_service.make_session_cookie()) is False
    assert auth_service.verify_session_cookie(auth_service.make_remember_cookie()) is False
    # Empty secret locks everything.
    monkeypatch.setattr(config_module.settings, "session_secret", "")
    assert auth_service.make_session_cookie() is None
    assert auth_service.verify_password("test123") is True  # password alone still checks
    monkeypatch.setattr(config_module.settings, "cto_password", "")
    assert auth_service.verify_password("test123") is False


def test_totp_secret_encrypted_at_rest(monkeypatch, tmp_path):
    _settings(monkeypatch)
    token = auth_service.encrypt_secret("HELLO")
    assert token and token != "HELLO"
    assert auth_service.decrypt_secret(token) == "HELLO"
    monkeypatch.setattr(config_module.settings, "session_secret", "rotated-secret")
    assert auth_service.decrypt_secret(token) is None  # rotation invalidates old blobs


def test_remember_days_tunable(monkeypatch, tmp_path):
    _settings(monkeypatch, remember_me_days=30)
    assert config_module.settings.remember_me_days == 30
    assert config_module.settings.remember_me_days * 86400 == 2592000
    assert config_module.settings.session_secret  # needed to sign
    cookie = auth_service.make_remember_cookie()
    assert auth_service.verify_remember_cookie(cookie) is True
