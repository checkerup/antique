# Antique 0.6.0: полный parity-релиз

## Реализовано

- AdsPower backup dry-run preview: API `/user/import/backup/preview`, CLI `preview-backup`, dashboard Tools.
- Mass-create templates: API `/user/template/create`, CLI `template-create`, deterministic seed support.
- Encrypted AES-GCM snapshots: API `/user/snapshot/export` and `/user/snapshot/import`, CLI `snapshot-export` and `snapshot-import`.
- Activity history foundation: SQLite `activity_events`, API `/activity`, CLI `activity`.
- Local/JSON proxy provider adapters: API `/proxy/providers/kinds` and `/proxy/providers/test`.
- Group CRUD: `/group/create`, `/group/update`, `/group/delete`.
- Resource/MCP health: `/resource/status`, `/mcp/status`.
- UI Tools panel for backup preview, activity and resource status.
- Updated docs, requirements, version to 0.6.0, and parity matrix.

## Tests added

`tests/test_operations_release.py` covers template batches, audit events, provider file/JSON loading, resource/MCP endpoints and group creation. Existing tests remain required, especially AdsPower import, auth-SOCKS5 launch, randomization, sorting, engines, Live View/CDP and sync.

## Agent command

```powershell
cd C:\ai_workflow\antidetect-local
.\.venv\Scripts\Activate.ps1
python -m pip install -e .
python -m pytest -q
python -m pytest tests\test_operations_release.py tests\test_sort_clone_features.py tests\test_import_launch_and_randomize.py tests\test_ui_release_040.py -v
```

## Manual smoke order

1. Start `start.bat`, open the dashboard and confirm version 0.6.0.
2. Tools → Preview AdsPower backup. Confirm it only reports profiles and does not create them.
3. Swagger `/user/template/create`: create three deterministic test profiles.
4. Tools → Recent activity and Resource status.
5. Create a local proxy file and test `/proxy/providers/test`.
6. Create/update/delete a non-default test group.
7. Export/import an encrypted snapshot with the correct password, then repeat with a wrong password and confirm no database changes.
8. Re-run the earlier full smoke: auth-SOCKS5 AdsPower profile, bulk proxy, randomization, sorting, clone, engines, Live View, CDP, sync, extensions, themes and mobile layout.

## Honest boundaries

The matrix items that remain deeper engineering are video-quality Live View, full CDP target proxying, WebRTC proxy-IP rewriting, provider-specific cloud APIs and team/cloud sync. The build exposes no fake green switches for those; they remain explicitly documented as backlog.
