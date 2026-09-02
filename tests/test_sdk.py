"""TDD tests for the antique Python SDK.

These tests use httpx transport injection (MockTransport) so they never hit
the network — they exercise the SDK client against a canned set of HTTP
responses that mirror the real REST API.

Run:  python -m pytest tests/test_sdk.py -v
"""
from __future__ import annotations

import json
import pytest
import httpx

from antique_sdk import AntiqueClient, AntiqueAPIError, ProfileNotFound
from antique_sdk.models import Profile, ProfileCreateRequest, HealthStatus


# ---------------------------------------------------------------------------
# Helpers — build a MockTransport that routes by (method, path)
# ---------------------------------------------------------------------------

def make_mock_transport(routes: dict | None = None, *, token: str | None = None):
    """Return an httpx.MockTransport configured with canned responses.

    ``routes`` maps (METHOD, path-prefix) → (status, json_body).
    """
    default_routes = {
        ("GET", "/health"): (200, {"status": "ok", "service": "antique", "version": "1.0.1"}),
        ("GET", "/info"): (200, {
            "service": "antique", "version": "1.0.1",
            "profile_count": 0, "running_count": 0, "running": [],
        }),
        ("GET", "/user/list"): (200, {
            "code": 0, "msg": "success",
            "data": {"list": [
                {"user_id": "abc123", "name": "test-profile", "group_id": "0",
                 "status": "Inactive", "debug_port": None, "ws_endpoint": None},
            ], "total": 1, "page": 1, "page_size": 100},
        }),
        ("POST", "/user/create"): (200, {
            "code": 0, "msg": "success",
            "data": {"user_id": "new123"},
        }),
        ("POST", "/user/start"): (200, {
            "code": 0, "msg": "success",
            "data": {"user_id": "abc123", "debug_port": 9222,
                     "ws_endpoint": "ws://127.0.0.1:9222", "pid": 12345,
                     "session_id": "sess-1"},
        }),
        ("POST", "/user/stop"): (200, {
            "code": 0, "msg": "success",
            "data": {"user_id": "abc123", "stopped": True},
        }),
        ("GET", "/user/active"): (200, {
            "code": 0, "msg": "success",
            "data": {"list": [
                {"user_id": "abc123", "session_id": "sess-1",
                 "debug_port": 9222, "ws_endpoint": "ws://127.0.0.1:9222",
                 "pid": 12345},
            ]},
        }),
        ("POST", "/user/import/backup/preview"): (200, {
            "code": 0, "msg": "success",
            "data": {"profiles": [{"name": "p1"}], "count": 1},
        }),
        ("POST", "/user/import/backup"): (200, {
            "code": 0, "msg": "success",
            "data": {"imported": 3, "skipped": 0, "errors": []},
        }),
        ("GET", "/profile/abc123"): (200, {
            "code": 0, "msg": "success",
            "data": {"user_id": "abc123", "name": "test-profile", "group_id": "0",
                     "fingerprint_config": {}, "cookies": []},
        }),
        ("POST", "/user/delete"): (200, {
            "code": 0, "msg": "success",
            "data": {"user_id": "abc123", "deleted": True},
        }),
    }
    if routes:
        default_routes.update(routes)

    def handler(request: httpx.Request) -> httpx.Response:
        # Token check
        if token is not None:
            auth = request.headers.get("authorization", "")
            if auth != f"Bearer {token}":
                return httpx.Response(401, json={"code": -1, "msg": "unauthorized", "data": None})

        method = request.method
        url_path = request.url.path

        # Try exact match first, then longest-prefix match
        for (m, prefix), (status, body) in sorted(default_routes.items(), key=lambda x: -len(x[0][1])):
            if method == m and url_path == prefix:
                return httpx.Response(status, json=body)

        for (m, prefix), (status, body) in sorted(default_routes.items(), key=lambda x: -len(x[0][1])):
            if method == m and url_path.startswith(prefix):
                return httpx.Response(status, json=body)

        return httpx.Response(404, json={"code": -1, "msg": "not found", "data": None})

    return httpx.MockTransport(handler)


# ---------------------------------------------------------------------------
# Tests: client construction & auth
# ---------------------------------------------------------------------------

