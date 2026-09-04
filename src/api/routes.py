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

import hmac
import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Body, File, HTTPException, Query, UploadFile, WebSocket

from .. import __version__
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
from ..core.operations import list_activity, record_activity, preview_backup, create_from_template, encrypted_snapshot, decrypt_snapshot, export_activity
from ..core.providers import ProviderConfig, ProxyProvider, list_provider_kinds
from ..core.backup_scheduler import add_schedule, list_schedules, run_schedule
from ..core import notify, rotation
from ..core.ssh_tunnel import SSHTunnelManager
from ..core.mcp_manager import get_mcp_manager


log = logging.getLogger("antique.api")
router = APIRouter()

# These are wired in by server.py at startup
_store: Optional[ProfileStore] = None
_launcher: Optional[BrowserLauncher] = None
_cdp: Optional[CDPProxy] = None
_ext_store: Optional[ExtensionStore] = None

# One SSH tunnel per profile, shared process-wide. It keeps no on-disk state,
# so it is created eagerly rather than wired in by server.py.
_ssh_tunnels = SSHTunnelManager()


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
    # Optional digital portrait (age/gender/occupation/income/country/device).
    # Any omitted field is filled coherently by the persona generator, and the
    # resulting persona drives locale, timezone, hardware, screen and fonts.
    persona: Optional[Dict[str, Any]] = None


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
    # Vendor pools (brightdata/decodo/smartproxy) authenticate with a bearer
    # token. It may also come from the matching *_API_KEY env var, so it stays
    # optional here and is never echoed back in responses.
    api_key: Optional[str] = None
    username: Optional[str] = None
    password: Optional[str] = None
    params: Optional[Dict[str, str]] = None


class DueDateRequest(BaseModel):
    """Reminder date for one profile. ``None``/empty clears it.

    Kept as a string so an unparseable value yields a 400 from our own
    validation instead of a 422 from pydantic's datetime coercion.
    """

    due_date: Optional[str] = None


class WebhookSettingsRequest(BaseModel):
    url: str = ""
    kind: str = "generic"
    enabled: bool = False
    events: Optional[List[str]] = None
    telegram_chat_id: str = ""


class RotationScheduleRequest(BaseModel):
    interval_min: int
    enabled: bool = True


class ScheduleRequest(BaseModel):
    destination: str
    interval_minutes: int = Field(default=1440, ge=5)


class ScheduleRunRequest(BaseModel):
    schedule_id: str
    password: str


class GroupRequest(BaseModel):
    group_id: str
    name: str
    sort_order: int = 0
    parent_id: str = ""


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
    # Concrete field values applied after randomize/shared/preserve — they win.
    # Unknown Fingerprint field names are rejected with 400.
    overrides: Optional[Dict[str, Any]] = None


class WebRTCRequest(BaseModel):
    """Set one profile's WebRTC handling mode."""

    mode: str
    # Explicit public IP advertised in ICE candidates (proxy mode only).
    public_ip: Optional[str] = None
    # Derive the public IP from the profile's proxy exit instead of passing it.
    # Requires the profile to actually have a proxy configured (else 400).
    detect_from_proxy: bool = False


class BulkWebRTCRequest(BaseModel):
    """Set the WebRTC mode on many profiles at once."""

    user_ids: List[str]
    mode: str
    public_ip: Optional[str] = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _is_overdue(due_date, now: Optional[Any] = None) -> bool:
    """True when a reminder date has already passed. Pure."""
    if due_date is None:
        return False
    from datetime import datetime as _dt
    moment = now or _dt.utcnow()
    stamp = due_date.replace(tzinfo=None) if getattr(due_date, "tzinfo", None) else due_date
    return stamp <= moment


def _profile_to_adspower_shape(p) -> Dict[str, Any]:
    due = getattr(p, "due_date", None)
    # Mask proxy credentials to prevent credential leakage in API responses.
    # Both proxy_user and proxy_password are replaced with "****" when set,
    # or "" when absent — so the shape is preserved but secrets are hidden.
    proxy_safe = None
    if p.proxy:
        proxy_safe = dict(p.proxy) if isinstance(p.proxy, dict) else p.proxy
        if isinstance(proxy_safe, dict):
            proxy_safe = dict(proxy_safe)  # Ensure we don't mutate original
            if "proxy_password" in proxy_safe:
                proxy_safe["proxy_password"] = "****" if proxy_safe.get("proxy_password") else ""
            if "proxy_user" in proxy_safe:
                proxy_safe["proxy_user"] = "****" if proxy_safe.get("proxy_user") else ""
    return {
        "user_id": p.user_id,
        "name": p.name,
        "group_id": p.group_id,
        "due_date": due.isoformat() if due else None,
        "overdue": _is_overdue(due),
        "created_at": p.created_at.isoformat() if p.created_at else None,
        "updated_at": p.updated_at.isoformat() if p.updated_at else None,
        "last_launched_at": p.last_launched_at.isoformat() if p.last_launched_at else None,
        "launch_count": p.launch_count,
        "remark": p.remark,
        "tags": p.tags,
        "account_status": p.account_status,
        "user_proxy_config": proxy_safe,
        "fingerprint_config": p.fingerprint,
        # Session cookies are credentials — never serialize in list views.
        # Count + has flag only; the blob itself is served by /user/{id}/cookies.
        "cookies_count": len(p.cookies) if isinstance(p.cookies, list) else (1 if p.cookies else 0),
        "has_cookies": bool(p.cookies),
        "status": "Active" if p.running_debug_port else "Inactive",
        "debug_port": p.running_debug_port,
        "ws_endpoint": p.running_ws,
    }


