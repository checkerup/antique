"""Typed dataclass models for the antique SDK."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


# ---------------------------------------------------------------------------
# Health & info
# ---------------------------------------------------------------------------

@dataclass
class HealthStatus:
    status: str
    service: str
    version: str


@dataclass
class InfoStatus:
    service: str
    version: str
    profile_count: int
    running_count: int
    running: List[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Profiles
# ---------------------------------------------------------------------------

@dataclass
class Profile:
    user_id: str
    name: str
    group_id: str = "0"
    status: str = "Inactive"
    debug_port: Optional[int] = None
    ws_endpoint: Optional[str] = None
    remark: str = ""
    tags: List[str] = field(default_factory=list)
    account_status: Optional[str] = None
    user_proxy_config: Optional[Dict[str, Any]] = None
    fingerprint_config: Optional[Dict[str, Any]] = None
    cookies: List[Dict[str, Any]] = field(default_factory=list)
    due_date: Optional[str] = None
    overdue: bool = False
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    last_launched_at: Optional[str] = None
    launch_count: int = 0


@dataclass
class ProfileCreateRequest:
    """Request model for creating a profile.

    Mirrors the API's ``UserCreate`` body. Only ``name`` is required.
    """
    name: str
    group_id: str = "0"
    user_proxy_config: Optional[Dict[str, Any]] = None
    fingerprint_config: Optional[Dict[str, Any]] = None
    cookies: Optional[List[Dict[str, Any]]] = None
    remark: str = ""
    tags: Optional[List[str]] = None
    account_status: Optional[str] = None
    user_id: Optional[str] = None
    persona: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        """Serialise to a JSON-ready dict, omitting None values."""
        d: Dict[str, Any] = {"name": self.name, "group_id": self.group_id}
        for key in (
            "user_proxy_config", "fingerprint_config", "cookies", "remark",
            "tags", "account_status", "user_id", "persona",
        ):
            val = getattr(self, key)
            if val is not None:
                d[key] = val
        return d


@dataclass
class StartedProfile:
    """Result of POST /user/start."""
    user_id: str
    debug_port: int
    ws_endpoint: str
    pid: int
    session_id: str


@dataclass
class StoppedProfile:
    """Result of POST /user/stop."""
    user_id: str
    stopped: bool


@dataclass
class ActiveProfile:
    """An entry in GET /user/active."""
    user_id: str
    session_id: str
    debug_port: int
    ws_endpoint: str
    pid: int


@dataclass
class ProfileListResponse:
    """Paginated response from GET /user/list."""
    profiles: List[Profile]
    total: int
    page: int
    page_size: int


@dataclass
class DeletedProfile:
    """Result of DELETE /user/delete."""
    user_id: str
    deleted: bool
