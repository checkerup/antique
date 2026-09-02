"""Security primitives for deployment-mode-aware authentication and
origin validation.

This module provides:

- ``DeploymentMode`` — an enum of the three explicit deployment modes
  (local, lan, remote) that control how strict the auth layer is.
- ``validate_deployment_mode`` — resolves an env-var or CLI string into
  a ``DeploymentMode``, raising on unknown values.
- ``is_loopback_host`` — exact host comparison (no substring bypass).
- ``is_origin_allowed`` — exact URL origin validation that parses the
  Origin header with ``urllib.parse`` and compares the host exactly.
- ``parse_allowed_origins`` — parses the comma-separated
  ``ANTIQUE_ALLOWED_ORIGINS`` env var into a clean list.
- ``generate_api_token`` — generates a cryptographically-secure URL-safe
  token suitable for use as ``ANTIQUE_API_TOKEN``.

The old ``is_local_origin`` in ``server.py`` used ``in`` (substring)
checks: ``"://localhost" in origin``.  That allowed
``http://localhost.evil.com`` to bypass the guard.  This module replaces
it with exact host extraction and comparison.
"""
from __future__ import annotations

import enum
import os
import secrets
from typing import Optional
from urllib.parse import urlsplit


class DeploymentMode(enum.Enum):
    """Three explicit deployment modes with different security postures.

    - ``LOCAL``  — loopback only, no token required, /json & /devtools
      exempt, CORS allows ``*``.  This is the default and preserves the
      existing developer-friendly behavior.
    - ``LAN``    — binds 0.0.0.0 for trusted-network access.  /json &
      /devtools stay exempt (local tooling), token is optional, CORS
      is restricted to the allowlist.
    - ``REMOTE`` — for tunnel/remote exposure.  Token is mandatory,
      /json & /devtools require auth, CORS is restrictive, and only
      allowlisted origins pass.
    """

    LOCAL = "local"
    LAN = "lan"
    REMOTE = "remote"


# Hosts that are considered loopback / safe for local mode.
# Note: "0.0.0.0" is NOT here — it binds to all interfaces, not loopback.
_LOOPBACK_HOSTS = frozenset({"127.0.0.1", "localhost", "::1"})


def validate_deployment_mode(value: Optional[str]) -> DeploymentMode:
    """Resolve a deployment-mode string (from env var or CLI) into a
    ``DeploymentMode``.

    If ``value`` is ``None``, falls back to the ``ANTIQUE_DEPLOY_MODE``
    environment variable, then defaults to ``LOCAL``.

    Raises ``ValueError`` for unrecognised values so the operator gets
    a clear error at startup rather than a silently-permissive default.
    """
    if value is None:
        value = os.environ.get("ANTIQUE_DEPLOY_MODE", "local")
    if not value:
        value = "local"
    try:
        return DeploymentMode(value.lower().strip())
    except ValueError:
        raise ValueError(
            f"Invalid deployment mode '{value}'. "
            f"Valid options: {', '.join(m.value for m in DeploymentMode)}"
        )


def is_loopback_host(host: str) -> bool:
    """True if *host* is exactly a loopback address.

    This is an **exact** comparison — ``localhost.evil.com`` is NOT
    ``localhost``.  The old substring-based check (``"://localhost" in
    origin``) was vulnerable to that bypass.
    """
    if not host:
        return False
    # Strip brackets from IPv6 literal ([::1] → ::1)
    h = host.strip().strip("[]").lower()
    return h in _LOOPBACK_HOSTS


def is_origin_allowed(
    origin: str,
    allowed_origins: Optional[list] = None,
) -> bool:
    """True if an Origin/Referer header is from localhost or is in the
    explicit allowlist.

    **Exact URL origin validation** — no substring matching.  The origin
    is parsed with ``urllib.parse.urlsplit`` and the *host* is compared
    exactly against the set of loopback hosts and against each entry in
    ``allowed_origins`` (also parsed to host+scheme for full-origin
    comparison).

    - Empty origin (curl, scripts) → allowed.
    - ``http://127.0.0.1:8080`` → allowed (loopback host).
    - ``http://localhost.evil.com`` → blocked (host is
      ``localhost.evil.com``, not ``localhost``).
    - ``https://abc123.ngrok-free.app`` → allowed only if that exact
      origin is in ``allowed_origins``.
    """
    if not origin:
        return True  # non-browser clients (curl, scripts) send no Origin

    try:
        parsed = urlsplit(origin.lower().strip())
    except ValueError:
        return False

    host = parsed.hostname or ""
    if is_loopback_host(host):
        return True

    # Check the allowlist with exact origin matching.
    for entry in (allowed_origins or []):
        e = str(entry).strip()
        if not e:
            continue
        try:
            allowed_parsed = urlsplit(e.lower())
        except ValueError:
            continue
        # Exact match: scheme + host + port must all agree.
        if (
            parsed.scheme == allowed_parsed.scheme
            and (parsed.hostname or "") == (allowed_parsed.hostname or "")
            and (parsed.port or default_port(parsed.scheme))
            == (allowed_parsed.port or default_port(allowed_parsed.scheme))
        ):
            return True

    return False


def default_port(scheme: str) -> int:
    """Default port for a URL scheme (for normalising origin comparison)."""
    return 443 if scheme == "https" else 80


def parse_allowed_origins(raw: str) -> list[str]:
    """Parse the ``ANTIQUE_ALLOWED_ORIGINS`` env var into a clean list.

    Comma-separated, whitespace stripped, empty entries dropped.
    """
    if not raw:
        return []
    return [o.strip() for o in raw.split(",") if o.strip()]


def generate_api_token() -> str:
    """Generate a cryptographically-secure URL-safe API token.

    Uses ``secrets.token_urlsafe(32)`` which yields ~43 characters of
    entropy from 256 bits of random data — sufficient for bearer-token
    authentication.
    """
    return secrets.token_urlsafe(32)
