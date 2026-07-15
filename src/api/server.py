"""FastAPI server entry point for the local API + UI.

Usage:
    python -m src.api.server --ui-port 8080
    # or via CLI:  python -m src.cli serve
"""
from __future__ import annotations

import argparse
import logging
import os
from pathlib import Path
from typing import Optional

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse

from ..core.browser import BrowserLauncher
from ..core.cdp import CDPProxy
from ..core.profile import ProfileStore
from ..core.storage import ensure_default_group
from .routes import router as api_router
from ..ui.dashboard import router as ui_router


log = logging.getLogger("adshield.server")


# Paths that never require auth (health, docs, dashboard, CDP discovery).
_AUTH_EXEMPT_PREFIXES = (
    "/health",
    "/docs",
    "/openapi.json",
    "/redoc",
    "/json/",        # CDP discovery endpoints used by local tooling
    "/devtools/",    # CDP websockets
)


def is_local_origin(origin: str, allowed_origins: Optional[list] = None) -> bool:
    """True if an Origin/Referer header points at localhost (or is absent), or
    matches one of the caller-supplied ``allowed_origins`` substrings.

    Used to block DNS-rebinding: a page on evil.com must not be allowed to
    drive the local API from the user's browser. ``allowed_origins`` lets the
    operator explicitly trust extra hosts (e.g. an ngrok/tunnel domain when the
    dashboard is exposed remotely) via the ``ANTIQUE_ALLOWED_ORIGINS`` env var.
    """
    if not origin:
        return True  # non-browser clients (curl, scripts) send no Origin
    o = origin.lower()
    for host in ("://127.0.0.1", "://localhost", "://[::1]", "://0.0.0.0"):
        if host in o:
            return True
    for extra in (allowed_origins or []):
        e = str(extra).strip().lower()
        if e and e in o:
            return True
    return False


def auth_check(
    path: str,
    method: str,
    headers: dict,
    *,
    token: str,
    allowed_origins: Optional[list] = None,
) -> tuple:
    """Decide whether a request is allowed. Pure + unit-testable.

    Returns ``(allowed: bool, status: int, message: str)``.

    Rules:
      - Exempt paths are always allowed.
      - A cross-origin browser request (non-local, non-allow-listed Origin) is
        rejected (403).
      - If ``token`` is set, a matching ``Authorization: Bearer <token>`` is
        required; otherwise 401.
      - If ``token`` is empty, only the Origin guard applies.
    """
    # Normalise header access (case-insensitive).
    lower = {k.lower(): v for k, v in headers.items()}

    if any(path.startswith(p) for p in _AUTH_EXEMPT_PREFIXES) or path == "/":
        return (True, 200, "ok")

    origin = lower.get("origin", "") or lower.get("referer", "")
    if not is_local_origin(origin, allowed_origins):
        return (False, 403, "cross-origin requests are not allowed")

    if token:
        auth = lower.get("authorization", "")
        expected = f"Bearer {token}"
        if auth != expected:
            return (False, 401, "missing or invalid API token")

    return (True, 200, "ok")


def create_app(
    *,
    api_port: int = 50325,
    cdp_port: int = 5555,
    data_root: Optional[Path] = None,
    headless: bool = False,
) -> FastAPI:
    """Build the FastAPI app with all wiring done."""
    if data_root is None:
        data_root = Path(os.environ.get("ANTIQUE_DATA_DIR", "data"))
    data_root.mkdir(parents=True, exist_ok=True)

    store = ProfileStore(db_path=data_root / "antique.db")
    ensure_default_group(store.engine)
    launcher = BrowserLauncher(store, data_root=data_root, headless=headless)
    cdp = CDPProxy(launcher)

    from .routes import wire as wire_routes
    # Pass the launcher's ExtensionStore so /extension/* routes work; without
    # it those endpoints hit `assert _ext_store is not None` and 500.
    wire_routes(store, launcher, cdp, launcher.ext_store)

    app = FastAPI(title="antique", version="0.5.0")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    api_token = os.environ.get("ANTIQUE_API_TOKEN", "")
    # Extra trusted origins (comma-separated) for remote/tunnel access, e.g.
    # ANTIQUE_ALLOWED_ORIGINS="ngrok-free.app,mytunnel.example.com".
    allowed_origins = [
        o.strip() for o in os.environ.get("ANTIQUE_ALLOWED_ORIGINS", "").split(",") if o.strip()
    ]

    @app.middleware("http")
    async def _auth_middleware(request, call_next):
        allowed, status, message = auth_check(
            request.url.path,
            request.method,
            dict(request.headers),
            token=api_token,
            allowed_origins=allowed_origins,
        )
        if not allowed:
            return JSONResponse(
                status_code=status,
                content={"code": -1, "msg": message, "data": None},
            )
        return await call_next(request)

    app.include_router(api_router, prefix="")
    app.include_router(ui_router, prefix="")

    app.state.store = store
    app.state.launcher = launcher
    app.state.cdp = cdp

    @app.on_event("shutdown")
    async def shutdown():
        await launcher.stop_all()

    @app.get("/", include_in_schema=False)
    async def root():
        dash = (Path(__file__).parent.parent / "ui" / "templates" / "index.html").resolve()
        if dash.exists():
            return FileResponse(str(dash))
        return {"msg": "antique API running", "docs": "/docs"}

    return app


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
    p = argparse.ArgumentParser()
    p.add_argument("--api-port", type=int, default=50325)
    p.add_argument("--ui-port", type=int, default=8080)
    p.add_argument("--cdp-port", type=int, default=5555)
    p.add_argument("--headless", action="store_true")
    p.add_argument("--host", default="127.0.0.1")
    args = p.parse_args()

    app = create_app(
        api_port=args.api_port,
        cdp_port=args.cdp_port,
        headless=args.headless,
    )
    uvicorn.run(app, host=args.host, port=args.ui_port, log_level="info")


if __name__ == "__main__":
    main()