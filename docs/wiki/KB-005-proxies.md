# KB-005 — Proxy Providers & Crypto Payout Filter

**Applies to: antique ≥ 1.1.1** (updated: 2026-09-04)

## Provider kinds
`GET /proxy/providers/kinds` returns 8 crypto-native payout kinds:
`usdt_trc20, usdt_bep20, usdt_spl, btc, ton, ton_jetton, eth_erc20, mixed_crypto`

## Payout matrix (researched 2026-09-04)
| Provider | Pay-in | Payout |
|----------|--------|--------|
| NodeMaven | ✅ | ✅ |
| LunaProxy | ✅ | ✅ |
| Proxy-Seller | ✅ | ✅ |
| Proxy-Cheap | ✅ | ✅ |
| IP2World | ✅ | ✅ |
| Decodo | ✅ | ❌ |
| BrightData | ✅ | ❌ |
| Oxylabs | ❌ | ❌ |
| 922S5 | closed 2026 | — |

Rule: providers without crypto/ru-card payout are excluded from the UI provider dropdown regardless of price.

## In-app behavior
- Proxy leak: `f70c288` fixed plaintext password exposure in API responses (masked since 1.0.1).
- Rotation & health-check built in; geo-matching pairs profile locale/timezone with proxy exit.
