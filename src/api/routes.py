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
from ..core.operations import list_activity, record_activity, preview_backup, create_from_template, encrypted_snapshot, decrypt_snapshot
from ..core.providers import ProviderConfig, ProxyProvider, list_provider_kinds


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
    account_status: Optional[str] = None
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
    account_status: Optional[str] = None


class UserDelete(BaseModel):
    user_id: str


class UserClone(BaseModel):
    user_id: str
    name: Optional[str] = None
    user_id_override: Optional[str] = None


class BulkStatusUpdate(BaseModel):
    user_ids: List[str]
    account_status: str


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


class TemplateCreateRequest(BaseModel):
    template: Dict[str, Any]
    count: int = Field(default=1, ge=1, le=1000)
    seed: Optional[str] = None


class SnapshotRequest(BaseModel):
    path: str
    password: str
    overwrite: bool = False


class ProviderRequest(BaseModel):
    name: str
    kind: str = "file"
    source: str
    enabled: bool = True


class GroupRequest(BaseModel):
    group_id: str
    name: str
    sort_order: int = 0


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


class BulkFingerprintRandomize(BaseModel):
    user_ids: List[str]
    os_family: str = "windows"
    shared_fields: List[str] = Field(default_factory=list)
    preserve_fields: List[str] = Field(default_factory=lambda: ["engine", "extensions"])
    seed: Optional[str] = None


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
        "account_status": p.account_status,
        "user_proxy_config": p.proxy,
        "fingerprint_config": p.fingerprint,
        "cookies": p.cookies,
        "status": "Active" if p.running_debug_port else "Inactive",
        "debug_port": p.running_debug_port,
        "ws_endpoint": p.running_ws,
    }


def _ads_response(success: bool, **data: Any) -> Dict[str, Any]:
    return {"code": 0 if success else 1, "msg": "success" if success else "error", "data": data}


def _fingerprint_with_patch(raw: Optional[Dict[str, Any]], base: Optional[Dict[str, Any]] = None) -> Fingerprint:
    """Merge a partial UI/API patch onto a full coherent fingerprint.

    Previously ``{"browser_engine": "chromium"}`` constructed a Fingerprint
    with empty UA/noise/fonts. Editing one field also reset every omitted field
    to dataclass defaults. Both behaviours could break profile launch.
    """
    from dataclasses import fields as dc_fields
    valid = {f.name for f in dc_fields(Fingerprint)}
    merged = generate_fingerprint().canonical() if base is None else dict(base)
    merged.update({k: v for k, v in (raw or {}).items() if k in valid})
    return Fingerprint(**{k: v for k, v in merged.items() if k in valid})


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------


@router.get("/health")
def health() -> Dict[str, Any]:
    return {"status": "ok", "service": "antique", "version": "0.6.0"}


# ---------------------------------------------------------------------------
# Profiles
# ---------------------------------------------------------------------------


@router.post("/user/create")
def user_create(body: UserCreate) -> Dict[str, Any]:
    assert _store is not None
    fp = _fingerprint_with_patch(body.fingerprint_config)
    p = _store.create(
        name=body.name,
        group_id=body.group_id,
        proxy=body.user_proxy_config or {},
        fingerprint=fp,
        cookies=body.cookies or [],
        tags=body.tags or [],
        remark=body.remark or "",
        account_status=body.account_status or "new",
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
    existing = _store.get(body.user_id)
    if existing is None:
        raise HTTPException(status_code=404, detail="user_id not found")
    fp = _fingerprint_with_patch(body.fingerprint_config, existing.fingerprint) if body.fingerprint_config is not None else None
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
            account_status=body.account_status,
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
    account_status: Optional[str] = Query(None),
    sort_by: str = Query("name", pattern="^(name|id|user_id|group|status|tags|launches|cookies|created|updated|last_launched|proxy|engine|live)$"),
    sort_order: str = Query("asc", pattern="^(asc|desc)$"),
) -> Dict[str, Any]:
    assert _store is not None
    profiles = _store.list(group_id=group_id, tag=tag, search=search, account_status=account_status, sort_by=sort_by, sort_order=sort_order)
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
        sort_by=sort_by,
        sort_order=sort_order,
    )


