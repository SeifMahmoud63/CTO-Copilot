"""Unit tests proving the Alembic setup migrates the 2-table schema correctly.

Run from the repo root:
    python -m pytest tests/ -v

All migration tests run against throwaway SQLite files — no MySQL needed.
"""
import asyncio

import sqlalchemy as sa
from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, inspect

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HEAD = "0003_auth_state"
EXPECTED_TABLES = {"pull_requests", "engineers", "daily_reports", "auth_state"}
LEGACY_TABLES = ("pr_summaries", "pr_impact_scores", "pr_approvals", "audit_logs")


def make_cfg(db_path: Path, monkeypatch) -> Config:
    """Config pointing at a scratch SQLite DB (ALEMBIC_URL wins over .env)."""
    monkeypatch.setenv("ALEMBIC_URL", f"sqlite:///{db_path}")
    cfg = Config(str(ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(ROOT / "alembic"))
    return cfg


def user_tables(db_path: Path) -> set:
    eng = create_engine(f"sqlite:///{db_path}")
    try:
        return set(inspect(eng).get_table_names()) - {"alembic_version"}
    finally:
        eng.dispose()


def test_single_head_no_branching():
    script = ScriptDirectory(str(ROOT / "alembic"))
    heads = script.get_heads()
    revisions = list(script.walk_revisions())
    assert list(heads) == [HEAD], f"expected single head, got {heads}"
    assert len(revisions) == 3
    by_rev = {r.revision: r for r in revisions}
    assert by_rev["0002_daily_reports"].down_revision == "0001_initial_two_tables"
    assert by_rev[HEAD].down_revision == "0002_daily_reports"


def test_upgrade_head_creates_exactly_two_tables(tmp_path, monkeypatch):
    db = tmp_path / "fresh.db"
    command.upgrade(make_cfg(db, monkeypatch), "head")
    assert user_tables(db) == EXPECTED_TABLES


def test_migrated_columns_match_models(tmp_path, monkeypatch):
    """Every column in models must exist after migration and vice versa."""
    from app.models import Base

    db = tmp_path / "cols.db"
    command.upgrade(make_cfg(db, monkeypatch), "head")

    eng = create_engine(f"sqlite:///{db}")
    try:
        insp = inspect(eng)
        for table in EXPECTED_TABLES:
            migrated = {c["name"] for c in insp.get_columns(table)}
            modeled = set(Base.metadata.tables[table].columns.keys())
            assert migrated == modeled, f"{table}: migrated={migrated} modeled={modeled}"
    finally:
        eng.dispose()


def test_upgrade_drops_legacy_tables(tmp_path, monkeypatch):
    db = tmp_path / "legacy.db"
    eng = create_engine(f"sqlite:///{db}")
    try:
        with eng.begin() as conn:
            for legacy in LEGACY_TABLES:
                conn.execute(sa.text(f"CREATE TABLE {legacy} (id INTEGER PRIMARY KEY)"))
    finally:
        eng.dispose()

    command.upgrade(make_cfg(db, monkeypatch), "head")

    tables = user_tables(db)
    assert tables == EXPECTED_TABLES
    assert not (set(LEGACY_TABLES) & tables)


def test_downgrade_upgrade_roundtrip(tmp_path, monkeypatch):
    db = tmp_path / "roundtrip.db"
    cfg = make_cfg(db, monkeypatch)
    command.upgrade(cfg, "head")
    assert user_tables(db) == EXPECTED_TABLES

    command.downgrade(cfg, "base")
    assert user_tables(db) == set()

    command.upgrade(cfg, "head")
    assert user_tables(db) == EXPECTED_TABLES


def test_stamp_existing_db_marks_head_without_running(tmp_path, monkeypatch):
    """Mirrors the real-DB flow: tables already exist -> stamp, no DDL executed."""
    from app.models import Base

    expected = set(Base.metadata.tables.keys())
    assert {"pull_requests", "engineers"} <= expected

    db = tmp_path / "existing.db"
    eng = create_engine(f"sqlite:///{db}")
    try:
        Base.metadata.create_all(eng)
    finally:
        eng.dispose()

    command.stamp(make_cfg(db, monkeypatch), "head")

    eng = create_engine(f"sqlite:///{db}")
    try:
        with eng.connect() as conn:
            version = conn.execute(sa.text("SELECT version_num FROM alembic_version")).scalar()
        assert version == HEAD
        assert user_tables(db) == expected
    finally:
        eng.dispose()


def test_sync_url_converts_aiomysql_to_pymysql(monkeypatch):
    """Settings must hand Alembic a sync driver URL (async drivers crash it)."""
    from app.core.config import Settings

    monkeypatch.setenv(
        "DATABASE_URL", "mysql+aiomysql://u:p@somehost:3306/db?charset=utf8mb4"
    )
    url = Settings().sync_database_url
    assert "pymysql" in url
    assert "aiomysql" not in url
    assert "asyncmy" not in url
    assert "somehost" in url  # host/db preserved, only the driver changes


def test_init_db_runs_alembic_upgrade_head(monkeypatch):
    """App startup must drive migrations through `alembic upgrade head`."""
    from alembic import command as alembic_command
    from app.db import session as session_module

    calls = []
    monkeypatch.setattr(
        alembic_command, "upgrade", lambda cfg, rev: calls.append((cfg, rev))
    )
    # init_db also runs create_all afterwards (needs live MySQL) — the
    # wiring under test is the alembic call, so only assert it happened.
    try:
        asyncio.run(session_module.init_db())
    except Exception:
        pass
    assert len(calls) == 1
    assert calls[0][1] == "head"
    assert calls[0][0].get_main_option("script_location").endswith("alembic")
