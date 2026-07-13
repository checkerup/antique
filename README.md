# antique

**A self-hosted, open-source replacement for AdsPower — multi-profile browser farm with fingerprint spoofing, proxy rotation, .adb bundle import, and an AdsPower-compatible REST API.**

> Built autonomously to replace a paid AdsPower subscription with the same UX and API surface, no licensing, fully local.

[English](README.md) · [Русский](README.ru.md) · [中文](README.zh.md)

---

## Table of contents

1. [What this is (TL;DR for agents)](#1-what-this-is-tldr-for-agents)
2. [Quick start](#2-quick-start)
3. [Architecture overview](#3-architecture-overview)
4. [Module map](#4-module-map)
5. [Data model and storage schema](#5-data-model-and-storage-schema)
6. [Profile lifecycle](#6-profile-lifecycle)
7. [CLI reference](#7-cli-reference)
8. [REST API reference](#8-rest-api-reference)
9. [Cookie import / export formats](#9-cookie-import--export-formats)
10. [Fingerprint system](#10-fingerprint-system)
11. [Full-profile (.adb) import flow](#11-full-profile-adb-import-flow)
12. [CDP multiplexer](#12-cdp-multiplexer)
13. [Data directory layout](#13-data-directory-layout)
14. [Testing](#14-testing)
15. [Known limitations and roadmap](#15-known-limitations-and-roadmap)
16. [Environment variables](#16-environment-variables)
17. [License](#17-license)

---

## 1. What this is (TL;DR for agents)

antique is a Python service that:

- Spawns isolated Chromium contexts (Playwright `launch_persistent_context`) per profile — each profile has its own user data dir, cookies, localStorage, IndexedDB.
- Generates internally-consistent browser fingerprints (UA, navigator, screen, timezone, locale, WebGL vendor/renderer, audio + canvas noise seeds) and injects JS init scripts to patch the browser at boot.
- Persists profiles in SQLite (`data/antique.db`) — proxies, fingerprints, cookies, tags, sessions, import bookkeeping.
- Imports `.adb` profile bundles exported from AdsPower (cookies + LocalStorage + IndexedDB). The import uses native Chromium reading instead of brittle LevelDB parsing — we copy the source directories into Playwright's `user_data_dir` and let Chromium read them itself.
- Exposes an AdsPower-compatible REST API on `http://127.0.0.1:<port>/...` so existing scripts that already talk to AdsPower can switch by changing the base URL.
- Ships a single-page dashboard at `/` (or `/dashboard`) and a FastAPI Swagger at `/docs`.
- 300+ pytest tests passing.
- Geo matching (timezone/locale/geolocation aligned to the proxy exit country), proxy rotation/failover, headless stealth, and a stealth self-test harness.
- Swappable browser engines: Chromium, Google Chrome, Microsoft Edge, Firefox, Camoufox (deep engine-level stealth), WebKit.
- One-click AdsPower backup import (whole backup folder or a single profile), preserving user_id, cookies, proxy, tags.
- Dashboard with light/dark themes, engine picker, and an AdsPower import flow.
- Bulk operations: start/stop/delete/export multiple profiles, bulk proxy import/assign.
- Group management and filtering.
- Proxy health-check with IP detection and latency measurement.
- Fingerprint editing from the dashboard UI.

**What it is NOT (yet):**
- Not a headless browser farm for thousands of profiles — designed for tens of profiles per machine.
- Not a multi-user auth layer — single-process, no auth on the REST API, runs locally.
- Not a proxy provider — uses proxies you supply.

**When to use it:** when an AdsPower-compatible local browser farm is needed with full profile isolation, fingerprint control, and .adb bundle import — without paying for AdsPower.

**When NOT to use it:** when you need >100 concurrent browser contexts on one machine, when you need cross-process profile sharing, or when you need a managed cloud solution.

---

## 2. Quick start

### Requirements

- Python 3.10+
- Windows / macOS / Linux
- Playwright (`pip install playwright && playwright install chromium`)

### Install

```bash
git clone https://github.com/<your-org>/antique
cd antique
python -m venv .venv && source .venv/bin/activate   # or .venv\Scripts\activate on Windows
pip install -e .
playwright install chromium
```

### Run the server

```bash
python -m src.cli serve --ui-port 8080
```

That gives you:

- Dashboard: <http://127.0.0.1:8080/>
- REST API: <http://127.0.0.1:8080/user/list>
- API docs: <http://127.0.0.1:8080/docs>
- Health: <http://127.0.0.1:8080/health>

### Create a profile and launch it

```bash
# Create a profile
python -m src.cli create "My first profile" --tags test

# List profiles
python -m src.cli list

# Launch (prints debug port + websocket endpoint)
python -m src.cli start <user_id>

# Stop
python -m src.cli stop <user_id>
```

Or via the REST API:

```bash
curl -X POST http://127.0.0.1:8080/user/create \
  -H 'Content-Type: application/json' \
  -d '{"name": "Profile 1", "tags": ["test"]}'

curl -X POST http://127.0.0.1:8080/user/start \
  -H 'Content-Type: application/json' \
  -d '{"user_id": "<user_id>"}'
```

### Import an AdsPower `.adb` bundle

```bash
# Cookies only (fast, works with .txt/.json/.adb/.zip/.tar.gz)
python -m src.cli import-cookies path/to/bundle.adb --name "Imported"

# Full profile — copies LocalStorage + IndexedDB into the new profile
python -m src.cli import-cookies path/to/bundle.adb --full --name "Full import"
```

---

## 3. Architecture overview

```
                           ┌──────────────────────────────────┐
                           │           FastAPI app            │
                           │   (src/api/server.py + routes)   │
                           ├──────────────────────────────────┤
                           │                                  │
       REST /user/*  ───►   │  ProfileStore (SQLite)           │
       WS /devtools/* ───►  │  BrowserLauncher (Playwright)    │
                           │  CDPProxy (CDP multiplexer)      │
                           │                                  │
                           └─────────┬──────────┬─────────────┘
                                     │          │
                                     ▼          ▼
                            ┌────────────────────────┐
                            │  data/                  │
                            │  ├─ antique.db       │  ← profiles, sessions, tags, groups
                            │  └─ profiles/<user_id>/ │  ← Playwright user_data_dir per profile
                            │      ├─ Default/         │  ← cookies, cache, Local Storage, IndexedDB
                            │      └─ ...              │
                            └────────────────────────┘
                                     │
                                     ▼
                            ┌────────────────────────┐
                            │  Chromium (one per      │
                            │  running profile)       │
                            └────────────────────────┘
```

**Three layers:**

1. **Storage layer** (`src/core/storage.py`, `src/core/profile.py`) — SQLModel/SQLite. Profiles, sessions, tags, groups, proxy/fingerprint/cookies as JSON-encoded columns.
2. **Browser layer** (`src/core/browser.py`, `src/core/cdp.py`, `src/core/fingerprint.py`, `src/core/cookie.py`) — Playwright persistent contexts, fingerprint JS injection, CDP multiplexer, cookie/profile import.
3. **Interface layer** (`src/api/server.py`, `src/api/routes.py`, `src/cli.py`, `src/ui/dashboard.py`) — FastAPI REST + WS, typer CLI, single-page HTML dashboard.

---

## 4. Module map

```
src/
├── __init__.py
├── cli.py                         ← typer CLI (serve, create, list, start, stop, delete,
│                                    import-cookies, reimport, export-cookies, export/import-profile,
│                                    warm, run-flow, geo-match, proxy-rotate, detect-test, fingerprint)
├── consoleutil.py                  ← UTF-8 console fix + ASCII fallback (Windows CP1251/CP437)
├── core/
│   ├── __init__.py
│   ├── storage.py                 ← SQLModel models (ProfileRecord, SessionRecord, TagRecord,
│   │                                 GroupRecord) + engine/session helpers
│   ├── profile.py                 ← Profile dataclass (public) + ProfileStore (CRUD)
│   ├── fingerprint.py             ← Fingerprint dataclass + generate_fingerprint() + JS init
│   │                                 script template + Playwright launch options
│   ├── proxy.py                   ← ProxyConfig + parse_proxy() + AdsPower↔Playwright
│   │                                 shape conversion
│   ├── cookie.py                  ← Cookie dataclass, Netscape/JSON/.adb parsers,
│   │                                 LocalStorage + IndexedDB extraction/copying
│   ├── browser.py                 ← BrowserLauncher — launches persistent Chromium contexts,
│   │                                 records sessions, applies imported state
│   ├── cdp.py                     ← CDPProxy — multiplexes a single debug port across
│   │                                 multiple user_ids, exposes /json/list + WS routes
│   ├── automation.py              ← Cookie Robot / no-code flow runner (Step model,
│   │                                 parse_flow, cookie_robot_flow, FlowRunner)
│   ├── portable.py                ← Portable .antq profile export/import (build_bundle,
│   │                                 export_profile, import_profile)
│   ├── geo.py                     ← Country/proxy-exit → timezone/locale/languages/geo
│   │                                 (geo_for_country, geo_from_proxy, apply_geo_to_fingerprint)
│   ├── proxy_pool.py              ← Proxy pool + rotation/failover (sticky/round_robin/random)
│   ├── detect.py                  ← Stealth self-test harness (build_collector_script, score_report)
│   └── engines.py                 ← Browser engine registry (EngineSpec, resolve_engine, list_engines)
├── api/
│   ├── __init__.py
│   ├── server.py                  ← FastAPI app factory, CORS, mount UI + API routes
│   └── routes.py                  ← All REST endpoints + WS handlers
└── ui/
    ├── __init__.py
    ├── dashboard.py               ← Single-page HTML dashboard router
    └── templates/
        └── index.html             ← Dashboard SPA (vanilla JS + fetch())

tests/
├── test_fingerprint.py            ← Fingerprint generation, init script injection
├── test_cookie.py                 ← Cookie parsing (all formats) + .adb bundle handling
├── test_profile.py                ← ProfileStore CRUD
├── test_proxy.py                  ← Proxy config validation
├── test_storage.py                ← SQLite engine + migrations
└── test_profile_import.py         ← Full-profile .adb import flow (NEW)
```

---

## 5. Data model and storage schema

Database: `data/antique.db` (SQLite, single file).

### Tables

```sql
-- Profiles: one row per browser profile
CREATE TABLE profiles (
    user_id                  TEXT PRIMARY KEY,    -- 8-char base36 random id
    name                     TEXT NOT NULL,
    group_id                 TEXT NOT NULL DEFAULT '0',
    user_proxy_config        TEXT NOT NULL DEFAULT '{}',  -- JSON
    fingerprint_config       TEXT NOT NULL DEFAULT '{}',  -- JSON of Fingerprint dataclass
    cookies                  TEXT NOT NULL DEFAULT '[]',  -- JSON list of cookie dicts
    tags                     TEXT NOT NULL DEFAULT '[]',  -- JSON list of strings
    remark                   TEXT NOT NULL DEFAULT '',
    import_source_path       TEXT NOT NULL DEFAULT '',   -- path to extracted .adb bundle
    initial_state_applied    INTEGER NOT NULL DEFAULT 0, -- bool: has LocalStorage/IDB been copied?
    created_at               DATETIME,
    updated_at               DATETIME,
    last_launched_at         DATETIME,
    launch_count             INTEGER NOT NULL DEFAULT 0
);

-- Sessions: one row per running browser
CREATE TABLE sessions (
    session_id   TEXT PRIMARY KEY,
    user_id      TEXT NOT NULL REFERENCES profiles(user_id),
    debug_port   INTEGER NOT NULL,
    ws_endpoint  TEXT NOT NULL,
    pid          INTEGER,
    started_at   DATETIME,
    status       TEXT NOT NULL DEFAULT 'running'   -- running | stopped | crashed
);

CREATE TABLE tags (
    id    INTEGER PRIMARY KEY,
    name  TEXT UNIQUE NOT NULL,
    color TEXT NOT NULL DEFAULT '#888888'
);

CREATE TABLE groups (
    group_id    TEXT PRIMARY KEY,
    name        TEXT NOT NULL,
    sort_order  INTEGER NOT NULL DEFAULT 0
);
```

### Why JSON-encoded columns?

Proxies, fingerprints, and cookies are heterogeneous dicts/lists with many optional fields. JSON-encoded TEXT columns avoid sparse-tables-of-many-columns and keep migrations trivial. Trade-off: no SQL-level querying of fingerprint fields, which we don't need.

### Profile dataclass vs ProfileRecord

- `Profile` (in `src/core/profile.py`) — the public dataclass. Decoupled from storage so the API doesn't leak SQLModel.
- `ProfileRecord` (in `src/core/storage.py`) — the persisted row. `_record_to_profile()` builds a `Profile` from a `ProfileRecord`.

---

## 6. Profile lifecycle

```
            ┌──────────┐
            │ created  │  ← POST /user/create, cli create, import-cookies
            └────┬─────┘
                 │
                 ▼
            ┌──────────┐
            │ idle     │  ← profile exists, browser not running
            └────┬─────┘
                 │  POST /user/start  or  cli start
                 ▼
            ┌──────────┐
            │ running  │  ← Playwright persistent context is live
            └────┬─────┘
                 │  POST /user/stop  or  cli stop
                 ▼
            ┌──────────┐
            │ stopped  │  ← context closed, SessionRecord.status = 'stopped'
            └──────────┘

  (any state) ──► deleted   ← POST /user/delete, cli delete (cascades to sessions)
```

### Full-profile import lifecycle (extra)

```
  created → import_source_path set → (first launch) → LocalStorage/IDB copied
                                                              → initial_state_applied = True
                                                              → (later launches skip the copy)
```

The `initial_state_applied` flag ensures we only copy the source bundle's `Local Storage/leveldb/` and `IndexedDB/` once. Re-imports require `cli reimport <user_id>` or `POST /user/{id}/reimport` which resets the flag.

---

## 7. CLI reference

```text
python -m src.cli serve [--ui-port 8080] [--cdp-port 5555] [--host 127.0.0.1] [--headless]
python -m src.cli list [--search TEXT] [--group ID] [--tag TEXT]
python -m src.cli create NAME [--group ID] [--proxy-type TYPE] [--proxy-host HOST]
                        [--proxy-port PORT] [--proxy-user U] [--proxy-password P]
                        [--remark TEXT] [--tags t1,t2] [--user-id ID]
                        [--fingerprint-seed SEED]
python -m src.cli start USER_ID [--port DEBUG_PORT]
python -m src.cli stop USER_ID
python -m src.cli delete USER_ID [--yes]
python -m src.cli import-cookies PATH [--name NAME] [--proxy-type TYPE] [--full]
python -m src.cli reimport USER_ID
python -m src.cli export-cookies USER_ID [--format json|netscape] [--out FILE]
python -m src.cli export-profile USER_ID [--out FILE.antq]
python -m src.cli import-profile FILE.antq [--name NAME] [--user-id ID]
python -m src.cli warm USER_ID [--url URL ...] [--urls FILE] [--dwell-min MS] [--dwell-max MS] [--scrolls N] [--headless]
python -m src.cli run-flow USER_ID FLOW.json [--stop-on-error] [--headless]
python -m src.cli geo-match USER_ID [--country US|DE|RU|...]     # align tz/locale/geolocation to a country or the proxy exit
python -m src.cli proxy-rotate USER_ID POOL.txt [--strategy sticky|round_robin|random]
python -m src.cli detect-test USER_ID [--url URL] [--headless]   # stealth self-test, graded report
python -m src.cli create ... [--geo-country US|DE|RU|...]        # create already aligned to a country
python -m src.cli engines                                       # list engines + stealth tier
python -m src.cli create ... [--engine chromium|chrome|edge|firefox|camoufox|webkit]
python -m src.cli import-backup PATH [--overwrite] [--limit N]  # import an AdsPower backup folder
python -m src.cli fingerprint [--seed SEED] [--os windows|macos|linux]
```

### Exit codes

- `0` — success
- `1` — user error (missing args, profile not found, invalid format)
- non-zero from typer for shell errors

### Environment variables

See [Environment variables](#16-environment-variables).

---

## 8. REST API reference

Base URL: `http://127.0.0.1:<ui-port>` (the same port serves UI + API; AdsPower uses 50325 separately).

All responses use the AdsPower shape: `{"code": 0, "msg": "success", "data": {...}}`.

### Health

```http
GET /health
→ {"status": "ok", "service": "antique", "version": "0.1.0"}
```

### Profiles

```http
POST /user/create
Body: {
  "name": "string",
  "group_id": "0" (optional),
  "user_proxy_config": {"proxy_type":"http","proxy_host":"...","proxy_port":...} (optional),
  "fingerprint_config": {...} (optional, partial Fingerprint allowed),
  "cookies": [{"name":"x","value":"y","domain":".example.com",...}] (optional),
  "remark": "string" (optional),
  "tags": ["string"] (optional),
  "user_id": "string" (optional, generated if omitted)
}
→ {code:0, msg:"success", data:{id, user_id, name}}

POST /user/update
Body: {user_id, name?, group_id?, user_proxy_config?, fingerprint_config?,
       cookies?, remark?, tags?}
→ {code:0, msg:"success", data:{id, user_id, name}}

GET /user/list?group_id=&page=1&page_size=100&search=&tag=
→ {code:0, msg:"success", data:{list:[Profile...], total, page, page_size}}

POST /user/delete
Body: {user_id}
→ {code:0, msg:"success", data:{user_id, deleted:true}}

POST /user/start
Body: {user_id, debug_port? (optional), launch_args? (optional, unused)}
→ {code:0, msg:"success", data:{user_id, debug_port, ws_endpoint, pid, session_id}}

POST /user/stop
Body: {user_id}
→ {code:0, msg:"success", data:{user_id, stopped:true|false}}

GET /user/active
→ {code:0, msg:"success", data:{list:[{user_id, session_id, debug_port,
                                       ws_endpoint, pid}]}}

POST /user/import
Body: {name, source_path}   OR   multipart file=@bundle.adb
→ creates a profile from an AdsPower bundle (cookies-only by default,
  set Content-Type with multipart to use the full extraction path)

POST /user/{user_id}/reimport
→ resets initial_state_applied so the next launch re-copies LocalStorage/IDB
  from the saved bundle path
```

### Geo / proxy-pool / portable / detect (v0.2)

```http
GET  /geo/countries
→ {code:0, data:{countries:["US","DE",...]}}

POST /user/{user_id}/geo/match      Body: {country?: "DE"}   # omit to derive from the profile's proxy country
→ aligns timezone/locale/languages/geolocation; persists onto the fingerprint

POST /proxy/pool/next               Body: {proxy_list, strategy?: sticky|round_robin|random, user_id?}
→ {code:0, data:{proxy:{...}, assigned, server}}   # optionally assigns to user_id

POST /user/{user_id}/export/portable
→ {code:0, data:{bundle:{...}}}   # .antq bundle (fingerprint+proxy+cookies+tags)

POST /user/import/portable          Body: {bundle:{...}, name?, user_id?}
→ {code:0, data:{user_id, name, cookie_count}}

POST /detect/score                  Body: {signals:{...}, expected?:{...}}
→ {code:0, data:{score, grade, ok, checks, failures}}   # pure stealth scoring, no browser

GET  /engine/list
→ {code:0, data:{list:[{key,label,base,stealth,channel,needs_install,supports_extensions,supports_cdp}]}}

POST /user/import/backup            Body: {source_path, overwrite?, limit?}
→ {code:0, data:{imported_count, updated_count, skipped_count, error_count, cookie_sources, ...}}
```

### Profile shape returned by `/user/list`

```json
{
  "user_id": "k7m3x9p2",
  "name": "Profile 1",
  "group_id": "0",
  "created_at": "2026-06-30T10:00:00",
  "updated_at": "2026-06-30T10:00:00",
  "last_launched_at": null,
  "launch_count": 0,
  "remark": "",
  "tags": [],
  "user_proxy_config": {},
  "fingerprint_config": {},
  "cookies": [],
  "status": "Inactive",
  "debug_port": null,
  "ws_endpoint": null
}
```

### CDP multiplexer

```http
GET /json/version
→ {Browser, Protocol-Version, User-Agent, webSocketDebuggerUrl, ...}

GET /json/list?user_id=<id>
→ [{id, type:"page", title, url, webSocketDebuggerUrl, description}, ...]

WS /devtools/page/{user_id}/{target_id}
→ Chromium DevTools Protocol websocket
```

---

## 9. Cookie import / export formats

### Supported import formats

| Format | Detection | Notes |
|---|---|---|
| Netscape `cookies.txt` | `.txt` extension | curl/wget format; tabs or spaces |
| Playwright/CDP JSON | `.json` extension | list of `{name, value, domain, ...}` dicts |
| AdsPower `.adb` | `.adb` / `.zip` / `.tar` / `.tgz` / folder | cookies + LocalStorage + IndexedDB |

### Supported export formats

- `json` (default) — Playwright/Chrome DevTools shape
- `netscape` — universal curl-compatible `cookies.txt`

### Auto-detection in `import_cookies(path)`

```python
def import_cookies(path):
    p = Path(path)
    if p.is_dir() or p.suffix.lower() in (".adb", ".zip", ".tar", ".tgz"):
        return import_adspower_profile(p)
    if p.suffix.lower() == ".json":
        return import_cookies_json(p.read_text())
    return import_cookies_netscape(p.read_text())
```

### Parsing AdsPower `.adb`

`.adb` is a Chrome user-profile bundle (folder, `.zip`, or `.tar.gz`). The Chromium cookies table is at `<profile>/Default/Cookies` (SQLite).

The parser:

1. Extracts the archive to a temp dir (if needed).
2. Walks for `*/Cookies` files; prefers `Default/Cookies`, falls back to `Profile 1/2/3/Cookies`.
3. Opens the SQLite DB in RO mode (`file:...?mode=ro`); falls back to a private temp copy if locked.
4. Reads the cookies table. Handles schema variations (older Chrome lacks `samesite` and `is_persistent` columns).
5. Converts Chrome's `expires_utc` (Windows FILETIME, microseconds since 1601-01-01) to Unix epoch seconds.

---

## 10. Fingerprint system

A `Fingerprint` is a coherent bundle of browser-visible attributes:

- **Identity**: User-Agent, navigator.platform/vendor/oscpu, webdriver flag
- **Screen**: width/height/colorDepth/pixelRatio + window.innerWidth/Height
- **Locale / timezone**: navigator.languages, Intl timezone
- **WebGL**: vendor + renderer strings (via `WEBGL_debug_renderer_info`)
- **WebGPU**: adapter vendor/architecture/description (via `navigator.gpu.requestAdapter().requestAdapterInfo()`), coherent with the WebGL GPU; software-renderer profiles disable `navigator.gpu`
- **Fonts**: per-OS installed-font allow-list, enforced through `document.fonts.check`
- **Audio**: deterministic noise seed for AudioContext jitter
- **Canvas**: deterministic noise seed for `toDataURL`/`toBlob` pixel jitter
- **WebRTC**: IP-leak prevention (`block_webrtc_ip`)
- **Geolocation**: `navigator.geolocation` coordinates + accuracy, spoofable and aligned to the proxy exit country (see [geo matching](#geo-matching-timezone--locale--geolocation))
- **Headless stealth**: `window.chrome`/`chrome.runtime` shims + `permissions.query` coherence so new-headless doesn't leak the classic tells
- **Plugins**: realistic Chrome plugin list (2-5 entries)
- **Connection**: type/downlink/rtt (Network Information API)
- **Hardware**: hardwareConcurrency, deviceMemory

### Geo matching (timezone / locale / geolocation)

`src/core/geo.py` maps an ISO country code (or a proxy's exit country) to a
coherent `GeoProfile` (timezone, locale, `navigator.languages`, lat/lon) and
applies it onto a fingerprint so a US proxy never ships a Moscow timezone.

```python
from src.core.geo import geo_for_country, geo_from_proxy, apply_geo_to_fingerprint
apply_geo_to_fingerprint(fp, geo_for_country("DE"))          # explicit country
apply_geo_to_fingerprint(fp, geo_from_proxy(profile.proxy))  # from proxy exit
```

CLI: `create --geo-country DE`, or `geo-match USER_ID --country DE` (omit
`--country` to derive it from the profile's proxy).

### Stealth self-test

`src/core/detect.py` collects live signals from a profile page
(`build_collector_script`) and grades them (`score_report`): a 0-100 stealth
score + letter grade, flagging automation tells (webdriver, missing
`window.chrome`, permission mismatch, platform/UA disagreement) and
fingerprint drift vs the intended values. CLI: `detect-test USER_ID`.

### Generation

```python
from src.core.fingerprint import generate_fingerprint

fp = generate_fingerprint()                                  # random
fp = generate_fingerprint(seed="my-profile-1")               # deterministic
fp = generate_fingerprint(os_family="macos")                 # macOS UA + screen
```

Coherence rules:
- OS family ↔ UA ↔ platform ↔ vendor ↔ screen
- Locale ↔ timezone pool (e.g. `en-GB` → `Europe/London`)
- WebGL vendor ↔ renderer (NVIDIA vendor never paired with Apple GPU)
- UA versions are recent (Chrome 118-132)

### Injection

Two layers:

1. **Launch args** (`to_playwright_launch_options`) — handles proxy, locale, UA, timezone, window size, viewport, device scale factor. Done at Chromium start.

2. **JS init script** (`build_init_script`) — patches `Navigator.prototype`, `HTMLCanvasElement.prototype`, `AudioContext.prototype`, `RTCPeerConnection.prototype`, etc. on every new document. Canvas/audio noise uses Mulberry32 seeded by the fingerprint's `audio_noise_seed` and `canvas_noise_seed` for reproducibility.

### Limitations

- WebGL is read-only on Chromium for the unmasked fields — we patch `getParameter` and `getExtension`, but if the page uses `WEBGL_debug_renderer_info` differently, the patch can be bypassed.
- Canvas noise is mild (±2 per channel) — strong noise breaks visual rendering on some sites. Increase noise on a per-profile basis if needed.
- Fonts are enforced via `document.fonts.check` (measure-based enumeration returns the allow-list). Deep canvas-measurement font probes that bypass `document.fonts` are not fully covered yet.
- WebGPU spoofing patches `requestAdapterInfo()`/`adapter.info`; it does not rewrite low-level `GPUAdapter` limits/features.

---

## 11. Full-profile (.adb) import flow

The flow for a full-profile import:

```
1. POST /user/import  (or  cli import-cookies --full PATH)
   ↓
2. profile created (user_id assigned)
   ↓
3. .adb bundle extracted to  data/profiles/imports/<user_id>/
   ↓
4. Cookies parsed from <user_id>/Default/Cookies, written to profile.cookies
   ↓
5. profile.import_source_path = "<user_id>"   ← bookmark for launcher
   ↓
6. (later) POST /user/start
   ↓
7. BrowserLauncher._maybe_apply_imported_state(profile, user_dir):
     - if import_source_path set AND initial_state_applied is False:
       - find_profile_default_dir(<user_id>)
       - copytree Local Storage/leveldb  →  user_dir/Default/Local Storage/leveldb
       - copytree IndexedDB              →  user_dir/Default/IndexedDB
       - mark_initial_state_applied(user_id)
   ↓
8. Chromium reads the directories natively and treats them as if it had
   written them itself — no LevelDB parser, no Snappy codec, no version drift.
```

### Why copy instead of parse?

Chrome ≥ 61 stores `localStorage` in Snappy-compressed LevelDB. IndexedDB uses V8 structured-clone values. Re-implementing the decoder is:

- Version-coupled (Chrome's encoding changes between versions).
- Windows-hostile (`plyvel` requires native LevelDB + Snappy builds).
- Fragile (one byte out of place and the whole profile fails to load).

Copying the directories verbatim is dumb, reliable, and works for every Chromium version Playwright ships.

### Re-importing

After a `.adb` re-export:

```bash
python -m src.cli reimport <user_id>
# or
curl -X POST http://127.0.0.1:8080/user/<user_id>/reimport
```

This resets `initial_state_applied = False`. The next launch wipes the existing `Local Storage/leveldb/` and `IndexedDB/` (because `force=True` is set inside `apply_initial_state_to_user_data` when re-applying) and re-copies from the bundle.

### Force flag

`apply_initial_state_to_user_data(..., force=True)` overwrites existing dirs. The launcher uses `force=False` on first apply (so we don't accidentally clobber state we just copied), and the reimport flow flips this explicitly.

---

## 12. CDP multiplexer

Playwright owns the Chromium process per profile, but external automation (Selenium, Puppeteer, custom scripts) wants a single CDP endpoint per profile. The `CDPProxy` (`src/core/cdp.py`) multiplexes:

- `GET /json/version` — returns a fake version payload pointing at `ws://127.0.0.1:5555/devtools/browser`
- `GET /json/list?user_id=<id>` — lists pages for a profile
- `WS /devtools/page/{user_id}/{target_id}` — proxy a websocket connection to the right Playwright page

Note: the WS endpoint is **simulated** — actual CDP traffic goes through Playwright's context, not a real Chrome debug port. This works for browser-attached automation that doesn't need low-level protocol features.

For real CDP, point your automation at the per-profile websocket returned by `POST /user/start`:

```json
{"ws_endpoint": "ws://127.0.0.1:50321/devtools/browser", "debug_port": 50321}
```

---

## 13. Data directory layout

```
data/
├── antique.db                 ← SQLite (profiles, sessions, tags, groups)
└── profiles/
    ├── <user_id>/                ← Playwright user_data_dir for the profile
    │   ├── Default/
    │   │   ├── Cookies
    │   │   ├── Local Storage/leveldb/...
    │   │   ├── IndexedDB/...
    │   │   └── (all Chromium user-data files)
    │   └── ...
    └── imports/
        └── <user_id>/            ← Extracted .adb bundle (full-profile imports)
            ├── Default/...
            └── ...
```

Override with `ANTIQUE_DATA_DIR=/some/path` (env var).

---

## 14. Testing

```bash
python -m pytest                    # all tests
python -m pytest tests/test_cookie.py -v
python -m pytest -k adb             # only .adb-related tests
```

Test files:

- `test_storage.py` — SQLite engine, tables
- `test_profile.py` — ProfileStore CRUD, full-profile fields, session bookkeeping
- `test_fingerprint.py` — Fingerprint generation + init script injection
- `test_proxy.py` — ProxyConfig validation + Playwright shape conversion
- `test_cookie.py` — Cookie parsing (Netscape/JSON/.adb), LocalStorage/IndexedDB extraction
- `test_profile_import.py` — Full-profile import flow
- `test_webgpu_fonts.py` — WebGPU adapter spoofing + font allow-list generation & injection
- `test_automation.py` — Cookie Robot / flow parser, builder, and runner against a fake page
- `test_portable.py` — Portable `.antq` export/import round-trip
- `test_geo.py` — Country/proxy → timezone/locale/geolocation matching
- `test_proxy_pool.py` — Proxy pool rotation strategies + failover
- `test_detect.py` — Stealth self-test scoring + collector script
- `test_console.py` — Windows UTF-8 console fix + ASCII fallback
- `test_api_endpoints.py` — HTTP-level tests (TestClient): extension wiring regression, geo-match, proxy-pool, portable round-trip, detect scoring
- `test_auth.py` — API auth + origin guard (DNS-rebinding, Bearer token, tunnel allow-list)
- `test_engines.py` — Browser engine registry: specs, capabilities, alias/priority resolution, launcher wiring (NEW)

Run only the newest suites:

```bash
python -m pytest tests/test_engines.py tests/test_api_endpoints.py -v
```

---

## 15. Known limitations and roadmap

### Done (in this build)

- [x] Multi-profile isolated Chromium contexts
- [x] Fingerprint generation + JS injection
- [x] HTTP/HTTPS/SOCKS5 proxies
- [x] Cookie import (Netscape, JSON, .adb bundle)
- [x] Cookie export (Netscape, JSON)
- [x] Full .adb profile import (cookies + LocalStorage + IndexedDB)
- [x] Re-import flow (`cli reimport`, `POST /user/{id}/reimport`)
- [x] AdsPower-compatible REST API
- [x] CDP multiplexer (simulated)
- [x] Single-page dashboard with full CRUD
- [x] **Bulk operations** (start/stop/delete/export multiple profiles at once)
- [x] **Group filtering** in UI and API (`GET /group/list`, filter by group_id)
- [x] **Proxy health-check** per profile (`POST /user/{id}/proxy/check`, `POST /proxy/check`)
- [x] **Bulk proxy import** (paste proxy list, auto-assign to profiles, `POST /user/bulk/proxy/import`)
- [x] **Fingerprint editing from UI** (tabbed modal: UA, screen, hardware, network, WebGL)
- [x] **Bulk proxy assignment** (`POST /user/bulk/proxy/assign`)
- [x] Proxy list parser (supports `type://host:port`, `type://user:pass@host:port`, `host:port:user:pass`)
- [x] **Extension manager** (install from unpacked dir, .crx, Chrome Web Store; per-profile assignment)
- [x] **MCP server** (JSON-RPC 2.0 over stdio, 12 tools: list/open/close/navigate/screenshot/execute_script/cookies/proxy_check)
- [x] **Multi-engine support** (Chromium, Firefox, Camoufox/ShardX; per-profile or env-var)
- [x] **Client Hints** (Sec-CH-UA headers via custom browser args, auto-generated from fingerprint)
- [x] **Extensions per profile** (`--load-extension` + `--disable-extensions-except` at launch)
- [x] **WebGPU fingerprint spoofing** (adapter vendor/architecture/description, coherent with WebGL GPU)
- [x] **Font fingerprint spoofing** (per-OS installed-font allow-list via `document.fonts.check`)
- [x] **Cookie Robot / no-code automation flows** (`warm`, `run-flow`; JSON step model: goto/wait/scroll/click/type/press/hover/screenshot/eval)
- [x] **Portable profile export/import** (`.antq` bundles: fingerprint + proxy + cookies + tags, transfer between machines)
- [x] **Geo matching** (timezone/locale/languages/geolocation aligned to country or proxy exit, `src/core/geo.py`)
- [x] **Geolocation spoofing** (`navigator.geolocation` coords + accuracy, coherent with the geo profile)
- [x] **Proxy rotation + failover** (pool with sticky/round_robin/random strategies, `src/core/proxy_pool.py`)
- [x] **Headless stealth** (`window.chrome`/`chrome.runtime` shims + `permissions.query` coherence)
- [x] **Stealth self-test harness** (`detect-test`, graded 0-100 report, `src/core/detect.py`)
- [x] **Optional API auth** (`ANTIQUE_API_TOKEN` Bearer token + cross-origin/DNS-rebinding guard)
- [x] **Windows UTF-8 console fix** (no more `UnicodeEncodeError` on CP1251/CP437 terminals)
- [x] **Swappable browser engines** (Chromium/Chrome/Edge/Firefox/Camoufox/WebKit registry, `src/core/engines.py`, `/engine/list`, `create --engine`)
- [x] **Camoufox deep-stealth engine** (Gecko-level fingerprint spoofing; falls back to bundled Firefox if not installed)
- [x] **One-click AdsPower backup import** (whole backup folder or single profile; dashboard + `import-backup` CLI + `/user/import/backup`)
- [x] **Redesigned dashboard** (light/dark themes, engine picker, AdsPower import, toasts)
- [x] 300+ pytest tests passing

### Known limitations

- **Simulated CDP multiplexer.** The `/json/list` + `/devtools/page/...` endpoints don't expose a real Chrome debug port for external automation — use the per-profile websocket from `POST /user/start` instead.
- **API auth is opt-in.** Set `ANTIQUE_API_TOKEN` to require a Bearer token; unset, the API is open on `127.0.0.1` (still protected by the cross-origin guard). Single-process, no multi-user roles.
- **No proxy provider integration.** You supply proxies; we don't pull them from BrightData/Decodo/etc. Rotation/failover over a supplied pool is implemented.
- **Headless stealth is best-effort.** `window.chrome` + permissions tells are patched; deep headless heuristics (paint timing, GPU quirks) are not fully covered.
- **WebRTC is block-only.** IPs are blocked; exposing a proxy-matched public IP via ICE candidate rewriting is on the roadmap.
- **Camoufox requires a separate install.** `pip install camoufox && python -m camoufox fetch`. Without it, the `camoufox` engine falls back to bundled Firefox (standard stealth, not deep).
- **Chrome/Edge engines need the real browser installed** on the host (Playwright channel). Otherwise use the bundled `chromium`.
- **Firefox/Camoufox/WebKit engines don't expose per-profile CDP or load .crx extensions** — those are Chromium-only.

### Roadmap

- [ ] **Real CDP per profile** — assign a unique `--remote-debugging-port` per profile (still simulated).
- [ ] **WebRTC proxy-IP rewriting** — expose the proxy's public IP via ICE candidates instead of blocking.
- [ ] **MCP server UI integration** — start/stop MCP from the dashboard.
- [ ] **Proxy provider integrations** — BrightData, Decodo, smartproxy.
- [ ] **Extension Web Store browser** — search and install extensions from UI.
- [x] **Cookie warming** — done via the Cookie Robot (`warm` command + automation flows).
- [x] **Proxy rotation** — done (`src/core/proxy_pool.py`, `proxy-rotate` CLI).
- [x] **Headless stealth** — done (`window.chrome` + permissions patches).
- [x] **Detection self-test** — done (`detect-test`, `src/core/detect.py`).

---

## 16. Environment variables

| Variable | Default | Purpose |
|---|---|---|
| `ANTIQUE_DATA_DIR` | `./data` | Root for `antique.db` + profile user data dirs |
| `ANTIQUE_DB` | `<data_dir>/antique.db` | SQLite path override |
| `ANTIQUE_BROWSER_CHANNEL` | (unset, uses bundled Chromium) | Playwright browser channel: `chrome`, `msedge`, `chromium-beta` |
| `ANTIQUE_API_TOKEN` | (unset, open) | If set, REST API requires `Authorization: Bearer <token>` |
| `ANTIQUE_ALLOWED_ORIGINS` | (unset) | Comma-separated extra trusted Origin substrings for remote/tunnel access (e.g. `ngrok-free.app`). Localhost is always trusted. Needed when the dashboard is exposed through a tunnel, otherwise the DNS-rebinding guard returns 403. |
| `ANTIDETECT_ENGINE` | `chromium` | Default browser engine: `chromium`, `firefox`, `camoufox` |
| `PYTHONIOENCODING` | (auto UTF-8) | The CLI now forces UTF-8 stdio itself; set to `utf-8` only if you disable that |
| `HOST` (CLI only) | `127.0.0.1` | Bind address for `serve` |
| `UI_PORT` (CLI only) | `8080` | Port for `serve` |

---

## 17. License

MIT — see `LICENSE`.