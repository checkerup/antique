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


def _read():
    return UI.read_text(encoding="utf-8-sig")


# ---------------------------------------------------------------------------
# Health summary bar
# ---------------------------------------------------------------------------


def test_dashboard_has_health_bar():
    html = _read()
    assert 'class="health-bar"' in html
    assert 'id="health-bar"' in html
    assert 'role="status"' in html
    assert 'aria-live="polite"' in html
    assert 'aria-busy="true"' in html


def test_dashboard_has_health_status_indicators():
    html = _read()
    assert "health-dot" in html
    assert "health-dot healthy" in html
    assert "health-dot warning" in html
    assert "health-dot critical" in html
    assert 'id="health-label"' in html


def test_dashboard_has_health_stats():
    html = _read()
    assert 'id="hs-total"' in html
    assert 'id="hs-running"' in html
    assert 'id="hs-migration"' in html
    assert 'id="hs-proxy"' in html
    assert 'id="hs-crashed"' in html


def test_dashboard_has_health_details_toggle():
    html = _read()
    assert 'id="health-details"' in html
    assert 'id="issues-list"' in html
    assert "toggleHealthDetails" in html


def test_dashboard_calls_loadHealth():
    html = _read()
    assert "loadHealth()" in html
    assert "setInterval(loadHealth" in html
    assert "/diagnostics/summary" in html


def test_dashboard_has_renderIssues_function():
    html = _read()
    assert "function renderIssues" in html
    assert "issue-row" in html
    assert "issue-type" in html


# ---------------------------------------------------------------------------
# Toast notifications
# ---------------------------------------------------------------------------


def test_dashboard_has_toast_notification():
    html = _read()
    assert 'class="toast"' in html
    assert 'id="toast"' in html
    assert 'id="toast-msg"' in html
    assert "function showToast" in html
    assert "function hideToast" in html
    assert 'role="alert"' in html
    assert 'aria-live="assertive"' in html


# ---------------------------------------------------------------------------
# Per-profile diagnostics
# ---------------------------------------------------------------------------


def test_dashboard_has_diagnose_button():
    html = _read()
    assert "diagnoseProfile" in html
    assert 'class="btn sm diag"' in html
    assert "Diag" in html


def test_dashboard_has_diagnose_modal():
    html = _read()
    assert 'id="diagnoseModal"' in html
    assert 'id="diag-body"' in html
    assert 'id="diag-name"' in html
    assert "function diagnoseProfile" in html
    assert "function closeDiagnose" in html


def test_diagnose_uses_diagnostics_endpoint():
    html = _read()
    js = html[html.find("<script"):html.find("</script>")]
    assert "/diagnostics/summary" in js


# ---------------------------------------------------------------------------
# Workflow: start / attach automation
# ---------------------------------------------------------------------------


def test_dashboard_has_attach_button_for_running_profiles():
    html = _read()
    assert "openCdp" in html
    assert "Attach" in html
    assert "function openCdp" in html


# ---------------------------------------------------------------------------
# Workflow: create profile with inline validation
# ---------------------------------------------------------------------------


def test_create_profile_uses_toast_not_alert():
    html = _read()
    js = html[html.find("<script"):html.find("</script>")]
    # The submitCreate function should use showToast, not alert
    create_section = js[js.find("async function submitCreate"):js.find("async function submitImport")]
    assert "showToast" in create_section
    assert "loading" in create_section  # button loading state


def test_create_profile_has_inline_validation():
    html = _read()
    assert 'class="field-error"' in html or "field-error" in html
    assert "invalid" in html


# ---------------------------------------------------------------------------
# Workflow: start/stop with loading state
# ---------------------------------------------------------------------------


def test_act_function_has_loading_state():
    html = _read()
    js = html[html.find("<script"):html.find("</script>")]
    act_section = js[js.find("async function act("):js.find("async function del(")]
    assert "loading" in act_section
    assert "showToast" in act_section


# ---------------------------------------------------------------------------
# Accessibility
# ---------------------------------------------------------------------------


def test_buttons_have_aria_labels():
    html = _read()
    assert 'aria-label="Start' in html
    assert 'aria-label="Stop' in html
    assert 'aria-label="Attach' in html
    assert 'aria-label="Diagnose' in html


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
        "AdsPower backup folder",
        "Smart fingerprint randomization",
        "Recent activity",
        "Resource status",
        "Backup schedules",
        "Mass create",
        "Proxy provider",
        "MCP status",
        "Extension catalog",
        "data-theme=\"dark\"",
        "oklch(",
    ):
        assert marker in html, f"missing existing marker: {marker}"
