# Инструкция для локального агента: проверка фич автотестами

> Проект: `C:\ai_workflow\antidetect-local`. Python 3.10+, pytest с `asyncio_mode = "auto"` (уже в `pyproject.toml`).

Файл покрывает **два захода фич**. Всё тестируется оффлайн, живой браузер для юнит-тестов НЕ нужен.

## Заход 1 (ранее)
| Фича | Код | Тесты |
|---|---|---|
| WebGPU-спуфинг | `src/core/fingerprint.py` | `tests/test_webgpu_fonts.py` |
| Спуфинг шрифтов | `src/core/fingerprint.py` | `tests/test_webgpu_fonts.py` |
| Cookie Robot / флоу-раннер | `src/core/automation.py` | `tests/test_automation.py` |
| Портативный `.antq` | `src/core/portable.py` | `tests/test_portable.py` |

## Заход 2
| Фича | Код | Тесты |
|---|---|---|
| Гео-привязка (tz/locale/geo по IP) | `src/core/geo.py` | `tests/test_geo.py` |
| Ротация прокси + failover | `src/core/proxy_pool.py` | `tests/test_proxy_pool.py` |
| Geolocation + headless-стелс | `src/core/fingerprint.py` | `tests/test_webgpu_fonts.py`, `tests/test_fingerprint.py` |
| Детект-харнесс | `src/core/detect.py` | `tests/test_detect.py` |
| Фикс UTF-8 консоли | `src/consoleutil.py`, `src/cli.py` | `tests/test_console.py` |
| API-авторизация + origin-guard | `src/api/server.py` | `tests/test_auth.py` |
| Новые REST-эндпоинты + регресс ext_store | `src/api/routes.py`, `src/api/server.py` | `tests/test_api_endpoints.py` |

## Заход 3 (текущий) — Robinhood Chain
| Фича | Код | Тесты |
|---|---|---|
| **Мониторинг кошельков EVM** (NEW) | `src/core/chain.py` | `tests/test_chain.py` |
| **Поиск ранних покупателей токена** (NEW) | `src/core/chain.py` | `tests/test_chain.py` |
| REST + MCP для chain | `src/api/routes.py`, `src/mcp/server.py` | `tests/test_api_endpoints.py`, `tests/test_chain.py` |

### Что проверяют chain-тесты (всё оффлайн, транспорт замокан)
- Пресеты Robinhood (chain id 4663 / testnet 46630), `get_chain`, `supported_chains`.
- Хелперы: `hex_to_int`, `wei_to_eth`, `normalize_address`, `is_valid_address`, `topic_to_address`.
- `parse_early_buyers`: порядок по (блок, log index), дедуп, исключение zero/токен/exclude, лимит, фильтр non-Transfer.
- `summarize_wallet_activity`: flat RPC и Blockscout-shape, sent/received, first/last block.
- `ChainClient` с фейк-транспортами: block_number, chain_id, баланс, monitor_wallet (выживает при падении explorer), early_buyers (сборка getLogs-фильтра), hex-конверсия блоков.
- MCP: тулы `chain_monitor_wallets` и `chain_early_buyers` отдаются в `tools/list`.

### Команды прогона
```bash
python -m pytest tests/test_chain.py -v
python -m pytest tests/test_chain.py tests/test_api_endpoints.py -v
```

### Живой smoke (требует сети, публичный RPC rate-limited)
```bash
python -m src.cli chain-wallet 0x<addr> --chain robinhood
python -m src.cli chain-early-buyers 0x<token> --chain robinhood --limit 20 --from-block 0 --to-block latest
```

---

## 0. Подготовка

```bash
cd C:\ai_workflow\antidetect-local
python -m venv .venv
.venv\Scripts\activate
pip install -e .
pip install -r requirements.txt
playwright install chromium   # только для живого браузера; юнит-тестам не нужен
```

> Важное по фиксу консоли: `PYTHONIOENCODING=utf-8` больше НЕ требуется — CLI сам форсит UTF-8 на старте
> (`src/cli.py: force_utf8_stdio()`). Если терминал всё равно не умеет UTF-8, `consoleutil.to_safe()`
> подменяет ✓/→ на ASCII (`[OK]`, `->`), так что `UnicodeEncodeError` больше не возникает.

---

## 1. Полный прогон

```bash
python -m pytest
```

Ожидаемо: все тесты зелёные (было 175 → стало больше за счёт `test_detect.py` и `test_console.py`).

---

## 2. Только новые сьюты этого захода

```bash
python -m pytest tests/test_detect.py tests/test_console.py -v
```

