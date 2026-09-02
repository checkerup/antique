# Packaging Guide for antique

This document covers all packaging, deployment, and distribution paths.

## 1. Reproducible dependency lock

`packaging/requirements-lock.txt` pins every transitive dependency to the
exact version that passed CI. Use it as a pip constraints file:

```bash
# Install with pinned versions (reproducible)
pip install -c packaging/requirements-lock.txt -e .
pip install -c packaging/requirements-lock.txt -r requirements.txt
```

**Regenerate** the lock from a known-good venv:

```bash
pip freeze --exclude-editable | sort > packaging/requirements-lock.txt
```

The lock is compatible with the existing `.venv` — it doesn't replace
`requirements.txt` (which stays as the source of unpinned ranges), it
constrains the resolution to exact versions.

## 2. Windows portable build (PyInstaller)

Build a self-contained portable directory:

```bat
scripts\build-portable.bat
```

Output: `dist\antique-portable\antique\antique.exe`

The portable bundle includes:
- The antique CLI executable + all Python dependencies
- UI templates and static files
- Fingerprint corpus data

It does **not** bundle Playwright browser binaries — those are downloaded
on first run via `start.bat` inside the portable bundle.

### PyInstaller spec

`packaging/antique.spec` defines the build configuration:
- `--onedir` mode (directory, not single-file — faster startup)
- Hidden imports for dynamically-loaded modules (uvicorn, sqlalchemy, etc.)
- Data files: UI templates, static assets, fingerprint corpus
- No UPX (can trigger AV false positives)

## 3. One-click Windows launcher

`scripts/antique-launcher.bat` provides install/update/rollback/serve:

```bat
scripts\antique-launcher.bat install     :: fresh install
scripts\antique-launcher.bat update       :: update deps + package
scripts\antique-launcher.bat rollback     :: show previous version
scripts\antique-launcher.bat serve       :: start server (default)
```

- Install/update use `packaging/requirements-lock.txt` for reproducibility.
- Pre-update version is recorded in `.antique-backups\last_version.txt`.
- Rollback prints instructions for manual git checkout + reinstall.

## 4. Linux systemd service

Install as a hardened systemd service:

```bash
sudo bash packaging/install-systemd.sh
sudo systemctl enable --now antique
```

**Hardening** (in `packaging/antique.service`):
- Non-root `antique` system user (no shell login)
- `NoNewPrivileges=true`
- `ProtectSystem=strict` (only `/var/lib/antique` writable)
- `ProtectKernelTunables/Modules/ControlGroups=true`
- `PrivateTmp`, `PrivateDevices`
- `CapabilityBoundingSet=` (empty — no capabilities)
- `RestrictAddressFamilies=AF_INET AF_INET6 AF_UNIX`
- Resource limits: 4096 file descriptors, 512 tasks

## 5. Docker (hardened)

```bash
docker compose up
```

**Hardening defaults** (in `docker-compose.yml`):
- Non-root `antique` user inside the container
- `read_only: true` filesystem (writes only to `/data` volume)
- `security_opt: no-new-privileges:true`
- `cap_drop: ALL`
- Memory limit: 2GB, CPU limit: 2.0
- Healthcheck on `/health` endpoint
- Port bound to `127.0.0.1` only (not `0.0.0.0`)

## 6. CI matrix

`.github/workflows/ci.yml` runs on every push/PR:

| job | OS | Python | what |
|---|---|---|---|
| `test` | ubuntu + windows | 3.11, 3.12 | unit tests, compile checks |
| `static-checks` | ubuntu | 3.11 | config validation, security defaults |
| `package-build` | ubuntu + windows | 3.11/3.12 | sdist+wheel build, install smoke |

Static checks verify:
- `pyproject.toml` parses as valid TOML
- `requirements.txt` entries are well-formed
- `requirements-lock.txt` pins are `name==version` format
- `antique.service` has hardening directives
- `Dockerfile` has `USER antique` (non-root)
- `docker-compose.yml` has `no-new-privileges`, `cap_drop`, `read_only`

## 7. Code signing

**No code signing is configured or claimed.** The portable `.exe` will
trigger Windows SmartScreen warnings on first run. To resolve this in
production:

1. Obtain an EV (Extended Validation) code signing certificate.
2. Sign `antique.exe` with `signtool`:
   ```bat
   signtool sign /f cert.pfx /p PASSWORD /fd SHA256 /tr http://timestamp.digicert.com /td SHA256 dist\antique-portable\antique\antique.exe
   ```
3. Submit to Microsoft for SmartScreen reputation building.

See the [Microsoft docs](https://learn.microsoft.com/en-us/windows-hardware/drivers/install/authenticode-signing)
for Authenticode signing details.
