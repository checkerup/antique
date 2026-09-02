"""Tests for quality-lab report schema, output formatters, redaction, and matrix.

These cover:
  - Report schema determinism (same inputs → same shape)
  - SuiteResult aggregation (pass/fail/skip/error counts, is_green)
  - QualityReport.to_dict / compute_summary
  - JSON and JUnit XML serialisation
  - Redaction patterns
  - Matrix plan construction and cell marking
"""
from __future__ import annotations

import json
import re
import xml.etree.ElementTree as ET

import pytest

from quality_lab.report import (
    CheckResult,
    CheckStatus,
    QualityReport,
    SuiteResult,
)
from quality_lab.output import to_json, to_junit_xml, to_summary_text
from quality_lab.redaction import redact_artifact, redact_report, redact_text
from quality_lab.matrix import build_matrix, MatrixCell, MatrixPlan


# ===========================================================================
# Report schema
# ===========================================================================


class TestCheckStatus:
    def test_four_statuses(self):
        assert CheckStatus.PASS.value == "pass"
        assert CheckStatus.FAIL.value == "fail"
        assert CheckStatus.SKIP.value == "skip"
        assert CheckStatus.ERROR.value == "error"

    def test_is_terminal_failure(self):
        assert CheckStatus.FAIL.is_terminal_failure
        assert CheckStatus.ERROR.is_terminal_failure
        assert not CheckStatus.PASS.is_terminal_failure
        assert not CheckStatus.SKIP.is_terminal_failure


class TestCheckResult:
    def test_to_dict_has_all_fields(self):
        r = CheckResult(
            name="test",
            status=CheckStatus.PASS,
            severity="critical",
            detail="ok",
            duration_ms=1.5,
            metadata={"key": "val"},
        )
        d = r.to_dict()
        assert d["name"] == "test"
        assert d["status"] == "pass"
        assert d["severity"] == "critical"
        assert d["detail"] == "ok"
        assert d["duration_ms"] == 1.5
        assert d["metadata"] == {"key": "val"}


class TestSuiteResult:
    def _suite(self, statuses):
        checks = []
        for i, s in enumerate(statuses):
            checks.append(CheckResult(name=f"check_{i}", status=s))
        return SuiteResult(name="test", checks=checks)

    def test_counts_all_pass(self):
        s = self._suite([CheckStatus.PASS, CheckStatus.PASS, CheckStatus.PASS])
        assert s.passed == 3
        assert s.failed == 0
        assert s.skipped == 0
        assert s.errored == 0
        assert s.total == 3
        assert s.is_green

    def test_counts_mixed(self):
        s = self._suite([CheckStatus.PASS, CheckStatus.FAIL, CheckStatus.SKIP, CheckStatus.ERROR])
        assert s.passed == 1
        assert s.failed == 1
        assert s.skipped == 1
        assert s.errored == 1
        assert s.total == 4
        assert not s.is_green

    def test_skip_is_green(self):
        """A suite with only skips and passes is green (skip != failure)."""
        s = self._suite([CheckStatus.PASS, CheckStatus.SKIP, CheckStatus.SKIP])
        assert s.is_green

    def test_to_dict(self):
        s = self._suite([CheckStatus.PASS, CheckStatus.FAIL])
        d = s.to_dict()
        assert d["name"] == "test"
        assert d["passed"] == 1
        assert d["failed"] == 1
        assert d["is_green"] is False
        assert len(d["checks"]) == 2


class TestQualityReport:
    def test_schema_version_pinned(self):
        r = QualityReport()
        assert r.schema_version == "1.0.0"

    def test_report_id_generated(self):
        r1 = QualityReport()
        r2 = QualityReport()
        assert r1.report_id != r2.report_id
        assert len(r1.report_id) == 12

    def test_compute_summary_all_green(self):
        r = QualityReport()
        r.add_suite(SuiteResult(
            name="s1",
            checks=[
                CheckResult(name="a", status=CheckStatus.PASS),
                CheckResult(name="b", status=CheckStatus.PASS),
            ],
        ))
        r.add_suite(SuiteResult(
            name="s2",
            checks=[
                CheckResult(name="c", status=CheckStatus.PASS),
                CheckResult(name="d", status=CheckStatus.SKIP),
            ],
        ))
        r.compute_summary()
        assert r.summary["total_suites"] == 2
        assert r.summary["total_checks"] == 4
        assert r.summary["passed"] == 3
        assert r.summary["skipped"] == 1
        assert r.summary["failed"] == 0
        assert r.summary["errored"] == 0
        assert r.summary["all_green"] is True
        assert r.summary["status"] == "pass"
        assert r.is_green

    def test_compute_summary_not_green(self):
        r = QualityReport()
        r.add_suite(SuiteResult(
            name="s1",
            checks=[
                CheckResult(name="a", status=CheckStatus.PASS),
                CheckResult(name="b", status=CheckStatus.FAIL),
            ],
        ))
        r.compute_summary()
        assert r.summary["all_green"] is False
        assert r.summary["status"] == "fail"
        assert not r.is_green

    def test_to_dict_round_trip(self):
        r = QualityReport()
        r.add_suite(SuiteResult(
            name="s1",
            checks=[CheckResult(name="a", status=CheckStatus.PASS)],
        ))
        r.environment = {"base_url": "http://localhost"}
        d = r.to_dict()
        assert "schema_version" in d
        assert "report_id" in d
        assert "timestamp" in d
        assert "environment" in d
        assert "summary" in d
        assert "suites" in d
        assert d["suites"][0]["name"] == "s1"
        # Summary is computed during to_dict
        assert d["summary"]["total_checks"] == 1

    def test_empty_report_is_green(self):
        r = QualityReport()
        r.compute_summary()
        assert r.is_green  # no suites → vacuously green
        assert r.summary["total_suites"] == 0


