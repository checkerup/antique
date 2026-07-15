# Инструкция локальному агенту: проверка antique 0.6.0

Проект: `C:\ai_workflow\antidetect-local`. Не менять рабочую БД для тестов: pytest использует временные каталоги.

## 1. Подготовка

```powershell
cd C:\ai_workflow\antidetect-local
.\.venv\Scripts\Activate.ps1
python -m pip install -e .
python -m pip install -r requirements.txt
```

Для живых smoke-тестов:

```powershell
python -m playwright install chromium firefox webkit
python -m camoufox fetch
```

## 2. Обязательный автоматический прогон

```powershell
python -m pytest -q
python -m pytest tests\test_import_launch_and_randomize.py tests\test_sort_clone_features.py tests\test_operations_release.py tests\test_ui_release_040.py -v
python -m pytest tests\test_backup_import.py tests\test_profile_import.py tests\test_api_endpoints.py -v
```

Критерий: все тесты зелёные, warnings допустимы только от сторонних библиотек. Зафиксировать число passed, время и полный текст любого failure.

## 3. Что обязательно покрывает новый suite

`tests/test_import_launch_and_randomize.py`:

- частичный `fingerprint_config` при создании не оставляет пустые UA/noise/fonts;
- частичное редактирование отпечатка не сбрасывает скрытые поля;
- умная bulk-рандомизация создаёт разные профили, но умеет держать одинаковое разрешение;
- движок профиля сохраняется при рандомизации;
- REST `/user/bulk/fingerprint/randomize` сохраняет результат;
- локальный SOCKS5 bridge принимает Chromium без auth, авторизуется на upstream по RFC 1929 и передаёт трафик.

`tests/test_ui_release_040.py` фиксирует наличие theme, AdsPower import, bulk proxy, smart randomization, flow, Manage, extensions, release docs и установку движков в `start.bat`.

`tests/test_sort_clone_features.py` проверяет сортировку Store/API по полям, clone и bulk status.

`tests/test_operations_release.py` проверяет templates, activity audit, provider adapters, groups, resource/MCP status endpoints.

Смежные обязательные suite:

- `test_backup_import.py`: метаданные, proxy, cookies, исходный AdsPower user_id;
- `test_profile_import.py`: Local Storage, IndexedDB, WebStorage;
- `test_bulk_and_proxy.py`: массовое назначение и разбор форматов proxy;
- `test_fingerprint.py` + `test_webgpu_fonts.py`: когерентность и JS-инъекция;
- `test_engines.py`: выбор движка;
- `test_status_liveview.py` + `test_sync.py`: Live View, CDP, статусы, синхронизация;
- `test_auth.py`: token/origin guard.

## 4. Живой регресс запуска AdsPower-профиля

1. Запустить `start.bat` и открыть `http://127.0.0.1:8080/`.
2. Import → AdsPower backup folder → `C:\ai_workflow\adspower_profiles_backup`.
3. Выбрать профиль с `socks5` и заполненными `proxy_user/proxy_password`.
4. Нажать Start.
5. Ожидание: HTTP 200, окно браузера открыто, строка стала Live. Старый результат HTTP 500 недопустим.
6. Нажать Proxy check. Зафиксировать внешний IP и latency.
7. Проверить авторизацию на целевом сайте и сохранность localStorage/IndexedDB.
8. Stop → повторный Start. Сессия должна сохраниться, а импорт не должен затирать накопленные данные.

Если Start не прошёл, сохранить ответ Network → `/user/start`, traceback сервера и `user_id`. Теперь API должен вернуть 422 с реальной причиной, а не безликий 500.

## 5. Живой smoke массовых операций

1. Выбрать 3 профиля.
2. Assign proxies → вставить 2 прокси разных поддерживаемых форматов. Проверить циклическое назначение 1, 2, 1.
3. Randomize fingerprint → Windows, Shared: Screen, Preserve: Engine + Extensions.
4. Сверить через FP/API: разрешение одинаковое; UA/noise/GPU у профилей различаются; движки не поменялись.
5. Повторить с seed. Два одинаковых прогона на одинаковом наборе должны дать одинаковый результат.
6. Проверить bulk Start/Stop, proxy check, export, delete на тестовых профилях.

## 6. UI smoke

Проверить при ширине 1440px и 390px:

- светлая и тёмная темы, сохранение темы после reload;
- таблица, поиск, фильтры group/engine/status;
- empty/error/loading состояния;
- create/import/fingerprint/bulk-proxy/randomize/live-view модалки;
- клавиатурный focus, отсутствие горизонтального переполнения страницы;
- читаемость OKLCH-палитры и контраст кнопок;
- ошибки показываются toast и не ломают последующие действия.

## 7. Проверка движков

```powershell
python -m src.cli engines
```

Создать и запустить тестовый профиль на `chromium`, `firefox`, `webkit`, `camoufox`. Chrome/Edge проверять только если каналы установлены в ОС. Для каждого зафиксировать: запуск, proxy, cookies, Live View, Stop/Start. CDP ожидается только у Chromium-base.

## 8. Сортировка, clone и bulk status

```powershell
python -m pytest tests\test_sort_clone_features.py -v
python -m src.cli list --sort name --order desc
python -m src.cli clone <USER_ID> --name "Copy"
python -m src.cli bulk-status <USER_ID_1> <USER_ID_2> warming
```

UI: в Sort выбери любое поле и нажми его повторно для asc/desc. Проверить reload, фильтры и сортировку после авто-refresh.

## 9. Parity release smoke

```powershell
python -m src.cli preview-backup C:\ai_workflow\adspower_profiles_backup
python -m src.cli template-create template.json --count 3 --seed demo
python -m src.cli activity
python -m src.cli snapshot-export data\backup.enc --password
python -m src.cli snapshot-import data\backup.enc --password
```

Swagger smoke: `/user/import/backup/preview`, `/user/template/create`, `/user/snapshot/export`, `/user/snapshot/import`, `/activity`, `/resource/status`, `/mcp/status`, `/proxy/providers/kinds`, `/proxy/providers/test`, `/group/create`, `/group/update`, `/group/delete`.

Критерий: preview не создаёт профили; template создаёт ровно N; неверный пароль snapshot не меняет БД; activity содержит события; provider file/json не отправляет секреты в логи.

## 10. Финальный отчёт агента

Отчёт должен содержать:

- версии Python, Playwright и ОС;
- число passed/failed/skipped;
- результат живого запуска импортированного auth-SOCKS5 профиля;
- результат bulk proxy и smart randomization;
- smoke по четырём движкам;
- найденные дефекты с точными шагами, логом и user_id;
- подтверждение, что `README.md`, `QUICKSTART.md` и эта инструкция соответствуют поведению.
