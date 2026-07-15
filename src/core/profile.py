"""Profile CRUD over SQLite.

A ``Profile`` is the user-facing representation; ``ProfileRecord`` is the
persisted row. We keep them decoupled so the public API doesn't leak
SQLModel internals.
"""
from __future__ import annotations

import json
import secrets
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from sqlmodel import Session, select

from .fingerprint import Fingerprint, generate_fingerprint
from .storage import ProfileRecord, SessionRecord, make_engine, init_db, get_session


# ---------------------------------------------------------------------------
# Public dataclass
# ---------------------------------------------------------------------------


@dataclass
class Profile:
    user_id: str
    name: str
    group_id: str = "0"

    # Sub-configs (already deserialised)
    proxy: Dict[str, Any] = field(default_factory=dict)
    fingerprint: Dict[str, Any] = field(default_factory=dict)
    cookies: List[Dict[str, Any]] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)
    remark: str = ""
    # Account lifecycle status (multi-account ops): new|warming|active|limited|banned|retired
    account_status: str = "new"

    # Full-profile import (.adb bundle path + apply-on-first-launch flag)
    import_source_path: str = ""
    initial_state_applied: bool = False

    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    last_launched_at: Optional[datetime] = None
    launch_count: int = 0

    # In-memory state for the running process (not persisted)
    running_pid: Optional[int] = None
    running_debug_port: Optional[int] = None
    running_ws: Optional[str] = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _new_user_id() -> str:
    """Generate an AdsPower-style short id (8 lowercase alphanum chars)."""
    # Use a 5-byte value for an 8-char base36 — plenty of entropy.
    n = int.from_bytes(secrets.token_bytes(5), "big")
    alphabet = "abcdefghijklmnopqrstuvwxyz0123456789"
    out = ""
    while n > 0 and len(out) < 8:
        out = alphabet[n % 36] + out
        n //= 36
    return out.ljust(8, "0")


def _record_to_profile(r: ProfileRecord, running: Optional[SessionRecord] = None) -> Profile:
    p = Profile(
        user_id=r.user_id,
        name=r.name,
        group_id=r.group_id,
        proxy=json.loads(r.user_proxy_config) if r.user_proxy_config else {},
        fingerprint=json.loads(r.fingerprint_config) if r.fingerprint_config else {},
        cookies=json.loads(r.cookies) if r.cookies else [],
        tags=json.loads(r.tags) if r.tags else [],
        remark=r.remark,
        account_status=getattr(r, "account_status", "new") or "new",
        import_source_path=r.import_source_path or "",
        initial_state_applied=bool(r.initial_state_applied),
        created_at=r.created_at,
        updated_at=r.updated_at,
        last_launched_at=r.last_launched_at,
        launch_count=r.launch_count,
    )
    if running and running.status == "running":
        p.running_pid = running.pid
        p.running_debug_port = running.debug_port
        p.running_ws = running.ws_endpoint
    return p


# ---------------------------------------------------------------------------
# Store
# ---------------------------------------------------------------------------


