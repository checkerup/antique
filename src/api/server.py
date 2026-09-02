"""FastAPI server entry point for the local API + UI.

Usage:
    python -m src.api.server --ui-port 8080
    # or via CLI:  python -m src.cli serve
"""
from __future__ import annotations

import argparse
import hmac
import logging
import os
from pathlib import Path
from typing import Optional

import uvicorn
from fastapi import FastAPI, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse

from .. import __version__
from ..core.browser import BrowserLauncher
from ..core.cdp import CDPProxy
from ..core.profile import ProfileStore
from ..core.security import (
    DeploymentMode,
    generate_api_token,
    is_origin_allowed,
    parse_allowed_origins,
    validate_deployment_mode,
)
from ..core.storage import ensure_default_group
from .routes import router as api_router
from .v1_router import router as v1_meta_router
from ..ui.dashboard import router as ui_router


log = logging.getLogger("adshield.server")


# ---------------------------------------------------------------------------
# Path classification — which paths are always exempt vs. mode-dependent
# ---------------------------------------------------------------------------

# Paths that NEVER require auth in any mode: health, docs, PWA assets.
_AUTH_EXEMPT_ALWAYS = frozenset({
    "/health",
    "/docs",
    "/openapi.json",
    "/redoc",
    "/manifest.json",
    "/sw.js",
    "/ui/manifest.json",
})

# Paths that are exempt in local/LAN mode (CDP discovery/tooling) but
# require auth in remote mode.  These carry profile data or allow
# WebSocket injection so they must be gated when exposed.
_CDP_PREFIXES = (
    "/json/",
    "/devtools/",
)

# The root "/" serves the dashboard — treated as always-exempt (it's a
# static HTML file, not API data).


def _is_path_exempt(path: str, mode: DeploymentMode) -> bool:
    """True if *path* does not require authentication in *mode*."""
    if path == "/" or path in _AUTH_EXEMPT_ALWAYS:
        return True
    if any(path.startswith(p) for p in _CDP_PREFIXES):
        # /json and /devtools are only exempt in local/lan mode.
        return mode != DeploymentMode.REMOTE
    return False


def is_local_origin(origin: str, allowed_origins: Optional[list] = None) -> bool:
    """True if an Origin/Referer header points at localhost (or is absent),
    or matches one of the caller-supplied ``allowed_origins``.

    .. deprecated::
        This function is kept for backward compatibility with
        ``test_auth.py``.  It delegates to the new exact-match
        ``is_origin_allowed``.  New code should call ``is_origin_allowed``
        directly.
    """
    return is_origin_allowed(origin, allowed_origins)


def auth_check(
    path: str,
    method: str,
    headers: dict,
    *,
    token: str,
    allowed_origins: Optional[list] = None,
    mode: DeploymentMode = DeploymentMode.LOCAL,
) -> tuple:
    """Decide whether a request is allowed. Pure + unit-testable.

    Returns ``(allowed: bool, status: int, message: str)``.

    Rules (mode-aware):

    - **Always-exempt paths** (health, docs, PWA assets, ``/``) are
      allowed in every mode.
    - **CDP paths** (``/json/*``, ``/devtools/*``) are exempt in local
      and LAN mode but require auth in remote mode.
    - A cross-origin browser request (non-local, non-allow-listed
      Origin) is rejected (403).
    - If ``token`` is set, a matching ``Authorization: Bearer ***`` is
      required; otherwise 401.
    - If ``token`` is empty, only the Origin guard applies (unless the
      path is CDP and mode is REMOTE — but that's handled at startup
      by the fail-closed check, not here).
    """
    # Normalise header access (case-insensitive).
    lower = {k.lower(): v for k, v in headers.items()}

    if _is_path_exempt(path, mode):
        return (True, 200, "ok")

    origin = lower.get("origin", "") or lower.get("referer", "")
    if not is_origin_allowed(origin, allowed_origins):
        return (False, 403, "cross-origin requests are not allowed")

    if token:
        auth = lower.get("authorization", "")
        expected = f"Bearer {token}"
        # Constant-time comparison to prevent timing attacks.
        if not hmac.compare_digest(auth, expected):
            return (False, 401, "missing or invalid API token")

    return (True, 200, "ok")


