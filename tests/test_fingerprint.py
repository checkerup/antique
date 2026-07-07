"""Tests for fingerprint generation."""
import json

import pytest

from src.core.fingerprint import (
    Fingerprint,
    build_init_script,
    generate_fingerprint,
    to_playwright_launch_options,
)


def test_generate_fingerprint_returns_full_object():
    fp = generate_fingerprint()
    # Required fields populated
    assert fp.user_agent.startswith("Mozilla/5.0")
    assert fp.platform
    assert fp.vendor
    assert fp.screen_width > 0
    assert fp.screen_height > 0
    assert fp.pixel_ratio > 0
    assert fp.timezone
    assert fp.locale
    assert fp.webgl_vendor
    assert fp.webgl_renderer
    assert fp.audio_noise_seed > 0
    assert fp.canvas_noise_seed > 0
    assert fp.noise  # hash populated
    assert fp.id     # id populated


def test_generate_fingerprint_deterministic_with_seed():
    fp1 = generate_fingerprint(seed="test-seed")
    fp2 = generate_fingerprint(seed="test-seed")
    assert fp1.canonical() == fp2.canonical()
    # Different seed → different result (very high probability)
    fp3 = generate_fingerprint(seed="other-seed")
    assert fp1.canonical() != fp3.canonical()


def test_generate_fingerprint_for_each_os():
    for os_family in ("windows", "macos", "linux"):
        fp = generate_fingerprint(os_family=os_family)
        if os_family == "windows":
            assert "Windows" in fp.user_agent
            assert fp.platform == "Win32"
        elif os_family == "macos":
            assert "Macintosh" in fp.user_agent
            assert fp.platform == "MacIntel"
        elif os_family == "linux":
            assert "Linux" in fp.user_agent
            assert "Linux" in fp.platform


def test_fingerprint_os_consistency():
    """Locale + timezone should be coherent (both from the same locale pool)."""
    fp = generate_fingerprint(seed="consistent")
    # Whatever locale it picked, the timezone should be in that locale's pool
    # We don't hard-code the pool here, just sanity-check timezone is set.
    assert "/" in fp.timezone


def test_to_playwright_launch_options_contains_args():
    fp = generate_fingerprint(seed="x")
    opts = to_playwright_launch_options(fp)
    assert "args" in opts
    assert any("--disable-blink-features=AutomationControlled" in a for a in opts["args"])
    assert any(f"--lang={fp.locale}" in a for a in opts["args"])
    assert opts["locale"] == fp.locale
    assert opts["timezone_id"] == fp.timezone
    assert opts["user_agent"] == fp.user_agent
    assert opts["device_scale_factor"] == fp.pixel_ratio


def test_to_playwright_launch_options_with_proxy():
    fp = generate_fingerprint(seed="x")
    opts = to_playwright_launch_options(fp, proxy={"server": "http://1.2.3.4:8080"})
    assert opts["proxy"]["server"] == "http://1.2.3.4:8080"


def test_build_init_script_returns_valid_js():
    fp = generate_fingerprint(seed="x")
    js = build_init_script(fp)
    # Must NOT still contain the placeholder
    assert "__AD_CFG__" not in js
    # Should be non-trivial JS
    assert "Navigator" in js
    assert "cfg.platform" in js
    assert "cfg.webgl_vendor" in js
    # Config serialised
    assert fp.platform in js
    assert fp.webgl_renderer in js


def test_init_script_handles_special_chars():
    """Quotes / backslashes in config must not break the JS template literal."""
    fp = Fingerprint(
        platform="Win32",
        vendor='weird "vendor" with \\backslashes',
        webgl_vendor="A & B <c> 'd'",
        webgl_renderer="R",
    )
    js = build_init_script(fp)
    # Should still produce parseable JS (we don't run it here, but it must
    # at least be syntactically valid JSON in the inlined cfg block)
    assert '"platform":"Win32"' in js
    # Quotes are escaped via json.dumps default
    assert '\\"' in js or '\\\\' in js


def test_fingerprint_canonical_is_json_safe():
    fp = generate_fingerprint()
    d = fp.canonical()
    # Should round-trip via JSON without errors
    s = json.dumps(d)
    d2 = json.loads(s)
    assert d == d2