# ===========================================================================
# JSON output
# ===========================================================================


class TestJsonOutput:
    def test_to_json_is_valid_json(self):
        r = QualityReport()
        r.add_suite(SuiteResult(
            name="s",
            checks=[CheckResult(name="a", status=CheckStatus.PASS)],
        ))
        text = to_json(r)
        parsed = json.loads(text)
        assert parsed["schema_version"] == "1.0.0"
        assert parsed["suites"][0]["checks"][0]["status"] == "pass"

    def test_to_json_redacted(self):
        r = QualityReport()
        r.add_suite(SuiteResult(
            name="s",
            checks=[CheckResult(
                name="a",
                status=CheckStatus.PASS,
                detail="email: user@example.com",
                metadata={"ip": "203.0.113.42"},
            )],
        ))
        text = to_json(r, redacted=True)
        parsed = json.loads(text)
        detail = parsed["suites"][0]["checks"][0]["detail"]
        assert "user@example.com" not in detail
        assert "[REDACTED:email]" in detail
        ip = parsed["suites"][0]["checks"][0]["metadata"]["ip"]
        assert "203.0.113.42" not in ip
        assert "[REDACTED:ip]" in ip


# ===========================================================================
# JUnit XML output
# ===========================================================================


class TestJUnitXml:
    def test_well_formed_xml(self):
        r = QualityReport()
        r.add_suite(SuiteResult(
            name="smoke",
            checks=[
                CheckResult(name="a", status=CheckStatus.PASS),
                CheckResult(name="b", status=CheckStatus.FAIL, detail="boom"),
                CheckResult(name="c", status=CheckStatus.SKIP, detail="no network"),
                CheckResult(name="d", status=CheckStatus.ERROR, detail="crash"),
            ],
        ))
        xml = to_junit_xml(r)
        root = ET.fromstring(xml)
        assert root.tag == "testsuites"
        assert root.get("failures") == "1"
        assert root.get("errors") == "1"
        assert root.get("skipped") == "1"

        suite = root[0]
        assert suite.tag == "testsuite"
        assert suite.get("name") == "smoke"
        assert suite.get("tests") == "4"

        # PASS → no child
        assert len(suite[0]) == 0
        # FAIL → <failure>
        assert suite[1][0].tag == "failure"
        # SKIP → <skipped>
        assert suite[2][0].tag == "skipped"
        # ERROR → <error>
        assert suite[3][0].tag == "error"

    def test_empty_report_junit(self):
        r = QualityReport()
        xml = to_junit_xml(r)
        root = ET.fromstring(xml)
        assert root.get("tests") == "0"
        assert root.get("failures") == "0"

    def test_junit_escapes_special_chars(self):
        r = QualityReport()
        r.add_suite(SuiteResult(
            name="s",
            checks=[CheckResult(
                name="a",
                status=CheckStatus.FAIL,
                detail='<script>alert("xss")</script> & more',
            )],
        ))
        xml = to_junit_xml(r)
        # Must be parseable XML — escape() handles <, >, & but not quotes in
        # attribute values. The XML parser will succeed because our detail
        # goes into a message="" attribute and escape() covers & < >.
        root = ET.fromstring(xml)
        assert root is not None  # valid XML despite special chars


# ===========================================================================
# Summary text
# ===========================================================================


class TestSummaryText:
    def test_contains_key_sections(self):
        r = QualityReport()
        r.add_suite(SuiteResult(
            name="smoke",
            checks=[CheckResult(name="a", status=CheckStatus.PASS)],
        ))
        text = to_summary_text(r)
        assert "Quality Lab Report" in text
        assert "smoke" in text
        assert "Overall" in text
        assert "PASS" in text


# ===========================================================================
# Redaction
# ===========================================================================


