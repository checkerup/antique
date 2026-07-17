# Antique 0.9.0: owner-complete operations slice

## Added

- Activity filtering by `user_id` and `action`.
- Activity JSON export via `POST /activity/export` and dashboard Tools button.
- Extension catalog workflow in Tools: list installed extensions, install unpacked path or 32-character Web Store ID, uninstall installed extensions.
- MCP status in UI, with honest `stdio` transport reporting.
- Nested group tree endpoint `/group/tree`, parent-aware CRUD, safe deletion guards for default and non-empty parent folders, and UI folder management.
- Static UI contract and operation regression coverage expanded.
- Version synchronized to 0.9.0.

## Required test commands

```powershell
cd C:\ai_workflow\antidetect-local
.\.venv\Scripts\Activate.ps1
python -m pip install -e .
python -m pytest -q
python -m pytest tests\test_operations_release.py tests\test_sort_clone_features.py tests\test_import_launch_and_randomize.py tests\test_ui_release_040.py -v
```

## Full owner run

Use `docs/OWNER-FULL-TEST-CHECKLIST.md`. It covers activity filter/export, extension catalog install/uninstall, MCP status, nested folders, backup schedules, provider testing, resource metrics and all earlier browser/import/fingerprint/automation checks.

## Honest limits

MCP remains a stdio integration, extension Web Store install requires network, Live View remains periodic screenshots, legacy CDP multiplexer remains simulated, and WebRTC IP rewriting/team cloud sync remain separate architecture work.
