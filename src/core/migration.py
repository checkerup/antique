"""Per-profile migration state machine.

Tracks each profile's progress through the migration pipeline from an
AdsPower backup import to full launch/site verification. State is persisted
in SQLite (``migration_state`` table) so it survives process restarts.

Lifecycle::

    discovered → metadata_imported → storage_copied →
    extensions_remapped → launch_verified → site_verified

Any step may transition to ``failed``; from ``failed`` you can retry back
to any prior state (the pipeline picks up where it left off).

The module also provides source/cookie/storage/extension validation that
**does not launch external sites** — site verification is an explicit opt-in
step the caller must request separately.
"""
from __future__ import annotations

import enum
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from sqlmodel import Session, select

from .backup_import import (
    _cookie_json_path,
    _profile_dir,
    load_adspower_profiles_index,
    prepare_backup_profile_payload,
)
from .cookie import import_adspower_profile, import_cookies_json, find_profile_default_dir
from .storage import MigrationRecord


class MigrationStatus(enum.Enum):
    """All valid migration states, in pipeline order."""

    DISCOVERED = "discovered"
    METADATA_IMPORTED = "metadata_imported"
    STORAGE_COPIED = "storage_copied"
    EXTENSIONS_REMAPPED = "extensions_remapped"
    LAUNCH_VERIFIED = "launch_verified"
    SITE_VERIFIED = "site_verified"
    FAILED = "failed"


class MigrationError(Exception):
    """Raised on invalid state transitions or persistence failures."""


# Valid transitions: current_status -> set of allowed next statuses.
VALID_TRANSITIONS: Dict[str, set] = {
    "discovered": {"metadata_imported", "failed"},
    "metadata_imported": {"storage_copied", "failed", "discovered"},
    "storage_copied": {"extensions_remapped", "failed", "metadata_imported"},
    "extensions_remapped": {"launch_verified", "failed", "storage_copied"},
    "launch_verified": {"site_verified", "failed", "extensions_remapped"},
    "site_verified": set(),  # terminal success — no transitions out
    "failed": {
        "discovered",
        "metadata_imported",
        "storage_copied",
        "extensions_remapped",
        "launch_verified",
    },
}


