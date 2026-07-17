# Antique 0.9.0: owner-complete operations slice

## Added

- Activity filtering by `user_id` and `action`.
- Activity JSON export via `POST /activity/export` and dashboard Tools button.
- Extension catalog workflow in Tools: list installed extensions, install unpacked path or 32-character Web Store ID.
- MCP status workflow in Tools, with the honest transport state `stdio`.
- Nested group parent support and UI folder creation.
- Static UI contract now covers all owner-facing Tools actions.
- New activity/export/extension/MCP regression coverage.
- Version synchronized to 0.9.0.

## Tests

```powershell
cd C:\ai_workflow\antidetect-local
.\.venv\Scripts\Activate.ps1
python -m pip install -e .
python -m pytest -q
python -m pytest tests\test_operations_release.py tests\test_sort_clone_features.py tests\test_import_launch_and_randomize.py tests\test_ui_release_040.py -v
```

## Full owner run

Use `docs/OWNER-FULL-TEST-CHECKLIST.md`. It now includes activity filter/export, extension catalog, MCP status, nested folders, backup schedules, provider testing and all earlier browser/import/fingerprint/automation checks.

## Honest limits

MCP remains a stdio integration, extension Web Store install requires network, Live View remains periodic screenshots, legacy CDP multiplexer remains simulated, and WebRTC IP rewriting/team cloud sync remain separate architecture work.
