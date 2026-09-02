"""Deterministic report schema for the quality lab.

Every field has a fixed position and type so that downstream consumers
(JUnit XML, JSON, CI dashboards) can parse the report without heuristics.

Schema version is pinned in ``QualityReport.schema_version``. If the shape
changes in a breaking way, bump the version and document the migration.
"""
from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class CheckStatus(str, Enum):
    """The four possible outcomes of a single check.

    Using ``str`` enum so JSON serialisation is trivial.
    """

    PASS = "pass"
    FAIL = "fail"
    SKIP = "skip"
    ERROR = "error"

    @property
    def is_terminal_failure(self) -> bool:
        """True for FAIL and ERROR (the report should not be 'green')."""
        return self in (CheckStatus.FAIL, CheckStatus.ERROR)


@dataclass
class CheckResult:
    """One atomic assertion inside a suite.

    Attributes:
        name: stable identifier, e.g. ``health_endpoint_responds``
        status: one of pass/fail/skip/error
        severity: critical | high | medium | low (informational for skips)
        detail: human-readable explanation; for skip, the prerequisite that
                was missing
        duration_ms: wall-clock time the probe took (0 for pure functions)
        metadata: optional structured payload (e.g. HTTP status, JSON path)
    """

    name: str
    status: CheckStatus
    severity: str = "medium"
    detail: str = ""
    duration_ms: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "status": self.status.value,
            "severity": self.severity,
            "detail": self.detail,
            "duration_ms": round(self.duration_ms, 2),
            "metadata": self.metadata,
        }


@dataclass
class SuiteResult:
    """Aggregated result of one suite (e.g. ``smoke``).

    A suite is a logical group of checks that share a precondition family.
    """

    name: str
    checks: List[CheckResult] = field(default_factory=list)
    description: str = ""

    @property
    def passed(self) -> int:
        return sum(1 for c in self.checks if c.status == CheckStatus.PASS)

    @property
    def failed(self) -> int:
        return sum(1 for c in self.checks if c.status == CheckStatus.FAIL)

    @property
    def skipped(self) -> int:
        return sum(1 for c in self.checks if c.status == CheckStatus.SKIP)

    @property
    def errored(self) -> int:
        return sum(1 for c in self.checks if c.status == CheckStatus.ERROR)

    @property
    def total(self) -> int:
        return len(self.checks)

    @property
    def is_green(self) -> bool:
        """True when there are zero failures and zero errors.

        Skips are NOT failures — a skip means an honest prerequisite check
        said "can't run this here", which is the correct outcome in that
        environment.
        """
        return self.failed == 0 and self.errored == 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "passed": self.passed,
            "failed": self.failed,
            "skipped": self.skipped,
            "errored": self.errored,
            "total": self.total,
            "is_green": self.is_green,
            "checks": [c.to_dict() for c in self.checks],
        }


@dataclass
class QualityReport:
    """Top-level report produced by :func:`run_quality_lab`.

    This is the canonical object that serialises to JSON and JUnit XML.
    """

    schema_version: str = "1.0.0"
    report_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    timestamp: str = field(
        default_factory=lambda: time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    )
    suites: List[SuiteResult] = field(default_factory=list)
    environment: Dict[str, Any] = field(default_factory=dict)
    summary: Dict[str, Any] = field(default_factory=dict)

    def compute_summary(self) -> Dict[str, Any]:
        """Recalculate the aggregate summary and store it in ``self.summary``."""
        total_checks = sum(s.total for s in self.suites)
        total_pass = sum(s.passed for s in self.suites)
        total_fail = sum(s.failed for s in self.suites)
        total_skip = sum(s.skipped for s in self.suites)
        total_error = sum(s.errored for s in self.suites)
        all_green = all(s.is_green for s in self.suites)
        self.summary = {
            "total_suites": len(self.suites),
            "total_checks": total_checks,
            "passed": total_pass,
            "failed": total_fail,
            "skipped": total_skip,
            "errored": total_error,
            "all_green": all_green,
            # Overall status string for CI badge consumption.
            "status": "pass" if all_green else "fail",
        }
        return self.summary

    def to_dict(self) -> Dict[str, Any]:
        self.compute_summary()
        return {
            "schema_version": self.schema_version,
            "report_id": self.report_id,
            "timestamp": self.timestamp,
            "environment": self.environment,
            "summary": self.summary,
            "suites": [s.to_dict() for s in self.suites],
        }

    def add_suite(self, suite: SuiteResult) -> None:
        self.suites.append(suite)

    @property
    def is_green(self) -> bool:
        return all(s.is_green for s in self.suites)
