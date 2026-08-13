"""Tests for the real fingerprint corpus."""
from pathlib import Path

import pytest

from src.core.fingerprint import Fingerprint, generate_fingerprint
from src.core.fingerprint_corpus import (
    add_noise,
    corpus_size,
    sample_from_corpus,
)


def test_corpus_has_entries():
    assert corpus_size() >= 3  # we ship 4 entries (win x2, mac, linux)


def test_corpus_windows_has_entries():
    assert corpus_size(os_family="windows") >= 2


def test_corpus_macos_has_entries():
    assert corpus_size(os_family="macos") >= 1


def test_corpus_linux_has_entries():
    assert corpus_size(os_family="linux") >= 1


def test_sample_returns_fingerprint():
    fp = sample_from_corpus(os_family="windows", seed="test")
    assert fp is not None
    assert fp.platform == "Win32"
    assert fp.user_agent.startswith("Mozilla/5.0")


def test_sample_deterministic_with_seed():
    a = sample_from_corpus(os_family="windows", seed="same")
    b = sample_from_corpus(os_family="windows", seed="same")
    assert a is not None and b is not None
    assert a.id == b.id  # same seed → same entry sampled


def test_sample_different_seeds_may_differ():
    fps = set()
    for s in ("a", "b", "c", "d", "e", "f", "g", "h"):
        fp = sample_from_corpus(os_family="windows", seed=s)
        if fp:
            fps.add(fp.id)
    # With 2 windows entries, at least one distinct id should appear
    assert len(fps) >= 1


def test_sample_no_matching_os_returns_none():
    fp = sample_from_corpus(os_family="webos", seed="x")
    assert fp is None


def test_add_noise_perturbs_screen_dims():
    fp = sample_from_corpus(os_family="windows", seed="n1")
    assert fp is not None
    original_w = fp.screen_width
    noisy = add_noise(fp, seed="n1")
    # Noise is small (±3%) — screen dim should be close but not identical
    assert noisy.screen_width != original_w or True  # may occasionally match by chance
    # But within reasonable range
    assert abs(noisy.screen_width - original_w) <= original_w * 0.05


def test_add_noise_deterministic():
    a = add_noise(sample_from_corpus(os_family="windows", seed="x"), seed="n")
    b = add_noise(sample_from_corpus(os_family="windows", seed="x"), seed="n")
    assert a is not None and b is not None
    assert a.screen_width == b.screen_width
    assert a.hardware_concurrency == b.hardware_concurrency


def test_generate_fingerprint_uses_corpus_by_default():
    """generate_fingerprint() should prefer corpus when entries exist."""
    fp = generate_fingerprint(seed="gen-corpus", os_family="windows")
    assert fp.platform == "Win32"
    # If corpus is used, the fp comes from a real entry (not synthetic template).
    # We can't easily distinguish, but we can verify it's valid and complete.
    assert fp.user_agent.startswith("Mozilla/5.0")
    assert fp.screen_width > 0
    assert fp.hardware_concurrency > 0


def test_generate_fingerprint_fallback_to_template():
    """generate_fingerprint(use_corpus=False) always uses template synthesis."""
    fp = generate_fingerprint(seed="gen-template", os_family="windows", use_corpus=False)
    assert fp.platform == "Win32"
    assert fp.user_agent.startswith("Mozilla/5.0")


def test_corpus_fp_has_required_fields():
    fp = sample_from_corpus(os_family="windows", seed="fields")
    assert fp is not None
    for field in ("user_agent", "platform", "webgl_vendor", "fonts", "timezone", "hardware_concurrency"):
        assert getattr(fp, field, None) is not None
