# Antique 0.8.0: UI-complete parity iteration

## Added

- Nested folders: `GroupRecord.parent_id`, parent-aware group create/update/list, empty-folder visibility.
- Tools panel now exposes backup preview, recent activity, resource metrics, backup schedules, mass-create templates, proxy provider testing, folder creation and Swagger.
- Audit hooks cover create/update/start/stop/delete/backup import/bulk status.
- Resource endpoint reports running profile handles, PID/debug ports/ws and RSS/CPU when available, with Windows-safe fallback.
- Backup scheduler registry and encrypted snapshot execution remain available through API and CLI.
- HTTP JSON provider is documented and tested.
- Updated static UI contract tests and created the owner-wide checklist: `docs/OWNER-FULL-TEST-CHECKLIST.md`.
- Version synchronized to 0.8.0.

## Required test commands

```powershell
cd C:\ai_workflow\antidetect-local
.\.venv\Scripts\Activate.ps1
python -m pip install -e .
python -m pytest -q
python -m pytest tests\test_operations_release.py tests\test_sort_clone_features.py tests\test_import_launch_and_randomize.py tests\test_ui_release_040.py -v
```

## Owner test order

Run `docs/OWNER-FULL-TEST-CHECKLIST.md` from A to H. It covers installation, UI states, profile CRUD, AdsPower import including authenticated SOCKS5, engines, fingerprint, operations/tools, automation/integrations, Docker and automated gate.

## Still intentionally not faked

Low-latency video Live View/input streaming, full CDP target proxy, WebRTC proxy-IP rewriting and team/cloud sync require dedicated browser/network/security architecture. They remain explicit backlog, not green UI switches.
