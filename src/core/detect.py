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
        # WebRTC leak check — only when the caller collected candidate IPs
        # (``webrtc_ips``) and told us the intended mode. Kept optional so the
        # base scorer stays browser-free and existing callers are unaffected.
        if "webrtc_mode" in expected and "webrtc_ips" in signals:
            ips = [str(i) for i in (signals.get("webrtc_ips") or []) if i]
            mode = expected.get("webrtc_mode")
            pub = (expected.get("webrtc_public_ip") or "").strip()
            if mode == "block":
                add(
                    "webrtc_no_leak",
                    len(ips) == 0,
                    "high",
                    f"WebRTC candidate IPs leaked in block mode: {ips}" if ips else "no candidates",
                )
            elif mode == "proxy":
                private = [i for i in ips if _is_private_ip(i)]
                real_leak = private or [i for i in ips if pub and i != pub]
                add(
                    "webrtc_matches_proxy",
                    not real_leak,
                    "high",
                    f"WebRTC IPs {ips} do not all match proxy IP {pub!r}" if real_leak else f"all candidates = {pub}",
                )

    return report


def _is_private_ip(ip: str) -> bool:
    """True for RFC1918 / loopback / link-local IPv4 (a real-IP leak tell)."""
    parts = (ip or "").split(".")
    if len(parts) != 4:
        return False
    try:
        a, b = int(parts[0]), int(parts[1])
    except ValueError:
        return False
    if a == 10 or a == 127:
        return True
    if a == 192 and b == 168:
        return True
    if a == 172 and 16 <= b <= 31:
        return True
    if a == 169 and b == 254:
        return True
    return False


def expected_from_fingerprint(fp) -> Dict[str, Any]:
    """Build the ``expected`` cross-check dict from a Fingerprint dataclass."""
    from .fingerprint import effective_webrtc_mode
    return {
        "webgl_vendor": fp.webgl_vendor,
        "timezone": fp.timezone,
        "platform": fp.platform,
        "languages_count": len(fp.languages),
        "webrtc_mode": effective_webrtc_mode(fp),
        "webrtc_public_ip": fp.webrtc_public_ip,
    }


def build_webrtc_probe_script(timeout_ms: int = 1500) -> str:
    """Return async JS (a Promise) that gathers WebRTC candidate IPs.

    Resolves to ``{"webrtc_ips": [...]}`` — the deduped list of IPv4 addresses
    exposed via ICE candidates. Merge this into the collector signals before
    calling :func:`score_report` to activate the WebRTC leak checks. Safe to
    run on any page; resolves (possibly empty) after ``timeout_ms``.
    """
    return (
        r"""
    (() => new Promise((resolve) => {
      const ips = new Set();
      const IP4 = /(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})/;
      let pc;
      try {
        pc = new RTCPeerConnection({ iceServers: [] });
      } catch (e) { resolve({ webrtc_ips: [] }); return; }
      const done = () => {
        try { pc.close(); } catch (e) {}
        resolve({ webrtc_ips: Array.from(ips) });
      };
      pc.onicecandidate = (evt) => {
        if (!evt || !evt.candidate) { done(); return; }
        const c = evt.candidate.candidate || '';
        if (/\.local\b/i.test(c)) return;
        const m = IP4.exec(c);
        if (m) ips.add(m[1]);
      };
      try {
        pc.createDataChannel('probe');
        pc.createOffer().then((o) => pc.setLocalDescription(o)).catch(() => {});
      } catch (e) {}
      setTimeout(done, __TIMEOUT__);
    }))
    """.replace("__TIMEOUT__", str(int(timeout_ms)))
    )

# ---------------------------------------------------------------------------
# Static fingerprint consistency audit (browser-free)
# ---------------------------------------------------------------------------
def _fp_value(fp, key, default=None):
    if isinstance(fp, dict):
        return fp.get(key, default)
    return getattr(fp, key, default)


