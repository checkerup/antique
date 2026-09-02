"""P6 — Executable Browser Quality Lab.

A deterministic, no-fake-success quality lab for Antique browser profiles.

The lab runs *probes* that produce a structured report. Every probe is one of:
  - **PASS**   — prerequisite met, assertion succeeded
  - **FAIL**   — prerequisite met, assertion failed
  - **SKIP**   — prerequisite absent (no network, no browser, no account);
                  the reason is recorded, never silently dropped
  - **ERROR**  — probe crashed unexpectedly; the exception text is captured

Probes are organised into suites:
  - ``smoke``           — local health / OpenAPI / CDP sanity
  - ``fingerprint``     — coherence assertions on collected JSON
  - ``matrix``          — engine × OS × site coverage planning
  - ``live_public``     — optional checks against real public sites
                          (skipped explicitly when prerequisites are absent)

Public entry points:
  - :func:`run_quality_lab` — run suites and return a :class:`QualityReport`
  - :class:`QualityReport` — deterministic serialisable report
  - CLI: ``python -m quality_lab`` or ``python tools/quality_lab.py``
"""
from __future__ import annotations

from .report import (
    CheckStatus,
    CheckResult,
    SuiteResult,
    QualityReport,
)
from .probes import (
    Probe,
    ProbeContext,
    SmokeProbes,
    FingerprintProbes,
    MatrixProbes,
    LivePublicProbes,
)
from .runner import run_quality_lab
from .redaction import redact_artifact, redact_report
from .output import to_json, to_junit_xml, to_summary_text
from .matrix import build_matrix, MatrixCell, MatrixPlan

__all__ = [
    "CheckStatus",
    "CheckResult",
    "SuiteResult",
    "QualityReport",
    "Probe",
    "ProbeContext",
    "SmokeProbes",
    "FingerprintProbes",
    "MatrixProbes",
    "LivePublicProbes",
    "run_quality_lab",
    "redact_artifact",
    "redact_report",
    "to_json",
    "to_junit_xml",
    "to_summary_text",
    "build_matrix",
    "MatrixCell",
    "MatrixPlan",
]
