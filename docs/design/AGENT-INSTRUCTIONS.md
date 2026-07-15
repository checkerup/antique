# antique — Instructions for the design/generation agent

You are producing the full visual identity for **antique**, a self-hosted
anti-detect browser. Everything you need is in this folder:

- `BRAND.md` — identity, colors, glyph concept, do/don't, typography, voice.
- `ASSET-SPEC.md` — exact files, sizes, formats, destination paths, wiring.
- `PROMPTS.md` — copy-paste prompts for the image model.

## Workflow (do in order)

1. **Logo first.** Generate Concept A (“Masked A”) from `PROMPTS.md`. Produce
   3–4 variations, pick the one most legible at 16px. Also render Concept B
   and C once each as alternates for the record.
2. **Vectorize.** The icon MUST end up as clean SVG (not raster). Options:
   - recreate the chosen concept directly in SVG by hand/in Figma, or
   - auto-trace the raster (e.g. `vtracer` / Illustrator Image Trace) then
     hand-clean nodes. Target a single monoline path for the glyph.
   Keep the gradient as an SVG `<linearGradient>` at 135°, stops #4d8dfd →
   #b98cff.
3. **Export the icon set** listed in `ASSET-SPEC.md` §1 (svg + 16/32 png +
   apple-touch 180 + icon-1024). Use a squircle mask (iOS-style), not a plain
   rounded rect.
4. **Wordmark lockups** (§2): set “antique” in Inter/Geist 600, build dark and
   light SVG lockups.
5. **Marketing** (§3): social-card 1280x640, README-banner 1280x320, hero.
6. **Screenshots** (§4): run the app (`start.bat`, then
   http://127.0.0.1:8080/), capture dark + light at 2x, trim chrome.
7. **Optimize:** run `svgo` on all SVGs; compress PNGs (pngquant/oxipng).
8. **Wire into the app** following `ASSET-SPEC.md` §5 (static mount + favicon
   links + swap the text `.logo` box for the gradient mark). Reload the
   dashboard and confirm it still renders in both themes.

## Hard constraints

- Gradient is EXACTLY 135°, #4d8dfd → #b98cff, 2 stops. Same everywhere.
- Neutrals and accents must match the tokens in `BRAND.md` (they mirror the
  live UI in `src/ui/templates/index.html` — don't invent new colors).
- Lowercase “antique” always. Never all-caps, never a literal human face.
- No hacker/matrix/spy cliches. Developer-tool polish only.
- Every icon must read at 16px. Test before finalizing.

## Deliverable = a PR that

- adds `src/ui/static/*` and `assets/brand/*` per the spec,
- wires favicon + logo into `index.html` and static mount into `server.py`,
- updates README to show `assets/brand/README-banner.png` at the top,
- leaves the dashboard working in dark AND light themes.

## Notes / rationale

- The “masked a” ties the name to the core value (identity + concealment) and
  stays unique vs competitors (Dolphin = dolphin, GoLogin = wordmark, AdsPower
  = generic). Keep it abstract and geometric.
- If you can only ship one thing well: the **gradient squircle app icon** +
  **favicon** + **social card**. Those three carry 90% of the brand impression
  on GitHub.
