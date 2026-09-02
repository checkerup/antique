# Browser launch policies

Antique exposes an explicit launch policy through `ANTIQUE_LAUNCH_POLICY`.
A policy is a compatibility contract, not a claim that every website will
accept a browser session.

| Policy | Intended use | Trade-off |
|---|---|---|
| `google-compatible` (default) | Normal interactive Chrome sessions and Google sign-in | Removes Playwright's `--enable-automation` and `--no-sandbox` defaults; keeps web security and site isolation enabled |
| `standard` | Debugging and maximum Playwright compatibility | Keeps Playwright defaults; direct extension launches may include `--no-sandbox` |
| `stealth` | Legacy sites that key on `navigator.webdriver` / AutomationControlled | Adds `--disable-blink-features=AutomationControlled`; may be rejected by Google |

Example:

```bash
set ANTIQUE_LAUNCH_POLICY=google-compatible
antique serve --ui-port 8080
```

```bash
ANTIQUE_LAUNCH_POLICY=standard antique serve --ui-port 8080
```

Unknown names fail closed with a clear error. Site-specific behavior must be
validated by the quality lab before a release. The historical native Google
probe showed `google-compatible` reaching the normal sign-in page while the
legacy and no-CDP variants were rejected; credentials and account acceptance
remain external prerequisites.
