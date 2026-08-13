"""Event notifications: Discord / Telegram / generic webhooks.

Profiles are long-lived and unattended, so operators need to hear about
crashes, stops, and failed stealth audits without watching the dashboard.

The payload builder is a pure function so it can be unit-tested without any
network access; :func:`send_event` takes an injectable ``sender`` for the
same reason.
"""
from __future__ import annotations

import json
import urllib.request
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

KINDS = ("discord", "telegram", "generic")
EVENTS = ("profile_start", "profile_stop", "profile_crash", "proxy_fail", "detect_fail")


class WebhookError(ValueError):
    """Raised when a webhook configuration is invalid."""


@dataclass
class WebhookConfig:
    url: str = ""
    kind: str = "generic"
    enabled: bool = False
    events: List[str] = field(default_factory=lambda: list(EVENTS))
    telegram_chat_id: str = ""

    def validate(self) -> None:
        if self.kind not in KINDS:
            raise WebhookError(f"unknown webhook kind {self.kind!r}; expected one of {list(KINDS)}")
        unknown = [e for e in self.events if e not in EVENTS]
        if unknown:
            raise WebhookError(f"unknown events: {unknown}")
        if self.enabled and not self.url:
            raise WebhookError("webhook is enabled but url is empty")
        if self.enabled and self.kind == "telegram" and not self.telegram_chat_id:
            raise WebhookError("telegram webhooks need telegram_chat_id")

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def config_path(data_root: Path) -> Path:
    return Path(data_root) / "webhook.json"


def load_config(data_root: Path) -> WebhookConfig:
    path = config_path(data_root)
    if not path.exists():
        return WebhookConfig()
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return WebhookConfig()
    if not isinstance(raw, dict):
        return WebhookConfig()
    cfg = WebhookConfig(
        url=str(raw.get("url", "")),
        kind=str(raw.get("kind", "generic")),
        enabled=bool(raw.get("enabled", False)),
        events=list(raw.get("events") or EVENTS),
        telegram_chat_id=str(raw.get("telegram_chat_id", "")),
    )
    return cfg


def save_config(data_root: Path, cfg: WebhookConfig) -> WebhookConfig:
    cfg.validate()
    path = config_path(data_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(cfg.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8")
    return cfg


def format_message(event: str, data: Dict[str, Any]) -> str:
    """Human-readable one-liner for an event. Pure."""
    name = data.get("name") or data.get("user_id") or "unknown profile"
    detail = data.get("detail") or ""
    titles = {
        "profile_start": "started",
        "profile_stop": "stopped",
        "profile_crash": "CRASHED",
        "proxy_fail": "proxy failed",
        "detect_fail": "failed the stealth audit",
    }
    verb = titles.get(event, event)
    line = f"[antique] {name} {verb}"
    return f"{line}: {detail}" if detail else line


def build_payload(kind: str, event: str, data: Dict[str, Any]) -> Dict[str, Any]:
    """Build the provider-specific JSON body. Pure and unit-testable."""
    if kind not in KINDS:
        raise WebhookError(f"unknown webhook kind {kind!r}")
    message = format_message(event, data)
    if kind == "discord":
        return {"content": message}
    if kind == "telegram":
        return {"chat_id": data.get("chat_id", ""), "text": message}
    return {
        "event": event,
        "message": message,
        "data": data,
        "sent_at": datetime.utcnow().isoformat() + "Z",
    }


def _post(url: str, payload: Dict[str, Any], timeout: float = 5.0) -> int:
    body = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(url, data=body, method="POST")
    request.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return int(getattr(response, "status", 200) or 200)


def send_event(
    cfg: WebhookConfig,
    event: str,
    data: Optional[Dict[str, Any]] = None,
    *,
    sender: Optional[Callable[[str, Dict[str, Any]], int]] = None,
) -> Dict[str, Any]:
    """Deliver one event. Never raises: returns a result dict instead."""
    payload_data = dict(data or {})
    if cfg.kind == "telegram" and cfg.telegram_chat_id:
        payload_data.setdefault("chat_id", cfg.telegram_chat_id)
    if not cfg.enabled:
        return {"sent": False, "reason": "disabled", "event": event}
    if event not in cfg.events:
        return {"sent": False, "reason": "event not subscribed", "event": event}
    if not cfg.url:
        return {"sent": False, "reason": "no url", "event": event}
    payload = build_payload(cfg.kind, event, payload_data)
    post = sender or _post
    try:
        status = post(cfg.url, payload)
    except Exception as exc:  # network problems must never break a launch
        return {"sent": False, "reason": f"{type(exc).__name__}: {exc}", "event": event}
    return {"sent": True, "status": status, "event": event, "payload": payload}
