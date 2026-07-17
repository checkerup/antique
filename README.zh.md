# antique

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

antique 是一个 Python 服务，功能如下：

- 为每个 profile 启动独立的 Chromium context（Playwright `launch_persistent_context`）—— 每个 profile 拥有自己的 user data dir、cookies、localStorage、IndexedDB。
- 生成内部一致的 browser fingerprint（UA、navigator、screen、timezone、locale、WebGL vendor/renderer、audio + canvas noise seed），并注入 JS init script 在启动时对浏览器进行 patch。
- 在 SQLite（`data/antique.db`）中持久化 profile —— 包括 proxy、fingerprint、cookies、tags、sessions 以及导入相关的元数据。
- 导入从 AdsPower 导出的 `.adb` profile bundle（cookies + LocalStorage + IndexedDB）。导入采用原生 Chromium 读取，而非脆弱的 LevelDB 解析 —— 我们把源目录拷贝到 Playwright 的 `user_data_dir`，让 Chromium 自己读取。
- 在 `http://127.0.0.1:<port>/...` 上暴露 AdsPower 兼容的 REST API，因此已经对接 AdsPower 的现有脚本只需修改 base URL 即可切换。
- 在 `/`（或 `/dashboard`）提供一个单页 dashboard，在 `/docs` 提供 FastAPI Swagger。
- 340+ 个 pytest 测试通过。
- 可更换的浏览器引擎：Chromium, Google Chrome, Microsoft Edge, Firefox, Camoufox（引擎级深层防关联）, WebKit。
- 一键式 AdsPower 备份导入（导入整个备份目录或单个 profile），保留 user_id, cookies, proxy, tags。
- 支持亮色/暗色主题、引擎选择器、AdsPower 导入、网页端 Live View、以及账号状态标签的 Dashboard。
- Live View（运行中 profile 的实时截图）、真实的 profile 级别 CDP 端口、并发多 profile 自动化同步（在多 profile 间同步运行同一流程），以及 Docker 一键运行。
- 批量操作：支持批量启动/停止/删除/导出 profile，批量导入和分配代理。
- 分组管理与过滤。
- 代理健康度检查（检测出口 IP 与网络延迟）。
- 直接在 Dashboard 界面编辑指纹信息。

**它还不是（尚未实现的功能）：**

- 不是为数千个 profile 设计的无头浏览器农场 —— 设计目标是单机几十个 profile。
- 不是多用户鉴权层 —— 单进程，REST API 默认无鉴权，本地运行。
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
git clone https://github.com/<your-org>/antique
cd antique
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
│   ├── browser.py                 ← BrowserLauncher —— 启动 persistent Chromium context，记录 session，应用导入的初始状态
│   ├── cdp.py                     ← CDPProxy —— 在多个 user_id 间复用单个 debug port，暴露 /json/list + WS 路由
│   ├── automation.py              ← Cookie Robot / 无代码自动化流程执行器（Step 模型，parse_flow，cookie_robot_flow，FlowRunner）
│   ├── portable.py                ← 便携式 .antq 配置文件导入/导出（build_bundle，export_profile，import_profile）
│   ├── geo.py                     ← 地理位置匹配：国家/出口代理 → 时区/语言/经纬度 (geo_for_country, geo_from_proxy, apply_geo_to_fingerprint)
│   ├── proxy_pool.py              ← 代理池和轮换策略（sticky/round_robin/random）
│   ├── detect.py                  ← 指纹防关联自检机制（build_collector_script, score_report）
│   ├── engines.py                 ← 浏览器引擎注册表 (EngineSpec, resolve_engine, list_engines)
│   ├── sync.py                    ← 多 profile 同步自动化处理器 (run_sync_flow, FlowTask)
│   ├── fingerprint_ops.py         ← 智能批量指纹随机化，支持字段组共享/锁定
│   ├── socks_bridge.py            ← 本地 SOCKS5 代理授权桥接器（解决 Chromium 不支持带账号密码的 SOCKS5 问题）
│   ├── operations.py              ← 模板批量创建、AES-GCM 加密快照、备份预览与操作审计
│   ├── providers.py               ← 本地/远程代理源提取器（支持 File/JSON/HTTP-JSON）
│   └── backup_scheduler.py        ← 本地加密备份计划管理器（支持 AES-GCM 与多时段设置）
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

