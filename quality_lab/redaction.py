"""Artifact redaction — strip secrets from quality-lab outputs.

When the lab collects probe artifacts (HTTP responses, fingerprint JSON,
log excerpts), those artifacts may contain sensitive data: API tokens, email
addresses, real IP addresses, cookie values. This module provides deterministic
redaction so that reports can be shared or persisted without leaking.

The redaction is pattern-based and conservative: it redacts anything that
*looks* like a secret, even if that means some false positives. A redacted
value is replaced with ``[REDACTED:<kind>]`` so the consumer can see *what*
was removed without seeing the value.
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Union


# ---------------------------------------------------------------------------
# Patterns — ordered from most specific to most general
# ---------------------------------------------------------------------------

_PATTERNS: List[tuple[str, str, str]] = [
    # Bearer tokens / Authorization headers
    (r"(?i)(bearer\s+)[A-Za-z0-9\-._~+\/]+", r"\1[REDACTED:token]"),
    # Authorization header value (non-Bearer)
    (r"(?i)(\"authorization\"\s*[:=]\s*\")[^\"]+", r"\1[REDACTED:auth]"),
    # API keys (common env-var names followed by a value)
    (r"(?i)((?:api[_-]?key|api[_-]?secret|access[_-]?token|secret[_-]?key)\s*[:=]\s*)[\"\']?[A-Za-z0-9\-_]{16,}", r"\1[REDACTED:key]"),
    # Email addresses
    (r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}", "[REDACTED:email]"),
    # IPv4 addresses (but not 127.0.0.1 or 0.0.0.0 — those are safe)
    (r"\b(?!127\.0\.0\.1|0\.0\.0\.0|255\.255\.255\.255)(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})\b", "[REDACTED:ip]"),
    # Cookie values (key=value pairs that look like session cookies)
    (r"(?i)(cookie\s*[:=]\s*)[\"\']?[^;\"'\s,]+", r"\1[REDACTED:cookie]"),
    # Passwords in JSON-like structures
    (r"(?i)(\"password\"\s*:\s*\")[^\"]*", r"\1[REDACTED:password]"),
    # Phone numbers (E.164 or common formats)
    (r"\+?\d{1,3}[\s\-]?\(?\d{3}\)?[\s\-]?\d{3}[\s\-]?\d{4}", "[REDACTED:phone]"),
]

# Pre-compile for speed
_COMPILED = [(re.compile(p), r) for p, r in _PATTERNS]


def redact_text(text: str) -> str:
    """Redact known secret patterns from a plain-text string."""
    result = text
    for pattern, replacement in _COMPILED:
        result = pattern.sub(replacement, result)
    return result


def redact_artifact(obj: Any) -> Any:
    """Recursively redact secrets from a JSON-serialisable structure.

    Works on dicts, lists, strings, and passes through other types untouched.
    """
    if isinstance(obj, str):
        return redact_text(obj)
    if isinstance(obj, dict):
        return {k: redact_artifact(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [redact_artifact(item) for item in obj]
    return obj


def redact_report(report_dict: Dict[str, Any]) -> Dict[str, Any]:
    """Redact a serialised quality-lab report dict.

    This walks the full report structure: environment, suite metadata, and
    check metadata/detail fields. Returns a new dict; the input is not mutated.
    """
    redacted: Dict[str, Any] = {}

    for key in ("schema_version", "report_id", "timestamp"):
        redacted[key] = report_dict.get(key)

    redacted["environment"] = redact_artifact(report_dict.get("environment", {}))

    new_suites = []
    for suite in report_dict.get("suites", []):
        s = dict(suite)
        s["description"] = redact_text(str(s.get("description", "")))
        new_checks = []
        for chk in s.get("checks", []):
            c = dict(chk)
            c["detail"] = redact_text(str(c.get("detail", "")))
            c["metadata"] = redact_artifact(c.get("metadata", {}))
            new_checks.append(c)
        s["checks"] = new_checks
        new_suites.append(s)
    redacted["suites"] = new_suites
    redacted["summary"] = dict(report_dict.get("summary", {}))
    return redacted
