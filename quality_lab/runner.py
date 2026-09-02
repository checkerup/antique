"""Report runner — orchestrates suites into a QualityReport."""
from __future__ import annotations

import platform
import sys
from typing import Any, Dict, List, Optional

from .probes import (
    FingerprintProbes,
    LivePublicProbes,
    MatrixProbes,
    ProbeContext,
    SmokeProbes,
)
from .report import QualityReport, SuiteResult


def _build_environment(ctx: ProbeContext) -> Dict[str, Any]:
    """Collect static environment metadata for the report header."""
    return {
        "base_url": ctx.base_url,
        "engine": ctx.engine,
        "os_family": ctx.os_family,
        "site": ctx.site or "(none)",
        "has_fingerprint_json": ctx.fingerprint_json is not None,
        "live_browser": ctx.live_browser,
        "account_email_provided": ctx.account_email is not None,
        "python_version": sys.version.split()[0],
        "platform": platform.platform(),
    }


# Map suite name → suite runner function
_SUITE_RUNNERS = {
    "smoke": SmokeProbes.run,
    "fingerprint": FingerprintProbes.run,
    "matrix": MatrixProbes.run,
    "live_public": LivePublicProbes.run,
}

_ALL_SUITES = ["smoke", "fingerprint", "matrix", "live_public"]


def run_quality_lab(
    ctx: Optional[ProbeContext] = None,
    suites: Optional[List[str]] = None,
) -> QualityReport:
    """Run the quality lab and return a deterministic :class:`QualityReport`.

    Args:
        ctx: probe context. If None, a default one is created (pointing at
              http://127.0.0.1:8080 with no fingerprint and no live browser).
        suites: list of suite names to run. Defaults to all four suites.
              Unknown names raise ValueError.

    Returns:
        A :class:`QualityReport` with all suite results aggregated and
        the summary computed.
    """
    if ctx is None:
        ctx = ProbeContext()

    if suites is None:
        suites = list(_ALL_SUITES)

    # Validate suite names
    for name in suites:
        if name not in _SUITE_RUNNERS:
            raise ValueError(
                f"Unknown suite '{name}'. Valid suites: {sorted(_SUITE_RUNNERS)}"
            )

    report = QualityReport()
    report.environment = _build_environment(ctx)

    for suite_name in suites:
        runner = _SUITE_RUNNERS[suite_name]
        suite_result: SuiteResult = runner(ctx)
        report.add_suite(suite_result)

    report.compute_summary()
    return report
