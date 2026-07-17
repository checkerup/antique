# Antique 0.9.0: полный owner test checklist

Тестировать на копии рабочей папки/БД. Для рабочих AdsPower-профилей сначала сделать encrypted snapshot.

## A. Установка и сервер

- [ ] Двойной клик `start.bat` на чистой машине.
- [ ] `.venv` создаётся, зависимости устанавливаются, Chromium/Firefox/WebKit доступны.
- [ ] Camoufox устанавливается отдельно или корректно показывается fallback.
- [ ] Dashboard `/`, Swagger `/docs`, `/health`, `/info` возвращают 0.9.0.
- [ ] Повторный запуск не переустанавливает браузеры.
- [ ] Запуск с `ANTIQUE_API_TOKEN` требует Bearer token.
- [ ] ngrok origin работает только через `ANTIQUE_ALLOWED_ORIGINS`.

## B. UI foundation

- [ ] Тёмная и светлая тема, reload сохраняет выбор.
- [ ] 1440px и 390px: нет блокирующего переполнения, таблица скроллится.
- [ ] Empty state, loading, server unavailable, invalid form, toast error/success.
- [ ] Keyboard focus на inputs, buttons, selects.
- [ ] Search по имени и ID.
- [ ] Фильтры group, engine, account status.
- [ ] Sort: name, ID, live, engine, status, group, tags, proxy, cookies, launches, created, updated, last launched.
- [ ] Повторный выбор поля меняет asc/desc, reload и авто-refresh не сбрасывают сортировку.

## C. Profiles

- [ ] Создать direct профиль.
- [ ] Создать HTTP/HTTPS/SOCKS5 профиль с auth.
- [ ] Создать профиль с engine, geo, group, tags.
- [ ] FP editor: изменить одно поле, остальные не сбрасываются.
- [ ] Manage: name, group, tags, remark, status, geo, extensions.
- [ ] Clone: новый ID, данные копируются, статус новый.
- [ ] Start/Stop/Restart.
- [ ] Bulk Start/Stop/Delete только на тестовой группе.
- [ ] Account statuses: new, warming, active, limited, banned, retired.

## D. AdsPower import

- [ ] Tools → Preview backup: показывает counts, proxy, cookies, geo, state; ничего не создаёт.
- [ ] Import `C:\ai_workflow\adspower_profiles_backup`.
- [ ] Повторный импорт без overwrite даёт skipped.
- [ ] Overwrite обновляет профиль.
- [ ] AdsPower `user_id`, name, group, tags, remark, proxy сохраняются.
- [ ] JSON cookies используются первыми, битый JSON падает обратно на Cookies DB.
- [ ] Local Storage, IndexedDB, WebStorage применяются при первом старте.
- [ ] Профиль с auth-SOCKS5 запускается без старого HTTP 500.
- [ ] Proxy check показывает ожидаемый exit IP.
- [ ] Stop/Start не затирает накопленное состояние.
- [ ] Single `.adb`, `.zip`, Netscape и JSON cookie import.
- [ ] `.antq` export/import.

## E. Fingerprint and engines

- [ ] Chromium: fingerprint, extensions, real CDP, Live View.
- [ ] Chrome/Edge: только если installed channel exists.
- [ ] Firefox: launch, proxy, cookies, restart.
- [ ] Camoufox: deep mode or explicit fallback message.
- [ ] WebKit: launch and restart.
- [ ] WebGL/WebGPU coherence.
- [ ] Font list and canvas/audio noise.
- [ ] Geo timezone/locale/languages/coordinates coherence.
- [ ] WebRTC block behavior.
- [ ] `detect-test` report and expected score.
- [ ] Smart randomization: unique fields differ, selected shared fields match, engine/extensions preserved, seed deterministic.

## F. Operations / Tools

- [ ] Tools → Recent activity shows create/update/start/stop/delete/import/bulk status.
- [ ] Activity filter by user/action returns only matching events.
- [ ] Export activity writes JSON without exposing unrelated records.
- [ ] Extension catalog lists installed extensions and installs a test unpacked extension.
- [ ] MCP status shows stdio/available honestly.
- [ ] Tools → Resource status shows RSS/CPU and running profile ports.
- [ ] Tools → Backup schedules lists registered schedules.
- [ ] Mass create from template creates exact N profiles.
- [ ] Wrong template / count >1000 is rejected.
- [ ] Encrypted snapshot export creates file.
- [ ] Correct password restores; wrong password does not change DB.
- [ ] Backup schedule create/list/run updates `last_run_at`.
- [ ] Provider file and JSON source return proxy count.
- [ ] HTTP JSON provider works against a local mock endpoint.
- [ ] Proxy credentials do not appear in logs or profile metadata.
- [ ] Folders: create root, create child with parent_id, list empty folders, update, delete test folder.
- [ ] Default folder cannot be accidentally lost from UI flow.
- [ ] Swagger `/mcp/status` returns available.

## G. Automation and integration

- [ ] Cookie Robot warm on a safe test site.
- [ ] JSON flow: goto, wait, scroll, click, type, screenshot.
- [ ] Sync flow across two profiles.
- [ ] One failed profile does not cancel other profiles.
- [ ] Live View screenshot refreshes.
- [ ] Real Chromium CDP websocket attaches from Puppeteer/Selenium.
- [ ] Extensions install, list, assign, launch.
- [ ] MCP stdio tools list and basic browser operation.
- [ ] Docker compose starts and data volume persists across restart.

## H. Automated gate

```powershell
cd C:\ai_workflow\antidetect-local
.\.venv\Scripts\Activate.ps1
python -m pytest -q
python -m pytest tests\test_operations_release.py tests\test_sort_clone_features.py tests\test_import_launch_and_randomize.py tests\test_ui_release_040.py -v
```

Release gate: all tests green, auth-SOCKS5 profile launches, no data loss after restart, all owner UI workflows visible, and no unhandled 500 on expected user errors.
