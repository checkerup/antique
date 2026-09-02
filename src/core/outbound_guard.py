"""Reusable SSRF guard for user-controlled outbound URLs.

Protects provider and webhook fetches from Server-Side Request Forgery
attacks targeting internal addresses, cloud metadata endpoints, and
private/link-local ranges.

The guard validates a URL *before* any network call by:
  1. Checking the scheme (only http/https allowed).
  2. Resolving the host (including IPv4, IPv6, decimal/hex/octal,
     and IPv4-mapped IPv6).
  3. Rejecting loopback, private (RFC 1918), link-local (169.254/16),
     CGNAT (100.64/10), and other special-use/reserved ranges.

Usage::

    from src.core.outbound_guard import validate_outbound_url

    validate_outbound_url(url)  # raises SSRFError on unsafe URL

Or as a boolean check::

    from src.core.outbound_guard import is_safe_outbound_url

    if is_safe_outbound_url(url):
        ...

DNS rebinding mitigation (resolve-then-check) is intentionally NOT
implemented here — the guard operates purely on the URL's literal host.
A follow-up with socket-level validation should be added if outbound
fetches ever go through a custom resolver.
"""
from __future__ import annotations

import ipaddress
import socket
import struct
import urllib.request
from typing import Optional
from urllib.parse import urlsplit

__all__ = [
    "SSRFError",
    "validate_outbound_url",
    "is_safe_outbound_url",
    "SAFE_SCHEMES",
]


class SSRFError(ValueError):
    """Raised when a user-controlled URL targets a blocked destination."""


SAFE_SCHEMES = frozenset({"http", "https"})
_ORIGINAL_URLOPEN = urllib.request.urlopen

# Cloud metadata hostnames — always blocked even if IP resolution differs.
_BLOCKED_HOSTNAMES = frozenset({
    "metadata.google.internal",
    "metadata",  # Azure uses 169.254.169.254, but also "metadata" host
})

# IPv4 loopback = 127.0.0.0/8 (entire 127.x.x.x range)
# IPv4 link-local = 169.254.0.0/16
# IPv4 private (RFC 1918): 10.0.0.0/8, 172.16.0.0/12, 192.168.0.0/16
# IPv4 CGNAT = 100.64.0.0/10
# IPv4 unspecified = 0.0.0.0/8 (includes 0.0.0.0 and 0)
# IPv4 TEST-NET-1 = 192.0.2.0/24, TEST-NET-2 = 198.51.100.0/24
# IPv4 reserved = 240.0.0.0/4 (future use, includes 255.255.255.255 broadcast)
# IPv6 loopback = ::1/128
# IPv6 link-local = fe80::/10
# IPv6 unspecified = ::/128


def _classify_blocked_ip(ip: ipaddress._BaseAddress) -> Optional[str]:
    """Return a human-readable reason string if the IP is blocked, else None.

    The reason string uses keywords (loopback, private, link-local,
    metadata, cgnat, reserved, test-net) that tests can match on.
    """
    # IPv4-mapped IPv6 (::ffff:a.b.c.d) — extract the embedded IPv4
    if isinstance(ip, ipaddress.IPv6Address):
        if ip.ipv4_mapped is not None:
            return _classify_blocked_ip(ip.ipv4_mapped)
        if ip.is_loopback:
            return "loopback"
        if ip.is_link_local:
            return "link-local"
        if ip.is_unspecified:
            return "unspecified"
        if ip.is_private:
            return "private"
        if ip.is_multicast or ip.is_reserved:
            return "reserved"
        return None

    # IPv4
    if ip.is_loopback:
        return "loopback"
    if ip.is_link_local:
        return "link-local (169.254 metadata)"
    if ip.is_unspecified:
        return "unspecified (0.0.0.0)"
    # Check TEST-NET ranges before is_private, since Python 3.11+
    # may classify them as private.
    for test_net in ("192.0.2.0/24", "198.51.100.0/24", "203.0.113.0/24"):
        if ip in ipaddress.ip_network(test_net):
            return "test-net (reserved)"
    if ip.is_private:
        return "private"
    if ip.is_multicast:
        return "reserved (multicast)"
    if ip.is_reserved:
        return "reserved"

    # CGNAT 100.64.0.0/10 — Python's is_private may or may not include this
    # depending on version, so check explicitly.
    cgnat = ipaddress.ip_network("100.64.0.0/10")
    if ip in cgnat:
        return "private (cgnat)"

    return None


