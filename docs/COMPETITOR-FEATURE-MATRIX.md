# Feature matrix: Antique 0.4.0 vs popular anti-detect managers

The goal is parity where it is useful, not blindly cloning every paid feature. Many vendor pages advertise anti-detect guarantees that cannot be verified from a local manager.

## Implemented in Antique

- Isolated persistent profiles with SQLite metadata and per-profile user-data directories.
- AdsPower-compatible REST API and CLI.
- Whole AdsPower backup import, single `.adb`/zip import, cookie JSON/Netscape import.
- Authenticated SOCKS5 bridge for imported AdsPower proxies.
- Per-profile proxy, proxy health-check, proxy pools and rotation strategies.
- Geo alignment: locale, languages, timezone and geolocation.
- Fingerprint generation and editing: UA, platform, screen, hardware, WebGL/WebGPU, fonts, audio/canvas seeds, plugins, connection, WebRTC block.
- Smart bulk fingerprint randomization with shared and preserved field groups.
- Swappable Chromium, Chrome, Edge, Firefox, Camoufox and WebKit engines.
- Persistent cookies, Local Storage, IndexedDB, WebStorage and portable `.antq` export/import.
- Extensions install/assignment for Chromium.
- Cookie Robot flows, warm, sync flows across profiles.
- Live screenshot, per-profile real Chromium CDP, account statuses, notes/remarks, tags and groups.
- Light/dark dashboard, filtering, full profile-list sorting, bulk start/stop/delete/export/proxy/status actions.
- Clone profile, re-import state, Swagger, Docker, MCP and optional API auth.
- Stealth collector/scoring harness and Windows console compatibility.

## Added in this release

- `/user/list?sort_by=...&sort_order=asc|desc` for API clients.
- CLI: `list --sort ... --order asc|desc`.
- UI sorting: name, ID, live, engine, account status, group, tags, proxy, cookies, launches, created, updated, last launched; selection persists in localStorage.
- REST/CLI/UI profile clone.
- Bulk status updates.
- New regression tests for all three.

## Implemented in 0.9.0

- Backup dry-run preview: `/user/import/backup/preview`, CLI `preview-backup`, dashboard Tools.
- Mass-create templates: `/user/template/create`, CLI `template-create`.
- Encrypted AES-GCM snapshots: `/user/snapshot/export`, `/user/snapshot/import`, CLI snapshot commands.
- Activity history foundation: `/activity`, CLI `activity`.
- Local file/JSON proxy providers: `/proxy/providers/kinds`, `/proxy/providers/test`.
- Group CRUD: `/group/create`, `/group/update`, `/group/delete`.
- Resource and MCP health status: `/resource/status`, `/mcp/status`.
- Activity hooks on create/update/start/stop/delete/import/bulk status.
- Backup scheduler registry with encrypted snapshot run: `/backup/schedules`, CLI `backup-schedule` and `backup-schedules`.
- HTTP JSON proxy provider adapter, with no credentials stored in profile records.
- Activity filters and JSON export.
- Extension catalog UI for installed extensions and local/Web Store installation.
- MCP status UI and nested folder creation in Tools.

## High-value parity backlog

These are the remaining serious gaps against AdsPower/Dolphin/GoLogin-style managers:

1. **Nested folders and drag/drop assignment**: flat group CRUD is implemented; nested hierarchy and drag/drop remain.
2. **Activity history**: add richer event filters, retention and export. Core hooks are implemented.
3. **Profile templates and mass creation**: add a dashboard template editor and preview. API/CLI batch creation are implemented.
4. **Backup scheduler**: external scheduler integration and restore validation remain. Registry and encrypted run are implemented.
5. **Proxy provider adapters**: add provider-specific auth/config adapters. File, JSON and HTTP-JSON sources are implemented.
6. **Extension catalog UI**: search/install/update from Web Store or local catalog, not just API install.
7. **MCP management in UI**: status, start/stop, tool health and connection settings.
8. **Real Live View stream**: current Live View is periodic PNG screenshots, not low-latency video/input streaming.
9. **CDP target proxy**: the legacy multiplexer remains simulated; direct Chromium CDP is real.
10. **WebRTC proxy-IP rewriting**: current behavior blocks external candidates; it does not expose a proxy-matched ICE IP.
11. **Resource/process dashboard**: CPU, RAM, browser PID, port, uptime and crash reason per profile.
12. **Import validation wizard**: dry-run preview, collision report, invalid proxy report, cookie count and storage health before committing.
13. **Team/cloud sync**: intentionally not included in the local-first build; would require a security model and encrypted transport.

## Recommendation

Do not add all twelve blindly. The best next product slice is: activity history, mass-create templates, import dry-run, folders, resource monitoring, then extension catalog. WebRTC rewriting and a video Live View need deeper browser/network work and should not be faked in UI.
