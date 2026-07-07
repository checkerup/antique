"""Web UI for managing profiles.

A simple FastAPI sub-app that serves a single-page dashboard. The HTML
template lives at ``src/ui/templates/index.html`` and uses fetch() to
talk to the JSON API.
"""
from __future__ import annotations

import logging
from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import FileResponse, HTMLResponse


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