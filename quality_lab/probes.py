"""Probe definitions and suite implementations.

Every probe inherits from :class:`Probe` and implements :meth:`run`, which
returns a :class:`CheckResult`. Probes receive a :class:`ProbeContext` that
carries shared resources: an HTTP transport, a base URL, and flags.

Design principles:
  1. **No fake success** — if a prerequisite is absent, the probe returns
     SKIP with an honest reason. Never PASS on a placeholder.
  2. **Deterministic** — the same inputs produce the same report shape.
  3. **Observable** — we assert on what the system *does*, not on what
     its config *says*. (behavioural-verification principle)
"""
from __future__ import annotations

import json
import socket
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple

from .report import CheckResult, CheckStatus, SuiteResult


# ---------------------------------------------------------------------------
# Probe context — shared resources injected into every probe
# ---------------------------------------------------------------------------


@dataclass
class ProbeContext:
    """Carries shared state and configuration into every probe.

    Attributes:
        base_url: Antique API base URL (default http://127.0.0.1:8080)
        http_get: callable(path, timeout) -> (status_code, body_dict_or_text, latency_ms)
                  When None, uses :func:`_default_http_get`. This is injectable
                  so tests can use FastAPI TestClient without a live server.
        fingerprint_json: collected fingerprint dict for coherence checks
        engine: engine key for matrix context
        os_family: OS family for matrix context
        site: target site for live probes
        account_email: email for login-flow tests (None = not provided)
        live_browser: True when a real browser session is available
        network_available: True when outbound internet is reachable
    """

    base_url: str = "http://127.0.0.1:8080"
    http_get: Optional[Callable] = None
    fingerprint_json: Optional[Dict[str, Any]] = None
    engine: str = "chromium"
    os_family: str = "windows"
    site: str = ""
    account_email: Optional[str] = None
    live_browser: bool = False
    network_available: Optional[bool] = None

    def resolve_http_get(self) -> Callable:
        """Return the configured http_get, or the default one."""
        if self.http_get is not None:
            return self.http_get
        return _default_http_get

    def check_network(self) -> bool:
        """Honest network-reachability check (cached after first call)."""
        if self.network_available is not None:
            return self.network_available
        try:
            socket.create_connection(("8.8.8.8", 53), timeout=2).close()
            self.network_available = True
        except OSError:
            self.network_available = False
        return self.network_available


