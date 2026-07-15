# antique — Quick Start

Self-hosted anti-detect browser: isolated profiles, per-profile fingerprints,
proxies, multi-engine, AdsPower import, dashboard + REST API + MCP.

## 1. What you need

- **Python 3.10+** on PATH (`python --version`).
- Windows / macOS / Linux. (Batch launcher below is Windows.)
- Everything else (browser engine, deps) is installed automatically on first run.

## 2. Start it (Windows, one click)

Double-click **`start.bat`** in the project root.

- First run: creates `.venv`, installs antique, downloads the Chromium engine.
- Later runs: just boots the server.
- Stop with `Ctrl+C`.

Then open:

- Dashboard: <http://127.0.0.1:8080/>
- API docs (Swagger): <http://127.0.0.1:8080/docs>

### Manual start (any OS)

```bash
python -m venv .venv
. .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -e .
python -m playwright install chromium firefox webkit
python -m src.cli serve --ui-port 8080
```

## 3. First steps in the dashboard

1. **+ New profile** — name it, pick an **engine**, optionally a **geo country**
   (aligns timezone/locale/geolocation) and a proxy. A coherent fingerprint is
   generated automatically.
2. **Start** — launches a real browser window with that profile's fingerprint
   + proxy. **Stop** closes it.
3. **FP** — edit the fingerprint (engine, UA, screen, hardware, WebGL, WebRTC) without resetting omitted fields.
4. Select profiles → **Assign proxies** for cyclic bulk assignment from a pasted list.
5. Select profiles → **Randomize fingerprint** to choose OS, shared fields (for example one resolution), preserved fields, and an optional deterministic seed.
6. **⚡** — live-check the profile's proxy (IP + latency).
7. Top-right **☀️/🌙** — toggle light / dark theme (remembered).

## 4. Import your AdsPower profiles

**Import → AdsPower backup folder.** Point it at your backup directory (the one
with `all_profiles_list.json`, e.g. `C:\ai_workflow\adspower_profiles_backup`).
Profiles, cookies, proxies, tags and local state are imported and the original
AdsPower `user_id` is preserved. AdsPower `ip_country` aligns geo settings.
Authenticated SOCKS5 profiles use an automatic local bridge, so Chromium can
start them without the old HTTP 500. Tick *Overwrite* to refresh existing profiles.

**Import → Single file / .adb** for a one-off `.adb`/`.zip` bundle, a Netscape
`cookies.txt`, or a Playwright/Chrome cookie JSON.

CLI equivalent:

```bash
python -m src.cli import-backup "C:\ai_workflow\adspower_profiles_backup"
python -m src.cli import-cookies path\to\bundle.adb --full
```

## 5. Browser engines

Engines are swappable per profile (or globally via `ANTIDETECT_ENGINE`):

| key | base | stealth | notes |
|---|---|---|---|
| `chromium` | Chromium | standard | default, bundled, extensions + real CDP |
| `chrome` | Chromium | standard | real Google Chrome (must be installed) |
| `edge` | Chromium | standard | real Microsoft Edge (must be installed) |
| `firefox` | Firefox | standard | bundled Gecko, no Chromium tells |
| `camoufox` | Firefox | **deep** | hardened Firefox, engine-level spoofing; `pip install camoufox` |
| `webkit` | WebKit | basic | Safari-like, for macOS/iOS-flavoured profiles |

```bash
python -m src.cli engines                 # list engines
python -m src.cli create "p1" --engine camoufox
```

Enable Camoufox (strongest stealth):

```bash
pip install camoufox
python -m camoufox fetch
```

## 6. Automation / AI

- **REST API** (AdsPower-compatible) at `/docs`. Set `ANTIQUE_API_TOKEN` to
  require a Bearer token; set `ANTIQUE_ALLOWED_ORIGINS` if exposing via a tunnel.
- **MCP server** for AI agents: `python -m src.cli mcp` (stdio).
- External automation attaches over the per-profile CDP websocket returned by
  `POST /user/start`.

## 7. Environment variables

| var | default | purpose |
|---|---|---|
| `ANTIQUE_DATA_DIR` | `./data` | DB + profile data dirs |
| `ANTIDETECT_ENGINE` | `chromium` | global default engine |
| `ANTIQUE_API_TOKEN` | (unset) | require Bearer token on the API |
| `ANTIQUE_ALLOWED_ORIGINS` | (unset) | extra trusted origins (tunnels) |

## 8. Run in Docker (alternative to start.bat)

```bash
docker compose up          # dashboard on http://127.0.0.1:8080/
```
Profiles + DB persist in the `antique-data` volume. Runs headless in the
container. Set `ANTIQUE_API_TOKEN` in `docker-compose.yml` if you expose the port.

## 9. New in 0.6.0

- AdsPower backup preview, mass-create templates, encrypted snapshots, activity history, provider adapters, group CRUD, resource/MCP status and Tools panel.
- Full profile-list sorting in UI, CLI and REST, with asc/desc and persistent UI selection.
- Clone profile, bulk status updates, and improved profile operations in Manage.
- Competitor parity matrix and remaining product backlog: `docs/COMPETITOR-FEATURE-MATRIX.md`.

### Also included from 0.5.0 and 0.4.0

- Fixed AdsPower authenticated-SOCKS5 profile launch via a loopback RFC 1929 bridge.
- Added bulk proxy assignment and smart fingerprint randomization to the dashboard.
- Partial fingerprint create/update now merges safely instead of blanking hidden fields.
- `start.bat` prepares Chromium, Firefox, WebKit and Camoufox best-effort.
- Full manual test plan: `docs/MANUAL-TEST-PLAN.md`.

### Also included from 0.3.0

- **Live View** — on a running profile click the eye icon to watch a live
  screenshot; the modal also shows the real CDP websocket for automation.
- **Account statuses** — each profile has a status (new/warming/active/limited/
  banned/retired); set it inline in the table or filter by it.
- **Sync groups** — run one automation flow across many profiles at once:
  `python -m src.cli sync flow.json -u <id1> -u <id2>` or `POST /sync/run`.
- **Real per-profile CDP** — `GET /user/{id}/cdp` returns the attachable
  DevTools websocket for a running Chromium profile.

## 10. Sort, clone and bulk status

```bash
python -m src.cli list --sort name --order desc
python -m src.cli clone <USER_ID> --name "Copy"
python -m src.cli bulk-status <USER_ID_1> <USER_ID_2> warming
```

In the dashboard use **Sort**. Pick a field and select it again to flip ascending/descending. The choice survives reload.

That's it. Create a profile, hit **Start**, and you're running.