def validate_startup(
    mode: DeploymentMode,
    host: str,
    api_token: str,
) -> None:
    """Fail-closed startup validation.

    In **remote** mode bound to a non-loopback interface, an API token
    is mandatory — the server refuses to start without one rather than
    silently running an open API.

    In **local** and **LAN** modes, no token is required (local is
    loopback-only; LAN assumes a trusted network).
    """
    from ..core.security import is_loopback_host

    if mode == DeploymentMode.REMOTE and not api_token:
        # If binding to loopback only, remote mode is safe without token.
        if host and not is_loopback_host(host):
            raise RuntimeError(
                "API token is required in remote mode when binding to a "
                "non-loopback address. Set ANTIQUE_API_TOKEN or use "
                "--generate-token. Use --deploy-mode local or lan if "
                "you don't need authentication."
            )


def _resolve_cors_origins(
    mode: DeploymentMode,
    allowed_origins: list,
) -> list:
    """Compute the CORS allow-origins list for the given mode.

    - Local: ``["*"]`` (developer convenience).
    - LAN/Remote: the explicit allowlist only (no wildcard).
    """
    if mode == DeploymentMode.LOCAL:
        return ["*"]
    # In LAN/remote, restrict to the operator-supplied allowlist.
    # If empty, CORS will simply reject cross-origin browser requests,
    # which is the safe default.
    return list(allowed_origins) if allowed_origins else []


