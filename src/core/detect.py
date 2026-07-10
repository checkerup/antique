"""Stealth self-test harness (CreepJS / FingerprintJS-style).

After spoofing a fingerprint you want an objective answer to "does this
profile look like a real browser, or does it leak automation/inconsistency
tells?". Competitors ship a built-in "check my browser" page; this is the
local, offline-scoreable equivalent.

Two pieces:

1. ``build_collector_script()`` — JS evaluated inside the profile's page that
   gathers raw detection *signals* into a plain dict (webdriver flag, window
   .chrome presence, plugin/language counts, WebGL + WebGPU vendor, timezone,
   installed-font count, permissions coherence, UA-vs-platform agreement).

2. ``score_report(signals, expected=None)`` — a PURE function that turns those
   signals into a graded report: a list of checks with pass/fail + severity,
   an overall score, and a letter grade. Optionally cross-checks the collected
   values against the fingerprint we *intended* to present (``expected``) to
   catch "the patch didn't take" bugs.

The scorer is fully unit-testable without a browser: feed it a signals dict.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


# Severity weights: how many points a failed check subtracts.
_SEVERITY_WEIGHT = {"critical": 40, "high": 20, "medium": 10, "low": 5}


@dataclass
class Check:
    name: str
    ok: bool
    severity: str          # critical | high | medium | low
    detail: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {"name": self.name, "ok": self.ok, "severity": self.severity, "detail": self.detail}


@dataclass
class Report:
    checks: List[Check] = field(default_factory=list)

    @property
    def passed(self) -> int:
        return sum(1 for c in self.checks if c.ok)

    @property
    def failed_checks(self) -> List[Check]:
        return [c for c in self.checks if not c.ok]

    def score(self) -> int:
        """0..100. Starts at 100, subtracts each failed check's weight."""
        penalty = sum(_SEVERITY_WEIGHT.get(c.severity, 10) for c in self.checks if not c.ok)
        return max(0, 100 - penalty)

    def grade(self) -> str:
        s = self.score()
        if s >= 90:
            return "A"
        if s >= 75:
            return "B"
        if s >= 60:
            return "C"
        if s >= 40:
            return "D"
        return "F"

    def ok(self) -> bool:
        """True when there are no critical failures."""
        return not any((not c.ok) and c.severity == "critical" for c in self.checks)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "score": self.score(),
            "grade": self.grade(),
            "ok": self.ok(),
            "passed": self.passed,
            "total": len(self.checks),
            "checks": [c.to_dict() for c in self.checks],
            "failures": [c.to_dict() for c in self.failed_checks],
        }


def build_collector_script() -> str:
    """Return JS that collects raw detection signals into a JSON object.

    Designed to be passed to Playwright's ``page.evaluate``. Returns a plain
    object (no functions) so it serialises cleanly back to Python.
    """
    return r"""
    (() => {
      const s = {};
      try { s.webdriver = navigator.webdriver; } catch (e) { s.webdriver = null; }
      try { s.has_chrome = !!window.chrome; } catch (e) { s.has_chrome = false; }
      try { s.has_chrome_runtime = !!(window.chrome && window.chrome.runtime); } catch (e) { s.has_chrome_runtime = false; }
      try { s.plugins_count = navigator.plugins ? navigator.plugins.length : 0; } catch (e) { s.plugins_count = 0; }
      try { s.languages_count = (navigator.languages || []).length; } catch (e) { s.languages_count = 0; }
      try { s.language = navigator.language || ''; } catch (e) { s.language = ''; }
      try { s.platform = navigator.platform || ''; } catch (e) { s.platform = ''; }
      try { s.user_agent = navigator.userAgent || ''; } catch (e) { s.user_agent = ''; }
      try { s.hardware_concurrency = navigator.hardwareConcurrency || 0; } catch (e) { s.hardware_concurrency = 0; }
      try { s.device_memory = navigator.deviceMemory || 0; } catch (e) { s.device_memory = 0; }
      try { s.timezone = Intl.DateTimeFormat().resolvedOptions().timeZone || ''; } catch (e) { s.timezone = ''; }
      // WebGL vendor/renderer
      try {
        const c = document.createElement('canvas');
        const gl = c.getContext('webgl') || c.getContext('experimental-webgl');
        const dbg = gl && gl.getExtension('WEBGL_debug_renderer_info');
        s.webgl_vendor = dbg ? gl.getParameter(dbg.UNMASKED_VENDOR_WEBGL) : '';
        s.webgl_renderer = dbg ? gl.getParameter(dbg.UNMASKED_RENDERER_WEBGL) : '';
      } catch (e) { s.webgl_vendor = ''; s.webgl_renderer = ''; }
      // WebGPU
      s.has_webgpu = false;
      try { s.has_webgpu = !!navigator.gpu; } catch (e) {}
      // Notification/permissions coherence tell
      s.permission_mismatch = false;
      try {
        if (navigator.permissions && window.Notification) {
          navigator.permissions.query({ name: 'notifications' }).then((r) => {
            s.permission_mismatch = (r.state === 'denied' && Notification.permission === 'default');
          }).catch(() => {});
        }
      } catch (e) {}
      return s;
    })()
    """


