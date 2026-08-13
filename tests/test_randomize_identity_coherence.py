"""Regression tests: batch randomization must keep the identity set coherent.

user_agent, platform, vendor and oscpu are all functions of one OS. Copying or
overriding them individually — which ``preserve_fields`` and ``overrides`` both
do — used to leave e.g. a Windows UA next to platform "MacIntel", failing the
critical ua_platform_coherence audit check.
"""
from dataclasses import asdict

import pytest

from src.core.detect import score_fingerprint
from src.core.fingerprint import generate_fingerprint
from src.core.fingerprint_ops import os_family_from_ua, randomize_batch

OS_FAMILIES = ("windows", "macos", "linux")


def _profile(os_family, seed="base"):
    return asdict(generate_fingerprint(seed=seed, os_family=os_family))


def _checks(fp):
    return {c["name"]: c["ok"] for c in score_fingerprint(fp).to_dict()["checks"]}


def _assert_clean(fp, context):
    report = score_fingerprint(fp).to_dict()
    failed = [c["name"] for c in report["checks"] if not c["ok"]]
    assert failed == [], f"{context}: audit failures {failed}"
    assert report["score"] == 100, f"{context}: score {report['score']}"


# --------------------------------------------------------------------------
# UA inference
# --------------------------------------------------------------------------

@pytest.mark.parametrize("ua,expected", [
    ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/126.0.0.0", "windows"),
    ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) Chrome/126.0.0.0", "macos"),
    ("Mozilla/5.0 (X11; Linux x86_64) Chrome/126.0.0.0", "linux"),
    ("", None),
    ("CustomAgent/1.0", None),
])
def test_os_family_from_ua(ua, expected):
    assert os_family_from_ua(ua) == expected


# --------------------------------------------------------------------------
# preserve_fields must not desync identity
# --------------------------------------------------------------------------

@pytest.mark.parametrize("stored_os", OS_FAMILIES)
@pytest.mark.parametrize("target_os", OS_FAMILIES)
def test_preserving_ua_across_os_families_stays_coherent(stored_os, target_os):
    """Preserve a UA from one OS while randomizing for another."""
    profiles = {"u1": _profile(stored_os)}
    out = randomize_batch(
        profiles,
        os_family=target_os,
        preserve_fields=["user_agent"],
        seed="regress",
    )["u1"]

    # The preserved UA wins, and everything else follows it.
    assert os_family_from_ua(out.user_agent) == stored_os
    _assert_clean(out, f"stored={stored_os} target={target_os}")


@pytest.mark.parametrize("stored_os", OS_FAMILIES)
def test_preserving_whole_identity_group_stays_coherent(stored_os):
    """The 'identity' group preserves all four fields together."""
    out = randomize_batch(
        {"u1": _profile(stored_os)},
        os_family="linux",
        preserve_fields=["identity"],
        seed="regress",
    )["u1"]
    assert os_family_from_ua(out.user_agent) == stored_os
    _assert_clean(out, f"identity group from {stored_os}")


# --------------------------------------------------------------------------
# overrides must not desync identity
# --------------------------------------------------------------------------

@pytest.mark.parametrize("field,value", [
    ("platform", "MacIntel"),
    ("platform", "Win32"),
    ("platform", "Linux x86_64"),
    ("oscpu", "Intel Mac OS X 10_15_7"),
    ("vendor", "Apple Computer, Inc."),
])
def test_overriding_one_identity_field_is_realigned(field, value):
    """A lone platform/oscpu/vendor override must not contradict the UA."""
    out = randomize_batch(
        {"u1": _profile("windows")},
        os_family="windows",
        overrides={field: value},
        seed="regress",
    )["u1"]
    _assert_clean(out, f"override {field}={value}")


@pytest.mark.parametrize("ua_os", OS_FAMILIES)
def test_overriding_user_agent_drags_identity_with_it(ua_os):
    """Overriding only the UA re-derives platform/vendor/oscpu to match."""
    ua = generate_fingerprint(seed="ua", os_family=ua_os).user_agent
    out = randomize_batch(
        {"u1": _profile("windows")},
        os_family="windows",
        overrides={"user_agent": ua},
        seed="regress",
    )["u1"]

    assert out.user_agent == ua
    reference = generate_fingerprint(os_family=ua_os)
    assert out.platform == reference.platform
    assert out.oscpu == reference.oscpu
    _assert_clean(out, f"UA override to {ua_os}")


def test_unrecognised_ua_is_left_alone():
    """A custom UA we can't classify must not be silently rewritten."""
    out = randomize_batch(
        {"u1": _profile("windows")},
        os_family="windows",
        overrides={"user_agent": "CustomAgent/1.0"},
        seed="regress",
    )["u1"]
    assert out.user_agent == "CustomAgent/1.0"
    assert out.platform == "Win32"  # untouched, matching os_family


# --------------------------------------------------------------------------
# GPU must not contradict the OS
# --------------------------------------------------------------------------

def test_apple_gpu_is_replaced_under_a_windows_ua():
    """Preserving a macOS GPU under a Windows UA fails webgl_os_coherence."""
    mac = _profile("macos")
    out = randomize_batch(
        {"u1": mac},
        os_family="windows",
        preserve_fields=["gpu"],
        seed="regress",
    )["u1"]

    assert os_family_from_ua(out.user_agent) == "windows"
    assert _checks(out)["webgl_os_coherence"]
    _assert_clean(out, "macOS GPU preserved under Windows UA")


# --------------------------------------------------------------------------
# Overrides still win for non-identity fields
# --------------------------------------------------------------------------

def test_non_identity_overrides_survive_alignment():
    """Realigning identity must not clobber unrelated overrides."""
    out = randomize_batch(
        {"u1": _profile("windows")},
        os_family="macos",
        shared_fields=["timezone"],
        preserve_fields=["user_agent"],
        overrides={"hardware_concurrency": 12, "timezone": "Europe/Berlin"},
        seed="regress",
    )["u1"]

    assert out.hardware_concurrency == 12
    assert out.timezone == "Europe/Berlin"
    _assert_clean(out, "non-identity overrides")


@pytest.mark.parametrize("seed", [f"batch-{i}" for i in range(8)])
def test_whole_batch_is_coherent(seed):
    """Every profile in a mixed batch comes out clean."""
    profiles = {f"u{i}": _profile(os_, seed=f"{seed}-{i}")
                for i, os_ in enumerate(OS_FAMILIES)}
    out = randomize_batch(
        profiles,
        os_family="macos",
        shared_fields=["timezone", "screen"],
        preserve_fields=["user_agent", "engine"],
        seed=seed,
    )
    assert len(out) == len(profiles)
    for uid, fp in out.items():
        _assert_clean(fp, f"batch {seed} profile {uid}")
