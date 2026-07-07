"""Bulk AdsPower-backup import helpers.

This module imports a *directory backup* shaped like::

    backup_root/
      all_profiles_list.json
      json_cookies/
        <user_id>_cookies.json
      <user_id>/
        Default/
          Local Storage/
          WebStorage/
          Network/Cookies

The goal is to make importing a real AdsPower backup folder simple:

- preserve AdsPower ``user_id`` so existing mappings stay stable;
- reuse profile metadata from ``all_profiles_list.json``;
- prefer exported JSON cookies when available;
- fall back to the Chromium cookie DB inside the profile dir;
- keep ``import_source_path`` pointed at the original profile directory so
  the launcher can copy LocalStorage / WebStorage on first launch.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from .cookie import import_adspower_profile, import_cookies_json
from .profile import ProfileStore


def load_adspower_profiles_index(root: Path) -> List[Dict[str, Any]]:
    """Load ``all_profiles_list.json`` from a backup root."""
    index_path = Path(root) / "all_profiles_list.json"
    if not index_path.exists():
        raise FileNotFoundError(index_path)
    data = json.loads(index_path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError("all_profiles_list.json must contain a list")
    return [item for item in data if isinstance(item, dict)]


def _normalize_tags(raw: Any) -> List[str]:
    if not isinstance(raw, list):
        return []
    tags: List[str] = []
    for item in raw:
        value = ""
        if isinstance(item, str):
            value = item.strip()
        elif isinstance(item, dict):
            value = str(
                item.get("name")
                or item.get("tag_name")
                or item.get("value")
                or item.get("label")
                or ""
            ).strip()
        if value and value not in tags:
            tags.append(value)
    return tags


def _normalize_proxy(raw: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    data = dict(raw or {})
    proxy_soft = str(data.get("proxy_soft") or "").lower()
    proxy_type = str(data.get("proxy_type") or data.get("type") or "direct").lower()
    if proxy_soft == "no_proxy" or proxy_type in {"", "no_proxy", "direct"}:
        return {"proxy_type": "direct"}
    out: Dict[str, Any] = {
        "proxy_type": proxy_type,
        "proxy_host": str(data.get("proxy_host") or data.get("host") or ""),
        "proxy_port": int(data.get("proxy_port") or data.get("port") or 0),
    }
    if data.get("proxy_user"):
        out["proxy_user"] = str(data["proxy_user"])
    if data.get("proxy_password"):
        out["proxy_password"] = str(data["proxy_password"])
    if not out["proxy_host"] or not out["proxy_port"]:
        return {"proxy_type": "direct"}
    return out


def _profile_name(meta: Dict[str, Any]) -> str:
    return (
        str(meta.get("name") or "").strip()
        or str(meta.get("username") or "").strip()
        or f"Imported {meta.get('user_id', 'profile')}"
    )


def _profile_remark(meta: Dict[str, Any]) -> str:
    parts: List[str] = []
    remark = str(meta.get("remark") or "").strip()
    if remark:
        parts.append(remark)
    domain_name = str(meta.get("domain_name") or "").strip()
    if domain_name:
        parts.append(f"domain_name={domain_name}")
    serial_number = str(meta.get("serial_number") or "").strip()
    if serial_number:
        parts.append(f"serial_number={serial_number}")
    ip_country = str(meta.get("ip_country") or "").strip()
    if ip_country:
        parts.append(f"ip_country={ip_country}")
    return " | ".join(parts)


def _cookie_json_path(root: Path, user_id: str) -> Path:
    return Path(root) / "json_cookies" / f"{user_id}_cookies.json"


def _profile_dir(root: Path, user_id: str) -> Path:
    return Path(root) / user_id


def prepare_backup_profile_payload(root: Path, meta: Dict[str, Any]) -> Dict[str, Any]:
    """Build a create/update payload for one AdsPower backup profile."""
    user_id = str(meta.get("user_id") or "").strip()
    if not user_id:
        raise ValueError("profile entry is missing user_id")

    profile_dir = _profile_dir(root, user_id)
    cookie_json = _cookie_json_path(root, user_id)

    cookie_source = "none"
    cookies: List[Dict[str, Any]] = []
    if cookie_json.exists():
        cookies = [c.to_playwright() for c in import_cookies_json(cookie_json.read_text(encoding="utf-8"))]
        cookie_source = "json"
    elif profile_dir.exists():
        cookies = [c.to_playwright() for c in import_adspower_profile(profile_dir)]
        cookie_source = "profile_dir"

    import_source_path = str(profile_dir) if profile_dir.exists() else ""

    return {
        "user_id": user_id,
        "name": _profile_name(meta),
        "group_id": str(meta.get("group_id") or "0"),
        "proxy": _normalize_proxy(meta.get("user_proxy_config")),
        "cookies": cookies,
        "tags": _normalize_tags(meta.get("fbcc_user_tag")),
        "remark": _profile_remark(meta),
        "import_source_path": import_source_path,
        "cookie_source": cookie_source,
        "has_full_state": bool(import_source_path),
    }


def import_adspower_backup_root(
    root: Path,
    store: ProfileStore,
    *,
    overwrite: bool = False,
    limit: Optional[int] = None,
) -> Dict[str, Any]:
    """Import an entire AdsPower backup root into ``ProfileStore``.

    ``overwrite=False`` skips profiles that already exist.
    ``limit`` can be used for dry-runs / staged imports.
    """
    root = Path(root)
    profiles = load_adspower_profiles_index(root)

    imported: List[str] = []
    updated: List[str] = []
    skipped: List[str] = []
    errors: List[Dict[str, str]] = []
    cookie_sources = {"json": 0, "profile_dir": 0, "none": 0}
    full_state_profiles = 0

    for idx, meta in enumerate(profiles):
        if limit is not None and idx >= limit:
            break
        try:
            payload = prepare_backup_profile_payload(root, meta)
            cookie_sources[payload["cookie_source"]] = cookie_sources.get(payload["cookie_source"], 0) + 1
            if payload["has_full_state"]:
                full_state_profiles += 1
            existing = store.get(payload["user_id"])
            if existing and not overwrite:
                skipped.append(payload["user_id"])
                continue
            if existing:
                store.update(
                    payload["user_id"],
                    name=payload["name"],
                    group_id=payload["group_id"],
                    proxy=payload["proxy"],
                    cookies=payload["cookies"],
                    tags=payload["tags"],
                    remark=payload["remark"],
                )
                if payload["import_source_path"]:
                    store.set_import_source(payload["user_id"], payload["import_source_path"], reset_applied=True)
                updated.append(payload["user_id"])
                continue

            store.create(
                name=payload["name"],
                group_id=payload["group_id"],
                proxy=payload["proxy"],
                cookies=payload["cookies"],
                tags=payload["tags"],
                remark=payload["remark"],
                user_id=payload["user_id"],
            )
            if payload["import_source_path"]:
                store.set_import_source(payload["user_id"], payload["import_source_path"], reset_applied=True)
            imported.append(payload["user_id"])
        except Exception as exc:
            errors.append({
                "user_id": str(meta.get("user_id") or ""),
                "error": str(exc),
            })

    processed = min(len(profiles), limit) if limit is not None else len(profiles)
    return {
        "source_path": str(root),
        "processed": processed,
        "imported_count": len(imported),
        "updated_count": len(updated),
        "skipped_count": len(skipped),
        "error_count": len(errors),
        "full_state_profiles": full_state_profiles,
        "cookie_sources": cookie_sources,
        "imported_user_ids": imported,
        "updated_user_ids": updated,
        "skipped_user_ids": skipped,
        "errors": errors,
    }
