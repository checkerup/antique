"""Operator diagnostics: pure health-summary aggregation.

This module reads from the existing ``ProfileStore`` and activity log to
produce a single health-summary dict the dashboard can render. It does
**not** touch migration, security, or server modules — it only *reads*
data that already exists.

The main entry point is ``compute_health_summary(store, running_uids,
proxy_results)`` which returns a dict with:
  - overall_status: "healthy" | "warning" | "critical"
  - profiles_total / profiles_running / profiles_stopped
  - profiles_needing_migration
  - proxy_failures
  - crashed_sessions
  - account_status_breakdown
  - recent_activity (≤10 items)
  - issues: list of {type, user_id, detail}
"""
from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Dict, List, Optional

from .profile import ProfileStore
from .operations import list_activity
from .storage import SessionRecord


def compute_health_summary(
    store: ProfileStore,
    *,
    running_uids: Optional[List[str]] = None,
    proxy_results: Optional[Dict[str, Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """Aggregate a health summary from existing store data.

    Parameters
    ----------
    store
        The ProfileStore to read profiles, sessions, and activity from.
    running_uids
        List of currently-running user_ids (from the launcher). If
        ``None``, sessions are read from the DB.
    proxy_results
        Optional ``{user_id: {status, ip, latency_ms, error}}`` dict from
        recent proxy checks. Used to count proxy failures.

    Returns
    -------
    dict
        Health summary with the fields documented in the module docstring.
    """
    running_set = set(running_uids or [])
    proxy_results = proxy_results or {}

    # --- profiles ---
    all_profiles = store.list()
    profiles_total = len(all_profiles)
    profiles_running = sum(1 for p in all_profiles if p.user_id in running_set)
    profiles_stopped = profiles_total - profiles_running

    # --- migration: profiles with import_source_path but not yet applied ---
    profiles_needing_migration = sum(
        1 for p in all_profiles
        if p.import_source_path and not p.initial_state_applied
    )

    # --- account status breakdown ---
    status_breakdown: Dict[str, int] = {}
    for p in all_profiles:
        status_breakdown[p.account_status] = status_breakdown.get(p.account_status, 0) + 1

    # --- proxy failures ---
    proxy_failures = 0
    for uid, result in proxy_results.items():
        if isinstance(result, dict) and result.get("status") == "error":
            proxy_failures += 1

    # --- crashed sessions ---
    crashed_sessions = _count_crashed_sessions(store)

    # --- recent activity ---
    activity = list_activity(store, limit=10)
    recent_activity = [
        {
            "user_id": e.user_id,
            "action": e.action,
            "detail": e.detail if isinstance(e.detail, dict) else _safe_json(e.detail),
            "created_at": e.created_at,
        }
        for e in activity
    ]

    # --- issues list ---
    issues: List[Dict[str, Any]] = []

    for p in all_profiles:
        if p.import_source_path and not p.initial_state_applied:
            issues.append({
                "type": "migration",
                "user_id": p.user_id,
                "profile_name": p.name,
                "detail": f"Profile '{p.name}' has an AdsPower import source but initial state has not been applied yet.",
            })

    for uid, result in proxy_results.items():
        if isinstance(result, dict) and result.get("status") == "error":
            p = store.get(uid)
            name = p.name if p else uid
            issues.append({
                "type": "proxy",
                "user_id": uid,
                "profile_name": name,
                "detail": f"Profile '{name}' proxy check failed: {result.get('error', 'unknown error')}",
            })

    # Count banned/limited profiles as issues
    for p in all_profiles:
        if p.account_status in ("banned", "limited"):
            issues.append({
                "type": "account_status",
                "user_id": p.user_id,
                "profile_name": p.name,
                "detail": f"Profile '{p.name}' has account status '{p.account_status}'.",
            })

    # --- overall status ---
    if proxy_failures > 0 or crashed_sessions > 0:
        overall_status = "critical"
    elif profiles_needing_migration > 0 or any(
        p.account_status in ("banned", "limited") for p in all_profiles
    ):
        overall_status = "warning"
    else:
        overall_status = "healthy"

    return {
        "overall_status": overall_status,
        "profiles_total": profiles_total,
        "profiles_running": profiles_running,
        "profiles_stopped": profiles_stopped,
        "profiles_needing_migration": profiles_needing_migration,
        "proxy_failures": proxy_failures,
        "crashed_sessions": crashed_sessions,
        "account_status_breakdown": status_breakdown,
        "recent_activity": recent_activity,
        "issues": issues,
        "checked_at": datetime.utcnow().isoformat() + "Z",
    }


def _count_crashed_sessions(store: ProfileStore) -> int:
    """Count session records with status='crashed'."""
    from sqlmodel import Session as SqlSession, select

    try:
        with SqlSession(store.engine) as s:
            rows = s.exec(
                select(SessionRecord).where(SessionRecord.status == "crashed")
            ).all()
            return len(rows)
    except Exception:
        # If the sessions table doesn't exist yet or query fails, no crashes
        return 0


def _safe_json(raw: Any) -> Any:
    """Try to parse a JSON string; return the original on failure."""
    if isinstance(raw, str):
        try:
            return json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            return raw
    return raw
