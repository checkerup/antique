# antique — план реализации недостающих фич

> Составлено на основе аудита кода (`src/core/browser.py`, `src/core/cdp.py`, README roadmap).
> Порядок работы для каждой фичи: **реализация → обновление README → авто-тесты → инструкции локальному агенту**.

---

## Реализовано в этом заходе (топ-фичи конкурентов, которых у нас не было)

Разведка конкурентов (Dolphin Anty, AdsPower, GoLogin, Undetectable, Hidemium, Multilogin, JinDaGe):
повторяющиеся фичи, которых у нас не было и которые реально реализуемы на нашем стеке:

- [x] **WebGPU-спуфинг** — `navigator.gpu.requestAdapter().requestAdapterInfo()` (vendor/architecture/description),
  когерентно WebGL GPU. Dolphin/JinDaGe уже спуфят WebGPU, у нас fingerprint обрывался на WebGL.
  → `src/core/fingerprint.py`, тесты `tests/test_webgpu_fonts.py`.
- [x] **Спуфинг шрифтов** — per-OS allow-list через `document.fonts.check`. README сам признавал "fonts are not enumerated";
  у всех конкурентов это база. → `src/core/fingerprint.py`, тесты `tests/test_webgpu_fonts.py`.
- [x] **Cookie Robot / no-code флоу-раннер** — JSON-шаги (goto/wait/scroll/click/type/press/hover/screenshot/eval),
  валидация + асинхронный раннер. Аналог AdsPower RPA / Hidemium no-code.
  → `src/core/automation.py`, CLI `warm` и `run-flow`, тесты `tests/test_automation.py`.
- [x] **Портативный экспорт/импорт `.antq`** — перенос профиля между машинами (fingerprint+proxy+cookies+tags).
  Есть у AdsPower/GoLogin/Undetectable. → `src/core/portable.py`, CLI `export-profile`/`import-profile`,
  тесты `tests/test_portable.py`.

Инструкция по прогону тестов: `docs/AGENT-TESTING.md`.

---

## Статус бэклога (обновлено)

- [x] **API-авторизация (P0.2)** — токен `ANTIQUE_API_TOKEN` + origin-guard (`src/api/server.py`).
- [x] **Гео-привязка** — `src/core/geo.py` + CLI `geo-match`, `create --geo-country`.
- [x] **Geolocation-спуфинг** — init-script в `fingerprint.py`.
- [x] **Ротация прокси + failover (P1.3)** — `src/core/proxy_pool.py` + CLI `proxy-rotate`.
- [x] **Headless-стелс (P1.4)** — chrome.runtime + permissions в init-script.
- [x] **Детект-харнесс (P1.6)** — `src/core/detect.py` + CLI `detect-test`, тесты `test_detect.py`.
- [x] **Фикс UTF-8 консоли Windows** — `force_utf8_stdio` + `src/consoleutil.py`, тесты `test_console.py`.

### Остаётся в бэклоге

- [ ] **Реальный CDP на профиль (P0.1)** — `--remote-debugging-port`, пока симуляция.
- [ ] **WebRTC proxy-IP rewriting** — отдавать public IP прокси в ICE, а не только блокировать.
- [ ] **Интеграции провайдеров прокси**, **MCP UI**, **Web Store расширений**.

---

## Первоначальный аудит (история)

---

## P0 — Критично (ломает заявленный сценарий)

### 1. Настоящий CDP на профиль (`--remote-debugging-port`)

**Проблема.** `BrowserLauncher._launch()` возвращает `ws_endpoint = ws://127.0.0.1:{port}/devtools/browser`,
но Chromium запускается через `launch_persistent_context` **без** `--remote-debugging-port`.
Порт берётся из `_find_free_port()` и ни к чему не привязан → внешняя автоматизация
(Selenium/Puppeteer/пользовательские скрипты, ради которых и делался AdsPower-клон) подключиться не может.
CDP-мультиплексор в `cdp.py` — «симуляция», реальный протокол через него не ходит.

**Что сделать.**
- Пробрасывать `--remote-debugging-port={port}` и `--remote-debugging-address=127.0.0.1` в `launch_opts["args"]`.
- После старта читать реальный `webSocketDebuggerUrl` из `http://127.0.0.1:{port}/json/version`
  (Chromium поднимает его сам) и класть в `BrowserHandle.ws_endpoint` + `SessionRecord`.
