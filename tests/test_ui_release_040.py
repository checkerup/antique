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
        "Folders", "Export activity", "Extension catalog", "MCP status", "changeSort", "/user/bulk/fingerprint/randomize",
        "/user/bulk/proxy/import", "/sync/run", "/group/create", "/backup/schedules", "/activity/export",
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


def test_randomize_modal_has_clean_checkbox_layout():
    """Bug #2: randomize modal checkboxes use flex groups with separators."""
    html = UI.read_text(encoding="utf-8")
    assert 'class="checkbox-group"' in html
    assert 'class="group-sep"' in html
    # Both shared and preserve groups use the flex container
    assert html.count('class="checkbox-group"') >= 2
    # Separator between the two groups
    assert html.count('class="group-sep"') >= 1


def test_randomize_modal_has_overrides_panel():
    """Bug #1: overrides checkbox + input panel with the full field set."""
    html = UI.read_text(encoding="utf-8")
    assert 'id="rnd-overrides-enabled"' in html
    assert 'id="rnd-overrides-panel"' in html
    assert 'id="rnd-ov-user-agent"' in html
    assert 'id="rnd-ov-platform"' in html
    assert 'id="rnd-ov-screen-width"' in html
    assert 'id="rnd-ov-screen-height"' in html
    assert 'id="rnd-ov-hardware-concurrency"' in html
    assert 'id="rnd-ov-device-memory"' in html
    assert 'id="rnd-ov-webgl-vendor"' in html
    assert 'id="rnd-ov-webgl-renderer"' in html
    assert 'id="rnd-ov-timezone"' in html
    assert 'id="rnd-ov-languages"' in html
    assert 'onchange="toggleOverridesPanel()"' in html
    assert (ROOT / "QUICKSTART.md").exists()
    assert (ROOT / "docs" / "AGENT-TESTING.md").exists()
    assert (ROOT / "docs" / "MANUAL-TEST-PLAN.md").exists()
    assert (ROOT / "docs" / "RELEASE-0.7.0-REPORT.md").exists()
    assert (ROOT / "docs" / "OWNER-FULL-TEST-CHECKLIST.md").exists()