@router.post("/user/clone")
def user_clone(body: UserClone) -> Dict[str, Any]:
    """Clone metadata, fingerprint, proxy, cookies and tags into a new profile."""
    assert _store is not None
    source = _store.get(body.user_id)
    if source is None:
        raise HTTPException(status_code=404, detail="user_id not found")
    from .routes import _fingerprint_with_patch
    fp = _fingerprint_with_patch(source.fingerprint)
    try:
        clone = _store.create(
            name=body.name or f"{source.name} copy",
            group_id=source.group_id,
            proxy=dict(source.proxy),
            fingerprint=fp,
            cookies=list(source.cookies),
            tags=list(source.tags),
            remark=source.remark,
            account_status="new",
            user_id=body.user_id_override,
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    return _ads_response(True, user_id=clone.user_id, name=clone.name, source_user_id=body.user_id)


@router.post("/user/template/create")
def user_template_create(body: TemplateCreateRequest) -> Dict[str, Any]:
    assert _store is not None
    try:
        profiles = create_from_template(_store, body.template, body.count, seed=body.seed)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return _ads_response(True, created_count=len(profiles), user_ids=[p.user_id for p in profiles])


@router.post("/user/snapshot/export")
def snapshot_export(body: SnapshotRequest) -> Dict[str, Any]:
    assert _store is not None
    try:
        out = encrypted_snapshot(_store, Path(body.path), body.password)
    except (ValueError, RuntimeError, OSError) as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return _ads_response(True, path=str(out))


@router.post("/user/snapshot/import")
def snapshot_import(body: SnapshotRequest) -> Dict[str, Any]:
    assert _store is not None
    try:
        result = decrypt_snapshot(_store, Path(body.path), body.password, overwrite=body.overwrite)
    except (ValueError, RuntimeError, OSError) as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return _ads_response(True, **result)


@router.get("/proxy/providers/kinds")
def proxy_provider_kinds() -> Dict[str, Any]:
    return _ads_response(True, kinds=list_provider_kinds())


@router.post("/proxy/providers/test")
def proxy_provider_test(body: ProviderRequest) -> Dict[str, Any]:
    try:
        values = ProxyProvider(ProviderConfig(body.name, body.kind, body.source, body.enabled)).fetch()
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return _ads_response(True, provider=body.name, count=len(values), proxies=values)


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
    try:
        handle = await _launcher.start(p, debug_port=body.debug_port)
    except Exception as exc:
        log.exception("profile launch failed: %s", p.user_id)
        message = str(exc).strip() or exc.__class__.__name__
        raise HTTPException(
            status_code=422,
            detail=f"Could not start profile {p.user_id}: {message}",
        )
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


@router.post("/user/import/backup/preview")
def user_import_backup_preview(body: BackupImportRequest) -> Dict[str, Any]:
    try:
        return _ads_response(True, **preview_backup(Path(body.source_path)))
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))


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


@router.post("/user/bulk/status")
def user_bulk_status(body: BulkStatusUpdate) -> Dict[str, Any]:
    assert _store is not None
    results = []
    for uid in body.user_ids:
        try:
            _store.update(uid, account_status=body.account_status)
            results.append({"user_id": uid, "ok": True})
        except KeyError:
            results.append({"user_id": uid, "ok": False, "error": "not found"})
    return _ads_response(True, results=results, updated_count=sum(1 for r in results if r["ok"]))


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


