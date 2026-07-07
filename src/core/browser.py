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


class BrowserLauncher:
    def __init__(
        self,
        store: ProfileStore,
        *,
        data_root: Optional[Path] = None,
        headless: bool = False,
    ):
        self.store = store
        self.data_root = data_root or Path(os.environ.get("ANTIQUE_DATA_DIR", "data"))
        self.data_root.mkdir(parents=True, exist_ok=True)
        self.headless = headless
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

    async def _launch(self, profile: Profile, *, debug_port: Optional[int]) -> BrowserHandle:
        from playwright.async_api import async_playwright
        fp = self._resolve_fingerprint(profile)
        proxy_cfg = parse_proxy(profile.proxy or None)
        proxy_pw = proxy_cfg.to_playwright()
        user_dir = self._profile_user_dir(profile.user_id)
        # If the profile was created from a full .adb import, copy
        # LocalStorage + IndexedDB into the user_data_dir before the first
        # launch so Chromium reads them natively.
        await self._maybe_apply_imported_state(profile, user_dir)
        port = _find_free_port(debug_port)
        launch_opts = to_playwright_launch_options(fp, proxy=proxy_pw)
        launch_opts["headless"] = self.headless
        init_js = build_init_script(fp)
        playwright = await async_playwright().start()
        channel = os.environ.get("ANTIQUE_BROWSER_CHANNEL")
        chromium = playwright.chromium if not channel else playwright.chromium
        context = await chromium.launch_persistent_context(
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