# CHANGELOG

## [1.1.1] — 2026-09-04

### Security
- **SEC**: `GET /user/list` and `GET /profile/{id}` no longer serialize session cookies. Full cookie values are returned only via explicit opt-in (`?include_cookies=true`) on the profile detail endpoint.
- **SEC**: repository scrubbed — leaked Google cookie fixtures and internal research scripts (PII) removed from git tracking and history.
- **SEC**: production server guidance — bind `0.0.0.0` only with `ANTIQUE_DEPLOY_MODE=lan` + `ANTIQUE_API_TOKEN` (systemd unit template in `docs/packaging/`).

### Added
- Crypto-native proxy provider filter (8 payout kinds: USDT/BTC/TON/TRC-20/ERC-20/TON-Jetton/BEP-20/SOL) — `GET /proxy/providers/kinds` & UI filter.
- Google auth hardening: profile setup with custom flags; proxy provider list expansion.
- Full SPA UI (AdsPower-style dashboard, 3 languages EN/RU/ZH, PWA, a11y) + classic AdsPower API aliases.
- AdsPower live cookie decryption (AES-CBC from local AdsPower SQLite), fingerprint extraction, extension import, window title labeling.
- Encrypted AES-GCM snapshots for full profile sync (`/user/snapshot/export|import`).

### Fixed
- GMGN ban loop, proxy password leak in API responses (v1.0.1), auto-open DevTools flag, corpus shipping for CI.

## [1.1.0] — production readiness and migration center (#1)
- Production readiness, migration center, hardened imports API.

## [1.0.x] — SPA UI, group tree, folder CRUD, multi-field sorting, cloning, bulk ops, smart fingerprint randomization
- See `docs/RELEASE-1.0.1-REPORT.md`.

## [0.5–0.9] — iterative releases
- Multi-field sorting, cloning, Russian/Chinese docs sync, group tree, Live View, real CDP, synchronized automation, Docker, engines registry, AdsPower backup import, dark/light theme.

## [0.4.0] — initial public release
- Groups, bulk ops, proxy health-check, bulk proxy import, fingerprint editing UI.
