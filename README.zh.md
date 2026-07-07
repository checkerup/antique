# antidetect-local

**一个自托管、开源的 AdsPower 替代方案 —— 多 profile 浏览器农场，具备 fingerprint 伪装、proxy 轮换、.adb bundle 导入，以及 AdsPower 兼容的 REST API。**

> 自主构建，用于替代付费的 AdsPower 订阅，保持相同的 UX 和 API 接口，无需授权，完全本地运行。

[English](README.md) · [Русский](README.ru.md) · [中文](README.zh.md)

---

## 目录

1. [这是什么（给 agent 的 TL;DR）](#1-这是什么给-agent-的-tldr)
2. [快速开始](#2-快速开始)
3. [架构概览](#3-架构概览)
4. [模块结构](#4-模块结构)
5. [数据模型与存储 schema](#5-数据模型与存储-schema)
6. [Profile 生命周期](#6-profile-生命周期)
7. [CLI 参考](#7-cli-参考)
8. [REST API 参考](#8-rest-api-参考)
9. [Cookie 导入 / 导出格式](#9-cookie-导入--导出格式)
10. [Fingerprint 系统](#10-fingerprint-系统)
11. [完整 profile（.adb）导入流程](#11-完整-profileadb-导入流程)
12. [CDP multiplexer](#12-cdp-multiplexer)
13. [数据目录布局](#13-数据目录布局)
14. [测试](#14-测试)
15. [已知限制与 roadmap](#15-已知限制与-roadmap)
16. [环境变量](#16-环境变量)
17. [License](#17-license)

---

## 1. 这是什么（给 agent 的 TL;DR）

antidetect-local 是一个 Python 服务，功能如下：

- 为每个 profile 启动独立的 Chromium context（Playwright `launch_persistent_context`）—— 每个 profile 拥有自己的 user data dir、cookies、localStorage、IndexedDB。
- 生成内部一致的 browser fingerprint（UA、navigator、screen、timezone、locale、WebGL vendor/renderer、audio + canvas noise seed），并注入 JS init script 在启动时对浏览器进行 patch。
- 在 SQLite（`data/antidetect.db`）中持久化 profile —— 包括 proxy、fingerprint、cookies、tags、sessions 以及导入相关的元数据。
- 导入从 AdsPower 导出的 `.adb` profile bundle（cookies + LocalStorage + IndexedDB）。导入采用原生 Chromium 读取，而非脆弱的 LevelDB 解析 —— 我们把源目录拷贝到 Playwright 的 `user_data_dir`，让 Chromium 自己读取。
- 在 `http://127.0.0.1:<port>/...` 上暴露 AdsPower 兼容的 REST API，因此已经对接 AdsPower 的现有脚本只需修改 base URL 即可切换。
- 在 `/`（或 `/dashboard`）提供一个单页 dashboard，在 `/docs` 提供 FastAPI Swagger。
- 73/73 pytest 测试通过。

**它还不是（尚未实现的功能）：**

- 还不支持 Firefox/Camoufox —— 目前仅作为 stub（`src/core/browser.py` 只启动 Chromium）。
- 不是为数千个 profile 设计的无头浏览器农场 —— 设计目标是单机几十个 profile。
- 没有多用户鉴权层 —— 单进程，REST API 没有鉴权，本地运行。
- 不是 proxy provider —— 使用你提供的 proxy。

**何时使用它：** 当需要一个 AdsPower 兼容的本地浏览器农场，具备完整 profile 隔离、fingerprint 控制和 .adb bundle 导入能力时 —— 并且不想为 AdsPower 付费。

**何时不要使用它：** 当你需要单台机器上 >100 个并发 browser context、需要跨进程 profile 共享，或者需要一个托管云方案时。

---

## 2. 快速开始

### 环境要求

- Python 3.10+
- Windows / macOS / Linux
- Playwright（`pip install playwright && playwright install chromium`）

### 安装

```bash
git clone https://github.com/<your-org>/antidetect-local
cd antidetect-local
python -m venv .venv && source .venv/bin/activate   # or .venv\Scripts\activate on Windows
pip install -e .
playwright install chromium
```

### 启动服务

```bash
python -m src.cli serve --ui-port 8080
```

这将为你提供：

- Dashboard：<http://127.0.0.1:8080/>
- REST API：<http://127.0.0.1:8080/user/list>
- API 文档：<http://127.0.0.1:8080/docs>
- 健康检查：<http://127.0.0.1:8080/health>

### 创建一个 profile 并启动它

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

或者通过 REST API：

```bash
curl -X POST http://127.0.0.1:8080/user/create \
  -H 'Content-Type: application/json' \
  -d '{"name": "Profile 1", "tags": ["test"]}'

curl -X POST http://127.0.0.1:8080/user/start \
  -H 'Content-Type: application/json' \
  -d '{"user_id": "<user_id>"}'
```

### 导入一个 AdsPower `.adb` bundle

```bash
# Cookies only (fast, works with .txt/.json/.adb/.zip/.tar.gz)
python -m src.cli import-cookies path/to/bundle.adb --name "Imported"

# Full profile — copies LocalStorage + IndexedDB into the new profile
python -m src.cli import-cookies path/to/bundle.adb --full --name "Full import"
```

---

## 3. 架构概览

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
                             │  ├─ antidetect.db       │  ← profiles, sessions, tags, groups
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

**三层架构：**

1. **存储层**（`src/core/storage.py`、`src/core/profile.py`）—— SQLModel/SQLite。Profile、session、tag、group，以及 proxy/fingerprint/cookies 以 JSON 编码列的形式存储。
2. **浏览器层**（`src/core/browser.py`、`src/core/cdp.py`、`src/core/fingerprint.py`、`src/core/cookie.py`）—— Playwright persistent context、fingerprint JS 注入、CDP multiplexer、cookie/profile 导入。
3. **接口层**（`src/api/server.py`、`src/api/routes.py`、`src/cli.py`、`src/ui/dashboard.py`）—— FastAPI REST + WS、typer CLI、单页 HTML dashboard。

---

## 4. 模块结构

```
src/
├── __init__.py
├── cli.py                         ← typer CLI (serve, create, list, start, stop, delete,
│                                    import-cookies, reimport, export-cookies, fingerprint)
├── core/
│   ├── __init__.py
│   ├── storage.py                 ← SQLModel models (ProfileRecord, SessionRecord, TagRecord,
│   │                                 GroupRecord) + engine/session helpers
│   ├── profile.py                 ← Profile dataclass（公开）+ ProfileStore（CRUD）
│   ├── fingerprint.py             ← Fingerprint dataclass + generate_fingerprint() + JS init
│   │                                 script 模板 + Playwright launch options
│   ├── proxy.py                   ← ProxyConfig + parse_proxy() + AdsPower↔Playwright
│   │                                 格式互转
│   ├── cookie.py                  ← Cookie dataclass、Netscape/JSON/.adb parser、
│   │                                 LocalStorage + IndexedDB 抽取与拷贝
│   ├── browser.py                 ← BrowserLauncher —— 启动 persistent Chromium context，
│   │                                 记录 session，应用导入的初始状态
│   └── cdp.py                     ← CDPProxy —— 在多个 user_id 间复用单个 debug port，
│                                     暴露 /json/list + WS 路由
├── api/
│   ├── __init__.py
│   ├── server.py                  ← FastAPI app factory、CORS、挂载 UI 与 API 路由
│   └── routes.py                  ← 所有 REST 端点 + WS handler
└── ui/
    ├── __init__.py
    ├── dashboard.py               ← 单页 HTML dashboard 路由
    └── templates/
        └── index.html             ← Dashboard SPA（原生 JS + fetch()）

tests/
├── test_fingerprint.py            ← Fingerprint 生成、init script 注入
├── test_cookie.py                 ← Cookie 解析（所有格式）+ .adb bundle 处理
├── test_profile.py                ← ProfileStore CRUD
├── test_proxy.py                  ← Proxy config 校验
├── test_storage.py                ← SQLite engine + 迁移
└── test_profile_import.py         ← 完整 profile .adb 导入流程（新增）
```

---

## 5. 数据模型与存储 schema

数据库：`data/antidetect.db`（SQLite，单文件）。

### 表结构

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

### 为什么要用 JSON 编码列？

Proxy、fingerprint 和 cookies 都是异构的 dict/list，包含大量可选字段。JSON 编码的 TEXT 列避免了「稀疏表 + 大量列」的问题，也让迁移变得简单。代价是：无法在 SQL 层面查询 fingerprint 字段，但我们并不需要这种查询。

### Profile dataclass vs ProfileRecord

- `Profile`（在 `src/core/profile.py`）—— 公开的 dataclass。与存储解耦，避免 API 泄漏 SQLModel 细节。
- `ProfileRecord`（在 `src/core/storage.py`）—— 持久化的行。`_record_to_profile()` 由 `ProfileRecord` 构建 `Profile`。

---

## 6. Profile 生命周期

```
           ┌──────────┐
           │ created  │  ← POST /user/create, cli create, import-cookies
           └────┬─────┘
                │
                ▼
           ┌──────────┐
           │ idle     │  ← profile 已存在，但浏览器未启动
           └────┬─────┘
                │  POST /user/start  or  cli start
                ▼
           ┌──────────┐
           │ running  │  ← Playwright persistent context 处于活跃状态
           └────┬─────┘
                │  POST /user/stop  or  cli stop
                ▼
           ┌──────────┐
           │ stopped  │  ← context 已关闭，SessionRecord.status = 'stopped'
           └──────────┘

 (any state) ──► deleted   ← POST /user/delete, cli delete（级联删除 sessions）
```

### 完整 profile 导入生命周期（额外）

```
 created → import_source_path 已设置 → (首次启动) → 拷贝 LocalStorage/IDB
                                                     → initial_state_applied = True
                                                     → (后续启动跳过拷贝)
```

`initial_state_applied` 标志确保我们只拷贝源 bundle 的 `Local Storage/leveldb/` 和 `IndexedDB/` 一次。重新导入需要使用 `cli reimport <user_id>` 或 `POST /user/{id}/reimport`，它们会重置该标志。

---

## 7. CLI 参考

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
python -m src.cli fingerprint [--seed SEED] [--os windows|macos|linux]
```

### 退出码

- `0` —— 成功
- `1` —— 用户错误（参数缺失、未找到 profile、格式无效）
- 非零 —— typer 因 shell 错误返回

### 环境变量

参见 [环境变量](#16-环境变量)。

---

## 8. REST API 参考

Base URL：`http://127.0.0.1:<ui-port>`（同一端口同时提供 UI 和 API；AdsPower 在 50325 上独立提供）。

所有 response 均使用 AdsPower 格式：`{"code": 0, "msg": "success", "data": {...}}`。

### Health

```http
GET /health
→ {"status": "ok", "service": "antidetect-local", "version": "0.1.0"}
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

### `/user/list` 返回的 profile 形状

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

## 9. Cookie 导入 / 导出格式

### 支持的导入格式

| 格式 | 检测方式 | 说明 |
|---|---|---|
| Netscape `cookies.txt` | `.txt` 后缀 | curl/wget 格式；使用 tab 或空格 |
| Playwright/CDP JSON | `.json` 后缀 | `{name, value, domain, ...}` dict 的列表 |
| AdsPower `.adb` | `.adb` / `.zip` / `.tar` / `.tgz` / 文件夹 | cookies + LocalStorage + IndexedDB |

### 支持的导出格式

- `json`（默认）—— Playwright/Chrome DevTools 格式
- `netscape` —— 通用 curl 兼容的 `cookies.txt`

### `import_cookies(path)` 中的自动检测

```python
def import_cookies(path):
    p = Path(path)
    if p.is_dir() or p.suffix.lower() in (".adb", ".zip", ".tar", ".tgz"):
        return import_adspower_profile(p)
    if p.suffix.lower() == ".json":
        return import_cookies_json(p.read_text())
    return import_cookies_netscape(p.read_text())
```

### 解析 AdsPower `.adb`

`.adb` 是一个 Chrome user-profile bundle（文件夹、`.zip` 或 `.tar.gz`）。Chromium cookies 表位于 `<profile>/Default/Cookies`（SQLite）。

Parser 流程：

1. 将归档解压到临时目录（如需要）。
2. 遍历查找 `*/Cookies` 文件；优先选择 `Default/Cookies`，回退到 `Profile 1/2/3/Cookies`。
3. 以 RO 模式打开 SQLite DB（`file:...?mode=ro`）；若被锁定则回退到一份私有临时拷贝。
4. 读取 cookies 表。处理 schema 差异（旧版 Chrome 缺少 `samesite` 和 `is_persistent` 列）。
5. 将 Chrome 的 `expires_utc`（Windows FILETIME，自 1601-01-01 起的微秒数）转换为 Unix epoch 秒。

---

## 10. Fingerprint 系统

`Fingerprint` 是一组内部一致的、浏览器可见属性：

- **Identity**：User-Agent、navigator.platform/vendor/oscpu、webdriver flag
- **Screen**：width/height/colorDepth/pixelRatio + window.innerWidth/Height
- **Locale / timezone**：navigator.languages、Intl timezone
- **WebGL**：vendor + renderer 字符串（通过 `WEBGL_debug_renderer_info`）
- **Audio**：用于 AudioContext jitter 的确定性 noise seed
- **Canvas**：用于 `toDataURL`/`toBlob` 像素抖动 的确定性 noise seed
- **WebRTC**：防止 IP 泄漏（`block_webrtc_ip`）
- **Plugins**：逼真的 Chrome plugin 列表（2-5 条）
- **Connection**：type/downlink/rtt（Network Information API）
- **Hardware**：hardwareConcurrency、deviceMemory

### 生成

```python
from src.core.fingerprint import generate_fingerprint

fp = generate_fingerprint()                                  # 随机
fp = generate_fingerprint(seed="my-profile-1")               # 确定性
fp = generate_fingerprint(os_family="macos")                 # macOS UA + screen
```

一致性规则：

- OS family ↔ UA ↔ platform ↔ vendor ↔ screen
- Locale ↔ timezone 池（例如 `en-GB` → `Europe/London`）
- WebGL vendor ↔ renderer（NVIDIA vendor 永远不会与 Apple GPU 配对）
- UA 版本使用较新的 Chrome（118-132）

### 注入

两层机制：

1. **Launch args**（`to_playwright_launch_options`）—— 处理 proxy、locale、UA、timezone、窗口大小、viewport、device scale factor。在 Chromium 启动时设置。

2. **JS init script**（`build_init_script`）—— 在每个新文档上 patch `Navigator.prototype`、`HTMLCanvasElement.prototype`、`AudioContext.prototype`、`RTCPeerConnection.prototype` 等。Canvas/audio noise 使用 Mulberry32 算法，由 fingerprint 的 `audio_noise_seed` 和 `canvas_noise_seed` 播种，保证可复现。

### 局限性

- WebGL 在 Chromium 上对未掩码字段是只读的 —— 我们 patch `getParameter` 和 `getExtension`，但如果页面以其他方式使用 `WEBGL_debug_renderer_info`，patch 可以被绕过。
- Canvas noise 幅度较轻（每通道 ±2）—— 强 noise 会破坏某些站点的视觉渲染。如有需要可按 profile 增加 noise。
- 未枚举字体，fingerprint 中没有字体列表。如有需要可通过对 `document.fonts` 的 patch 添加。

---

## 11. 完整 profile（.adb）导入流程

完整 profile 导入的流程如下：

```
1. POST /user/import  (or  cli import-cookies --full PATH)
   ↓
2. profile created (user_id assigned)
   ↓
3. .adb bundle extracted to  data/profiles/imports/<user_id>/
   ↓
4. Cookies parsed from <user_id>/Default/Cookies, written to profile.cookies
   ↓
5. profile.import_source_path = "<user_id>"   ← 供 launcher 使用
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

### 为什么选择「拷贝」而不是「解析」？

Chrome ≥ 61 将 `localStorage` 存储在 Snappy 压缩的 LevelDB 中。IndexedDB 使用 V8 structured-clone 值。重新实现解码器意味着：

- 与版本耦合（Chrome 的编码在各版本间发生变化）。
- 对 Windows 不友好（`plyvel` 需要原生 LevelDB + Snappy 构建）。
- 脆弱（一个字节错位，整个 profile 就无法加载）。

原样拷贝这些目录是一种「笨拙但可靠」的方案，对 Playwright 附带的所有 Chromium 版本都有效。

### 重新导入

在 `.adb` 重新导出之后：

```bash
python -m src.cli reimport <user_id>
# or
curl -X POST http://127.0.0.1:8080/user/<user_id>/reimport
```

这会将 `initial_state_applied` 重置为 `False`。下次启动时会擦除现有的 `Local Storage/leveldb/` 和 `IndexedDB/`（因为在 `apply_initial_state_to_user_data` 内部再次应用时设置了 `force=True`），然后从 bundle 重新拷贝。

### Force 标志

`apply_initial_state_to_user_data(..., force=True)` 会覆盖现有目录。Launcher 在首次应用时使用 `force=False`（避免意外覆盖刚刚拷贝的状态），而 reimport 流程会显式翻转该标志。

---

## 12. CDP multiplexer

Playwright 拥有每个 profile 的 Chromium 进程，但外部自动化（Selenium、Puppeteer、自定义脚本）希望每个 profile 拥有一个 CDP endpoint。`CDPProxy`（`src/core/cdp.py`）实现了以下 multiplexer：

- `GET /json/version` —— 返回一个伪 version payload，指向 `ws://127.0.0.1:5555/devtools/browser`
- `GET /json/list?user_id=<id>` —— 列出某个 profile 的页面
- `WS /devtools/page/{user_id}/{target_id}` —— 将 websocket 代理到正确的 Playwright 页面

注意：WS endpoint 是 **模拟** 的 —— 真实的 CDP 流量走 Playwright 的 context，而不是一个真正的 Chrome debug port。对于不需要底层协议特性的「附加到浏览器」式自动化来说这已经够用。

如果需要真正的 CDP，请将自动化指向 `POST /user/start` 返回的 per-profile websocket：

```json
{"ws_endpoint": "ws://127.0.0.1:50321/devtools/browser", "debug_port": 50321}
```

---

## 13. 数据目录布局

```
data/
├── antidetect.db                 ← SQLite (profiles, sessions, tags, groups)
└── profiles/
    ├── <user_id>/                ← 该 profile 的 Playwright user_data_dir
    │   ├── Default/
    │   │   ├── Cookies
    │   │   ├── Local Storage/leveldb/...
    │   │   ├── IndexedDB/...
    │   │   └── (all Chromium user-data files)
    │   └── ...
    └── imports/
        └── <user_id>/            ← 解压后的 .adb bundle（完整 profile 导入）
            ├── Default/...
            └── ...
```

可通过环境变量 `ANTIDETECT_DATA_DIR=/some/path` 覆盖。

---

## 14. 测试

```bash
python -m pytest                    # all tests
python -m pytest tests/test_cookie.py -v
python -m pytest -k adb             # only .adb-related tests
```

**73 个测试**，分布在 6 个文件中：

- `test_storage.py` —— SQLite engine、tables
- `test_profile.py` —— ProfileStore CRUD、完整 profile 字段、session 簿记
- `test_fingerprint.py` —— Fingerprint 生成 + init script 注入
- `test_proxy.py` —— ProxyConfig 校验 + Playwright 格式互转
- `test_cookie.py` —— Cookie 解析（Netscape/JSON/.adb）、LocalStorage/IndexedDB 抽取
- `test_profile_import.py` —— 完整 profile 导入流程（新增，22 个测试）

---

## 15. 已知限制与 roadmap

### 已完成（本次构建）

- [x] 多 profile 隔离的 Chromium context
- [x] Fingerprint 生成 + JS 注入
- [x] HTTP/HTTPS/SOCKS5 proxy
- [x] Cookie 导入（Netscape、JSON、.adb bundle）
- [x] Cookie 导出（Netscape、JSON）
- [x] 完整 .adb profile 导入（cookies + LocalStorage + IndexedDB）
- [x] 重新导入流程（`cli reimport`、`POST /user/{id}/reimport`）
- [x] AdsPower 兼容的 REST API
- [x] CDP multiplexer（模拟）
- [x] 单页 dashboard
- [x] 73/73 pytest 测试通过

### 已知限制

- **仅支持 Chromium。** Firefox/Camoufox 未实现。`src/core/browser.py` 只启动 Chromium。
- **不支持浏览器扩展。** 没有机制将 `.crx` 或未打包的扩展加载到 profile 中。
- **模拟的 CDP multiplexer。** `/json/list` + `/devtools/page/...` 端点并没有暴露真正的 Chrome debug port 供外部自动化使用 —— 请改用 `POST /user/start` 返回的 per-profile websocket。
- **没有 proxy 轮换 / proxy 健康检查。** Proxy 在每个 profile 上是静态的，没有自动 failover。
- **没有多用户鉴权。** REST API 没有鉴权 —— 本地运行于 `127.0.0.1`，单进程。
- **没有 proxy provider 集成。** 你提供 proxy；我们不从 BrightData/Decodo 等拉取。
- **Headless 可用但不是 stealth 级别。** `--headless=true`（新版 headless）可用；`--headless=old` 与 stealth patch 未实现。

### Roadmap

- [ ] **Firefox/Camoufox** —— 实现与 `BrowserLauncher` 并行的 `FirefoxLauncher`，通过 profile 配置选择（`browser_type = "chromium"|"firefox"`）。
- [ ] **浏览器扩展** —— 将未打包的扩展加载到 profile 的 user data dir 中。
- [ ] **每个 profile 的真实 CDP** —— 为每个 profile 分配一个唯一的 `--remote-debugging-port`（目前 `BrowserLauncher` 选取一个空闲端口；需要稳定地暴露它）。
- [ ] **Proxy 轮换** —— 每个 profile 的 pool + 健康检查 + 自动 failover。
- [ ] **Headless stealth** —— `--headless=new` + stealth patch（navigator.webdriver、plugins、languages）。
- [ ] **Dashboard 重写** —— 当前的 `index.html` 仅作为占位；实现完整的 profiles/tags/groups CRUD UI。
- [ ] **Proxy provider 集成** —— BrightData、Decodo、smartproxy。
- [ ] **Cookie 预热** —— 在导出 cookies 前访问页面、模拟浏览。

---

## 16. 环境变量

| 变量 | 默认值 | 用途 |
|---|---|---|
| `ANTIDETECT_DATA_DIR` | `./data` | `antidetect.db` + profile user data dir 的根目录 |
| `ANTIDETECT_DB` | `<data_dir>/antidetect.db` | SQLite 路径覆盖 |
| `ANTIDETECT_BROWSER_CHANNEL` | （未设置，使用打包的 Chromium） | Playwright browser channel：`chrome`、`msedge`、`chromium-beta` |
| `HOST`（仅 CLI） | `127.0.0.1` | `serve` 的绑定地址 |
| `UI_PORT`（仅 CLI） | `8080` | `serve` 的端口 |

---

## 17. License

MIT —— 参见 `LICENSE`。