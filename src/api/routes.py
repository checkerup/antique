"""AdsPower-compatible API routes.

Endpoints mirror AdsPower's local API (port 50325) so existing scripts
that talk to AdsPower can switch by changing the base URL.

POST /user/create         {name, group_id?, user_proxy_config?, fingerprint_config?, remark?, tags?}
POST /user/update         {user_id, ...fields to update}
GET  /user/list           ?group_id=&page=&page_size=&search=
POST /user/delete         {user_id}
POST /user/start          {user_id, debug_port?}
POST /user/stop           {user_id}
GET  /user/active         (running sessions)
POST /user/import         (multipart file or {path}) → creates a profile from an AdsPower bundle
POST /user/export         {user_id, format} → returns the profile JSON
POST /user/{user_id}/reimport  Reset the initial_state_applied flag

Plus CDP-proxy routes:
GET  /json/version        Chrome devtools version
GET  /json/list?user_id=  CDP targets for a profile
WS   /devtools/page/{user_id}/{target_id}
"""
from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Body, File, HTTPException, Query, UploadFile, WebSocket
from pydantic import BaseModel, Field

from ..core.backup_import import import_adspower_backup_root
from ..core.browser import BrowserLauncher
from ..core.cdp import CDPProxy
from ..core.cookie import (
    Cookie,
    export_cookies_json,
    export_cookies_netscape,
    import_cookies,
    import_cookies_json,
    import_cookies_netscape,
    prepare_adspower_import,
)
from ..core.fingerprint import Fingerprint, generate_fingerprint
from ..core.profile import ProfileStore
from ..core.extension import ExtensionStore
from ..core.proxy import ProxyConfig, check_proxy, parse_proxy_list, parse_proxy, adspower_shape
from ..core.geo import geo_for_country, geo_from_proxy, apply_geo_to_fingerprint, supported_countries
from ..core.proxy_pool import ProxyPool
from ..core.portable import build_bundle, import_profile as portable_import, PortableBundleError
from ..core.detect import score_report, expected_from_fingerprint
from ..core.engines import list_engines, engine_keys


log = logging.getLogger("antique.api")
router = APIRouter()

# These are wired in by server.py at startup
_store: Optional[ProfileStore] = None
_launcher: Optional[BrowserLauncher] = None
_cdp: Optional[CDPProxy] = None
_ext_store: Optional[ExtensionStore] = None


def wire(store: ProfileStore, launcher: BrowserLauncher, cdp: CDPProxy, ext_store: Optional[ExtensionStore] = None) -> None:
    global _store, _launcher, _cdp, _ext_store
    _store = store
    _launcher = launcher
    _cdp = cdp
    _ext_store = ext_store


# ---------------------------------------------------------------------------
# Pydantic schemas — AdsPower-compatible shapes
# ---------------------------------------------------------------------------


class UserCreate(BaseModel):
    name: str
    group_id: str = "0"
    user_proxy_config: Optional[Dict[str, Any]] = None
    fingerprint_config: Optional[Dict[str, Any]] = None
    cookies: Optional[List[Dict[str, Any]]] = None
    remark: Optional[str] = ""
    tags: Optional[List[str]] = None
    user_id: Optional[str] = None


class UserUpdate(BaseModel):
    user_id: str
    name: Optional[str] = None
    group_id: Optional[str] = None
    user_proxy_config: Optional[Dict[str, Any]] = None
    fingerprint_config: Optional[Dict[str, Any]] = None
    cookies: Optional[List[Dict[str, Any]]] = None
    remark: Optional[str] = None
    tags: Optional[List[str]] = None


class UserDelete(BaseModel):
    user_id: str


class UserStart(BaseModel):
    user_id: str
    debug_port: Optional[int] = None
    launch_args: Optional[List[str]] = None


class UserStop(BaseModel):
    user_id: str


class UserImport(BaseModel):
    name: str
    source_path: str


