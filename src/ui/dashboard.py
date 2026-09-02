"""Web UI for managing profiles.

A simple FastAPI sub-app that serves a single-page dashboard. The HTML
template lives at ``src/ui/templates/index.html`` and uses fetch() to
talk to the JSON API.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict

from fastapi import APIRouter, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse


log = logging.getLogger("adshield.ui")
router = APIRouter()

_TEMPLATE_DIR = Path(__file__).parent / "templates"


@router.get("/ui", response_class=HTMLResponse)
@router.get("/dashboard", response_class=HTMLResponse)
@router.get("/ui/", response_class=HTMLResponse)
async def dashboard() -> FileResponse:
    """Serve the dashboard HTML."""
    html = _TEMPLATE_DIR / "index.html"
    if not html.exists():
        return HTMLResponse("<h1>Dashboard template not found</h1>", status_code=500)
    return FileResponse(str(html))


@router.get("/diagnostics/summary")
async def diagnostics_summary(request: Request) -> JSONResponse:
    """Operator health summary: profiles, migration, proxy failures, sessions.

    Reads from ``app.state.store`` and ``app.state.launcher`` (set by
    ``create_app`` in server.py). Does not touch routes.py globals.

    Returns an AdsPower-style ``{code, msg, data}`` envelope so the
    existing ``fetchJSON`` helper handles it transparently.
    """
    store = getattr(request.app.state, "store", None)
    launcher = getattr(request.app.state, "launcher", None)

    if store is None:
        return JSONResponse(
            status_code=503,
            content={"code": -1, "msg": "store not initialized", "data": None},
        )

    from ..core.diagnostics import compute_health_summary

    running_uids: list = []
    if launcher is not None:
        try:
            running_uids = [h.user_id for h in launcher.list_running()]
        except Exception as exc:
            log.warning("Could not enumerate running sessions: %s", exc)

    summary = compute_health_summary(store, running_uids=running_uids)
    return JSONResponse(content={"code": 0, "msg": "success", "data": summary})