class ProfileStore:
    """High-level CRUD wrapper around ProfileRecord."""

    def __init__(self, db_path: Optional[Path] = None):
        self.engine = make_engine(db_path)
        init_db(self.engine)

    # ---- creation ----

    def create(
        self,
        name: str,
        *,
        group_id: str = "0",
        proxy: Optional[Dict[str, Any]] = None,
        fingerprint: Optional[Fingerprint] = None,
        cookies: Optional[List[Dict[str, Any]]] = None,
        tags: Optional[List[str]] = None,
        remark: str = "",
        account_status: str = "new",
        user_id: Optional[str] = None,
    ) -> Profile:
        """Create and persist a new profile.

        If ``fingerprint`` is omitted, a fresh one is generated. If
        ``user_id`` is omitted, a random 8-char id is assigned.
        """
        uid = user_id or _new_user_id()
        fp = fingerprint or generate_fingerprint()
        with Session(self.engine) as s:
            # Collision check
            existing = s.get(ProfileRecord, uid)
            if existing is not None:
                raise ValueError(f"user_id collision: {uid}")
            record = ProfileRecord(
                user_id=uid,
                name=name,
                group_id=group_id,
                user_proxy_config=json.dumps(proxy or {}),
                fingerprint_config=json.dumps(asdict(fp)),
                cookies=json.dumps(cookies or []),
                tags=json.dumps(tags or []),
                remark=remark,
                account_status=account_status or "new",
            )
            s.add(record)
            s.commit()
            s.refresh(record)
            return _record_to_profile(record)

    # ---- reads ----

    def get(self, user_id: str) -> Optional[Profile]:
        with Session(self.engine) as s:
            r = s.get(ProfileRecord, user_id)
            if r is None:
                return None
            running = s.exec(
                select(SessionRecord).where(
                    SessionRecord.user_id == user_id,
                    SessionRecord.status == "running",
                )
            ).first()
            return _record_to_profile(r, running)

    def list(
        self,
        *,
        group_id: Optional[str] = None,
        tag: Optional[str] = None,
        search: Optional[str] = None,
        account_status: Optional[str] = None,
        sort_by: str = "name",
        sort_order: str = "asc",
    ) -> List[Profile]:
        with Session(self.engine) as s:
            stmt = select(ProfileRecord)
            if group_id is not None:
                stmt = stmt.where(ProfileRecord.group_id == group_id)
            records = s.exec(stmt).all()
            out: List[Profile] = []
            for r in records:
                running = s.exec(
                    select(SessionRecord).where(
                        SessionRecord.user_id == r.user_id,
                        SessionRecord.status == "running",
                    )
                ).first()
                p = _record_to_profile(r, running)
                if tag and tag not in p.tags:
                    continue
                if account_status and p.account_status != account_status:
                    continue
                if search and search.lower() not in p.name.lower():
                    continue
                out.append(p)
            sort_keys = {
                "name": lambda p: p.name.casefold(),
                "id": lambda p: p.user_id.casefold(),
                "user_id": lambda p: p.user_id.casefold(),
                "group": lambda p: p.group_id.casefold(),
                "status": lambda p: p.account_status.casefold(),
                "tags": lambda p: ",".join(p.tags).casefold(),
                "launches": lambda p: p.launch_count,
                "cookies": lambda p: len(p.cookies),
                "created": lambda p: p.created_at,
                "updated": lambda p: p.updated_at,
                "last_launched": lambda p: p.last_launched_at or datetime.min,
                "proxy": lambda p: str(p.proxy.get("proxy_host", "")).casefold(),
                "engine": lambda p: str(p.fingerprint.get("browser_engine", "chromium")).casefold(),
                "live": lambda p: 0 if p.running_debug_port else 1,
            }
            key = sort_keys.get(sort_by, sort_keys["name"])
            out.sort(key=key, reverse=sort_order.lower() == "desc")
            return out

    # ---- updates ----

    def update(
        self,
        user_id: str,
        *,
        name: Optional[str] = None,
        group_id: Optional[str] = None,
        proxy: Optional[Dict[str, Any]] = None,
        fingerprint: Optional[Fingerprint] = None,
        cookies: Optional[List[Dict[str, Any]]] = None,
        tags: Optional[List[str]] = None,
        remark: Optional[str] = None,
        account_status: Optional[str] = None,
    ) -> Profile:
        with Session(self.engine) as s:
            r = s.get(ProfileRecord, user_id)
            if r is None:
                raise KeyError(user_id)
            if name is not None:
                r.name = name
            if group_id is not None:
                r.group_id = group_id
            if proxy is not None:
                r.user_proxy_config = json.dumps(proxy)
            if fingerprint is not None:
                r.fingerprint_config = json.dumps(asdict(fingerprint))
            if cookies is not None:
                r.cookies = json.dumps(cookies)
            if tags is not None:
                r.tags = json.dumps(tags)
            if remark is not None:
                r.remark = remark
            if account_status is not None:
                r.account_status = account_status
            r.touch()
            s.add(r)
            s.commit()
            s.refresh(r)
            return _record_to_profile(r)

    def delete(self, user_id: str) -> bool:
        with Session(self.engine) as s:
            r = s.get(ProfileRecord, user_id)
            if r is None:
                return False
            # Cascade: delete sessions for this profile
            sessions = s.exec(
                select(SessionRecord).where(SessionRecord.user_id == user_id)
            ).all()
            for sess in sessions:
                s.delete(sess)
            s.delete(r)
            s.commit()
            return True

    # ---- full-profile import bookkeeping ----

    def set_import_source(self, user_id: str, source_path: str, *, reset_applied: bool = True) -> Profile:
        """Record the path to an extracted .adb bundle so the launcher can
        apply LocalStorage/IndexedDB on the next launch.

        By default ``initial_state_applied`` is reset to False so a re-import
        re-applies the state. Pass ``reset_applied=False`` if you want to
        keep the "already applied" flag (e.g. when pointing to the same path).
        """
        with Session(self.engine) as s:
            r = s.get(ProfileRecord, user_id)
            if r is None:
                raise KeyError(user_id)
            r.import_source_path = source_path
            if reset_applied:
                r.initial_state_applied = False
            r.touch()
            s.add(r)
            s.commit()
            s.refresh(r)
            return _record_to_profile(r)

    def mark_initial_state_applied(self, user_id: str) -> Profile:
        """Mark the full-profile state as applied so the launcher won't
        re-copy the localStorage/IndexedDB dirs on subsequent launches."""
        with Session(self.engine) as s:
            r = s.get(ProfileRecord, user_id)
            if r is None:
                raise KeyError(user_id)
            r.initial_state_applied = True
            r.touch()
            s.add(r)
            s.commit()
            s.refresh(r)
            return _record_to_profile(r)

    # ---- session bookkeeping ----

    def record_session(
        self,
        user_id: str,
        *,
        session_id: str,
        debug_port: int,
        ws_endpoint: str,
        pid: Optional[int] = None,
    ) -> None:
        with Session(self.engine) as s:
            # Mark old sessions as stopped
            olds = s.exec(
                select(SessionRecord).where(
                    SessionRecord.user_id == user_id,
                    SessionRecord.status == "running",
                )
            ).all()
            for old in olds:
                old.status = "stopped"
                s.add(old)
            # Bump launch counter
            r = s.get(ProfileRecord, user_id)
            if r is not None:
                r.last_launched_at = datetime.utcnow()
                r.launch_count += 1
                r.touch()
                s.add(r)
            sess = SessionRecord(
                session_id=session_id,
                user_id=user_id,
                debug_port=debug_port,
                ws_endpoint=ws_endpoint,
                pid=pid,
                status="running",
            )
            s.add(sess)
            s.commit()

    def stop_session(self, user_id: str) -> bool:
        """Mark all running sessions for a profile as stopped."""
        with Session(self.engine) as s:
            olds = s.exec(
                select(SessionRecord).where(
                    SessionRecord.user_id == user_id,
                    SessionRecord.status == "running",
                )
            ).all()
            if not olds:
                return False
            for o in olds:
                o.status = "stopped"
                s.add(o)
            s.commit()
            return True

    def get_session(self, user_id: str) -> Optional[SessionRecord]:
        with Session(self.engine) as s:
            return s.exec(
                select(SessionRecord).where(
                    SessionRecord.user_id == user_id,
                    SessionRecord.status == "running",
                )
            ).first()