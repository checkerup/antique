"""Tests for the SQLite storage layer."""
import tempfile
from pathlib import Path

import pytest

from src.core.storage import (
    GroupRecord,
    ProfileRecord,
    SessionRecord,
    ensure_default_group,
    init_db,
    make_engine,
)
from sqlmodel import Session, select


def test_init_db_creates_tables(tmp_path: Path):
    engine = make_engine(tmp_path / "test.db")
    init_db(engine)
    with Session(engine) as s:
        # Should be able to query an empty table
        rows = s.exec(select(ProfileRecord)).all()
        assert rows == []


def test_insert_and_query_profile(tmp_path: Path):
    engine = make_engine(tmp_path / "test.db")
    init_db(engine)
    with Session(engine) as s:
        rec = ProfileRecord(
            user_id="test01",
            name="Test Profile",
            user_proxy_config='{"proxy_type": "direct"}',
            fingerprint_config='{"user_agent": "test"}',
            cookies="[]",
            tags='["smoke"]',
        )
        s.add(rec)
        s.commit()
        s.refresh(rec)
        assert rec.user_id == "test01"
        assert rec.name == "Test Profile"
        assert rec.launch_count == 0
        # Read back
        got = s.get(ProfileRecord, "test01")
        assert got is not None
        assert got.name == "Test Profile"


def test_session_record_lifecycle(tmp_path: Path):
    engine = make_engine(tmp_path / "test.db")
    init_db(engine)
    with Session(engine) as s:
        prof = ProfileRecord(user_id="p1", name="p1")
        s.add(prof)
        s.commit()
        sess = SessionRecord(
            session_id="s1", user_id="p1", debug_port=9222, ws_endpoint="ws://x"
        )
        s.add(sess)
        s.commit()
        # Mark stopped
        sess.status = "stopped"
        s.add(sess)
        s.commit()
        s.refresh(sess)
        assert sess.status == "stopped"


def test_ensure_default_group(tmp_path: Path):
    engine = make_engine(tmp_path / "test.db")
    init_db(engine)
    ensure_default_group(engine)
    with Session(engine) as s:
        g = s.get(GroupRecord, "0")
        assert g is not None
        assert g.name == "Default"
    # Calling again is idempotent
    ensure_default_group(engine)
    with Session(engine) as s:
        all_groups = s.exec(select(GroupRecord)).all()
        assert len(all_groups) == 1