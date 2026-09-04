# KB-003 — Security Model

**Applies to: antique ≥ 1.1.1** (updated: 2026-09-04)

## Threat model
Self-hosted antidetect browser farm. Primary risks: (1) session-cookie theft from API, (2) LAN exposure, (3) repo hygiene (public GitHub).

## Deploy modes
| Mode | Binding | Auth |
|------|---------|------|
| `local` | 127.0.0.1 | none (trusted loopback) |
| `lan` | 0.0.0.0 | Bearer token required (`ANTIQUE_API_TOKEN`) |
| `remote` | 0.0.0.0 | Bearer token required |

## Cookie exposure policy
- `/user/list`: cookies masked (count only).
- `/profile/{id}`: full cookies only with `?include_cookies=true`.
- Rationale: 2026-09 audit found 64/119 profiles' live Google sessions (`__Secure-ENID`, `__Host-GAPS`) serialized in plaintext list responses on LAN.

## Production hardening checklist
1. `ANTIQUE_DEPLOY_MODE=lan` + strong `ANTIQUE_API_TOKEN` (stored in `~/.antique_token.env`, chmod 600).
2. systemd user unit with `KillMode=control-group` (kills orphaned uvicorn children on restart).
3. `git` tracking: NEVER commit cookies/keys/profiles — `.gitignore` covers `tools/`, `*_cookies.json`. Pre-push scan required (see repo hygiene rule).

## Known limitations
- Token is static (no rotation/HTTPS termination; put behind reverse proxy for TLS).
- UI statics served from the same port as API — no separate auth realm.
