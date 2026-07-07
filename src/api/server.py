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
from fastapi.responses import FileResponse

from ..core.browser import BrowserLauncher
from ..core.cdp import CDPProxy
from ..core.profile import ProfileStore
from ..core.storage import ensure_default_group
from .routes import router as api_router
from ..ui.dashboard import router as ui_router


log = logging.getLogger("adshield.server")


def create_app(
    *,
    api_port: int = 50325,
    cdp_port: int = 5555,
    data_root: Optional[Path] = None,
    headless: bool = False,
) -> FastAPI:
    """Build the FastAPI app with all wiring done."""
    if data_root is None:
        data_root = Path(os.environ.get("ANTIDETECT_DATA_DIR", "data"))
    data_root.mkdir(parents=True, exist_ok=True)

    store = ProfileStore(db_path=data_root / "antidetect.db")
    ensure_default_group(store.engine)
    launcher = BrowserLauncher(store, data_root=data_root, headless=headless)
    cdp = CDPProxy(launcher)

    from .routes import wire as wire_routes
    wire_routes(store, launcher, cdp)

    app = FastAPI(title="antidetect-local", version="0.1.0")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

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
        return {"msg": "antidetect-local API running", "docs": "/docs"}

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