class BackupImportRequest(BaseModel):
    source_path: str
    overwrite: bool = False
    limit: Optional[int] = Field(default=None, ge=1)


class BulkAction(BaseModel):
    user_ids: List[str]


class BulkProxyAssign(BaseModel):
    user_ids: List[str]
    user_proxy_config: Dict[str, Any]


class ProxyCheckRequest(BaseModel):
    user_proxy_config: Dict[str, Any]


class BulkProxyImport(BaseModel):
    proxy_list: str  # newline-separated proxy list
    user_ids: Optional[List[str]] = None  # if provided, assign 1:1; else create pool


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _profile_to_adspower_shape(p) -> Dict[str, Any]:
    return {
        "user_id": p.user_id,
        "name": p.name,
        "group_id": p.group_id,
        "created_at": p.created_at.isoformat() if p.created_at else None,
        "updated_at": p.updated_at.isoformat() if p.updated_at else None,
        "last_launched_at": p.last_launched_at.isoformat() if p.last_launched_at else None,
        "launch_count": p.launch_count,
        "remark": p.remark,
        "tags": p.tags,
        "user_proxy_config": p.proxy,
        "fingerprint_config": p.fingerprint,
        "cookies": p.cookies,
        "status": "Active" if p.running_debug_port else "Inactive",
        "debug_port": p.running_debug_port,
        "ws_endpoint": p.running_ws,
    }


def _ads_response(success: bool, **data: Any) -> Dict[str, Any]:
    return {"code": 0 if success else 1, "msg": "success" if success else "error", "data": data}


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------


@router.get("/health")
def health() -> Dict[str, Any]:
    return {"status": "ok", "service": "antique", "version": "0.2.0"}


# ---------------------------------------------------------------------------
# Profiles
# ---------------------------------------------------------------------------


@router.post("/user/create")
def user_create(body: UserCreate) -> Dict[str, Any]:
    assert _store is not None
    fp: Optional[Fingerprint] = None
    if body.fingerprint_config:
        from dataclasses import fields as dc_fields
        valid_keys = {f.name for f in dc_fields(Fingerprint)}
        cleaned = {k: v for k, v in body.fingerprint_config.items() if k in valid_keys}
        fp = Fingerprint(**cleaned)
    else:
        fp = generate_fingerprint()
    p = _store.create(
        name=body.name,
        group_id=body.group_id,
        proxy=body.user_proxy_config or {},
        fingerprint=fp,
        cookies=body.cookies or [],
        tags=body.tags or [],
        remark=body.remark or "",
        user_id=body.user_id,
    )
    return _ads_response(True, **{
        "id": p.user_id,
        "user_id": p.user_id,
        "name": p.name,
    })


@router.post("/user/update")
def user_update(body: UserUpdate) -> Dict[str, Any]:
    assert _store is not None
    fp = None
    if body.fingerprint_config:
        from dataclasses import fields as dc_fields
        valid_keys = {f.name for f in dc_fields(Fingerprint)}
        cleaned = {k: v for k, v in body.fingerprint_config.items() if k in valid_keys}
        fp = Fingerprint(**cleaned)
    try:
        p = _store.update(
            body.user_id,
            name=body.name,
            group_id=body.group_id,
            proxy=body.user_proxy_config,
            fingerprint=fp,
            cookies=body.cookies,
            tags=body.tags,
            remark=body.remark,
        )
    except KeyError:
        raise HTTPException(status_code=404, detail="user_id not found")
    return _ads_response(True, **{
        "id": p.user_id,
        "user_id": p.user_id,
        "name": p.name,
    })


