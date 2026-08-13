"""Real fingerprint corpus — curated device fingerprints for sampling.

Unlike the template-based generator (which synthesizes coherent but
synthetic fingerprints), the corpus stores REAL fingerprints captured from
actual devices (CreepJS/browserleaks dumps or consented telemetry). The
generator samples a real fingerprint and adds small deterministic noise,
producing a profile that looks like a genuine device rather than a
generated one.

Format: one JSON per device, named by a short slug. Each file contains a
complete Fingerprint dict (all fields), plus optional metadata:
{
  "source": "creepjs|browserleaks|consented",
  "device_hint": "desktop|laptop|mobile",
  "os_family": "windows|macos|linux",
  "captured_at": "ISO8601",
  "fingerprint": { ...all Fingerprint fields... }
}
"""
from __future__ import annotations

import json
import random
from dataclasses import fields
from pathlib import Path
from typing import Any, Dict, List, Optional

from .fingerprint import Fingerprint


CORPUS_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "fingerprint_corpus"


def _corpus_path() -> Path:
    """Return the corpus directory, creating it if missing."""
    CORPUS_DIR.mkdir(parents=True, exist_ok=True)
    return CORPUS_DIR


def _load_entry(path: Path) -> Optional[Dict[str, Any]]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return None
        # Support both raw Fingerprint dict and wrapped {fingerprint: {...}} format
        if "fingerprint" in data and isinstance(data["fingerprint"], dict):
            return data["fingerprint"]
        return data
    except Exception:
        return None


def _corpus_entries(os_family: Optional[str] = None) -> List[Dict[str, Any]]:
    """Load all valid fingerprint dicts from the corpus, optionally filtered."""
    entries: List[Dict[str, Any]] = []
    for p in _corpus_path().glob("*.json"):
        fp = _load_entry(p)
        if fp is None:
            continue
        if os_family is not None:
            platform = str(fp.get("platform", ""))
            if os_family == "windows" and platform != "Win32":
                continue
            if os_family == "macos" and platform != "MacIntel":
                continue
            if os_family == "linux" and "Linux" not in platform:
                continue
            # Unknown os_family: no match (return empty rather than everything)
            if os_family not in ("windows", "macos", "linux"):
                continue
        entries.append(fp)
    return entries


def sample_from_corpus(os_family: Optional[str] = None, seed: Optional[str] = None) -> Optional[Fingerprint]:
    """Sample a random real fingerprint from the corpus.

    Returns None if the corpus is empty or no matching entry found.
    The sampled fingerprint is NOT modified — use ``add_noise`` to perturb it.
    """
    entries = _corpus_entries(os_family=os_family)
    if not entries:
        return None
    rng = random.Random(seed)
    raw = rng.choice(entries)
    valid = {f.name for f in fields(Fingerprint)}
    fp = Fingerprint(**{k: v for k, v in raw.items() if k in valid})

    # Corpus entries only carry the fields a collector could observe, so
    # anything absent falls back to the dataclass default. For navigator.plugins
    # that default is an empty list — and a Chrome build reporting zero plugins
    # is a tell, since PDF Viewer is always present. Backfill a realistic set.
    if not fp.plugins and ("Chrome" in fp.user_agent or "Chrom" in fp.user_agent):
        from src.core.fingerprint import _chrome_plugins

        fp.plugins = _chrome_plugins(rng)

    return fp


def add_noise(fp: Fingerprint, seed: Optional[str] = None, magnitude: float = 0.05) -> Fingerprint:
    """Add small deterministic noise to a sampled fingerprint.

    Only perturbs continuous numeric fields (screen dims, hardware) and adds
    a tiny jitter to UA version numbers. String/categorical fields are left
    alone — they're the coherent core of the real device.
    """
    rng = random.Random(seed)

    # Screen dims: ±3% jitter (within real device variance).
    #
    # These six numbers are NOT independent — a real device always satisfies
    # inner <= avail <= screen. Jittering each field on its own breaks that
    # ordering (an avail_width wider than screen_width is an instant tell), so
    # jitter the physical screen once and re-derive the insets from it, keeping
    # the original chrome/taskbar deltas that the generator picked.
    if magnitude > 0:
        w_delta = fp.screen_width * 0.03
        h_delta = fp.screen_height * 0.03
        new_w = max(1, int(fp.screen_width + rng.uniform(-w_delta, w_delta)))
        new_h = max(1, int(fp.screen_height + rng.uniform(-h_delta, h_delta)))

        # Preserve the insets as they were, then clamp so the invariant holds
        # even when the jitter shrank the screen below the original inset.
        avail_w_inset = max(0, fp.screen_width - fp.avail_screen_width)
        avail_h_inset = max(0, fp.screen_height - fp.avail_screen_height)
        inner_w_inset = max(0, fp.avail_screen_width - fp.inner_width)
        inner_h_inset = max(0, fp.avail_screen_height - fp.inner_height)

        fp.screen_width = new_w
        fp.screen_height = new_h
        fp.avail_screen_width = max(1, min(new_w, new_w - avail_w_inset))
        fp.avail_screen_height = max(1, min(new_h, new_h - avail_h_inset))
        fp.inner_width = max(1, min(fp.avail_screen_width, fp.avail_screen_width - inner_w_inset))
        fp.inner_height = max(1, min(fp.avail_screen_height, fp.avail_screen_height - inner_h_inset))

    # Hardware: ±1 step, but browsers only ever report plausible values.
    # navigator.hardwareConcurrency is an even core count on real machines and
    # deviceMemory is quantised to a power of two, so snap instead of drifting
    # to tells like 7 cores or 3 GB.
    _CORES = (2, 4, 6, 8, 12, 16, 24, 32)
    _MEMORY = (2.0, 4.0, 8.0, 16.0, 32.0, 64.0)

    def _step(value, ladder):
        """Move value one rung along the ladder (or stay put)."""
        nearest = min(range(len(ladder)), key=lambda i: abs(ladder[i] - value))
        idx = min(len(ladder) - 1, max(0, nearest + rng.choice([-1, 0, 1])))
        return ladder[idx]

    fp.hardware_concurrency = int(_step(fp.hardware_concurrency, _CORES))
    fp.device_memory = float(_step(fp.device_memory, _MEMORY))

    # Noise seeds: perturb so each sample is unique but deterministic per seed
    if seed:
        import hashlib
        h = hashlib.sha256(seed.encode("utf-8")).hexdigest()
        fp.canvas_noise_seed = int(h[:8], 16)
        fp.audio_noise_seed = int(h[8:16], 16)

    return fp


def corpus_size(os_family: Optional[str] = None) -> int:
    """Return how many entries are in the corpus (optionally filtered by OS)."""
    return len(_corpus_entries(os_family=os_family))
