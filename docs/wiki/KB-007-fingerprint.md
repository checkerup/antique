# KB-007 — Fingerprint Engine

**Applies to: antique ≥ 1.0** (updated: 2026-09-04)

- Corpus-driven: shipped `fingerprint_corpus/` (must be present — CI test `test_corpus_has_entries` guards it).
- Synthesis: OS-coherent GPU (WebGL vendor/model consistent with platform UA) — fix `43b42ae`.
- Randomize: `/user/bulk/fingerprint/randomize` regenerates coherent fingerprints for selected profiles.
- Anti-detect flags: `--protected-canvasmark --protected-webglmark --protected-webglfp --disable-features=UserAgentClientHint`.
- `POST /detect-score` (alias stealth): runs the detection suite — target 100/100.
- Google auth hardening (1.1.1): flags tuned to reduce Google's "browser not secure" rejections.