def _ads_response(success: bool, **data: Any) -> Dict[str, Any]:
    return {"code": 0 if success else 1, "msg": "success" if success else "error", "data": data}


_PERSONA_KEYS = ("age", "gender", "occupation", "income_bracket", "country", "device_type", "seed")


def _persona_kwargs(raw: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Filter a raw persona dict down to ``generate_persona`` keyword args.

    Unknown keys are dropped rather than raising, so a UI can post the whole
    persona object back (including derived/display-only fields) unchanged.
    ``None`` values are dropped too — the generator fills those coherently.
    """
    data = dict(raw or {})
    return {k: data[k] for k in _PERSONA_KEYS if data.get(k) is not None}


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
    return {"status": "ok", "service": "antique", "version": __version__}


# ---------------------------------------------------------------------------
# Profiles
# ---------------------------------------------------------------------------


@router.post("/user/create")
def user_create(body: UserCreate) -> Dict[str, Any]:
    assert _store is not None
    persona_out: Optional[Dict[str, Any]] = None

    if body.persona is not None:
        # A persona drives the whole fingerprint: generate from the portrait,
        # then let any explicit fingerprint_config patch win on top.
        from ..core.persona import generate_with_persona, generate_persona, persona_to_dict

        try:
            portrait = generate_persona(**_persona_kwargs(body.persona))
        except (TypeError, ValueError) as exc:
            raise HTTPException(status_code=400, detail=f"invalid persona: {exc}")
        fp_obj, portrait = generate_with_persona(portrait)
        fp = _fingerprint_with_patch(body.fingerprint_config, fp_obj.canonical())
        persona_out = persona_to_dict(portrait)
    else:
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
    record_activity(_store, p.user_id, "create", {"name": p.name, "group_id": p.group_id})
    payload: Dict[str, Any] = {
        "id": p.user_id,
        "user_id": p.user_id,
        "name": p.name,
    }
    # Only present when a persona was requested — callers that don't use
    # personas see the exact response shape they saw before.
    if persona_out is not None:
        payload["persona"] = persona_out
    return _ads_response(True, **payload)


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
    record_activity(_store, p.user_id, "update", {"name": p.name})
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
    remark: Optional[str] = Query(None, description="Substring filter on the profile note/remark."),
    sort_by: str = Query("name", pattern="^(name|id|user_id|group|status|tags|launches|cookies|created|updated|last_launched|proxy|engine|live)$"),
    sort_order: str = Query("asc", pattern="^(asc|desc)$"),
) -> Dict[str, Any]:
    assert _store is not None
    profiles = _store.list(group_id=group_id, tag=tag, search=search, account_status=account_status, remark=remark, sort_by=sort_by, sort_order=sort_order)
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


@router.get("/user/reminders")
def user_reminders(
    only_overdue: bool = Query(False),
    limit: int = Query(200, ge=1, le=1000),
) -> Dict[str, Any]:
    """Profiles with a due date, soonest first. Overdue ones therefore lead."""
    assert _store is not None
    from datetime import datetime as _dt
    now = _dt.utcnow()
    dated = [p for p in _store.list() if getattr(p, "due_date", None) is not None]
    dated.sort(key=lambda p: p.due_date.replace(tzinfo=None) if p.due_date.tzinfo else p.due_date)
    overdue_count = sum(1 for p in dated if _is_overdue(p.due_date, now))
    selected = [p for p in dated if _is_overdue(p.due_date, now)] if only_overdue else dated
    sliced = selected[:limit]
    return _ads_response(
        True,
        list=[_profile_to_adspower_shape(p) for p in sliced],
        total=len(selected),
        overdue_count=overdue_count,
        only_overdue=only_overdue,
    )


@router.post("/user/{user_id}/due-date")
def user_set_due_date(user_id: str, body: DueDateRequest) -> Dict[str, Any]:
    """Set (or clear, with ``due_date: null``) a profile's reminder date."""
    assert _store is not None
    parsed = None
    if body.due_date is not None:
        raw = body.due_date.strip()
        if raw:
            from datetime import datetime as _dt
            try:
                parsed = _dt.fromisoformat(raw.replace("Z", "+00:00"))
            except ValueError:
                raise HTTPException(
                    status_code=400,
                    detail=f"due_date must be an ISO-8601 date or datetime, got {body.due_date!r}",
                )
            if parsed.tzinfo is not None:
                parsed = parsed.replace(tzinfo=None)
    try:
        p = _store.set_due_date(user_id, parsed)
    except KeyError:
        raise HTTPException(status_code=404, detail="user_id not found")
    record_activity(_store, user_id, "due_date", {"due_date": parsed.isoformat() if parsed else None})
    return _ads_response(
        True,
        user_id=p.user_id,
        due_date=p.due_date.isoformat() if p.due_date else None,
        overdue=_is_overdue(p.due_date),
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


@router.post("/backup/schedules")
def backup_schedule_create(body: ScheduleRequest) -> Dict[str, Any]:
    assert _store is not None
    try: item = add_schedule(_store, body.destination, body.interval_minutes)
    except ValueError as exc: raise HTTPException(status_code=400, detail=str(exc))
    return _ads_response(True, schedule=item.__dict__)


@router.get("/backup/schedules")
def backup_schedule_list() -> Dict[str, Any]:
    assert _store is not None
    return _ads_response(True, schedules=[x.__dict__ for x in list_schedules(_store)])


@router.post("/backup/schedules/run")
def backup_schedule_run(body: ScheduleRunRequest) -> Dict[str, Any]:
    assert _store is not None
    try: item = run_schedule(_store, body.schedule_id, body.password)
    except (KeyError, ValueError, RuntimeError, OSError) as exc: raise HTTPException(status_code=400, detail=str(exc))
    return _ads_response(True, schedule=item)


@router.get("/proxy/providers/kinds")
def proxy_provider_kinds() -> Dict[str, Any]:
    return _ads_response(True, kinds=list_provider_kinds())


@router.post("/proxy/providers/test")
def proxy_provider_test(body: ProviderRequest) -> Dict[str, Any]:
    try:
        values = ProxyProvider(
            ProviderConfig(
                name=body.name,
                kind=body.kind,
                source=body.source,
                enabled=body.enabled,
                api_key=body.api_key,
                username=body.username,
                password=body.password,
                params=body.params,
            )
        ).fetch()
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return _ads_response(True, provider=body.name, count=len(values), proxies=values)


# ---------------------------------------------------------------------------
# Webhook settings, proxy rotation schedules, SSH tunnels
# ---------------------------------------------------------------------------


def _data_root() -> Path:
    """Where per-install JSON settings live (webhooks, rotation schedules)."""
    if _launcher is not None and getattr(_launcher, "data_root", None):
        return Path(_launcher.data_root)
    return Path(os.environ.get("ANTIQUE_DATA_DIR", "data"))


@router.get("/settings/webhook")
def webhook_settings_get() -> Dict[str, Any]:
    return _ads_response(True, **notify.load_config(_data_root()).to_dict())


@router.post("/settings/webhook")
def webhook_settings_set(body: WebhookSettingsRequest) -> Dict[str, Any]:
    cfg = notify.WebhookConfig(
        url=body.url,
        kind=body.kind,
        enabled=body.enabled,
        events=list(body.events) if body.events is not None else list(notify.EVENTS),
        telegram_chat_id=body.telegram_chat_id,
    )
    try:
        notify.save_config(_data_root(), cfg)
    except notify.WebhookError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except OSError as exc:
        raise HTTPException(status_code=500, detail=f"could not persist webhook settings: {exc}")
    return _ads_response(True, **cfg.to_dict())


@router.post("/settings/webhook/test")
def webhook_settings_test() -> Dict[str, Any]:
    """Deliver one synthetic event using the stored config. Never raises."""
    cfg = notify.load_config(_data_root())
    result = notify.send_event(cfg, "profile_start", {"name": "webhook test", "detail": "manual test"})
    return _ads_response(True, **result)


def _schedule_shape(schedule: rotation.RotationSchedule, now=None) -> Dict[str, Any]:
    upcoming = rotation.next_run_at(schedule)
    return {
        **schedule.to_dict(),
        "next_run_at": upcoming.isoformat() if upcoming else None,
        "due": rotation.is_due(schedule, now),
    }


@router.get("/proxy/rotation/schedules")
def rotation_schedule_list() -> Dict[str, Any]:
    from datetime import datetime as _dt
    now = _dt.utcnow()
    schedules = rotation.load_schedules(_data_root())
    return _ads_response(
        True,
        list=[_schedule_shape(s, now) for s in schedules],
        total=len(schedules),
        due_count=len(rotation.due_schedules(schedules, now)),
    )


@router.post("/proxy/pool/{pool_id}/schedule")
def rotation_schedule_upsert(pool_id: str, body: RotationScheduleRequest) -> Dict[str, Any]:
    schedule = rotation.RotationSchedule(
        pool_id=pool_id, interval_min=body.interval_min, enabled=body.enabled
    )
    try:
        rotation.upsert_schedule(_data_root(), schedule)
    except rotation.RotationScheduleError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except OSError as exc:
        raise HTTPException(status_code=500, detail=f"could not persist schedule: {exc}")
    return _ads_response(True, schedule=_schedule_shape(schedule))


@router.delete("/proxy/pool/{pool_id}/schedule")
def rotation_schedule_delete(pool_id: str) -> Dict[str, Any]:
    if not rotation.remove_schedule(_data_root(), pool_id):
        raise HTTPException(status_code=404, detail=f"no rotation schedule for pool {pool_id!r}")
    return _ads_response(True, pool_id=pool_id, deleted=True)


@router.post("/proxy/rotation/run-due")
def rotation_run_due() -> Dict[str, Any]:
    """Stamp every due schedule as rotated and report which pools fired."""
    root = _data_root()
    due = rotation.due_schedules(rotation.load_schedules(root))
    rotated: List[str] = []
    for schedule in due:
        if rotation.mark_ran(root, schedule.pool_id) is not None:
            rotated.append(schedule.pool_id)
    return _ads_response(True, rotated=rotated, count=len(rotated))


@router.get("/proxy/ssh/tunnels")
def ssh_tunnels_list() -> Dict[str, Any]:
    active = _ssh_tunnels.active
    return _ads_response(
        True,
        list=[{"key": key, "local_port": port, "proxy_type": "socks5", "host": "127.0.0.1"}
              for key, port in sorted(active.items())],
        total=len(active),
    )


@router.post("/proxy/ssh/tunnels/{key}/close")
def ssh_tunnel_close(key: str) -> Dict[str, Any]:
    if not _ssh_tunnels.close(key):
        raise HTTPException(status_code=404, detail=f"no active ssh tunnel for {key!r}")
    return _ads_response(True, key=key, closed=True)


@router.post("/user/delete")
def user_delete(body: UserDelete) -> Dict[str, Any]:
    assert _store is not None
    ok = _store.delete(body.user_id)
    if ok:
        record_activity(_store, body.user_id, "delete")
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
    record_activity(_store, p.user_id, "start", {"debug_port": handle.debug_port})
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
    if ok and _store is not None:
        record_activity(_store, body.user_id, "stop")
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
    record_activity(_store, "*", "backup_import", {"source_path": body.source_path, "summary": summary})
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
def get_profile(user_id: str, include_cookies: bool = False) -> Dict[str, Any]:
    assert _store is not None
    p = _store.get(user_id)
    if p is None:
        raise HTTPException(status_code=404, detail="user_id not found")
    shape = _profile_to_adspower_shape(p)
    if include_cookies:
        # Explicit opt-in: the caller asks for the cookie blob (export tooling).
        shape["cookies"] = p.cookies
    return _ads_response(True, **shape)


# ---------------------------------------------------------------------------
# Migration center — per-profile migration state machine
# ---------------------------------------------------------------------------


class MigrationValidateRequest(BaseModel):
    source_path: str
    user_ids: Optional[List[str]] = None
    launch_sites: bool = False  # Ignored by default; never launches external sites


class MigrationRetryRequest(BaseModel):
    user_ids: List[str]


class MigrationRepairRequest(BaseModel):
    source_path: str
    user_ids: Optional[List[str]] = None


def _migration_mgr() -> "MigrationManager":
    assert _store is not None
    from ..core.migration import MigrationManager
    return MigrationManager(_store)


@router.get("/migration/status")
def migration_status(status: Optional[str] = Query(None)) -> Dict[str, Any]:
    """List migration state for all profiles, optionally filtered by status."""
    mgr = _migration_mgr()
    if status:
        from ..core.migration import MigrationStatus
        try:
            st = MigrationStatus(status)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"unknown status: {status}")
        records = mgr.list_by_status(st)
        items = [
            {
                "user_id": r.user_id,
                "status": r.status,
                "source_path": r.source_path,
                "detail": json.loads(r.detail) if r.detail else {},
                "created_at": r.created_at.isoformat() if r.created_at else None,
                "updated_at": r.updated_at.isoformat() if r.updated_at else None,
            }
            for r in records
        ]
    else:
        items = mgr.batch_status()
    return _ads_response(True, total=len(items), list=items)


@router.post("/migration/validate")
def migration_validate(body: MigrationValidateRequest) -> Dict[str, Any]:
    """Batch-validate source/cookie/storage/extension for profiles.

    Does **not** launch external sites by default. The ``launch_sites``
    parameter is accepted but site verification is never performed here.
    """
    mgr = _migration_mgr()
    results = mgr.batch_validate(Path(body.source_path), user_ids=body.user_ids)
    return _ads_response(True, results=results)


@router.post("/migration/retry")
def migration_retry(body: MigrationRetryRequest) -> Dict[str, Any]:
    """Retry failed migrations by resetting them to ``discovered``."""
    mgr = _migration_mgr()
    results = mgr.batch_retry(body.user_ids)
    return _ads_response(True, results=results)


@router.post("/migration/repair")
def migration_repair(body: MigrationRepairRequest) -> Dict[str, Any]:
    """Re-validate and repair migration state for profiles."""
    mgr = _migration_mgr()
    results = mgr.batch_repair(Path(body.source_path), user_ids=body.user_ids)
    return _ads_response(True, results=results)


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
    record_activity(_store, "*", "bulk_status", {"status": body.account_status, "updated_count": len([r for r in results if r["ok"]])})
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
            overrides=body.overrides,
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
        overrides=body.overrides or {},
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


@router.get("/extension/webstore/search")
def extension_webstore_search(
    q: str = Query(..., min_length=1, description="Chrome Web Store search text."),
    limit: int = Query(20, ge=1, le=50),
) -> Dict[str, Any]:
    """Search the Chrome Web Store for installable extensions.

    Results carry the ``webstore_id`` you can hand straight to
    ``/extension/install`` with ``source_type="webstore"``.
    """
    assert _ext_store is not None
    try:
        results = _ext_store.search_webstore(q, limit=limit)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:  # network/HTTP failures — surface, never fake results
        raise HTTPException(status_code=502, detail=f"web store search failed: {exc}")
    return _ads_response(True, query=q, results=results, count=len(results))


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
def activity_list(user_id: Optional[str] = Query(None), action: Optional[str] = Query(None), limit: int = Query(100, ge=1, le=1000)) -> Dict[str, Any]:
    assert _store is not None
    events = list_activity(_store, user_id=user_id, action=action, limit=limit)
    return _ads_response(True, events=[{"user_id": e.user_id, "action": e.action, "detail": e.detail, "created_at": e.created_at} for e in events])


@router.post("/activity/export")
def activity_export(path: str = Body(..., embed=True), user_id: Optional[str] = Body(None, embed=True), action: Optional[str] = Body(None, embed=True)) -> Dict[str, Any]:
    assert _store is not None
    try:
        out = export_activity(_store, Path(path), user_id=user_id, action=action)
    except OSError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return _ads_response(True, path=str(out))


@router.get("/resource/status")
def resource_status() -> Dict[str, Any]:
    assert _launcher is not None
    import os, time
    running = []
    for handle in _launcher.list_running():
        running.append({"user_id": handle.user_id, "pid": handle.pid, "debug_port": handle.debug_port, "ws_endpoint": handle.ws_endpoint})
    rss_kb = user_cpu_s = system_cpu_s = None
    try:
        import psutil
        proc = psutil.Process(os.getpid())
        rss_kb = proc.memory_info().rss // 1024
        cpu = proc.cpu_times(); user_cpu_s, system_cpu_s = cpu.user, cpu.system
    except ImportError:
        try:
            import resource
            usage = resource.getrusage(resource.RUSAGE_SELF)
            rss_kb, user_cpu_s, system_cpu_s = usage.ru_maxrss, usage.ru_utime, usage.ru_stime
        except ImportError:
            pass
    return _ads_response(True, running_count=len(running), process_count=len(running), pid=os.getpid(), rss_kb=rss_kb, user_cpu_s=user_cpu_s, system_cpu_s=system_cpu_s, checked_at=time.time(), profiles=running)


# ---------------------------------------------------------------------------
# MCP server management
# ---------------------------------------------------------------------------


@router.get("/mcp/status")
def mcp_status() -> Dict[str, Any]:
    """Live state of the managed MCP subprocess plus its tool inventory."""
    mgr = get_mcp_manager()
    state = mgr.status()
    tools = mgr.tools_list()
    return _ads_response(True, **state.to_dict(), tools=tools, tool_count=len(tools))


@router.post("/mcp/start")
def mcp_start() -> Dict[str, Any]:
    """Start the MCP server subprocess (idempotent)."""
    state = get_mcp_manager().start()
    if not state.running:
        raise HTTPException(status_code=500, detail=state.error or "failed to start MCP server")
    return _ads_response(True, **state.to_dict())


@router.post("/mcp/stop")
def mcp_stop() -> Dict[str, Any]:
    """Stop the MCP server subprocess (no-op when already stopped)."""
    state = get_mcp_manager().stop()
    if state.error:
        raise HTTPException(status_code=500, detail=state.error)
    return _ads_response(True, **state.to_dict())


@router.get("/mcp/config")
def mcp_config(include_env: bool = Query(False)) -> Dict[str, Any]:
    """Return the client config snippet for Claude Desktop / Cursor / Windsurf."""
    mgr = get_mcp_manager()
    config = mgr.config_json(include_env=include_env)
    return _ads_response(True, config=config, transport="stdio", include_env=include_env)


@router.post("/group/create")
def group_create(body: GroupRequest) -> Dict[str, Any]:
    assert _store is not None
    from ..core.storage import GroupRecord
    from sqlmodel import Session
    with Session(_store.engine) as s:
        if s.get(GroupRecord, body.group_id):
            raise HTTPException(status_code=409, detail="group already exists")
        if body.parent_id and not s.get(GroupRecord, body.parent_id):
            raise HTTPException(status_code=400, detail="parent group not found")
        s.add(GroupRecord(group_id=body.group_id, name=body.name, sort_order=body.sort_order, parent_id=body.parent_id)); s.commit()
    return _ads_response(True, group_id=body.group_id, name=body.name)


@router.post("/group/update")
def group_update(body: GroupRequest) -> Dict[str, Any]:
    assert _store is not None
    from ..core.storage import GroupRecord
    from sqlmodel import Session
    with Session(_store.engine) as s:
        row = s.get(GroupRecord, body.group_id)
        if not row: raise HTTPException(status_code=404, detail="group not found")
        if body.parent_id and body.parent_id != body.group_id and not s.get(GroupRecord, body.parent_id):
            raise HTTPException(status_code=400, detail="parent group not found")
        row.name, row.sort_order, row.parent_id = body.name, body.sort_order, body.parent_id; s.add(row); s.commit()
    return _ads_response(True, group_id=body.group_id, name=body.name)


@router.post("/group/delete")
def group_delete(group_id: str = Body(..., embed=True)) -> Dict[str, Any]:
    assert _store is not None
    from ..core.storage import GroupRecord
    from sqlmodel import Session, select
    with Session(_store.engine) as s:
        row = s.get(GroupRecord, group_id)
        if not row: raise HTTPException(status_code=404, detail="group not found")
        if group_id == "0": raise HTTPException(status_code=400, detail="default group cannot be deleted")
        child = s.exec(select(GroupRecord).where(GroupRecord.parent_id == group_id)).first()
        if child: raise HTTPException(status_code=409, detail="move or delete child groups first")
        s.delete(row); s.commit()
    return _ads_response(True, group_id=group_id, deleted=True)


@router.get("/group/tree")
def group_tree() -> Dict[str, Any]:
    assert _store is not None
    from ..core.storage import GroupRecord
    from sqlmodel import Session, select
    with Session(_store.engine) as s:
        rows = s.exec(select(GroupRecord).order_by(GroupRecord.sort_order, GroupRecord.name)).all()
    by_parent: Dict[str, List[Dict[str, Any]]] = {}
    for row in rows:
        by_parent.setdefault(getattr(row, "parent_id", ""), []).append({"group_id": row.group_id, "name": row.name, "sort_order": row.sort_order, "parent_id": getattr(row, "parent_id", "")})
    return _ads_response(True, tree=by_parent, roots=by_parent.get("", []))


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
            "parent_id": getattr(g, "parent_id", ""),
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
    # Mask credentials in the response — never echo proxy_user/password.
    if proxy_dict.get("proxy_user"):
        proxy_dict["proxy_user"] = "****"
    if proxy_dict.get("proxy_password"):
        proxy_dict["proxy_password"] = "****"
    assigned = False
    if body.user_id:
        assert _store is not None
        try:
            _store.update(body.user_id, proxy=adspower_shape(chosen))
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


class BulkDetectScore(BaseModel):
    user_ids: List[str]


@router.get("/user/{user_id}/detect-score")
def user_detect_score(user_id: str) -> Dict[str, Any]:
    """Audit one stored profile's fingerprint and return a graded stealth report.

    Static analysis only — the profile does not need to be running.
    """
    assert _store is not None
    profile = _store.get(user_id)
    if profile is None:
        raise HTTPException(status_code=404, detail="user_id not found")
    from ..core.detect import score_fingerprint
    report = score_fingerprint(profile.fingerprint or {})
    return _ads_response(True, user_id=user_id, name=profile.name, **report.to_dict())


@router.get("/user/{user_id}/fingerprint/preview")
def user_fingerprint_preview(user_id: str) -> Dict[str, Any]:
    """Human-readable, grouped view of a stored fingerprint plus its audit report."""
    assert _store is not None
    profile = _store.get(user_id)
    if profile is None:
        raise HTTPException(status_code=404, detail="user_id not found")
    from ..core.detect import fingerprint_preview
    preview = fingerprint_preview(profile.fingerprint or {})
    return _ads_response(True, user_id=user_id, name=profile.name, **preview)


@router.post("/user/bulk/detect-score")
def user_bulk_detect_score(body: BulkDetectScore) -> Dict[str, Any]:
    """Audit many profiles at once and summarise the grade distribution."""
    assert _store is not None
    if not body.user_ids:
        raise HTTPException(status_code=400, detail="user_ids must not be empty")
    from ..core.detect import score_fingerprint
    profiles = []
    missing: List[str] = []
    for uid in body.user_ids:
        profile = _store.get(uid)
        if profile is None:
            missing.append(uid)
        else:
            profiles.append(profile)
    if missing:
        raise HTTPException(status_code=400, detail=f"unknown user_ids: {', '.join(missing)}")
    results: List[Dict[str, Any]] = []
    count_by_grade: Dict[str, int] = {}
    for profile in profiles:
        report = score_fingerprint(profile.fingerprint or {})
        data = report.to_dict()
        grade = data["grade"]
        count_by_grade[grade] = count_by_grade.get(grade, 0) + 1
        results.append({
            "user_id": profile.user_id,
            "name": profile.name,
            "score": data["score"],
            "grade": grade,
            "ok": data["ok"],
            "passed": data["passed"],
            "total": data["total"],
            "failures": data["failures"],
        })
    scores = [r["score"] for r in results]
    summary = {
        "count": len(results),
        "avg": round(sum(scores) / len(scores), 1) if scores else 0,
        "min": min(scores) if scores else 0,
        "max": max(scores) if scores else 0,
        "count_by_grade": count_by_grade,
        "failing": sum(1 for r in results if not r["ok"]),
    }
    record_activity(_store, "*", "bulk_detect_score", {"count": len(results), "avg": summary["avg"]})
    return _ads_response(True, results=results, summary=summary)


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
# Personas
# ---------------------------------------------------------------------------


@router.get("/persona/generate")
def persona_generate(
    age: Optional[int] = Query(None, ge=13, le=99),
    gender: Optional[str] = Query(None),
    occupation: Optional[str] = Query(None),
    income_bracket: Optional[str] = Query(None),
    country: Optional[str] = Query(None),
    device_type: Optional[str] = Query(None),
    seed: Optional[str] = Query(None),
    preview: bool = Query(False, description="also return the derived fingerprint"),
) -> Dict[str, Any]:
    """Generate a coherent persona; any omitted trait is filled by the generator.

    With ``preview=true`` the fingerprint derived from that persona is returned
    alongside it, so the dashboard can show what a profile would look like
    before actually creating it.
    """
    from ..core.persona import generate_persona, generate_with_persona, persona_to_dict

    try:
        portrait = generate_persona(**_persona_kwargs({
            "age": age,
            "gender": gender,
            "occupation": occupation,
            "income_bracket": income_bracket,
            "country": country,
            "device_type": device_type,
            "seed": seed,
        }))
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=f"invalid persona: {exc}")

    out: Dict[str, Any] = {"persona": persona_to_dict(portrait)}
    if preview:
        fp, _ = generate_with_persona(portrait, seed=seed)
        out["fingerprint"] = fp.canonical()
    return _ads_response(True, **out)


