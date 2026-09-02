"""antique SDK — main client.

A typed, thin wrapper around the antique REST API built on httpx.  The
transport is injectable so tests can run without a live server.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Union

import httpx

from .exceptions import AntiqueAPIError, ProfileNotFound, TransportError
from .models import (
    ActiveProfile,
    DeletedProfile,
    HealthStatus,
    InfoStatus,
    Profile,
    ProfileCreateRequest,
    ProfileListResponse,
    StartedProfile,
    StoppedProfile,
)

DEFAULT_BASE_URL = "http://127.0.0.1:50325"
DEFAULT_TIMEOUT = 30.0


class AntiqueClient:
    """Typed client for the antique anti-detect browser REST API.

    Parameters
    ----------
    base_url
        Root URL of the antique server. Defaults to ``http://127.0.0.1:50325``.
    api_token
        Optional bearer token. If set, every request gets
        ``Authorization: Bearer <token>``. If ``None`` (default), no
        auth header is sent (server may allow unauthenticated local access).
    timeout
        Per-request timeout in seconds.
    transport
        httpx ``BaseTransport`` instance for transport injection. Primarily
        used by tests (``httpx.MockTransport``). If ``None``, a default
        ``httpx.AsyncHTTPTransport`` is used.
    """

    def __init__(
        self,
        base_url: str = DEFAULT_BASE_URL,
        *,
        api_token: Optional[str] = None,
        timeout: float = DEFAULT_TIMEOUT,
        transport: Optional[httpx.BaseTransport] = None,
    ) -> None:
        self._base_url = base_url
        self._token = api_token
        self._timeout = timeout
        self._transport = transport
        self._closed = False

        headers: Dict[str, str] = {"Accept": "application/json"}
        if api_token:
            headers["Authorization"] = f"Bearer {api_token}"

        client_kwargs: Dict[str, Any] = {
            "base_url": base_url,
            "timeout": timeout,
            "headers": headers,
        }
        if transport is not None:
            client_kwargs["transport"] = transport

        self._client = httpx.Client(**client_kwargs)

    # ------------------------------------------------------------------
    # Context-manager support
    # ------------------------------------------------------------------

    def __enter__(self) -> "AntiqueClient":
        return self

    def __exit__(self, *exc_info) -> None:
        self.close()

    def close(self) -> None:
        if not self._closed:
            self._client.close()
            self._closed = True

    @property
    def base_url(self) -> str:
        return self._base_url

    # ------------------------------------------------------------------
    # Internal request helpers
    # ------------------------------------------------------------------

    def _request(
        self,
        method: str,
        path: str,
        *,
        params: Optional[Dict[str, Any]] = None,
        json_body: Optional[Dict[str, Any]] = None,
    ) -> httpx.Response:
        if self._closed:
            raise RuntimeError("Client is closed")
        try:
            resp = self._client.request(method, path, params=params, json=json_body)
        except httpx.HTTPError as exc:
            raise TransportError(f"Request failed: {exc}", original=exc) from exc
        return resp

    def _check_response(self, resp: httpx.Response) -> Dict[str, Any]:
        """Validate HTTP status and API envelope; return parsed ``data``."""
        if resp.status_code >= 400:
            try:
                body = resp.json()
            except Exception:
                body = {"msg": resp.text}
            msg = body.get("detail") or body.get("msg") or f"HTTP {resp.status_code}"
            raise AntiqueAPIError(
                str(msg), status_code=resp.status_code,
                api_code=body.get("code"),
            )

        try:
            body = resp.json()
        except Exception as exc:
            raise AntiqueAPIError(
                f"Invalid JSON response: {exc}", status_code=resp.status_code,
            ) from exc

        # AdsPower envelope: {"code": 0, "msg": "success", "data": {...}}
        if isinstance(body, dict) and "code" in body:
            if body.get("code") != 0:
                msg = body.get("msg", "unknown error")
                raise AntiqueAPIError(
                    str(msg), status_code=resp.status_code,
                    api_code=body.get("code"),
                )
            return body.get("data") or {}

        # Non-envelope JSON (e.g. /health, /info)
        return body

    def _get_data_or_raise_404(
        self, resp: httpx.Response, user_id: str
    ) -> Dict[str, Any]:
        """Like _check_response but converts 404 → ProfileNotFound."""
        if resp.status_code == 404:
            raise ProfileNotFound(user_id)
        return self._check_response(resp)

    # ------------------------------------------------------------------
    # Health & info
    # ------------------------------------------------------------------

    def health(self) -> HealthStatus:
        """GET /health — server liveness check."""
        resp = self._request("GET", "/health")
        data = self._check_response(resp)
        return HealthStatus(
            status=data.get("status", "unknown"),
            service=data.get("service", ""),
            version=data.get("version", ""),
        )

    def info(self) -> InfoStatus:
        """GET /info — server diagnostics (profile/running counts)."""
        resp = self._request("GET", "/info")
        data = self._check_response(resp)
        return InfoStatus(
            service=data.get("service", ""),
            version=data.get("version", ""),
            profile_count=data.get("profile_count", 0),
            running_count=data.get("running_count", 0),
            running=data.get("running", []),
        )

    # ------------------------------------------------------------------
    # Profiles — CRUD
    # ------------------------------------------------------------------

    def list_profiles(
        self,
        *,
        group_id: Optional[str] = None,
        page: int = 1,
        page_size: int = 100,
        search: Optional[str] = None,
        tag: Optional[str] = None,
        account_status: Optional[str] = None,
        sort_by: str = "name",
        sort_order: str = "asc",
    ) -> List[Profile]:
        """GET /user/list — list profiles with pagination and filtering."""
        params: Dict[str, Any] = {
            "page": page,
            "page_size": page_size,
            "sort_by": sort_by,
            "sort_order": sort_order,
        }
        if group_id is not None:
            params["group_id"] = group_id
        if search is not None:
            params["search"] = search
        if tag is not None:
            params["tag"] = tag
        if account_status is not None:
            params["account_status"] = account_status

        resp = self._request("GET", "/user/list", params=params)
        data = self._check_response(resp)
        raw_list = data.get("list", [])
        return [_profile_from_dict(p) for p in raw_list]

    def create_profile(
        self,
        req_or_name: Optional[Union[ProfileCreateRequest, str]] = None,
        *,
        name: Optional[str] = None,
        group_id: Optional[str] = None,
        user_proxy_config: Optional[Dict[str, Any]] = None,
        fingerprint_config: Optional[Dict[str, Any]] = None,
        cookies: Optional[List[Dict[str, Any]]] = None,
        remark: Optional[str] = None,
        tags: Optional[List[str]] = None,
        account_status: Optional[str] = None,
        user_id: Optional[str] = None,
        persona: Optional[Dict[str, Any]] = None,
    ) -> str:
        """POST /user/create — create a profile, return the new ``user_id``.

        Accepts either a :class:`ProfileCreateRequest` or a bare ``name``
        string plus keyword args for convenience.
        """
        if isinstance(req_or_name, ProfileCreateRequest):
            if name is not None:
                raise TypeError("name cannot be combined with ProfileCreateRequest")
            body = req_or_name.to_dict()
        else:
            profile_name = name if name is not None else req_or_name
            if not isinstance(profile_name, str) or not profile_name.strip():
                raise TypeError("create_profile requires a non-empty name")
            body: Dict[str, Any] = {"name": profile_name}
            body.setdefault("group_id", "0")
            for k, v in [
                ("group_id", group_id),
                ("user_proxy_config", user_proxy_config),
                ("fingerprint_config", fingerprint_config),
                ("cookies", cookies),
                ("remark", remark),
                ("tags", tags),
                ("account_status", account_status),
                ("user_id", user_id),
                ("persona", persona),
            ]:
                if v is not None:
                    body[k] = v
        resp = self._request("POST", "/user/create", json_body=body)
        data = self._check_response(resp)
        return str(data["user_id"])

    def get_profile(self, user_id: str) -> Profile:
        """GET /profile/{user_id} — fetch a single profile."""
        resp = self._request("GET", f"/profile/{user_id}")
        data = self._get_data_or_raise_404(resp, user_id)
        return _profile_from_dict(data)

    def delete_profile(self, user_id: str) -> bool:
        """POST /user/delete — delete a profile by user_id."""
        resp = self._request("POST", "/user/delete", json_body={"user_id": user_id})
        data = self._check_response(resp)
        return bool(data.get("deleted", False))

    # ------------------------------------------------------------------
    # Profiles — start / stop / active
    # ------------------------------------------------------------------

    def start_profile(
        self,
        user_id: str,
        *,
        debug_port: Optional[int] = None,
        launch_args: Optional[List[str]] = None,
    ) -> StartedProfile:
        """POST /user/start — launch a browser for a profile."""
        body: Dict[str, Any] = {"user_id": user_id}
        if debug_port is not None:
            body["debug_port"] = debug_port
        if launch_args is not None:
            body["launch_args"] = launch_args
        resp = self._request("POST", "/user/start", json_body=body)
        if resp.status_code == 404:
            raise ProfileNotFound(user_id)
        data = self._check_response(resp)
        return StartedProfile(
            user_id=str(data["user_id"]),
            debug_port=int(data["debug_port"]),
            ws_endpoint=str(data["ws_endpoint"]),
            pid=int(data["pid"]),
            session_id=str(data["session_id"]),
        )

    def stop_profile(self, user_id: str) -> StoppedProfile:
        """POST /user/stop — stop a running browser session."""
        resp = self._request("POST", "/user/stop", json_body={"user_id": user_id})
        data = self._check_response(resp)
        return StoppedProfile(
            user_id=str(data["user_id"]),
            stopped=bool(data.get("stopped", False)),
        )

    def active_profiles(self) -> List[ActiveProfile]:
        """GET /user/active — list currently running browser sessions."""
        resp = self._request("GET", "/user/active")
        data = self._check_response(resp)
        raw_list = data.get("list", [])
        return [
            ActiveProfile(
                user_id=str(p["user_id"]),
                session_id=str(p["session_id"]),
                debug_port=int(p["debug_port"]),
                ws_endpoint=str(p["ws_endpoint"]),
                pid=int(p["pid"]),
            )
            for p in raw_list
        ]

    # ------------------------------------------------------------------
    # Migration / backup import
    # ------------------------------------------------------------------

    def import_backup_preview(self, source_path: str) -> Dict[str, Any]:
        """POST /user/import/backup/preview — preview a backup bundle."""
        body = {"source_path": source_path}
        resp = self._request("POST", "/user/import/backup/preview", json_body=body)
        return self._check_response(resp)

    def import_backup(
        self,
        source_path: str,
        *,
        overwrite: bool = False,
        limit: Optional[int] = None,
    ) -> Dict[str, Any]:
        """POST /user/import/backup — import profiles from an AdsPower backup."""
        body: Dict[str, Any] = {"source_path": source_path, "overwrite": overwrite}
        if limit is not None:
            body["limit"] = limit
        resp = self._request("POST", "/user/import/backup", json_body=body)
        return self._check_response(resp)

    # ------------------------------------------------------------------
    # Raw request escape hatch
    # ------------------------------------------------------------------

    def raw_request(
        self,
        method: str,
        path: str,
        *,
        params: Optional[Dict[str, Any]] = None,
        json_body: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Send an arbitrary request and return the parsed ``data`` envelope.

        This is an escape hatch for endpoints the SDK doesn't yet wrap.
        """
        resp = self._request(method, path, params=params, json_body=json_body)
        return self._check_response(resp)


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _profile_from_dict(d: Dict[str, Any]) -> Profile:
    """Build a :class:`Profile` from a raw API dict, tolerating missing keys."""
    return Profile(
        user_id=str(d.get("user_id", "")),
        name=str(d.get("name", "")),
        group_id=str(d.get("group_id", "0")),
        status=str(d.get("status", "Inactive")),
        debug_port=d.get("debug_port"),
        ws_endpoint=d.get("ws_endpoint"),
        remark=str(d.get("remark", "")),
        tags=list(d.get("tags", [])),
        account_status=d.get("account_status"),
        user_proxy_config=d.get("user_proxy_config"),
        fingerprint_config=d.get("fingerprint_config"),
        cookies=list(d.get("cookies", [])),
        due_date=d.get("due_date"),
        overdue=bool(d.get("overdue", False)),
        created_at=d.get("created_at"),
        updated_at=d.get("updated_at"),
        last_launched_at=d.get("last_launched_at"),
        launch_count=int(d.get("launch_count", 0)),
    )
