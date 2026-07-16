"""Static contract tests for the dashboard and release operations."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
UI = ROOT / "src" / "ui" / "templates" / "index.html"


def test_dashboard_contains_all_owner_workflows():
    html = UI.read_text(encoding="utf-8")
    for marker in (
        "data-theme=\"dark\"", "AdsPower backup folder", "Assign proxies",
        "Smart fingerprint randomization", "Run flow on selected profiles",
        "Manage profile", "Preview AdsPower backup", "Recent activity",
        "Resource status", "Backup schedules", "Mass create", "Proxy provider",
        "Folders", "changeSort", "/user/bulk/fingerprint/randomize",
        "/user/bulk/proxy/import", "/sync/run", "/group/create", "/backup/schedules",
    ):
        assert marker in html


def test_dashboard_uses_oklch_and_responsive_states():
    html = UI.read_text(encoding="utf-8")
    assert "oklch(" in html
    assert "@media(max-width:720px)" in html
    assert "Can't reach the server" in html
    assert "No profiles" in html


def test_start_bat_and_docs_exist():
    assert (ROOT / "start.bat").exists()
    assert (ROOT / "QUICKSTART.md").exists()
    assert (ROOT / "docs" / "AGENT-TESTING.md").exists()
    assert (ROOT / "docs" / "MANUAL-TEST-PLAN.md").exists()
    assert (ROOT / "docs" / "RELEASE-0.7.0-REPORT.md").exists()
