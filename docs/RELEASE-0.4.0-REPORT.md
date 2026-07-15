# Отчёт о работе: Antique 0.4.0

## Цель

Закрыть HTTP 500 при запуске профилей из AdsPower backup, довести массовые операции до продуктового UI, добавить управляемую рандомизацию отпечатков, обновить автотесты и инструкции.

## Найденные дефекты

### 1. Authenticated SOCKS5 из AdsPower ломал запуск

AdsPower backup содержит `socks5` с `proxy_user`/`proxy_password`. Chromium не умеет RFC 1929 credentials напрямую через Playwright proxy option. Ошибка поднималась до FastAPI как 500.

Исправление: `src/core/socks_bridge.py`. Для такого профиля запускается loopback-only SOCKS5 bridge. Chromium подключается без auth к `127.0.0.1:<random>`, bridge авторизуется на исходном прокси и двунаправленно передаёт TCP. Bridge закрывается вместе с BrowserHandle.

### 2. Частичный fingerprint создавал некорректный профиль

UI при выборе движка отправлял только `browser_engine`. API строил `Fingerprint(**partial)`, из-за чего UA/noise/fonts оставались пустыми или дефолтными. Редактор FP также сбрасывал все поля, которых не было в форме.

Исправление: `_fingerprint_with_patch()` в routes.py. Create накладывает patch на свежий coherent fingerprint, Update накладывает patch на текущий fingerprint.

### 3. Ошибка старта была непрозрачной

`/user/start` не обрабатывал launch exception и отдавал generic 500.

Исправление: endpoint пишет traceback в server log и возвращает HTTP 422 с user_id и причиной. Это не маскирует дефект, но делает диагностику нормальной.

### 4. Массовая смена прокси была API-only

Backend умел bulk import/assign, но в dashboard не было рабочего сценария.

Исправление: selection toolbar → Assign proxies, многострочный ввод, форматы URL/host:port, циклическое распределение.

### 5. Не было управляемой bulk-рандомизации

Исправление: `src/core/fingerprint_ops.py` + `/user/bulk/fingerprint/randomize` + UI wizard. Можно выбрать OS, deterministic seed, одинаковые группы (screen/locale/timezone/hardware/GPU) и сохраняемые группы (engine/extensions/timezone).

### 6. AdsPower geo metadata терялась

`ip_country` присутствует в index, но fingerprint генерировался в случайной стране.

Исправление: backup importer применяет поддерживаемый country к timezone/locale/geolocation при create/overwrite.

### 7. One-click launcher ставил только Chromium

UI предлагал Firefox/WebKit/Camoufox, но start.bat не готовил их.

Исправление: launcher ставит Chromium/Firefox/WebKit и best-effort Camoufox, использует marker для повторных запусков.

## UI

Палитра переведена на OKLCH, цветовая стратегия сменена с шаблонного синего SaaS на тёплый vermilion accent и tinted neutrals. Убраны gradient-logo и side-stripe toast. Сводка стала плоской information rail вместо набора одинаковых metric cards. Светлая/тёмная тема, mobile table overflow, Live View, import, filters и существующие операции сохранены.

## Автотесты

Новый `tests/test_import_launch_and_randomize.py` проверяет:

- полноценный fingerprint из partial create;
- merge semantics partial update;
- shared/preserved группы smart randomization;
- REST bulk randomization;
- SOCKS5 bridge handshake/auth/connect/data relay через fake upstream.

Полный прогон остаётся обязанностью локального агента, так как MCP filesystem не исполняет процессы на пользовательской машине.

## Изменённые файлы

- `src/core/socks_bridge.py` (new)
- `src/core/fingerprint_ops.py` (new)
- `src/core/browser.py`
- `src/core/backup_import.py`
- `src/api/routes.py`
- `src/api/server.py`
- `src/ui/templates/index.html`
- `start.bat`
- `pyproject.toml`, `src/__init__.py`
- `tests/test_import_launch_and_randomize.py` (new)
- `tests/test_api_endpoints.py`
- `docs/AGENT-TESTING.md`
- `docs/MANUAL-TEST-PLAN.md` (new)
- `README.md`, `QUICKSTART.md`

## Риск и остаточные ограничения

- SOCKS bridge реализует CONNECT, не UDP ASSOCIATE. Для браузерного HTTP(S) это достаточно; UDP-based proxy features не поддерживаются.
- Live real-browser smoke обязателен, unit-тест не заменяет конкретную версию Chromium/AdsPower LevelDB.
- Camoufox остаётся отдельным бинарём и может не скачаться при сетевых ограничениях; launcher продолжает работать на остальных движках.
- WebRTC остаётся block-only, не proxy-IP candidate rewriting.