class MigrationManager:
    """CRUD + state-machine logic over ``MigrationRecord`` rows.

    Uses the same engine as the ``ProfileStore`` it wraps, so migration
    state and profile metadata share one SQLite database and one transaction
    boundary.
    """

    def __init__(self, store):
        """``store`` is a ``ProfileStore`` whose engine we reuse."""
        self.store = store
        self.engine = store.engine

    # ---- creation / reset ----

    def create_or_reset(self, user_id: str, *, source_path: str = "") -> MigrationRecord:
        """Create a new migration record or reset an existing one to ``discovered``.

        Idempotent: safe to call multiple times. If the record already exists
        it is reset to ``discovered`` with the new ``source_path``.
        """
        with Session(self.engine) as s:
            existing = s.get(MigrationRecord, user_id)
            now = datetime.utcnow()
            if existing is not None:
                existing.status = MigrationStatus.DISCOVERED.value
                existing.source_path = source_path
                existing.detail = "{}"
                existing.updated_at = now
                s.add(existing)
                s.commit()
                s.refresh(existing)
                return existing
            rec = MigrationRecord(
                user_id=user_id,
                status=MigrationStatus.DISCOVERED.value,
                source_path=source_path,
                detail="{}",
                created_at=now,
                updated_at=now,
            )
            s.add(rec)
            s.commit()
            s.refresh(rec)
            return rec

    # ---- reads ----

    def get(self, user_id: str) -> Optional[MigrationRecord]:
        with Session(self.engine) as s:
            return s.get(MigrationRecord, user_id)

    def list_all(self) -> List[MigrationRecord]:
        with Session(self.engine) as s:
            return list(s.exec(select(MigrationRecord)).all())

    def list_by_status(self, status: MigrationStatus) -> List[MigrationRecord]:
        with Session(self.engine) as s:
            return list(
                s.exec(
                    select(MigrationRecord).where(
                        MigrationRecord.status == status.value
                    )
                ).all()
            )

    # ---- transitions ----

    def transition(
        self,
        user_id: str,
        target: MigrationStatus,
        *,
        detail: Optional[Dict[str, Any]] = None,
    ) -> MigrationRecord:
        """Transition a profile's migration to ``target`` status.

        Raises ``MigrationError`` if the transition is not in
        ``VALID_TRANSITIONS`` or the record doesn't exist.
        """
        with Session(self.engine) as s:
            rec = s.get(MigrationRecord, user_id)
            if rec is None:
                raise MigrationError(f"no migration record for user_id={user_id}")
            current = rec.status
            target_val = target.value if isinstance(target, MigrationStatus) else str(target)
            allowed = VALID_TRANSITIONS.get(current, set())
            if target_val not in allowed:
                raise MigrationError(
                    f"invalid transition: {current} → {target_val}"
                )
            rec.status = target_val
            if detail is not None:
                rec.detail = json.dumps(detail)
            rec.updated_at = datetime.utcnow()
            s.add(rec)
            s.commit()
            s.refresh(rec)
            return rec

    # ---- validation ----

    def validate_source(self, user_id: str, backup_root: Path) -> Dict[str, Any]:
        """Check that the profile's source directory exists in the backup."""
        profile_dir = _profile_dir(Path(backup_root), user_id)
        exists = profile_dir.exists()
        return {
            "source_valid": exists,
            "source_path": str(profile_dir),
            "source_path_exists": exists,
        }

    def validate_cookies(self, user_id: str, backup_root: Path) -> Dict[str, Any]:
        """Validate cookie availability from JSON or Chromium DB fallback."""
        backup_root = Path(backup_root)
        cookie_json = _cookie_json_path(backup_root, user_id)
        profile_dir = _profile_dir(backup_root, user_id)

        cookie_source = "none"
        cookie_count = 0

        if cookie_json.exists():
            try:
                cookies = [
                    c.to_playwright()
                    for c in import_cookies_json(
                        cookie_json.read_text(encoding="utf-8-sig")
                    )
                ]
                cookie_source = "json"
                cookie_count = len(cookies)
            except (OSError, UnicodeError, json.JSONDecodeError, ValueError):
                if profile_dir.exists():
                    cookies = [
                        c.to_playwright()
                        for c in import_adspower_profile(profile_dir)
                    ]
                    cookie_source = "profile_dir"
                    cookie_count = len(cookies)
        elif profile_dir.exists():
            cookies = [
                c.to_playwright() for c in import_adspower_profile(profile_dir)
            ]
            cookie_source = "profile_dir"
            cookie_count = len(cookies)

        return {
            "cookies_valid": cookie_count > 0,
            "cookie_source": cookie_source,
            "cookie_count": cookie_count,
        }

    def validate_storage(self, user_id: str, backup_root: Path) -> Dict[str, Any]:
        """Validate that LocalStorage/leveldb is present in the source profile."""
        profile_dir = _profile_dir(Path(backup_root), user_id)
        default_dir = find_profile_default_dir(profile_dir) if profile_dir.exists() else None
        has_local_storage = False
        has_web_storage = False
        has_network_cookies = False
        if default_dir is not None:
            has_local_storage = (default_dir / "Local Storage" / "leveldb").is_dir()
            has_web_storage = (default_dir / "WebStorage").is_dir()
            has_network_cookies = (default_dir / "Network" / "Cookies").is_file()
        storage_valid = has_local_storage or has_web_storage or has_network_cookies
        return {
            "storage_valid": storage_valid,
            "has_local_storage": has_local_storage,
            "has_web_storage": has_web_storage,
            "has_network_cookies": has_network_cookies,
        }

    def validate_extensions(self, user_id: str, backup_root: Path) -> Dict[str, Any]:
        """Validate extension data availability in the source profile."""
        profile_dir = _profile_dir(Path(backup_root), user_id)
        default_dir = find_profile_default_dir(profile_dir) if profile_dir.exists() else None
        ext_count = 0
        has_ext_state = False
        has_ext_cookies = False
        has_local_ext_settings = False
        if default_dir is not None:
            has_ext_state = (default_dir / "Extension State").is_dir()
            has_ext_cookies = (default_dir / "Extension Cookies").is_file()
            has_local_ext_settings = (default_dir / "Local Extension Settings").is_dir()
            # Count extensions if any storage exists
            if has_ext_state or has_ext_cookies or has_local_ext_settings:
                ext_count = 1  # At least one extension-related artifact
        return {
            "extensions_valid": True,  # Extensions are optional
            "extension_count": ext_count,
            "has_extension_state": has_ext_state,
            "has_extension_cookies": has_ext_cookies,
            "has_local_ext_settings": has_local_ext_settings,
        }

    def validate_all(self, user_id: str, backup_root: Path) -> Dict[str, Any]:
        """Run all four validation checks for one profile."""
        return {
            "source": self.validate_source(user_id, backup_root),
            "cookies": self.validate_cookies(user_id, backup_root),
            "storage": self.validate_storage(user_id, backup_root),
            "extensions": self.validate_extensions(user_id, backup_root),
        }

    # ---- batch operations ----

    def batch_validate(
        self, backup_root: Path, user_ids: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Validate all (or a subset of) profiles from a backup root.

        Does **not** launch external sites.
        """
        backup_root = Path(backup_root)
        if user_ids is None:
            try:
                all_profiles = load_adspower_profiles_index(backup_root)
                user_ids = [
                    str(m.get("user_id", "")).strip()
                    for m in all_profiles
                    if m.get("user_id")
                ]
            except FileNotFoundError:
                return {}
        results: Dict[str, Any] = {}
        for uid in user_ids:
            results[uid] = self.validate_all(uid, backup_root)
        return results

    def batch_status(self) -> List[Dict[str, Any]]:
        """Return migration status for all profiles as a list of dicts."""
        records = self.list_all()
        return [
            {
                "user_id": r.user_id,
                "status": r.status,
                "source_path": r.source_path,
                "detail": json.loads(r.detail) if r.detail else {},
                "created_at": r.created_at.isoformat() if r.created_at else None,
                "updated_at": r.updated_at.isoformat() if r.updated_at else None,
            }
            for r in records
        ]

    def batch_retry(
        self, user_ids: List[str]
    ) -> Dict[str, Dict[str, Any]]:
        """Retry failed migrations by resetting them to ``discovered``.

        Profiles not in ``failed`` state are skipped (``retried: False``).
        """
        results: Dict[str, Dict[str, Any]] = {}
        for uid in user_ids:
            rec = self.get(uid)
            if rec is None:
                results[uid] = {"retried": False, "reason": "no migration record"}
                continue
            if rec.status != MigrationStatus.FAILED.value:
                results[uid] = {
                    "retried": False,
                    "reason": f"status is {rec.status}, not failed",
                }
                continue
            # Reset to discovered for retry
            self.create_or_reset(uid, source_path=rec.source_path)
            results[uid] = {"retried": True}
        return results

    def batch_repair(
        self,
        backup_root: Path,
        user_ids: Optional[List[str]] = None,
    ) -> Dict[str, Dict[str, Any]]:
        """Re-validate and repair migration state for profiles.

        Runs validation checks and updates the detail field. Does **not**
        launch external sites.

        If a profile's source is still valid, its migration record is kept
        (or reset to ``discovered`` if it was ``failed``). If the source is
        gone, the record is marked ``failed``.
        """
        backup_root = Path(backup_root)
        if user_ids is None:
            try:
                all_profiles = load_adspower_profiles_index(backup_root)
                user_ids = [
                    str(m.get("user_id", "")).strip()
                    for m in all_profiles
                    if m.get("user_id")
                ]
            except FileNotFoundError:
                return {}

        results: Dict[str, Dict[str, Any]] = {}
        for uid in user_ids:
            rec = self.get(uid)
            if rec is None:
                # Create a record if missing
                rec = self.create_or_reset(uid, source_path=str(_profile_dir(backup_root, uid)))

            validation = self.validate_all(uid, backup_root)
            source_valid = validation["source"]["source_valid"]

            if not source_valid:
                if rec.status != MigrationStatus.FAILED.value:
                    self.transition(
                        uid,
                        MigrationStatus.FAILED,
                        detail={"error": "source path missing during repair", "validation": validation},
                    )
                results[uid] = {"repaired": False, "reason": "source invalid", "validation": validation}
            else:
                # If was failed, reset to discovered for re-processing
                if rec.status == MigrationStatus.FAILED.value:
                    self.create_or_reset(uid, source_path=rec.source_path)
                # Update detail with fresh validation
                rec = self.get(uid)
                if rec is not None:
                    self._update_detail(uid, {"validation": validation})
                results[uid] = {"repaired": True, "validation": validation}
        return results

    def _update_detail(self, user_id: str, detail: Dict[str, Any]) -> None:
        """Merge ``detail`` into the existing record's detail JSON."""
        with Session(self.engine) as s:
            rec = s.get(MigrationRecord, user_id)
            if rec is None:
                return
            existing = json.loads(rec.detail) if rec.detail else {}
            existing.update(detail)
            rec.detail = json.dumps(existing)
            rec.updated_at = datetime.utcnow()
            s.add(rec)
            s.commit()
