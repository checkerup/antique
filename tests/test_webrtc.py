"""Tests for WebRTC handling modes (block | real | proxy).

Covers the fingerprint field wiring, the effective-mode derivation (legacy
``block_webrtc_ip`` fallback), the init-script config inlining, backward
compatibility for profiles stored before these fields existed, and the
optional WebRTC leak checks in the stealth detect harness.

All tests are browser-free: they assert on generated JS strings and on the
pure scorer, exactly like the existing fingerprint/detect suites.
"""
import json
from dataclasses import fields

import pytest

from src.core.fingerprint import (
    Fingerprint,
    WEBRTC_MODES,
    build_init_script,
    effective_webrtc_mode,
    generate_fingerprint,
    set_webrtc_mode,
)
from src.core.detect import (
    build_webrtc_probe_script,
    expected_from_fingerprint,
    score_report,
    _is_private_ip,
)


# ---------------------------------------------------------------------------
# Fields + effective mode
# ---------------------------------------------------------------------------


def test_new_fields_have_backward_compatible_defaults():
    fp = Fingerprint()
    assert fp.webrtc_mode == ""
    assert fp.webrtc_public_ip == ""
    # Empty mode + legacy block flag True -> block.
    assert fp.block_webrtc_ip is True
    assert effective_webrtc_mode(fp) == "block"


def test_generate_leaves_webrtc_mode_unset_and_blocking():
    """Generation must not change legacy behaviour (blocking by default)."""
    fp = generate_fingerprint(seed="webrtc-gen")
    assert fp.webrtc_mode == ""
    assert fp.webrtc_public_ip == ""
    assert effective_webrtc_mode(fp) == "block"


def test_effective_mode_derives_from_legacy_flag():
    # No explicit mode, block flag False -> "real".
    fp = Fingerprint(block_webrtc_ip=False)
    assert effective_webrtc_mode(fp) == "real"
    # No explicit mode, block flag True -> "block".
    fp2 = Fingerprint(block_webrtc_ip=True)
    assert effective_webrtc_mode(fp2) == "block"


def test_explicit_mode_wins_over_legacy_flag():
    fp = Fingerprint(block_webrtc_ip=True, webrtc_mode="real")
    assert effective_webrtc_mode(fp) == "real"


def test_effective_mode_is_case_insensitive_and_trimmed():
    fp = Fingerprint(webrtc_mode="  PROXY ")
    assert effective_webrtc_mode(fp) == "proxy"


def test_unknown_mode_falls_back_to_legacy():
    fp = Fingerprint(webrtc_mode="garbage", block_webrtc_ip=True)
    assert effective_webrtc_mode(fp) == "block"


# ---------------------------------------------------------------------------
# set_webrtc_mode helper
# ---------------------------------------------------------------------------


def test_set_webrtc_mode_block_keeps_flag_coherent():
    fp = Fingerprint(block_webrtc_ip=False)
    set_webrtc_mode(fp, "block")
    assert fp.webrtc_mode == "block"
    assert fp.block_webrtc_ip is True


def test_set_webrtc_mode_real_clears_block_flag():
    fp = Fingerprint(block_webrtc_ip=True)
    set_webrtc_mode(fp, "real")
    assert fp.webrtc_mode == "real"
    assert fp.block_webrtc_ip is False


def test_set_webrtc_mode_proxy_sets_public_ip():
    fp = Fingerprint()
    set_webrtc_mode(fp, "proxy", public_ip=" 203.0.113.7 ")
    assert fp.webrtc_mode == "proxy"
    assert fp.webrtc_public_ip == "203.0.113.7"
    assert fp.block_webrtc_ip is False


def test_set_webrtc_mode_rejects_unknown():
    fp = Fingerprint()
    with pytest.raises(ValueError):
        set_webrtc_mode(fp, "tunnel")


def test_webrtc_modes_constant():
    assert WEBRTC_MODES == ("block", "real", "proxy")


# ---------------------------------------------------------------------------
# Init-script config inlining
# ---------------------------------------------------------------------------


def test_init_script_inlines_block_mode_by_default():
    fp = generate_fingerprint(seed="init-block")
    js = build_init_script(fp)
    assert '"webrtc_mode":"block"' in js
    # The mode dispatcher + block branch must be present.
    assert "wmode === 'block'" in js
    assert "iceServers: []" in js


def test_init_script_inlines_real_mode():
    fp = Fingerprint(webrtc_mode="real", fonts=["Arial"])
    js = build_init_script(fp)
    assert '"webrtc_mode":"real"' in js


def test_init_script_inlines_proxy_mode_and_public_ip():
    fp = Fingerprint(fonts=["Arial"])
    set_webrtc_mode(fp, "proxy", public_ip="198.51.100.42")
    js = build_init_script(fp)
    assert '"webrtc_mode":"proxy"' in js
    assert '"webrtc_public_ip":"198.51.100.42"' in js
    # Rewrite machinery present in the template.
    assert "wmode === 'proxy'" in js
    assert "c=IN IP4 " in js
    assert "RTCIceCandidate" in js


def test_init_script_proxy_mode_covers_ipv6():
    """IPv6 candidates must also be rewritten in proxy mode (no real IPv6 leak)."""
    fp = Fingerprint(fonts=["Arial"])
    set_webrtc_mode(fp, "proxy", public_ip="198.51.100.42")
    js = build_init_script(fp)
    # IPv6 regex + a documentation-range replacement address
    assert "c=IN IP6 " in js
    assert "2001:db8::1" in js
    assert "IP6" in js


