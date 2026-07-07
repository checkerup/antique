"""Proxy configuration parsing & validation.

AdsPower stores proxy config in a dict like:

    {
      "proxy_type": "http" | "https" | "socks5",
      "proxy_host": "1.2.3.4",
      "proxy_port": 8080,
      "proxy_user": "user",     # optional
      "proxy_password": "pass"  # optional
    }

We convert it to Playwright's ``proxy`` shape:

    {
      "server": "http://1.2.3.4:8080",
      "username": "...",  # only if provided
      "password": "..."   # only if provided
    }

Also supports ``"direct"`` (no proxy) and the special ``"system"`` (use OS proxy).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional


VALID_TYPES = {"http", "https", "socks5", "direct", "system"}


@dataclass
class ProxyConfig:
    type: str = "direct"  # http|https|socks5|direct|system
    host: str = ""
    port: int = 0
    username: str = ""
    password: str = ""

    def to_playwright(self) -> Optional[Dict[str, Any]]:
        """Return kwargs for ``playwright.chromium.launch(proxy=...)`` or ``None``."""
        if self.type in ("direct", "system"):
            return None
        if not self.host or not self.port:
            raise ValueError("Proxy host and port required for non-direct proxy")
        server = f"{self.type}://{self.host}:{self.port}"
        out: Dict[str, Any] = {"server": server}
        if self.username:
            out["username"] = self.username
        if self.password:
            out["password"] = self.password
        return out


def parse_proxy(d: Optional[Dict[str, Any]]) -> ProxyConfig:
    """Build ``ProxyConfig`` from AdsPower-style dict."""
    if not d:
        return ProxyConfig()
    t = (d.get("proxy_type") or d.get("type") or "direct").lower()
    if t not in VALID_TYPES:
        raise ValueError(f"Invalid proxy_type: {t!r}; must be one of {VALID_TYPES}")
    return ProxyConfig(
        type=t,
        host=d.get("proxy_host") or d.get("host") or "",
        port=int(d.get("proxy_port") or d.get("port") or 0),
        username=d.get("proxy_user") or d.get("username") or "",
        password=d.get("proxy_password") or d.get("password") or "",
    )


def adspower_shape(cfg: ProxyConfig) -> Dict[str, Any]:
    """Return the AdsPower dict shape for a ProxyConfig (for export)."""
    return {
        "proxy_type": cfg.type,
        "proxy_host": cfg.host,
        "proxy_port": cfg.port,
        "proxy_user": cfg.username,
        "proxy_password": cfg.password,
    }


async def check_proxy(cfg: ProxyConfig, timeout: float = 10.0) -> Dict[str, Any]:
    """Check proxy connectivity and return IP + latency.

    Makes a request to httpbin.org/ip through the proxy and measures
    response time. Returns a dict with status, ip, latency_ms, and error.
    """
    import asyncio
    import time

    if cfg.type in ("direct", "system") or not cfg.host or not cfg.port:
        return {
            "status": "skip",
            "ip": None,
            "latency_ms": None,
            "error": "No proxy configured (direct connection)",
        }

    proxy_url = f"{cfg.type}://{cfg.host}:{cfg.port}"
    if cfg.username and cfg.password:
        proxy_url = f"{cfg.type}://{cfg.username}:{cfg.password}@{cfg.host}:{cfg.port}"

    if cfg.type.startswith("socks"):
        import subprocess
        import json as _json
        start = time.monotonic()
        try:
            socks_proxy_url = proxy_url.replace("socks5://", "socks5h://")
            result = subprocess.run(
                ["curl", "-s", "--max-time", str(int(timeout)),
                 "--proxy", socks_proxy_url, "http://httpbin.org/ip"],
                capture_output=True, text=True, timeout=timeout + 2,
            )
            elapsed = (time.monotonic() - start) * 1000
            if result.returncode == 0:
                data = _json.loads(result.stdout)
                return {
                    "status": "ok",
                    "ip": data.get("origin", "unknown"),
                    "latency_ms": round(elapsed, 1),
                    "error": None,
                }
            return {
                "status": "error",
                "ip": None,
                "latency_ms": round(elapsed, 1),
                "error": result.stderr.strip() or f"exit code {result.returncode}",
            }
        except Exception as e:
            elapsed = (time.monotonic() - start) * 1000
            return {
                "status": "error",
                "ip": None,
                "latency_ms": round(elapsed, 1),
                "error": str(e),
            }

    try:
        import aiohttp

        start = time.monotonic()
        connector = aiohttp.TCPConnector(ssl=False)
        async with aiohttp.ClientSession(connector=connector) as session:
            async with session.get(
                "http://httpbin.org/ip",
                proxy=proxy_url,
                timeout=aiohttp.ClientTimeout(total=timeout),
            ) as resp:
                elapsed = (time.monotonic() - start) * 1000
                if resp.status == 200:
                    data = await resp.json()
                    return {
                        "status": "ok",
                        "ip": data.get("origin", "unknown"),
                        "latency_ms": round(elapsed, 1),
                        "error": None,
                    }
                return {
                    "status": "error",
                    "ip": None,
                    "latency_ms": round(elapsed, 1),
                    "error": f"HTTP {resp.status}",
                }
    except ImportError:
        import subprocess
        import json as _json

        start = time.monotonic()
        try:
            result = subprocess.run(
                ["curl", "-s", "--max-time", str(int(timeout)),
                 "--proxy", proxy_url, "http://httpbin.org/ip"],
                capture_output=True, text=True, timeout=timeout + 2,
            )
            elapsed = (time.monotonic() - start) * 1000
            if result.returncode == 0:
                data = _json.loads(result.stdout)
                return {
                    "status": "ok",
                    "ip": data.get("origin", "unknown"),
                    "latency_ms": round(elapsed, 1),
                    "error": None,
                }
            return {
                "status": "error",
                "ip": None,
                "latency_ms": round(elapsed, 1),
                "error": result.stderr or f"exit code {result.returncode}",
            }
        except Exception as e:
            elapsed = (time.monotonic() - start) * 1000
            return {
                "status": "error",
                "ip": None,
                "latency_ms": round(elapsed, 1),
                "error": str(e),
            }
    except asyncio.TimeoutError:
        return {
            "status": "timeout",
            "ip": None,
            "latency_ms": timeout * 1000,
            "error": f"Timeout after {timeout}s",
        }
    except Exception as e:
        return {
            "status": "error",
            "ip": None,
            "latency_ms": None,
            "error": str(e),
        }


def parse_proxy_list(text: str) -> list[ProxyConfig]:
    """Parse a bulk proxy list (one per line).

    Supported formats:
      - type://host:port
      - type://user:pass@host:port
      - host:port:user:pass (assumes http)
      - host:port (assumes http, no auth)
    """
    configs: list[ProxyConfig] = []
    for line in text.strip().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "://" in line:
            # URL format: type://[user:pass@]host:port
            scheme, rest = line.split("://", 1)
            user, password = "", ""
            if "@" in rest:
                auth, hostport = rest.rsplit("@", 1)
                if ":" in auth:
                    user, password = auth.split(":", 1)
                else:
                    user = auth
            else:
                hostport = rest
            parts = hostport.rsplit(":", 1)
            host = parts[0]
            port = int(parts[1]) if len(parts) > 1 else 0
            configs.append(ProxyConfig(
                type=scheme, host=host, port=port,
                username=user, password=password,
            ))
        else:
            # host:port or host:port:user:pass
            parts = line.split(":")
            if len(parts) == 2:
                configs.append(ProxyConfig(
                    type="http", host=parts[0], port=int(parts[1]),
                ))
            elif len(parts) == 4:
                configs.append(ProxyConfig(
                    type="http", host=parts[0], port=int(parts[1]),
                    username=parts[2], password=parts[3],
                ))
            elif len(parts) == 5:
                # type:host:port:user:pass
                configs.append(ProxyConfig(
                    type=parts[0], host=parts[1], port=int(parts[2]),
                    username=parts[3], password=parts[4],
                ))
    return configs