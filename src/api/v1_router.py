"""Version discovery for the stable v1 API.

Business endpoints are provided by the real AdsPower-compatible router, which
is mounted a second time at ``/api/v1`` by :func:`src.api.server.create_app`.
Keeping this module limited to discovery avoids a second, divergent set of
handlers and prevents successful-looking stub responses.
"""
from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from src import __version__

API_VERSION = "1.0.0"
API_VERSION_HEADER = "X-API-Version"

router = APIRouter()


class VersionInfo(BaseModel):
    api_version: str
    server_version: str
    status: str = "stable"


@router.get("/version", response_model=VersionInfo)
async def api_version() -> VersionInfo:
    return VersionInfo(api_version=API_VERSION, server_version=__version__)


@router.get("/health")
async def v1_health():
    return {
        "status": "ok",
        "service": "antique",
        "version": __version__,
        "api_version": API_VERSION,
    }
