"""SQLite storage layer using SQLModel.

Stores profiles, fingerprint configs, proxy configs, and session metadata.
DB file lives at ``data/antique.db`` by default — overridable via env.
"""
from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path
from typing import Optional

from sqlmodel import Field, SQLModel, create_engine, Session, select


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------


class ProfileRecord(SQLModel, table=True):
    """Persistent profile metadata. Mirrors AdsPower's user_profiles table."""

    __tablename__ = "profiles"

    # AdsPower-compatible primary key (short random alphanumeric id)
    user_id: str = Field(primary_key=True, index=True)
    name: str = Field(index=True)
    group_id: str = Field(default="0", index=True)

    # Fingerprint fields (stored as JSON-encoded strings for portability)
    user_proxy_config: str = Field(default="{}")  # JSON of proxy dict
    fingerprint_config: str = Field(default="{}")  # JSON of fingerprint dict
    cookies: str = Field(default="[]")  # JSON list of cookies

    # Tags / labels / notes
    tags: str = Field(default="[]")  # JSON list of strings
    remark: str = Field(default="")  # free-form note

    # Full-profile import (.adb bundle). When set, the launcher copies
    # LocalStorage/leveldb + IndexedDB from this path into Playwright's
    # user_data_dir before the first launch.
    import_source_path: str = Field(default="")  # absolute path on disk
    initial_state_applied: bool = Field(default=False)

    # Bookkeeping
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    last_launched_at: Optional[datetime] = Field(default=None)
    launch_count: int = Field(default=0)

    def touch(self) -> None:
        """Update ``updated_at`` to now."""
        self.updated_at = datetime.utcnow()


class SessionRecord(SQLModel, table=True):
    """A running browser session bound to a profile."""

    __tablename__ = "sessions"

    session_id: str = Field(primary_key=True, index=True)
    user_id: str = Field(foreign_key="profiles.user_id", index=True)
    debug_port: int  # CDP debug port (Chrome --remote-debugging-port)
    ws_endpoint: str  # full WS URL for CDP
    pid: Optional[int] = Field(default=None)
    started_at: datetime = Field(default_factory=datetime.utcnow)
    status: str = Field(default="running")  # running | stopped | crashed


class TagRecord(SQLModel, table=True):
    __tablename__ = "tags"

    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(unique=True, index=True)
    color: str = Field(default="#888888")


class GroupRecord(SQLModel, table=True):
    __tablename__ = "groups"

    group_id: str = Field(primary_key=True)
    name: str
    sort_order: int = Field(default=0)


# ---------------------------------------------------------------------------
# Engine / session factory
# ---------------------------------------------------------------------------


def _default_db_path() -> Path:
    """Resolve the default SQLite path under ``./data/antique.db``."""
    env = os.environ.get("ANTIQUE_DB")
    if env:
        return Path(env)
    base = Path(os.environ.get("ANTIQUE_DATA_DIR", "data"))
    base.mkdir(parents=True, exist_ok=True)
    return base / "antique.db"


def make_engine(db_path: Optional[Path] = None, echo: bool = False):
    """Build a SQLAlchemy engine for SQLite."""
    path = db_path or _default_db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    url = f"sqlite:///{path}"
    # check_same_thread=False because FastAPI/Playwright may use the engine
    # from multiple threads; SQLModel/SQLAlchemy serialises writes for us.
    return create_engine(url, echo=echo, connect_args={"check_same_thread": False})


def init_db(engine=None) -> None:
    """Create tables if they don't exist. Idempotent."""
    if engine is None:
        engine = make_engine()
    SQLModel.metadata.create_all(engine)


def get_session(engine=None) -> Session:
    """Open a session for the given engine (default DB)."""
    if engine is None:
        engine = make_engine()
    return Session(engine)


# ---------------------------------------------------------------------------
# Convenience helpers
# ---------------------------------------------------------------------------


def ensure_default_group(engine) -> None:
    """Make sure the default group ("0", "Default") exists."""
    with Session(engine) as s:
        existing = s.get(GroupRecord, "0")
        if existing is None:
            s.add(GroupRecord(group_id="0", name="Default", sort_order=0))
            s.commit()