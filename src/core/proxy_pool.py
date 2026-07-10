"""Proxy pool with rotation strategies and automatic failover.

The health-check (``core.proxy.check_proxy``) already tells us whether a proxy
is alive. What was missing is a *pool*: a set of proxies a profile (or group)
can draw from, with a strategy for picking the next one and automatic failover
when one goes dead.

Strategies:
  - ``sticky``       : keep using the current proxy until it's marked dead.
  - ``round_robin``  : advance to the next live proxy on every ``next()``.
  - ``random``       : pick a random live proxy each time (seedable for tests).

Dead proxies are skipped. ``mark_dead`` / ``mark_alive`` update liveness. When
every proxy is dead, ``next_proxy`` returns ``None`` (caller falls back to a
direct connection or errors out).

Pure, deterministic, offline-testable: liveness and selection are in-memory and
the ``random`` strategy takes an injectable ``random.Random``.
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from .proxy import ProxyConfig, parse_proxy_list


STRATEGIES = {"sticky", "round_robin", "random"}


def _key(cfg: ProxyConfig) -> str:
    """Stable identity for a proxy (ignores credentials rotation on same host)."""
    return f"{cfg.type}://{cfg.host}:{cfg.port}"


@dataclass
class ProxyPool:
    """An ordered set of proxies with rotation + failover."""

    proxies: List[ProxyConfig] = field(default_factory=list)
    strategy: str = "sticky"
    _dead: Dict[str, bool] = field(default_factory=dict)
    _index: int = 0
    _current_key: Optional[str] = None

    def __post_init__(self):
        if self.strategy not in STRATEGIES:
            raise ValueError(
                f"unknown strategy {self.strategy!r}; valid: {', '.join(sorted(STRATEGIES))}"
            )
        if not self.proxies:
            raise ValueError("ProxyPool needs at least one proxy")

    # ---- construction helpers ----

    @classmethod
    def from_list_text(cls, text: str, strategy: str = "sticky") -> "ProxyPool":
        """Build a pool from a bulk proxy list (see core.proxy.parse_proxy_list)."""
        proxies = parse_proxy_list(text)
        if not proxies:
            raise ValueError("no valid proxies parsed from list")
        return cls(proxies=proxies, strategy=strategy)

    # ---- liveness ----

    def mark_dead(self, cfg: ProxyConfig) -> None:
        self._dead[_key(cfg)] = True

    def mark_alive(self, cfg: ProxyConfig) -> None:
        self._dead[_key(cfg)] = False

    def is_dead(self, cfg: ProxyConfig) -> bool:
        return self._dead.get(_key(cfg), False)

    def live_proxies(self) -> List[ProxyConfig]:
        return [p for p in self.proxies if not self.is_dead(p)]

    def reset_liveness(self) -> None:
        """Mark every proxy alive again (e.g. after a cooldown period)."""
        self._dead.clear()

    # ---- selection ----

    def _find(self, key: Optional[str]) -> Optional[ProxyConfig]:
        if key is None:
            return None
        for p in self.proxies:
            if _key(p) == key:
                return p
        return None

    def current(self) -> Optional[ProxyConfig]:
        cur = self._find(self._current_key)
        if cur is not None and not self.is_dead(cur):
            return cur
        return None

    def next_proxy(self, rng: Optional[random.Random] = None) -> Optional[ProxyConfig]:
        """Return the next proxy according to the strategy, skipping dead ones.

        Returns ``None`` when no live proxy remains.
        """
        live = self.live_proxies()
        if not live:
            self._current_key = None
            return None

        if self.strategy == "sticky":
            cur = self.current()
            chosen = cur if cur is not None else live[0]
        elif self.strategy == "round_robin":
            # Advance through the full ordered list starting after the last index,
            # returning the first live proxy encountered.
            n = len(self.proxies)
            chosen = None
            for step in range(1, n + 1):
                cand = self.proxies[(self._index + step) % n]
                if not self.is_dead(cand):
                    chosen = cand
                    self._index = (self._index + step) % n
                    break
            if chosen is None:
                chosen = live[0]
        elif self.strategy == "random":
            r = rng or random.Random()
            chosen = r.choice(live)
        else:  # pragma: no cover - guarded in __post_init__
            chosen = live[0]

        self._current_key = _key(chosen)
        return chosen

    def failover(self, rng: Optional[random.Random] = None) -> Optional[ProxyConfig]:
        """Mark the current proxy dead and return the next live one.

        This is the method the launcher calls when a proxy health-check fails
        mid-session: the bad proxy is retired and a replacement is selected.
        """
        cur = self._find(self._current_key)
        if cur is not None:
            self.mark_dead(cur)
        # For sticky, current() now returns None so next_proxy picks a fresh one.
        return self.next_proxy(rng=rng)