Смежные (если нужно перепроверить гео/ротацию):

```bash
python -m pytest tests/test_geo.py tests/test_proxy_pool.py -v
```

---

## 3. Что проверяют новые тесты

**Детект-харнесс (`test_detect.py`)**
- Чистый профиль → 100/100, оценка A, без утечек.
- `webdriver=true` → критическая ошибка (минус 40, оценка C, `ok()=False`).
- Отсутствие `window.chrome`, permission mismatch, рассогласование platform/UA → флаги.
- Cross-check с ожидаемым fingerprint (WebGL vendor / timezone не совпали → fail).
- `build_collector_script()` — валидный JS (webdriver, WebGL, timezone).

**Фикс консоли (`test_console.py`)**
- `supports_unicode`: utf-8 → True, cp1251/None/неизвестный codec → False.
- `to_safe`: на utf-8 без изменений; на cp1251 меняет ✓→[OK], →→->, результат кодируется без краша.
- `ensure_utf8`: переконфигурирует поток; не падает на потоках без `reconfigure`.
- `cli.force_utf8_stdio` импортируется и идемпотентен.

---

## 4. Ручной smoke

```bash
# Фикс консоли: в PowerShell с русской локалью без PYTHONIOENCODING — не должно быть UnicodeEncodeError
python -m src.cli create "Smoke" --fingerprint-seed s1

# Гео-привязка
python -m src.cli create "DE profile" --geo-country DE
python -m src.cli geo-match <USER_ID> --country US

# Ротация прокси (POOL.txt — по прокси на строку)
python -m src.cli proxy-rotate <USER_ID> pool.txt --strategy round_robin

# Живой детект-тест (требует Chromium)
python -m src.cli detect-test <USER_ID> --url https://<local-creepjs>
```

---

## 5. Критерий готовности

`python -m pytest` → всё зелёное. Если красное в `test_detect.py` — смотри веса severity в `src/core/detect.py`
(`_SEVERITY_WEIGHT`), они задают ожидаемые очки в тестах (крит=40, high=20, medium=10, low=5).

---

## Заход 4 (текущий) — движки / UI / AdsPower / удалён ончейн

### Что изменилось
| Фича | Код | Тесты |
|---|---|---|
| **Реестр движков** (chromium/chrome/edge/firefox/camoufox/webkit) | `src/core/engines.py`, `src/core/browser.py` | `tests/test_engines.py` |
| **`/engine/list` + `create --engine`** | `src/api/routes.py`, `src/cli.py` | `tests/test_api_endpoints.py`, `tests/test_engines.py` |
| **Новый UI (тёмная/светлая тема, engine picker, AdsPower import)** | `src/ui/templates/index.html` | ручная проверка (статика) |
| **AdsPower backup import** (бэкенд был, добавлен API-тест) | `src/core/backup_import.py`, `/user/import/backup` | `tests/test_backup_import.py`, `tests/test_api_endpoints.py` |
| **Удалён ончейн** | `src/core/chain.py` (обнулён) | `tests/test_chain.py` (пуст) |

### Что проверяют тесты движков (`test_engines.py`, всё оффлайн)
- Реестр содержит все 6 движков; base/channel/stealth корректны.
- Капабилити: Chromium-движки → extensions + реальный CDP; firefox/camoufox/webkit → нет.
- Резолв: алиасы (google-chrome→chrome, safari→webkit), неизвестный→chromium.
- Приоритет: profile.browser_engine > ANTIDETECT_ENGINE > default.
- `browser_engine` сохраняется на профиле через fingerprint (round-trip).

### Команды
```bash
python -m pytest tests/test_engines.py tests/test_api_endpoints.py -v
python -m pytest            # полный прогон
```

### Ручной smoke
```bash
python -m src.cli engines                          # таблица движков
python -m src.cli create "cam" --engine camoufox   # создать на camoufox
python -m src.cli import-backup "C:\ai_workflow\adspower_profiles_backup"
# UI: открой http://127.0.0.1:8080/ , переключи тему (☀️/🌙), Import → AdsPower backup folder
```

> Ончейн удалён: `chain.py`/`test_chain.py` обнулены, chain-эндпоинты/CLI/MCP-тулы вырезаны.
> Если где-то остался `import ... chain` — это баг, сообщи.

### Камуфокс (опционально, для живого запуска)
```bash
pip install camoufox && python -m camoufox fetch
```
Без установки camoufox профиль мягко откатывается на бандловый Firefox (лог предупреждает, не падает).
