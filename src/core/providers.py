"""Provider interfaces for proxy pools, designed for local-first operation."""
from __future__ import annotations

import json
import os
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.core.outbound_guard import safe_urlopen


@dataclass
class ProviderConfig:
    name: str
    kind: str = "file"
    source: str = ""
    enabled: bool = True
    api_key: Optional[str] = None
    username: Optional[str] = None
    password: Optional[str] = None
    params: Optional[Dict[str, str]] = None


class ProxyProvider:
    """Fetch proxies from local files, JSON endpoints, or provider APIs.

    Provider adapters deliberately accept an explicit endpoint in ``source``.
    That keeps secrets out of URLs and works with self-hosted/provider-specific
    pools without hard-coding a brittle vendor endpoint.
    """

    _API_ENV = {
        "nodemaven": "NODEMAVEN_API_KEY",
        "lunaproxxy": "LUNAPROXY_API_KEY",
        "proxy-seller": "PROXY_SELLER_API_KEY",
        "proxy-cheap": "PROXY_CHEAP_API_KEY",
        "ip2world": "IP2WORLD_API_KEY",
    }

    def __init__(self, config: ProviderConfig):
        self.config = config

    def fetch(self) -> List[str]:
        if not self.config.enabled:
            return []
        if self.config.kind == "file":

            return [line.strip() for line in Path(self.config.source).read_text(encoding="utf-8").splitlines() if line.strip() and not line.startswith("#")]
        if self.config.kind == "json":
            data = json.loads(Path(self.config.source).read_text(encoding="utf-8"))
            if isinstance(data, dict):
                data = data.get("proxies", [])
            return [str(item.get("url") if isinstance(item, dict) else item) for item in data]
        if self.config.kind in {"http-json", "nodemaven", "lunaproxxy", "proxy-seller", "proxy-cheap", "ip2world"}:
            data = self._fetch_remote_json()
            return self._extract_proxy_urls(data)
        raise ValueError(f"unsupported provider kind: {self.config.kind}")

    def _fetch_remote_json(self) -> Any:
        if not self.config.source:
            raise ValueError("provider source endpoint is required")
        params = self.config.params or {}
        url = self.config.source
        if params:
            joiner = "&" if "?" in url else "?"
            url += joiner + urllib.parse.urlencode(params)
        headers = {"Accept": "application/json", "User-Agent": "antique-proxy-provider/1"}
        if self.config.kind in self._API_ENV:
            token = self.config.api_key or os.environ.get(self._API_ENV[self.config.kind])
            if not token:
                raise ValueError(f"{self.config.kind} requires api_key or {self._API_ENV[self.config.kind]}")
            headers["Authorization"] = f"Bearer {token}"
        elif self.config.api_key:
            headers["Authorization"] = f"Bearer {self.config.api_key}"
        request = urllib.request.Request(url, headers=headers)
        with safe_urlopen(request, timeout=10) as response:
            return json.loads(response.read().decode("utf-8"))

    @staticmethod
    def _extract_proxy_urls(payload: Any) -> List[str]:
        """Normalize common provider payloads into proxy URL strings."""
        if isinstance(payload, dict):
            for key in ("proxies", "data", "results", "items"):
                if key in payload:
                    return ProxyProvider._extract_proxy_urls(payload[key])
            if "url" in payload:
                return [str(payload["url"])]
            if {"host", "port"}.issubset(payload):
                scheme = payload.get("type", payload.get("protocol", "http"))
                auth = ""
                if payload.get("username"):
                    auth = str(payload["username"])
                    if payload.get("password") is not None:
                        auth += ":" + str(payload["password"])
                    auth += "@"
                return [f"{scheme}://{auth}{payload['host']}:{payload['port']}"]
            return []
        if isinstance(payload, list):
            return [item for value in payload for item in ProxyProvider._extract_proxy_urls(value)]
        if payload is None:
            return []
        return [str(payload).strip()]


def list_provider_kinds() -> List[str]:
    return [
        "file", "json", "http-json",
        "nodemaven", "lunaproxxy", "proxy-seller",
        "proxy-cheap", "ip2world",
    ]