@router.post("/user/bulk/fingerprint/randomize")
def user_bulk_fingerprint_randomize(body: BulkFingerprintRandomize) -> Dict[str, Any]:
    """Randomize selected profiles while optionally sharing or preserving groups."""
    assert _store is not None
    from ..core.fingerprint_ops import randomize_batch
    existing: Dict[str, Dict[str, Any]] = {}
    missing: List[str] = []
    for uid in body.user_ids:
        profile = _store.get(uid)
        if profile is None:
            missing.append(uid)
        else:
            existing[uid] = profile.fingerprint or {}
    try:
        generated = randomize_batch(
            existing,
            os_family=body.os_family,
            shared_fields=body.shared_fields,
            preserve_fields=body.preserve_fields,
            seed=body.seed,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    for uid, fp in generated.items():
        _store.update(uid, fingerprint=fp)
    return _ads_response(
        True,
        updated_count=len(generated),
        user_ids=list(generated),
        missing=missing,
        shared_fields=body.shared_fields,
        preserved_fields=body.preserve_fields,
    )


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


@router.get("/activity")
def activity_list(user_id: Optional[str] = Query(None), limit: int = Query(100, ge=1, le=1000)) -> Dict[str, Any]:
    assert _store is not None
    events = list_activity(_store, user_id=user_id, limit=limit)
    return _ads_response(True, events=[{"user_id": e.user_id, "action": e.action, "detail": e.detail, "created_at": e.created_at} for e in events])


@router.get("/resource/status")
def resource_status() -> Dict[str, Any]:
    assert _launcher is not None
    import os
    return _ads_response(True, running=len(_launcher.list_running()), process_count=len(_launcher.list_running()), pid=os.getpid())


@router.get("/mcp/status")
def mcp_status() -> Dict[str, Any]:
    return _ads_response(True, transport="stdio", status="available", tools="browser profile automation")


@router.post("/group/create")
def group_create(body: GroupRequest) -> Dict[str, Any]:
    assert _store is not None
    from ..core.storage import GroupRecord
    from sqlmodel import Session
    with Session(_store.engine) as s:
        if s.get(GroupRecord, body.group_id):
            raise HTTPException(status_code=409, detail="group already exists")
        s.add(GroupRecord(group_id=body.group_id, name=body.name, sort_order=body.sort_order)); s.commit()
    return _ads_response(True, group_id=body.group_id, name=body.name)


@router.post("/group/update")
def group_update(body: GroupRequest) -> Dict[str, Any]:
    assert _store is not None
    from ..core.storage import GroupRecord
    from sqlmodel import Session
    with Session(_store.engine) as s:
        row = s.get(GroupRecord, body.group_id)
        if not row: raise HTTPException(status_code=404, detail="group not found")
        row.name, row.sort_order = body.name, body.sort_order; s.add(row); s.commit()
    return _ads_response(True, group_id=body.group_id, name=body.name)


@router.post("/group/delete")
def group_delete(group_id: str = Body(..., embed=True)) -> Dict[str, Any]:
    assert _store is not None
    from ..core.storage import GroupRecord
    from sqlmodel import Session
    with Session(_store.engine) as s:
        row = s.get(GroupRecord, group_id)
        if not row: raise HTTPException(status_code=404, detail="group not found")
        s.delete(row); s.commit()
    return _ads_response(True, group_id=group_id, deleted=True)


@router.get("/group/list")
def group_list() -> Dict[str, Any]:
    """Return all unique groups with profile counts."""
    assert _store is not None
    from ..core.storage import GroupRecord
    from sqlmodel import Session, select
    
    profiles = _store.list()
    counts: Dict[str, int] = {}
    for p in profiles:
        gid = p.group_id or "0"
        counts[gid] = counts.get(gid, 0) + 1
        
    with Session(_store.engine) as s:
        groups = s.exec(select(GroupRecord)).all()
        
    group_list = []
    has_default = False
    for g in groups:
        if g.group_id == "0":
            has_default = True
        group_list.append({
            "group_id": g.group_id,
            "name": g.name,
            "sort_order": g.sort_order,
            "count": counts.get(g.group_id, 0)
        })
        
    if not has_default:
        group_list.append({
            "group_id": "0",
            "name": "Default",
            "sort_order": 0,
            "count": counts.get("0", 0)
        })
        
    group_list.sort(key=lambda x: (x["sort_order"], x["name"]))
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
# Account status (multi-account lifecycle)
# ---------------------------------------------------------------------------

ACCOUNT_STATUSES = ["new", "warming", "active", "limited", "banned", "retired"]


class StatusUpdate(BaseModel):
    account_status: str


@router.get("/status/list")
def status_list() -> Dict[str, Any]:
    """Preset account-status values (the UI offers these; field is free-form)."""
    return _ads_response(True, statuses=ACCOUNT_STATUSES)


@router.post("/user/{user_id}/status")
def user_set_status(user_id: str, body: StatusUpdate) -> Dict[str, Any]:
    """Set a profile's account status (e.g. active/banned/warming)."""
    assert _store is not None
    try:
        p = _store.update(user_id, account_status=body.account_status)
    except KeyError:
        raise HTTPException(status_code=404, detail="user_id not found")
    return _ads_response(True, user_id=user_id, account_status=p.account_status)


# ---------------------------------------------------------------------------
# Live View + real per-profile CDP
# ---------------------------------------------------------------------------


@router.post("/user/{user_id}/screenshot")
async def user_screenshot(user_id: str, full_page: bool = Query(False)) -> Dict[str, Any]:
    """Live View: return a base64 PNG of the running profile's active page."""
    assert _launcher is not None
    if not _launcher.is_running(user_id):
        raise HTTPException(status_code=409, detail="profile is not running")
    import base64
    buf = await _launcher.screenshot(user_id, full_page=full_page)
    if buf is None:
        raise HTTPException(status_code=409, detail="profile is not running")
    return _ads_response(True, user_id=user_id, base64_png=base64.b64encode(buf).decode())


@router.get("/user/{user_id}/cdp")
def user_cdp(user_id: str) -> Dict[str, Any]:
    """Return the REAL Chrome DevTools endpoint for a running Chromium profile.

    Reads Chromium's own ``/json/version`` on the profile's debug port. Use
    the returned ``webSocketDebuggerUrl`` to attach Selenium/Puppeteer/CDP.
    """
    assert _launcher is not None
    if not _launcher.is_running(user_id):
        raise HTTPException(status_code=409, detail="profile is not running")
    info = _launcher.real_cdp_info(user_id)
    if info is None:
        raise HTTPException(status_code=502, detail="CDP endpoint not available (non-Chromium engine or port not ready)")
    return _ads_response(True, **info)


# ---------------------------------------------------------------------------
# Synchronized multi-profile automation (sync groups)
# ---------------------------------------------------------------------------


class SyncRun(BaseModel):
    user_ids: List[str]
    flow: Any                       # list of step dicts, or {"steps": [...]}
    stop_on_error: bool = False
    max_concurrency: int = 0


@router.post("/sync/run")
async def sync_run(body: SyncRun) -> Dict[str, Any]:
    """Run one automation flow across many running profiles concurrently.

    Profiles must already be started (``/user/start``). Non-running or missing
    profiles come back as failed entries rather than aborting the batch.
    """
    assert _launcher is not None
    from ..core.automation import parse_flow, FlowValidationError
    from ..core.sync import run_sync
    try:
        steps = parse_flow(body.flow)
    except FlowValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    async def _page_for(uid: str):
        handle = _launcher.get_handle(uid)
        if handle is None:
            raise RuntimeError("profile is not running")
        return await _launcher._active_page(handle)

    report = await run_sync(
        body.user_ids, steps, _page_for,
        stop_on_error=body.stop_on_error, max_concurrency=body.max_concurrency,
    )
    return _ads_response(True, **report.to_dict())


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
        "version": "0.6.0",
        "profile_count": len(profiles),
        "running_count": len(running),
        "running": [h.user_id for h in running],
    }