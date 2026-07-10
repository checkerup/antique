"""Portable profile export / import (``.antq`` bundles).

Moves a profile between machines as a single self-contained JSON file:
fingerprint, proxy, cookies, tags, group, remark. This is the local
equivalent of AdsPower/GoLogin/Undetectable "profile transfer" — no cloud,
just a file you copy.

The bundle intentionally does NOT include the Chromium ``user_data_dir``
(LocalStorage/IndexedDB/cache) by default: that's large and machine-coupled.
For full-state transfer, use the existing ``.adb`` full-profile import path.
A future extension can attach a zipped user_data_dir under ``state_archive``.

Format (``.antq`` = JSON):

    {
      "format": "antique-profile",
      "version": 1,
      "exported_at": "2026-07-09T12:00:00Z",
      "profile": {
        "name": "...",
        "group_id": "0",
        "remark": "",
        "tags": [...],
        "proxy": {...},
        "fingerprint": {...},   # asdict(Fingerprint)
        "cookies": [...]        # Playwright-shape cookie dicts
      }
    }

Export/serialise is pure Python and fully unit-testable; import round-trips
through a ``ProfileStore``.
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional, Union

BUNDLE_FORMAT = "antique-profile"
BUNDLE_VERSION = 1


class PortableBundleError(ValueError):
    """Raised when a bundle is malformed or an unsupported version."""


def build_bundle(profile: Any) -> Dict[str, Any]:
    """Serialise a ``Profile`` dataclass into a portable bundle dict.

    Only the portable, machine-independent fields are included. Runtime
    fields (running_pid/debug_port/ws), timestamps, launch_count and the
    local ``import_source_path`` are intentionally dropped.
    """
    return {
        "format": BUNDLE_FORMAT,
        "version": BUNDLE_VERSION,
        "exported_at": datetime.utcnow().isoformat() + "Z",
        "source_user_id": getattr(profile, "user_id", ""),
        "profile": {
            "name": profile.name,
            "group_id": getattr(profile, "group_id", "0"),
            "remark": getattr(profile, "remark", ""),
            "tags": list(getattr(profile, "tags", []) or []),
            "proxy": dict(getattr(profile, "proxy", {}) or {}),
            "fingerprint": dict(getattr(profile, "fingerprint", {}) or {}),
            "cookies": list(getattr(profile, "cookies", []) or []),
        },
    }


def dumps_bundle(profile: Any, *, indent: int = 2) -> str:
    """Serialise a profile to a ``.antq`` JSON string."""
    return json.dumps(build_bundle(profile), indent=indent, ensure_ascii=False, default=str)


def export_profile(profile: Any, path: Union[str, Path]) -> Path:
    """Write a profile bundle to ``path`` (``.antq``). Returns the path."""
    p = Path(path)
    if p.suffix == "":
        p = p.with_suffix(".antq")
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(dumps_bundle(profile), encoding="utf-8")
    return p


def parse_bundle(data: Union[str, bytes, Dict[str, Any]]) -> Dict[str, Any]:
    """Validate and return the bundle dict from a string/bytes/dict."""
    if isinstance(data, (str, bytes)):
        try:
            data = json.loads(data)
        except json.JSONDecodeError as exc:
            raise PortableBundleError(f"invalid JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise PortableBundleError("bundle must be a JSON object")
    if data.get("format") != BUNDLE_FORMAT:
        raise PortableBundleError(
            f"unexpected format {data.get('format')!r}, expected {BUNDLE_FORMAT!r}"
        )
    version = data.get("version")
    if version != BUNDLE_VERSION:
        raise PortableBundleError(
            f"unsupported bundle version {version!r}; this build supports {BUNDLE_VERSION}"
        )
    profile = data.get("profile")
    if not isinstance(profile, dict):
        raise PortableBundleError("bundle is missing a 'profile' object")
    if not profile.get("name"):
        raise PortableBundleError("bundle profile is missing 'name'")
    return data


def load_bundle_file(path: Union[str, Path]) -> Dict[str, Any]:
    """Read + validate a ``.antq`` file."""
    text = Path(path).read_text(encoding="utf-8")
    return parse_bundle(text)


def import_profile(
    store: Any,
    bundle: Union[str, bytes, Dict[str, Any], Path],
    *,
    name: Optional[str] = None,
    user_id: Optional[str] = None,
) -> Any:
    """Create a new profile in ``store`` from a portable bundle.

    Args:
        store: a ``ProfileStore``.
        bundle: a bundle dict, JSON string/bytes, or a path to a ``.antq`` file.
        name: optional override for the new profile's name.
        user_id: optional explicit user_id (else the store generates one).

    Returns the created ``Profile``.
    """
    # Path-like → read file
    if isinstance(bundle, (str, Path)) and not (
        isinstance(bundle, str) and bundle.lstrip().startswith("{")
    ):
        maybe = Path(bundle)
        if maybe.exists():
            data = load_bundle_file(maybe)
        else:
            data = parse_bundle(bundle)  # treat as raw JSON string
    else:
        data = parse_bundle(bundle)

    prof = data["profile"]
    fp_dict = prof.get("fingerprint") or {}

    # Rebuild a Fingerprint object if we have data; else let the store generate.
    fingerprint = None
    if fp_dict:
        from .fingerprint import Fingerprint
        from dataclasses import fields as _fields
        valid = {f.name for f in _fields(Fingerprint)}
        cleaned = {k: v for k, v in fp_dict.items() if k in valid}
        fingerprint = Fingerprint(**cleaned)

    return store.create(
        name=name or prof["name"],
        group_id=prof.get("group_id", "0"),
        proxy=prof.get("proxy") or {},
        fingerprint=fingerprint,
        cookies=prof.get("cookies") or [],
        tags=prof.get("tags") or [],
        remark=prof.get("remark", ""),
        user_id=user_id,
    )
