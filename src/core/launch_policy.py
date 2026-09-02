"""Explicit browser launch policies.

A launch policy documents the compatibility/stealth trade-off instead of
scattering security-sensitive Chromium switches through the launcher.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Dict, Tuple


@dataclass(frozen=True)
class LaunchPolicy:
    name: str
    chromium_args: Tuple[str, ...] = ()
    ignore_playwright_default_args: Tuple[str, ...] = ()


_POLICIES: Dict[str, LaunchPolicy] = {
    "standard": LaunchPolicy(name="standard"),
    "stealth": LaunchPolicy(
        name="stealth",
        chromium_args=("--disable-blink-features=AutomationControlled",),
        ignore_playwright_default_args=("--enable-automation",),
    ),
    "google-compatible": LaunchPolicy(
        name="google-compatible",
        ignore_playwright_default_args=("--enable-automation", "--no-sandbox"),
    ),
}


def get_launch_policy(name: str | None = None) -> LaunchPolicy:
    """Resolve a known policy; reject typos rather than silently weakening it."""
    selected = (name or os.environ.get("ANTIQUE_LAUNCH_POLICY") or "google-compatible").strip().lower()
    try:
        return _POLICIES[selected]
    except KeyError as exc:
        choices = ", ".join(sorted(_POLICIES))
        raise ValueError(f"unknown launch policy {selected!r}; choose one of: {choices}") from exc


def list_launch_policies() -> Tuple[LaunchPolicy, ...]:
    return tuple(_POLICIES[name] for name in sorted(_POLICIES))
