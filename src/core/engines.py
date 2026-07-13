"""Browser engine registry.

antique can drive several browser engines. This module is the single source of
truth for *which* engines exist, how they map onto Playwright, and how stealthy
each one is. Keeping it declarative makes the engine trivially swappable: pick
an engine key per profile (``fingerprint.browser_engine``) or globally
(``ANTIDETECT_ENGINE`` env var), and the launcher does the rest.

Engine bases:
- ``chromium``  → Playwright Chromium (optionally a real Chrome/Edge channel)
- ``firefox``   → Playwright Firefox, or Camoufox (a hardened Firefox fork)
- ``webkit``    → Playwright WebKit (Safari-like), useful for macOS/iOS profiles

Stealth tiers (rough, honest):
- ``deep``      → engine-level fingerprint spoofing (Camoufox patches Gecko C++)
- ``standard``  → real browser build + our JS init-script patches
- ``basic``     → bundled engine + JS patches; fine for most sites

Everything here is pure data + pure functions, so it is fully unit-testable
without launching a browser.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass(frozen=True)
class EngineSpec:
    """Static description of one browser engine."""

    key: str                 # canonical id used everywhere (e.g. "camoufox")
    label: str               # human label for the UI
    base: str                # playwright driver: chromium | firefox | webkit
    stealth: str             # deep | standard | basic
    channel: Optional[str] = None   # playwright channel for chromium (chrome/msedge)
    needs_install: bool = False     # requires an extra install step
    install_hint: str = ""          # how to enable it
    description: str = ""
    aliases: tuple = ()             # alternative names accepted by resolve()

    @property
    def is_chromium(self) -> bool:
        return self.base == "chromium"

    @property
    def is_firefox(self) -> bool:
        return self.base == "firefox"

    @property
    def supports_extensions(self) -> bool:
        # Only Chromium engines load unpacked/.crx extensions via CLI flags.
        return self.base == "chromium"

    @property
    def supports_cdp(self) -> bool:
        # A real per-profile CDP endpoint is Chromium-only.
        return self.base == "chromium"

    def to_dict(self) -> Dict[str, object]:
        return {
            "key": self.key,
            "label": self.label,
            "base": self.base,
            "stealth": self.stealth,
            "channel": self.channel,
            "needs_install": self.needs_install,
            "install_hint": self.install_hint,
            "description": self.description,
            "supports_extensions": self.supports_extensions,
            "supports_cdp": self.supports_cdp,
        }


# Registry ------------------------------------------------------------------

_ENGINES: List[EngineSpec] = [
    EngineSpec(
        key="chromium",
        label="Chromium (bundled)",
        base="chromium",
        stealth="standard",
        description="Playwright's bundled Chromium. Default. Extensions + real CDP.",
        aliases=("default", "chrome-bundled"),
    ),
    EngineSpec(
        key="chrome",
        label="Google Chrome",
        base="chromium",
        channel="chrome",
        stealth="standard",
        needs_install=True,
        install_hint="Requires Google Chrome installed on the host.",
        description="Real Google Chrome build via Playwright channel. Best UA/Client-Hints match.",
        aliases=("google-chrome", "google_chrome"),
    ),
    EngineSpec(
        key="edge",
        label="Microsoft Edge",
        base="chromium",
        channel="msedge",
        stealth="standard",
        needs_install=True,
        install_hint="Requires Microsoft Edge installed on the host.",
        description="Real Microsoft Edge build via Playwright channel.",
        aliases=("msedge", "microsoft-edge"),
    ),
    EngineSpec(
        key="firefox",
        label="Firefox (bundled)",
        base="firefox",
        stealth="standard",
        description="Playwright's bundled Firefox. Gecko engine, no Chromium tells.",
        aliases=("ff", "gecko"),
    ),
    EngineSpec(
        key="camoufox",
        label="Camoufox (deep stealth)",
        base="firefox",
        stealth="deep",
        needs_install=True,
        install_hint="pip install camoufox && python -m camoufox fetch",
        description="Hardened Firefox fork with C++-level fingerprint spoofing. Strongest stealth. Falls back to bundled Firefox if not installed.",
        aliases=("camou", "camo"),
    ),
    EngineSpec(
        key="webkit",
        label="WebKit (Safari-like)",
        base="webkit",
        stealth="basic",
        description="Playwright WebKit. Use for Safari / macOS / iOS-flavoured profiles.",
        aliases=("safari",),
    ),
]

# key/alias -> spec
_BY_NAME: Dict[str, EngineSpec] = {}
for _spec in _ENGINES:
    _BY_NAME[_spec.key] = _spec
    for _a in _spec.aliases:
        _BY_NAME[_a] = _spec

DEFAULT_ENGINE = "chromium"


def list_engines() -> List[EngineSpec]:
    """All engine specs in registry (display order)."""
    return list(_ENGINES)


def engine_keys() -> List[str]:
    """Canonical engine keys."""
    return [e.key for e in _ENGINES]


def is_valid_engine(name: str) -> bool:
    return (name or "").strip().lower() in _BY_NAME


def resolve_engine(name: Optional[str]) -> EngineSpec:
    """Resolve an engine name (key or alias, case-insensitive) to an EngineSpec.

    Unknown / empty names fall back to the default engine so a bad value never
    crashes a launch.
    """
    key = (name or "").strip().lower()
    return _BY_NAME.get(key, _BY_NAME[DEFAULT_ENGINE])


def resolve_engine_for_profile(
    profile_engine: Optional[str] = None,
    *,
    env: Optional[Dict[str, str]] = None,
) -> EngineSpec:
    """Resolution order: explicit profile engine → ANTIDETECT_ENGINE env → default.

    ``env`` is injectable for testing; defaults to ``os.environ``.
    """
    if profile_engine and is_valid_engine(profile_engine):
        return resolve_engine(profile_engine)
    env = env if env is not None else dict(os.environ)
    env_engine = env.get("ANTIDETECT_ENGINE", "")
    if env_engine and is_valid_engine(env_engine):
        return resolve_engine(env_engine)
    return resolve_engine(DEFAULT_ENGINE)
