"""Tests for DevTools stealth — hiding DevTools open state from sites."""
from src.core.fingerprint import Fingerprint, build_init_script, generate_fingerprint, set_webrtc_mode


def test_init_script_includes_devtools_stealth():
    """The init script patches DevTools detection vectors."""
    fp = generate_fingerprint(seed="devtools")
    js = build_init_script(fp)
    # (1) console.debug timing suppression
    assert "console.debug" in js
    assert "DevTools stealth" in js or "devtools" in js.lower()
    # (2) window.chrome.runtime removal
    assert "window.chrome.runtime" in js or "chrome.runtime" in js
    # (3) outerWidth/outerHeight spoofing (docked-DevTools heuristic)
    assert "outerWidth" in js or "outerHeight" in js
    # (4) webdriver false (always present, but verify it's there)
    assert "webdriver" in js


def test_launch_options_include_devtools_args():
    """Chromium launch args avoid flags Google treats as insecure."""
    fp = generate_fingerprint(seed="devtools-args")
    from src.core.fingerprint import to_playwright_launch_options
    opts = to_playwright_launch_options(fp)
    args = opts.get("args", [])
    assert not any("AutomationControlled" in a for a in args)
    assert not any("disable-web-security" in a for a in args)
    assert not any("auto-open-devtools" in a for a in args)


def test_devtools_stealth_does_not_break_webrtc():
    """DevTools stealth and WebRTC modes coexist (no conflicts)."""
    fp = generate_fingerprint(seed="devtools-webrtc")
    set_webrtc_mode(fp, "proxy", public_ip="203.0.113.7")
    js = build_init_script(fp)
    # Both stealth and WebRTC proxy rewriting present
    assert "console.debug" in js
    assert "webrtc_mode" in js or "webrtc" in js
