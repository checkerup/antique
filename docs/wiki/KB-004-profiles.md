# KB-004 — Profile Lifecycle & Sync

**Applies to: antique ≥ 1.1.1** (updated: 2026-09-04)

## Lifecycle
`create → (import cookies) → start (launch engine) → automation → stop → export/sync`

- `POST /user/create` — name, group_id, tags, cookies, proxy, fingerprint (optional; auto-randomized otherwise).
- Start: engine profile dir `ANTIQUE_DATA_DIR/profiles/{user_id}/`, stealth flags injected, window title labeled.
- Statuses: `new / active / paused / archived` (+ AdsPower-compatible account statuses).

## Sync (cross-machine)
Encrypted AES-GCM snapshots (`/user/snapshot/export|import`) carry the full profile record (fingerprint, cookies, proxy, tags, groups by id). Profiles with colliding `user_id` are skipped unless `overwrite: true`.

## Import paths
| Source | Mechanism |
|--------|-----------|
| AdsPower `.adb` backup | `/user/import/backup` (preview: `/preview`) |
| AdsPower live DB | `tools` decrypt AES-CBC cookies from local AdsPower SQLite (internal, not in public repo) |
| Antique snapshot | `/user/snapshot/import` |

## Rules
- One user-data-dir must never be opened by AdsPower and Antique simultaneously.
- Test imports use `TEST-MIGRATION-` prefix.