@router.get("/user/list")
def user_list(
    group_id: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(100, ge=1, le=1000),
    search: Optional[str] = Query(None),
    tag: Optional[str] = Query(None),
) -> Dict[str, Any]:
    assert _store is not None
    profiles = _store.list(group_id=group_id, tag=tag, search=search)
    total = len(profiles)
    start = (page - 1) * page_size
    end = start + page_size
    sliced = profiles[start:end]
    return _ads_response(
        True,
        list=[_profile_to_adspower_shape(p) for p in sliced],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post("/user/delete")
def user_delete(body: UserDelete) -> Dict[str, Any]:
    assert _store is not None
    ok = _store.delete(body.user_id)
    if not ok:
        raise HTTPException(status_code=404, detail="user_id not found")
    return _ads_response(True, **{
        "user_id": body.user_id,
        "deleted": True,
    })


@router.post("/user/start")
async def user_start(body: UserStart) -> Dict[str, Any]:
    assert _store is not None and _launcher is not None
    p = _store.get(body.user_id)
    if p is None:
        raise HTTPException(status_code=404, detail="user_id not found")
    handle = await _launcher.start(p, debug_port=body.debug_port)
    return _ads_response(True, **{
        "user_id": p.user_id,
        "debug_port": handle.debug_port,
        "ws_endpoint": handle.ws_endpoint,
        "pid": handle.pid,
        "session_id": handle.session_id,
    })


@router.post("/user/stop")
async def user_stop(body: UserStop) -> Dict[str, Any]:
    assert _launcher is not None
    ok = await _launcher.stop(body.user_id)
    return _ads_response(True, **{
        "user_id": body.user_id,
        "stopped": ok,
    })


@router.get("/user/active")
def user_active() -> Dict[str, Any]:
    assert _launcher is not None
    handles = _launcher.list_running()
    return _ads_response(True, **{
        "list": [
            {
                "user_id": h.user_id,
                "session_id": h.session_id,
                "debug_port": h.debug_port,
                "ws_endpoint": h.ws_endpoint,
                "pid": h.pid,
            }
            for h in handles
        ]
    })


@router.post("/user/import")
async def user_import(
    body: Optional[UserImport] = None,
    file: Optional[UploadFile] = File(None),
) -> Dict[str, Any]:
    assert _store is not None
    import tempfile, shutil

    cookies: List[Cookie] = []
    extracted_path: Optional[str] = None
    profile_name = ""
    is_full_profile = False
    cleanup_src = False  # only set True when we wrote a temp file we own

    # Resolve the source bundle to a path on disk.
    src_path: Optional[Path] = None
    if file is not None:
        content = await file.read()
        name = file.filename or "uploaded"
        suffix = Path(name).suffix.lower()
        if suffix == ".json":
            cookies = import_cookies_json(content.decode("utf-8", errors="replace"))
            profile_name = Path(name).stem
        elif suffix in (".zip", ".adb", ".tar", ".tgz") or name.endswith(".tar.gz"):
            tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix or ".adb")
            tmp.write(content)
            tmp.close()
            src_path = Path(tmp.name)
            cleanup_src = True  # temp file we should delete after extraction
            profile_name = Path(name).stem
        else:
            cookies = import_cookies_netscape(content.decode("utf-8", errors="replace"))
            profile_name = Path(name).stem
    elif body is not None and body.source_path:
        src_path = Path(body.source_path)
        profile_name = body.name
    else:
        raise HTTPException(status_code=400, detail="Provide either file upload or source_path")

    if src_path is not None:
        # Create the profile with a generated user_id, then extract the bundle
        # under data/profiles/imports/<user_id>/ so the launcher can apply
        # LocalStorage/IndexedDB on first launch.
        p = _store.create(name=profile_name or "imported")
        import_root = Path(os.environ.get("ANTIQUE_DATA_DIR", "data")) / "profiles" / "imports"
        import_root.mkdir(parents=True, exist_ok=True)
        try:
            result = prepare_adspower_import(src_path, import_root, p.user_id)
            cookies = result["cookies"]
            extracted_path = result["extracted_path"]
            is_full_profile = True
        except ValueError:
            # Bundle format not supported — fall back to cookies-only via the
            # legacy import path.
            shutil.rmtree(import_root / p.user_id, ignore_errors=True)
            cookies = import_cookies(src_path)
        finally:
            if cleanup_src:
                try:
                    src_path.unlink()
                except OSError:
                    pass
        # Persist cookies + extraction path on the profile
        cookie_dicts = [c.to_playwright() for c in cookies]
        _store.update(p.user_id, cookies=cookie_dicts)
        if extracted_path:
            _store.set_import_source(p.user_id, extracted_path)
        return _ads_response(True, **{
            "user_id": p.user_id,
            "name": p.name,
            "cookie_count": len(cookies),
            "full_profile_import": is_full_profile,
            "import_source_path": extracted_path,
        })

    # Cookies-only flow (Netscape / JSON)
    cookie_dicts = [c.to_playwright() for c in cookies]
    p = _store.create(name=profile_name, cookies=cookie_dicts)
    return _ads_response(True, **{
        "user_id": p.user_id,
        "name": p.name,
        "cookie_count": len(cookies),
        "full_profile_import": False,
    })