def test_init_script_block_mode_untouched_by_ipv6():
    """Block mode (empty iceServers) doesn't need IPv6 handling — no candidates at all."""
    fp = generate_fingerprint(seed="block-ipv6")
    js = build_init_script(fp)
    assert "iceServers: []" in js


# ---------------------------------------------------------------------------
# Round-trip / persistence safety
# ---------------------------------------------------------------------------


def test_canonical_json_round_trip_includes_webrtc_fields():
    fp = generate_fingerprint(seed="rt-webrtc")
    set_webrtc_mode(fp, "proxy", public_ip="192.0.2.9")
    d = fp.canonical()
    assert "webrtc_mode" in d and "webrtc_public_ip" in d
    d2 = json.loads(json.dumps(d))
    assert d == d2


def test_resolve_from_legacy_stored_dict_without_new_fields():
    """A profile stored before these fields existed must load cleanly."""
    legacy = {
        "user_agent": "UA",
        "platform": "Win32",
        "block_webrtc_ip": True,
        # note: no webrtc_mode / webrtc_public_ip keys
    }
    valid = {f.name for f in fields(Fingerprint)}
    fp = Fingerprint(**{k: v for k, v in legacy.items() if k in valid})
    assert fp.webrtc_mode == ""
    assert effective_webrtc_mode(fp) == "block"


def test_resolve_ignores_unknown_keys():
    stored = {"webrtc_mode": "proxy", "webrtc_public_ip": "1.2.3.4", "bogus": 1}
    valid = {f.name for f in fields(Fingerprint)}
    fp = Fingerprint(**{k: v for k, v in stored.items() if k in valid})
    assert fp.webrtc_mode == "proxy"
    assert fp.webrtc_public_ip == "1.2.3.4"


# ---------------------------------------------------------------------------
# Detect harness: WebRTC leak checks (pure scorer)
# ---------------------------------------------------------------------------


def _base_signals(**overrides):
    s = {
        "webdriver": False,
        "has_chrome": True,
        "has_chrome_runtime": True,
        "plugins_count": 3,
        "languages_count": 2,
        "platform": "Win32",
        "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/125.0.0.0",
        "hardware_concurrency": 8,
        "timezone": "America/New_York",
        "webgl_vendor": "Google Inc. (NVIDIA)",
        "permission_mismatch": False,
    }
    s.update(overrides)
    return s


def test_scorer_skips_webrtc_check_without_collected_ips():
    """No webrtc_ips in signals -> no webrtc checks added (guarded)."""
    fp = Fingerprint()  # block mode
    report = score_report(_base_signals(), expected=expected_from_fingerprint(fp))
    names = {c.name for c in report.checks}
    assert "webrtc_no_leak" not in names
    assert "webrtc_matches_proxy" not in names


def test_scorer_block_mode_flags_leak():
    fp = Fingerprint()  # block
    signals = _base_signals(webrtc_ips=["192.168.1.5"])
    report = score_report(signals, expected=expected_from_fingerprint(fp))
    failed = {c.name for c in report.failed_checks}
    assert "webrtc_no_leak" in failed


def test_scorer_block_mode_passes_with_no_ips():
    fp = Fingerprint()  # block
    signals = _base_signals(webrtc_ips=[])
    report = score_report(signals, expected=expected_from_fingerprint(fp))
    failed = {c.name for c in report.failed_checks}
    assert "webrtc_no_leak" not in failed


def test_scorer_proxy_mode_passes_when_only_proxy_ip():
    fp = Fingerprint()
    set_webrtc_mode(fp, "proxy", public_ip="203.0.113.7")
    signals = _base_signals(webrtc_ips=["203.0.113.7"])
    report = score_report(signals, expected=expected_from_fingerprint(fp))
    failed = {c.name for c in report.failed_checks}
    assert "webrtc_matches_proxy" not in failed


def test_scorer_proxy_mode_flags_private_leak():
    fp = Fingerprint()
    set_webrtc_mode(fp, "proxy", public_ip="203.0.113.7")
    signals = _base_signals(webrtc_ips=["203.0.113.7", "10.0.0.4"])
    report = score_report(signals, expected=expected_from_fingerprint(fp))
    failed = {c.name for c in report.failed_checks}
    assert "webrtc_matches_proxy" in failed


def test_scorer_real_mode_adds_no_webrtc_check():
    fp = Fingerprint(webrtc_mode="real")
    signals = _base_signals(webrtc_ips=["10.0.0.4"])
    report = score_report(signals, expected=expected_from_fingerprint(fp))
    names = {c.name for c in report.checks}
    assert "webrtc_no_leak" not in names
    assert "webrtc_matches_proxy" not in names


def test_is_private_ip():
    assert _is_private_ip("10.0.0.1")
    assert _is_private_ip("192.168.1.1")
    assert _is_private_ip("172.16.5.4")
    assert _is_private_ip("127.0.0.1")
    assert _is_private_ip("169.254.10.10")
    assert not _is_private_ip("203.0.113.7")
    assert not _is_private_ip("8.8.8.8")
    assert not _is_private_ip("not-an-ip")


# ---------------------------------------------------------------------------
# WebRTC probe script
# ---------------------------------------------------------------------------


def test_webrtc_probe_script_shape():
    js = build_webrtc_probe_script(timeout_ms=800)
    assert "RTCPeerConnection" in js
    assert "webrtc_ips" in js
    assert "Promise" in js
    assert "800" in js  # timeout inlined


def test_expected_from_fingerprint_carries_webrtc_fields():
    fp = Fingerprint()
    set_webrtc_mode(fp, "proxy", public_ip="192.0.2.1")
    exp = expected_from_fingerprint(fp)
    assert exp["webrtc_mode"] == "proxy"
    assert exp["webrtc_public_ip"] == "192.0.2.1"
