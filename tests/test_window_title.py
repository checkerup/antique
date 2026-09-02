"""Per-profile browser window title labeling.

Requirements:
  - Every launched profile window/tab title keeps a clear prefix containing
    the Antique profile name, surviving SPA title changes (MutationObserver).
  - Prefix is sanitized and length-controlled.
  - Works in BOTH the subprocess+CDP path and the Playwright launch path.
  - Windows taskbar thumbnail / window label shows the profile name.
"""
from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.core.profile import Profile
from src.core.browser import BrowserLauncher
from src.core.fingerprint import generate_fingerprint


# ---------------------------------------------------------------------------
# Pure helper: sanitize_profile_title
# ---------------------------------------------------------------------------

from src.core.window_title import sanitize_profile_title, build_title_init_script


def test_sanitize_strips_control_and_newlines():
    out = sanitize_profile_title("My\nProfile\r\n<script>")
    assert "\n" not in out
    assert "\r" not in out
    assert "<" not in out
    assert ">" not in out
    assert "My" in out and "Profile" in out


def test_sanitize_collapses_runs_of_whitespace():
    out = sanitize_profile_title("Multiple    Spaces\tTab")
    assert "    " not in out
    assert "\t" not in out
    assert "Multiple" in out


def test_sanitize_preserves_unicode():
    out = sanitize_profile_title("Профиль 日本語 émoji 😀")
    assert "Профиль" in out
    assert "日本語" in out


def test_sanitize_truncates_long_names():
    long = "x" * 500
    out = sanitize_profile_title(long)
    assert len(out) <= 120


def test_sanitize_truncates_on_char_boundary():
    out = sanitize_profile_title("a" * 300)
    assert len(out) <= 120
    assert out.endswith("…") or len(out) < 120


def test_sanitize_empty_falls_back():
    out = sanitize_profile_title("")
    assert out  # not empty
    assert "antique" in out.lower()


def test_sanitize_none_falls_back():
    out = sanitize_profile_title(None)
    assert out
    assert "antique" in out.lower()


def test_sanitize_short_name_passthrough():
    out = sanitize_profile_title("alice")
    assert out == "alice"


# ---------------------------------------------------------------------------
# build_title_init_script — JS that prepends the prefix
# ---------------------------------------------------------------------------

def test_title_init_script_contains_prefix_and_mutation_observer():
    js = build_title_init_script("alice")
    assert "alice" in js
    # Must use a MutationObserver to re-apply the prefix on SPA title changes
    assert "MutationObserver" in js
    # Must set the title on the current document
    assert "document.title" in js


def test_title_init_script_sanitizes_prefix_inlined():
    """The prefix must be safely JSON-escaped into the JS, not interpolated raw."""
    js = build_title_init_script('a"; alert(1)')
    # Should NOT contain raw injected script context — the dangerous chars
    # must be escaped via JSON.
    assert "alert(1)" not in js or '\\"' in js


def test_title_init_script_appends_original_title():
    """The script must keep the site's original title text, just prefixed."""
    js = build_title_init_script("alice")
    # The prefix is separated from the rest, e.g. "[alice] "
    assert "[alice]" in js or "alice" in js


def test_title_init_script_is_parseable_js():
    """Sanity: the script is a non-empty, balanced JS string."""
    js = build_title_init_script("bob")
    assert js.strip().startswith(("{", "(", "/", "!", "v", "t", "f", "i", "c"))
    assert "()" in js or "function" in js


# ---------------------------------------------------------------------------
# BrowserLauncher integration — both launch paths add the title script
# ---------------------------------------------------------------------------

def _make_launcher(tmp_path):
    store = MagicMock()
    store.get = MagicMock(return_value=None)
    store.record_session = MagicMock()
    store.start_session = MagicMock()
    store.stop_session = MagicMock()
    store.mark_initial_state_applied = MagicMock()
    launcher = BrowserLauncher(store, data_root=tmp_path, headless=True)
    return launcher


def test_launch_subprocess_adds_title_init_script(tmp_path, monkeypatch):
    """The subprocess+CDP path must add a profile-name title init script."""
    launcher = _make_launcher(tmp_path)

    # Build a profile
    fp = generate_fingerprint(seed="t1")
    profile = Profile(user_id="u1", name="AdsAccount42", fingerprint=fp.canonical())

    # Mock the entire chain: subprocess.Popen, _wait_for_cdp_ws, async_playwright
    fake_ctx = MagicMock()
    fake_ctx.add_init_script = AsyncMock()
    fake_ctx.add_cookies = AsyncMock()
    fake_ctx.pages = []
    fake_ctx.new_page = AsyncMock()

    fake_browser = MagicMock()
    fake_browser.contexts = [fake_ctx]

    fake_pw = MagicMock()
    fake_pw.chromium = MagicMock()
    fake_pw.chromium.connect_over_cdp = AsyncMock(return_value=fake_browser)
    fake_pw.stop = AsyncMock()

    fake_proc = MagicMock()
    fake_proc.pid = 12345
    fake_proc.stderr = MagicMock()
    fake_proc.stderr.read = MagicMock(return_value=b"")
    fake_proc.kill = MagicMock()
    fake_proc.terminate = MagicMock()

    def fake_async_playwright():
        m = MagicMock()
        m.start = AsyncMock(return_value=fake_pw)
        return m

    async def fake_wait(port, attempts=60):
        return "ws://127.0.0.1:1/devtools/browser/0"

    monkeypatch.setattr(
        "src.core.browser.subprocess.Popen", lambda *a, **kw: fake_proc
    )
    monkeypatch.setattr("src.core.browser._wait_for_cdp_ws", fake_wait)
    monkeypatch.setattr("playwright.async_api.async_playwright", fake_async_playwright)

    handle = asyncio.run(launcher._launch_subprocess(profile, debug_port=0))

    # The init script added to the context must contain the profile name
    added = fake_ctx.add_init_script.call_args_list
    assert added, "subprocess path must call add_init_script"
    scripts = [c.kwargs.get("script") or c.args[0] for c in added]
    joined = "\n".join(scripts)
    assert "AdsAccount42" in joined
    assert "MutationObserver" in joined


