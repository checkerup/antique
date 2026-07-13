"""Fingerprint generation and injection.

A *fingerprint* is the bundle of browser-visible attributes that trackers
and detection scripts combine to identify a browser instance:

  - User-Agent
  - navigator.platform / vendor / oscpu
  - screen.width / height / colorDepth / pixelRatio
  - window.devicePixelRatio
  - timezone / Intl.DateTimeFormat().resolvedOptions().timeZone
  - navigator.language / languages
  - WebGL vendor / renderer (read via WebGLRenderingContext)
  - AudioContext sampleRate / fingerprint
  - Canvas fingerprint (toDataURL output)
  - WebRTC IP-leak prevention
  - navigator.plugins / mimeTypes
  - navigator.webdriver flag
  - Connection type / downlink (Network Information API)
  - Hardware concurrency / device memory
  - Fonts (enumerable via document.fonts / canvas-measured fonts)

This module:

1. ``Fingerprint`` dataclass — a coherent bundle of these fields.
2. ``generate_fingerprint(seed=None, os_family="windows")`` — produce a new
   realistic fingerprint. Optional ``seed`` makes output deterministic.
3. ``to_playwright_context(fp)`` / ``to_init_scripts(fp)`` — convert into
   Playwright launch args + JS init scripts that patch the browser at boot.

The init scripts cover what *can't* be done at launch time
(canvas/WebGL/audio/font noise). For that we inject deterministic noise
seeded by the fingerprint's ``noise`` field so a profile is reproducible
across runs.
"""
from __future__ import annotations

import hashlib
import json
import random
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional


# ---------------------------------------------------------------------------
# Constants — realistic distributions
# ---------------------------------------------------------------------------


# Common desktop resolutions (width x height, devicePixelRatio)
_SCREEN_PRESETS = [
    # (w, h, dpr, label)
    (1920, 1080, 1.0, "FHD"),
    (2560, 1440, 1.0, "2K"),
    (1366, 768, 1.0, "HD"),
    (1680, 1050, 1.0, "WSXGA+"),
    (1440, 900, 1.0, "WXGA+"),
    (3840, 2160, 1.0, "4K"),
    (1280, 800, 1.0, "WXGA"),
    (1280, 1024, 1.0, "SXGA"),
    (1536, 864, 1.0, "Other"),
    (1600, 900, 1.0, "HD+"),
    (1920, 1200, 1.0, "WUXGA"),
]

# macOS-only retina presets
_MAC_SCREEN_PRESETS = [
    (2560, 1600, 2.0, "Retina"),
    (2880, 1800, 2.0, "Retina"),
    (3024, 1964, 2.0, "Retina"),
]

# Common timezone IDs grouped by locale
_TIMEZONES_BY_LANG = {
    "en-US": ["America/New_York", "America/Chicago", "America/Denver", "America/Los_Angeles", "America/Phoenix"],
    "en-GB": ["Europe/London"],
    "de-DE": ["Europe/Berlin", "Europe/Vienna", "Europe/Zurich"],
    "fr-FR": ["Europe/Paris", "Europe/Brussels"],
    "es-ES": ["Europe/Madrid", "America/Mexico_City", "America/Buenos_Aires"],
    "it-IT": ["Europe/Rome"],
    "pt-BR": ["America/Sao_Paulo"],
    "ru-RU": ["Europe/Moscow", "Asia/Novosibirsk", "Asia/Yekaterinburg"],
    "ja-JP": ["Asia/Tokyo"],
    "ko-KR": ["Asia/Seoul"],
    "zh-CN": ["Asia/Shanghai", "Asia/Hong_Kong"],
    "pl-PL": ["Europe/Warsaw"],
    "tr-TR": ["Europe/Istanbul", "Asia/Istanbul"],
    "nl-NL": ["Europe/Amsterdam"],
    "uk-UA": ["Europe/Kiev", "Europe/Kyiv"],
}