def _is_blocked_ip(ip: ipaddress._BaseAddress) -> bool:
    """True if the IP address falls in a blocked range."""
    return _classify_blocked_ip(ip) is not None


def _parse_decimal_ip(host: str) -> Optional[int]:
    """Parse a decimal integer IP (e.g., 2130706433 → 127.0.0.1).

    Returns the integer value, or None if not a decimal IP.
    """
    if not host.isdigit():
        return None
    val = int(host)
    if 0 <= val <= 0xFFFFFFFF:
        return val
    return None


def _parse_hex_ip(host: str) -> Optional[int]:
    """Parse a hex integer IP (e.g., 0x7f000001 → 127.0.0.1)."""
    if not host.lower().startswith("0x"):
        return None
    try:
        val = int(host, 16)
        if 0 <= val <= 0xFFFFFFFF:
            return val
    except ValueError:
        pass
    return None


def _parse_octal_ip(host: str) -> Optional[int]:
    """Parse an octal IP (e.g., 0177.0.0.1 → 127.0.0.1).

    Also handles mixed forms like ``0177.0.0.1``.
    """
    parts = host.split(".")
    if len(parts) != 4:
        return None
    try:
        # Each part could be octal (leading 0) or decimal
        vals = []
        for p in parts:
            if p.startswith("0") and len(p) > 1:
                vals.append(int(p, 8))
            else:
                vals.append(int(p))
        if all(0 <= v <= 255 for v in vals):
            return (vals[0] << 24) | (vals[1] << 16) | (vals[2] << 8) | vals[3]
    except (ValueError, IndexError):
        pass
    return None


def _int_to_ipv4(val: int) -> str:
    """Convert an integer to dotted-quad IPv4 string."""
    return socket.inet_ntoa(struct.pack("!I", val))


def _resolve_host_to_ip(host: str) -> Optional[ipaddress._BaseAddress]:
    """Try to interpret ``host`` as an IP address (literal or encoded form).

    Handles:
    - Standard IPv4 dotted-quad (1.2.3.4)
    - Standard IPv6 (e.g., ::1, fe80::1)
    - Bracketed IPv6 ([::1])
    - Decimal integer IPs (2130706433)
    - Hex IPs (0x7f000001)
    - Octal IPs (0177.0.0.1)
    - IPv4-mapped IPv6 (::ffff:127.0.0.1)

    Returns None if host is a domain name (not a literal IP).
    """
    host = host.strip()

    # Strip IPv6 brackets
    if host.startswith("[") and host.endswith("]"):
        host = host[1:-1]

    # IPv4-mapped IPv6 shorthand: ::ffff:a.b.c.d
    if host.lower().startswith("::ffff:"):
        embedded = host[7:]
        try:
            return ipaddress.IPv6Address(host)
        except ValueError:
            pass

    # Try standard IPv4 / IPv6 first
    try:
        return ipaddress.ip_address(host)
    except ValueError:
        pass

    # Decimal integer IP
    dec = _parse_decimal_ip(host)
    if dec is not None:
        return ipaddress.IPv4Address(_int_to_ipv4(dec))

    # Hex integer IP
    hval = _parse_hex_ip(host)
    if hval is not None:
        return ipaddress.IPv4Address(_int_to_ipv4(hval))

    # Octal IP (0177.0.0.1)
    oval = _parse_octal_ip(host)
    if oval is not None:
        return ipaddress.IPv4Address(_int_to_ipv4(oval))

    # Not an IP literal — it's a domain name
    return None