def _default_http_get(
    path: str, timeout: float = 5.0, base_url: str = ""
) -> Tuple[int, Any, float]:
    """Default HTTP GET using urllib — no third-party deps.

    Returns ``(status_code, parsed_json_or_raw_text, latency_ms)``.
    """
    url = path if path.startswith("http") else base_url.rstrip("/") + path
    t0 = time.perf_counter()
    try:
        req = urllib.request.Request(url, headers={"Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            latency = (time.perf_counter() - t0) * 1000
            try:
                parsed = json.loads(body)
            except json.JSONDecodeError:
                parsed = body
            return resp.status, parsed, latency
    except urllib.error.HTTPError as e:
        latency = (time.perf_counter() - t0) * 1000
        body = ""
        try:
            body = e.read().decode("utf-8", errors="replace")
        except Exception:
            pass
        return e.code, body, latency
    except (urllib.error.URLError, socket.timeout, ConnectionError, OSError) as e:
        latency = (time.perf_counter() - t0) * 1000
        return 0, str(e), latency


# ---------------------------------------------------------------------------
# Probe base class
# ---------------------------------------------------------------------------


class Probe:
    """Base class for all probes.

    Subclasses implement :meth:`run` which must return a :class:`CheckResult`.
    The base provides a timing wrapper and a safe execution guard that catches
    unexpected exceptions and converts them to ERROR results.
    """

    name: str = "base"
    severity: str = "medium"

    def execute(self, ctx: ProbeContext) -> CheckResult:
        """Run the probe safely, timing it and catching crashes."""
        t0 = time.perf_counter()
        try:
            result = self.run(ctx)
            result.duration_ms = (time.perf_counter() - t0) * 1000
            return result
        except Exception as exc:
            return CheckResult(
                name=self.name,
                status=CheckStatus.ERROR,
                severity=self.severity,
                detail=f"Probe crashed: {type(exc).__name__}: {exc}",
                duration_ms=(time.perf_counter() - t0) * 1000,
            )

    def run(self, ctx: ProbeContext) -> CheckResult:  # pragma: no cover
        raise NotImplementedError


# ---------------------------------------------------------------------------
# Smoke Probes — local health / OpenAPI / CDP
# ---------------------------------------------------------------------------


class HealthProbe(Probe):
    """Check that the Antique /health endpoint responds with status=ok."""

    name = "health_endpoint_responds"
    severity = "critical"

    def run(self, ctx: ProbeContext) -> CheckResult:
        getter = ctx.resolve_http_get()
        status, body, latency = getter("/health", base_url=ctx.base_url)

        if status == 0:
            return CheckResult(
                name=self.name,
                status=CheckStatus.SKIP,
                severity=self.severity,
                detail=f"Server not reachable: {body}",
                metadata={"latency_ms": round(latency, 2)},
            )
        if status != 200:
            return CheckResult(
                name=self.name,
                status=CheckStatus.FAIL,
                severity=self.severity,
                detail=f"HTTP {status} from /health",
                metadata={"status": status, "latency_ms": round(latency, 2)},
            )
        # Check the body shape
        if isinstance(body, dict):
            svc = body.get("status")
            service = body.get("service", "")
            if svc == "ok":
                return CheckResult(
                    name=self.name,
                    status=CheckStatus.PASS,
                    severity=self.severity,
                    detail=f"Health OK, service={service}",
                    metadata={
                        "status": status,
                        "latency_ms": round(latency, 2),
                        "service": service,
                    },
                )
            return CheckResult(
                name=self.name,
                status=CheckStatus.FAIL,
                severity=self.severity,
                detail=f"status field is '{svc}', expected 'ok'",
                metadata={"body": body},
            )
        return CheckResult(
            name=self.name,
            status=CheckStatus.FAIL,
            severity=self.severity,
            detail=f"/health returned non-JSON: {str(body)[:200]}",
        )


class OpenAPIProbe(Probe):
    """Verify the OpenAPI schema endpoint is reachable and well-formed."""

    name = "openapi_schema_valid"
    severity = "high"

    def run(self, ctx: ProbeContext) -> CheckResult:
        getter = ctx.resolve_http_get()
        status, body, latency = getter("/openapi.json", base_url=ctx.base_url)

        if status == 0:
            return CheckResult(
                name=self.name,
                status=CheckStatus.SKIP,
                severity=self.severity,
                detail=f"Server not reachable: {body}",
            )
        if status != 200:
            return CheckResult(
                name=self.name,
                status=CheckStatus.FAIL,
                severity=self.severity,
                detail=f"HTTP {status} from /openapi.json",
            )
        if not isinstance(body, dict):
            return CheckResult(
                name=self.name,
                status=CheckStatus.FAIL,
                severity=self.severity,
                detail="/openapi.json returned non-JSON body",
            )
        paths = body.get("paths")
        info = body.get("info", {})
        if not isinstance(paths, dict) or len(paths) == 0:
            return CheckResult(
                name=self.name,
                status=CheckStatus.FAIL,
                severity=self.severity,
                detail="OpenAPI schema has no paths defined",
            )
        title = info.get("title", "")
        version = info.get("version", "")
        return CheckResult(
            name=self.name,
            status=CheckStatus.PASS,
            severity=self.severity,
            detail=f"OpenAPI valid: {len(paths)} paths, title={title}, v{version}",
            metadata={
                "path_count": len(paths),
                "title": title,
                "version": version,
            },
        )


class CDPVersionProbe(Probe):
    """Check that /json/version returns a CDP version payload."""

    name = "cdp_version_payload"
    severity = "high"

    def run(self, ctx: ProbeContext) -> CheckResult:
        getter = ctx.resolve_http_get()
        status, body, latency = getter("/json/version", base_url=ctx.base_url)

        if status == 0:
            return CheckResult(
                name=self.name,
                status=CheckStatus.SKIP,
                severity=self.severity,
                detail=f"Server not reachable: {body}",
            )
        if status != 200:
            return CheckResult(
                name=self.name,
                status=CheckStatus.FAIL,
                severity=self.severity,
                detail=f"HTTP {status} from /json/version",
            )
        if not isinstance(body, dict):
            return CheckResult(
                name=self.name,
                status=CheckStatus.FAIL,
                severity=self.severity,
                detail="/json/version returned non-JSON",
            )
        required_fields = {"Browser", "Protocol-Version"}
        present = required_fields & set(body.keys())
        if present != required_fields:
            return CheckResult(
                name=self.name,
                status=CheckStatus.FAIL,
                severity=self.severity,
                detail=f"Missing CDP fields: {required_fields - present}",
                metadata={"present": sorted(present)},
            )
        browser_name = body.get("Browser", "")
        protocol_version = body.get("Protocol-Version", "")
        return CheckResult(
            name=self.name,
            status=CheckStatus.PASS,
            severity=self.severity,
            detail=f"CDP version OK: {browser_name}, protocol {protocol_version}",
            metadata={
                # Preserve wire-format keys and provide normalized aliases for
                # report consumers.
                "Browser": body.get("Browser", ""),
                "Protocol-Version": body.get("Protocol-Version", ""),
                "browser": body.get("Browser", ""),
                "protocol_version": body.get("Protocol-Version", ""),
            },
        )


class SmokeProbes:
    """Suite of smoke probes for local health/OpenAPI/CDP."""

    SUITE_NAME = "smoke"
    DESCRIPTION = "Local health, OpenAPI schema, and CDP endpoint sanity"

    @staticmethod
    def probes() -> List[Probe]:
        return [HealthProbe(), OpenAPIProbe(), CDPVersionProbe()]

    @staticmethod
    def run(ctx: ProbeContext) -> SuiteResult:
        suite = SuiteResult(name=SmokeProbes.SUITE_NAME, description=SmokeProbes.DESCRIPTION)
        for probe in SmokeProbes.probes():
            suite.checks.append(probe.execute(ctx))
        return suite


# ---------------------------------------------------------------------------
# Fingerprint Coherence Probes — from collected JSON
# ---------------------------------------------------------------------------


class FingerprintCoherenceProbe(Probe):
    """Assert that a collected fingerprint JSON is internally coherent.

    Uses the existing :func:`src.core.detect.score_fingerprint` scorer to
    evaluate the fingerprint. The fingerprint must be provided as
    ``ctx.fingerprint_json`` — this probe does NOT launch a browser.
    """

    name = "fingerprint_coherence"
    severity = "critical"

    def run(self, ctx: ProbeContext) -> CheckResult:
        fp = ctx.fingerprint_json
        if fp is None:
            return CheckResult(
                name=self.name,
                status=CheckStatus.SKIP,
                severity=self.severity,
                detail="No fingerprint JSON provided in context",
            )
        if not isinstance(fp, dict):
            return CheckResult(
                name=self.name,
                status=CheckStatus.FAIL,
                severity=self.severity,
                detail=f"fingerprint_json is {type(fp).__name__}, expected dict",
            )

        try:
            from src.core.detect import score_fingerprint

            report = score_fingerprint(fp)
            report_dict = report.to_dict()
        except Exception as exc:
            return CheckResult(
                name=self.name,
                status=CheckStatus.ERROR,
                severity=self.severity,
                detail=f"Scorer crashed: {type(exc).__name__}: {exc}",
            )

        failures = report_dict.get("failures", [])
        score = report_dict.get("score", 0)
        ok = report_dict.get("ok", False)

        if not failures and score == 100:
            return CheckResult(
                name=self.name,
                status=CheckStatus.PASS,
                severity=self.severity,
                detail=f"Fingerprint coherent, score={score}",
                metadata={"score": score, "total_checks": report_dict.get("total", 0)},
            )
        if failures:
            failure_names = [f["name"] for f in failures]
            return CheckResult(
                name=self.name,
                status=CheckStatus.FAIL,
                severity=self.severity,
                detail=f"Fingerprint incoherent: {failure_names}",
                metadata={
                    "score": score,
                    "failures": failure_names,
                    "total_checks": report_dict.get("total", 0),
                },
            )
        # Score < 100 but no critical failures — still a pass with a note
        return CheckResult(
            name=self.name,
            status=CheckStatus.PASS,
            severity=self.severity,
            detail=f"Fingerprint passed (score={score}, no critical failures)",
            metadata={"score": score},
        )


class FingerprintFieldPresentProbe(Probe):
    """Assert that critical fingerprint fields are present and non-empty.

    Checks: user_agent, platform, timezone, webgl_vendor, languages, fonts.
    Each missing field is a separate sub-check aggregated into one result.
    """

    name = "fingerprint_critical_fields_present"
    severity = "high"

    REQUIRED_FIELDS = [
        "user_agent",
        "platform",
        "timezone",
        "webgl_vendor",
        "languages",
        "fonts",
    ]

    def run(self, ctx: ProbeContext) -> CheckResult:
        fp = ctx.fingerprint_json
        if fp is None:
            return CheckResult(
                name=self.name,
                status=CheckStatus.SKIP,
                severity=self.severity,
                detail="No fingerprint JSON provided in context",
            )

        missing = []
        empty = []
        for field_name in self.REQUIRED_FIELDS:
            val = fp.get(field_name)
            if val is None:
                missing.append(field_name)
            elif isinstance(val, (list, str)) and len(val) == 0:
                empty.append(field_name)

        if not missing and not empty:
            return CheckResult(
                name=self.name,
                status=CheckStatus.PASS,
                severity=self.severity,
                detail="All critical fingerprint fields present",
                metadata={"fields_checked": self.REQUIRED_FIELDS},
            )
        detail_parts = []
        if missing:
            detail_parts.append(f"missing: {missing}")
        if empty:
            detail_parts.append(f"empty: {empty}")
        return CheckResult(
            name=self.name,
            status=CheckStatus.FAIL,
            severity=self.severity,
            detail="; ".join(detail_parts),
            metadata={"missing": missing, "empty": empty},
        )


class FingerprintEngineMatchProbe(Probe):
    """Assert that the fingerprint's browser_engine is a known valid engine."""

    name = "fingerprint_engine_known"
    severity = "high"

    def run(self, ctx: ProbeContext) -> CheckResult:
        fp = ctx.fingerprint_json
        if fp is None:
            return CheckResult(
                name=self.name,
                status=CheckStatus.SKIP,
                severity=self.severity,
                detail="No fingerprint JSON provided in context",
            )

        engine = fp.get("browser_engine")
        if not engine:
            return CheckResult(
                name=self.name,
                status=CheckStatus.FAIL,
                severity=self.severity,
                detail="browser_engine field is missing or empty",
            )

        try:
            from src.core.engines import is_valid_engine

            if is_valid_engine(engine):
                return CheckResult(
                    name=self.name,
                    status=CheckStatus.PASS,
                    severity=self.severity,
                    detail=f"Engine '{engine}' is valid",
                    metadata={"engine": engine},
                )
            return CheckResult(
                name=self.name,
                status=CheckStatus.FAIL,
                severity=self.severity,
                detail=f"Engine '{engine}' is not in the registry",
                metadata={"engine": engine},
            )
        except ImportError:
            return CheckResult(
                name=self.name,
                status=CheckStatus.SKIP,
                severity=self.severity,
                detail="src.core.engines not available in this environment",
            )


class FingerprintProbes:
    """Suite of fingerprint coherence probes."""

    SUITE_NAME = "fingerprint"
    DESCRIPTION = "Fingerprint coherence assertions from collected JSON"

    @staticmethod
    def probes() -> List[Probe]:
        return [
            FingerprintCoherenceProbe(),
            FingerprintFieldPresentProbe(),
            FingerprintEngineMatchProbe(),
        ]

    @staticmethod
    def run(ctx: ProbeContext) -> SuiteResult:
        suite = SuiteResult(
            name=FingerprintProbes.SUITE_NAME,
            description=FingerprintProbes.DESCRIPTION,
        )
        for probe in FingerprintProbes.probes():
            suite.checks.append(probe.execute(ctx))
        return suite


# ---------------------------------------------------------------------------
# Matrix Probes — engine/OS/site coverage planning
# ---------------------------------------------------------------------------


class MatrixPlanProbe(Probe):
    """Produce and validate the engine×OS×site coverage matrix plan."""

    name = "matrix_plan_valid"
    severity = "medium"

    def run(self, ctx: ProbeContext) -> CheckResult:
        from .matrix import build_matrix

        plan = build_matrix()
        plan_dict = plan.to_dict()
        total = plan_dict["total_cells"]
        if total == 0:
            return CheckResult(
                name=self.name,
                status=CheckStatus.FAIL,
                severity=self.severity,
                detail="Matrix plan produced zero cells",
            )
        # Every engine should have at least one planned cell
        engines_with_plans = set()
        for cell in plan.cells:
            if cell.status == "planned":
                engines_with_plans.add(cell.engine)
        if not engines_with_plans:
            return CheckResult(
                name=self.name,
                status=CheckStatus.FAIL,
                severity=self.severity,
                detail="No engines have any planned cells",
            )
        return CheckResult(
            name=self.name,
            status=CheckStatus.PASS,
            severity=self.severity,
            detail=f"Matrix valid: {total} cells, {len(engines_with_plans)} engines with plans",
            metadata={
                "total_cells": total,
                "engines": list(engines_with_plans),
                "sites": plan.sites,
                "os_families": plan.os_families,
            },
        )


class MatrixProbes:
    """Suite of matrix planning probes."""

    SUITE_NAME = "matrix"
    DESCRIPTION = "Engine × OS × site coverage matrix planning"

    @staticmethod
    def probes() -> List[Probe]:
        return [MatrixPlanProbe()]

    @staticmethod
    def run(ctx: ProbeContext) -> SuiteResult:
        suite = SuiteResult(
            name=MatrixProbes.SUITE_NAME,
            description=MatrixProbes.DESCRIPTION,
        )
        for probe in MatrixProbes.probes():
            suite.checks.append(probe.execute(ctx))
        return suite


# ---------------------------------------------------------------------------
# Live Public Probes — optional, honest prerequisite detection
# ---------------------------------------------------------------------------


class NetworkReachabilityProbe(Probe):
    """Honest check that outbound network is available.

    This is a *prerequisite* probe: its result determines whether downstream
    live-public probes should run or skip. If it fails, downstream probes
    will SKIP (not fail) because the prerequisite is absent.
    """

    name = "network_reachable"
    severity = "high"

    def run(self, ctx: ProbeContext) -> CheckResult:
        reachable = ctx.check_network()
        if reachable:
            return CheckResult(
                name=self.name,
                status=CheckStatus.PASS,
                severity=self.severity,
                detail="Outbound network reachable (DNS resolver port 53)",
            )
        return CheckResult(
            name=self.name,
            status=CheckStatus.SKIP,
            severity=self.severity,
            detail="Outbound network not reachable — live public probes will skip",
        )


class LivePublicSiteProbe(Probe):
    """Attempt a read-only HTTP GET against a public site.

    This probe is only meaningful when:
      1. Network is available
      2. A live browser session exists (for real fingerprint validation)
      3. A target site is specified

    If any prerequisite is absent, it SKIPS with an honest reason — never
    a fake PASS.
    """

    name = "live_public_site_reachable"
    severity = "medium"

    def run(self, ctx: ProbeContext) -> CheckResult:
        # Prerequisite 1: network
        if not ctx.check_network():
            return CheckResult(
                name=self.name,
                status=CheckStatus.SKIP,
                severity=self.severity,
                detail="Skipped: outbound network not reachable",
            )
        # Prerequisite 2: site specified
        if not ctx.site:
            return CheckResult(
                name=self.name,
                status=CheckStatus.SKIP,
                severity=self.severity,
                detail="Skipped: no target site specified",
            )
        # Prerequisite 3: live browser (we can't do a meaningful fingerprint
        # check without one; a bare HTTP GET would be testing the lab's own
        # network, not the browser's stealth)
        if not ctx.live_browser:
            return CheckResult(
                name=self.name,
                status=CheckStatus.SKIP,
                severity=self.severity,
                detail="Skipped: no live browser session available for fingerprint validation",
            )
        # Prerequisite 4: account (for login-flow sites)
        if "accounts.google.com" in ctx.site and not ctx.account_email:
            return CheckResult(
                name=self.name,
                status=CheckStatus.SKIP,
                severity=self.severity,
                detail="Skipped: Google login flow requires an account email",
            )

        # All prerequisites met — attempt the actual check
        getter = ctx.resolve_http_get()
        status, body, latency = getter(ctx.site, timeout=10.0)
        if status == 0:
            return CheckResult(
                name=self.name,
                status=CheckStatus.FAIL,
                severity=self.severity,
                detail=f"Site unreachable: {body}",
                metadata={"site": ctx.site},
            )
        if status >= 500:
            return CheckResult(
                name=self.name,
                status=CheckStatus.FAIL,
                severity=self.severity,
                detail=f"Server error {status} from {ctx.site}",
                metadata={"site": ctx.site, "status": status},
            )
        # 2xx or 3xx is a pass for reachability
        return CheckResult(
            name=self.name,
            status=CheckStatus.PASS,
            severity=self.severity,
            detail=f"Site {ctx.site} responded HTTP {status}",
            metadata={"site": ctx.site, "status": status, "latency_ms": round(latency, 2)},
        )


class LivePublicProbes:
    """Suite of optional live public checks.

    These probes are opt-in: they only run when all prerequisites are met.
    In CI or offline environments, they skip explicitly.
    """

    SUITE_NAME = "live_public"
    DESCRIPTION = "Optional live public-site checks (skip when prerequisites absent)"

    @staticmethod
    def probes() -> List[Probe]:
        return [NetworkReachabilityProbe(), LivePublicSiteProbe()]

    @staticmethod
    def run(ctx: ProbeContext) -> SuiteResult:
        suite = SuiteResult(
            name=LivePublicProbes.SUITE_NAME,
            description=LivePublicProbes.DESCRIPTION,
        )
        for probe in LivePublicProbes.probes():
            suite.checks.append(probe.execute(ctx))
        return suite
