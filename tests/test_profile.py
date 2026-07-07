"""Tests for ProfileStore (CRUD + sessions)."""
import tempfile
from pathlib import Path

import pytest

from src.core.fingerprint import generate_fingerprint
from src.core.profile import ProfileStore


@pytest.fixture
def store(tmp_path):
    s = ProfileStore(db_path=tmp_path / "test.db")
    return s


def test_create_minimal(store):
    p = store.create(name="alpha")
    assert p.user_id
    assert len(p.user_id) == 8
    assert p.name == "alpha"
    assert p.group_id == "0"
    assert p.proxy == {}
    assert p.fingerprint  # should be populated by generator
    assert p.cookies == []


def test_create_with_explicit_fingerprint(store):
    fp = generate_fingerprint(seed="known")
    p = store.create(name="beta", fingerprint=fp)
    # Fingerprint should round-trip via the JSON blob
    assert p.fingerprint["id"] == fp.id


def test_create_with_user_id(store):
    p = store.create(name="gamma", user_id="mycustom1")
    assert p.user_id == "mycustom1"
    # Duplicate id should fail
    with pytest.raises(ValueError):
        store.create(name="another", user_id="mycustom1")


def test_get_existing(store):
    p1 = store.create(name="p1")
    p2 = store.get(p1.user_id)
    assert p2 is not None
    assert p2.user_id == p1.user_id
    assert p2.name == "p1"


def test_get_missing_returns_none(store):
    assert store.get("nope") is None


def test_list_with_search(store):
    store.create(name="alpha-account")
    store.create(name="beta-account")
    store.create(name="gamma")
    all_profiles = store.list()
    assert len(all_profiles) == 3
    only_alpha = store.list(search="alpha")
    assert len(only_alpha) == 1
    assert only_alpha[0].name == "alpha-account"


def test_update_name(store):
    p = store.create(name="old")
    p2 = store.update(p.user_id, name="new")
    assert p2.name == "new"
    # Get from DB to confirm persisted
    p3 = store.get(p.user_id)
    assert p3.name == "new"


def test_update_cookies(store):
    p = store.create(name="p1")
    cookies = [{"name": "foo", "value": "bar", "domain": ".example.com"}]
    store.update(p.user_id, cookies=cookies)
    p2 = store.get(p.user_id)
    assert p2.cookies == cookies


def test_delete(store):
    p = store.create(name="doomed")
    assert store.delete(p.user_id) is True
    assert store.get(p.user_id) is None
    # Deleting again returns False
    assert store.delete(p.user_id) is False


def test_session_record_and_stop(store):
    p = store.create(name="p1")
    store.record_session(
        p.user_id,
        session_id="s1",
        debug_port=9222,
        ws_endpoint="ws://x",
        pid=1234,
    )
    sess = store.get_session(p.user_id)
    assert sess is not None
    assert sess.debug_port == 9222
    assert sess.status == "running"
    assert store.stop_session(p.user_id) is True
    # After stop, no running session
    assert store.get_session(p.user_id) is None
    # Second stop returns False (no running sessions)
    assert store.stop_session(p.user_id) is False


def test_record_session_bumps_launch_count(store):
    p = store.create(name="p1")
    assert p.launch_count == 0
    store.record_session(p.user_id, session_id="s1", debug_port=9222, ws_endpoint="ws://x")
    p2 = store.get(p.user_id)
    assert p2.launch_count == 1
    assert p2.last_launched_at is not None