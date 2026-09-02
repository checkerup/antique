"""Tests for the /diagnostics/summary API endpoint.

This endpoint lives on the UI router (dashboard.py), not routes.py,
to avoid editing shared backend files.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from src.api.server import create_app
from src.core.operations import record_activity
from src.core.storage import SessionRecord
from sqlmodel import Session as SqlSession


@pytest.fixture
def client(tmp_path):
    return TestClient(create_app(data_root=tmp_path))


def _create(client, name="diag-profile"):
    r = client.post("/user/create", json={"name": name})
    assert r.status_code == 200, r.text
    return r.json()["data"]["user_id"]


# ---------------------------------------------------------------------------
# Endpoint shape
# ---------------------------------------------------------------------------


def test_diagnostics_summary_returns_200(client):
    r = client.get("/diagnostics/summary")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["code"] == 0
    assert body["msg"] == "success"


def test_diagnostics_summary_has_all_fields(client):
    _create(client, "test-1")
    r = client.get("/diagnostics/summary")
    data = r.json()["data"]
    for key in (
        "overall_status",
        "profiles_total",
        "profiles_running",
        "profiles_stopped",
        "profiles_needing_migration",
        "proxy_failures",
        "crashed_sessions",
        "account_status_breakdown",
        "recent_activity",
        "issues",
        "checked_at",
    ):
        assert key in data, f"missing key: {key}"


def test_diagnostics_summary_counts_profiles(client):
    _create(client, "a")
    _create(client, "b")
    r = client.get("/diagnostics/summary")
    data = r.json()["data"]
    assert data["profiles_total"] == 2
    assert data["profiles_running"] == 0
    assert data["profiles_stopped"] == 2
    assert data["overall_status"] == "healthy"


def test_diagnostics_summary_includes_activity(client):
    uid = _create(client, "activity-1")
    r = client.get("/diagnostics/summary")
    data = r.json()["data"]
    assert len(data["recent_activity"]) >= 1
    entry = data["recent_activity"][0]
    assert entry["action"] == "create"


def test_diagnostics_summary_detects_migration_needed(client, tmp_path):
    uid = _create(client, "migrate-test")
    # Set import source path via the reimport endpoint or directly via store
    # We'll use the /user/{user_id}/reimport logic by setting the source path
    # through the store directly (accessed via app.state)
    import json
    from src.core.storage import ProfileRecord
    store = client.app.state.store
    with SqlSession(store.engine) as s:
        rec = s.get(ProfileRecord, uid)
        rec.import_source_path = str(tmp_path / "fake_backup")
        rec.initial_state_applied = False
        s.add(rec)
        s.commit()

    r = client.get("/diagnostics/summary")
    data = r.json()["data"]
    assert data["profiles_needing_migration"] == 1
    assert data["overall_status"] == "warning"
    migration_issues = [i for i in data["issues"] if i["type"] == "migration"]
    assert len(migration_issues) == 1
    assert migration_issues[0]["user_id"] == uid


def test_diagnostics_summary_empty_store(client):
    r = client.get("/diagnostics/summary")
    data = r.json()["data"]
    assert data["profiles_total"] == 0
    assert data["overall_status"] == "healthy"
    assert data["issues"] == []


def test_diagnostics_summary_account_status_breakdown(client):
    client.post("/user/create", json={"name": "new-p", "account_status": "new"})
    client.post("/user/create", json={"name": "active-p", "account_status": "active"})
    client.post("/user/create", json={"name": "banned-p", "account_status": "banned"})
    r = client.get("/diagnostics/summary")
    data = r.json()["data"]
    bd = data["account_status_breakdown"]
    assert bd.get("new") == 1
    assert bd.get("active") == 1
    assert bd.get("banned") == 1
    # Banned profiles should create issues
    status_issues = [i for i in data["issues"] if i["type"] == "account_status"]
    assert len(status_issues) == 1


def test_diagnostics_summary_crashed_session(client):
    uid = _create(client, "crash-test")
    store = client.app.state.store
    with SqlSession(store.engine) as s:
        s.add(SessionRecord(
            session_id="crash-sess",
            user_id=uid,
            debug_port=12345,
            ws_endpoint="ws://localhost:12345",
            pid=999,
            status="crashed",
        ))
        s.commit()
    r = client.get("/diagnostics/summary")
    data = r.json()["data"]
    assert data["crashed_sessions"] == 1
    assert data["overall_status"] == "critical"