@router.post("/user/import/backup")
def user_import_backup(body: BackupImportRequest) -> Dict[str, Any]:
    assert _store is not None
    summary = import_adspower_backup_root(
        Path(body.source_path),
        _store,
        overwrite=body.overwrite,
        limit=body.limit,
    )
    return _ads_response(True, **summary)


@router.post("/user/{user_id}/reimport")
async def user_reimport(user_id: str) -> Dict[str, Any]:
    """Reset the ``initial_state_applied`` flag so the next launch re-copies
    LocalStorage/IndexedDB from the persisted ``import_source_path``.

    Use this if you want to refresh a profile from a re-exported .adb bundle.
    The bundle must already be on disk at the recorded path — re-import it via
    ``/user/import`` (with the same ``name``) if you need to swap the source.
    """
    assert _store is not None
    p = _store.get(user_id)
    if p is None:
        raise HTTPException(status_code=404, detail="user_id not found")
    if not p.import_source_path:
        raise HTTPException(
            status_code=400,
            detail="profile has no import_source_path; import via /user/import first",
        )
    _store.set_import_source(user_id, p.import_source_path, reset_applied=True)
    return _ads_response(True, **{
        "user_id": user_id,
        "reset": True,
        "import_source_path": p.import_source_path,
    })


@router.post("/user/export")
def user_export(
    user_id: str = Query(...),
    format: str = Query("json", description="json | netscape"),
) -> Dict[str, Any]:
    assert _store is not None
    p = _store.get(user_id)
    if p is None:
        raise HTTPException(status_code=404, detail="user_id not found")
    cookies = [
        Cookie(
            name=c.get("name", ""),
            value=c.get("value", ""),
            domain=c.get("domain", ""),
            path=c.get("path", "/"),
            expires=float(c.get("expires", -1)),
            http_only=bool(c.get("httpOnly", c.get("http_only", False))),
            secure=bool(c.get("secure", False)),
            same_site=c.get("sameSite", c.get("same_site", "Lax")),
        )
        for c in p.cookies
    ]
    if format == "netscape":
        text = export_cookies_netscape(cookies)
    else:
        text = export_cookies_json(cookies)
    return {"code": 0, "msg": "success", "data": {"text": text, "format": format}}


@router.get("/profile/{user_id}")
def get_profile(user_id: str) -> Dict[str, Any]:
    assert _store is not None
    p = _store.get(user_id)
    if p is None:
        raise HTTPException(status_code=404, detail="user_id not found")
    return _ads_response(True, **_profile_to_adspower_shape(p))


# ---------------------------------------------------------------------------
# Bulk operations
# ---------------------------------------------------------------------------


