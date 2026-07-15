"""Static contract tests for the 0.4.0 dashboard and Windows launcher."""
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
UI = ROOT / "src" / "ui" / "templates" / "index.html"


def test_dashboard_contains_core_product_workflows():
    html = UI.read_text(encoding="utf-8")
    for marker in (
        "data-theme=\"dark\"",
        "Assign proxies",
        "Smart fingerprint randomization",
        "Run flow on selected profiles",
        "Manage profile",
        "AdsPower backup folder",
        "Live View",
        "/user/bulk/fingerprint/randomize",
        "/user/bulk/proxy/import",
        "/sync/run",
        "/extension/list",
    ):
        assert marker in html


def test_dashboard_uses_oklch_and_has_no_gradient_logo():
    html = UI.read_text(encoding="utf-8")
    assert "oklch(" in html
    assert "linear-gradient" not in html
    assert "border-left:3px" not in html


def test_start_bat_prepares_all_bundled_engines():
    bat = (ROOT / "start.bat").read_text(encoding="utf-8")
    assert "playwright install chromium firefox webkit" in bat
    assert "python -m camoufox fetch" in bat
    assert ".antique-browsers-v2" in bat


def test_release_docs_exist():
    assert (ROOT / "docs" / "AGENT-TESTING.md").exists()
    assert (ROOT / "docs" / "MANUAL-TEST-PLAN.md").exists()
    assert (ROOT / "docs" / "RELEASE-0.4.0-REPORT.md").exists()