def _platform_matches_ua(platform: str, ua: str) -> bool:
    """Coarse check that navigator.platform agrees with the UA OS token."""
    ua = (ua or "").lower()
    p = (platform or "").lower()
    if not p or not ua:
        return False
    if p == "win32":
        return "windows" in ua
    if p == "macintel":
        return "mac os" in ua or "macintosh" in ua
    if "linux" in p:
        return "linux" in ua
    return True  # unknown platform token — don't penalise


def score_report(signals: Dict[str, Any], expected: Optional[Dict[str, Any]] = None) -> Report:
    """Turn a raw signals dict into a graded :class:`Report`.

    Args:
        signals: output of the collector script (see ``build_collector_script``).
        expected: optional dict of intended fingerprint values to cross-check,
            e.g. ``{"webgl_vendor": ..., "timezone": ..., "platform": ...,
            "fonts_count": N}``. When provided, mismatches add checks.
    """
    report = Report()
    add = lambda *a, **k: report.checks.append(Check(*a, **k))

    # --- Automation tells (critical) ---
    add(
        "webdriver_false",
        signals.get("webdriver") is False,
        "critical",
        f"navigator.webdriver = {signals.get('webdriver')!r} (expected False)",
    )
    add(
        "has_window_chrome",
        bool(signals.get("has_chrome")),
        "high",
        "window.chrome missing (headless tell)" if not signals.get("has_chrome") else "present",
    )
    add(
        "chrome_runtime_present",
        bool(signals.get("has_chrome_runtime")),
        "medium",
        "window.chrome.runtime missing" if not signals.get("has_chrome_runtime") else "present",
    )

    # --- Plausibility of navigator surface ---
    add(
        "plugins_present",
        int(signals.get("plugins_count") or 0) > 0,
        "medium",
        f"navigator.plugins.length = {signals.get('plugins_count')}",
    )
    add(
        "languages_present",
        int(signals.get("languages_count") or 0) > 0,
        "high",
        f"navigator.languages length = {signals.get('languages_count')}",
    )
    add(
        "hardware_concurrency_sane",
        int(signals.get("hardware_concurrency") or 0) > 0,
        "low",
        f"hardwareConcurrency = {signals.get('hardware_concurrency')}",
    )
    add(
        "webgl_vendor_present",
        bool(signals.get("webgl_vendor")),
        "high",
        f"WebGL vendor = {signals.get('webgl_vendor')!r}",
    )
    add(
        "timezone_present",
        bool(signals.get("timezone")),
        "medium",
        f"timezone = {signals.get('timezone')!r}",
    )
    add(
        "permissions_coherent",
        not bool(signals.get("permission_mismatch")),
        "high",
        "notifications permission/Notification.permission mismatch (headless tell)"
        if signals.get("permission_mismatch")
        else "coherent",
    )
    add(
        "platform_matches_ua",
        _platform_matches_ua(signals.get("platform", ""), signals.get("user_agent", "")),
        "high",
        f"platform={signals.get('platform')!r} vs UA={signals.get('user_agent')!r}",
    )

    # --- Cross-check against the intended fingerprint (optional) ---
    if expected:
        if "webgl_vendor" in expected:
            add(
                "webgl_vendor_matches_expected",
                (signals.get("webgl_vendor") or "") == expected["webgl_vendor"],
                "high",
                f"got {signals.get('webgl_vendor')!r}, expected {expected['webgl_vendor']!r}",
            )
        if "timezone" in expected:
            add(
                "timezone_matches_expected",
                (signals.get("timezone") or "") == expected["timezone"],
                "high",
                f"got {signals.get('timezone')!r}, expected {expected['timezone']!r}",
            )
        if "platform" in expected:
            add(
                "platform_matches_expected",
                (signals.get("platform") or "") == expected["platform"],
                "medium",
                f"got {signals.get('platform')!r}, expected {expected['platform']!r}",
            )
        if "languages_count" in expected:
            add(
                "languages_count_matches_expected",
                int(signals.get("languages_count") or 0) == int(expected["languages_count"]),
                "low",
                f"got {signals.get('languages_count')}, expected {expected['languages_count']}",
            )

    return report


def expected_from_fingerprint(fp) -> Dict[str, Any]:
    """Build the ``expected`` cross-check dict from a Fingerprint dataclass."""
    return {
        "webgl_vendor": fp.webgl_vendor,
        "timezone": fp.timezone,
        "platform": fp.platform,
        "languages_count": len(fp.languages),
    }
