# KB-002 — API Reference (AdsPower-compatible)

**Applies to: antique ≥ 1.1.1** (updated: 2026-09-04)

All endpoints follow the AdsPower response envelope: `{"code": 0, "msg": "success", "data": {...}}`.
Error codes: `0` = ok, `-1` = generic error, `401/403` auth errors (LAN mode).

## Authentication
- `local` mode (loopback): no token needed.
- `lan`/`remote` mode: `Authorization: Bearer $ANTIQUE_API_TOKEN` required on every request except `/health`, `/info`.

## Profile management
| Method | Path | Notes |
|--------|------|-------|
| GET | `/user/list` | Paginated. **Cookies are NOT serialized** (masked to count only) since 1.1.1. |
| GET | `/profile/{user_id}` | Full profile. Cookies only with `?include_cookies=true`. |
| POST | `/user/create` | Accepts `cookies[]` at creation. |
| POST | `/user/update` | Partial update. |
| POST | `/user/delete` | |
| POST | `/user/bulk/{action}` | create / status / export … |
| POST | `/user/export` | AdsPower-compatible export. |

## Snapshots & sync
| Method | Path | Notes |
|--------|------|-------|
| POST | `/user/snapshot/export` | AES-GCM encrypted, `{"path", "password"}`. |
| POST | `/user/snapshot/import` | `{"path", "password", "overwrite?"}`. Returns `imported_count`/`skipped_count`. |

## Proxy providers
| Method | Path | Notes |
|--------|------|-------|
| GET | `/proxy/providers/kinds` | 8 crypto-native payout kinds (since 1.1.1). |

## Legacy aliases (AdsPower drop-in)
`/profile/start/{id}` ↔ `/user/start`, auditProfile, startProfile etc. — see `src/api/routes.py`.

## Cookie handling policy (1.1.1)
List responses never include cookie values. Detail includes them only on explicit opt-in. This prevents accidental LAN exposure of live session cookies.