class TestRedaction:
    def test_redact_email(self):
        text = "Contact user@example.com for details"
        result = redact_text(text)
        assert "user@example.com" not in result
        assert "[REDACTED:email]" in result

    def test_redact_bearer_token(self):
        text = "Authorization: Bearer abc123xyz456"
        result = redact_text(text)
        assert "abc123xyz456" not in result
        assert "[REDACTED:token]" in result

    def test_redact_ipv4(self):
        text = "Connecting to 203.0.113.42"
        result = redact_text(text)
        assert "203.0.113.42" not in result
        assert "[REDACTED:ip]" in result

    def test_does_not_redact_localhost(self):
        text = "Server at 127.0.0.1:8080"
        result = redact_text(text)
        assert "127.0.0.1" in result

    def test_redact_password_in_json(self):
        text = '{"password": "secret123"}'
        result = redact_text(text)
        assert "secret123" not in result
        assert "[REDACTED:password]" in result

    def test_redact_dict_recursive(self):
        obj = {
            "user": "test@example.com",
            "config": {"server_ip": "198.51.100.1"},
            "list": ["token: Bearer xyz123abc456"],
        }
        result = redact_artifact(obj)
        assert "test@example.com" not in result["user"]
        assert "198.51.100.1" not in result["config"]["server_ip"]
        assert "xyz123abc456" not in result["list"][0]

    def test_redact_report(self):
        report_dict = {
            "schema_version": "1.0.0",
            "report_id": "abc123",
            "timestamp": "2026-01-01T00:00:00Z",
            "environment": {"base_url": "http://admin:pass@203.0.113.5:8080"},
            "summary": {"status": "pass"},
            "suites": [{
                "name": "smoke",
                "description": "",
                "checks": [{
                    "name": "probe1",
                    "status": "pass",
                    "severity": "high",
                    "detail": "Connected to 203.0.113.42",
                    "duration_ms": 10.0,
                    "metadata": {"url": "http://user@example.com"},
                }],
            }],
        }
        redacted = redact_report(report_dict)
        check = redacted["suites"][0]["checks"][0]
        assert "203.0.113.42" not in check["detail"]
        assert "user@example.com" not in check["metadata"]["url"]

    def test_redact_preserves_non_string_types(self):
        obj = {"count": 42, "ratio": 0.95, "flag": True, "none": None}
        result = redact_artifact(obj)
        assert result["count"] == 42
        assert result["ratio"] == 0.95
        assert result["flag"] is True
        assert result["none"] is None


# ===========================================================================
# Matrix
# ===========================================================================


class TestMatrix:
    def test_default_matrix_has_all_engines(self):
        plan = build_matrix()
        assert "chromium" in plan.engines
        assert "camoufox" in plan.engines
        assert "webkit" in plan.engines

    def test_default_matrix_has_all_oss(self):
        plan = build_matrix()
        assert "windows" in plan.os_families
        assert "macos" in plan.os_families
        assert "linux" in plan.os_families

    def test_total_cells_equals_product(self):
        plan = build_matrix()
        expected = len(plan.engines) * len(plan.os_families) * len(plan.sites)
        assert plan.to_dict()["total_cells"] == expected

    def test_unsupported_cells_marked(self):
        """WebKit is meaningful on all OS families, so no unsupported expected."""
        plan = build_matrix()
        # All engines support all three OS families in our model
        unsupported = [c for c in plan.cells if c.status == "unsupported"]
        assert len(unsupported) == 0

    def test_mark_covered(self):
        plan = build_matrix()
        plan.mark_covered("chromium", "windows", "https://accounts.google.com")
        covered = [c for c in plan.cells if c.status == "covered"]
        assert len(covered) == 1
        assert covered[0].engine == "chromium"
        assert covered[0].os_family == "windows"

    def test_mark_skip(self):
        plan = build_matrix()
        plan.mark_skip("webkit", "linux", "https://okx.com", "no webkit on linux ci")
        skipped = [c for c in plan.cells if c.status == "skip"]
        assert len(skipped) == 1
        assert skipped[0].reason == "no webkit on linux ci"

    def test_custom_engines_oss_sites(self):
        plan = build_matrix(
            engines=["chromium"],
            os_families=["windows"],
            sites=["https://example.com"],
        )
        assert len(plan.cells) == 1
        assert plan.cells[0].engine == "chromium"
        assert plan.cells[0].os_family == "windows"
        assert plan.cells[0].site == "https://example.com"

    def test_matrix_to_dict(self):
        plan = build_matrix(
            engines=["chromium"],
            os_families=["windows"],
            sites=["https://example.com"],
        )
        d = plan.to_dict()
        assert d["total_cells"] == 1
        assert d["planned"] == 1
        assert d["covered"] == 0