# WebGL vendor/renderer pairings — keep GPU vendor ↔ renderer consistent.
# Values match what real Chrome on Windows/macOS/Linux reports.
_GPU_PROFILES = [
    ("Google Inc. (NVIDIA)", "ANGLE (NVIDIA, NVIDIA GeForce RTX 3060 Direct3D11 vs_5_0 ps_5_0)"),
    ("Google Inc. (NVIDIA)", "ANGLE (NVIDIA, NVIDIA GeForce RTX 4070 Direct3D11 vs_5_0 ps_5_0)"),
    ("Google Inc. (NVIDIA)", "ANGLE (NVIDIA, NVIDIA GeForce GTX 1660 SUPER Direct3D11 vs_5_0 ps_5_0)"),
    ("Google Inc. (AMD)", "ANGLE (AMD, AMD Radeon RX 580 Direct3D11 vs_5_0 ps_5_0)"),
    ("Google Inc. (AMD)", "ANGLE (AMD, AMD Radeon RX 6700 XT Direct3D11 vs_5_0 ps_5_0)"),
    ("Google Inc. (Intel)", "ANGLE (Intel, Intel(R) UHD Graphics 630 Direct3D11 vs_5_0 ps_5_0)"),
    ("Google Inc. (Intel)", "ANGLE (Intel, Intel(R) Iris Xe Graphics Direct3D11 vs_5_0 ps_5_0)"),
    ("Apple Inc.", "Apple GPU"),
    ("Apple Inc.", "Apple M1 Pro"),
    ("Apple Inc.", "Apple M2"),
    ("Mozilla", "llvmpipe (LLVM 15.0.6, 256 bits)"),
]

# User-Agent presets grouped by OS family
_UA_PRESETS = {
    "windows": [
        # Chrome
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/{major}.0.{build}.{patch} Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/{major}.0.{build}.{patch} Safari/537.36",
    ],
    "macos": [
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/{major}.0.{build}.{patch} Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15",
    ],
    "linux": [
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/{major}.0.{build}.{patch} Safari/537.36",
    ],
}

# WebGPU adapter profiles, coherent with the WebGL GPU vendor.
# Each entry: (match-substring-in-webgl-vendor, gpu_vendor, gpu_architecture, gpu_description)
# navigator.gpu.requestAdapter().requestAdapterInfo() exposes these.
_WEBGPU_PROFILES = [
    ("NVIDIA", "nvidia", "ampere", "NVIDIA GeForce RTX 3060"),
    ("NVIDIA", "nvidia", "ada-lovelace", "NVIDIA GeForce RTX 4070"),
    ("AMD", "amd", "rdna2", "AMD Radeon RX 6700 XT"),
    ("AMD", "amd", "gcn", "AMD Radeon RX 580"),
    ("Intel", "intel", "gen-12lp", "Intel(R) Iris(R) Xe Graphics"),
    ("Intel", "intel", "gen-9", "Intel(R) UHD Graphics 630"),
    ("Apple", "apple", "metal-3", "Apple M1 Pro"),
    ("Apple", "apple", "metal-3", "Apple M2"),
    ("Mozilla", "", "", ""),  # llvmpipe / software → no WebGPU adapter
]

# Font sets per OS family. A realistic-but-not-exhaustive base set that a
# clean install of each OS ships. Detection scripts measure text width to
# enumerate installed fonts, so a coherent per-OS list matters.
_FONTS_BY_OS = {
    "windows": [
        "Arial", "Arial Black", "Bahnschrift", "Calibri", "Cambria",
        "Cambria Math", "Candara", "Comic Sans MS", "Consolas", "Constantia",
        "Corbel", "Courier New", "Ebrima", "Franklin Gothic Medium", "Gabriola",
        "Gadugi", "Georgia", "Impact", "Ink Free", "Javanese Text",
        "Leelawadee UI", "Lucida Console", "Lucida Sans Unicode", "Malgun Gothic",
        "Marlett", "Microsoft Himalaya", "Microsoft JhengHei", "Microsoft New Tai Lue",
        "Microsoft PhagsPa", "Microsoft Sans Serif", "Microsoft Tai Le",
        "Microsoft YaHei", "MingLiU-ExtB", "Mongolian Baiti", "MS Gothic",
        "MV Boli", "Myanmar Text", "Nirmala UI", "Palatino Linotype",
        "Segoe MDL2 Assets", "Segoe Print", "Segoe Script", "Segoe UI",
        "Segoe UI Emoji", "Segoe UI Historic", "Segoe UI Symbol", "SimSun",
        "Sitka", "Sylfaen", "Symbol", "Tahoma", "Times New Roman",
        "Trebuchet MS", "Verdana", "Webdings", "Wingdings", "Yu Gothic",
    ],
    "macos": [
        "American Typewriter", "Andale Mono", "Arial", "Arial Black",
        "Arial Narrow", "Arial Rounded MT Bold", "Arial Unicode MS",
        "Avenir", "Avenir Next", "Avenir Next Condensed", "Baskerville",
        "Big Caslon", "Bodoni 72", "Bradley Hand", "Brush Script MT",
        "Chalkboard", "Chalkboard SE", "Chalkduster", "Charter", "Cochin",
        "Comic Sans MS", "Copperplate", "Courier", "Courier New", "Didot",
        "DIN Alternate", "DIN Condensed", "Futura", "Geneva", "Georgia",
        "Gill Sans", "Helvetica", "Helvetica Neue", "Herculanum",
        "Hoefler Text", "Impact", "Lucida Grande", "Luminari", "Marker Felt",
        "Menlo", "Monaco", "Noteworthy", "Optima", "Palatino", "Papyrus",
        "Phosphate", "Rockwell", "San Francisco", "Savoye LET", "SignPainter",
        "Skia", "Snell Roundhand", "Tahoma", "Times", "Times New Roman",
        "Trattatello", "Trebuchet MS", "Verdana", "Zapfino",
    ],
    "linux": [
        "Bitstream Vera Sans", "Bitstream Vera Sans Mono", "Bitstream Vera Serif",
        "Century Schoolbook L", "DejaVu Sans", "DejaVu Sans Mono",
        "DejaVu Serif", "Dingbats", "FreeMono", "FreeSans", "FreeSerif",
        "Liberation Mono", "Liberation Sans", "Liberation Serif",
        "Nimbus Mono L", "Nimbus Roman No9 L", "Nimbus Sans L", "Noto Sans",
        "Noto Serif", "Standard Symbols L", "Ubuntu", "Ubuntu Condensed",
        "Ubuntu Mono", "URW Bookman L", "URW Chancery L", "URW Gothic L",
        "URW Palladio L",
    ],
}


