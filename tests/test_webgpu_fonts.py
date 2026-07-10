"""Tests for WebGPU adapter spoofing + font enumeration fingerprint fields."""
import json

import pytest

from src.core.fingerprint import (
    Fingerprint,
    build_init_script,
    generate_fingerprint,
    _FONTS_BY_OS,
)


# ---------------------------------------------------------------------------
# WebGPU
# ---------------------------------------------------------------------------


def test_generate_populates_webgpu_fields():
    fp = generate_fingerprint(seed="wgpu")
    assert isinstance(fp.webgpu_enabled, bool)
    # When enabled, vendor/architecture/description must be non-empty.
    if fp.webgpu_enabled:
        assert fp.webgpu_vendor
        assert fp.webgpu_architecture
        assert fp.webgpu_description
    else:
        assert fp.webgpu_vendor == ""


def test_webgpu_is_coherent_with_webgl_vendor():
    """The WebGPU vendor should line up with the WebGL GPU vendor family."""
    # Try many seeds; every generated pair must be coherent.
    for i in range(50):
        fp = generate_fingerprint(seed=f"coh-{i}")
        wgl = fp.webgl_vendor.lower()
        if not fp.webgpu_enabled:
            # Only the software renderer (Mozilla/llvmpipe) disables WebGPU.
            assert "mozilla" in wgl
            continue
        v = fp.webgpu_vendor
        if "nvidia" in wgl:
            assert v == "nvidia"
        elif "amd" in wgl:
            assert v == "amd"
        elif "intel" in wgl:
            assert v == "intel"
        elif "apple" in wgl:
            assert v == "apple"


def test_webgpu_deterministic_with_seed():
    a = generate_fingerprint(seed="same")
    b = generate_fingerprint(seed="same")
    assert (a.webgpu_vendor, a.webgpu_architecture, a.webgpu_description) == (
        b.webgpu_vendor, b.webgpu_architecture, b.webgpu_description
    )


def test_init_script_contains_webgpu_patch():
    fp = generate_fingerprint(seed="wgpu2")
    js = build_init_script(fp)
    assert "navigator.gpu" in js
    assert "requestAdapter" in js
    assert "cfg.webgpu_vendor" in js
    # The concrete values must be inlined in the cfg JSON.
    if fp.webgpu_enabled:
        assert fp.webgpu_vendor in js
        assert fp.webgpu_description in js


def test_disabled_webgpu_removes_gpu():
    """A software-renderer fingerprint must patch navigator.gpu to undefined."""
    fp = Fingerprint(webgpu_enabled=False, webgpu_vendor="", fonts=["Arial"])
    js = build_init_script(fp)
    assert '"webgpu_enabled":false' in js
    assert "get: () => undefined" in js


# ---------------------------------------------------------------------------
# Fonts
# ---------------------------------------------------------------------------


def test_generate_populates_fonts():
    fp = generate_fingerprint(seed="fonts")
    assert isinstance(fp.fonts, list)
    assert len(fp.fonts) > 5
    # Core cross-platform fonts always present.
    assert "Arial" in fp.fonts
    assert "Times New Roman" in fp.fonts
    # No duplicates, sorted.
    assert fp.fonts == sorted(set(fp.fonts))


def test_fonts_are_os_specific():
    win = generate_fingerprint(seed="os", os_family="windows")
    mac = generate_fingerprint(seed="os", os_family="macos")
    lin = generate_fingerprint(seed="os", os_family="linux")
    win_pool = set(_FONTS_BY_OS["windows"])
    mac_pool = set(_FONTS_BY_OS["macos"])
    lin_pool = set(_FONTS_BY_OS["linux"])
    # Each generated set is drawn only from its OS pool.
    assert set(win.fonts).issubset(win_pool)
    assert set(mac.fonts).issubset(mac_pool)
    assert set(lin.fonts).issubset(lin_pool)
    # And is distinctly that OS: only <=6 fonts are dropped, so an OS set can
    # never collapse into a different OS's pool.
    assert not set(win.fonts).issubset(mac_pool)
    assert not set(mac.fonts).issubset(win_pool)
    assert not set(lin.fonts).issubset(win_pool)


def test_fonts_deterministic_with_seed():
    a = generate_fingerprint(seed="detf")
    b = generate_fingerprint(seed="detf")
    assert a.fonts == b.fonts


def test_init_script_contains_font_patch():
    fp = generate_fingerprint(seed="fonts3")
    js = build_init_script(fp)
    assert "document.fonts.check" in js
    assert "cfg.fonts" in js
    # At least one real font name inlined
    assert "Arial" in js


def test_fingerprint_with_new_fields_json_round_trips():
    fp = generate_fingerprint(seed="rt")
    d = fp.canonical()
    d2 = json.loads(json.dumps(d))
    assert d == d2
    # New fields present in canonical dict
    assert "webgpu_vendor" in d
    assert "fonts" in d
