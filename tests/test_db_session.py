"""Unit tests for the DB loop-teardown noise filter (no MySQL needed).

Run from the repo root:
    python -m pytest tests/test_db_session.py -v
"""
import sys
from types import SimpleNamespace

from app.db import session as session_module


def _aiomysql_like_obj():
    cls = type("Connection", (), {"__module__": "aiomysql.connection"})
    return cls()


def test_predicate_matches_db_teardown_noise():
    err = RuntimeError("Event loop is closed")
    assert session_module.is_loop_teardown_noise(err, _aiomysql_like_obj()) is True


def test_predicate_rejects_everything_else():
    assert session_module.is_loop_teardown_noise(
        ValueError("Event loop is closed"), _aiomysql_like_obj()) is False
    assert session_module.is_loop_teardown_noise(
        RuntimeError("boom"), _aiomysql_like_obj()) is False
    # Same message, but from our own code paths (no DB frames/object).
    try:
        raise RuntimeError("Event loop is closed")
    except RuntimeError as e:
        assert session_module.is_loop_teardown_noise(e, object()) is False
        assert session_module.is_loop_teardown_noise(e, None) is False


def test_install_is_idempotent_and_delegates():
    prev = sys.unraisablehook
    seen = []
    session_module._installed_noise_filter = False

    def fake_prev(unraisable):
        seen.append(unraisable)

    sys.unraisablehook = fake_prev
    try:
        session_module.install_loop_noise_filter()
        session_module.install_loop_noise_filter()  # second call is a no-op
        assert sys.unraisablehook is not fake_prev

        # Matching noise is swallowed (prev NOT called).
        sys.unraisablehook(SimpleNamespace(
            exc_value=RuntimeError("Event loop is closed"),
            object=_aiomysql_like_obj()))
        assert seen == []

        # Anything else flows to the previous hook untouched.
        other = SimpleNamespace(exc_value=ValueError("real problem"), object=None)
        sys.unraisablehook(other)
        assert seen == [other]
    finally:
        sys.unraisablehook = prev
        session_module._installed_noise_filter = False
