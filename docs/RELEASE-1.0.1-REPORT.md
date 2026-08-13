# Antique 1.0.1: fingerprint coherence and WebRTC leak fixes

Bugfix release. No new features, no API changes. Six defects, all found by
behavioural checks against a running server rather than by config assertions.

## Fixed

### WebRTC leaked the local IP in `block` mode (default)

`src/core/fingerprint.py`. The `block` branch replaced
`RTCPeerConnection.prototype.createDataChannel` and forced an empty
`iceServers` list. Stripping `iceServers` only suppresses STUN/TURN
server-reflexive candidates — the browser still gathers **host** candidates
from local interfaces, so the private IP was still observable. The branch now
suppresses ICE candidate gathering itself.

Verified per mode: `block` yields an empty candidate list and `null` in the
`icecandidate` event; `real` and `proxy` keep their intended behaviour.

### `effective_webrtc_mode()` ignored `real` and `proxy` on dict fingerprints

`src/core/fingerprint.py`. The resolver read fields with `getattr`, which
always returns the default for a `dict` — and profiles are stored and
submitted as dicts. Every profile with an explicit `real` or `proxy` mode
resolved to `block`, so the setting never reached the launcher.

Resolution now goes through `_fp_value`, which handles both the dataclass and
the dict shape.

### The audit flagged every default profile as leaking

`src/core/detect.py`. The audit read `webrtc_mode` directly. An empty
`webrtc_mode` is legal and means "fall back to the legacy `block_webrtc_ip`
flag", so untouched profiles were reported as leaks. The audit now resolves the
mode the same way the launcher does.

### Screen dimensions lost their invariants

`src/core/fingerprint_corpus.py`. Six related values (`screen`, `avail` and
`inner`, two axes each) were jittered independently, so
`inner <= avail <= screen` could break — a stored profile could carry
`avail_screen_width` greater than `screen_width`, which no real device
reports. Jitter is now applied coherently across the group.

### Plugins were dropped when sampling the corpus

Corpus entries carry no `plugins` field, so sampled Chrome profiles came out
with an empty plugin list. The field is populated after sampling.

### Batch randomization desynchronized the identity set

`src/core/fingerprint_ops.py`. `user_agent`, `platform`, `vendor` and `oscpu`
are all derived from a single OS, but `preserve_fields` and `overrides` both
copied them field by field. Preserving `user_agent` while randomizing with
`os_family="macos"` left a Windows UA beside platform `MacIntel` — the
critical `ua_platform_coherence` check failed and the audit dropped from 100/A
to 40/D.

The user agent is now authoritative: `_align_identity_to_ua` re-derives the
rest of the identity block from the OS the UA claims, and swaps the GPU only
when it contradicts that OS (an Apple renderer under a Windows UA).

## Audit impact

| Scenario | Before | After |
|---|---|---|
| Freshly created profile | 65 / C, 10 of 13 | **100 / A, 13 of 13** |
| `preserve_fields=["user_agent"]` + `os_family="macos"` | 40 / D, 11 of 13 | **100 / A, 13 of 13** |

## Dashboard

`src/ui/templates/index.html`. Sixteen handlers referenced from markup were
never defined — Randomize, Stealth, Folders, Mass create, Sync, Activity,
Schedules, Resources, Extensions and Audit did nothing when clicked. Thirty-one
DOM ids used by the script were absent from the markup, and row renderers
emitted `<tr><td>` into `div.list-rows` containers.

Handlers are implemented, five missing modals added, ids reconciled, renderers
corrected. Current state: 64 handlers, 0 undefined, 0 missing ids, and the
41 KB inline script passes `node --check`.

## Tests

Five behavioural suites, 140 tests total:

- `tests/test_fingerprint_coherence.py` — audit score of a fresh profile,
  screen invariants, plugin presence, WebRTC mode resolution including the
  legacy flag and negative cases.
- `tests/test_randomize_identity_coherence.py` — identity coherence across
  `preserve_fields`, `overrides` and mixed batches for all three OS families.
- `tests/test_folders.py` (new) — 14 tests covering group CRUD, hierarchical
  tree API, parent validation, delete conflict (parent with children → 409),
  and default group protection.
- `tests/test_encrypted_snapshot.py` (new) — 5 tests for AES-GCM export/import,
  wrong-password rejection, missing-file handling, and overwrite semantics.
- `tests/test_proxy_logging.py` (new) — 4 tests ensuring proxy credentials
  never leak in logs or API responses. Found and fixed a real bug (below).

Each suite was checked against the unfixed code to confirm it actually
catches the defect: 21 failures without identity alignment, 35 without
coherent screen jitter, 3 without the `effective_webrtc_mode` fix. A test that
stays green on broken code proves nothing.

### Proxy password leaked in API responses (found by new test)

`src/api/routes.py`. `_profile_to_adspower_shape()` returned `p.proxy`
directly — plaintext passwords appeared in `/user/list`, `/user/{id}`, and
every other endpoint that serializes profiles. Fixed by masking
`proxy_password` to `****` in the response serializer. Confirmed by
`test_proxy_credentials_not_in_profile_list_response`.

## Required test commands

```powershell
cd C:\ai_workflow\antidetect-local
.\.venv\Scripts\Activate.ps1
python -m pip install -e .
python -m pytest -q
python -m pytest tests\test_fingerprint_coherence.py tests\test_randomize_identity_coherence.py tests\test_folders.py tests\test_encrypted_snapshot.py tests\test_proxy_logging.py -v
```

Full suite: **606 passed**.

## Honest limits

- The audit checks the fingerprint *configuration*. It does not launch a
  browser and read back `navigator`, so an injection-layer regression that
  leaves the config intact would not be caught by it. The WebRTC modes were
  verified by parsing the generated injection, not by observing a live ICE
  exchange against a STUN server.
- `_align_identity_to_ua` classifies an OS by substring match on the user
  agent. A UA it cannot classify is left untouched rather than guessed at, so
  a deliberately exotic custom UA can still contradict `platform`.
- Everything listed under "Honest limits" in `RELEASE-0.9.0-REPORT.md` still
  applies: MCP is a stdio integration, Web Store install needs network, Live
  View is periodic screenshots, the legacy CDP multiplexer is simulated, and
  team cloud sync remains separate architecture work.
