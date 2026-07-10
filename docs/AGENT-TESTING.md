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

## Заход 2 (текущий)
| Фича | Код | Тесты |
|---|---|---|
| Гео-привязка (tz/locale/geo по IP) | `src/core/geo.py` | `tests/test_geo.py` |
| Ротация прокси + failover | `src/core/proxy_pool.py` | `tests/test_proxy_pool.py` |
| Geolocation + headless-стелс | `src/core/fingerprint.py` | `tests/test_webgpu_fonts.py`, `tests/test_fingerprint.py` |
| **Детект-харнесс** (NEW) | `src/core/detect.py` | `tests/test_detect.py` |
| **Фикс UTF-8 консоли** (NEW) | `src/consoleutil.py`, `src/cli.py` | `tests/test_console.py` |

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
