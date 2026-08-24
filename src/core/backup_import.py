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

from .cookie import (
    import_adspower_profile,
    import_cookies_json,
    parse_extension_info_from_secure_prefs,
    find_profile_default_dir,
)
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
    try:
        port = int(data.get("proxy_port") or data.get("port") or 0)
    except (TypeError, ValueError):
        port = 0
    out: Dict[str, Any] = {
        "proxy_type": proxy_type if proxy_type in {"http", "https", "socks5"} else "direct",
        "proxy_host": str(data.get("proxy_host") or data.get("host") or ""),
        "proxy_port": port,
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
        try:
            cookies = [c.to_playwright() for c in import_cookies_json(cookie_json.read_text(encoding="utf-8-sig"))]
            cookie_source = "json"
        except (OSError, UnicodeError, json.JSONDecodeError, ValueError):
            # A broken exported JSON must not discard an otherwise usable
            # Chromium profile. Fall back to the profile Cookies DB.
            if profile_dir.exists():
                cookies = [c.to_playwright() for c in import_adspower_profile(profile_dir)]
                cookie_source = "profile_dir"
    elif profile_dir.exists():
        cookies = [c.to_playwright() for c in import_adspower_profile(profile_dir)]
        cookie_source = "profile_dir"

    import_source_path = str(profile_dir) if profile_dir.exists() else ""

    # Parse extension info from Secure Preferences
    extensions_info: List[Dict[str, Any]] = []
    has_extension_state = False
    has_extension_cookies = False
    has_local_ext_settings = False
    if profile_dir.exists():
        default_dir = find_profile_default_dir(profile_dir)
        if default_dir is not None:
            extensions_info = parse_extension_info_from_secure_prefs(default_dir)
            has_extension_state = (default_dir / "Extension State").is_dir()
            has_extension_cookies = (default_dir / "Extension Cookies").is_file()
            has_local_ext_settings = (default_dir / "Local Extension Settings").is_dir()

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
        "ip_country": str(meta.get("ip_country") or "").upper(),
        "extensions_info": extensions_info,
        "has_extension_state": has_extension_state,
        "has_extension_cookies": has_extension_cookies,
        "has_local_ext_settings": has_local_ext_settings,
    }


