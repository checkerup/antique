"""AdsPower fingerprint import — bridges AdsPower profile cache artifacts into
Antique ``Fingerprint`` objects.

Sources (per AdsPower profile cache dir ``C:\\.ADSPOWER_GLOBAL\\cache\\<uid>_xxx``):
  * ``<hash>_Other`` / ``<hash>_<platform>`` — plain-JSON WebGL config:
    ``{"UNMASKED_VENDOR_WEBGL": ..., "UNMASKED_RENDERER_WEBGL": ...}``
  * ``<hash>`` (~844B encoded) — dynamicconfig (encrypted, unreadable)
  * ``<hash>`` (~19KB encoded) — staticconfig (encrypted, unreadable)

The encoded configs are AES-encrypted by AdsPower's cloud key and cannot be
decoded offline (verified: entropy 7.27 bits/byte after custom-b64 decode).
The WebGL JSON however is plaintext and is the single most site-visible GPU
signal — this module imports it.

Deterministic seeds: canvas/audio/clientrect noise seeds are derived from the
profile uid + webgl renderer, so every AdsPower profile gets a STABLE but
DISTINCT noise profile — matching AdsPower's per-profile ``--protected-canvasmark`` /
``--protected-audiofp`` / ``--protected-clientrectfp`` behaviour (seeds are
per-profile constants, not per-session randoms).
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any, Dict, Optional

from .fingerprint import Fingerprint

ADSPOWER_CACHE = Path(r"C:\.ADSPOWER_GLOBAL\cache")

# Chrome version pinned near the engine we actually run.
_ENGINE_MAJOR = 146


def _stable_seed(uid: str, salt: str) -> int:
    """Deterministic 30-bit seed from uid + salt (same profile -> same seed)."""
    h = hashlib.sha256(f"{uid}:{salt}".encode("utf-8")).digest()
    return int.from_bytes(h[:4], "big") % (2**30) + 1


def find_webgl_json(cache_dir: Path) -> Optional[Dict[str, str]]:
    """Find and parse the plain-JSON WebGL fingerprint file in a profile cache."""
    for f in cache_dir.iterdir():
        if not f.is_file():
            continue
        # AdsPower names: <32-hex>_Other  or  <32-hex>_iPhone (platform suffix)
        m = re.match(r"^[0-9a-f]{32}_", f.name)
        if not m:
            continue
        try:
            data = json.loads(f.read_text(encoding="utf-8", errors="replace"))
        except Exception:
            continue
        if isinstance(data, dict) and "UNMASKED_RENDERER_WEBGL" in data:
            return data
    return None


def webgl_from_ads(data: Dict[str, str]) -> tuple[str, str]:
    """Extract (vendor, renderer) from an AdsPower WebGL JSON."""
    vendor = data.get("UNMASKED_VENDOR_WEBGL", "Google Inc. (Intel)")
    renderer = data.get("UNMASKED_RENDERER_WEBGL", "")
    # AdsPower sometimes writes "Google Inc.(Intel)" without space — normalise
    vendor = vendor.replace("Inc.(", "Inc. (")
    return vendor, renderer


def ads_profile_to_fingerprint(
    uid: str,
    *,
    os_hint: str = "windows",
    languages: Optional[list] = None,
    locale: str = "",
    timezone: str = "",
    screen: Optional[tuple[int, int]] = None,
    cache_root: Path = ADSPOWER_CACHE,
) -> Optional[Fingerprint]:
    """Build an Antique Fingerprint from an AdsPower profile cache.

    Only the GPU/WebGL pair comes from AdsPower (the rest is either encrypted
    or not present); missing fields keep the generator's coherent defaults.
    Noise seeds are derived deterministically from the uid so a migrated
    profile keeps its canvas/audio identity across launches.
    """
    # locate the profile cache dir: <uid>_<suffix>
    dirs = [d for d in cache_root.iterdir() if d.is_dir() and d.name.split("_")[0] == uid]
    if not dirs:
        return None
    cache_dir = dirs[0]

    webgl_json = find_webgl_json(cache_dir)
    if not webgl_json:
        return None
    vendor, renderer = webgl_from_ads(webgl_json)

    fp = Fingerprint()
    # UA: modern Chrome near the engine version
    fp.user_agent = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        f"(KHTML, like Gecko) Chrome/{_ENGINE_MAJOR}.0.7680.80 Safari/537.36"
    )
    fp.platform = "Win32"
    fp.vendor = "Google Inc."
    fp.webgl_vendor = vendor
    fp.webgl_renderer = renderer
    # WebGPU coherent with the WebGL GPU vendor
    gpu = vendor.lower()
    if "nvidia" in gpu:
        fp.webgpu_vendor, fp.webgpu_architecture = "nvidia", "ampere"
    elif "amd" in gpu or "radeon" in gpu:
        fp.webgpu_vendor, fp.webgpu_architecture = "amd", "rdna2"
    elif "intel" in gpu:
        fp.webgpu_vendor, fp.webgpu_architecture = "intel", "gen12"
    if fp.webgpu_architecture:
        fp.webgpu_description = renderer.split("(")[-1].split(")")[0] or "Integrated GPU"

    if languages:
        fp.languages = list(languages)
        fp.accept_language = ",".join(fp.languages[:2])
    if locale:
        fp.locale = locale
    if timezone:
        fp.timezone = timezone
    if screen:
        w, h = screen
        fp.screen_width = fp.avail_screen_width = w
        fp.screen_height = h
        fp.avail_screen_height = h - 40
        fp.inner_width, fp.inner_height = w, h - 80

    # Stable per-profile noise seeds (AdsPower parity: constant per profile)
    fp.canvas_noise_seed = _stable_seed(uid, "canvas")
    fp.audio_noise_seed = _stable_seed(uid, "audio")

    fp.noise = hashlib.sha256(f"ads:{uid}".encode()).hexdigest()
    return fp
