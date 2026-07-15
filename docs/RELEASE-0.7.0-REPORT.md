# Antique 0.7.0: продолжение parity-релиза

## Что добавлено

- **Настоящий audit history**: API create/update/start/stop/delete/backup-import/bulk-status теперь пишут события в `activity_events`. Просмотр: `/activity`, CLI `activity`, UI Tools.
- **Backup scheduler registry**: локальные расписания с интервалом и encrypted AES-GCM snapshot run. API `/backup/schedules`, `/backup/schedules/run`, CLI `backup-schedule`, `backup-schedules`. Запуск можно вызывать Windows Task Scheduler или cron, без скрытого daemon.
- **HTTP JSON proxy provider**: дополнительно к file/json источникам, URL с JSON-ответом `{"proxies": [...]}` или `{"data": [...]}`. Секреты не сохраняются в profile rows и не печатаются.
- **Resource metrics**: `/resource/status` показывает running profiles, pid, debug ports, websocket, RSS/CPU при доступном psutil или безопасный fallback.
- **Parity docs/tests**: обновлены матрица, agent guide, новый отчёт и `test_operations_release.py`.

## Проверка

```powershell
cd C:\ai_workflow\antidetect-local
.\.venv\Scripts\Activate.ps1
python -m pip install -e .
python -m pytest -q
python -m pytest tests\test_operations_release.py tests\test_sort_clone_features.py tests\test_import_launch_and_randomize.py tests\test_ui_release_040.py -v
```

Ручной smoke: создать/update профиль и проверить `/activity`; зарегистрировать schedule, list, run с паролем; проверить `last_run_at`; проверить resource status на Windows; провайдер HTTP JSON гонять только через mock endpoint.

## Что осталось честно в backlog

- nested folders и drag/drop, dashboard template editor;
- activity retention/export;
- provider-specific auth adapters;
- extension catalog search/install/update;
- MCP start/stop control;
- low-latency Live View video/input;
- full CDP target proxy;
- WebRTC proxy-IP rewriting;
- team/cloud sync.

Последние четыре требуют отдельной сетевой/браузерной архитектуры, поэтому их нельзя закрывать декоративными endpoints.