_OS_PROFILES = {
    "windows": {
        "platform": "Win32",
        "oscpu": "",
        "ua_platform": '"Windows"',
        "vendor": '"Google Inc."',
    },
    "macos": {
        "platform": "MacIntel",
        "oscpu": "",
        "ua_platform": '"macOS"',
        "vendor": '"Apple Computer, Inc."',
    },
    "linux": {
        "platform": "Linux x86_64",
        "oscpu": "Linux x86_64",
        "ua_platform": '"Linux"',
        "vendor": '"Google Inc."',
    },
}


# ---------------------------------------------------------------------------
# Fingerprint dataclass
# ---------------------------------------------------------------------------


@dataclass
class Fingerprint:
    """A coherent fingerprint bundle.

    All fields default to ``None`` meaning "let the real browser decide"
    or, after generation, "this value should be patched in".
    """

    # Identity / UA
    user_agent: str = ""
    accept_language: str = "en-US,en;q=0.9"
    languages: List[str] = field(default_factory=lambda: ["en-US", "en"])

    # navigator.*
    platform: str = "Win32"
    vendor: str = "Google Inc."
    oscpu: str = ""
    hardware_concurrency: int = 8
    device_memory: float = 8.0
    webdriver: bool = False  # always False — we patch navigator.webdriver

    # Screen
    screen_width: int = 1920
    screen_height: int = 1080
    avail_screen_width: int = 1920
    avail_screen_height: int = 1040
    color_depth: int = 24
    pixel_ratio: float = 1.0
    inner_width: int = 1920
    inner_height: int = 969

    # Locale / timezone
    locale: str = "en-US"
    timezone: str = "America/New_York"

    # WebGL
    webgl_vendor: str = "Google Inc. (NVIDIA)"
    webgl_renderer: str = "ANGLE (NVIDIA, NVIDIA GeForce RTX 3060 Direct3D11 vs_5_0 ps_5_0)"

    # WebGPU (navigator.gpu.requestAdapter().requestAdapterInfo()).
    # Empty gpu_vendor means "no WebGPU adapter available" (software renderer).
    webgpu_enabled: bool = True
    webgpu_vendor: str = "nvidia"
    webgpu_architecture: str = "ampere"
    webgpu_description: str = "NVIDIA GeForce RTX 3060"

    # Installed fonts (enumerated by width-measurement detection scripts)
    fonts: List[str] = field(default_factory=list)

    # Geolocation (navigator.geolocation). When spoof_geolocation is True the
    # init script overrides getCurrentPosition/watchPosition with these coords.
    # These are normally derived from the proxy's exit country (see core.geo).
    spoof_geolocation: bool = False
    geo_latitude: float = 0.0
    geo_longitude: float = 0.0
    geo_accuracy: float = 50.0

    # Audio (deterministic noise seed for AudioContext)
    audio_noise_seed: int = 0

    # Canvas (deterministic noise seed)
    canvas_noise_seed: int = 0

    # Connection (Network Information API)
    connection_type: str = "wifi"
    connection_downlink: float = 10.0
    connection_rtt: int = 50

    # WebRTC IP-leak prevention (block all STUN/external IP)
    block_webrtc_ip: bool = True

    # Plugins / mime types (Chrome desktop realistic)
    plugins: List[Dict[str, Any]] = field(default_factory=list)

    # Noise secret (deterministic seed used for canvas/audio/font entropy)
    noise: str = ""

    # Browser engine key (see src/core/engines.py). Empty = use global default
    # (ANTIDETECT_ENGINE env or 'chromium'). Persisted so a profile keeps its
    # engine across launches.
    browser_engine: str = ""

    # Extension ids assigned to this profile (managed via the extension store).
    extensions: List[str] = field(default_factory=list)

    # Auto-generated id (hash of canonical fields)
    id: str = ""

    def canonical(self) -> Dict[str, Any]:
        return asdict(self)


