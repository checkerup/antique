"""Static contract tests for the SPA dashboard and release operations.

The dashboard is now a split SPA (index.html + assets/app.js + i18n dicts),
so contracts assert across the bundle. Intent of every original check is kept:
owner workflows present, OKLCH theme + responsive, clean randomize modal.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
UI = ROOT / "src" / "ui" / "templates" / "index.html"
APP_JS = ROOT / "src" / "ui" / "templates" / "assets" / "app.js"
BUNDLE = UI.read_text(encoding="utf-8-sig") + "\n" + APP_JS.read_text(encoding="utf-8-sig")


def test_dashboard_contains_all_owner_workflows():
    html = BUNDLE
    for marker in (
        "id=\"migrate-path\"",           # AdsPower backup folder picker
        "id=\"migrate-preview-btn\"",    # Preview AdsPower backup
        "id=\"proxy-import-btn\"",       # Import / assign proxies
        "id=\"proxy-lines\"",            # Proxy lines area
        "rnd-shared",                      # Smart fingerprint randomization
        "id=\"flow-json\"",              # Run flow on selected profiles
        "id=\"drawer\"",                  # Manage profile
        "id=\"activity-list\"",          # Recent activity
        "id=\"resource-status\"",        # Resource status
        "id=\"schedule-list\"",          # Backup schedules
        "modal-mass",                      # Mass create
        "id=\"cookie-import-btn\"",     # Cookie import
        "id=\"screen-groups\"",          # Folders
        "activity-export",                 # Export activity
        "id=\"ext-search-q\"",           # Extension catalog
        "id=\"mcp-summary\"",           # MCP status
        "/user/bulk/fingerprint/randomize",
        "/user/bulk/proxy/import",
        "/sync/run",
        "/group/create",
        "/backup/schedules",
        "/activity/export",
    ):
        assert marker in html, marker


def test_dashboard_uses_oklch_and_responsive_states():
    html = UI.read_text(encoding="utf-8-sig")
    assert "oklch(" in html
    assert "@media (max-width: 900px)" in html or "@media(max-width:720px)" in html
    # i18n fallback strings live in the dict, table empty state in html
    assert "No profiles" in (UI.read_text(encoding="utf-8-sig") + (ROOT / "src/ui/templates/assets/i18n.js").read_text(encoding="utf-8-sig"))


def test_start_bat_and_docs_exist():
    assert (ROOT / "start.bat").exists()


def test_randomize_modal_has_clean_checkbox_layout():
    """Bug #2: randomize modal checkboxes use flex groups with separators."""
    html = UI.read_text(encoding="utf-8-sig")
    assert 'class="checkbox-group"' in html
    assert 'class="group-sep"' in html
    assert html.count('class="checkbox-group"') >= 2
    assert html.count('class="group-sep"') >= 1


def test_randomize_modal_has_overrides_panel():
    """Bug #1: overrides checkbox + input panel with the full field set."""
    html = UI.read_text(encoding="utf-8-sig")
    assert 'id="rnd-overrides-enabled"' in html
    assert 'id="rnd-overrides-panel"' in html
    for field in ("user-agent", "platform", "screen-width", "screen-height",
                  "hardware-concurrency", "device-memory", "webgl-vendor",
                  "webgl-renderer", "timezone", "languages"):
        assert f'id="rnd-ov-{field}"' in html, field