@router.post("/user/bulk/start")
async def user_bulk_start(body: BulkAction) -> Dict[str, Any]:
    assert _store is not None and _launcher is not None
    results = []
    for uid in body.user_ids:
        p = _store.get(uid)
        if p is None:
            results.append({"user_id": uid, "ok": False, "error": "not found"})
            continue
        try:
            handle = await _launcher.start(p)
            results.append({"user_id": uid, "ok": True, "debug_port": handle.debug_port})
        except Exception as e:
            results.append({"user_id": uid, "ok": False, "error": str(e)})
    return _ads_response(True, results=results)


@router.post("/user/bulk/stop")
async def user_bulk_stop(body: BulkAction) -> Dict[str, Any]:
    assert _launcher is not None
    results = []
    for uid in body.user_ids:
        try:
            ok = await _launcher.stop(uid)
            results.append({"user_id": uid, "ok": ok})
        except Exception as e:
            results.append({"user_id": uid, "ok": False, "error": str(e)})
    return _ads_response(True, results=results)


@router.post("/user/bulk/delete")
def user_bulk_delete(body: BulkAction) -> Dict[str, Any]:
    assert _store is not None
    results = []
    for uid in body.user_ids:
        ok = _store.delete(uid)
        results.append({"user_id": uid, "deleted": ok})
    return _ads_response(True, results=results, deleted_count=sum(1 for r in results if r["deleted"]))


@router.post("/user/bulk/export")
def user_bulk_export(body: BulkAction) -> Dict[str, Any]:
    assert _store is not None
    exports = []
    for uid in body.user_ids:
        p = _store.get(uid)
        if p is None:
            continue
        cookies = [
            Cookie(
                name=c.get("name", ""),
                value=c.get("value", ""),
                domain=c.get("domain", ""),
                path=c.get("path", "/"),
                expires=float(c.get("expires", -1)),
                http_only=bool(c.get("httpOnly", c.get("http_only", False))),
                secure=bool(c.get("secure", False)),
                same_site=c.get("sameSite", c.get("same_site", "Lax")),
            )
            for c in p.cookies
        ]
        exports.append({
            "user_id": uid,
            "name": p.name,
            "cookies_json": export_cookies_json(cookies),
        })
    return _ads_response(True, profiles=exports, count=len(exports))


# ---------------------------------------------------------------------------
# Proxy check & bulk proxy assignment
# ---------------------------------------------------------------------------


@router.post("/proxy/check")
async def proxy_check(body: ProxyCheckRequest) -> Dict[str, Any]:
    cfg = parse_proxy(body.user_proxy_config)
    result = await check_proxy(cfg)
    return _ads_response(True, **result)


@router.post("/user/{user_id}/proxy/check")
async def user_proxy_check(user_id: str) -> Dict[str, Any]:
    assert _store is not None
    p = _store.get(user_id)
    if p is None:
        raise HTTPException(status_code=404, detail="user_id not found")
    cfg = parse_proxy(p.proxy)
    result = await check_proxy(cfg)
    return _ads_response(True, user_id=user_id, **result)


@router.post("/user/bulk/proxy/assign")
def user_bulk_proxy_assign(body: BulkProxyAssign) -> Dict[str, Any]:
    assert _store is not None
    results = []
    for uid in body.user_ids:
        try:
            _store.update(uid, proxy=body.user_proxy_config)
            results.append({"user_id": uid, "ok": True})
        except KeyError:
            results.append({"user_id": uid, "ok": False, "error": "not found"})
    return _ads_response(True, results=results)


