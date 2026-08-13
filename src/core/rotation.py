"""Timer-based proxy rotation schedules.

Long-running profiles accumulate IP age, so operators want "rotate this pool
every N minutes" instead of clicking rotate by hand. Schedules are persisted
as JSON next to the database; the due calculation is a pure function so the
whole feature is unit-testable without sleeping or spawning tasks.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

MIN_INTERVAL_MIN = 1
MAX_INTERVAL_MIN = 24 * 60


class RotationScheduleError(ValueError):
    """Raised for invalid rotation schedule input."""


@dataclass
class RotationSchedule:
    pool_id: str
    interval_min: int
    enabled: bool = True
    last_run_at: Optional[str] = None

    def validate(self) -> None:
        if not self.pool_id:
            raise RotationScheduleError("pool_id is required")
        if not isinstance(self.interval_min, int) or isinstance(self.interval_min, bool):
            raise RotationScheduleError("interval_min must be an integer")
        if not (MIN_INTERVAL_MIN <= self.interval_min <= MAX_INTERVAL_MIN):
            raise RotationScheduleError(
                f"interval_min must be between {MIN_INTERVAL_MIN} and {MAX_INTERVAL_MIN}"
            )

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def schedules_path(data_root: Path) -> Path:
    return Path(data_root) / "proxy_rotation.json"


def load_schedules(data_root: Path) -> List[RotationSchedule]:
    path = schedules_path(data_root)
    if not path.exists():
        return []
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    out: List[RotationSchedule] = []
    for item in raw if isinstance(raw, list) else []:
        if not isinstance(item, dict) or not item.get("pool_id"):
            continue
        out.append(
            RotationSchedule(
                pool_id=str(item.get("pool_id")),
                interval_min=int(item.get("interval_min") or MIN_INTERVAL_MIN),
                enabled=bool(item.get("enabled", True)),
                last_run_at=item.get("last_run_at"),
            )
        )
    return out


def save_schedules(data_root: Path, schedules: List[RotationSchedule]) -> List[RotationSchedule]:
    path = schedules_path(data_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps([s.to_dict() for s in schedules], indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return schedules


def upsert_schedule(data_root: Path, schedule: RotationSchedule) -> List[RotationSchedule]:
    schedule.validate()
    schedules = [s for s in load_schedules(data_root) if s.pool_id != schedule.pool_id]
    schedules.append(schedule)
    return save_schedules(data_root, schedules)


def remove_schedule(data_root: Path, pool_id: str) -> bool:
    schedules = load_schedules(data_root)
    kept = [s for s in schedules if s.pool_id != pool_id]
    if len(kept) == len(schedules):
        return False
    save_schedules(data_root, kept)
    return True


def next_run_at(schedule: RotationSchedule) -> Optional[datetime]:
    """When this schedule is next due. ``None`` means "due immediately"."""
    if not schedule.last_run_at:
        return None
    try:
        last = datetime.fromisoformat(str(schedule.last_run_at).replace("Z", "+00:00"))
    except ValueError:
        return None
    last = last.replace(tzinfo=None) if last.tzinfo else last
    return last + timedelta(minutes=schedule.interval_min)


def is_due(schedule: RotationSchedule, now: Optional[datetime] = None) -> bool:
    """Pure: has this schedule reached its next rotation moment?"""
    if not schedule.enabled:
        return False
    moment = now or datetime.utcnow()
    upcoming = next_run_at(schedule)
    return upcoming is None or upcoming <= moment


def due_schedules(schedules: List[RotationSchedule], now: Optional[datetime] = None) -> List[RotationSchedule]:
    """Pure: subset of schedules that should rotate right now."""
    return [s for s in schedules if is_due(s, now)]


def mark_ran(data_root: Path, pool_id: str, when: Optional[datetime] = None) -> Optional[RotationSchedule]:
    stamp = (when or datetime.utcnow()).isoformat()
    schedules = load_schedules(data_root)
    found = None
    for schedule in schedules:
        if schedule.pool_id == pool_id:
            schedule.last_run_at = stamp
            found = schedule
    if found is not None:
        save_schedules(data_root, schedules)
    return found
