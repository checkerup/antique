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


def os_family_from_ua(ua: str) -> Optional[str]:
    """Infer the OS family a user-agent string claims, or None if unclear."""
    ua = (ua or "").lower()
    if "windows" in ua:
        return "windows"
    if "mac os" in ua or "macintosh" in ua:
        return "macos"
    if "linux" in ua or "x11" in ua:
        return "linux"
    return None


def _align_identity_to_ua(fp: Fingerprint) -> None:
    """Re-derive platform/vendor/oscpu from the UA so the identity set agrees.

    navigator.platform, vendor and oscpu are all functions of the OS the UA
    advertises. ``randomize_batch`` can leave them mismatched — preserving a
    Windows user_agent while generating for macOS, or overriding one field
    alone — and a Win32 platform under a macOS UA is an instant detection.
    The UA is treated as authoritative because it's the value callers pin.
    """
    family = os_family_from_ua(fp.user_agent)
    if family is None:
        return  # unrecognised UA: leave the fingerprint untouched

    # Borrow the identity block from a throwaway fingerprint for that OS rather
    # than re-deriving the values here — keeps this in lockstep with the
    # generator (vendor stays "Google Inc." on every OS for a Chrome build, and
    # macOS reports an oscpu the _OS_PROFILES table leaves empty).
    reference = generate_fingerprint(os_family=family)
    fp.platform = reference.platform
    fp.oscpu = reference.oscpu
    fp.vendor = reference.vendor

    # A GPU is tied to the OS too: Apple silicon under a Windows UA fails
    # webgl_os_coherence. Re-roll the GPU only when it contradicts the OS.
    gl = f"{fp.webgl_vendor} {fp.webgl_renderer}"
    if family != "macos" and ("Apple" in gl or "Intel Iris" in gl):
        fp.webgl_vendor = reference.webgl_vendor
        fp.webgl_renderer = reference.webgl_renderer


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
    overrides: Optional[Mapping[str, Any]] = None,
) -> Dict[str, Fingerprint]:
    """Create one coherent randomized fingerprint per profile.

    ``shared_fields`` copies selected groups from one generated template to all
    profiles (for example ``screen`` keeps the same resolution). Other groups
    remain independently randomized. ``preserve_fields`` copies values from
    each profile's current fingerprint, useful for keeping engine/extensions.

    ``overrides`` is an optional mapping of field → value that is applied
    AFTER generation, shared-field sharing, and preserve-field copying — so
    it always wins. Keys must be valid Fingerprint field names; unknown keys
    raise ValueError. This lets callers set concrete values (e.g. a specific
    user_agent or timezone) on selected profiles instead of randomizing them.
    """
    if os_family not in {"windows", "macos", "linux"}:
        raise ValueError("os_family must be windows, macos, or linux")
    shared = _keys(shared_fields)
    preserve = _keys(preserve_fields)
    if overrides:
        valid = {f.name for f in fields(Fingerprint)}
        unknown = set(overrides) - valid
        if unknown:
            raise ValueError(f"unknown override fields: {sorted(unknown)}")
    template = generate_fingerprint(seed=f"{seed}:shared" if seed else None, os_family=os_family)
    result: Dict[str, Fingerprint] = {}
    for user_id, raw in profiles.items():
        current = fingerprint_from_dict(raw)
        fresh = generate_fingerprint(seed=f"{seed}:{user_id}" if seed else None, os_family=os_family)
        for key in shared:
            setattr(fresh, key, getattr(template, key))
        for key in preserve:
            setattr(fresh, key, getattr(current, key))
        # Apply explicit overrides AFTER randomize+shared+preserve — they always win.
        if overrides:
            for key, value in overrides.items():
                setattr(fresh, key, value)
        # user_agent, platform, vendor and oscpu all derive from one OS. Copying
        # or overriding them field by field desyncs the set — preserving a
        # Windows UA while os_family="macos" leaves platform "MacIntel", which
        # fails the critical ua_platform_coherence check. Whatever UA won above
        # is authoritative, so realign the rest to it.
        _align_identity_to_ua(fresh)
        # Recompute stable identity after all requested overrides.
        import hashlib, json
        payload = json.dumps(fresh.canonical(), sort_keys=True, default=str).encode("utf-8")
        fresh.noise = hashlib.sha256(payload + (seed or "").encode("utf-8")).hexdigest()
        fresh.id = hashlib.sha256(payload).hexdigest()[:16]
        result[user_id] = fresh
    return result