@router.post("/user/bulk/proxy/import")
def user_bulk_proxy_import(body: BulkProxyImport) -> Dict[str, Any]:
    """Import a list of proxies and assign them to profiles.

    If user_ids is provided, assigns proxies 1:1 (cycling if fewer proxies than profiles).
    If user_ids is not provided, assigns to all profiles in order.
    """
    assert _store is not None
    from ..core.proxy import adspower_shape
    configs = parse_proxy_list(body.proxy_list)
    if not configs:
        raise HTTPException(status_code=400, detail="No valid proxies found in input")

    target_ids = body.user_ids
    if not target_ids:
        profiles = _store.list()
        target_ids = [p.user_id for p in profiles]

    results = []
    for i, uid in enumerate(target_ids):
        cfg = configs[i % len(configs)]
        proxy_dict = adspower_shape(cfg)
        try:
            _store.update(uid, proxy=proxy_dict)
            results.append({"user_id": uid, "ok": True, "proxy": f"{cfg.type}://{cfg.host}:{cfg.port}"})
        except KeyError:
            results.append({"user_id": uid, "ok": False, "error": "not found"})
    return _ads_response(True, results=results, assigned_count=sum(1 for r in results if r.get("ok")))


# ---------------------------------------------------------------------------
# Extensions
# ---------------------------------------------------------------------------


@router.get("/extension/list")
def extension_list() -> Dict[str, Any]:
    """List all installed extensions."""
    assert _ext_store is not None
    exts = _ext_store.list()
    return _ads_response(True, list=[e.to_dict() for e in exts], total=len(exts))


@router.post("/extension/install")
async def extension_install(
    source_type: str = Body("unpacked"),
    path: Optional[str] = Body(None),
    webstore_id: Optional[str] = Body(None),
    name: Optional[str] = Body(None),
    file: Optional[UploadFile] = File(None),
) -> Dict[str, Any]:
    """Install an extension from unpacked dir, .crx file, or Chrome Web Store ID."""
    assert _ext_store is not None
    if source_type == "webstore" and webstore_id:
        ext = _ext_store.install_from_webstore(webstore_id, name=name)
    elif source_type == "crx" and file:
        import tempfile
        tmp = tempfile.NamedTemporaryFile(suffix=".crx", delete=False)
        content = await file.read()
        tmp.write(content)
        tmp.close()
        try:
            ext = _ext_store.install_from_crx(Path(tmp.name), name=name)
        finally:
            os.unlink(tmp.name)
    elif source_type == "crx" and path:
        ext = _ext_store.install_from_crx(Path(path), name=name)
    elif path:
        ext = _ext_store.install_from_unpacked(Path(path), name=name)
    else:
        raise HTTPException(status_code=400, detail="Provide path, file, or webstore_id")
    return _ads_response(True, **ext.to_dict())


@router.post("/extension/uninstall")
def extension_uninstall(ext_id: str = Body(..., embed=True)) -> Dict[str, Any]:
    """Uninstall an extension."""
    assert _ext_store is not None
    ok = _ext_store.uninstall(ext_id)
    return _ads_response(True, ext_id=ext_id, deleted=ok)


@router.post("/user/{user_id}/extensions")
def user_set_extensions(user_id: str, extension_ids: List[str] = Body(...)) -> Dict[str, Any]:
    """Assign extensions to a profile."""
    assert _store is not None
    p = _store.get(user_id)
    if p is None:
        raise HTTPException(status_code=404, detail="user_id not found")
    fp = dict(p.fingerprint) if p.fingerprint else {}
    fp["extensions"] = extension_ids
    from ..core.fingerprint import Fingerprint
    from dataclasses import fields as dc_fields
    valid_keys = {f.name for f in dc_fields(Fingerprint)}
    cleaned = {k: v for k, v in fp.items() if k in valid_keys}
    # Store extensions separately in the fingerprint dict
    # (extensions is not a Fingerprint dataclass field, so we handle it specially)
    _store.update(user_id, fingerprint=Fingerprint(**cleaned))
    # Also store extensions in the raw fingerprint JSON
    import json
    from ..core.storage import ProfileRecord
    from sqlmodel import Session
    with Session(_store.engine) as s:
        r = s.get(ProfileRecord, user_id)
        if r:
            fp_data = json.loads(r.fingerprint_config) if r.fingerprint_config else {}
            fp_data["extensions"] = extension_ids
            r.fingerprint_config = json.dumps(fp_data)
            r.touch()
            s.add(r)
            s.commit()
    return _ads_response(True, user_id=user_id, extensions=extension_ids)