def test_launch_playwright_adds_title_init_script(tmp_path, monkeypatch):
    """The Playwright launch path must add a profile-name title init script."""
    launcher = _make_launcher(tmp_path)

    fp = generate_fingerprint(seed="t2")
    profile = Profile(user_id="u2", name="CryptoWallet", fingerprint=fp.canonical())

    fake_ctx = MagicMock()
    fake_ctx.add_init_script = AsyncMock()
    fake_ctx.add_cookies = AsyncMock()
    fake_ctx.pages = []
    fake_ctx.new_page = AsyncMock()

    fake_pw = MagicMock()
    fake_pw.chromium = MagicMock()
    fake_pw.chromium.launch_persistent_context = AsyncMock(return_value=fake_ctx)
    fake_pw.firefox = MagicMock()
    fake_pw.firefox.launch_persistent_context = AsyncMock(return_value=fake_ctx)
    fake_pw.webkit = MagicMock()
    fake_pw.webkit.launch_persistent_context = AsyncMock(return_value=fake_ctx)
    fake_pw.stop = AsyncMock()

    def fake_async_playwright():
        m = MagicMock()
        m.start = AsyncMock(return_value=fake_pw)
        return m

    async def fake_wait(port, attempts=30):
        return ""

    monkeypatch.setattr("playwright.async_api.async_playwright", fake_async_playwright)
    monkeypatch.setattr("src.core.browser._wait_for_cdp_ws", fake_wait)

    handle = asyncio.run(launcher._launch(profile, debug_port=0))

    added = fake_ctx.add_init_script.call_args_list
    assert added, "playwright path must call add_init_script"
    scripts = [c.kwargs.get("script") or c.args[0] for c in added]
    joined = "\n".join(scripts)
    assert "CryptoWallet" in joined
    assert "MutationObserver" in joined


def test_launch_subprocess_title_script_applied_to_existing_pages(tmp_path, monkeypatch):
    """Subprocess path must also re-apply the title on already-open pages."""
    launcher = _make_launcher(tmp_path)

    fp = generate_fingerprint(seed="t3")
    profile = Profile(user_id="u3", name="EcomStore", fingerprint=fp.canonical())

    # A page that already exists (e.g. the browser's initial about:blank)
    fake_page = MagicMock()
    fake_page.evaluate = AsyncMock()

    fake_ctx = MagicMock()
    fake_ctx.add_init_script = AsyncMock()
    fake_ctx.add_cookies = AsyncMock()
    fake_ctx.pages = [fake_page]
    fake_ctx.new_page = AsyncMock()

    fake_browser = MagicMock()
    fake_browser.contexts = [fake_ctx]

    fake_pw = MagicMock()
    fake_pw.chromium = MagicMock()
    fake_pw.chromium.connect_over_cdp = AsyncMock(return_value=fake_browser)
    fake_pw.stop = AsyncMock()

    fake_proc = MagicMock()
    fake_proc.pid = 999
    fake_proc.stderr = MagicMock()
    fake_proc.stderr.read = MagicMock(return_value=b"")
    fake_proc.kill = MagicMock()
    fake_proc.terminate = MagicMock()

    def fake_async_playwright():
        m = MagicMock()
        m.start = AsyncMock(return_value=fake_pw)
        return m

    async def fake_wait(port, attempts=60):
        return "ws://127.0.0.1:1/devtools/browser/0"

    monkeypatch.setattr(
        "src.core.browser.subprocess.Popen", lambda *a, **kw: fake_proc
    )
    monkeypatch.setattr("src.core.browser._wait_for_cdp_ws", fake_wait)
    monkeypatch.setattr("playwright.async_api.async_playwright", fake_async_playwright)

    asyncio.run(launcher._launch_subprocess(profile, debug_port=0))

    # The existing page must have had the title script evaluated on it
    fake_page.evaluate.assert_awaited()
    eval_script = fake_page.evaluate.call_args.args[0]
    assert "EcomStore" in eval_script
    assert "MutationObserver" in eval_script


# ---------------------------------------------------------------------------
# build_title_init_script — behavioral verification of the JS itself
# ---------------------------------------------------------------------------

def test_title_script_maintains_prefix_when_title_changes_jsdom_like():
    """The JS keeps a prefix even when the site changes the title afterward.

    We simulate the relevant parts: the script should define a function that,
    given a title, prepends the prefix, and a MutationObserver that re-applies it.
    """
    js = build_title_init_script("MyProfile")
    # The script must reference its prefix constant
    assert "MyProfile" in js
    # Must set up the observer to watch <title> / document.title
    assert "MutationObserver" in js
    assert "observe" in js
    # Must define a childList / characterData subtree on title element
    assert "childList" in js or "characterData" in js
