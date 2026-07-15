# antique — Asset Spec (exact deliverables)

> Every file a generation/design agent must produce, with sizes, formats and
> destination paths. Colors/gradient/glyph are defined in `BRAND.md`.
> Ready-to-use image-model prompts are in `PROMPTS.md`.

## Destination layout

```
src/ui/static/               <- create this; serve via FastAPI StaticFiles
  favicon.svg
  favicon-32.png
  favicon-16.png
  apple-touch-icon.png        (180x180)
  logo-mark.svg               (icon only, transparent)
  logo-mark-gradient.svg      (icon on gradient squircle)
  logo-lockup-dark.svg        (mark + “antique” wordmark, light text)
  logo-lockup-light.svg       (mark + “antique” wordmark, dark text)
assets/brand/                 <- repo-level marketing assets
  icon-1024.png               (app/store icon, gradient squircle)
  social-card.png             (1280x640 GitHub/OG banner)
  hero.png                    (1600x900 dashboard-on-gradient hero)
  screenshot-dark.png         (real dashboard screenshot, dark)
  screenshot-light.png        (real dashboard screenshot, light)
  README-banner.png           (1280x320 slim header for README)
```

## 1. App icon / favicon (Concept A — Masked A)

- **logo-mark.svg**: glyph only, white, transparent bg, 24x24 viewbox, single
  monoline. Must stay legible at 16px.
- **logo-mark-gradient.svg**: the glyph on a squircle filled with the identity
  gradient (135° `#4d8dfd→#b98cff`), corner radius 22% of side.
- **icon-1024.png**: 1024x1024 export of the gradient squircle, ambient shadow
  baked out (transparent corners). Source for store/app icon.
- **favicon.svg** + **favicon-32.png** + **favicon-16.png** + **apple-touch-icon.png**.

## 2. Wordmark lockups

- Horizontal lockup: mark + `antique` (Inter/Geist 600, tracking -0.5%).
- Two variants: **dark** (light text `#e6edf3`, for dark bg) and **light**
  (dark text `#16202e`, for light bg). Transparent backgrounds, SVG.
- Clear space around lockup = height of the mark on all sides.

## 3. GitHub / social

- **social-card.png** 1280x640: dark bg `#0b0e14`, lockup centered-left,
  identity-gradient accent shape bleeding from a corner, tagline
  “Self-hosted anti-detect browser” in muted text. This is the OG image.
- **README-banner.png** 1280x320: slim version, wordmark + one-liner.
- **hero.png** 1600x900: the dashboard screenshot floating on a soft
  gradient/blurred backdrop, subtle shadow. For the landing/README top.

## 4. Product screenshots (real, not mocked)

Take from the running app at `http://127.0.0.1:8080/`:
- **screenshot-dark.png** and **screenshot-light.png** — profiles table with a
  few sample rows, engine badges visible, one modal optionally open.
- Crop to 16:10, retina (2x), trim browser chrome.

## 5. Wiring the favicon/logo into the app (after assets exist)

1. Create `src/ui/static/` and drop the favicon set + `logo-mark-gradient.svg`.
2. In `src/api/server.py`, mount static files:
   ```python
   from fastapi.staticfiles import StaticFiles
   app.mount("/static", StaticFiles(directory=str(Path(__file__).parent.parent / "ui" / "static")), name="static")
   ```
3. In `src/ui/templates/index.html` `<head>`, add:
   ```html
   <link rel="icon" href="/static/favicon.svg">
   <link rel="apple-touch-icon" href="/static/apple-touch-icon.png">
   ```
   and replace the text logo box (`.logo`) with the gradient mark:
   ```html
   <img class="logo" src="/static/logo-mark-gradient.svg" alt="antique" width="34" height="34">
   ```
4. Point README/social preview at `assets/brand/social-card.png` via repo
   settings (Social preview) and a top `![antique](assets/brand/README-banner.png)`.

## 6. Acceptance checklist

- [ ] Icon legible at 16px and 1024px.
- [ ] Gradient identical everywhere (135°, `#4d8dfd→#b98cff`).
- [ ] Dark AND light lockups exist and pass contrast (WCAG AA on their bg).
- [ ] Favicon set complete (svg + 16 + 32 + apple-touch 180).
- [ ] Social card 1280x640, README banner 1280x320.
- [ ] SVGs optimized (svgo), PNGs compressed.
- [ ] Assets wired into `index.html` + `server.py`, dashboard still loads.
