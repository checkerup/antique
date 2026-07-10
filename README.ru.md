# antique

**Самохостируемый open-source аналог AdsPower — мульти-профильная ферма браузеров с подменой fingerprint, ротацией прокси, импортом .adb-бандлов и совместимым с AdsPower REST API.**

> Собран автономно, чтобы заменить платную подписку AdsPower тем же UX и формой API, без лицензий, полностью локально.

[English](README.md) · [Русский](README.ru.md) · [中文](README.zh.md)

---

## Содержание

1. [Что это такое (TL;DR для агентов)](#1-что-это-такое-tldr-для-агентов)
2. [Быстрый старт](#2-быстрый-старт)
3. [Обзор архитектуры](#3-обзор-архитектуры)
4. [Карта модулей](#4-карта-модулей)
5. [Модель данных и схема хранилища](#5-модель-данных-и-схема-хранилища)
6. [Жизненный цикл профиля](#6-жизненный-цикл-профиля)
7. [Справочник по CLI](#7-справочник-по-cli)
8. [Справочник по REST API](#8-справочник-по-rest-api)
9. [Форматы импорта/экспорта cookies](#9-форматы-импортаэкспорта-cookies)
10. [Система fingerprint](#10-система-fingerprint)
11. [Полный поток импорта профиля (.adb)](#11-полный-поток-импорта-профиля-adb)
12. [CDP-мультиплексор](#12-cdp-мультиплексор)
13. [Структура каталога data](#13-структура-каталога-data)
14. [Тестирование](#14-тестирование)
15. [Известные ограничения и roadmap](#15-известные-ограничения-и-roadmap)
16. [Переменные окружения](#16-переменные-окружения)
17. [Лицензия](#17-лицензия)

---

## 1. Что это такое (TL;DR для агентов)

antique — это Python-сервис, который:

- Создаёт изолированные контексты Chromium (Playwright `launch_persistent_context`) для каждого профиля — у каждого профиля свой user data dir, cookies, localStorage, IndexedDB.
- Генерирует внутренне-согласованные browser fingerprint (UA, navigator, screen, timezone, locale, WebGL vendor/renderer, audio + canvas noise seeds) и инжектит JS init script, чтобы патчить браузер при загрузке.
- Сохраняет профили в SQLite (`data/antique.db`) — proxies, fingerprints, cookies, tags, sessions, import bookkeeping.
- Импортирует `.adb`-бандлы профилей, экспортированные из AdsPower (cookies + LocalStorage + IndexedDB). Импорт использует нативное чтение Chromium вместо хрупкого парсинга LevelDB — мы копируем исходные директории в Playwright `user_data_dir` и позволяем Chromium читать их самостоятельно.
- Предоставляет совместимый с AdsPower REST API на `http://127.0.0.1:<port>/...`, так что существующие скрипты, которые уже работают с AdsPower, могут переключиться, поменяв только базовый URL.
- Включает одностраничный dashboard на `/` (или `/dashboard`) и FastAPI Swagger на `/docs`.
- 73/73 pytest-тестов проходят.

**Чем этот проект НЕ является (пока):**
- Не Firefox/Camoufox — пока это stub (`src/core/browser.py` запускает только Chromium).
- Не headless-ферма браузеров на тысячи профилей — рассчитана на десятки профилей на машину.
- Не мультипользовательский auth-слой — однопроцессный, без auth в REST API, запускается локально.
- Не провайдер прокси — использует прокси, которые вы предоставляете сами.

**Когда использовать:** когда нужна совместимая с AdsPower локальная ферма браузеров с полной изоляцией профилей, контролем fingerprint и импортом .adb-бандлов — без оплаты AdsPower.

**Когда НЕ использовать:** когда нужны >100 одновременных контекстов браузера на одной машине, когда нужен cross-process sharing профилей, или когда нужно управляемое облачное решение.

---

## 2. Быстрый старт

### Требования

- Python 3.10+
- Windows / macOS / Linux
- Playwright (`pip install playwright && playwright install chromium`)

### Установка

```bash
git clone https://github.com/<your-org>/antique
cd antique
python -m venv .venv && source .venv/bin/activate   # или .venv\Scripts\activate на Windows
pip install -e .
playwright install chromium
```

### Запуск сервера

```bash
python -m src.cli serve --ui-port 8080
```

Это даёт вам:

- Dashboard: <http://127.0.0.1:8080/>
- REST API: <http://127.0.0.1:8080/user/list>
- API docs: <http://127.0.0.1:8080/docs>
- Health: <http://127.0.0.1:8080/health>

### Создать профиль и запустить его

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

Или через REST API:

```bash
curl -X POST http://127.0.0.1:8080/user/create \
  -H 'Content-Type: application/json' \
  -d '{"name": "Profile 1", "tags": ["test"]}'

curl -X POST http://127.0.0.1:8080/user/start \
  -H 'Content-Type: application/json' \
  -d '{"user_id": "<user_id>"}'
```

### Импорт AdsPower `.adb`-бандла

```bash
# Cookies only (fast, works with .txt/.json/.adb/.zip/.tar.gz)
python -m src.cli import-cookies path/to/bundle.adb --name "Imported"

# Full profile — copies LocalStorage + IndexedDB into the new profile
python -m src.cli import-cookies path/to/bundle.adb --full --name "Full import"
```

---

## 3. Обзор архитектуры

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

**Три слоя:**

1. **Storage layer** (`src/core/storage.py`, `src/core/profile.py`) — SQLModel/SQLite. Профили, сессии, теги, группы, proxy/fingerprint/cookies как JSON-кодированные колонки.
2. **Browser layer** (`src/core/browser.py`, `src/core/cdp.py`, `src/core/fingerprint.py`, `src/core/cookie.py`) — Playwright persistent contexts, инжекция fingerprint JS, CDP multiplexer, импорт cookie/профиля.
3. **Interface layer** (`src/api/server.py`, `src/api/routes.py`, `src/cli.py`, `src/ui/dashboard.py`) — FastAPI REST + WS, typer CLI, одностраничный HTML-dashboard.

---

## 4. Карта модулей

```
src/
├── __init__.py
├── cli.py                         ← typer CLI (serve, create, list, start, stop, delete,
│                                    import-cookies, reimport, export-cookies, fingerprint)
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
│   ├── browser.py                 ← BrowserLauncher — запускает изолированные контексты Chromium,
│   │                                 сохраняет сессии, применяет импортированное состояние
│   ├── cdp.py                     ← CDPProxy — мультиплексирует один порт отладки для
│   │                                 разных user_id, предоставляет роуты /json/list + WS
│   ├── automation.py              ← Cookie Robot / no-code флоу-раннер (модель Step,
│   │                                 parse_flow, cookie_robot_flow, FlowRunner)
│   ├── portable.py                ← Портативный экспорт/импорт профилей .antq (build_bundle,
│   │                                 export_profile, import_profile)
│   ├── geo.py                     ← Привязка к стране/выходу прокси → таймзона/локаль/языки/гео
│   │                                 (geo_for_country, geo_from_proxy, apply_geo_to_fingerprint)
│   ├── proxy_pool.py              ← Пул прокси + ротация/failover (sticky/round_robin/random)
│   └── detect.py                  ← Селф-тест маскировки / детект-харнесс (build_collector_script, score_report)
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

## 5. Модель данных и схема хранилища

База данных: `data/antique.db` (SQLite, один файл).

### Таблицы

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

### Почему JSON-кодированные колонки?

Proxies, fingerprints и cookies — это гетерогенные dicts/lists со множеством опциональных полей. JSON-кодированные TEXT-колонки позволяют избежать sparse-tables-of-many-columns и упрощают миграции. Цена: нет SQL-уровня для запросов по полям fingerprint, но он нам и не нужен.

### Profile dataclass vs ProfileRecord

- `Profile` (в `src/core/profile.py`) — публичный dataclass. Отделён от storage, чтобы API не утекал SQLModel наружу.
- `ProfileRecord` (в `src/core/storage.py`) — сохраняемая строка. `_record_to_profile()` собирает `Profile` из `ProfileRecord`.

---

## 6. Жизненный цикл профиля

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

### Жизненный цикл импорта полного профиля (дополнительно)

```
  created → import_source_path set → (first launch) → LocalStorage/IDB copied
                                                             → initial_state_applied = True
                                                             → (later launches skip the copy)
```

Флаг `initial_state_applied` гарантирует, что мы копируем `Local Storage/leveldb/` и `IndexedDB/` исходного бандла только один раз. Для повторного импорта нужны `cli reimport <user_id>` или `POST /user/{id}/reimport`, которые сбрасывают флаг.

---

## 7. Справочник по CLI

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
python -m src.cli geo-match USER_ID [--country US|DE|RU|...]     # выравнивание таймзоны/локали/гео под страну или выход прокси
python -m src.cli proxy-rotate USER_ID POOL.txt [--strategy sticky|round_robin|random]
python -m src.cli detect-test USER_ID [--url URL] [--headless]   # селф-тест маскировки с оценкой A-F
python -m src.cli create ... [--geo-country US|DE|RU|...]        # создание профиля с привязкой к стране
python -m src.cli fingerprint [--seed SEED] [--os windows|macos|linux]
```

### Коды возврата

- `0` — успех
- `1` — ошибка пользователя (отсутствуют аргументы, профиль не найден, неверный формат)
- ненулевой от typer для ошибок shell

### Переменные окружения

Смотрите [Переменные окружения](#16-переменные-окружения).

---

## 8. Справочник по REST API

Base URL: `http://127.0.0.1:<ui-port>` (тот же порт обслуживает UI + API; AdsPower использует 50325 отдельно).

Все ответы используют форму AdsPower: `{"code": 0, "msg": "success", "data": {...}}`.

### Health

```http
GET /health
→ {"status": "ok", "service": "antique", "version": "0.1.0"}
```

### Профили

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

### Форма профиля, возвращаемая `/user/list`

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

## 9. Форматы импорта/экспорта cookies

### Поддерживаемые форматы импорта

| Format | Detection | Notes |
|---|---|---|
| Netscape `cookies.txt` | `.txt` extension | curl/wget format; tabs or spaces |
| Playwright/CDP JSON | `.json` extension | list of `{name, value, domain, ...}` dicts |
| AdsPower `.adb` | `.adb` / `.zip` / `.tar` / `.tgz` / folder | cookies + LocalStorage + IndexedDB |

### Поддерживаемые форматы экспорта

- `json` (по умолчанию) — форма Playwright/Chrome DevTools
- `netscape` — универсальный `cookies.txt`, совместимый с curl

### Автоопределение в `import_cookies(path)`

```python
def import_cookies(path):
    p = Path(path)
    if p.is_dir() or p.suffix.lower() in (".adb", ".zip", ".tar", ".tgz"):
        return import_adspower_profile(p)
    if p.suffix.lower() == ".json":
        return import_cookies_json(p.read_text())
    return import_cookies_netscape(p.read_text())
```

### Парсинг AdsPower `.adb`

`.adb` — это бандл Chrome user-profile (папка, `.zip` или `.tar.gz`). Таблица cookies Chromium находится в `<profile>/Default/Cookies` (SQLite).

Парсер:

1. Распаковывает архив во временную директорию (если нужно).
2. Ищет файлы `*/Cookies`; предпочитает `Default/Cookies`, иначе возвращается к `Profile 1/2/3/Cookies`.
3. Открывает SQLite DB в RO-режиме (`file:...?mode=ro`); если залочена — откатывается на приватную временную копию.
4. Читает таблицу cookies. Обрабатывает вариации схемы (в старом Chrome нет колонок `samesite` и `is_persistent`).
5. Конвертирует `expires_utc` Chrome (Windows FILETIME, микросекунды с 1601-01-01) в Unix epoch-секунды.

---

## 10. Система fingerprint

`Fingerprint` — это согласованный набор атрибутов, видимых браузеру:

- **Identity**: User-Agent, navigator.platform/vendor/oscpu, флаг webdriver
- **Screen**: width/height/colorDepth/pixelRatio + window.innerWidth/Height
- **Locale / timezone**: navigator.languages, Intl timezone
- **WebGL**: строки vendor + renderer (через `WEBGL_debug_renderer_info`)
- **WebGPU**: вендор/архитектура/описание адаптера (через `navigator.gpu.requestAdapter().requestAdapterInfo()`), согласовано с WebGL GPU; профили со встроенным (software) рендером отключают `navigator.gpu`
- **Шрифты**: белый список установленных шрифтов под каждую ОС, форсируется через `document.fonts.check`
- **Audio**: детерминированный noise seed для джиттера AudioContext
- **Canvas**: детерминированный noise seed для пиксельного джиттера `toDataURL`/`toBlob`
- **WebRTC**: предотвращение утечки IP (`block_webrtc_ip`)
- **Plugins**: реалистичный список плагинов Chrome (2-5 записей)
- **Connection**: type/downlink/rtt (Network Information API)
- **Hardware**: hardwareConcurrency, deviceMemory

### Генерация

```python
from src.core.fingerprint import generate_fingerprint

fp = generate_fingerprint()                                  # random
fp = generate_fingerprint(seed="my-profile-1")               # deterministic
fp = generate_fingerprint(os_family="macos")                 # macOS UA + screen
```

Правила согласованности:
- Семейство ОС ↔ UA ↔ platform ↔ vendor ↔ screen
- Locale ↔ пул timezone (например, `en-GB` → `Europe/London`)
- WebGL vendor ↔ renderer (NVIDIA vendor никогда не сочетается с Apple GPU)
- Версии UA свежие (Chrome 118-132)

### Инжекция

Два слоя:

1. **Launch args** (`to_playwright_launch_options`) — обрабатывает proxy, locale, UA, timezone, размер окна, viewport, device scale factor. Выполняется при старте Chromium.

2. **JS init script** (`build_init_script`) — патчит `Navigator.prototype`, `HTMLCanvasElement.prototype`, `AudioContext.prototype`, `RTCPeerConnection.prototype` и т.д. в каждом новом документе. Canvas/audio noise использует Mulberry32, посеянный `audio_noise_seed` и `canvas_noise_seed` fingerprint для воспроизводимости.

### Ограничения

- WebGL read-only для unmasked полей в Chromium — мы патчим `getParameter` и `getExtension`, но если страница использует `WEBGL_debug_renderer_info` иначе, патч можно обойти.
- Canvas noise мягкий (±2 на канал) — сильный шум ломает визуальный рендеринг на некоторых сайтах. Увеличивайте noise по профилю, если нужно.
- Шрифты форсируются через `document.fonts.check` (эмуляция перечисления через измерение размеров возвращает белый список). Глубокие проверки шрифтов через размеры canvas, обходящие `document.fonts`, пока полностью не скрыты.
- Подмена WebGPU патчит `requestAdapterInfo()` / `adapter.info`, но не переписывает низкоуровневые лимиты/функции `GPUAdapter`.
- Стелс безголового режима (headless stealth) является базовым: патчатся основные детекты (`window.chrome`, permissions API), но глубокие тайминги рендеринга и специфичные для GPU тесты в headless-режиме могут палиться.
- WebRTC работает в режиме блокировки: реальные IP блокируются, но подмена публичного IP через ICE candidates пока в планах.

---

## 11. Полный поток импорта профиля (.adb)

Поток для импорта полного профиля:

```
1. POST /user/import  (или  cli import-cookies --full PATH)
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
8. Chromium читает директории нативно и обрабатывает их так, будто он
   сам их записал — без парсера LevelDB, без Snappy codec, без version drift.
```

### Почему копировать, а не парсить?

Chrome ≥ 61 хранит `localStorage` в Snappy-сжатом LevelDB. IndexedDB использует V8 structured-clone values. Реализация декодера:

- Привязана к версии (кодирование Chrome меняется между версиями).
- Не дружит с Windows (`plyvel` требует нативных сборок LevelDB + Snappy).
- Хрупкая (один байт не на месте — и весь профиль не загрузится).

Копировать директории verbatim — тупо, надёжно и работает для каждой версии Chromium, которую поставляет Playwright.

### Повторный импорт

После повторного экспорта `.adb`:

```bash
python -m src.cli reimport <user_id>
# или
curl -X POST http://127.0.0.1:8080/user/<user_id>/reimport
```

Это сбрасывает `initial_state_applied = False`. Следующий запуск стирает существующие `Local Storage/leveldb/` и `IndexedDB/` (потому что `force=True` устанавливается внутри `apply_initial_state_to_user_data` при повторном применении) и копирует заново из бандла.

### Флаг force

`apply_initial_state_to_user_data(..., force=True)` перезаписывает существующие директории. Launcher использует `force=False` при первом применении (чтобы случайно не затереть только что скопированное состояние), а поток reimport явно переключает это.

---

## 12. CDP multiplexer

Playwright владеет процессом Chromium на профиль, но внешняя автоматизация (Selenium, Puppeteer, кастомные скрипты) хочет одну CDP-конечную точку на профиль. `CDPProxy` (`src/core/cdp.py`) мультиплексирует:

- `GET /json/version` — возвращает фейковый version payload, указывающий на `ws://127.0.0.1:5555/devtools/browser`
- `GET /json/list?user_id=<id>` — список страниц для профиля
- `WS /devtools/page/{user_id}/{target_id}` — проксирует websocket-соединение к нужной странице Playwright

Замечание: WS-конечная точка **симулированная** — реальный CDP-трафик идёт через контекст Playwright, а не через настоящий Chrome debug port. Это работает для браузерной автоматизации, которой не нужны низкоуровневые фичи протокола.

Для настоящего CDP направьте автоматизацию на per-profile websocket, возвращаемый `POST /user/start`:

```json
{"ws_endpoint": "ws://127.0.0.1:50321/devtools/browser", "debug_port": 50321}
```

---

## 13. Структура каталога data

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

Override через `ANTIQUE_DATA_DIR=/some/path` (env var).

---

## 14. Тестирование

```bash
python -m pytest                    # all tests
python -m pytest tests/test_cookie.py -v
python -m pytest -k adb             # only .adb-related tests
```

**250+ тестов** (на самом деле сейчас 258):

- `test_storage.py` — SQLite engine, tables
- `test_profile.py` — ProfileStore CRUD, full-profile fields, session bookkeeping
- `test_fingerprint.py` — Fingerprint generation + init script injection
- `test_proxy.py` — ProxyConfig validation + Playwright shape conversion
- `test_cookie.py` — Cookie parsing (Netscape/JSON/.adb), LocalStorage/IndexedDB extraction
- `test_profile_import.py` — Full-profile import flow
- `test_webgpu_fonts.py` — подмена WebGPU адаптера + генерация и инжекция белого списка шрифтов
- `test_automation.py` — Cookie Robot / парсер флоу, билдер и раннер на фейковой странице
- `test_portable.py` — портативный экспорт/импорт профилей .antq
- `test_geo.py` — сопоставление страна/прокси → таймзона/локаль/геолокация
- `test_proxy_pool.py` — стратегии ротации прокси-пула + отказоустойчивость
- `test_detect.py` — селф-тест маскировки / детект-харнесс
- `test_console.py` — фикс вывода UTF-8 в Windows-консоль + ASCII-фолбэк
- `test_api_endpoints.py` — HTTP-тесты API (TestClient): регрессии расширений, гео-матчинг, прокси-пул, экспорт, скоринг скрытности
- `test_auth.py` — авторизация по API + Origin-guard (DNS-rebinding, Bearer-токен, разрешенные хосты) (НОВОЕ)

Запустить только новые наборы тестов:

```bash
python -m pytest tests/test_detect.py tests/test_console.py tests/test_api_endpoints.py tests/test_auth.py -v
```

---

## 15. Известные ограничения и roadmap

### Сделано (в этой сборке)

- [x] Multi-profile isolated Chromium contexts
- [x] Fingerprint generation + JS injection
- [x] HTTP/HTTPS/SOCKS5 proxies
- [x] Cookie import (Netscape, JSON, .adb bundle)
- [x] Cookie export (Netscape, JSON)
- [x] Full .adb profile import (cookies + LocalStorage + IndexedDB)
- [x] Re-import flow (`cli reimport`, `POST /user/{id}/reimport`)
- [x] AdsPower-compatible REST API
- [x] CDP multiplexer (simulated)
- [x] Single-page dashboard
- [x] **Менеджер расширений** (установка из распакованных папок, .crx, Chrome Web Store; назначение на профиль)
- [x] **MCP-сервер** (JSON-RPC 2.0 через stdio, 12 инструментов: list/open/close/navigate/screenshot/execute_script/cookies/proxy_check)
- [x] **Поддержка нескольких движков** (Chromium, Firefox, Camoufox/ShardX; на каждый профиль или через env-var)
- [x] **Client Hints** (Sec-CH-UA заголовки через кастомные аргументы браузера, автогенерация из фингерпринта)
- [x] **Расширения на профиль** (`--load-extension` + `--disable-extensions-except` при запуске)
- [x] **Подмена WebGPU фингерпринта** (согласовано с WebGL GPU)
- [x] **Подмена шрифтов** (через белый список под каждую ОС в `document.fonts.check`)
- [x] **Cookie Robot / автоматизация без кода** (`warm`, `run-flow`; модель шагов в JSON)
- [x] **Портативный экспорт/импорт профилей** (бандлы `.antq`)
- [x] **Привязка к ГЕО** (согласование таймзоны/локали/языков/геолокации под страну или выход прокси, `src/core/geo.py`)
- [x] **Подмена геолокации** (`navigator.geolocation` совпадает с гео-профилем)
- [x] **Ротация и отказоустойчивость прокси** (пул со стратегиями sticky/round_robin/random, `src/core/proxy_pool.py`)
- [x] **Headless-стелс** (подмена заглушек `window.chrome`/`chrome.runtime` + согласованность `permissions.query`)
- [x] **Детект-харнесс** (селф-тест маскировки `detect-test` с оценкой отчета 0-100, `src/core/detect.py`)
- [x] **Опциональная авторизация по токену** (переменная `ANTIQUE_API_TOKEN` + защита от Cross-Origin/DNS-rebinding)
- [x] **Фикс кодировки в консоли Windows** (вывод UTF-8 с ASCII-фолбэком без падений `UnicodeEncodeError`)
- [x] 175+ тестов pytest пройдены

### Известные ограничения

- **Для Camoufox требуется отдельная установка.** Запустите `pip install camoufox` для активации движка Camoufox. Без него будет использоваться стандартный Firefox.
- **Симулированный CDP multiplexer.** Эндпоинты `/json/list` + `/devtools/page/...` не открывают настоящий Chrome debug port для внешней автоматизации — используйте per-profile websocket из `POST /user/start`.
- **API-авторизация опциональна.** Задайте `ANTIQUE_API_TOKEN` для требования Bearer-токена; если не задано, доступ открыт локально на `127.0.0.1` (все еще защищено Cross-Origin гардом). Ролей и мультипользователей нет.
- **Нет интеграции с провайдерами прокси.** Прокси поставляются пулом; автоматическая ротация поверх вашего пула реализована.
- **Стелс безголового режима (headless stealth) базовый.** Внедрены патчи на `window.chrome` и permissions, но глубокие тесты таймингов и GPU в headless-режиме могут палиться.
- **WebRTC работает только в режиме блокировки.** IP-адреса блокируются; подмена на публичный IP через ICE-кандидаты в планах.

### Roadmap

- [ ] **Настоящий CDP на профиль** — назначать уникальный `--remote-debugging-port` для каждого профиля (пока симулировано).
- [ ] **Подмена WebRTC IP через ICE-кандидаты** — выдавать публичный IP прокси вместо блокировки.
- [ ] **Интеграция MCP в UI** — запуск и остановка MCP-сервера прямо из дашборда.
- [ ] **Поиск расширений в Web Store** — поиск и установка расширений из UI.
- [ ] **FingerprintJS-интеграция** — использование fingerprintjs/fingerprintjs для проверки обнаружения.

---

## 16. Переменные окружения

| Variable | Default | Purpose |
|---|---|---|
| `ANTIQUE_DATA_DIR` | `./data` | Root for `antique.db` + profile user data dirs |
| `ANTIQUE_DB` | `<data_dir>/antique.db` | SQLite path override |
| `ANTIQUE_BROWSER_CHANNEL` | (unset, uses bundled Chromium) | Playwright browser channel: `chrome`, `msedge`, `chromium-beta` |
| `ANTIQUE_API_TOKEN` | (unset, open) | Если задан, REST API требует заголовок `Authorization: Bearer <token>` |
| `ANTIQUE_ALLOWED_ORIGINS` | (unset) | Разделенный запятыми список разрешенных подстрок Origin для удаленного/туннельного доступа (например, `ngrok-free.app`). Localhost разрешен всегда. Требуется, если дашборд открывается через внешний туннель, иначе Origin-guard выдаст 403. |
| `ANTIDETECT_ENGINE` | `chromium` | Дефолтный браузерный движок: `chromium`, `firefox`, `camoufox` |
| `PYTHONIOENCODING` | (auto UTF-8) | CLI сам форсирует UTF-8 вывод; задавайте `utf-8` только если отключаете фикс |
| `HOST` (CLI only) | `127.0.0.1` | Bind address for `serve` |
| `UI_PORT` (CLI only) | `8080` | Port for `serve` |

---

## 17. Лицензия

MIT — смотрите `LICENSE`.