# ---------------------------------------------------------------------------
# WebRTC handling modes
# ---------------------------------------------------------------------------


@router.get("/webrtc/modes")
def webrtc_modes() -> Dict[str, Any]:
    """List the supported WebRTC handling modes."""
    from ..core.fingerprint import WEBRTC_MODES
    return _ads_response(
        True,
        modes=list(WEBRTC_MODES),
        descriptions={
            "block": "No ICE servers — no candidates gathered. Zero leak, but an anomaly.",
            "real": "WebRTC untouched. Real local/public IPs are exposed.",
            "proxy": "Candidate IPs rewritten to the proxy exit IP. Best realism.",
        },
    )


@router.post("/user/bulk/webrtc")
def user_bulk_webrtc(body: BulkWebRTCRequest) -> Dict[str, Any]:
    """Set the WebRTC mode on many profiles at once.

    NOTE: this route MUST stay declared before ``/user/{user_id}/webrtc``.
    FastAPI matches in declaration order, so the parameterised route would
    otherwise swallow this one with user_id="bulk".
    """
    assert _store is not None
    from ..core.fingerprint import WEBRTC_MODES, set_webrtc_mode

    mode = (body.mode or "").strip().lower()
    if mode not in WEBRTC_MODES:
        raise HTTPException(
            status_code=400,
            detail=f"unknown webrtc mode {body.mode!r}; expected one of {', '.join(WEBRTC_MODES)}",
        )
    public_ip = (body.public_ip or "").strip()
    if mode == "proxy" and not public_ip:
        raise HTTPException(status_code=400, detail="proxy mode requires public_ip")

    results: List[Dict[str, Any]] = []
    for uid in body.user_ids:
        profile = _store.get(uid)
        if profile is None:
            results.append({"user_id": uid, "ok": False, "error": "not found"})
            continue
        fp = _fingerprint_with_patch(None, base=profile.fingerprint or None)
        set_webrtc_mode(fp, mode, public_ip=public_ip if mode == "proxy" else None)
        _store.update(uid, fingerprint=fp)
        results.append({"user_id": uid, "ok": True})

    updated = sum(1 for r in results if r["ok"])
    record_activity(_store, "*", "bulk_webrtc", {"mode": mode, "updated_count": updated})
    return _ads_response(True, results=results, updated_count=updated, mode=mode)