class TestClientConstruction:
    def test_default_base_url(self):
        client = AntiqueClient()
        assert str(client.base_url).rstrip("/") == "http://127.0.0.1:50325"

    def test_custom_base_url(self):
        client = AntiqueClient(base_url="http://localhost:8080")
        assert "8080" in str(client.base_url)

    def test_with_token(self):
        client = AntiqueClient(api_token="secret")
        assert client._token == "secret"

    def test_transport_injection(self):
        transport = make_mock_transport()
        client = AntiqueClient(transport=transport)
        assert client._transport is transport

    def test_custom_timeout(self):
        client = AntiqueClient(timeout=60.0)
        assert client._timeout == 60.0


# ---------------------------------------------------------------------------
# Tests: auth header injection
# ---------------------------------------------------------------------------

class TestAuth:
    def test_token_sent_as_bearer(self):
        transport = make_mock_transport(token="mytoken")
        client = AntiqueClient(base_url="http://test", api_token="mytoken", transport=transport)
        result = client.health()
        assert result.status == "ok"

    def test_no_token_no_auth_header(self):
        requests_seen = []

        def handler(request: httpx.Request) -> httpx.Response:
            requests_seen.append(request)
            return httpx.Response(200, json={"status": "ok", "service": "antique", "version": "1.0.1"})

        transport = httpx.MockTransport(handler)
        client = AntiqueClient(base_url="http://test", transport=transport)
        client.health()
        assert "authorization" not in requests_seen[0].headers


# ---------------------------------------------------------------------------
# Tests: health & info
# ---------------------------------------------------------------------------

class TestHealth:
    def test_health(self):
        transport = make_mock_transport()
        client = AntiqueClient(transport=transport)
        result = client.health()
        assert result.status == "ok"
        assert result.service == "antique"
        assert result.version == "1.0.1"

    def test_info(self):
        transport = make_mock_transport()
        client = AntiqueClient(transport=transport)
        result = client.info()
        assert result.service == "antique"
        assert result.profile_count == 0
        assert result.running_count == 0
        assert isinstance(result.running, list)


# ---------------------------------------------------------------------------
# Tests: profiles — list/create/start/stop/active
# ---------------------------------------------------------------------------

class TestProfiles:
    def test_list_profiles(self):
        transport = make_mock_transport()
        client = AntiqueClient(transport=transport)
        profiles = client.list_profiles()
        assert len(profiles) == 1
        assert isinstance(profiles[0], Profile)
        assert profiles[0].user_id == "abc123"
        assert profiles[0].name == "test-profile"

    def test_list_profiles_with_params(self):
        captured = []

        def handler(request: httpx.Request) -> httpx.Response:
            captured.append(request)
            return httpx.Response(200, json={
                "code": 0, "msg": "success",
                "data": {"list": [], "total": 0, "page": 1, "page_size": 50},
            })

        transport = httpx.MockTransport(handler)
        client = AntiqueClient(transport=transport)
        client.list_profiles(page=2, page_size=50, search="foo")
        assert "page=2" in str(captured[0].url)
        assert "page_size=50" in str(captured[0].url)
        assert "search=foo" in str(captured[0].url)

    def test_create_profile(self):
        transport = make_mock_transport()
        client = AntiqueClient(transport=transport)
        req = ProfileCreateRequest(name="my-profile")
        user_id = client.create_profile(req)
        assert user_id == "new123"

    def test_create_profile_with_kwargs(self):
        captured = []

        def handler(request: httpx.Request) -> httpx.Response:
            captured.append(request)
            return httpx.Response(200, json={
                "code": 0, "msg": "success", "data": {"user_id": "kw1"},
            })

        transport = httpx.MockTransport(handler)
        client = AntiqueClient(transport=transport)
        user_id = client.create_profile("kw-profile", group_id="1")
        assert user_id == "kw1"
        body = json.loads(captured[0].content)
        assert body["name"] == "kw-profile"
        assert body["group_id"] == "1"

    def test_start_profile(self):
        transport = make_mock_transport()
        client = AntiqueClient(transport=transport)
        result = client.start_profile("abc123")
        assert result.user_id == "abc123"
        assert result.debug_port == 9222
        assert result.ws_endpoint == "ws://127.0.0.1:9222"
        assert result.pid == 12345

    def test_start_profile_with_debug_port(self):
        captured = []

        def handler(request: httpx.Request) -> httpx.Response:
            captured.append(request)
            return httpx.Response(200, json={
                "code": 0, "msg": "success",
                "data": {"user_id": "x", "debug_port": 9999,
                         "ws_endpoint": "ws://x", "pid": 1, "session_id": "s"},
            })

        transport = httpx.MockTransport(handler)
        client = AntiqueClient(transport=transport)
        client.start_profile("x", debug_port=9999)
        body = json.loads(captured[0].content)
        assert body["debug_port"] == 9999

    def test_stop_profile(self):
        transport = make_mock_transport()
        client = AntiqueClient(transport=transport)
        result = client.stop_profile("abc123")
        assert result.user_id == "abc123"
        assert result.stopped is True

    def test_active_profiles(self):
        transport = make_mock_transport()
        client = AntiqueClient(transport=transport)
        result = client.active_profiles()
        assert len(result) == 1
        assert result[0].user_id == "abc123"
        assert result[0].debug_port == 9222

    def test_get_profile(self):
        transport = make_mock_transport()
        client = AntiqueClient(transport=transport)
        profile = client.get_profile("abc123")
        assert profile.user_id == "abc123"
        assert profile.name == "test-profile"

    def test_delete_profile(self):
        transport = make_mock_transport()
        client = AntiqueClient(transport=transport)
        result = client.delete_profile("abc123")
        assert result is True


