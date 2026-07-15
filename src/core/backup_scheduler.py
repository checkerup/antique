"""Local backup schedule registry.

The service stays local-first: schedules are persisted as JSON and can be
triggered by a Windows Task Scheduler/cron job or the API run endpoint. This
avoids a hidden daemon while still providing a repeatable backup workflow.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List

from .operations import encrypted_snapshot
from .profile import ProfileStore


@dataclass
class BackupSchedule:
    schedule_id: str
    destination: str
    interval_minutes: int = 1440
    enabled: bool = True
    next_run_at: str = ""
    last_run_at: str = ""


def _path(store: ProfileStore) -> Path:
    return Path(store.engine.url.database).parent / "backup-schedules.json"


def list_schedules(store: ProfileStore) -> List[BackupSchedule]:
    path = _path(store)
    if not path.exists(): return []
    return [BackupSchedule(**x) for x in json.loads(path.read_text(encoding="utf-8"))]


def save_schedules(store: ProfileStore, schedules: List[BackupSchedule]) -> None:
    path = _path(store); path.write_text(json.dumps([asdict(x) for x in schedules], indent=2), encoding="utf-8")


def add_schedule(store: ProfileStore, destination: str, interval_minutes: int = 1440) -> BackupSchedule:
    if interval_minutes < 5: raise ValueError("interval_minutes must be at least 5")
    now = datetime.utcnow()
    item = BackupSchedule(f"backup-{int(now.timestamp())}", destination, interval_minutes, True, (now + timedelta(minutes=interval_minutes)).isoformat(), "")
    schedules = list_schedules(store); schedules.append(item); save_schedules(store, schedules); return item


def run_schedule(store: ProfileStore, schedule_id: str, password: str) -> Dict[str, Any]:
    schedules = list_schedules(store)
    item = next((x for x in schedules if x.schedule_id == schedule_id), None)
    if item is None: raise KeyError(schedule_id)
    encrypted_snapshot(store, Path(item.destination), password)
    now = datetime.utcnow(); item.last_run_at = now.isoformat(); item.next_run_at = (now + timedelta(minutes=item.interval_minutes)).isoformat(); save_schedules(store, schedules)
    return asdict(item)