- `CDPProxy` переключить с симуляции на реальный реверс-прокси к этому порту
  (либо просто отдавать наружу настоящий ws и `/json/list`).
- Обработать гонку: порт занят к моменту старта Chromium → retry с новым портом.

**Тесты.** Старт профиля → `GET /json/version` на debug_port отдаёт валидный CDP,
подключение `websockets`-клиентом проходит хендшейк, `Target.getTargets` возвращает страницы.

---

### 2. Опциональная авторизация REST API

**Проблема.** API без авторизации на `127.0.0.1`. Любая открытая в браузере веб-страница
может слать POST на `http://127.0.0.1:8080/user/start` (DNS-rebinding / CSRF на localhost) —
запускать/удалять профили пользователя.

**Что сделать.**
- Env `ANTIQUE_API_TOKEN`; если задан — middleware требует `Authorization: Bearer <token>`.
- Проверка `Origin`/`Host` заголовков (блок not-localhost Origin) для защиты от DNS-rebinding.
- Dashboard подхватывает токен из localStorage.

**Тесты.** Запрос без токена → 401; с токеном → 200; чужой Origin → 403.

---

## P1 — Высокий приоритет (заявлено в roadmap, реальные векторы детекта)

### 3. Ротация прокси + авто-failover

Health-check уже есть (`POST /proxy/check`), ротации нет.
- Пул прокси на профиль/группу, при падении health-check → автопереключение на следующий живой.
- Стратегии: sticky (по умолчанию), round-robin, on-failure.
- Env/поле профиля для стратегии; лог смен.

**Тесты.** Мок дохлого прокси → профиль переезжает на живой; sticky не меняет без нужды.

### 4. Headless stealth

`--headless=new` работает, но детектится. Добавить патчи под headless:
- `navigator.webdriver`, отсутствие `chrome.runtime`, WebGL/размеры окна в headless.
- Прогнать через self-test харнесс (см. п.6).

**Тесты.** Init-script в headless-режиме не палит `webdriver`, `chrome` объект присутствует.

### 5. Fingerprint: список шрифтов

README сам отмечает: шрифты не эмулируются — это живой вектор детекта.
- Добавить в `Fingerprint` детерминированный `fonts[]` (по OS-семейству).
- Патч `document.fonts` / measure-based enumeration в init-script.

**Тесты.** Два разных seed → разные наборы; одинаковый seed → одинаковые (детерминизм).

### 6. Харнесс детект-тестирования (CreepJS / FingerprintJS)

Автоматическая проверка стелса: поднять профиль, зайти на локально захостенный
FingerprintJS/CreepJS, собрать отчёт (webdriver, canvas/webgl consistency, UA-vs-CH match).
- CLI: `python -m src.cli detect-test <user_id>`.
- Используется как регрессионный тест стелса в CI.

**Тесты.** Прогон возвращает структурированный отчёт; ключевые флаги (webdriver=false) зелёные.

### 7. Cookie warming

Перед экспортом «прогреть» профиль: обойти список URL, проэмулировать скролл/паузы,
дать сайтам поставить куки.
- CLI: `warm <user_id> --urls file.txt`; поле профиля с warm-списком.

**Тесты.** После warm у профиля прибавились куки/localStorage от целевых доменов (на моке).

---

## P2 — Ценно, но не срочно

### 8. Интеграции провайдеров прокси
BrightData / Decodo / smartproxy: подтягивать пул через их API вместо ручного ввода.

### 9. UI-интеграция MCP-сервера
Старт/стоп MCP из дашборда + индикатор статуса.

### 10. Web Store браузер расширений
Поиск и установка расширений прямо из UI (сейчас только по URL/пути).

---

## Порядок выполнения

1. **P0.1 (реальный CDP)** — фундамент, без него продукт не выполняет главное обещание.
2. **P0.2 (auth)** — дёшево, закрывает реальную дыру безопасности.
3. **P1.6 (детект-харнесс)** — раньше стелс-фич, чтобы мерить прогресс объективно.
4. **P1.4 + P1.5 (headless stealth + шрифты)** — валидируются харнессом из п.3.
5. **P1.3 (ротация прокси)** и **P1.7 (warming)**.
6. **P2** по остаточному принципу.
