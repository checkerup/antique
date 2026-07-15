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

## High-value parity backlog

These are the remaining serious gaps against AdsPower/Dolphin/GoLogin-style managers:

1. **Folder/group CRUD**: current group IDs and filtering work, but there is no first-class folder editor, nested folders or drag/drop assignment.
2. **Activity history**: store an audit trail for create, update, launch, stop, proxy change, import and status changes.
3. **Profile templates and mass creation**: create N profiles from a template with controlled fingerprint variation.
4. **Backup scheduler**: scheduled encrypted database/profile snapshots and restore validation.
5. **Proxy provider adapters**: optional integrations with provider APIs, with secrets kept out of profile JSON and logs.
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