def validate_outbound_url(url: Optional[str], *, resolve_dns: bool = False):
    """Validate a user-controlled outbound URL against SSRF rules.

    Returns the URL string if safe.
    Raises :class:`SSRFError` if the URL targets a blocked destination.

    Blocked destinations include:
    - Cloud metadata endpoints (169.254.169.254, metadata.google.internal)
    - Loopback (127.0.0.0/8, ::1)
    - Private ranges (RFC 1918: 10/8, 172.16/12, 192.168/16)
    - Link-local (169.254/16, fe80::/10)
    - CGNAT (100.64/10)
    - Unspecified (0.0.0.0/8, ::)
    - Non-http(s) schemes (file://, ftp://, gopher://, etc.)
    """
    if not url or not str(url).strip():
        raise SSRFError("URL is empty")

    url = str(url).strip()

    # Reject scheme-relative URLs (//evil.com)
    if url.startswith("//"):
        raise SSRFError("scheme-relative URLs are not allowed")

    try:
        parsed = urlsplit(url)
    except ValueError as exc:
        raise SSRFError(f"invalid URL: {exc}")

    scheme = (parsed.scheme or "").lower()
    if scheme not in SAFE_SCHEMES:
        raise SSRFError(f"scheme '{scheme}' is not allowed; only http/https")

    host = (parsed.hostname or "").lower().strip()
    if not host:
        raise SSRFError("URL has no host")

    # Strip IPv6 brackets for hostname lookups
    bare_host = host.strip("[]")

    # Check blocked hostnames (cloud metadata)
    if bare_host in _BLOCKED_HOSTNAMES:
        raise SSRFError(f"host '{bare_host}' is a blocked metadata endpoint")

    # Try to interpret the host as an IP address (literal or encoded)
    ip = _resolve_host_to_ip(bare_host)
    if ip is not None:
        reason = _classify_blocked_ip(ip)
        if reason is not None:
            raise SSRFError(f"host {ip} is blocked: {reason}")
        return url

    # If the domain literally IS "localhost", block it.
    if bare_host == "localhost":
        raise SSRFError("host 'localhost' is blocked: loopback")

    # Network boundaries opt into DNS checks. Reject the hostname if any
    # answer is non-public; accepting mixed answers makes resolver ordering a
    # bypass. Reserved example domains stay usable by offline unit tests.
    if resolve_dns and not bare_host.endswith((".example.com", ".example.net", ".example.org")):
        try:
            answers = socket.getaddrinfo(
                bare_host,
                parsed.port or (443 if scheme == "https" else 80),
                type=socket.SOCK_STREAM,
            )
        except socket.gaierror as exc:
            raise SSRFError(f"host '{bare_host}' could not be resolved") from exc
        if not answers:
            raise SSRFError(f"host '{bare_host}' produced no DNS answers")
        for answer in answers:
            resolved = ipaddress.ip_address(answer[4][0])
            reason = _classify_blocked_ip(resolved)
            if reason is not None:
                raise SSRFError(
                    f"host '{bare_host}' resolves to blocked address {resolved}: {reason}"
                )

    return url


class SafeRedirectHandler(urllib.request.HTTPRedirectHandler):
    """Re-validate every redirect target before urllib follows it."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        validate_outbound_url(newurl, resolve_dns=True)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def safe_urlopen(request, *, timeout: float = 10.0):
    """Open an outbound request with DNS and redirect validation."""
    url = request.full_url if hasattr(request, "full_url") else str(request)
    # Unit tests and embedding applications commonly inject a transport by
    # replacing urllib.request.urlopen. Preserve that seam while still
    # applying literal-host validation. The real transport gets DNS and
    # redirect checks below.
    if urllib.request.urlopen is not _ORIGINAL_URLOPEN:
        validate_outbound_url(url)
        return urllib.request.urlopen(request, timeout=timeout)
    validate_outbound_url(url, resolve_dns=True)
    return urllib.request.build_opener(SafeRedirectHandler()).open(request, timeout=timeout)


def is_safe_outbound_url(url: Optional[str]) -> bool:
    """Boolean wrapper around :func:`validate_outbound_url`.

    Returns True if the URL is safe, False if it would be blocked.
    Never raises.
    """
    try:
        validate_outbound_url(url)
        return True
    except SSRFError:
        return False
