"""Output formatters — JSON, JUnit XML, and human-readable summary."""
from __future__ import annotations

import json
import xml.etree.ElementTree as ET
from typing import Any, Dict

from .report import CheckStatus, QualityReport, SuiteResult


def to_json(report: QualityReport, redacted: bool = False) -> str:
    """Serialise a report to a JSON string.

    Args:
        report: the report to serialise.
        redacted: if True, run :func:`redact_report` on the dict first.
    """
    report_dict = report.to_dict()
    if redacted:
        from .redaction import redact_report

        report_dict = redact_report(report_dict)
    return json.dumps(report_dict, indent=2, ensure_ascii=False)


def to_junit_xml(report: QualityReport) -> str:
    """Convert a report to JUnit XML format.

    The JUnit format maps:
      - report  → <testsuites>
      - suite   → <testsuite>
      - check   → <testcase> with <failure>/<skipped>/<error> children

    JUnit conventions:
      - PASS  → <testcase> with no children
      - FAIL  → <testcase><failure message="..."/>
      - SKIP  → <testcase><skipped message="..."/>
      - ERROR → <testcase><error message="..."/>
    """
    report.compute_summary()
    total = report.summary.get("total_checks", 0)
    failures = report.summary.get("failed", 0)
    errors = report.summary.get("errored", 0)
    skipped = report.summary.get("skipped", 0)
    root = ET.Element("testsuites", {
        "tests": str(total), "failures": str(failures),
        "errors": str(errors), "skipped": str(skipped),
    })

    for suite in report.suites:
        s_total = suite.total
        s_fail = suite.failed
        s_err = suite.errored
        s_skip = suite.skipped
        suite_node = ET.SubElement(root, "testsuite", {
            "name": suite.name, "tests": str(s_total),
            "failures": str(s_fail), "errors": str(s_err),
            "skipped": str(s_skip),
        })

        for check in suite.checks:
            classname = f"quality_lab.{suite.name}"
            case = ET.SubElement(suite_node, "testcase", {
                "classname": classname,
                "name": check.name,
                "time": f"{check.duration_ms / 1000.0:.4f}",
            })
            if check.status == CheckStatus.FAIL:
                ET.SubElement(case, "failure", {"message": check.detail})
            elif check.status == CheckStatus.SKIP:
                ET.SubElement(case, "skipped", {"message": check.detail})
            elif check.status == CheckStatus.ERROR:
                ET.SubElement(case, "error", {"message": check.detail})

    return ET.tostring(root, encoding="unicode", xml_declaration=True)


def to_summary_text(report: QualityReport) -> str:
    """Human-readable one-line-per-suite summary."""
    report.compute_summary()
    lines = []
    lines.append(f"Quality Lab Report — {report.report_id} ({report.timestamp})")
    lines.append(f"Schema v{report.schema_version}")
    lines.append("")
    for suite in report.suites:
        status_emoji = "✅" if suite.is_green else "❌"
        lines.append(
            f"  {status_emoji} {suite.name:15s} "
            f"pass={suite.passed} fail={suite.failed} "
            f"skip={suite.skipped} error={suite.errored} "
            f"({suite.total} checks)"
        )
    lines.append("")
    s = report.summary
    overall = "PASS ✅" if s.get("all_green") else "FAIL ❌"
    lines.append(
        f"  Overall: {overall} "
        f"({s['passed']} passed, {s['failed']} failed, "
        f"{s['skipped']} skipped, {s['errored']} errored)"
    )
    return "\n".join(lines)