@router.get("/user/{user_id}/extensions")
def user_get_extensions(user_id: str) -> Dict[str, Any]:
    """Get extensions assigned to a profile."""
    assert _store is not None
    p = _store.get(user_id)
    if p is None:
        raise HTTPException(status_code=404, detail="user_id not found")
    ext_ids = p.fingerprint.get("extensions", []) if p.fingerprint else []
    return _ads_response(True, user_id=user_id, extensions=ext_ids)


# ---------------------------------------------------------------------------
# Groups
# ---------------------------------------------------------------------------


@router.get("/group/list")
def group_list() -> Dict[str, Any]:
    """Return all unique group_ids with profile counts."""
    assert _store is not None
    profiles = _store.list()
    groups: Dict[str, int] = {}
    for p in profiles:
        gid = p.group_id or "0"
        groups[gid] = groups.get(gid, 0) + 1
    group_list = [{"group_id": gid, "count": cnt} for gid, cnt in sorted(groups.items())]
    return _ads_response(True, list=group_list, total=len(group_list))


# ---------------------------------------------------------------------------
# Geo matching (timezone / locale / geolocation)
# ---------------------------------------------------------------------------


class GeoMatchRequest(BaseModel):
    country: Optional[str] = None  # ISO code; if omitted, derived from the proxy


@router.get("/geo/countries")
def geo_countries() -> Dict[str, Any]:
    """List ISO country codes the geo matcher can align a profile to."""
    return _ads_response(True, countries=supported_countries())


@router.post("/user/{user_id}/geo/match")
def user_geo_match(user_id: str, body: GeoMatchRequest) -> Dict[str, Any]:
    """Align a profile's timezone/locale/languages/geolocation to a country
    (explicit ``country``) or to its proxy's exit country."""
    assert _store is not None
    from dataclasses import fields as dc_fields
    p = _store.get(user_id)
    if p is None:
        raise HTTPException(status_code=404, detail="user_id not found")
    valid = {f.name for f in dc_fields(Fingerprint)}
    fp = Fingerprint(**{k: v for k, v in (p.fingerprint or {}).items() if k in valid})
    if body.country:
        geo = geo_for_country(body.country)
    else:
        geo = geo_from_proxy(p.proxy)
        if geo is None:
            raise HTTPException(
                status_code=400,
                detail="no country given and proxy has no country to derive from",
            )
    apply_geo_to_fingerprint(fp, geo)
    _store.update(user_id, fingerprint=fp)
    return _ads_response(True, user_id=user_id, country=geo.country, timezone=geo.timezone,
                         locale=geo.locale, latitude=geo.latitude, longitude=geo.longitude)


# ---------------------------------------------------------------------------
# Proxy pool rotation
# ---------------------------------------------------------------------------


class ProxyPoolNext(BaseModel):
    proxy_list: str
    strategy: str = "round_robin"  # sticky | round_robin | random
    user_id: Optional[str] = None  # if set, assign the chosen proxy to this profile


@router.post("/proxy/pool/next")
def proxy_pool_next(body: ProxyPoolNext) -> Dict[str, Any]:
    """Pick the next proxy from a pool (rotation strategy) and optionally assign
    it to a profile. Returns the chosen proxy."""
    try:
        pool = ProxyPool.from_list_text(body.proxy_list, strategy=body.strategy)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    chosen = pool.next_proxy()
    if chosen is None:
        raise HTTPException(status_code=400, detail="no live proxy in the pool")
    proxy_dict = adspower_shape(chosen)
    assigned = False
    if body.user_id:
        assert _store is not None
        try:
            _store.update(body.user_id, proxy=proxy_dict)
            assigned = True
        except KeyError:
            raise HTTPException(status_code=404, detail="user_id not found")
    return _ads_response(True, proxy=proxy_dict, assigned=assigned,
                         server=f"{chosen.type}://{chosen.host}:{chosen.port}")


