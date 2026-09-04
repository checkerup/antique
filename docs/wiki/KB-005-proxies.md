# KB-005 — Proxy Providers & Crypto Payout Filter

**Applies to: antique ≥ 1.1.2** (updated: 2026-09-05)

## Provider kinds

`GET /proxy/providers/kinds` returns 8 kinds:
`file, json, http-json` (generic) + `nodemaven, proxy-seller, proxy-cheap, proxy6, proxy5` (crypto-native vendor adapters).

Vendor adapters send `Authorization: Bearer <key>` (from request body or
`<VENDOR>_API_KEY` env var) and normalize common pool payloads
(`proxies|data|results|items`, `{host,port}`).

## Payout matrix (verified 2026-09-05)

| Provider | Commission | Pay-in / Payout | Status |
|----------|-----------|-----------------|--------|
| NodeMaven | 50% first payment + 10% recurring | ✅ crypto / ✅ USDT TRC-20, BTC | live |
| Proxy-Seller | up to 50% lifetime | ✅ crypto / ✅ USDT, BTC | live |
| Proxy-Cheap | 25% lifetime | ✅ crypto (CoinGate) / ✅ wallet | live |
| Proxy6 | 30% first payment, 20% recurring | ✅ / ✅ USDT ERC-20/BEP-20, WebMoney WMZ, **no minimum** | live |
| Proxy5 | 10% lifetime | ✅ / ✅ USDT TRC-20, min $50 | live |
| LunaProxy | — | — | ❌ site unreachable (RU network) — removed |
| IP2World | — | — | ❌ site unreachable (RU network) — removed |
| Decodo | pay-in crypto | ❌ western payout rails | excluded |
| BrightData | pay-in crypto | ❌ PayPal/bank | excluded |
| Oxylabs | ❌ no crypto pay-in | ❌ | excluded |
| 922S5 | closed 2026 | — | — |

Rule: providers without crypto/ru-card payout, or unreachable from the
target network, are excluded from the UI provider dropdown regardless of price.

## Referral links (in-app, Settings → Proxy providers)

| Vendor | Link |
|--------|------|
| NodeMaven | `https://nodemaven.com/?ref_id=1d8624a8` |
| Proxy-Seller | `https://proxy-seller.com/?partner=ZABA0TN9F1GYRZ` |
| Proxy-Cheap | `https://app.proxy-cheap.com/r/jmYN04AE` |
| Proxy6 | `https://proxy6.net/?r=495791` |
| Proxy5 | `https://proxy5.net/user/aff.php?aff=298` |

Referral IDs are affiliate codes, not secrets: they are meant to be published
inside the app UI. Registered by the project owner.

## In-app behavior
- Proxy leak: `f70c288` fixed plaintext password exposure in API responses (masked since 1.0.1).
- Rotation & health-check built in; geo-matching pairs profile locale/timezone with proxy exit.
