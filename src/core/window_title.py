"""Per-profile browser window title labeling.

When a profile is launched, we prepend a visible prefix like ``[ProfileName]``
to every tab/window title so the Windows taskbar thumbnail and window label
show which profile the window belongs to — an AdsPower-style identification.

The prefix is:
  - Sanitized (control chars, angle brackets, excessive whitespace removed)
  - Length-controlled (max 60 chars so it stays readable in the taskbar)
  - Applied via an init script that uses a ``MutationObserver`` to re-apply
    the prefix after SPA-driven title changes, and also sets it immediately
    for the current document.

Used by ``BrowserLauncher`` in BOTH the subprocess+CDP path and the
Playwright ``launch_persistent_context`` path.
"""
from __future__ import annotations

import json
import re
from typing import Optional

__all__ = ["sanitize_profile_title", "build_title_init_script", "TITLE_PREFIX_MAX"]

# Keep the prefix itself short so the real page title is still visible in the
# tab bar and taskbar thumbnail.
TITLE_PREFIX_MAX = 60

# Control characters (C0 + C1 + common line separators) — removed entirely.
_CONTROL_RE = re.compile(r"[\x00-\x1f\x7f-\x9f]")

# Runs of whitespace (including tabs / NBSP / form-feed) → single space.
_WS_RE = re.compile(r"\s+")

# Angle brackets — would let a malicious/careless profile name inject HTML
# into the <title> element. Strip them.
_ANGLE_RE = re.compile(r"[<>]")

_FALLBACK = "antique"


def sanitize_profile_title(name: Optional[str]) -> str:
    """Sanitize a profile name for use as a window-title prefix.

    - Strips control characters and angle brackets (HTML-safety).
    - Collapses runs of whitespace to a single space.
    - Truncates to ``TITLE_PREFIX_MAX`` chars on a character boundary, with an
      ellipsis when truncated.
    - Falls back to ``"antique"`` when the input is empty / None / all-empty.

    Returns a clean, human-readable string safe to inline into JS via
    ``json.dumps``.
    """
    if name is None:
        name = ""
    # Normalize and strip dangerous/nuisance characters.
    cleaned = _ANGLE_RE.sub("", str(name))
    cleaned = _CONTROL_RE.sub("", cleaned)
    cleaned = _WS_RE.sub(" ", cleaned).strip()
    if not cleaned:
        return _FALLBACK
    if len(cleaned) > TITLE_PREFIX_MAX:
        cleaned = cleaned[: TITLE_PREFIX_MAX - 1].rstrip() + "…"
    return cleaned


# ---------------------------------------------------------------------------
# JS init script
# ---------------------------------------------------------------------------

# The script is self-contained and idempotent: it can be ``add_init_script``-ed
# (runs on every new document) AND ``page.evaluate``-d on already-open pages.
#
# Design:
#   - We compute the desired prefix once: ``[ProfileName] ``.
#   - ``applyTitle()`` reads the *current* document.title, strips any existing
#     ``[...]`` prefix we may have added, then prepends ours. This keeps the
#     site's real title visible and prevents double-prefixing on re-runs.
#   - A ``MutationObserver`` watches the ``<title>`` element for childList /
#     characterData changes (the exact mutation an SPA makes when it sets
#     ``document.title``) and re-applies the prefix via ``applyTitle``.
#   - Everything is best-effort: any error is swallowed so a title-patching
#     failure never breaks the page.
_TITLE_SCRIPT_TEMPLATE = r"""
(() => {
  const PREFIX = __AD_TITLE_PREFIX__;
  const MARKER = String.fromCharCode(8203); // zero-width space marker not used; kept simple
  function currentBase() {
    let t = (document.title || '').replace(/^\s+/, '').replace(/\s+$/, '');
    // Strip a leading "[...]" prefix we previously added so we never stack.
    const m = t.match(/^\[[^\]]*\]\s*/);
    if (m) t = t.slice(m[0].length);
    return t;
  }
  function applyTitle() {
    try {
      const base = currentBase();
      const next = '[' + PREFIX + '] ' + (base || '');
      if (document.title !== next) document.title = next;
    } catch (e) {}
  }
  applyTitle();
  try {
    const mo = new MutationObserver(() => applyTitle());
    const start = () => {
      try {
        const titleEl = document.querySelector('title') || null;
        if (titleEl) {
          mo.observe(titleEl, { childList: true, characterData: true, subtree: true });
        } else {
          // No <title> yet (e.g. about:blank) — wait for head to gain one.
          const headMO = new MutationObserver(() => {
            const te = document.querySelector('title');
            if (te) { headMO.disconnect(); mo.observe(te, { childList: true, characterData: true, subtree: true }); applyTitle(); }
          });
          headMO.observe(document.documentElement, { childList: true, subtree: true });
        }
      } catch (e) {}
    };
    if (document.readyState === 'loading') {
      document.addEventListener('DOMContentLoaded', start, { once: true });
    } else {
      start();
    }
  } catch (e) {}
})();
"""


def build_title_init_script(profile_name: str) -> str:
    """Build the JS init script that prepends ``[profile_name]`` to the title.

    The script:
      - sets the prefix on the current document immediately;
      - installs a ``MutationObserver`` on ``<title>`` to re-apply the prefix
        when an SPA changes ``document.title``;
      - is idempotent (strips a previously-added ``[...]`` prefix first).

    ``profile_name`` is sanitized and JSON-escaped before inlining, so it is
    safe even if the name contains quotes, backslashes, or Unicode.
    """
    safe = sanitize_profile_title(profile_name)
    prefix_json = json.dumps(safe, separators=(",", ":"))
    return _TITLE_SCRIPT_TEMPLATE.replace("__AD_TITLE_PREFIX__", prefix_json)
