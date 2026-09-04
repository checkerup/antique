# KB-006 — Deployment

**Applies to: antique ≥ 1.1.1** (updated: 2026-09-04)

## Requirements
- Python 3.11+ (`pip install -e .` or `pip install -r requirements.txt`), Chromium/Camoufox available for profile launch.
- Data root: `ANTIQUE_DATA_DIR` (default `./data`). Contains `antique.db` (SQLite), `profiles/` (per-profile browser dirs), `extensions/`, `fingerprint_corpus/`.

## systemd (recommended, prod)
```ini
# ~/.config/systemd/user/antique-api.service
[Unit]
Description=Antique API (prod, LAN+token)
After=network.target

[Service]
Type=simple
KillMode=control-group
WorkingDirectory=%h/antique
EnvironmentFile=%h/.antique_token.env        # ANTIQUE_API_TOKEN=...
Environment=ANTIQUE_DATA_DIR=%h/antique/data
Environment=ANTIQUE_DEPLOY_MODE=lan
Environment=ANTIQUE_HEADLESS=1
ExecStart=%h/antique/.venv/bin/python -m src.cli serve --host 0.0.0.0 --ui-port 8085 --headless
Restart=always
RestartSec=3

[Install]
WantedBy=default.target
```
```bash
systemctl --user daemon-reload && systemctl --user enable --now antique-api
loginctl enable-linger $USER   # survive reboot
```

**Pitfalls learned 2026-09-04:**
- `KillMode=control-group` is REQUIRED: uvicorn spawns children that survive `kill -9` of the main PID, hold the port, and get reparented to init — a respawned instance then crashes with "address already in use" in a loop.
- `EnvironmentFile` needs plain `KEY=VALUE` lines (no `export`, no `source`-able shell syntax).
- The old nested `data/data/antique.db` layout was a bug — one data root only (`ANTIQUE_DATA_DIR`).

## Profile sync (Windows → Linux server)
```bash
# Export (offline, no server needed)
python -c "from src.core.profile import ProfileStore; from src.core.operations import encrypted_snapshot; \
  encrypted_snapshot(ProfileStore(Path('data/antique.db')), Path('out.sync'), 'PASSWORD')"
scp out.sync server:/tmp/
# Import on server
curl -X POST -H "Authorization: Bearer $ANTIQUE_API_TOKEN" \
  -d '{"path":"/tmp/out.sync","password":"PASSWORD"}' http://127.0.0.1:8085/user/snapshot/import
```

## Docker
See `docs/packaging/PACKAGING.md` and repo `Dockerfile`.

## Update procedure
```bash
systemctl --user stop antique-api
cd ~/antique && git fetch origin && git reset --hard origin/main
systemctl --user start antique-api
```
