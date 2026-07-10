"""Tests for the stealth self-test harness (score_report + collector)."""
import pytest

from src.core.detect import (
    Report,
    build_collector_script,
    expected_from_fingerprint,
    score_report,
)
from src.core.fingerprint import generate_fingerprint


def _clean_signals(**overrides):
    """A signals dict that should pass every base check."""
    s = {
        "webdriver": False,
        "has_chrome": True,
        "has_chrome_runtime": True,
        "plugins_count": 3,
        "languages_count": 2,
        "language": "en-US",
        "platform": "Win32",
        "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/125.0.0.0",
        "hardware_concurrency": 8,
        "device_memory": 8,
        "timezone": "America/New_York",
        "webgl_vendor": "Google Inc. (NVIDIA)",
        "webgl_renderer": "ANGLE (NVIDIA, RTX 3060)",
        "has_webgpu": True,
        "permission_mismatch": False,
    }
    s.update(overrides)
    return s


def test_collector_script_is_nontrivial_js():
    js = build_collector_script()
    assert "navigator.webdriver" in js
    assert "WEBGL_debug_renderer_info" in js
    assert "resolvedOptions" in js  # timezone
    assert "return s" in js


def test_clean_profile_scores_A_and_passes():
    report = score_report(_clean_signals())
    assert isinstance(report, Report)
    assert report.ok()
    assert report.score() == 100
    assert report.grade() == "A"
    assert not report.failed_checks


def test_webdriver_leak_is_critical_failure():
    report = score_report(_clean_signals(webdriver=True))
    assert not report.ok()  # critical failed
    assert report.grade() in ("C", "D", "F")
    names = {c.name for c in report.failed_checks}
    assert "webdriver_false" in names


def test_missing_window_chrome_penalised_but_not_critical():
    report = score_report(_clean_signals(has_chrome=False, has_chrome_runtime=False))
    # window.chrome is high, runtime is medium -> 20 + 10 = 30 penalty
    assert report.ok()  # no critical failed
    assert report.score() == 70
    names = {c.name for c in report.failed_checks}
    assert "has_window_chrome" in names
    assert "chrome_runtime_present" in names


def test_permission_mismatch_flagged():
    report = score_report(_clean_signals(permission_mismatch=True))
    names = {c.name for c in report.failed_checks}
    assert "permissions_coherent" in names


def test_platform_ua_mismatch_flagged():
    report = score_report(_clean_signals(platform="MacIntel"))  # UA is Windows
    names = {c.name for c in report.failed_checks}
    assert "platform_matches_ua" in names


def test_no_languages_is_high_severity():
    report = score_report(_clean_signals(languages_count=0))
    names = {c.name for c in report.failed_checks}
    assert "languages_present" in names
    assert report.score() == 80  # single high failure


def test_expected_cross_check_matches():
    fp = generate_fingerprint(seed="detect")
    expected = expected_from_fingerprint(fp)
    signals = _clean_signals(
        webgl_vendor=fp.webgl_vendor,
        timezone=fp.timezone,
        platform=fp.platform,
        languages_count=len(fp.languages),
        user_agent=fp.user_agent,
    )
    report = score_report(signals, expected=expected)
    names = {c.name for c in report.failed_checks}
    assert "webgl_vendor_matches_expected" not in names
    assert "timezone_matches_expected" not in names


def test_expected_cross_check_detects_mismatch():
    fp = generate_fingerprint(seed="detect2")
    expected = expected_from_fingerprint(fp)
    # Collected values differ from the intended fingerprint -> mismatches.
    signals = _clean_signals(
        webgl_vendor="Google Inc. (AMD)",
        timezone="Europe/Moscow",
    )
    expected["webgl_vendor"] = "Google Inc. (Intel)"
    expected["timezone"] = "Asia/Tokyo"
    report = score_report(signals, expected=expected)
    names = {c.name for c in report.failed_checks}
    assert "webgl_vendor_matches_expected" in names
    assert "timezone_matches_expected" in names


def test_report_to_dict_shape():
    d = score_report(_clean_signals()).to_dict()
    assert set(d) >= {"score", "grade", "ok", "passed", "total", "checks", "failures"}
    assert d["score"] == 100
    assert d["total"] == len(d["checks"])


def test_grade_boundaries():
    # Force specific scores via crafted failures.
    # One critical (40) -> 60 -> C
    r = score_report(_clean_signals(webdriver=True))
    assert r.score() == 60
    assert r.grade() == "C"
