# KB-008 — UI & i18n

**Applies to: antique ≥ 1.1.0** (updated: 2026-09-04)

- SPA dashboard at `/` (served by the same uvicorn): profiles grid, groups tree, automation, extensions, proxy settings, backups, settings.
- i18n: EN / RU / ZH — `src/ui/templates/assets/i18n.js`; README parity `README.md` / `README.ru.md` / `README.zh.md`.
- PWA manifest + dark/light theme; a11y pass done.
- UI reads cookies ONLY as counts/flags (`cookies_count`, `has_cookies`) — never values (1.1.1 masking).
- Test scripts live outside the repo (`.ui_*.py`) — DOM 0 JS errors required on all 8 screens.