数据库：`data/antique.db`（SQLite，单文件）。

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
           └────┬─────┘

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
python -m src.cli export-profile USER_ID [--out FILE.antq]
python -m src.cli import-profile FILE.antq [--name NAME] [--user-id ID]
python -m src.cli warm USER_ID [--url URL ...] [--urls FILE] [--dwell-min MS] [--dwell-max MS] [--scrolls N] [--headless]
python -m src.cli run-flow USER_ID FLOW.json [--stop-on-error] [--headless]
python -m src.cli engines                                        # 列出支持的浏览器引擎及其防关联等级
python -m src.cli create ... [--engine chromium|chrome|edge|firefox|camoufox|webkit] # 创建指定引擎的 profile
python -m src.cli import-backup PATH [--overwrite] [--limit N]   # 导入 AdsPower 备份目录
python -m src.cli clone USER_ID [--name NAME] [--user-id NEW_ID] # 克隆 profile (复制指纹、代理、Cookie 及标签)
python -m src.cli bulk-status USER_ID [USER_ID ...] STATUS      # 批量修改账号状态
python -m src.cli list ... [--sort name|launches|...] [--order asc|desc] # 支持 13 种字段排序和升降序选择
python -m src.cli fingerprint [--seed SEED] [--os windows|macos|linux]
python -m src.cli preview-backup PATH                                # 预览 AdsPower 备份目录而不实际导入
python -m src.cli template-create TEMPLATE.json [--count N] [--seed S] # 使用 JSON 模板批量创建 profile
python -m src.cli snapshot-export PATH                               # 导出 AES-GCM 加密的 profile 备份快照
python -m src.cli snapshot-import PATH [--overwrite]                 # 从加密快照中恢复 profile 备份
python -m src.cli activity [--user USER_ID] [--limit N]              # 查看操作审计历史日志
python -m src.cli backup-schedule DESTINATION [--interval-minutes MIN] # 注册本地加密备份计划流程
python -m src.cli backup-schedules                                   # 列出所有注册的备份计划
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

### Geo / proxy-pool / portable / detect / chain / sync

