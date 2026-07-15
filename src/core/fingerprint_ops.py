"""High-level fingerprint operations used by the dashboard and REST API."""
from __future__ import annotations

from dataclasses import fields
from typing import Any, Dict, Iterable, Mapping, Optional

from .fingerprint import Fingerprint, generate_fingerprint


FIELD_GROUPS: Dict[str, tuple[str, ...]] = {
    "identity": ("user_agent", "platform", "vendor", "oscpu"),
    "screen": (
        "screen_width", "screen_height", "avail_screen_width", "avail_screen_height",
        "inner_width", "inner_height", "color_depth", "pixel_ratio",
    ),
    "locale": ("locale", "accept_language", "languages"),
    "timezone": ("timezone", "spoof_geolocation", "geo_latitude", "geo_longitude", "geo_accuracy"),
    "hardware": ("hardware_concurrency", "device_memory"),
    "gpu": (
        "webgl_vendor", "webgl_renderer", "webgpu_enabled", "webgpu_vendor",
        "webgpu_architecture", "webgpu_description",
    ),
    "fonts": ("fonts",),
    "network": ("connection_type", "connection_downlink", "connection_rtt", "block_webrtc_ip"),
    "engine": ("browser_engine",),
    "extensions": ("extensions",),
}


def _keys(groups: Iterable[str]) -> set[str]:
    valid = {f.name for f in fields(Fingerprint)}
    out: set[str] = set()
    for group in groups:
        if group in FIELD_GROUPS:
            out.update(FIELD_GROUPS[group])
        elif group in valid:
            out.add(group)
        else:
            raise ValueError(f"unknown fingerprint field group: {group}")
    return out


def fingerprint_from_dict(raw: Optional[Mapping[str, Any]]) -> Fingerprint:
    valid = {f.name for f in fields(Fingerprint)}
    return Fingerprint(**{k: v for k, v in dict(raw or {}).items() if k in valid})


def randomize_batch(
    profiles: Mapping[str, Mapping[str, Any]],
    *,
    os_family: str = "windows",
    shared_fields: Iterable[str] = (),
    preserve_fields: Iterable[str] = ("engine", "extensions"),
    seed: Optional[str] = None,
) -> Dict[str, Fingerprint]:
    """Create one coherent randomized fingerprint per profile.

    ``shared_fields`` copies selected groups from one generated template to all
    profiles (for example ``screen`` keeps the same resolution). Other groups
    remain independently randomized. ``preserve_fields`` copies values from
    each profile's current fingerprint, useful for keeping engine/extensions.
    """
    if os_family not in {"windows", "macos", "linux"}:
        raise ValueError("os_family must be windows, macos, or linux")
    shared = _keys(shared_fields)
    preserve = _keys(preserve_fields)
    template = generate_fingerprint(seed=f"{seed}:shared" if seed else None, os_family=os_family)
    result: Dict[str, Fingerprint] = {}
    for user_id, raw in profiles.items():
        current = fingerprint_from_dict(raw)
        fresh = generate_fingerprint(seed=f"{seed}:{user_id}" if seed else None, os_family=os_family)
        for key in shared:
            setattr(fresh, key, getattr(template, key))
        for key in preserve:
            setattr(fresh, key, getattr(current, key))
        # Recompute stable identity after all requested overrides.
        import hashlib, json
        payload = json.dumps(fresh.canonical(), sort_keys=True, default=str).encode("utf-8")
        fresh.noise = hashlib.sha256(payload + (seed or "").encode("utf-8")).hexdigest()
        fresh.id = hashlib.sha256(payload).hexdigest()[:16]
        result[user_id] = fresh
    return result
