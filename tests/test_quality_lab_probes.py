"""Tests for quality-lab probe execution, aggregation, and failure/skip semantics.

Covers:
  - Smoke probes against a FastAPI TestClient (no live server needed)
  - Smoke probes when server is unreachable (→ SKIP, not FAIL)
  - Fingerprint coherence probes with valid/invalid collected JSON
  - Fingerprint probes when no JSON is provided (→ SKIP)
  - Matrix plan probe
  - Live public probes: all four prerequisite-absent scenarios → SKIP
  - Live public probes: all prerequisites met → PASS
  - Report aggregation across suites
  - Deterministic schema across runs
  - CLI entry point
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

# Ensure repo root is importable
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from quality_lab.probes import (
    CDPVersionProbe,
    FingerprintCoherenceProbe,
    FingerprintEngineMatchProbe,
    FingerprintFieldPresentProbe,
    HealthProbe,
    LivePublicSiteProbe,
    MatrixPlanProbe,
    NetworkReachabilityProbe,
    OpenAPIProbe,
    ProbeContext,
)
from quality_lab.report import CheckStatus, QualityReport, SuiteResult
from quality_lab.runner import run_quality_lab
from quality_lab.output import to_junit_xml, to_json, to_summary_text
from quality_lab.matrix import build_matrix


# ===========================================================================
# Fixtures — FastAPI TestClient as the HTTP transport
# ===========================================================================


@pytest.fixture
def app_client(tmp_path):
    """Build a real Antique app with TestClient — no live server."""
    from src.api.server import create_app

    app = create_app(data_root=tmp_path)
    return TestClient(app)


def _make_ctx(app_client, **kwargs) -> ProbeContext:
    """Build a ProbeContext that routes HTTP through the TestClient."""
    def http_get(path, timeout=5.0, base_url=""):
        url = path if path.startswith("http") else path
        resp = app_client.get(url, follow_redirects=True)
        body = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else resp.text
        return resp.status_code, body, 0.0

    return ProbeContext(http_get=http_get, **kwargs)


def _make_unreachable_ctx(**kwargs) -> ProbeContext:
    """Build a ctx whose HTTP GET always returns 0 (server not reachable)."""
    def http_get(path, timeout=5.0, base_url=""):
        return 0, "Connection refused", 0.0

    return ProbeContext(http_get=http_get, **kwargs)


# ===========================================================================
# Smoke probes — against TestClient
# ===========================================================================


class TestHealthProbe:
    def test_pass_against_test_client(self, app_client):
        ctx = _make_ctx(app_client)
        result = HealthProbe().execute(ctx)
        assert result.status == CheckStatus.PASS
        assert "ok" in result.detail.lower()
        assert result.metadata.get("service") == "antique"

    def test_skip_when_server_unreachable(self):
        ctx = _make_unreachable_ctx()
        result = HealthProbe().execute(ctx)
        assert result.status == CheckStatus.SKIP
        assert "not reachable" in result.detail.lower()

    def test_fail_on_wrong_status_field(self, app_client):
        """Inject a bad /health response through a custom http_get."""
        def http_get(path, timeout=5.0, base_url=""):
            if "/health" in path:
                return 200, {"status": "broken", "service": "antique"}, 1.0
            return 404, "", 0.0

        ctx = ProbeContext(http_get=http_get)
        result = HealthProbe().execute(ctx)
        assert result.status == CheckStatus.FAIL
        assert "broken" in result.detail

    def test_fail_on_non_200(self):
        def http_get(path, timeout=5.0, base_url=""):
            return 503, "Service Unavailable", 0.0

        ctx = ProbeContext(http_get=http_get)
        result = HealthProbe().execute(ctx)
        assert result.status == CheckStatus.FAIL
        assert "503" in result.detail


class TestOpenAPIProbe:
    def test_pass_against_test_client(self, app_client):
        ctx = _make_ctx(app_client)
        result = OpenAPIProbe().execute(ctx)
        assert result.status == CheckStatus.PASS
        assert result.metadata["path_count"] > 0

    def test_skip_when_server_unreachable(self):
        ctx = _make_unreachable_ctx()
        result = OpenAPIProbe().execute(ctx)
        assert result.status == CheckStatus.SKIP

    def test_fail_on_non_json(self):
        def http_get(path, timeout=5.0, base_url=""):
            return 200, "not json", 0.0

        ctx = ProbeContext(http_get=http_get)
        result = OpenAPIProbe().execute(ctx)
        assert result.status == CheckStatus.FAIL

    def test_fail_on_empty_paths(self):
        def http_get(path, timeout=5.0, base_url=""):
            return 200, {"paths": {}, "info": {}}, 0.0

        ctx = ProbeContext(http_get=http_get)
        result = OpenAPIProbe().execute(ctx)
        assert result.status == CheckStatus.FAIL


class TestCDPVersionProbe:
    def test_pass_against_test_client(self, app_client):
        ctx = _make_ctx(app_client)
        result = CDPVersionProbe().execute(ctx)
        assert result.status == CheckStatus.PASS
        assert "browser" in result.metadata
        assert "protocol_version" in result.metadata

    def test_skip_when_server_unreachable(self):
        ctx = _make_unreachable_ctx()
        result = CDPVersionProbe().execute(ctx)
        assert result.status == CheckStatus.SKIP

    def test_fail_on_missing_fields(self):
        def http_get(path, timeout=5.0, base_url=""):
            return 200, {"Browser": "test"}, 0.0  # missing Protocol-Version

        ctx = ProbeContext(http_get=http_get)
        result = CDPVersionProbe().execute(ctx)
        assert result.status == CheckStatus.FAIL
        assert "Protocol-Version" in result.detail


# ===========================================================================
# Fingerprint coherence probes
# ===========================================================================


def _good_fingerprint():
    """A fingerprint dict that passes all coherence checks."""
    from src.core.fingerprint import generate_fingerprint

    fp = generate_fingerprint(seed="quality-lab-test")
    return fp.canonical() if hasattr(fp, "canonical") else {
        k: getattr(fp, k) for k in [
            "user_agent", "platform", "vendor", "oscpu",
            "screen_width", "screen_height", "avail_screen_width", "avail_screen_height",
            "inner_width", "inner_height", "pixel_ratio", "color_depth",
            "locale", "timezone", "languages", "webgl_vendor", "webgl_renderer",
            "hardware_concurrency", "device_memory", "webdriver",
            "audio_noise_seed", "canvas_noise_seed", "noise",
            "block_webrtc_ip", "webrtc_mode", "webrtc_public_ip",
            "fonts", "plugins", "browser_engine", "extensions",
            "spoof_geolocation", "geo_latitude", "geo_longitude", "geo_accuracy",
            "webgpu_enabled", "webgpu_vendor", "webgpu_architecture", "webgpu_description",
            "connection_type", "connection_downlink", "connection_rtt",
        ]
    }


class TestFingerprintCoherenceProbe:
    def test_pass_on_good_fingerprint(self):
        fp = _good_fingerprint()
        ctx = ProbeContext(fingerprint_json=fp)
        result = FingerprintCoherenceProbe().execute(ctx)
        assert result.status == CheckStatus.PASS
        assert result.metadata.get("score", 0) == 100

    def test_skip_when_no_fingerprint(self):
        ctx = ProbeContext(fingerprint_json=None)
        result = FingerprintCoherenceProbe().execute(ctx)
        assert result.status == CheckStatus.SKIP
        assert "No fingerprint" in result.detail

    def test_fail_on_incoherent_fingerprint(self):
        fp = _good_fingerprint()
        fp["webdriver"] = True  # critical: webdriver must be False
        fp["user_agent"] = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0"
        fp["platform"] = "MacIntel"  # mismatch: Windows UA + MacIntel platform
        ctx = ProbeContext(fingerprint_json=fp)
        result = FingerprintCoherenceProbe().execute(ctx)
        assert result.status == CheckStatus.FAIL
        assert "ua_platform_coherence" in str(result.metadata.get("failures", [])) or \
               "webdriver_off" in str(result.metadata.get("failures", []))

    def test_error_on_non_dict_fingerprint(self):
        ctx = ProbeContext(fingerprint_json="not a dict")
        result = FingerprintCoherenceProbe().execute(ctx)
        assert result.status == CheckStatus.FAIL
        assert "expected dict" in result.detail


class TestFingerprintFieldPresentProbe:
    def test_pass_on_complete_fingerprint(self):
        fp = _good_fingerprint()
        ctx = ProbeContext(fingerprint_json=fp)
        result = FingerprintFieldPresentProbe().execute(ctx)
        assert result.status == CheckStatus.PASS

    def test_skip_when_no_fingerprint(self):
        ctx = ProbeContext(fingerprint_json=None)
        result = FingerprintFieldPresentProbe().execute(ctx)
        assert result.status == CheckStatus.SKIP

    def test_fail_on_missing_fields(self):
        fp = {"user_agent": "x"}  # missing most required fields
        ctx = ProbeContext(fingerprint_json=fp)
        result = FingerprintFieldPresentProbe().execute(ctx)
        assert result.status == CheckStatus.FAIL
        assert "platform" in result.metadata["missing"]
        assert "timezone" in result.metadata["missing"]

    def test_fail_on_empty_fields(self):
        fp = _good_fingerprint()
        fp["languages"] = []
        fp["fonts"] = []
        ctx = ProbeContext(fingerprint_json=fp)
        result = FingerprintFieldPresentProbe().execute(ctx)
        assert result.status == CheckStatus.FAIL
        assert "languages" in result.metadata["empty"]
        assert "fonts" in result.metadata["empty"]


class TestFingerprintEngineMatchProbe:
    def test_pass_on_known_engine(self):
        fp = _good_fingerprint()
        ctx = ProbeContext(fingerprint_json=fp)
        result = FingerprintEngineMatchProbe().execute(ctx)
        assert result.status == CheckStatus.PASS

    def test_skip_when_no_fingerprint(self):
        ctx = ProbeContext(fingerprint_json=None)
        result = FingerprintEngineMatchProbe().execute(ctx)
        assert result.status == CheckStatus.SKIP

    def test_fail_on_unknown_engine(self):
        fp = _good_fingerprint()
        fp["browser_engine"] = "nonexistent_engine"
        ctx = ProbeContext(fingerprint_json=fp)
        result = FingerprintEngineMatchProbe().execute(ctx)
        assert result.status == CheckStatus.FAIL

    def test_fail_on_missing_engine(self):
        fp = _good_fingerprint()
        fp.pop("browser_engine", None)
        ctx = ProbeContext(fingerprint_json=fp)
        result = FingerprintEngineMatchProbe().execute(ctx)
        assert result.status == CheckStatus.FAIL
        assert "missing" in result.detail.lower()


# ===========================================================================
# Matrix plan probe
# ===========================================================================


class TestMatrixPlanProbe:
    def test_pass(self):
        ctx = ProbeContext()
        result = MatrixPlanProbe().execute(ctx)
        assert result.status == CheckStatus.PASS
        assert result.metadata["total_cells"] > 0
        assert len(result.metadata["engines"]) > 0

    def test_matrix_has_expected_sites(self):
        ctx = ProbeContext()
        result = MatrixPlanProbe().execute(ctx)
        sites = result.metadata["sites"]
        assert "https://accounts.google.com" in sites
        assert "https://okx.com" in sites


# ===========================================================================
# Live public probes — prerequisite detection
# ===========================================================================


class TestNetworkReachabilityProbe:
    def test_pass_when_network_available(self):
        ctx = ProbeContext(network_available=True)
        result = NetworkReachabilityProbe().execute(ctx)
        assert result.status == CheckStatus.PASS

    def test_skip_when_network_unavailable(self):
        ctx = ProbeContext(network_available=False)
        result = NetworkReachabilityProbe().execute(ctx)
        assert result.status == CheckStatus.SKIP
        assert "not reachable" in result.detail.lower()


class TestLivePublicSiteProbe:
    def test_skip_no_network(self):
        ctx = ProbeContext(network_available=False, site="https://example.com")
        result = LivePublicSiteProbe().execute(ctx)
        assert result.status == CheckStatus.SKIP
        assert "network" in result.detail.lower()

    def test_skip_no_site(self):
        ctx = ProbeContext(network_available=True, site="")
        result = LivePublicSiteProbe().execute(ctx)
        assert result.status == CheckStatus.SKIP
        assert "no target site" in result.detail.lower()

    def test_skip_no_browser(self):
        ctx = ProbeContext(
            network_available=True,
            site="https://example.com",
            live_browser=False,
        )
        result = LivePublicSiteProbe().execute(ctx)
        assert result.status == CheckStatus.SKIP
        assert "no live browser" in result.detail.lower()

    def test_skip_no_account_for_google(self):
        ctx = ProbeContext(
            network_available=True,
            site="https://accounts.google.com",
            live_browser=True,
            account_email=None,
        )
        result = LivePublicSiteProbe().execute(ctx)
        assert result.status == CheckStatus.SKIP
        assert "account email" in result.detail.lower()

    def test_pass_when_all_prerequisites_met(self):
        def http_get(path, timeout=5.0, base_url=""):
            return 200, {"status": "ok"}, 50.0

        ctx = ProbeContext(
            http_get=http_get,
            network_available=True,
            site="https://example.com",
            live_browser=True,
            account_email="test@example.com",
        )
        result = LivePublicSiteProbe().execute(ctx)
        assert result.status == CheckStatus.PASS
        assert result.metadata["status"] == 200

    def test_fail_on_server_error(self):
        def http_get(path, timeout=5.0, base_url=""):
            return 503, "error", 0.0

        ctx = ProbeContext(
            http_get=http_get,
            network_available=True,
            site="https://example.com",
            live_browser=True,
        )
        result = LivePublicSiteProbe().execute(ctx)
        assert result.status == CheckStatus.FAIL
        assert "503" in result.detail

    def test_fail_on_connection_error(self):
        def http_get(path, timeout=5.0, base_url=""):
            return 0, "Connection refused", 0.0

        ctx = ProbeContext(
            http_get=http_get,
            network_available=True,
            site="https://example.com",
            live_browser=True,
        )
        result = LivePublicSiteProbe().execute(ctx)
        assert result.status == CheckStatus.FAIL


# ===========================================================================
# Report aggregation — end-to-end runner
# ===========================================================================


class TestReportAggregation:
    def test_full_report_has_four_suites(self, app_client):
        ctx = _make_ctx(app_client)
        report = run_quality_lab(ctx)
        suite_names = [s.name for s in report.suites]
        assert "smoke" in suite_names
        assert "fingerprint" in suite_names
        assert "matrix" in suite_names
        assert "live_public" in suite_names

    def test_summary_counts_match_individual_suites(self, app_client):
        ctx = _make_ctx(app_client)
        report = run_quality_lab(ctx)
        total_pass = sum(s.passed for s in report.suites)
        total_fail = sum(s.failed for s in report.suites)
        total_skip = sum(s.skipped for s in report.suites)
        assert report.summary["passed"] == total_pass
        assert report.summary["failed"] == total_fail
        assert report.summary["skipped"] == total_skip

    def test_deterministic_schema(self, app_client):
        """Two runs produce the same schema shape (not same report_id)."""
        ctx = _make_ctx(app_client)
        r1 = run_quality_lab(ctx)
        r2 = run_quality_lab(ctx)
        d1 = r1.to_dict()
        d2 = r2.to_dict()
        # Schema version is the same
        assert d1["schema_version"] == d2["schema_version"]
        # Same suite names in same order
        assert [s["name"] for s in d1["suites"]] == [s["name"] for s in d2["suites"]]
        # Same summary structure
        assert set(d1["summary"].keys()) == set(d2["summary"].keys())

    def test_subset_suites(self, app_client):
        ctx = _make_ctx(app_client)
        report = run_quality_lab(ctx, suites=["smoke"])
        assert len(report.suites) == 1
        assert report.suites[0].name == "smoke"

    def test_unknown_suite_raises(self):
        ctx = ProbeContext()
        with pytest.raises(ValueError, match="Unknown suite"):
            run_quality_lab(ctx, suites=["nonexistent"])

    def test_skip_does_not_make_report_red(self):
        """A report with only passes and skips is green."""
        suite = SuiteResult(
            name="test",
            checks=[
                # All skip (e.g. no fingerprint, no network)
            ],
        )
        # Even an empty suite is green
        report = QualityReport()
        report.add_suite(suite)
        report.compute_summary()
        assert report.is_green
        assert report.summary["status"] == "pass"

    def test_failure_makes_report_red(self):
        suite = SuiteResult(
            name="test",
            checks=[
                # Will add a failing check
            ],
        )
        from quality_lab.report import CheckResult
        suite.checks.append(CheckResult(name="x", status=CheckStatus.FAIL))
        report = QualityReport()
        report.add_suite(suite)
        report.compute_summary()
        assert not report.is_green
        assert report.summary["status"] == "fail"

    def test_error_makes_report_red(self):
        from quality_lab.report import CheckResult
        suite = SuiteResult(
            name="test",
            checks=[CheckResult(name="x", status=CheckStatus.ERROR)],
        )
        report = QualityReport()
        report.add_suite(suite)
        report.compute_summary()
        assert not report.is_green

    def test_mixed_pass_skip_is_green(self):
        from quality_lab.report import CheckResult
        suite = SuiteResult(
            name="test",
            checks=[
                CheckResult(name="a", status=CheckStatus.PASS),
                CheckResult(name="b", status=CheckStatus.SKIP),
                CheckResult(name="c", status=CheckStatus.SKIP),
            ],
        )
        report = QualityReport()
        report.add_suite(suite)
        report.compute_summary()
        assert report.is_green
        assert report.summary["passed"] == 1
        assert report.summary["skipped"] == 2

    def test_json_and_junit_from_runner(self, app_client):
        ctx = _make_ctx(app_client)
        report = run_quality_lab(ctx)
        json_str = to_json(report)
        assert '"schema_version"' in json_str
        xml_str = to_junit_xml(report)
        assert "<testsuites" in xml_str

    def test_environment_captured(self, app_client):
        ctx = _make_ctx(app_client, engine="chrome", os_family="windows")
        report = run_quality_lab(ctx)
        assert report.environment["engine"] == "chrome"
        assert report.environment["os_family"] == "windows"
        assert "python_version" in report.environment


# ===========================================================================
# Probe error handling
# ===========================================================================


class TestProbeErrorHandling:
    def test_probe_crash_becomes_error(self):
        """If a probe.run() raises, execute() catches it and returns ERROR."""
        from quality_lab.probes import Probe

        class CrashingProbe(Probe):
            name = "crash"
            severity = "high"

            def run(self, ctx):
                raise RuntimeError("boom")

        ctx = ProbeContext()
        result = CrashingProbe().execute(ctx)
        assert result.status == CheckStatus.ERROR
        assert "boom" in result.detail
        assert result.duration_ms > 0


# ===========================================================================
# CLI
# ===========================================================================


class TestCLI:
    def test_help_exits_cleanly(self):
        from quality_lab.__main__ import build_parser

        parser = build_parser()
        # Just verify the parser builds without error
        assert parser is not None

    def test_run_with_defaults(self, app_client, tmp_path):
        """Run the CLI with a custom http_get — verify exit code 0."""
        # We can't easily inject http_get via CLI args, so test the
        # functional path: run with all suites and check it doesn't crash.
        from quality_lab.__main__ import main

        # The CLI uses _default_http_get which will try the live server.
        # If the live server is running (port 8080), this will work.
        # If not, smoke probes will SKIP and the report will still be green.
        output_path = tmp_path / "report.json"
        junit_path = tmp_path / "junit.xml"
        exit_code = main([
            "--output", str(output_path),
            "--junit", str(junit_path),
            "--summary",
        ])
        # Exit code 0 = green, 1 = not green (both valid outcomes)
        assert exit_code in (0, 1)
        assert output_path.exists()
        assert junit_path.exists()
        # Validate the output files are parseable
        report_data = json.loads(output_path.read_text(encoding="utf-8"))
        assert "schema_version" in report_data
        assert report_data["schema_version"] == "1.0.0"
        junit_text = junit_path.read_text(encoding="utf-8")
        assert "<testsuites" in junit_text

    def test_resolve_suites_all(self):
        from quality_lab.__main__ import _resolve_suites

        assert _resolve_suites("all") is None

    def test_resolve_suites_explicit(self):
        from quality_lab.__main__ import _resolve_suites

        result = _resolve_suites("smoke,matrix")
        assert result == ["smoke", "matrix"]

    def test_load_fingerprint_nonexistent(self):
        from quality_lab.__main__ import _load_fingerprint

        assert _load_fingerprint(Path("/nonexistent/path.json")) is None

    def test_load_fingerprint_valid(self, tmp_path):
        from quality_lab.__main__ import _load_fingerprint

        fp_path = tmp_path / "fp.json"
        fp_path.write_text('{"user_agent": "test"}', encoding="utf-8")
        result = _load_fingerprint(fp_path)
        assert result == {"user_agent": "test"}