```http
GET  /geo/countries
→ {code:0, data:{countries:["US","DE",...]}}

POST /user/{user_id}/geo/match      Body: {country?: "DE"}   # 若为空，则从该 profile 绑定的代理国家自动推导
→ 对齐时区/语言/地理位置；持久化并写入 fingerprint

POST /proxy/pool/next               Body: {proxy_list, strategy?: sticky|round_robin|random, user_id?}
→ {code:0, data:{proxy:{...}, assigned, server}}   # 选择性绑定代理给指定的 user_id

POST /user/{user_id}/export/portable
→ {code:0, data:{bundle:{...}}}   # .antq 打包数据 (fingerprint+proxy+cookies+tags)

POST /user/import/portable          Body: {bundle:{...}, name?, user_id?}
→ {code:0, data:{user_id, name, cookie_count}}

POST /detect/score                  Body: {signals:{...}, expected?:{...}}
→ {code:0, data:{score, grade, ok, checks, failures}}   # 纯指纹检测评分，无需运行浏览器

GET  /engine/list
→ {code:0, data:{list:[{key,label,base,stealth,channel,needs_install,supports_extensions,supports_cdp}]}}

POST /user/import/backup            Body: {source_path, overwrite?, limit?}
→ {code:0, data:{imported_count, updated_count, skipped_count, error_count, ...}}

POST /user/import/backup/preview    Body: {source_path}
→ {code:0, data:{profiles:[...], total_count, groups:[...], tags:[...]}} # 预览 AdsPower 备份

POST /user/template/create          Body: {template, count, seed?}
→ {code:0, data:{created_count, user_ids:[...]}}  # 模板批量创建

POST /user/snapshot/export          Body: {path, password, overwrite?}
→ {code:0, data:{path}}                           # 导出加密快照 (AES-GCM)

POST /user/snapshot/import          Body: {path, password, overwrite?}
→ {code:0, data:{imported_count, updated_count, skipped_count}} # 导入加密快照

GET  /activity?user_id=...&action=...&limit=...  → 获取操作审计日志列表 (支持用户与动作过滤)

POST /activity/export               Body: {path, user_id?, action?}
→ {code:0, data:{path, count}}      # 将操作审计日志导出为 JSON 文件

GET  /resource/status                → 获取系统资源占用状态 (PID、活动进程数)

GET  /mcp/status                     → 获取 MCP 服务端运行状态及支持的工具列表

GET  /proxy/providers/kinds          → 获取支持的本地代理源类型列表 (file, json, http-json)

POST /proxy/providers/test          Body: {name, kind, source, enabled?}
→ {code:0, data:{provider, count, proxies:[...]}} # 测试加载本地代理源数据

POST /backup/schedules              Body: {destination, interval_minutes}
→ {code:0, data:{schedule:{schedule_id, destination, interval_minutes, enabled, next_run_at, last_run_at}}} # 增加备份计划

GET  /backup/schedules              → 获取已注册备份计划列表

POST /backup/schedules/run          Body: {schedule_id, password}
→ {code:0, data:{schedule:{...}}}   # 手动触发指定快照备份任务

POST /group/create                  Body: {group_id, name, sort_order?, parent_id?}
→ {code:0, data:{group_id, name}}                 # 创建分组 (支持 parent_id 实现嵌套分组)

POST /group/update                  Body: {group_id, name, sort_order?, parent_id?}
→ {code:0, data:{group_id, name}}                 # 更新分组

POST /group/delete                  Body: {group_id} (embed=True)
→ {code:0, data:{group_id, deleted:true}}         # 删除分组

GET  /extension/list                → 获取已安装的全局扩展程序列表

POST /extension/install             Body: {source}
→ {code:0, data:{ext_id, name, version}} # 通过本地目录、.crx 文件或 Chrome Web Store ID 安装扩展程序

POST /extension/uninstall           Body: {ext_id} (embed=True)
→ {code:0, data:{ext_id, uninstalled:true}} # 卸载扩展程序

POST /user/{user_id}/extensions     Body: List[str] (扩展程序 ID 列表)
→ {code:0, data:{user_id, extensions:[...]}} # 为 profile 分配扩展程序

GET  /user/{user_id}/extensions     → 获取分配给该 profile 的扩展程序 ID 列表

POST /user/clone                    Body: {user_id, name?, user_id_override?}
→ {code:0, data:{user_id, name, source_user_id}}

POST /user/bulk/status              Body: {user_ids:[...], account_status}
→ {code:0, data:{results:[{user_id, ok, error?}], updated_count}}

POST /user/bulk/fingerprint/randomize
Body: {user_ids:[...], os_family?, shared_fields?:["screen","gpu",...], preserve_fields?:["engine",...], seed?}
→ {code:0, data:{updated_count, user_ids:[...]}}

GET  /status/list                   → 预设账号状态列表
POST /user/{user_id}/status         Body: {account_status}
POST /user/{user_id}/screenshot     → {code:0, data:{base64_png}}   # Live View 截图 (需处于运行状态)
GET  /user/{user_id}/cdp            → {code:0, data:{webSocketDebuggerUrl, debug_port, ...}}  # 真实的 CDP
POST /sync/run                      Body: {user_ids:[...], flow:[...], stop_on_error?, max_concurrency?}
→ {code:0, data:{ok, succeeded, total, results:[{user_id, ok, completed, total, error}]}}
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
- **WebGPU**：adapter vendor/architecture/description（通过 `navigator.gpu.requestAdapter().requestAdapterInfo()`），与 WebGL GPU 一致；使用软件渲染的 profile 会禁用 `navigator.gpu`
- **Fonts**：每个 OS 独立的文件字体白名单，通过 `document.fonts.check` 强制执行
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
- 字体通过 `document.fonts.check` 强制执行（通过尺寸测量的字体枚举将返回白名单）。目前尚未完全覆盖绕过 `document.fonts` 的深层 canvas 尺寸字体探测。
- WebGPU 伪装仅 patch 了 `requestAdapterInfo()` / `adapter.info`，并不重写底层的 `GPUAdapter` 限制/特性。
- 无头模式防关联（headless stealth）属于基础性规避：已 patch `window.chrome` 以及 permissions API，但深层的渲染时序（paint timing）以及特定于 GPU 硬件的无头特征可能会被标记。
- WebRTC 仅支持“禁用/阻断”模式：已对真实 IP 进行拦截阻断，通过重写 ICE 候选者来实现与代理一致的外网 IP 功能目前处于计划阶段。

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
├── antique.db                 ← SQLite (profiles, sessions, tags, groups, backup_scheduler.py)
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

可通过环境变量 `ANTIQUE_DATA_DIR=/some/path` 覆盖。

---

## 14. 测试

```bash
python -m pytest                    # all tests
python -m pytest tests/test_cookie.py -v
python -m pytest -k adb             # only .adb-related tests
```

**300+ 个测试**（目前共 310 个）：

- `test_storage.py` —— SQLite engine、tables
- `test_profile.py` —— ProfileStore CRUD、完整 profile 字段、session 记录
- `test_fingerprint.py` —— Fingerprint 生成 + init script 注入
- `test_proxy.py` —— ProxyConfig 校验 + Playwright 格式互转
- `test_cookie.py` —— Cookie 解析（Netscape/JSON/.adb）、LocalStorage/IndexedDB 抽取
- `test_profile_import.py` —— 完整 profile 导入流程
- `test_webgpu_fonts.py` —— WebGPU adapter 伪装 + font 白名单生成与注入
- `test_automation.py` —— Cookie Robot / flow 语法解析、构建与执行
- `test_portable.py` —— 便携式 `.antq` 导出与导入验证
- `test_geo.py` —— 国家/出口代理与时区/语言/地理位置自动对齐
- `test_proxy_pool.py` —— 代理池轮换策略及健康度容灾测试
- `test_detect.py` —— 指纹防关联自检机制
- `test_console.py` —— Windows 终端 UTF-8 输出重构与 ASCII 回退验证
- `test_api_endpoints.py` —— HTTP 级别 API 测试 (TestClient)：扩展组件回归、地理匹配、代理池、便携式导入导出、检测评分
- `test_auth.py` —— API 鉴权 + 来源保护 (DNS-rebinding、Bearer 令牌、隧道允许列表)
- `test_engines.py` —— 浏览器引擎注册表：规格、能力、别名解析、优先决议、启动器对接
- `test_sync.py` —— 跨 profile 同步自动化流程测试 (并发控制、异常隔离)
- `test_status_liveview.py` —— 账号状态、Live View 截图、CDP 连接检测与截图异常路径测试
- `test_import_launch_and_randomize.py` —— 导入后启动回归、本地带密 SOCKS5 代理桥接、批量指纹智能随机化 (0.4.0 新增)
- `test_ui_release_040.py` —— 对发布版 0.4.0 UI 核心元素的静态与行为集成测试 (0.4.0 新增)
- `test_sort_clone_features.py` —— profile 排序选择、复制克隆及批量账号状态更新测试
- `test_operations_release.py` —— 模板批量创建、AES-GCM 加密快照、操作审计日志（支持过滤与 JSON 导出）、本地/远程代理源测试（包含 HTTP-JSON）、分组 CRUD、本地加密备份计划管理、扩展目录及 MCP 状态监测测试 (0.9.0 新增)

仅运行最新的测试套件：

```bash
python -m pytest tests/test_operations_release.py tests/test_sort_clone_features.py tests/test_import_launch_and_randomize.py tests/test_ui_release_040.py -v
```

---

## 15. 0.6.0 版本功能发布

新增了与 AdsPower 的功能对齐：AdsPower 备份 data 无导入预览 (dry-run)、配置模板与批量创建、AES-GCM 加密快照备份导出/导入、操作历史审计日志、本地文件/JSON代理源轮换提取、自定义分组的 CRUD 增删改查、系统资源占用和 MCP 监控端点，以及网页端 Dashboard 的 Tools 工具箱控制面板。新测试套件位于 `tests/test_operations_release.py`。

## 16. 0.7.0 版本功能发布

新增了扩展的 AdsPower 功能对齐：支持完整的系统操作历史审计（在创建、修改、启动、停止、删除、导入备份及批量更新状态时自动记录详细 audit 日志）、本地加密备份计划管理器（支持 AES-GCM 快照备份及定期任务注册，无需驻留守护进程，可通过 Windows 任务计划程序 or cron 定期调用）、HTTP JSON 远程代理源提取器（支持从动态 API 获取代理池），以及更精细的 CPU 与 RSS 内存性能指标统计统计，在 Windows 下提供安全的回退机制。

## 17. 0.8.0 版本功能发布

新增了嵌套文件夹/嵌套分组（在 `groups` 表中通过 `parent_id` 实现文件夹层级管理功能）、网页端大工具箱面板（Tools Workspace）的完整集成（可直接在 UI 交互界面浏览操作审计、系统物理资源、快照备份计划以及 AdsPower 备份干跑预览），并提供了在 `docs/OWNER-FULL-TEST-CHECKLIST.md` 中的系统全面功能验收测试方案（A 至 H 章节）。

## 18. 0.9.0 版本功能发布

新增了以下功能：支持按 Profile 和操作类型对活动日志（Activity Log）进行过滤；支持通过 API 和 UI 将活动日志导出为 JSON 格式；在 Tools 中新增了扩展程序目录（Extension Catalog）功能，支持查看已安装的扩展程序并能通过解压目录或 Chrome Web Store ID 进行安装；集成了 MCP 服务的状态显示及 stdio 状态；完善了在 `docs/OWNER-FULL-TEST-CHECKLIST.md` 和 `docs/RELEASE-0.9.0-REPORT.md` 中的自动化与操作验收用例。

## 19. 已知限制与 roadmap

### 已完成（本次构建）

- [x] 多 profile 隔离 of Chromium context
- [x] Fingerprint 生成 + JS 注入
- [x] HTTP/HTTPS/SOCKS5 proxy
- [x] Cookie 导入（Netscape、JSON、.adb bundle）
- [x] Cookie 导出（Netscape、JSON）
- [x] 完整 .adb profile 导入（cookies + LocalStorage + IndexedDB）
- [x] 重新导入流程（`cli reimport`、`POST /user/{id}/reimport`）
- [x] AdsPower 兼容的 REST API
- [x] CDP multiplexer（模拟）
- [x] 单页 dashboard
- [x] **扩展管理器**（支持从解压目录、.crx、Chrome Web Store 安装；支持 profile 分配）
- [x] **MCP 服务端**（基于 stdio 的 JSON-RPC 2.0，提供 12 个工具：list/open/close/navigate/screenshot/execute_script/cookies/proxy_check 等）
- [x] **多浏览器引擎支持**（Chromium、Firefox、Camoufox/ShardX；支持按 profile 或环境变量指定）
- [x] **Client Hints**（通过自定义浏览器启动参数伪装 Sec-CH-UA 请求头，基于 fingerprint 自动生成）
- [x] **Profile 级扩展加载**（启动时加载 `--load-extension` 与 `--disable-extensions-except`）
- [x] **WebGPU fingerprint 伪装**（与 WebGL GPU 一致）
- [x] **字体 fingerprint 伪装**（每个 OS 独立的字体白名单）
- [x] **Cookie Robot / 无代码自动化流程**（支持 `warm` 预热、`run-flow` 执行，提供 JSON 语法步骤）
- [x] **便携式 profile 导出/导入**（使用 `.antq` 压缩包迁移 fingerprint + proxy + cookies + tags）
- [x] **地理位置匹配 (Geo matching)**（自动根据国家/出口代理 IP 对齐时区、语言和经纬度，`src/core/geo.py`）
- [x] **地理定位伪装**（`navigator.geolocation` 的坐标与精度和地理配置保持一致）
- [x] **代理轮换与健康容灾**（提供 sticky/round_robin/random 策略的代理池，`src/core/proxy_pool.py`）
- [x] **Headless 隐身 (Headless stealth)**（支持 `window.chrome`/`chrome.runtime` 接口仿真与 `permissions.query` 接口一致性）
- [x] **防关联检测评估**（`detect-test` 工具，提供 0-100 综合评分与 A-F 评级报告，`src/core/detect.py`）
- [x] **可更换浏览器引擎** (Chromium/Chrome/Edge/Firefox/Camoufox/WebKit 注册表, `src/core/engines.py`, `/engine/list`, `create --engine`)
- [x] **Camoufox 深度隐身引擎** (Gecko 级指纹伪装；若未安装，则回退至捆绑 Firefox)
- [x] **一键 AdsPower 备份导入** (支持导入整文件夹或单 profile; CLI `import-backup` + `/user/import/backup` + 网页端)
- [x] **账号状态标识** (`new`/`warming`/`active`/`limited`/`banned`/`retired`) 及过滤机制
- [x] **Live View** (在 Dashboard 直观预览正在运行的 profile 实时截图)
- [x] **真实的 CDP 服务** (为每个 Chromium profile 提供独占的 CDP 调试端口)
- [x] **跨 profile 同步控制** (并发同步执行相同步骤, `src/core/sync.py`)
- [x] **Docker 容器部署支持**
- [x] **多字段排序机制** (Dashboard、REST API 与 CLI 支持 13 种属性排序及升降序)
- [x] **Profile 克隆复制** (支持一键完整复制指纹、代理、Cookie 与标签)
- [x] **批量状态修改** (支持在 Dashboard 界面、API 和 CLI 批量更新账号状态)
- [x] **智能批量随机化指纹** (可锁定部分字段或跨 profile 共享相同的指纹特征字段)
- [x] **带密 SOCKS5 代理桥** (利用 loopback 管道透明代理解决原生 Chromium 对 socks 账号密码的校验缺陷)
- [x] **AdsPower 备份预览 (dry-run)** (支持在网页/API/CLI预览AdsPower备份数据而不实际写入库)
- [x] **模板批量创建** (支持使用 JSON 模板进行 profile 批量创建与指纹随机生成)
- [x] **AES-GCM 加密快照** (支持导出和导入经过密码保护的 profile 压缩备份快照)
- [x] **操作历史审计** (后台自动记录操作日志，支持 API 及 CLI 查询历史记录，支持核心操作的 audit 事件)
- [x] **本地代理源提取** (支持文件/JSON/HTTP-JSON形式的代理源轮换提取)
- [x] **CRUD分组管理** (支持在后台与 API 进行自定义分组的创建、修改和删除)
- [x] **资源状态与 MCP 监控** (支持查询 PID、活动浏览器进程数以及 MCP tools 映射，支持 CPU/RSS 资源消耗详细指标)
- [x] **本地加密备份计划管理器** (API `/backup/schedules`，支持 AES-GCM 备份自动跑任务，无需守护进程)
- [x] 300+ 个 pytest 测试通过

### 已知限制

- **模拟的 CDP multiplexer。** `/json/list` + `/devtools/page/...` 端点并没有暴露真正的 Chrome debug port 供外部自动化使用 —— 请改用 `POST /user/start` 返回的 per-profile websocket。
- **API 鉴权为可选机制。** 设置 `ANTIQUE_API_TOKEN` 环境变量后方要求提供 Bearer 令牌；如未设置，则默认对 `127.0.0.1` 开放（但仍受跨域 Cross-Origin 策略保护）。单进程，暂不支持多用户角色。
- **没有 proxy provider 直连集成。** 代理需要由您以代理池方式提供；我们支持对已有的代理池进行自动轮换与故障切换。
- **Headless 隐深为尽力而为（Best-effort）。** 已伪装 permissions 和 `window.chrome` 指标，但极其底层的渲染时序（paint timing）以及特定的 GPU 硬件指纹目前尚未完全涵盖。
- **WebRTC 目前仅能选择阻断模式。** 阻断真实 IP 泄漏；重写 ICE 候选以暴露与代理一致的外网 IP 功能目前位于 Roadmap 中。
- **Camoufox 需要额外安装。** `pip install camoufox && python -m camoufox fetch`。若未安装，`camoufox` 引擎会自动回退至捆绑的 Firefox（标准防关联而非深度）。
- **Chrome/Edge 引擎需要本地安装了对应的真实浏览器。** 否则建议使用默认的 `chromium`。
- **Firefox/Camoufox/WebKit 引擎不支持 per-profile CDP 以及加载 .crx 扩展。** 这些能力仅限 Chromium。

### Roadmap

- [x] **每个 profile 的真实 CDP** — 为每个 profile 分配一个唯一的 `--remote-debugging-port`。
- [ ] **WebRTC 代理外网 IP 重写** — 在 ICE 候选里暴露代理的公网 IP 而非直接阻断。
- [x] **MCP 服务的 UI 集成** — 支持从 dashboard Tools 面板查看 stdio 运行状态 (0.9.0)。
- [x] **扩展 Web Store 浏览器** — 扩展目录功能（支持 unpacked 目录与 Web Store ID）已在 Tools 中集成 (0.9.0)。
- [ ] **FingerprintJS 验证集成** — 引入 fingerprintjs/fingerprintjs 检测套件以进行防关联效果检验。

---

## 19. 环境变量

| 变量 | 默认值 | 用途 |
|---|---|---|
| `ANTIQUE_DATA_DIR` | `./data` | `antique.db` + profile user data dir 的根目录 |
| `ANTIQUE_DB` | `<data_dir>/antique.db` | SQLite 路径覆盖 |
| `ANTIQUE_BROWSER_CHANNEL` | （未设置，使用打包 of Chromium） | Playwright browser channel：`chrome`、`msedge`、`chromium-beta` |
| `ANTIQUE_API_TOKEN` | （未设置，公开） | 如果设置，所有 REST API 将校验 `Authorization: Bearer <token>` 请求头 |
| `ANTIQUE_ALLOWED_ORIGINS` | （未设置） | 允许进行远程/隧道访问的额外的信任 Origin 字符串子串的逗号分隔列表（如 `ngrok-free.app`）。Localhost 始终受信任。如果通过外部隧道（如 ngrok）打开 dashboard 必须配置此项，否则 Origin-guard 将返回 403 错误。 |
| `ANTIDETECT_ENGINE` | `chromium` | 默认浏览器引擎：`chromium`、`firefox`、`camoufox` |
| `PYTHONIOENCODING` | （自动 UTF-8） | CLI 内部会自动接管编码处理并强制进行 UTF-8 打印输出，除非该功能被停用否则无需设置 |
| `HOST`（仅 CLI） | `127.0.0.1` | `serve` 的绑定地址 |
| `UI_PORT`（仅 CLI） | `8080` | `serve` 的端口 |

---

## 20. License

MIT —— 参见 `LICENSE`。