"""Console encoding helpers.

On Windows the default console codepage is often CP1251 (Cyrillic locale) or
CP437, which cannot encode Unicode glyphs like the check-mark (U+2713) we use
in CLI output. Printing them raises ``UnicodeEncodeError: 'charmap' codec
can't encode character '\u2713'``.

This module:

1. ``ensure_utf8(streams)`` — reconfigure stdout/stderr to UTF-8 at startup so
   the glyphs print correctly without the user having to set
   ``PYTHONIOENCODING=utf-8`` by hand.
2. ``supports_unicode(encoding)`` / ``to_safe(text, encoding)`` — a pure
   fallback: if a stream still can't do UTF-8 (reconfigure failed, exotic
   terminal), substitute the fancy glyphs with ASCII equivalents so the
   command never crashes.

The pure helpers are fully unit-testable without a real terminal.
"""
from __future__ import annotations

import sys
from typing import Iterable, Optional


# Fancy glyph -> ASCII fallback. Keep this list in sync with symbols used in
# CLI output (see src/cli.py).
SAFE_SUBSTITUTIONS = {
    "\u2713": "[OK]",     # ✓ check mark
    "\u2714": "[OK]",     # ✔ heavy check mark
    "\u2717": "[X]",      # ✗ ballot x
    "\u2718": "[X]",      # ✘ heavy ballot x
    "\u2192": "->",       # → rightwards arrow
    "\u2190": "<-",       # ← leftwards arrow
    "\u2014": "-",        # — em dash
    "\u2013": "-",        # – en dash
    "\u2022": "*",        # • bullet
    "\u2026": "...",      # … ellipsis
    "\u00b1": "+/-",      # ± plus-minus
}


def supports_unicode(encoding: Optional[str]) -> bool:
    """Return True if ``encoding`` can encode our fancy glyphs.

    A ``None`` encoding (unknown) is treated as not-safe.
    """
    if not encoding:
        return False
    try:
        for glyph in SAFE_SUBSTITUTIONS:
            glyph.encode(encoding)
        return True
    except (LookupError, UnicodeEncodeError):
        return False


def to_safe(text: str, encoding: Optional[str]) -> str:
    """Return ``text`` unchanged if ``encoding`` supports it, else substitute
    the fancy glyphs with ASCII equivalents.

    This never raises: any leftover unencodable character is replaced with a
    ``?`` as a last resort.
    """
    if supports_unicode(encoding):
        return text
    out = text
    for glyph, repl in SAFE_SUBSTITUTIONS.items():
        out = out.replace(glyph, repl)
    if encoding:
        # Last-resort: drop anything still unencodable.
        try:
            out = out.encode(encoding, errors="replace").decode(encoding, errors="replace")
        except LookupError:
            pass
    return out


def ensure_utf8(streams: Optional[Iterable] = None) -> bool:
    """Reconfigure the given text streams (default: stdout+stderr) to UTF-8.

    Returns True if at least one stream was successfully reconfigured. Safe to
    call multiple times and on platforms/streams that don't support
    ``reconfigure`` (returns False, changes nothing).
    """
    if streams is None:
        streams = [sys.stdout, sys.stderr]
    ok = False
    for stream in streams:
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is None:
            continue
        try:
            reconfigure(encoding="utf-8", errors="replace")
            ok = True
        except (ValueError, OSError):
            # Stream already detached / not reconfigurable — ignore.
            continue
    return ok