# ---------------------------------------------------------------------------
# Generator
# ---------------------------------------------------------------------------


def _ua_for(os_family: str, rng: random.Random) -> str:
    template = rng.choice(_UA_PRESETS[os_family])
    # Pick a recent Chrome version
    major = rng.randint(118, 132)
    build = rng.randint(4000, 6800)
    patch = rng.randint(50, 200)
    return template.format(major=major, build=build, patch=patch)


def _lang_for(rng: random.Random) -> tuple[str, str, List[str]]:
    lang = rng.choice(list(_TIMEZONES_BY_LANG.keys()))
    langs = [lang] + (["en-US", "en"] if lang != "en-US" else ["en"])
    accept = f"{lang},{lang.split('-')[0]};q=0.9,en-US;q=0.8,en;q=0.7"
    return lang, accept, langs


def _pick_screen(os_family: str, rng: random.Random) -> tuple:
    if os_family == "macos" and rng.random() < 0.6:
        return rng.choice(_MAC_SCREEN_PRESETS)
    return rng.choice(_SCREEN_PRESETS)


def _chrome_plugins(rng: random.Random) -> List[Dict[str, Any]]:
    # Realistic Chrome plugins (PDF Viewer is universal; others vary)
    plugins = [
        {"name": "PDF Viewer", "filename": "internal-pdf-viewer", "description": "Portable Document Format"},
        {"name": "Chrome PDF Viewer", "filename": "internal-pdf-viewer", "description": "Portable Document Format"},
        {"name": "Chromium PDF Viewer", "filename": "internal-pdf-viewer", "description": "Portable Document Format"},
        {"name": "Microsoft Edge PDF Viewer", "filename": "internal-pdf-viewer", "description": "Portable Document Format"},
        {"name": "WebKit built-in PDF", "filename": "internal-pdf-viewer", "description": "Portable Document Format"},
    ]
    rng.shuffle(plugins)
    return plugins[: rng.randint(2, 5)]


def generate_fingerprint(
    seed: Optional[str] = None,
    os_family: str = "windows",
) -> Fingerprint:
    """Generate a new, internally-consistent fingerprint.

    Args:
        seed: optional string; deterministic output if provided.
        os_family: 'windows' | 'macos' | 'linux'.

    Returns:
        Fingerprint dataclass.
    """
    if os_family not in _OS_PROFILES:
        raise ValueError(f"Unknown os_family: {os_family!r}")

    rng = random.Random(seed) if seed else random.SystemRandom()

    fp = Fingerprint()

    # UA + navigator basics
    fp.user_agent = _ua_for(os_family, rng)
    os_data = _OS_PROFILES[os_family]
    fp.platform = os_data["platform"]
    fp.vendor = os_data["vendor"]
    fp.oscpu = os_data["oscpu"]
    fp.webdriver = False

    # Locale + timezone — keep them consistent
    lang, accept, langs = _lang_for(rng)
    fp.accept_language = accept
    fp.languages = langs
    fp.locale = lang
    tz_pool = _TIMEZONES_BY_LANG.get(lang, _TIMEZONES_BY_LANG["en-US"])
    fp.timezone = rng.choice(tz_pool)

    # Screen
    w, h, dpr, _ = _pick_screen(os_family, rng)
    fp.screen_width = w
    fp.screen_height = h
    fp.avail_screen_width = w
    fp.avail_screen_height = h - rng.randint(20, 60)  # taskbar
    fp.color_depth = rng.choice([24, 30, 48])
    fp.pixel_ratio = dpr
    fp.inner_width = w
    fp.inner_height = h - rng.randint(80, 160)  # chrome + nav bars

    # Hardware
    fp.hardware_concurrency = rng.choice([2, 4, 4, 8, 8, 8, 12, 16])
    fp.device_memory = rng.choice([4.0, 8.0, 8.0, 16.0, 32.0])

    # GPU
    fp.webgl_vendor, fp.webgl_renderer = rng.choice(_GPU_PROFILES)

    # WebGPU adapter — keep it coherent with the chosen WebGL GPU vendor.
    _webgpu_matches = [
        prof for prof in _WEBGPU_PROFILES if prof[0] in fp.webgl_vendor
    ] or [_WEBGPU_PROFILES[-1]]
    _wg = rng.choice(_webgpu_matches)
    fp.webgpu_vendor = _wg[1]
    fp.webgpu_architecture = _wg[2]
    fp.webgpu_description = _wg[3]
    # Software renderers (Mozilla/llvmpipe) don't expose a WebGPU adapter.
    fp.webgpu_enabled = bool(_wg[1])

    # Fonts — a randomized-but-deterministic subset of the OS base set.
    _font_pool = list(_FONTS_BY_OS.get(os_family, _FONTS_BY_OS["windows"]))
    # Always keep the core cross-app fonts; sample the rest so profiles differ.
    _core_fonts = [f for f in _font_pool if f in (
        "Arial", "Courier New", "Times New Roman", "Verdana", "Georgia",
        "Tahoma", "Trebuchet MS", "Comic Sans MS", "Impact",
    )]
    _rest = [f for f in _font_pool if f not in _core_fonts]
    rng.shuffle(_rest)
    _keep = _rest[: max(0, len(_rest) - rng.randint(0, 6))]
    fp.fonts = sorted(set(_core_fonts) | set(_keep))

    # Audio / canvas noise seeds
    fp.audio_noise_seed = rng.randint(1, 2**30)
    fp.canvas_noise_seed = rng.randint(1, 2**30)

    # Network info
    fp.connection_type = rng.choice(["wifi", "wifi", "wifi", "ethernet", "4g"])
    fp.connection_downlink = round(rng.uniform(1.5, 75.0), 1)
    fp.connection_rtt = rng.randint(20, 250)

    # WebRTC block
    fp.block_webrtc_ip = True

    # Plugins
    fp.plugins = _chrome_plugins(rng)

    # Noise string + id
    raw = json.dumps(fp.canonical(), sort_keys=True, default=str).encode("utf-8")
    fp.noise = hashlib.sha256(raw + (seed or "").encode("utf-8")).hexdigest()
    fp.id = hashlib.sha256(fp.user_agent.encode("utf-8") + raw).hexdigest()[:16]

    return fp


