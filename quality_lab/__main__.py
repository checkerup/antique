"""CLI entry point for the quality lab.

Usage:
    python -m quality_lab [options]
    python tools/quality_lab.py [options]

Options:
    --base-url URL     Antique API base URL (default: http://127.0.0.1:8080)
    --fingerprint FILE  Path to a collected fingerprint JSON file
    --suites LIST      Comma-separated suite names (default: all)
    --output FILE      Write JSON report to file
    --junit FILE       Write JUnit XML report to file
    --site URL         Target site for live public probes
    --live-browser     Assert that a live browser session is available
    --account-email E  Email for login-flow tests
    --redact           Redact secrets from the report output
    --summary          Print human-readable summary to stdout
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import List, Optional

from .probes import ProbeContext
from .runner import run_quality_lab
from .output import to_json, to_junit_xml, to_summary_text


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="quality_lab",
        description="Executable browser quality lab for Antique profiles.",
    )
    parser.add_argument(
        "--base-url",
        default="http://127.0.0.1:8080",
        help="Antique API base URL",
    )
    parser.add_argument(
        "--fingerprint",
        type=Path,
        default=None,
        help="Path to a collected fingerprint JSON file",
    )
    parser.add_argument(
        "--suites",
        default="all",
        help="Comma-separated suite names (default: all)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Write JSON report to file",
    )
    parser.add_argument(
        "--junit",
        type=Path,
        default=None,
        help="Write JUnit XML report to file",
    )
    parser.add_argument(
        "--site",
        default="",
        help="Target site for live public probes",
    )
    parser.add_argument(
        "--live-browser",
        action="store_true",
        help="Assert that a live browser session is available",
    )
    parser.add_argument(
        "--account-email",
        default=None,
        help="Email for login-flow tests",
    )
    parser.add_argument(
        "--redact",
        action="store_true",
        help="Redact secrets from the report output",
    )
    parser.add_argument(
        "--summary",
        action="store_true",
        help="Print human-readable summary to stdout",
    )
    return parser


def _load_fingerprint(path: Optional[Path]) -> Optional[dict]:
    if path is None or not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def _resolve_suites(suites_arg: str) -> Optional[List[str]]:
    if suites_arg.lower() == "all":
        return None
    return [s.strip() for s in suites_arg.split(",") if s.strip()]


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    fp_json = _load_fingerprint(args.fingerprint)
    suites = _resolve_suites(args.suites)

    ctx = ProbeContext(
        base_url=args.base_url,
        fingerprint_json=fp_json,
        site=args.site,
        live_browser=args.live_browser,
        account_email=args.account_email,
    )

    try:
        report = run_quality_lab(ctx, suites=suites)
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2

    if args.summary:
        print(to_summary_text(report))

    if args.output:
        args.output.write_text(
            to_json(report, redacted=args.redact), encoding="utf-8"
        )
        print(f"JSON report written to {args.output}", file=sys.stderr)

    if args.junit:
        args.junit.write_text(
            to_junit_xml(report), encoding="utf-8"
        )
        print(f"JUnit XML written to {args.junit}", file=sys.stderr)

    # Exit code: 0 = green, 1 = not green, 2 = usage error
    return 0 if report.is_green else 1


if __name__ == "__main__":
    raise SystemExit(main())
