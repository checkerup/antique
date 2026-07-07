"""CDP multiplexer (a minimal AdsPower-style proxy).

AdsPower exposes two HTTP ports:

  - ``50325`` — local API for managing profiles (start/stop/create/list)
  - ``5555``  — local CDP proxy: HTTP requests like
    ``GET http://localhost:5555/json/version`` return the same JSON as
    Chrome's remote-debugging endpoint. The twist is that requests are
    scoped to a specific profile via the ``user_id`` header or path.

We implement a similar pattern with FastAPI:

  - ``GET  /json/version``  → returns Chrome version (or our marker)
  - ``GET  /json/list``     → returns list of pages for a profile
  - ``GET  /json/new?user_id=...``  → opens a new tab on that profile
  - ``WS   /devtools/page/<user_id>/<target_id>`` → forwards to Playwright CDP
  - ``POST /start/<user_id>`` / ``POST /stop/<user_id>``

For simplicity and reliability we proxy CDP through Playwright rather than
spinning our own Chromium subprocess. External automation tools that
already speak CDP (like the user's existing ``adspower-mcp`` server) can
point their ``ADSPOWER_CDP_URL`` at this server.
"""
from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .browser import BrowserHandle, BrowserLauncher


@dataclass
class CDPSession:
    """A CDP page session — currently just a reference to a Playwright page."""
    user_id: str
    target_id: str
    page: Any  # playwright Page


class CDPProxy:
    """Routes CDP calls to the correct BrowserHandle for a given user_id."""

    def __init__(self, launcher: BrowserLauncher):
        self.launcher = launcher
        # user_id -> CDPSession[] (one per page opened in that profile)
        self._pages: Dict[str, List[CDPSession]] = {}

    async def list_targets(self, user_id: str) -> List[Dict[str, Any]]:
        """Return a list of CDP targets (pages) for ``user_id``."""
        handle = self.launcher.get_handle(user_id)
        if handle is None:
            return []
        pages = self._pages.get(user_id, [])
        out: List[Dict[str, Any]] = []
        for idx, session in enumerate(pages):
            try:
                url = session.page.url
            except Exception:
                url = "about:blank"
            out.append({
                "id": session.target_id,
                "type": "page",
                "title": "",
                "url": url,
                "webSocketDebuggerUrl": self._ws_url(user_id, session.target_id),
                "description": "",
            })
        return out

    async def open_new_page(self, user_id: str, url: str = "about:blank") -> Optional[CDPSession]:
        """Open a new tab in the user's profile and return a CDP session."""
        handle = self.launcher.get_handle(user_id)
        if handle is None:
            return None
        ctx = handle.context
        page = await ctx.new_page()
        if url and url != "about:blank":
            try:
                await page.goto(url, wait_until="domcontentloaded")
            except Exception:
                pass
        target_id = f"page-{user_id}-{len(self._pages.get(user_id, [])) + 1}-{id(page)}"
        session = CDPSession(user_id=user_id, target_id=target_id, page=page)
        self._pages.setdefault(user_id, []).append(session)
        return session

    def close_target(self, user_id: str, target_id: str) -> bool:
        sessions = self._pages.get(user_id, [])
        for i, s in enumerate(sessions):
            if s.target_id == target_id:
                try:
                    asyncio.get_event_loop().create_task(s.page.close())
                except Exception:
                    pass
                sessions.pop(i)
                return True
        return False

    def _ws_url(self, user_id: str, target_id: str) -> str:
        return f"ws://127.0.0.1:5555/devtools/page/{user_id}/{target_id}"

    # ---- JSON endpoints expected by chrome-remote-interface clients ----

    def version_payload(self) -> Dict[str, Any]:
        """Return the standard ``/json/version`` shape."""
        return {
            "Browser": f"antique/{self.launcher.__class__.__name__}",
            "Protocol-Version": "1.3",
            "User-Agent": "Mozilla/5.0 antique",
            "V8-Version": "",
            "WebKit-Version": "",
            "webSocketDebuggerUrl": "ws://127.0.0.1:5555/devtools/browser",
        }

    def list_payload(self, user_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Return the ``/json/list`` shape. If ``user_id`` is None, lists all."""
        if user_id is not None:
            # We can't await list_targets in a sync method; callers should use
            # the async version. Provide a sync snapshot for FastAPI response.
            return []  # populated in FastAPI layer via async wrapper
        all_pages: List[Dict[str, Any]] = []
        for uid in self.launcher.list_running():
            for sess in self._pages.get(uid.user_id, []):
                all_pages.append({
                    "id": sess.target_id,
                    "type": "page",
                    "title": "",
                    "url": "",
                    "webSocketDebuggerUrl": self._ws_url(uid.user_id, sess.target_id),
                    "description": "",
                })
        return all_pages