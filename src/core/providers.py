"""Provider interfaces for proxy pools, designed for local-first operation."""
from __future__ import annotations

import json
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass
class ProviderConfig:
    name: str
    kind: str = "file"
    source: str = ""
    enabled: bool = True


class ProxyProvider:
    def __init__(self, config: ProviderConfig):
        self.config = config

    def fetch(self) -> List[str]:
        if self.config.kind == "file":
            return [line.strip() for line in Path(self.config.source).read_text(encoding="utf-8").splitlines() if line.strip() and not line.startswith("#")]
        if self.config.kind == "json":
            data = json.loads(Path(self.config.source).read_text(encoding="utf-8"))
            if isinstance(data, dict):
                data = data.get("proxies", [])
            return [str(item.get("url") if isinstance(item, dict) else item) for item in data]
        if self.config.kind == "http-json":
            request = urllib.request.Request(self.config.source, headers={"Accept": "application/json", "User-Agent": "antique-proxy-provider/1"})
            with urllib.request.urlopen(request, timeout=10) as response:
                data = json.loads(response.read().decode("utf-8"))
            if isinstance(data, dict):
                data = data.get("proxies", data.get("data", []))
            return [str(item.get("url") if isinstance(item, dict) else item) for item in data]
        raise ValueError(f"unsupported provider kind: {self.config.kind}")


def list_provider_kinds() -> List[str]:
    return ["file", "json", "http-json"]