def import_adspower_backup_root(
    root: Path,
    store: ProfileStore,
    *,
    overwrite: bool = False,
    limit: Optional[int] = None,
    ext_store: Optional["ExtensionStore"] = None,
    adspower_root: Optional[Path] = None,
) -> Dict[str, Any]:
    """Import an entire AdsPower backup root into ``ProfileStore``.

    ``overwrite=False`` skips profiles that already exist.
    ``limit`` can be used for dry-runs / staged imports.
    ``ext_store``: if provided, user extensions are installed from the
    AdsPower global store and their IDs stored in the profile fingerprint.
    ``adspower_root``: path to ``C:\\.ADSPOWER_GLOBAL`` (auto-detected if
    not provided).
    """
    root = Path(root)

    # Load all profiles from the backup index once — used both for extension
    # scanning (when ext_store is provided) and for the main import loop.
    all_profiles = load_adspower_profiles_index(root)

    # Lazy import to avoid circular dependency
    installed_extensions: Dict[str, str] = {}  # chrome_ext_id -> antique_ext_id
    if ext_store is not None:
        # Install all unique extensions from ANY profile that has them.
        # Extensions are global — installed once, shared by all profiles.
        # Scan ALL profiles (not just up to limit) for extension code.
        seen_ext_ids: set = set()
        for meta in all_profiles:
            user_id = str(meta.get("user_id") or "").strip()
            if not user_id:
                continue
            profile_dir = _profile_dir(root, user_id)
            if not profile_dir.exists():
                continue
            default_dir = find_profile_default_dir(profile_dir)
            if default_dir is None:
                continue
            results = ext_store.install_extensions_from_secure_prefs(
                default_dir, adspower_root=adspower_root,
            )
            for r in results:
                if r.get("installed") and r.get("antique_ext_id"):
                    installed_extensions[r["ext_id"]] = r["antique_ext_id"]
                    seen_ext_ids.add(r["ext_id"])

    imported: List[str] = []
    updated: List[str] = []
    skipped: List[str] = []
    errors: List[Dict[str, str]] = []
    cookie_sources = {"json": 0, "profile_dir": 0, "none": 0}
    full_state_profiles = 0
    extensions_installed_count = len(installed_extensions)

    for idx, meta in enumerate(all_profiles):
        if limit is not None and idx >= limit:
            break
        try:
            payload = prepare_backup_profile_payload(root, meta)
            cookie_sources[payload["cookie_source"]] = cookie_sources.get(payload["cookie_source"], 0) + 1
            if payload["has_full_state"]:
                full_state_profiles += 1

            # Determine which Chrome extension IDs this profile has enabled
            profile_ext_ids: List[str] = []
            for ext_info in payload.get("extensions_info", []):
                if ext_info.get("enabled", False) and ext_info.get("ext_id"):
                    profile_ext_ids.append(ext_info["ext_id"])

            existing = store.get(payload["user_id"])
            if existing and not overwrite:
                skipped.append(payload["user_id"])
                continue
            if existing:
                fp = None
                if payload["ip_country"]:
                    try:
                        from .fingerprint_ops import fingerprint_from_dict
                        from .geo import apply_geo_to_fingerprint, geo_for_country
                        fp = fingerprint_from_dict(existing.fingerprint)
                        apply_geo_to_fingerprint(fp, geo_for_country(payload["ip_country"]))
                    except ValueError:
                        fp = None
                # Store extension IDs in fingerprint
                if fp is not None and profile_ext_ids:
                    fp_dict = fp.canonical() if hasattr(fp, "canonical") else fp.__dict__
                    fp_dict["extensions"] = profile_ext_ids
                    fp = fingerprint_from_dict(fp_dict) if fp else None
                store.update(
                    payload["user_id"],
                    name=payload["name"],
                    group_id=payload["group_id"],
                    proxy=payload["proxy"],
                    fingerprint=fp,
                    cookies=payload["cookies"],
                    tags=payload["tags"],
                    remark=payload["remark"],
                )
                if payload["import_source_path"]:
                    store.set_import_source(payload["user_id"], payload["import_source_path"], reset_applied=True)
                updated.append(payload["user_id"])
                continue

            fp = None
            if payload["ip_country"]:
                try:
                    from .fingerprint import generate_fingerprint
                    from .geo import apply_geo_to_fingerprint, geo_for_country
                    fp = generate_fingerprint()
                    apply_geo_to_fingerprint(fp, geo_for_country(payload["ip_country"]))
                except ValueError:
                    fp = None
            # Store extension IDs in fingerprint
            if fp is not None and profile_ext_ids:
                fp_dict = fp.canonical() if hasattr(fp, "canonical") else fp.__dict__
                fp_dict["extensions"] = profile_ext_ids
                from .fingerprint_ops import fingerprint_from_dict
                fp = fingerprint_from_dict(fp_dict)
            store.create(
                name=payload["name"],
                group_id=payload["group_id"],
                proxy=payload["proxy"],
                fingerprint=fp,
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

    processed = min(len(all_profiles), limit) if limit is not None else len(all_profiles)
    return {
        "source_path": str(root),
        "processed": processed,
        "imported_count": len(imported),
        "updated_count": len(updated),
        "skipped_count": len(skipped),
        "error_count": len(errors),
        "full_state_profiles": full_state_profiles,
        "cookie_sources": cookie_sources,
        "extensions_installed": extensions_installed_count,
        "imported_user_ids": imported,
        "updated_user_ids": updated,
        "skipped_user_ids": skipped,
        "errors": errors,
    }