def create_app(
    *,
    api_port: int = 50325,
    cdp_port: int = 5555,
    data_root: Optional[Path] = None,
    headless: bool = False,
    deploy_mode: Optional[DeploymentMode] = None,
    api_token: Optional[str] = None,
    allowed_origins: Optional[list] = None,
) -> FastAPI:
    """Build the FastAPI app with all wiring done.

    Parameters
    ----------
    deploy_mode : DeploymentMode
        Security posture. Defaults to resolving from
        ``ANTIQUE_DEPLOY_MODE`` env var, then ``LOCAL``.
    api_token : str, optional
        Bearer token for API auth. Defaults to ``ANTIQUE_API_TOKEN``
        env var.
    allowed_origins : list, optional
        Explicitly-trusted origins for cross-origin access in LAN/remote
        mode. Defaults to ``ANTIQUE_ALLOWED_ORIGINS`` env var.
    """
    if data_root is None:
        data_root = Path(os.environ.get("ANTIQUE_DATA_DIR", "data"))
    data_root.mkdir(parents=True, exist_ok=True)

    # Resolve security parameters.
    if deploy_mode is None:
        deploy_mode = validate_deployment_mode(None)
    if api_token is None:
        api_token = os.environ.get("ANTIQUE_API_TOKEN", "")
    if allowed_origins is None:
        allowed_origins = parse_allowed_origins(
            os.environ.get("ANTIQUE_ALLOWED_ORIGINS", "")
        )

    store = ProfileStore(db_path=data_root / "antique.db")
    ensure_default_group(store.engine)
    launcher = BrowserLauncher(store, data_root=data_root, headless=headless)
    cdp = CDPProxy(launcher)

    from .routes import wire as wire_routes
    # Pass the launcher's ExtensionStore so /extension/* routes work; without
    # it those endpoints hit `assert _ext_store is not None` and 500.
    wire_routes(store, launcher, cdp, launcher.ext_store)

    app = FastAPI(title="antique", version=__version__)

    # CORS — restrictive in LAN/remote mode.
    cors_origins = _resolve_cors_origins(deploy_mode, allowed_origins)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def _auth_middleware(request, call_next):
        allowed, status, message = auth_check(
            request.url.path,
            request.method,
            dict(request.headers),
            token=api_token,
            allowed_origins=allowed_origins,
            mode=deploy_mode,
        )
        if not allowed:
            return JSONResponse(
                status_code=status,
                content={"code": -1, "msg": message, "data": None},
            )
        return await call_next(request)

    app.include_router(api_router, prefix="")
    # The stable v1 namespace delegates to the exact same handlers and wired
    # store/launcher as the legacy AdsPower-compatible API.  Mount the small
    # metadata router first so /api/v1/version and /api/v1/health have explicit
    # versioned representations.
    app.include_router(v1_meta_router, prefix="/api/v1")
    app.include_router(api_router, prefix="/api/v1")
    app.include_router(ui_router, prefix="")

    app.state.store = store
    app.state.launcher = launcher
    app.state.cdp = cdp
    app.state.deploy_mode = deploy_mode
    app.state.api_token = api_token
    app.state.allowed_origins = allowed_origins

    from contextlib import asynccontextmanager

    @asynccontextmanager
    async def lifespan(app):
        yield
        await launcher.stop_all()

    app.router.lifespan_context = lifespan

    @app.get("/", include_in_schema=False)
    async def root():
        dash = (Path(__file__).parent.parent / "ui" / "templates" / "index.html").resolve()
        if dash.exists():
            return FileResponse(str(dash))
        return {"msg": "antique API running", "docs": "/docs"}

    # ------------------------------------------------------------------
    # PWA assets
    #
    # Served from src/ui/templates/ so the dashboard is installable and works
    # offline. The service worker must be served from the origin root for its
    # scope to cover the whole dashboard, which is why these are app-level
    # routes rather than a mounted /static sub-path. Both files are authored
    # with a UTF-8 BOM, so they are read with utf-8-sig and re-served as clean
    # UTF-8 (a BOM makes manifest.json unparseable for strict JSON clients).
    # ------------------------------------------------------------------

    def _pwa_asset(name: str, media_type: str) -> Response:
        path = (Path(__file__).parent.parent / "ui" / "templates" / name).resolve()
        if not path.exists():
            raise HTTPException(status_code=404, detail=f"{name} not found")
        return Response(
            content=path.read_text(encoding="utf-8-sig"),
            media_type=media_type,
            headers={"Cache-Control": "no-cache"},
        )

    @app.get("/manifest.json", include_in_schema=False)
    async def pwa_manifest():
        return _pwa_asset("manifest.json", "application/manifest+json")

    @app.get("/ui/manifest.json", include_in_schema=False)
    async def pwa_manifest_ui():
        return _pwa_asset("manifest.json", "application/manifest+json")

    @app.get("/sw.js", include_in_schema=False)
    async def pwa_service_worker():
        return _pwa_asset("sw.js", "application/javascript")

    return app


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
    p = argparse.ArgumentParser()
    p.add_argument("--api-port", type=int, default=50325)
    p.add_argument("--ui-port", type=int, default=8080)
    p.add_argument("--cdp-port", type=int, default=5555)
    p.add_argument("--headless", action="store_true")
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument(
        "--deploy-mode",
        default=None,
        choices=["local", "lan", "remote"],
        help="Deployment security mode (default: local)",
    )
    p.add_argument(
        "--generate-token",
        action="store_true",
        help="Generate a secure API token, print it, and use it for this session",
    )
    args = p.parse_args()

    mode = validate_deployment_mode(args.deploy_mode)

    api_token = os.environ.get("ANTIQUE_API_TOKEN", "")
    if args.generate_token:
        api_token = generate_api_token()
        print(f"Generated API token: {api_token}")
        print("Set ANTIQUE_API_TOKEN=<token> to persist it across restarts.")

    # Fail-closed: refuse to start in an insecure configuration.
    validate_startup(mode=mode, host=args.host, api_token=api_token)

    app = create_app(
        api_port=args.api_port,
        cdp_port=args.cdp_port,
        headless=args.headless,
        deploy_mode=mode,
        api_token=api_token,
    )
    uvicorn.run(app, host=args.host, port=args.ui_port, log_level="info")


if __name__ == "__main__":
    main()