# ---------------------------------------------------------------------------
# Conversion: fingerprint → Playwright launch context + init scripts
# ---------------------------------------------------------------------------


def to_playwright_launch_options(fp: Fingerprint, proxy: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Build kwargs for ``playwright.chromium.launch_persistent_context``.

    Note: launch args here only handle browser-level switches (proxy, locale,
    UA, window size). Browser-internal patching (canvas/WebGL/audio) goes
    through ``to_init_scripts``.
    """
    opts: Dict[str, Any] = {
        "headless": False,  # most anti-detect use-cases need a real window
        "args": [
            "--disable-blink-features=AutomationControlled",
            "--disable-features=IsolateOrigins,site-per-process",
            "--disable-site-isolation-trials",
            "--disable-web-security",
            f"--lang={fp.locale}",
            f"--window-size={fp.screen_width},{fp.screen_height}",
            "--no-default-browser-check",
            "--no-first-run",
            "--disable-infobars",
            "--disable-dev-shm-usage",
            # Don't disable GPU — anti-detect checks for WebGL availability
        ],
        "viewport": {"width": fp.inner_width, "height": fp.inner_height},
        "screen": {"width": fp.screen_width, "height": fp.screen_height},
        "device_scale_factor": fp.pixel_ratio,
        "locale": fp.locale,
        "timezone_id": fp.timezone,
        "user_agent": fp.user_agent,
        "accept_downloads": True,
        "ignore_https_errors": True,
        "bypass_csp": False,
    }
    # Color scheme & reduced motion are nice but not fingerprint-critical
    if proxy:
        opts["proxy"] = proxy
    # Align the Geolocation API + permission grant with the spoofed coords so
    # the JS override in the init script isn't contradicted by a hard denial.
    if fp.spoof_geolocation:
        opts["geolocation"] = {
            "latitude": fp.geo_latitude,
            "longitude": fp.geo_longitude,
            "accuracy": fp.geo_accuracy,
        }
        opts["permissions"] = ["geolocation"]
    return opts


# ---------------------------------------------------------------------------
# Init scripts (JS injected at document creation)
# ---------------------------------------------------------------------------


INIT_SCRIPT_TEMPLATE = r"""
(() => {
  const cfg = __AD_CFG__;
  const noise = (seed) => {
    // Mulberry32 — small, fast, deterministic
    let t = seed >>> 0;
    return () => {
      t = (t + 0x6D2B79F5) | 0;
      let r = t;
      r = Math.imul(r ^ (r >>> 15), r | 1);
      r ^= r + Math.imul(r ^ (r >>> 7), r | 61);
      return ((r ^ (r >>> 14)) >>> 0) / 4294967296;
    };
  };
  const audioRand = noise(cfg.audio_noise_seed);
  const canvasRand = noise(cfg.canvas_noise_seed);

  // ---- navigator.webdriver = false ----
  try {
    Object.defineProperty(Navigator.prototype, 'webdriver', {
      get: () => false,
      configurable: true,
    });
  } catch (e) {}

  // ---- navigator.platform / vendor / oscpu ----
  try {
    Object.defineProperty(Navigator.prototype, 'platform', { get: () => cfg.platform });
  } catch (e) {}
  try {
    Object.defineProperty(Navigator.prototype, 'vendor', { get: () => cfg.vendor });
  } catch (e) {}
  if (cfg.oscpu) {
    try {
      Object.defineProperty(Navigator.prototype, 'oscpu', { get: () => cfg.oscpu });
    } catch (e) {}
  }

  // ---- navigator.languages ----
  try {
    Object.defineProperty(Navigator.prototype, 'languages', {
      get: () => cfg.languages,
      configurable: true,
    });
  } catch (e) {}

  // ---- navigator.hardwareConcurrency / deviceMemory ----
  try {
    Object.defineProperty(Navigator.prototype, 'hardwareConcurrency', {
      get: () => cfg.hardware_concurrency,
      configurable: true,
    });
  } catch (e) {}
  try {
    Object.defineProperty(Navigator.prototype, 'deviceMemory', {
      get: () => cfg.device_memory,
      configurable: true,
    });
  } catch (e) {}

  // ---- navigator.connection (Network Information API) ----
  if ('connection' in navigator) {
    try {
      const c = navigator.connection;
      Object.defineProperty(c, 'type', { get: () => cfg.connection_type });
      Object.defineProperty(c, 'downlink', { get: () => cfg.connection_downlink });
      Object.defineProperty(c, 'rtt', { get: () => cfg.connection_rtt });
    } catch (e) {}
  }

  // ---- Plugins (override navigator.plugins) ----
  try {
    const arr = cfg.plugins.map((p) => {
      const plugin = Object.create(Plugin.prototype);
      Object.defineProperty(plugin, 'name', { get: () => p.name });
      Object.defineProperty(plugin, 'filename', { get: () => p.filename });
      Object.defineProperty(plugin, 'description', { get: () => p.description });
      return plugin;
    });
    const pluginArr = arr.filter ? arr : [];
    // PluginArray duck-type
    const pa = Object.create(PluginArray.prototype);
    arr.forEach((p, i) => Object.defineProperty(pa, i, { get: () => p }));
    Object.defineProperty(pa, 'length', { get: () => arr.length });
    Object.defineProperty(pa, 'refresh', { value: () => {} });
    Object.defineProperty(Navigator.prototype, 'plugins', {
      get: () => pa,
      configurable: true,
    });
  } catch (e) {}

  // ---- WebGL vendor/renderer ----
  const patchWebGL = (proto) => {
    const getParam = proto.getParameter;
    proto.getParameter = function (param) {
      // UNMASKED_VENDOR_WEBGL = 0x9245
      if (param === 0x9245) return cfg.webgl_vendor;
      // UNMASKED_RENDERER_WEBGL = 0x9246
      if (param === 0x9246) return cfg.webgl_renderer;
      return getParam.call(this, param);
    };
    const getExt = proto.getExtension;
    proto.getExtension = function (name) {
      const ext = getExt.call(this, name);
      if (!ext) return ext;
      if (name === 'WEBGL_debug_renderer_info') {
        return new Proxy(ext, {
          get(target, prop) {
            if (prop === 'UNMASKED_VENDOR_WEBGL') return 0x9245;
            if (prop === 'UNMASKED_RENDERER_WEBGL') return 0x9246;
            return target[prop];
          },
        });
      }
      return ext;
    };
  };
  try { patchWebGL(HTMLCanvasElement.prototype.getContext('webgl').constructor.prototype); } catch (e) {}
  try { patchWebGL(HTMLCanvasElement.prototype.getContext('webgl2').constructor.prototype); } catch (e) {}

  // ---- Canvas noise (mild, deterministic) ----
  try {
    const origToDataURL = HTMLCanvasElement.prototype.toDataURL;
    const origToBlob = HTMLCanvasElement.prototype.toBlob;
    const noiseToCanvas = (canvas, ctx) => {
      const w = canvas.width, h = canvas.height;
      if (w > 0 && h > 0) {
        const img = ctx.getImageData(0, 0, Math.min(w, 64), Math.min(h, 64));
        const data = img.data;
        for (let i = 0; i < data.length; i += 4) {
          const r = Math.floor(canvasRand() * 4) - 2; // ±2
          data[i]     = Math.max(0, Math.min(255, data[i]     + r));
          data[i + 1] = Math.max(0, Math.min(255, data[i + 1] + r));
          data[i + 2] = Math.max(0, Math.min(255, data[i + 2] + r));
        }
        ctx.putImageData(img, 0, 0);
      }
    };
    HTMLCanvasElement.prototype.toDataURL = function (...args) {
      try {
        const ctx = this.getContext('2d');
        if (ctx) noiseToCanvas(this, ctx);
      } catch (e) {}
      return origToDataURL.apply(this, args);
    };
    HTMLCanvasElement.prototype.toBlob = function (...args) {
      try {
        const ctx = this.getContext('2d');
        if (ctx) noiseToCanvas(this, ctx);
      } catch (e) {}
      return origToBlob.apply(this, args);
    };
  } catch (e) {}

  // ---- AudioContext noise (sampleRate jitter) ----
  try {
    const AC = window.AudioContext || window.webkitAudioContext;
    if (AC && AC.prototype) {
      const origCreateOscillator = AC.prototype.createOscillator;
      AC.prototype.createOscillator = function () {
        const osc = origCreateOscillator.call(this);
        const origConnect = osc.connect.bind(osc);
        osc.connect = function (dest) {
          // jitter frequency slightly
          const r = audioRand();
          osc.frequency.value = osc.frequency.value * (1 + (r - 0.5) * 0.0001);
          return origConnect(dest);
        };
        return osc;
      };
    }
  } catch (e) {}

  // ---- WebRTC IP leak prevention ----
  if (cfg.block_webrtc_ip) {
    try {
      const RTC = window.RTCPeerConnection || window.webkitRTCPeerConnection;
      if (RTC) {
        const origCreate = RTC.prototype.createDataChannel;
        RTC.prototype.createDataChannel = function (...args) {
          // Force empty iceServers to prevent STUN IP leak
          if (this._iceServersOverridden) return origCreate.apply(this, args);
          this._iceServersOverridden = true;
          try {
            this.setConfiguration({ iceServers: [] });
          } catch (e) {}
          return origCreate.apply(this, args);
        };
        const origSetConfig = RTC.prototype.setConfiguration;
        RTC.prototype.setConfiguration = function (cfg) {
          if (cfg && cfg.iceServers) cfg.iceServers = [];
          return origSetConfig.call(this, cfg);
        };
      }
    } catch (e) {}
  }

  // ---- WebGPU adapter info ----
  try {
    if (navigator.gpu && typeof navigator.gpu.requestAdapter === 'function') {
      if (!cfg.webgpu_enabled) {
        // Software renderer: no adapter available.
        Object.defineProperty(Navigator.prototype, 'gpu', {
          get: () => undefined,
          configurable: true,
        });
      } else {
        const origRequestAdapter = navigator.gpu.requestAdapter.bind(navigator.gpu);
        navigator.gpu.requestAdapter = async function (...args) {
          const adapter = await origRequestAdapter(...args);
          if (!adapter) return adapter;
          const info = {
            vendor: cfg.webgpu_vendor,
            architecture: cfg.webgpu_architecture,
            device: '',
            description: cfg.webgpu_description,
          };
          // requestAdapterInfo (deprecated) + info getter (current)
          if (typeof adapter.requestAdapterInfo === 'function') {
            adapter.requestAdapterInfo = async () => info;
          }
          try {
            Object.defineProperty(adapter, 'info', { get: () => info, configurable: true });
          } catch (e) {}
          return adapter;
        };
      }
    }
  } catch (e) {}

  // ---- Font enumeration spoofing ----
  // Detection scripts measure text width for a probe string in each candidate
  // font vs a fallback. We force the fallback (font "not installed") for any
  // font that isn't in our allow-list, and allow those that are.
  try {
    if (Array.isArray(cfg.fonts) && cfg.fonts.length) {
      const allow = new Set(cfg.fonts.map((f) => f.toLowerCase()));
      // document.fonts.check(font) → true only for allowed families
      if (document.fonts && typeof document.fonts.check === 'function') {
        const origCheck = document.fonts.check.bind(document.fonts);
        document.fonts.check = function (fontSpec, text) {
          try {
            // fontSpec looks like: '12px "Some Font"'
            const m = /\d+px\s+[\"']?([^\"']+)[\"']?/.exec(fontSpec);
            if (m) {
              const fam = m[1].trim().toLowerCase();
              const generic = new Set(['serif', 'sans-serif', 'monospace', 'cursive', 'fantasy', 'system-ui']);
              if (!generic.has(fam) && !allow.has(fam)) return false;
            }
          } catch (e) {}
          return origCheck(fontSpec, text);
        };
      }
      // Expose the count via a non-standard hook some scripts read
      try {
        Object.defineProperty(navigator, '__installedFontCount', {
          get: () => cfg.fonts.length,
          configurable: true,
        });
      } catch (e) {}
    }
  } catch (e) {}

  // ---- Geolocation spoofing ----
  if (cfg.spoof_geolocation && navigator.geolocation) {
    try {
      const coords = {
        latitude: cfg.geo_latitude,
        longitude: cfg.geo_longitude,
        accuracy: cfg.geo_accuracy,
        altitude: null,
        altitudeAccuracy: null,
        heading: null,
        speed: null,
      };
      const makePosition = () => ({
        coords,
        timestamp: Date.now(),
      });
      navigator.geolocation.getCurrentPosition = function (success, error) {
        try { success(makePosition()); } catch (e) {}
      };
      navigator.geolocation.watchPosition = function (success, error) {
        try { success(makePosition()); } catch (e) {}
        return 0;
      };
    } catch (e) {}
  }

  // ---- Headless stealth: window.chrome + permissions coherence ----
  try {
    if (!window.chrome) {
      Object.defineProperty(window, 'chrome', {
        value: { runtime: {}, app: {}, csi: function () {}, loadTimes: function () {} },
        configurable: true,
        writable: true,
      });
    } else if (!window.chrome.runtime) {
      window.chrome.runtime = {};
    }
  } catch (e) {}
  try {
    // In headless, permissions.query for 'notifications' returns 'denied'
    // while Notification.permission is 'default' — a classic tell. Align them.
    if (navigator.permissions && navigator.permissions.query) {
      const origQuery = navigator.permissions.query.bind(navigator.permissions);
      navigator.permissions.query = function (params) {
        if (params && params.name === 'notifications') {
          return Promise.resolve({ state: Notification.permission, onchange: null });
        }
        return origQuery(params);
      };
    }
  } catch (e) {}

  // ---- Screen / window size consistency ----
  try {
    Object.defineProperty(window.screen, 'width', { get: () => cfg.screen_width });
    Object.defineProperty(window.screen, 'height', { get: () => cfg.screen_height });
    Object.defineProperty(window.screen, 'availWidth', { get: () => cfg.avail_screen_width });
    Object.defineProperty(window.screen, 'availHeight', { get: () => cfg.avail_screen_height });
    Object.defineProperty(window.screen, 'colorDepth', { get: () => cfg.color_depth });
    Object.defineProperty(window.screen, 'pixelDepth', { get: () => cfg.color_depth });
    Object.defineProperty(window, 'devicePixelRatio', { get: () => cfg.pixel_ratio });
  } catch (e) {}
})();
"""


def build_init_script(fp: Fingerprint) -> str:
    """Build the JS init script that patches the browser on every new doc.

    Returns a single JS string with cfg inlined as JSON. Playwright accepts
    either a string or path; we pass the string.
    """
    cfg = {
        "platform": fp.platform,
        "vendor": fp.vendor,
        "oscpu": fp.oscpu,
        "languages": fp.languages,
        "hardware_concurrency": fp.hardware_concurrency,
        "device_memory": fp.device_memory,
        "connection_type": fp.connection_type,
        "connection_downlink": fp.connection_downlink,
        "connection_rtt": fp.connection_rtt,
        "plugins": fp.plugins,
        "webgl_vendor": fp.webgl_vendor,
        "webgl_renderer": fp.webgl_renderer,
        "audio_noise_seed": fp.audio_noise_seed,
        "canvas_noise_seed": fp.canvas_noise_seed,
        "block_webrtc_ip": fp.block_webrtc_ip,
        "screen_width": fp.screen_width,
        "screen_height": fp.screen_height,
        "avail_screen_width": fp.avail_screen_width,
        "avail_screen_height": fp.avail_screen_height,
        "color_depth": fp.color_depth,
        "pixel_ratio": fp.pixel_ratio,
        "webgpu_enabled": fp.webgpu_enabled,
        "webgpu_vendor": fp.webgpu_vendor,
        "webgpu_architecture": fp.webgpu_architecture,
        "webgpu_description": fp.webgpu_description,
        "fonts": fp.fonts,
        "spoof_geolocation": fp.spoof_geolocation,
        "geo_latitude": fp.geo_latitude,
        "geo_longitude": fp.geo_longitude,
        "geo_accuracy": fp.geo_accuracy,
    }
    cfg_json = json.dumps(cfg, separators=(",", ":"))
    return INIT_SCRIPT_TEMPLATE.replace("__AD_CFG__", cfg_json)