# ---------------------------------------------------------------------------
# Portable profile export / import (.antq)
# ---------------------------------------------------------------------------


class PortableImport(BaseModel):
    bundle: Dict[str, Any]
    name: Optional[str] = None
    user_id: Optional[str] = None


@router.post("/user/{user_id}/export/portable")
def user_export_portable(user_id: str) -> Dict[str, Any]:
    """Export a profile as a portable .antq bundle (fingerprint+proxy+cookies+tags)."""
    assert _store is not None
    p = _store.get(user_id)
    if p is None:
        raise HTTPException(status_code=404, detail="user_id not found")
    return _ads_response(True, bundle=build_bundle(p))


@router.post("/user/import/portable")
def user_import_portable(body: PortableImport) -> Dict[str, Any]:
    """Import a profile from a portable .antq bundle dict."""
    assert _store is not None
    try:
        p = portable_import(_store, body.bundle, name=body.name, user_id=body.user_id)
    except PortableBundleError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return _ads_response(True, user_id=p.user_id, name=p.name, cookie_count=len(p.cookies))


# ---------------------------------------------------------------------------
# Stealth self-test scoring
# ---------------------------------------------------------------------------


class DetectScore(BaseModel):
    signals: Dict[str, Any]
    expected: Optional[Dict[str, Any]] = None


@router.post("/detect/score")
def detect_score(body: DetectScore) -> Dict[str, Any]:
    """Score a collected signals dict (from the detect collector script) into a
    graded stealth report. Pure scoring — no browser needed."""
    report = score_report(body.signals, expected=body.expected)
    return _ads_response(True, **report.to_dict())


# ---------------------------------------------------------------------------
# Browser engines
# ---------------------------------------------------------------------------


@router.get("/engine/list")
def engine_list() -> Dict[str, Any]:
    """List available browser engines (for the UI engine picker)."""
    return _ads_response(True, list=[e.to_dict() for e in list_engines()], total=len(engine_keys()))


# ---------------------------------------------------------------------------
# CDP proxy endpoints
# ---------------------------------------------------------------------------


@router.get("/json/version")
def cdp_version() -> Dict[str, Any]:
    assert _cdp is not None
    return _cdp.version_payload()


@router.get("/json/list")
async def cdp_list(user_id: Optional[str] = Query(None)) -> Dict[str, Any]:
    assert _cdp is not None
    if user_id:
        targets = await _cdp.list_targets(user_id)
        return {"targets": targets}
    return {"targets": _cdp.list_payload()}


@router.get("/json/new/{user_id}")
async def cdp_new(user_id: str, url: str = "about:blank") -> Dict[str, Any]:
    assert _cdp is not None
    session = await _cdp.open_new_page(user_id, url=url)
    if session is None:
        raise HTTPException(status_code=404, detail="user_id not running")
    return {
        "id": session.target_id,
        "type": "page",
        "title": "",
        "url": url,
        "webSocketDebuggerUrl": _cdp._ws_url(user_id, session.target_id),
    }


@router.websocket("/devtools/page/{user_id}/{target_id}")
async def cdp_ws(ws: WebSocket, user_id: str, target_id: str):
    assert _cdp is not None
    sessions = _cdp._pages.get(user_id, [])
    target = next((s for s in sessions if s.target_id == target_id), None)
    if target is None:
        await ws.close(code=4404)
        return
    await ws.accept()
    try:
        while True:
            msg = await ws.receive_text()
            await ws.send_text(msg)
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Diagnostics
# ---------------------------------------------------------------------------


@router.get("/info")
def info() -> Dict[str, Any]:
    assert _store is not None and _launcher is not None
    profiles = _store.list()
    running = _launcher.list_running()
    return {
        "service": "antique",
        "version": "0.2.0",
        "profile_count": len(profiles),
        "running_count": len(running),
        "running": [h.user_id for h in running],
    }