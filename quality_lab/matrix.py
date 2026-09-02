"""Engine × OS × Site coverage matrix planning.

The matrix is a *planning* tool: it enumerates the combinations of browser
engines, operating systems, and target sites that should be tested, and marks
each cell with a status (planned, covered, unsupported, skip).

This is pure data + pure functions — no browser is launched.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass(frozen=True)
class MatrixCell:
    """One intersection of engine × OS × site."""

    engine: str
    os_family: str
    site: str
    status: str = "planned"  # planned | covered | unsupported | skip
    reason: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "engine": self.engine,
            "os_family": self.os_family,
            "site": self.site,
            "status": self.status,
            "reason": self.reason,
        }


@dataclass
class MatrixPlan:
    """A full matrix plan: all cells + dimension labels."""

    engines: List[str] = field(default_factory=list)
    os_families: List[str] = field(default_factory=list)
    sites: List[str] = field(default_factory=list)
    cells: List[MatrixCell] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "engines": self.engines,
            "os_families": self.os_families,
            "sites": self.sites,
            "cells": [c.to_dict() for c in self.cells],
            "total_cells": len(self.cells),
            "covered": sum(1 for c in self.cells if c.status == "covered"),
            "planned": sum(1 for c in self.cells if c.status == "planned"),
            "unsupported": sum(1 for c in self.cells if c.status == "unsupported"),
        }

    def mark_covered(
        self, engine: str, os_family: str, site: str, reason: str = ""
    ) -> None:
        """Mark a specific cell as covered (a probe ran and passed)."""
        for i, c in enumerate(self.cells):
            if c.engine == engine and c.os_family == os_family and c.site == site:
                self.cells[i] = MatrixCell(
                    engine=engine,
                    os_family=os_family,
                    site=site,
                    status="covered",
                    reason=reason,
                )
                return

    def mark_skip(
        self, engine: str, os_family: str, site: str, reason: str
    ) -> None:
        """Mark a cell as skipped with a reason."""
        for i, c in enumerate(self.cells):
            if c.engine == engine and c.os_family == os_family and c.site == site:
                self.cells[i] = MatrixCell(
                    engine=engine,
                    os_family=os_family,
                    site=site,
                    status="skip",
                    reason=reason,
                )
                return


# ---------------------------------------------------------------------------
# Compatibility rules — which engine×OS combos are meaningful
# ---------------------------------------------------------------------------

# Chromium engines run on all three desktop OS families
_CHROMIUM_OSS = {"windows", "macos", "linux"}
# Firefox/Camoufox also run everywhere
_FIREFOX_OSS = {"windows", "macos", "linux"}
# WebKit is mainly useful for macOS (Safari-like profiles)
_WEBKIT_OSS = {"macos", "windows", "linux"}


def _engine_supports_os(engine: str, os_family: str) -> bool:
    """Whether an engine is meaningful on a given OS family."""
    e = engine.lower()
    if e in ("chromium", "chrome", "edge"):
        return os_family.lower() in _CHROMIUM_OSS
    if e in ("firefox", "camoufox"):
        return os_family.lower() in _FIREFOX_OSS
    if e == "webkit":
        return os_family.lower() in _WEBKIT_OSS
    return True  # unknown engine — don't block


# Default target sites for the matrix
DEFAULT_SITES = [
    "https://accounts.google.com",
    "https://okx.com",
    "https://browserleaks.com",
    "https://creepjs-api.web.app",
]


def build_matrix(
    engines: Optional[List[str]] = None,
    os_families: Optional[List[str]] = None,
    sites: Optional[List[str]] = None,
) -> MatrixPlan:
    """Build a full cross-product matrix plan.

    Each cell starts as ``planned``. Cells for engine×OS combos that don't
    make sense (e.g. WebKit-only features on Linux) are ``unsupported``.
    The caller can then mark cells as ``covered`` or ``skip`` as probes run.
    """
    if engines is None:
        engines = ["chromium", "chrome", "edge", "firefox", "camoufox", "webkit"]
    if os_families is None:
        os_families = ["windows", "macos", "linux"]
    if sites is None:
        sites = list(DEFAULT_SITES)

    cells: List[MatrixCell] = []
    for engine in engines:
        for os_family in os_families:
            for site in sites:
                if _engine_supports_os(engine, os_family):
                    cells.append(
                        MatrixCell(
                            engine=engine,
                            os_family=os_family,
                            site=site,
                            status="planned",
                        )
                    )
                else:
                    cells.append(
                        MatrixCell(
                            engine=engine,
                            os_family=os_family,
                            site=site,
                            status="unsupported",
                            reason=f"{engine} not meaningful on {os_family}",
                        )
                    )

    return MatrixPlan(
        engines=engines,
        os_families=os_families,
        sites=sites,
        cells=cells,
    )