def score_fingerprint(fp) -> Report:
    """Score a stored fingerprint without launching a browser."""
    ua = str(_fp_value(fp, "user_agent", ""))
    platform = str(_fp_value(fp, "platform", ""))
    oscpu = str(_fp_value(fp, "oscpu", ""))
    vendor = str(_fp_value(fp, "vendor", ""))
    checks = []
    checks.append(Check("ua_platform_coherence", _platform_matches_ua(platform, ua), "critical", "UA and platform agree"))
    os_ok = ("Windows" in ua) == ("Win" in platform) and (not oscpu or ("Windows" in oscpu) == ("Win" in platform))
    checks.append(Check("ua_oscpu_vendor", os_ok, "high", "OS strings agree"))
    gl = str(_fp_value(fp, "webgl_vendor", "")) + " " + str(_fp_value(fp, "webgl_renderer", ""))
    gl_ok = not ("Win" in platform and ("Apple" in gl or "Intel Iris" in gl)) and bool(gl.strip())
    checks.append(Check("webgl_os_coherence", gl_ok, "high", "GPU is plausible for platform"))
    webgpu = bool(_fp_value(fp, "webgpu_enabled", False))
    wg_ok = (not webgpu) or bool(_fp_value(fp, "webgpu_vendor", "")) and bool(_fp_value(fp, "webgpu_architecture", ""))
    checks.append(Check("webgpu_coherence", wg_ok, "medium", "WebGPU fields are complete when enabled"))
    tz = str(_fp_value(fp, "timezone", "")); locale = str(_fp_value(fp, "locale", "")); langs = _fp_value(fp, "languages", []) or []
    locale_ok = bool(tz and locale and langs)
    checks.append(Check("timezone_locale_coherence", locale_ok, "high", "Timezone, locale, and languages are present"))
    geo_ok = True
    if _fp_value(fp, "spoof_geolocation", False):
        lat = _fp_value(fp, "geo_latitude"); lon = _fp_value(fp, "geo_longitude")
        geo_ok = lat is not None and lon is not None and -90 <= float(lat) <= 90 and -180 <= float(lon) <= 180
    checks.append(Check("geo_timezone_coherence", geo_ok, "high", "Geolocation coordinates are valid"))
    sw, sh = _fp_value(fp,"screen_width",0), _fp_value(fp,"screen_height",0)
    aw, ah = _fp_value(fp,"avail_screen_width",sw), _fp_value(fp,"avail_screen_height",sh)
    iw, ih = _fp_value(fp,"inner_width",aw), _fp_value(fp,"inner_height",ah)
    ratio = _fp_value(fp,"pixel_ratio",1)
    screen_ok = all(isinstance(x,(int,float)) and x > 0 for x in (sw,sh,aw,ah,iw,ih)) and aw <= sw and ah <= sh and iw <= aw and ih <= ah and 1 <= float(ratio) <= 3
    checks.append(Check("screen_sanity", screen_ok, "medium", "Viewport dimensions are coherent"))
    hc, dm = _fp_value(fp,"hardware_concurrency",0), _fp_value(fp,"device_memory",0)
    hardware_ok = isinstance(hc,(int,float)) and 2 <= hc <= 32 and isinstance(dm,(int,float)) and 2 <= dm <= 64
    checks.append(Check("hardware_plausible", hardware_ok, "medium", "Hardware values are plausible"))
    fonts = _fp_value(fp,"fonts",[]) or []
    fonts_ok = isinstance(fonts, (list,tuple)) and len(fonts) > 0
    checks.append(Check("fonts_os_coherence", fonts_ok, "medium", "Font allow-list is present"))
    noise_ok = bool(_fp_value(fp,"audio_noise_seed",None)) and bool(_fp_value(fp,"canvas_noise_seed",None))
    checks.append(Check("noise_seeds_present", noise_ok, "low", "Stable noise seeds are present"))
    checks.append(Check("webdriver_off", _fp_value(fp,"webdriver",False) is False, "critical", "webdriver is disabled"))
    # An empty webrtc_mode is legal: it means "fall back to the legacy
    # block_webrtc_ip flag". Resolve it the way the launcher does, but via
    # _fp_value so dict-shaped fingerprints work too (effective_webrtc_mode uses
    # getattr, which silently reports "block" for every dict).
    #
    # Note this only accepts an *empty* mode as legacy. A non-empty unknown value
    # ("banana") stays a failure here: the launcher tolerates it, but a profile
    # carrying a mode string nothing understands is a misconfiguration worth
    # surfacing in the audit.
    raw_mode = str(_fp_value(fp, "webrtc_mode", "") or "").strip().lower()
    if raw_mode:
        mode = raw_mode
    else:
        mode = "block" if _fp_value(fp, "block_webrtc_ip", True) else "real"
    mode_ok = mode in {"block","real","proxy"} and (mode != "proxy" or bool(_fp_value(fp,"webrtc_public_ip",None)))
    checks.append(Check("webrtc_mode_valid", mode_ok, "high", "WebRTC mode and public IP agree"))
    plugins = _fp_value(fp,"plugins",[]) or []
    plugins_ok = ("Chrome" not in ua and "Chrom" not in ua) or bool(plugins)
    checks.append(Check("plugins_present", plugins_ok, "low", "Chrome profiles expose plugins"))
    return Report(checks=checks)


def fingerprint_preview(fp) -> Dict[str, Any]:
    report = score_fingerprint(fp).to_dict()
    failed = {x["name"] for x in report["failures"]}
    groups = [
        ("Identity", ("user_agent","platform","vendor","oscpu")),
        ("Display", ("screen_width","screen_height","avail_screen_width","avail_screen_height","inner_width","inner_height","pixel_ratio")),
        ("Locale + Geo", ("locale","languages","timezone","spoof_geolocation","geo_latitude","geo_longitude","geo_accuracy")),
        ("Graphics", ("webgl_vendor","webgl_renderer","webgpu_enabled","webgpu_vendor","webgpu_architecture","webgpu_description")),
        ("Hardware", ("hardware_concurrency","device_memory")),
        ("Noise", ("audio_noise_seed","canvas_noise_seed","noise")),
        ("Network / WebRTC", ("connection_type","connection_downlink","connection_rtt","webrtc_mode","webrtc_public_ip","block_webrtc_ip")),
        ("Fonts", ("fonts","plugins")),
        ("Extensions", ("extensions","browser_engine")),
    ]
    fields = []
    for title, keys in groups:
        items = []
        for key in keys:
            value = _fp_value(fp, key, None)
            if value is not None:
                items.append({"key": key, "value": value, "warn": key in failed, "note": "failed consistency check" if key in failed else ""})
        fields.append({"title": title, "fields": items})
    return {"groups": fields, "report": report}
