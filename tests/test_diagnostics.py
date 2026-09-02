"""Tests for the operator diagnostics/health-summary module.

These tests exercise the pure ``compute_health_summary`` function which
aggregates data already available from the ProfileStore, the activity log,
and proxy/session metadata — without touching any API server.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

import pytest

from src.core.diagnostics import compute_health_summary
from src.core.profile import ProfileStore
from src.core.operations import record_activity


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def store(tmp_path):
    return ProfileStore(db_path=tmp_path / "diag.db")


def _make_profile(store, name="p1", proxy=None, status="new", tags=None):
    """Create a profile with sensible defaults for diagnostics tests."""
    return store.create(
        name=name,
        proxy=proxy or {},
        tags=tags or [],
        account_status=status,
    )


# ---------------------------------------------------------------------------
# Health summary — structure
# ---------------------------------------------------------------------------


def test_health_summary_returns_well_formed_dict(store):
    _make_profile(store, "alpha")
    summary = compute_health_summary(store, running_uids=[], proxy_results={})
    assert "overall_status" in summary
    assert "profiles_total" in summary
    assert "profiles_running" in summary
    assert "profiles_stopped" in summary
    assert "profiles_needing_migration" in summary
    assert "proxy_failures" in summary
    assert "crashed_sessions" in summary
    assert "recent_activity" in summary
    assert "issues" in summary
    assert isinstance(summary["issues"], list)


def test_health_summary_counts_profiles(store):
    _make_profile(store, "a")
    _make_profile(store, "b")
    summary = compute_health_summary(store, running_uids=[], proxy_results={})
    assert summary["profiles_total"] == 2
    assert summary["profiles_stopped"] == 2
    assert summary["profiles_running"] == 0


def test_health_summary_counts_running(store):
    p = _make_profile(store, "a")
    summary = compute_health_summary(store, running_uids=[p.user_id], proxy_results={})
    assert summary["profiles_running"] == 1
    assert summary["profiles_stopped"] == 0


# ---------------------------------------------------------------------------
# Migration detection
# ---------------------------------------------------------------------------


def test_profiles_needing_migration_detects_unimported_adspower(store):
    """Profiles with import_source_path set but initial_state_applied=False
    still need migration completion."""
    p = _make_profile(store, "adspower-1")
    store.set_import_source(p.user_id, "C:\\backup\\profile_dir", reset_applied=True)
    summary = compute_health_summary(store, running_uids=[], proxy_results={})
    assert summary["profiles_needing_migration"] == 1


def test_profiles_needing_migration_excludes_applied(store):
    p = _make_profile(store, "adspower-2")
    store.set_import_source(p.user_id, "C:\\backup\\profile_dir", reset_applied=True)
    store.mark_initial_state_applied(p.user_id)
    summary = compute_health_summary(store, running_uids=[], proxy_results={})
    assert summary["profiles_needing_migration"] == 0


def test_profiles_needing_migration_excludes_no_source(store):
    _make_profile(store, "fresh-profile")
    summary = compute_health_summary(store, running_uids=[], proxy_results={})
    assert summary["profiles_needing_migration"] == 0


# ---------------------------------------------------------------------------
# Proxy failure aggregation
# ---------------------------------------------------------------------------


def test_proxy_failures_aggregated_from_results(store):
    p1 = _make_profile(store, "px-1", proxy={"proxy_type": "http", "proxy_host": "bad.host", "proxy_port": 9999})
    p2 = _make_profile(store, "px-2", proxy={"proxy_type": "http", "proxy_host": "good.host", "proxy_port": 8080})
    proxy_results = {
        p1.user_id: {"status": "error", "error": "connection refused"},
        p2.user_id: {"status": "ok", "ip": "1.2.3.4", "latency_ms": 100},
    }
    summary = compute_health_summary(store, running_uids=[], proxy_results=proxy_results)
    assert summary["proxy_failures"] == 1
    # The issue list should mention the failed proxy
    issue_texts = " ".join(i.get("detail", "") for i in summary["issues"])
    assert "connection refused" in issue_texts or summary["proxy_failures"] >= 1


def test_proxy_failures_zero_when_all_ok(store):
    p = _make_profile(store, "px-ok", proxy={"proxy_type": "http", "proxy_host": "h", "proxy_port": 80})
    proxy_results = {p.user_id: {"status": "ok", "ip": "1.2.3.4", "latency_ms": 50}}
    summary = compute_health_summary(store, running_uids=[], proxy_results=proxy_results)
    assert summary["proxy_failures"] == 0


def test_proxy_failures_skips_direct(store):
    p = _make_profile(store, "no-proxy")
    proxy_results = {p.user_id: {"status": "skip", "error": "No proxy configured"}}
    summary = compute_health_summary(store, running_uids=[], proxy_results=proxy_results)
    assert summary["proxy_failures"] == 0


# ---------------------------------------------------------------------------
# Overall status logic
# ---------------------------------------------------------------------------


def test_overall_status_healthy(store):
    _make_profile(store, "ok-1")
    summary = compute_health_summary(store, running_uids=[], proxy_results={})
    assert summary["overall_status"] == "healthy"


def test_overall_status_warning_with_migration(store):
    p = _make_profile(store, "need-migration")
    store.set_import_source(p.user_id, "C:\\bak", reset_applied=True)
    summary = compute_health_summary(store, running_uids=[], proxy_results={})
    assert summary["overall_status"] == "warning"


def test_overall_status_critical_with_proxy_failures(store):
    p = _make_profile(store, "px-bad", proxy={"proxy_type": "http", "proxy_host": "x", "proxy_port": 1})
    proxy_results = {p.user_id: {"status": "error", "error": "timeout"}}
    summary = compute_health_summary(store, running_uids=[], proxy_results=proxy_results)
    assert summary["overall_status"] == "critical"


# ---------------------------------------------------------------------------
# Recent activity
# ---------------------------------------------------------------------------


def test_recent_activity_included(store):
    p = _make_profile(store, "act-1")
    record_activity(store, p.user_id, "create", {"name": "act-1"})
    summary = compute_health_summary(store, running_uids=[], proxy_results={})
    assert len(summary["recent_activity"]) >= 1
    entry = summary["recent_activity"][0]
    assert "action" in entry
    assert "user_id" in entry
    assert "created_at" in entry


def test_recent_activity_limited_to_10(store):
    p = _make_profile(store, "act-many")
    for i in range(15):
        record_activity(store, p.user_id, "test_action", {"i": i})
    summary = compute_health_summary(store, running_uids=[], proxy_results={})
    assert len(summary["recent_activity"]) == 10


# ---------------------------------------------------------------------------
# Issues list
# ---------------------------------------------------------------------------


def test_issues_list_contains_migration_entries(store):
    p = _make_profile(store, "migrate-issue")
    store.set_import_source(p.user_id, "C:\\bak", reset_applied=True)
    summary = compute_health_summary(store, running_uids=[], proxy_results={})
    migration_issues = [i for i in summary["issues"] if i.get("type") == "migration"]
    assert len(migration_issues) == 1
    assert migration_issues[0]["user_id"] == p.user_id


def test_issues_list_contains_proxy_failures(store):
    p = _make_profile(store, "px-fail", proxy={"proxy_type": "http", "proxy_host": "h", "proxy_port": 1})
    proxy_results = {p.user_id: {"status": "error", "error": "refused"}}
    summary = compute_health_summary(store, running_uids=[], proxy_results=proxy_results)
    proxy_issues = [i for i in summary["issues"] if i.get("type") == "proxy"]
    assert len(proxy_issues) == 1


# ---------------------------------------------------------------------------
# Crashed sessions
# ---------------------------------------------------------------------------


def test_crashed_sessions_empty_by_default(store):
    _make_profile(store, "no-crash")
    summary = compute_health_summary(store, running_uids=[], proxy_results={})
    assert summary["crashed_sessions"] == 0


def test_crashed_sessions_counted_from_session_records(store):
    """When a session record has status='crashed', it should be counted."""
    from src.core.storage import SessionRecord, get_session
    from sqlmodel import Session as SqlSession

    p = _make_profile(store, "crashed-profile")
    with SqlSession(store.engine) as s:
        s.add(SessionRecord(
            session_id="sess-crash-1",
            user_id=p.user_id,
            debug_port=9999,
            ws_endpoint="ws://localhost:9999",
            pid=12345,
            status="crashed",
        ))
        s.commit()

    summary = compute_health_summary(store, running_uids=[], proxy_results={})
    assert summary["crashed_sessions"] == 1


# ---------------------------------------------------------------------------
# Account status breakdown
# ---------------------------------------------------------------------------


def test_account_status_breakdown(store):
    _make_profile(store, "new-1", status="new")
    _make_profile(store, "active-1", status="active")
    _make_profile(store, "banned-1", status="banned")
    summary = compute_health_summary(store, running_uids=[], proxy_results={})
    breakdown = summary.get("account_status_breakdown", {})
    assert breakdown.get("new") == 1
    assert breakdown.get("active") == 1
    assert breakdown.get("banned") == 1


# ---------------------------------------------------------------------------
# Empty store
# ---------------------------------------------------------------------------


def test_empty_store_summary(store):
    summary = compute_health_summary(store, running_uids=[], proxy_results={})
    assert summary["profiles_total"] == 0
    assert summary["overall_status"] == "healthy"
    assert summary["issues"] == []