# ---------------------------------------------------------------------------
# Tests: migration / backup import
# ---------------------------------------------------------------------------

class TestMigration:
    def test_import_backup_preview(self):
        transport = make_mock_transport()
        client = AntiqueClient(transport=transport)
        result = client.import_backup_preview("/path/to/backup")
        assert "profiles" in result
        assert result["count"] == 1

    def test_import_backup(self):
        transport = make_mock_transport()
        client = AntiqueClient(transport=transport)
        result = client.import_backup("/path/to/backup")
        assert result["imported"] == 3
        assert result["skipped"] == 0


# ---------------------------------------------------------------------------
# Tests: error handling
# ---------------------------------------------------------------------------

class TestErrors:
    def test_api_error_on_non_zero_code(self):
        transport = make_mock_transport({
            ("GET", "/user/list"): (200, {"code": 1, "msg": "internal error", "data": None}),
        })
        client = AntiqueClient(transport=transport)
        with pytest.raises(AntiqueAPIError) as exc_info:
            client.list_profiles()
        assert "internal error" in str(exc_info.value)

    def test_not_found_raises_profile_not_found(self):
        transport = make_mock_transport({
            ("GET", "/profile/missing"): (404, {"detail": "user_id not found"}),
        })
        client = AntiqueClient(transport=transport)
        with pytest.raises(ProfileNotFound):
            client.get_profile("missing")

    def test_http_error_on_500(self):
        transport = make_mock_transport({
            ("GET", "/health"): (500, {"error": "server crash"}),
        })
        client = AntiqueClient(transport=transport)
        with pytest.raises(AntiqueAPIError):
            client.health()

    def test_error_includes_status_code(self):
        transport = make_mock_transport({
            ("GET", "/user/list"): (403, {"detail": "forbidden"}),
        })
        client = AntiqueClient(transport=transport)
        with pytest.raises(AntiqueAPIError) as exc_info:
            client.list_profiles()
        assert exc_info.value.status_code == 403


# ---------------------------------------------------------------------------
# Tests: context manager
# ---------------------------------------------------------------------------

class TestContextManager:
    def test_context_manager_closes(self):
        transport = make_mock_transport()
        with AntiqueClient(transport=transport) as client:
            result = client.health()
            assert result.status == "ok"
        # After exit, client should be closed
        assert client._closed is True

    def test_context_manager_available(self):
        transport = make_mock_transport()
        client = AntiqueClient(transport=transport)
        assert hasattr(client, "__enter__")
        assert hasattr(client, "__exit__")


# ---------------------------------------------------------------------------
# Tests: model types
# ---------------------------------------------------------------------------

class TestModels:
    def test_health_status_model(self):
        h = HealthStatus(status="ok", service="antique", version="1.0.1")
        assert h.status == "ok"
        assert h.version == "1.0.1"

    def test_profile_model(self):
        p = Profile(user_id="x", name="n")
        assert p.user_id == "x"
        assert p.name == "n"
        # Optional fields should have defaults
        assert p.group_id == "0"
        assert p.status == "Inactive"

    def test_profile_create_request(self):
        req = ProfileCreateRequest(name="test")
        assert req.name == "test"
        assert req.group_id == "0"
