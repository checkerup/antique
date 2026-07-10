"""Tests for Windows console UTF-8 safety (the ✓ UnicodeEncodeError fix).

Regression coverage for: on CP1251/CP437 Windows terminals, printing the CLI
check-mark raised ``UnicodeEncodeError: 'charmap' codec can't encode character
'\u2713'``.
"""
import io

import pytest

from src.consoleutil import SAFE_SUBSTITUTIONS, ensure_utf8, supports_unicode, to_safe


class FakeStream:
    """Minimal stream exposing reconfigure(), records calls."""

    def __init__(self, encoding="cp1251", allow_reconfigure=True):
        self.encoding = encoding
        self.name = "<fake>"
        self.allow_reconfigure = allow_reconfigure
        self.reconfigured_to = None

    def reconfigure(self, encoding=None, errors=None):
        if not self.allow_reconfigure:
            raise ValueError("cannot reconfigure")
        self.encoding = encoding
        self.reconfigured_to = (encoding, errors)


# --- supports_unicode ---


def test_supports_unicode_utf8_true():
    assert supports_unicode("utf-8") is True


def test_supports_unicode_cp1251_false():
    # CP1251 (Windows Cyrillic) cannot encode ✓ / → etc.
    assert supports_unicode("cp1251") is False


def test_supports_unicode_none_false():
    assert supports_unicode(None) is False


def test_supports_unicode_unknown_encoding_false():
    assert supports_unicode("definitely-not-a-codec") is False


# --- to_safe ---


def test_to_safe_passthrough_on_utf8():
    text = "✓ done → next"
    assert to_safe(text, "utf-8") == text


def test_to_safe_substitutes_on_cp1251():
    out = to_safe("✓ done → next", "cp1251")
    assert "✓" not in out
    assert "→" not in out
    assert "[OK]" in out
    assert "->" in out


def test_to_safe_never_raises_and_is_encodable():
    out = to_safe("✓✗→•…±", "cp1251")
    # Result must be encodable in the target codec (no crash downstream).
    out.encode("cp1251")


def test_all_substitutions_are_ascii():
    for repl in SAFE_SUBSTITUTIONS.values():
        repl.encode("ascii")  # must not raise


# --- ensure_utf8 ---


def test_ensure_utf8_reconfigures_stream():
    s = FakeStream(encoding="cp1251")
    ok = ensure_utf8([s])
    assert ok is True
    assert s.encoding == "utf-8"
    assert s.reconfigured_to == ("utf-8", "replace")


def test_ensure_utf8_survives_unreconfigurable_stream():
    s = FakeStream(allow_reconfigure=False)
    # Must not raise; returns False because nothing was reconfigured.
    assert ensure_utf8([s]) is False


def test_ensure_utf8_skips_streams_without_reconfigure():
    plain = io.StringIO()  # no reconfigure attribute
    assert ensure_utf8([plain]) is False


# --- cli-level fix is wired ---


def test_cli_force_utf8_stdio_is_importable_and_idempotent():
    from src.cli import force_utf8_stdio
    s = FakeStream(encoding="cp866")
    first = force_utf8_stdio([s])
    second = force_utf8_stdio([s])  # idempotent, no crash
    assert s.encoding == "utf-8"
    assert isinstance(first, list) and isinstance(second, list)
