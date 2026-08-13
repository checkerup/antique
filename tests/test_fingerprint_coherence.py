"""Behavioural regression tests for fingerprint coherence.

These cover defects that config-level assertions could not catch: the audit
score of a freshly created profile, the screen-dimension invariants after
noise, and WebRTC mode resolution for dict-shaped fingerprints.
"""
import pytest

from src.core.detect import score_fingerprint
from src.core.fingerprint import Fingerprint, effective_webrtc_mode, generate_fingerprint
from src.core.fingerprint_corpus import add_noise, sample_from_corpus


def _checks(fp):
    return {c["name"]: c["ok"] for c in score_fingerprint(fp).to_dict()["checks"]}


# --------------------------------------------------------------------------
# A default profile must be clean out of the box
# --------------------------------------------------------------------------

@pytest.mark.parametrize("seed", [f"seed-{i}" for i in range(10)])
def test_generated_fingerprint_passes_every_audit_check(seed):
    """A freshly generated fingerprint scores 100 — no self-inflicted tells."""
    report = score_fingerprint(generate_fingerprint(seed=seed)).to_dict()
    failed = [c["name"] for c in report["checks"] if not c["ok"]]
    assert failed == [], f"audit failures on a default profile: {failed}"
    assert report["score"] == 100


# --------------------------------------------------------------------------
# Screen dimension invariants: inner <= avail <= screen
# --------------------------------------------------------------------------

@pytest.mark.parametrize("seed", [f"noise-{i}" for i in range(25)])
def test_add_noise_preserves_screen_ordering(seed):
    """Jitter must not push avail/inner past the physical screen."""
    fp = generate_fingerprint(seed=seed)
    add_noise(fp, seed=seed)

    assert fp.avail_screen_width <= fp.screen_width
    assert fp.avail_screen_height <= fp.screen_height
    assert fp.inner_width <= fp.avail_screen_width
    assert fp.inner_height <= fp.avail_screen_height
    assert all(v > 0 for v in (
        fp.screen_width, fp.screen_height,
        fp.avail_screen_width, fp.avail_screen_height,
        fp.inner_width, fp.inner_height,
    ))


@pytest.mark.parametrize("seed", [f"tiny-{i}" for i in range(10)])
def test_add_noise_survives_small_screens(seed):
    """A screen smaller than its own insets must still come out coherent."""
    fp = generate_fingerprint(seed=seed)
    fp.screen_width, fp.screen_height = 40, 30
    fp.avail_screen_width, fp.avail_screen_height = 40, 20
    fp.inner_width, fp.inner_height = 40, 10

    add_noise(fp, seed=seed)

    assert fp.inner_width <= fp.avail_screen_width <= fp.screen_width
    assert fp.inner_height <= fp.avail_screen_height <= fp.screen_height


@pytest.mark.parametrize("seed", [f"hw-{i}" for i in range(20)])
def test_add_noise_keeps_hardware_plausible(seed):
    """Cores stay even and memory stays a power of two after jitter."""
    fp = generate_fingerprint(seed=seed)
    add_noise(fp, seed=seed)

    assert fp.hardware_concurrency in (2, 4, 6, 8, 12, 16, 24, 32)
    assert fp.device_memory in (2.0, 4.0, 8.0, 16.0, 32.0, 64.0)
    assert _checks(fp)["hardware_plausible"]


def test_add_noise_is_deterministic_for_a_seed():
    a, b = generate_fingerprint(seed="fixed"), generate_fingerprint(seed="fixed")
    add_noise(a, seed="same")
    add_noise(b, seed="same")
    assert (a.screen_width, a.inner_height, a.hardware_concurrency) == \
           (b.screen_width, b.inner_height, b.hardware_concurrency)


# --------------------------------------------------------------------------
# Chrome must expose plugins
# --------------------------------------------------------------------------

def test_corpus_sample_backfills_chrome_plugins():
    """A Chrome UA reporting zero plugins is a tell; corpus samples must not."""
    fp = sample_from_corpus(seed="plug")
    if fp is None:
        pytest.skip("fingerprint corpus is empty in this checkout")
    if "Chrom" in fp.user_agent:
        assert fp.plugins, "Chrome fingerprint sampled with no navigator.plugins"
        assert _checks(fp)["plugins_present"]


# --------------------------------------------------------------------------
# WebRTC mode resolution — dicts and dataclasses alike
# --------------------------------------------------------------------------

@pytest.mark.parametrize("fp,expected", [
    ({"webrtc_mode": "real"}, "real"),
    ({"webrtc_mode": "proxy"}, "proxy"),
    ({"webrtc_mode": "block"}, "block"),
    ({"webrtc_mode": "  REAL  "}, "real"),
    ({"webrtc_mode": "", "block_webrtc_ip": True}, "block"),
    ({"webrtc_mode": "", "block_webrtc_ip": False}, "real"),
    ({"webrtc_mode": None, "block_webrtc_ip": False}, "real"),
    ({}, "block"),
])
def test_effective_webrtc_mode_reads_dicts(fp, expected):
    """Stored profiles are dicts — getattr() alone reported 'block' for all."""
    assert effective_webrtc_mode(fp) == expected


def test_effective_webrtc_mode_reads_dataclass():
    fp = Fingerprint()
    fp.webrtc_mode = "proxy"
    assert effective_webrtc_mode(fp) == "proxy"
    assert effective_webrtc_mode(Fingerprint()) == "block"


@pytest.mark.parametrize("fp,expected", [
    ({"webrtc_mode": "", "block_webrtc_ip": True}, True),
    ({"webrtc_mode": "real"}, True),
    ({"webrtc_mode": "proxy", "webrtc_public_ip": "203.0.113.9"}, True),
    ({"webrtc_mode": "proxy", "webrtc_public_ip": ""}, False),
    ({"webrtc_mode": "banana"}, False),
])
def test_audit_webrtc_mode_check(fp, expected):
    """proxy without a public IP, and unknown modes, must fail the audit."""
    fp.setdefault("user_agent", "Mozilla/5.0 Chrome/120.0.0.0")
    assert _checks(fp)["webrtc_mode_valid"] is expected
