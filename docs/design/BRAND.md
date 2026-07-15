# antique — Brand & Visual Identity

> Source of truth for the visual identity of **antique**, a self-hosted,
> open-source anti-detect browser (multi-profile fingerprint farm). This doc is
> written so a design/generation agent can produce every asset without further
> questions. Pair it with `ASSET-SPEC.md` (exact files to produce) and
> `AGENT-INSTRUCTIONS.md` (how to generate + assemble).

## 1. Positioning

- **What it is:** local, private, developer-first alternative to AdsPower /
  GoLogin / Multilogin. Runs on your machine, no cloud, no subscription.
- **Who it's for:** power users, scrapers, multi-account operators, automation
  engineers, AI agents.
- **Personality:** precise, technical, trustworthy, quietly powerful. NOT
  "hacker/dark-web" cliche (no green matrix code, no hoodies, no skulls).
  Think developer-tool polish: Linear, Vercel, Raycast, Arc.
- **One-liner:** “Every identity, isolated. Run tens of browser profiles that
  look like real, different people — on your own machine.”

## 2. Name & wordmark

- Product name is always lowercase: **antique**.
- Wordmark font: a modern geometric-humanist sans. Preferred (open-source):
  **Inter**, **Geist**, or **Space Grotesk**. Weight 600–700 for the wordmark.
- Letter-spacing: -0.5% to -1% (slightly tight). Never all-caps in the logo.
- The dotless glyph idea: the mark plays on the first letter **a** fused with a
  privacy **domino mask** (the classic eye-mask silhouette) — identity + hiding.

## 3. Color system

Matches the dashboard theme tokens already in `src/ui/templates/index.html`.

### Core
| Token | Hex | Use |
|---|---|---|
| Accent / Blue | `#4d8dfd` | primary brand, buttons, links |
| Accent light | `#6ea8fe` | dark-theme accent, highlights |
| Violet | `#b98cff` | gradient partner, secondary accent |
| Green | `#46c56a` | success, “running”, deep-stealth badge |
| Red | `#f26d6d` | danger, errors |
| Yellow | `#e0b341` | warnings, “checking” |

### Neutrals (dark theme — primary)
| Token | Hex |
|---|---|
| bg | `#0b0e14` |
| panel | `#151a23` |
| panel-2 | `#1b2029` |
| border | `#262c38` |
| text | `#e6edf3` |
| muted | `#8b95a5` |

### Neutrals (light theme)
| Token | Hex |
|---|---|
| bg | `#f5f7fb` |
| panel | `#ffffff` |
| border | `#e2e7ef` |
| text | `#16202e` |
| muted | `#5d6b7e` |

### Signature gradient
**“Identity gradient”** = 135° linear, `#4d8dfd → #b98cff`.
Used on the logo tile, hero backgrounds, and the app icon. This is the single
most recognizable brand element — keep it consistent everywhere.

## 4. Logomark concept (the icon)

**Concept A — “Masked A” (primary, recommended).**
- Rounded-square tile (squircle, iOS-style corner radius ~22% of side).
- Fill: the identity gradient (135°, blue→violet).
- Centered white glyph: a lowercase **a** whose counter (the hole) is shaped
  like a **domino privacy mask** — or, alternatively, the negative space forms
  two mask eye-holes. One continuous, confident line. Must read at 16px.
- Soft ambient shadow under the tile on dark backgrounds.

**Concept B — “Layered identities” (alt).**
- Three overlapping rounded cards/silhouettes fanned out (like stacked profile
  cards), each a slightly different tint of the gradient, implying many
  isolated identities. Monoline, minimal.

**Concept C — “Fingerprint ring” (alt).**
- A minimal circular fingerprint-swirl where a couple of ridges break/offset,
  hinting at “spoofed”. Very subtle, geometric, not literal.

Go with **Concept A** for the app icon and favicon; B or C can be used as
secondary illustrations / social banner motifs.

## 5. Do / Don't

**Do:** flat vector, crisp edges, generous padding, one accent gradient, plenty
of negative space, rounded geometry echoing the UI's 10px radii.

**Don't:** drop shadows on the glyph itself, skeuomorphism, gradients with more
than 2 stops, matrix/green-on-black, spy/hacker cliches, emoji as a logo,
literal human faces.

## 6. Iconography (in-app)

Use a single line-icon set, 1.5px stroke, rounded caps. Recommended open sets:
**Lucide** or **Phosphor** (both MIT). Keep the current UI's emoji quick-actions
optional; prefer swapping them for Lucide equivalents:
- start → `play`, stop → `square`, fingerprint → `fingerprint`,
  proxy check → `zap`, delete → `trash-2`, theme → `sun`/`moon`,
  import → `download`, new → `plus`.

## 7. Typography scale (web/UI)

- Font: Inter (UI), JetBrains Mono / SF Mono (code + IDs).
- Sizes: 24/700 stat numbers, 17/700 modal titles, 14/400 body, 12/600 table
  headers (uppercase, +0.6px tracking), 11 mono for IDs.

## 8. Voice (for copy on the site / README hero)

Short, confident, technical. “Isolated profiles. Real fingerprints. Your
machine.” Avoid hype words (“revolutionary”, “next-gen”). State capabilities
plainly.