@router.post("/user/{user_id}/webrtc")
async def user_set_webrtc(user_id: str, body: WebRTCRequest) -> Dict[str, Any]:
    """Set one profile's WebRTC mode, preserving every other fingerprint field."""
    assert _store is not None
    from ..core.fingerprint import WEBRTC_MODES, set_webrtc_mode

    mode = (body.mode or "").strip().lower()
    if mode not in WEBRTC_MODES:
        raise HTTPException(
            status_code=400,
            detail=f"unknown webrtc mode {body.mode!r}; expected one of {', '.join(WEBRTC_MODES)}",
        )

    profile = _store.get(user_id)
    if profile is None:
        raise HTTPException(status_code=404, detail="user_id not found")

    public_ip = (body.public_ip or "").strip()
    detected_ip: Optional[str] = None

    # Optionally learn the exit IP from the profile's own proxy.
    if mode == "proxy" and body.detect_from_proxy:
        cfg = parse_proxy(profile.proxy or {})
        if cfg.type in ("direct", "system") or not cfg.host or not cfg.port:
            raise HTTPException(
                status_code=400,
                detail="detect_from_proxy requires a proxy on this profile (it is direct)",
            )
        result = await check_proxy(cfg)
        detected_ip = result.get("ip")
        if not detected_ip:
            raise HTTPException(
                status_code=400,
                detail=f"could not detect proxy exit IP: {result.get('error') or 'unknown error'}",
            )
        public_ip = detected_ip

    if mode == "proxy" and not public_ip:
        raise HTTPException(
            status_code=400,
            detail="proxy mode requires public_ip or detect_from_proxy=true",
        )

    # Merge onto the stored fingerprint so nothing else is disturbed.
    fp = _fingerprint_with_patch(None, base=profile.fingerprint or None)
    set_webrtc_mode(fp, mode, public_ip=public_ip if mode == "proxy" else None)
    _store.update(user_id, fingerprint=fp)
    record_activity(_store, user_id, "webrtc_mode", {"mode": mode, "public_ip": fp.webrtc_public_ip})
    return _ads_response(
        True,
        user_id=user_id,
        mode=mode,
        public_ip=fp.webrtc_public_ip or None,
        detected_ip=detected_ip,
    )


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
    # WebSocket endpoints bypass the HTTP auth middleware, so we enforce
    # auth here directly. In remote mode with a token set, the client must
    # provide a valid Bearer token; otherwise we close with 4401.
    # In local/LAN mode, the WS is exempt (consistent with /json and /devtools).
    from .server import auth_check
    from ..core.security import DeploymentMode, is_origin_allowed

    deploy_mode: DeploymentMode = getattr(ws.app.state, "deploy_mode", DeploymentMode.LOCAL)
    api_token: str = getattr(ws.app.state, "api_token", "")
    allowed_origins: list = getattr(ws.app.state, "allowed_origins", [])

    # Check origin (WS Origin header or Host header)
    origin = ws.headers.get("origin", "") or ws.headers.get("referer", "")
    if not is_origin_allowed(origin, allowed_origins):
        await ws.close(code=4403)
        return

    # In remote mode, CDP paths require auth
    if deploy_mode == DeploymentMode.REMOTE and api_token:
        auth_header = ws.headers.get("authorization", "")
        expected = f"Bearer {api_token}"
        if not hmac.compare_digest(auth_header, expected):
            await ws.close(code=4401)
            return

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
        "version": __version__,
        "profile_count": len(profiles),
        "running_count": len(running),
        "running": [h.user_id for h in running],
    }