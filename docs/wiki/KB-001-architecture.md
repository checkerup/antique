# KB-001 — Architecture Overview

**Applies to: antique ≥ 0.4** (updated: 2026-09-04)

```
┌───────────────────────── src/ ─────────────────────────┐
│ cli.py        argparse entry: serve, import, snapshot   │
│ api/                                                      │
│  ├ server.py  uvicorn app, deploy modes (local/lan/remote)│
│  └ routes.py  AdsPower-compatible REST surface           │
│ core/                                                     │
│  ├ profile.py   ProfileStore (SQLite/SQLModel)           │
│  ├ browser.py   engine launch (Chromium/Camoufox),       │
│  │              fingerprint flags                        │
│  ├ cookie.py    cookie import/export/translation         │
│  ├ adspower_crypto.py AES-CBC live cookie decrypt        │
│  └ operations.py  snapshots (AES-GCM), bulk ops          │
│ ui/            SPA dashboard (3 languages, PWA)          │
└──────────────────────────────────────────────────────────┘
```

- **Store**: single SQLite DB at `ANTIQUE_DATA_DIR/antique.db` (tables: profiles, groups, tags, activity_events, sessions, migration_state).
- **Per-profile browser data**: `ANTIQUE_DATA_DIR/profiles/{user_id}/`.
- **Fingerprint corpus**: shipped JSON corpus + synthesis with OS-coherent GPU selection.
- **Stealth flags**: `--protected-canvasmark --protected-webglmark --protected-webglfp --disable-features=UserAgentClientHint`.
- **Import paths**: AdsPower `.adb` bundles (encrypted), AdsPower live SQLite cookie decrypt, snapshot files.

See KB-002 (API), KB-003 (security), KB-004 (profiles), KB-005 (proxies), KB-006 (deployment), KB-007 (fingerprint), KB-008 (UI).
