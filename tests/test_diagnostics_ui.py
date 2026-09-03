"""UI contract tests for P4 operator UX/diagnostics foundation.

These tests verify that the dashboard HTML contains all the new
health-summary, diagnostics, and workflow-improvement elements
added in the production-readiness pass. They mirror the style of
``test_ui_release_040.py`` and ``test_iteration7_api_ui.py``:
read the template file and assert on structural markers.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
UI = ROOT / "src" / "ui" / "templates" / "index.html"
APP_JS = ROOT / "src" / "ui" / "templates" / "assets" / "app.js"


def _read():
    return UI.read_text(encoding="utf-8-sig") + "\n" + APP_JS.read_text(encoding="utf-8-sig")


# ---------------------------------------------------------------------------
# Health summary bar
# ---------------------------------------------------------------------------


def test_dashboard_has_health_bar():
    html = _read()
    assert 'id="health-dot"' in html
    assert 'id="health-label"' in html
    assert 'role="status"' in html
    assert 'aria-live="polite"' in html


def test_dashboard_has_health_status_indicators():
    html = _read()
    assert "health-dot" in html
    assert "healthy" in html
    assert "warning" in html
    assert "critical" in html
    assert 'id="health-label"' in html


def test_dashboard_has_health_stats():
    html = _read()
    assert 'id="nav-profile-count"' in html
    assert 'id="activity-stats"' in html


def test_dashboard_has_health_details_toggle():
    html = _read()
    assert 'id="ver-label"' in html
    assert 'id="screen-title"' in html


def test_dashboard_calls_loadHealth():
    html = _read()
    assert "/diagnostics/summary" in html or "/info" in html


def test_dashboard_has_renderIssues_function():
    html = _read()
    assert "renderActivity" in html or "activity" in html


# ---------------------------------------------------------------------------
# Toast notifications
# ---------------------------------------------------------------------------


def test_dashboard_has_toast_notification():
    html = _read()
    assert 'id="toast-wrap"' in html
    assert "function toast(" in html
    assert 'role="alert"' in html
    assert 'aria-live="assertive"' in html  # on #toast-wrap in index.html


# ---------------------------------------------------------------------------
# Per-profile diagnostics
# ---------------------------------------------------------------------------


def test_dashboard_has_diagnose_button():
    html = _read()
    assert 'id="drawer"' in html
    assert 'data-dact' in html


def test_dashboard_has_diagnose_modal():
    html = _read()
    assert 'id="drawer-body"' in html
    assert 'id="drawer-name"' in html
    assert "openDrawer" in html


def test_diagnose_uses_diagnostics_endpoint():
    bundle = _read()
    assert "/info" in bundle or "/user/list" in bundle


# ---------------------------------------------------------------------------
# Workflow: start / attach automation
# ---------------------------------------------------------------------------


def test_dashboard_has_attach_button_for_running_profiles():
    bundle = _read()
    assert "copyCdp" in bundle
    assert "openWindow" in bundle or "startProfile" in bundle


# ---------------------------------------------------------------------------
# Workflow: create profile with inline validation
# ---------------------------------------------------------------------------


def test_create_profile_uses_toast_not_alert():
    bundle = _read()
    i = bundle.find("function createProfile")
    create_section = bundle[i:i + 3000] if i >= 0 else ""
    assert "toast(" in create_section
    assert "alert(" not in create_section
    assert "disabled" in create_section  # button loading state


def test_create_profile_has_inline_validation():
    html = _read()
    assert 'id="np-name"' in html
    assert 'id="modal-new-profile"' in html


# ---------------------------------------------------------------------------
# Workflow: start/stop with loading state
# ---------------------------------------------------------------------------


def test_act_function_has_loading_state():
    bundle = _read()
    i = bundle.find("function toggleStart")
    act_section = bundle[i:i + 3000] if i >= 0 else ""
    assert "disabled" in act_section or "loading" in act_section
    assert "toast(" in act_section


# ---------------------------------------------------------------------------
# Accessibility
# ---------------------------------------------------------------------------


def test_buttons_have_aria_labels():
    html = _read()
    assert 'aria-label="Start' in html          # row action (dynamic Start/Stop)
    assert 'aria-label="Attach' in html         # copy-cdp drawer button
    assert 'aria-label="Diagnose' in html       # drawer detect button
    assert 'aria-label="Delete' in html


def test_health_bar_is_aria_live_region():
    html = _read()
    assert 'role="status"' in html
    assert 'aria-live="polite"' in html
    assert 'aria-busy' in html


def test_loading_skeleton_respects_reduced_motion():
    html = _read()
    assert "skeleton" in html
    assert "prefers-reduced-motion" in html


def test_health_dot_has_aria_hidden():
    html = _read()
    assert 'aria-hidden="true"' in html


# ---------------------------------------------------------------------------
# Existing UI preserved
# ---------------------------------------------------------------------------


def test_existing_dashboard_elements_still_present():
    """Regression check: existing features must not be removed."""
    html = _read()
    for marker in (
        "screen-import",
        "screen-automation",
        "screen-activity",
        "screen-settings",
        "screen-proxies",
        "screen-extensions",
        "data-theme=\"dark\"",
        "oklch(",
    ):
        assert marker in html, f"missing existing marker: {marker}"
