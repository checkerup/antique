"""Browser launcher: spawn a Chromium with the profile's fingerprint.

Uses Playwright's ``launch_persistent_context`` so each profile lives in
its own user data dir (the same isolation Chrome gives to multi-account
launch). Cookies / localStorage / IndexedDB persist between launches.

The launcher also:

  - Sets up the JS init script that patches navigator/canvas/WebGL/audio
    on every new document.
  - Imports cookies via ``context.add_cookies``.
  - Records the session in the ProfileStore.
  - Returns a CDP-capable handle so external automation can attach via
    the websocket endpoint.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import socket
import subprocess
import sys
import time
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from .cookie import Cookie
from .extension import ExtensionStore
from .engines import EngineSpec, resolve_engine, resolve_engine_for_profile, engine_keys
from .fingerprint import Fingerprint, build_init_script, to_playwright_launch_options
from .profile import Profile, ProfileStore
from .proxy import ProxyConfig, parse_proxy


log = logging.getLogger("antique.browser")


def _find_free_port(preferred: Optional[int] = None) -> int:
    if preferred is not None:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(("127.0.0.1", preferred))
                return preferred
            except OSError:
                pass
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@dataclass
class BrowserHandle:
    user_id: str
    session_id: str
    debug_port: int
    ws_endpoint: str
    pid: Optional[int]
    context: Any


# Browser engine types (kept as module constants for convenience; the source
# of truth is src/core/engines.py).
ENGINE_CHROMIUM = "chromium"
ENGINE_FIREFOX = "firefox"
ENGINE_CAMOUFOX = "camoufox"
VALID_ENGINES = set(engine_keys())


def build_debug_port_args(port: int) -> List[str]:
    """Chromium flags that expose a REAL CDP endpoint on ``port``.

    Previously the launcher advertised ``ws://127.0.0.1:{port}/devtools/browser``
    but never passed ``--remote-debugging-port`` to Chromium, so external
    automation (Selenium/Puppeteer/user scripts — the whole point of an
    AdsPower-compatible farm) could not attach. These flags fix that: Chromium
    itself listens on the port and serves ``/json/version`` + the browser WS.
    """
    if port is None or int(port) <= 0:
        return []
    return [
        f"--remote-debugging-port={int(port)}",
        "--remote-debugging-address=127.0.0.1",
    ]


def _build_client_hints_args(fp: Fingerprint) -> List[str]:
    """Build Chromium command-line args for Client Hints (Sec-CH-UA*).

    Client Hints are sent by Chromium to servers and must match the
    fingerprint's UA, platform, and mobile status to avoid detection.
    """
    args = []
    # Extract major version from UA string
    import re
    major_match = re.search(r"Chrome/(\d+)", fp.user_agent)
    major = major_match.group(1) if major_match else "125"

    # Sec-CH-UA brand list (Chromium uses a greased brand + real brand)
    brand_list = f'"Chromium";v="{major}", "Google Chrome";v="{major}", "Not-A.Brand";v="8"'

    # Platform mapping
    platform_map = {
        "Win32": "Windows",
        "MacIntel": "macOS",
        "Linux x86_64": "Linux",
    }
    ch_platform = platform_map.get(fp.platform, "Windows")

    # Bitness
    bitness = "64"  # almost all modern systems

    # Build the args
    args.extend([
        f"--user-agent-client-hint-brand={brand_list}",
        f"--user-agent-client-hint-full-version={major}.0.0.0",
        f"--user-agent-client-hint-platform={ch_platform}",
        f"--user-agent-client-hint-platform-version=15.0.0",
        f"--user-agent-client-hint-architecture=x86",
        f"--user-agent-client-hint-bitness={bitness}",
        "--user-agent-client-hint-mobile=?0",
        "--user-agent-client-hint-model=",
        "--user-agent-client-hint-wow64=?0",
    ])
    return args


class BrowserLauncher:
    def __init__(
        self,
        store: ProfileStore,
        *,
        data_root: Optional[Path] = None,
        headless: bool = False,
        ext_store: Optional[ExtensionStore] = None,
    ):
        self.store = store
        self.data_root = data_root or Path(os.environ.get("ANTIQUE_DATA_DIR", "data"))
        self.data_root.mkdir(parents=True, exist_ok=True)
        self.headless = headless
        self.ext_store = ext_store or ExtensionStore(data_root=self.data_root)
        self._live: Dict[str, BrowserHandle] = {}
        self._launch_locks: Dict[str, asyncio.Lock] = {}
        self._lock = asyncio.Lock()

    def is_running(self, user_id: str) -> bool:
        return user_id in self._live

    def get_handle(self, user_id: str) -> Optional[BrowserHandle]:
        return self._live.get(user_id)

    def list_running(self) -> List[BrowserHandle]:
        return list(self._live.values())

    async def start(self, profile: Profile, *, debug_port: Optional[int] = None) -> BrowserHandle:
        existing = self._live.get(profile.user_id)
        if existing is not None:
            return existing
        async with self._lock:
            lock = self._launch_locks.setdefault(profile.user_id, asyncio.Lock())
        async with lock:
            existing = self._live.get(profile.user_id)
            if existing is not None:
                return existing
            handle = await self._launch(profile, debug_port=debug_port)
            self._live[profile.user_id] = handle
            return handle

    async def stop(self, user_id: str) -> bool:
        handle = self._live.pop(user_id, None)
        if handle is None:
            self.store.stop_session(user_id)
            return False
        try:
            await handle.context.close()
        except Exception:
            pass
        self.store.stop_session(user_id)
        return True

    async def stop_all(self) -> int:
        uids = list(self._live.keys())
        n = 0
        for uid in uids:
            if await self.stop(uid):
                n += 1
        return n

    def _resolve_fingerprint(self, profile: Profile) -> Fingerprint:
        from dataclasses import fields
        if profile.fingerprint:
            valid_keys = {f.name for f in fields(Fingerprint)}
            cleaned = {k: v for k, v in profile.fingerprint.items() if k in valid_keys}
            return Fingerprint(**cleaned)
        return Fingerprint()

    def _profile_user_dir(self, user_id: str) -> Path:
        d = self.data_root / "profiles" / user_id
        d.mkdir(parents=True, exist_ok=True)
        return d

    async def _maybe_apply_imported_state(
        self, profile: Profile, user_dir: Path
    ) -> None:
        """If the profile was created from a .adb bundle, copy the source
        profile's LocalStorage/leveldb and IndexedDB folders into ``user_dir``
        before the first launch.

        Runs once per profile; the ``initial_state_applied`` flag on the
        ProfileRecord prevents re-copying on subsequent launches so the
        user's accumulated localStorage state is preserved.

        Errors are logged but don't block the launch — if the source bundle
        is gone or corrupt, the profile still boots empty.
        """
        # Lazy import — these helpers pull in shutil which is otherwise unused
        # on the hot path of every launch.
        from .cookie import (
            apply_initial_state_to_user_data,
            find_profile_default_dir,
        )

        if not profile.import_source_path:
            return  # not an imported profile
        if profile.initial_state_applied:
            return  # already done on a previous launch
        src = Path(profile.import_source_path)
        if not src.exists():
            return  # source bundle is gone — skip silently

        default_dir = find_profile_default_dir(src)
        if default_dir is None:
            return  # nothing to copy

        try:
            apply_initial_state_to_user_data(default_dir, user_dir)
        except Exception as exc:  # pragma: no cover — defensive
            log.warning(
                "antique: failed to apply imported state for %s: %s",
                profile.user_id,
                exc,
            )
            return

        # Only flip the flag if we actually copied something — otherwise the
        # next launch will retry, which is the right behaviour when the
        # source bundle didn't have localStorage/IndexedDB in the first place.
        target_default = user_dir / "Default"
        ls_copied = (target_default / "Local Storage" / "leveldb").exists()
        idb_copied = (target_default / "IndexedDB").exists()
        webstorage_copied = (target_default / "WebStorage").exists()
        if ls_copied or idb_copied or webstorage_copied:
            self.store.mark_initial_state_applied(profile.user_id)

    def _resolve_engine_spec(self, profile: Profile) -> EngineSpec:
        """Resolve the EngineSpec for a profile (profile setting → env → default)."""
        profile_engine = ""
        if profile.fingerprint:
            profile_engine = profile.fingerprint.get("browser_engine", "")
        return resolve_engine_for_profile(profile_engine)

    def _get_engine(self, profile: Profile) -> str:
        """Determine which browser engine key to use for a profile."""
        return self._resolve_engine_spec(profile).key

    def _get_extension_paths(self, profile: Profile) -> List[str]:
        """Get extension paths for this profile."""
        ext_ids = []
        if profile.fingerprint:
            ext_ids = profile.fingerprint.get("extensions", [])
        if not ext_ids:
            return []
        return self.ext_store.get_extensions_for_profile(ext_ids)

    async def _launch(self, profile: Profile, *, debug_port: Optional[int]) -> BrowserHandle:
        from playwright.async_api import async_playwright
        fp = self._resolve_fingerprint(profile)
        proxy_cfg = parse_proxy(profile.proxy or None)
        proxy_pw = proxy_cfg.to_playwright()
        user_dir = self._profile_user_dir(profile.user_id)
        spec = self._resolve_engine_spec(profile)

        # If the profile was created from a full .adb import, copy
        # LocalStorage + IndexedDB into the user_data_dir before the first
        # launch so Chromium reads them natively.
        await self._maybe_apply_imported_state(profile, user_dir)
        port = _find_free_port(debug_port)
        launch_opts = to_playwright_launch_options(fp, proxy=proxy_pw)
        launch_opts["headless"] = self.headless
        init_js = build_init_script(fp)

        # Client Hints + real per-profile CDP + extensions are Chromium-only.
        if spec.is_chromium:
            ch_args = _build_client_hints_args(fp)
            launch_opts.setdefault("args", []).extend(ch_args)
            launch_opts.setdefault("args", []).extend(build_debug_port_args(port))

        ext_paths = self._get_extension_paths(profile)
        if ext_paths and spec.supports_extensions:
            ext_arg = f"--load-extension={','.join(ext_paths)}"
            launch_opts.setdefault("args", []).append(ext_arg)
            # Disable extension security to allow loading unpacked
            launch_opts["args"].append("--enable-extensions")
            launch_opts["args"].append("--disable-extensions-except=" + ",".join(ext_paths))

        playwright = await async_playwright().start()
        # An explicit channel on the engine (chrome/msedge) wins; otherwise fall
        # back to the ANTIQUE_BROWSER_CHANNEL override (if any).
        channel = spec.channel or os.environ.get("ANTIQUE_BROWSER_CHANNEL")

        if spec.key == "camoufox":
            # Camoufox: hardened Firefox with engine-level spoofing. Try the
            # camoufox library; fall back to bundled Firefox if not installed.
            try:
                from camoufox.asyncio import AsyncNewBrowser
                camo_config = {
                    "os": "windows" if fp.platform == "Win32" else "macos" if fp.platform == "MacIntel" else "linux",
                    "screen": {"width": fp.screen_width, "height": fp.screen_height},
                    "locale": fp.locale,
                    "timezone": fp.timezone,
                }
                if proxy_pw:
                    camo_config["proxy"] = proxy_pw
                browser = await AsyncNewBrowser(headless=self.headless, config=camo_config)
                context = await browser.new_context(
                    user_agent=fp.user_agent,
                    viewport={"width": fp.inner_width, "height": fp.inner_height},
                )
            except ImportError:
                log.warning("camoufox not installed, falling back to bundled Firefox")
                context = await playwright.firefox.launch_persistent_context(
                    user_data_dir=str(user_dir),
                    headless=self.headless,
                    proxy=proxy_pw,
                    locale=fp.locale,
                    timezone_id=fp.timezone,
                    user_agent=fp.user_agent,
                    viewport={"width": fp.inner_width, "height": fp.inner_height},
                )
        elif spec.base == "firefox":
            context = await playwright.firefox.launch_persistent_context(
                user_data_dir=str(user_dir),
                headless=self.headless,
                proxy=proxy_pw,
                locale=fp.locale,
                timezone_id=fp.timezone,
                user_agent=fp.user_agent,
                viewport={"width": fp.inner_width, "height": fp.inner_height},
            )
        elif spec.base == "webkit":
            context = await playwright.webkit.launch_persistent_context(
                user_data_dir=str(user_dir),
                headless=self.headless,
                proxy=proxy_pw,
                locale=fp.locale,
                timezone_id=fp.timezone,
                user_agent=fp.user_agent,
                viewport={"width": fp.inner_width, "height": fp.inner_height},
            )
        else:
            # Chromium base (bundled Chromium, or a real chrome/msedge channel).
            context = await playwright.chromium.launch_persistent_context(
                user_data_dir=str(user_dir),
                channel=channel,
                **launch_opts,
            )

        await context.add_init_script(init_js)
        if profile.cookies:
            cookies = [
                Cookie(
                    name=c.get("name", ""),
                    value=c.get("value", ""),
                    domain=c.get("domain", ""),
                    path=c.get("path", "/"),
                    expires=float(c.get("expires", -1)),
                    http_only=bool(c.get("httpOnly", False)),
                    secure=bool(c.get("secure", False)),
                    same_site=c.get("sameSite", "Lax"),
                ).to_playwright()
                for c in profile.cookies
            ]
            try:
                await context.add_cookies(cookies)
            except Exception:
                pass
        session_id = f"{profile.user_id}-{int(time.time())}"
        ws_endpoint = f"ws://127.0.0.1:{port}/devtools/browser"
        pid: Optional[int] = None
        try:
            browser_proc = context.browser._impl_obj._process if context.browser else None
            if browser_proc and browser_proc.pid:
                pid = browser_proc.pid
        except Exception:
            pass
        self.store.record_session(
            profile.user_id,
            session_id=session_id,
            debug_port=port,
            ws_endpoint=ws_endpoint,
            pid=pid,
        )
        return BrowserHandle(
            user_id=profile.user_id,
            session_id=session_id,
            debug_port=port,
            ws_endpoint=ws_endpoint,
            pid=pid,
            context=context,
        )