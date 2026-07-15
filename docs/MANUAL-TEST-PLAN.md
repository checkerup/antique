# Antique 0.4.0: ручной тест-план владельца

Иди строго по порядку. Не тестируй массовое удаление на рабочих профилях.

## 0. Первый запуск

1. Двойной клик `start.bat`.
2. Первый запуск должен создать `.venv`, установить зависимости, Chromium/Firefox/WebKit и попытаться скачать Camoufox.
3. Открыть `http://127.0.0.1:8080/` и `http://127.0.0.1:8080/docs`.
4. Ожидание: версия 0.4.0, сервер не пишет traceback.

## 1. Базовый профиль

1. New profile → имя `smoke-direct`, Direct, Chromium.
2. Убедиться, что профиль появился с полным fingerprint.
3. Start → окно открылось, статус Live.
4. Открыть несколько сайтов, перезапустить профиль.
5. Ожидание: cookies/localStorage сохранились.
6. Live View → картинка обновляется. Copy CDP → непустой websocket.
7. Stop → Idle.

## 2. Главный регресс: AdsPower + authenticated SOCKS5

1. Import → AdsPower backup folder.
2. Путь: `C:\ai_workflow\adspower_profiles_backup`.
3. Сначала импортировать без Overwrite, затем повторить и проверить skipped.
4. Выбрать любой профиль с SOCKS5 user/password и нажать Start.
5. Ожидание: окно открывается, `/user/start` возвращает 200. Старый HTTP 500 закрыт loopback SOCKS bridge.
6. Proxy check → внешний IP совпадает с прокси.
7. Проверить нужный аккаунт: авторизация, localStorage и IndexedDB.
8. Stop/Start: состояние не потеряно.
9. Overwrite import → профиль обновлён, следующий запуск снова применяет исходный state.

## 3. Массовая смена прокси

1. Создать 3 тестовых профиля, выбрать их чекбоксами.
2. Assign proxies, вставить 2 строки: auth SOCKS5 и HTTP.
3. Ожидание: назначение циклом 1, 2, 1.
4. Check proxies. Ошибка одного прокси не должна ломать остальные строки.
5. Запустить профили и проверить внешний IP в браузере.

## 4. Умная рандомизация отпечатков

1. Выбрать 3 профиля → Randomize fingerprint.
2. OS Windows, Shared: Screen, Preserve: Engine + Extensions.
3. Проверить FP каждого: resolution одинаковое; UA/noise/GPU/hardware различаются; engine остался прежним.
4. Повторить с Shared GPU + Hardware.
5. Повторить с Preserve timezone для гео-привязанных профилей.
6. Указать seed `campaign-01`, сохранить значения, повторить. Ожидание: детерминированный результат.

## 5. Редактор fingerprint

1. FP → изменить только screen width.
2. Сохранить и снова открыть FP/API.
3. Ожидание: UA, WebGL, fonts, noise не сбросились. Это отдельный регресс 0.4.0.
4. Проверить WebRTC block, locale, timezone, hardware, WebGL.

## 6. Движки

Проверить по одному чистому профилю:

- Chromium: Start, extensions, Live View, CDP.
- Firefox: Start, cookies, proxy, restart.
- WebKit: Start, proxy, restart.
- Camoufox: Start, deep-stealth fingerprint, restart.
- Chrome/Edge: только если установлены локальные каналы.

Ожидание: неподдерживаемая функция объясняется в UI/API, а не даёт 500.

## 7. Geo и proxy

1. Создать профиль с country DE.
2. Проверить timezone Europe/Berlin, locale и geolocation.
3. Назначить прокси другой страны и применить geo-match через Swagger.
4. Proxy health показывает status/IP/latency, Direct показывает skip.

## 8. Импорт/экспорт

1. Cookies JSON и Netscape: импорт, экспорт, повторный импорт.
2. Single `.adb`/zip: cookies + local state.
3. Portable `.antq`: export одного профиля, import как копия.
4. Bulk export cookies по нескольким профилям.

## 9. Автоматизация

1. Cookie Robot/warm на example.com.
2. run-flow с goto, wait, scroll, click/type на тестовой странице.
3. Sync flow на 2 профиля. Один намеренно остановить.
4. Ожидание: второй продолжает; отчёт показывает ошибку только первого.

## 10. Операционный UI

1. Поиск по name/ID.
2. Фильтры group/engine/status и их комбинации.
3. Статусы new/warming/active/limited/banned/retired.
4. Светлая/тёмная тема и reload.
5. 390px mobile и 1440px desktop.
6. Empty, loading, server unavailable, invalid form, proxy error.
7. Bulk Start/Stop/Delete только на тестовых профилях.

## 11. Extensions и API

1. `/extension/list` возвращает 200.
2. Установить unpacked extension и привязать к Chromium-профилю.
3. Проверить Swagger endpoints, Bearer token и allowed origins при ngrok.
4. Убедиться, что секреты прокси не попадают в публичный скрин/лог.

## 12. Критерий первого релиза

Релиз годен, если: полный pytest зелёный; импортированный auth-SOCKS5 профиль стартует; direct и proxy профили переживают restart; smart randomization не ломает когерентность; Chromium/Firefox/Camoufox запускаются; UI не имеет блокирующих ошибок на desktop/mobile.
