"""Security hardening tests for deployment modes, exact origin validation,
fail-closed startup, and mode-aware auth exemptions.

These tests codify the P2 security requirements:

1. Explicit deployment modes (local/LAN/remote) with different auth rules.
2. Exact URL origin validation — no substring bypass (evil.com not allowed
   by a "localhost.evil.com" trick, no "localhost" substring matching).
3. Remote/non-loopback startup must fail closed without an API token.
4. /json and /devtools must NOT be universally auth-exempt in remote mode.
5. Secure generated-token helper.
6. Restrictive CORS allowlist (not "*" in remote/LAN mode).
7. Tests for malicious origins, missing/incorrect token, exempt
   static/health behavior, and mode config.
"""
import os
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from src.core.security import (
    DeploymentMode,
    generate_api_token,
    validate_deployment_mode,
    is_loopback_host,
    parse_allowed_origins,
    is_origin_allowed,
)
from src.api.server import auth_check, create_app


# ===========================================================================
# DeploymentMode validation
# ===========================================================================


class TestDeploymentMode:
    def test_default_mode_is_local(self):
        mode = validate_deployment_mode(None)
        assert mode == DeploymentMode.LOCAL

    def test_explicit_local(self):
        assert validate_deployment_mode("local") == DeploymentMode.LOCAL

    def test_explicit_lan(self):
        assert validate_deployment_mode("lan") == DeploymentMode.LAN

    def test_explicit_remote(self):
        assert validate_deployment_mode("remote") == DeploymentMode.REMOTE

    def test_invalid_mode_raises(self):
        with pytest.raises(ValueError, match="Invalid deployment mode"):
            validate_deployment_mode("internet")

    def test_case_insensitive(self):
        assert validate_deployment_mode("LOCAL") == DeploymentMode.LOCAL
        assert validate_deployment_mode("Remote") == DeploymentMode.REMOTE

    def test_env_var_resolution(self):
        with patch.dict(os.environ, {"ANTIQUE_DEPLOY_MODE": "remote"}):
            assert validate_deployment_mode(None) == DeploymentMode.REMOTE


# ===========================================================================
# is_loopback_host — exact host check, not substring
# ===========================================================================


class TestLoopbackHost:
    @pytest.mark.parametrize("host", [
        "127.0.0.1",
        "localhost",
        "::1",
    ])
    def test_loopback_hosts_recognised(self, host):
        assert is_loopback_host(host) is True

    def test_zero_bind_not_loopback(self):
        """0.0.0.0 binds to all interfaces, NOT loopback — must not be
        treated as safe for fail-closed checks."""
        assert is_loopback_host("0.0.0.0") is False

    def test_evil_not_loopback(self):
        assert is_loopback_host("evil.com") is False

    def test_localhost_substring_not_loopback(self):
        """localhost.evil.com must NOT be treated as loopback."""
        assert is_loopback_host("localhost.evil.com") is False

    def test_evil_localhost_substring_not_loopback(self):
        """evil.localhost must NOT be treated as loopback."""
        assert is_loopback_host("evil.localhost") is False

    def test_127_substring_not_loopback(self):
        """127.0.0.1.evil.com must NOT be treated as loopback."""
        assert is_loopback_host("127.0.0.1.evil.com") is False

    def test_ipv6_localhost_substring_not_loopback(self):
        assert is_loopback_host("[::1].evil.com") is False


# ===========================================================================
# is_origin_allowed — exact URL origin validation, no substring bypass
# ===========================================================================


class TestOriginAllowed:
    def test_empty_origin_allowed(self):
        """Non-browser clients (curl, scripts) send no Origin."""
        assert is_origin_allowed("") is True

    @pytest.mark.parametrize("origin", [
        "http://127.0.0.1:8080",
        "http://localhost:8080",
        "https://localhost",
        "http://[::1]:8080",
    ])
    def test_loopback_origins_allowed(self, origin):
        assert is_origin_allowed(origin) is True

    def test_foreign_origin_blocked(self):
        assert is_origin_allowed("https://evil.com") is False

    def test_localhost_substring_origin_blocked(self):
        """http://localhost.evil.com must NOT pass the loopback check."""
        assert is_origin_allowed("http://localhost.evil.com") is False

    def test_127_substring_origin_blocked(self):
        """http://127.0.0.1.evil.com must NOT pass."""
        assert is_origin_allowed("http://127.0.0.1.evil.com") is False

    def test_allowlisted_origin_allowed(self):
        assert is_origin_allowed(
            "https://abc123.ngrok-free.app",
            allowed_origins=["https://abc123.ngrok-free.app"],
        ) is True

    def test_allowlist_exact_match_not_substring(self):
        """If allowed_origins contains 'ngrok-free.app', only exact origin
        'https://ngrok-free.app' is allowed, not 'https://evil.ngrok-free.app'."""
        assert is_origin_allowed(
            "https://ngrok-free.app",
            allowed_origins=["https://ngrok-free.app"],
        ) is True
        # Substring on an untrusted host must fail
        assert is_origin_allowed(
            "https://evil.ngrok-free.app",
            allowed_origins=["https://ngrok-free.app"],
        ) is False

    def test_allowlist_empty_entries_ignored(self):
        assert is_origin_allowed("https://evil.com", allowed_origins=["", "  "]) is False

    def test_allowlist_does_not_leak_to_others(self):
        assert is_origin_allowed("https://evil.com", allowed_origins=["ngrok-free.app"]) is False

    def test_malicious_origin_with_localhost_path(self):
        """https://evil.com/localhost must not pass."""
        assert is_origin_allowed("https://evil.com/localhost") is False

    def test_malicious_origin_with_localhost_query(self):
        """http://evil.com?x=localhost must not pass."""
        assert is_origin_allowed("http://evil.com?x=localhost") is False

    def test_allowlisted_with_port(self):
        assert is_origin_allowed(
            "http://192.168.1.50:8080",
            allowed_origins=["http://192.168.1.50:8080"],
        ) is True

    def test_allowlisted_scheme_mismatch_blocked(self):
        """http://example.com is not the same as https://example.com."""
        assert is_origin_allowed(
            "http://example.com",
            allowed_origins=["https://example.com"],
        ) is False


# ===========================================================================
# parse_allowed_origins — parses env var into a safe list
# ===========================================================================


class TestParseAllowedOrigins:
    def test_empty_string(self):
        assert parse_allowed_origins("") == []

    def test_single_entry(self):
        assert parse_allowed_origins("https://ngrok-free.app") == ["https://ngrok-free.app"]

    def test_multiple_entries(self):
        result = parse_allowed_origins("https://a.com,https://b.com")
        assert result == ["https://a.com", "https://b.com"]

    def test_whitespace_stripped(self):
        result = parse_allowed_origins("  https://a.com , https://b.com  ")
        assert result == ["https://a.com", "https://b.com"]

    def test_empty_entries_ignored(self):
        result = parse_allowed_origins(",  ,https://a.com,")
        assert result == ["https://a.com"]


# ===========================================================================
# generate_api_token — secure token generation
# ===========================================================================


class TestGenerateApiToken:
    def test_generates_urlsafe_string(self):
        token = generate_api_token()
        assert isinstance(token, str)
        assert len(token) >= 32
        # Must be URL-safe
        import string
        allowed = set(string.ascii_letters + string.digits + "-_")
        assert all(c in allowed for c in token)

    def test_unique_each_call(self):
        tokens = {generate_api_token() for _ in range(100)}
        assert len(tokens) == 100  # no collisions

    def test_sufficient_entropy(self):
        """Token should have at least 256 bits of entropy (32 bytes)."""
        token = generate_api_token()
        # URL-safe base64 of 32 bytes → ~43 chars
        assert len(token) >= 32


# ===========================================================================
# auth_check — mode-aware behavior
# ===========================================================================


class TestAuthCheckLocalMode:
    """In local mode: exempt paths are always open, /json and /devtools
    are exempt, no token required, local origin allowed."""

    def test_exempt_paths_always_allowed(self):
        for path in ("/health", "/docs", "/openapi.json", "/json/version", "/"):
            ok, status, _ = auth_check(path, "GET", {}, token="", mode=DeploymentMode.LOCAL)
            assert ok is True
            assert status == 200

    def test_json_exempt_in_local(self):
        ok, _, _ = auth_check("/json/list", "GET", {}, token="", mode=DeploymentMode.LOCAL)
        assert ok is True

    def test_devtools_exempt_in_local(self):
        ok, _, _ = auth_check("/devtools/page/abc/123", "GET", {}, token="", mode=DeploymentMode.LOCAL)
        assert ok is True

    def test_local_origin_no_token_allowed(self):
        ok, status, _ = auth_check(
            "/user/list", "GET",
            {"origin": "http://127.0.0.1:8080"},
            token="", mode=DeploymentMode.LOCAL,
        )
        assert ok is True
        assert status == 200

    def test_foreign_origin_blocked(self):
        ok, status, _ = auth_check(
            "/user/list", "GET",
            {"origin": "https://evil.com"},
            token="", mode=DeploymentMode.LOCAL,
        )
        assert ok is False
        assert status == 403

    def test_malicious_localhost_substring_origin_blocked(self):
        ok, status, _ = auth_check(
            "/user/list", "GET",
            {"origin": "http://localhost.evil.com"},
            token="", mode=DeploymentMode.LOCAL,
        )
        assert ok is False
        assert status == 403


class TestAuthCheckRemoteMode:
    """In remote mode: /json and /devtools require auth (not universally exempt),
    token is always required, and only allowlisted origins pass."""

    def test_health_still_exempt(self):
        ok, _, _ = auth_check("/health", "GET", {}, token="secret", mode=DeploymentMode.REMOTE)
        assert ok is True

    def test_static_assets_exempt(self):
        for path in ("/", "/manifest.json", "/sw.js"):
            ok, _, _ = auth_check(path, "GET", {}, token="secret", mode=DeploymentMode.REMOTE)
            assert ok is True

    def test_json_requires_token_in_remote(self):
        ok, status, _ = auth_check(
            "/json/version", "GET", {},
            token="secret", mode=DeploymentMode.REMOTE,
        )
        assert ok is False
        assert status == 401

    def test_json_with_correct_token_allowed_in_remote(self):
        ok, _, _ = auth_check(
            "/json/version", "GET",
            {"authorization": "Bearer secret"},
            token="secret", mode=DeploymentMode.REMOTE,
        )
        assert ok is True

    def test_devtools_requires_token_in_remote(self):
        ok, status, _ = auth_check(
            "/devtools/page/abc/123", "GET", {},
            token="secret", mode=DeploymentMode.REMOTE,
        )
        assert ok is False
        assert status == 401

    def test_devtools_with_correct_token_allowed_in_remote(self):
        ok, _, _ = auth_check(
            "/devtools/page/abc/123", "GET",
            {"authorization": "Bearer secret"},
            token="secret", mode=DeploymentMode.REMOTE,
        )
        assert ok is True

    def test_missing_token_rejected(self):
        ok, status, _ = auth_check(
            "/user/list", "GET", {},
            token="secret", mode=DeploymentMode.REMOTE,
        )
        assert ok is False
        assert status == 401

    def test_wrong_token_rejected(self):
        ok, status, _ = auth_check(
            "/user/list", "GET",
            {"authorization": "Bearer nope"},
            token="secret", mode=DeploymentMode.REMOTE,
        )
        assert ok is False
        assert status == 401

    def test_allowlisted_origin_with_token_allowed(self):
        ok, _, _ = auth_check(
            "/user/list", "GET",
            {"origin": "https://abc123.ngrok-free.app", "authorization": "Bearer secret"},
            token="secret", mode=DeploymentMode.REMOTE,
            allowed_origins=["https://abc123.ngrok-free.app"],
        )
        assert ok is True

    def test_foreign_origin_even_with_token_rejected(self):
        ok, status, _ = auth_check(
            "/user/list", "GET",
            {"origin": "https://evil.com", "authorization": "Bearer secret"},
            token="secret", mode=DeploymentMode.REMOTE,
        )
        assert ok is False
        assert status == 403


class TestAuthCheckLanMode:
    """LAN mode: /json and /devtools are exempt (like local), but token
    is required when set, and non-loopback origins must be allowlisted."""

    def test_json_exempt_in_lan(self):
        ok, _, _ = auth_check("/json/list", "GET", {}, token="", mode=DeploymentMode.LAN)
        assert ok is True

    def test_devtools_exempt_in_lan(self):
        ok, _, _ = auth_check("/devtools/page/abc/123", "GET", {}, token="", mode=DeploymentMode.LAN)
        assert ok is True

    def test_lan_origin_allowed_without_token(self):
        ok, _, _ = auth_check(
            "/user/list", "GET",
            {"origin": "http://192.168.1.50:8080"},
            token="", mode=DeploymentMode.LAN,
            allowed_origins=["http://192.168.1.50:8080"],
        )
        assert ok is True

    def test_foreign_origin_blocked(self):
        ok, status, _ = auth_check(
            "/user/list", "GET",
            {"origin": "https://evil.com"},
            token="", mode=DeploymentMode.LAN,
        )
        assert ok is False
        assert status == 403


# ===========================================================================
# Fail-closed startup validation
# ===========================================================================


class TestFailClosedStartup:
    """Remote mode without a token must refuse to start."""

    def test_remote_without_token_raises(self):
        from src.api.server import validate_startup
        with pytest.raises(RuntimeError, match="API token is required"):
            validate_startup(
                mode=DeploymentMode.REMOTE,
                host="0.0.0.0",
                api_token="",
            )

    def test_remote_with_token_ok(self):
        from src.api.server import validate_startup
        validate_startup(
            mode=DeploymentMode.REMOTE,
            host="0.0.0.0",
            api_token="some-secret-token",
        )  # no exception

    def test_remote_loopback_without_token_ok(self):
        """Even in remote mode, binding to loopback only is safe without token."""
        from src.api.server import validate_startup
        validate_startup(
            mode=DeploymentMode.REMOTE,
            host="127.0.0.1",
            api_token="",
        )  # no exception

    def test_local_without_token_ok(self):
        from src.api.server import validate_startup
        validate_startup(
            mode=DeploymentMode.LOCAL,
            host="127.0.0.1",
            api_token="",
        )  # no exception

    def test_lan_without_token_ok(self):
        """LAN mode defaults to no-token (trusted network)."""
        from src.api.server import validate_startup
        validate_startup(
            mode=DeploymentMode.LAN,
            host="0.0.0.0",
            api_token="",
        )  # no exception


# ===========================================================================
# CORS allowlist — restrictive in non-local modes
# ===========================================================================


class TestCorsConfig:
    def test_local_mode_cors_allows_all(self, tmp_path):
        """Local mode keeps the permissive '*' for dev convenience."""
        app = create_app(data_root=tmp_path, deploy_mode=DeploymentMode.LOCAL)
        # Find the CORS middleware config
        cors_mw = None
        for mw in app.user_middleware:
            if "CORSMiddleware" in str(mw.cls):
                cors_mw = mw
                break
        assert cors_mw is not None
        assert "*" in cors_mw.kwargs.get("allow_origins", [])

    def test_remote_mode_cors_restrictive(self, tmp_path):
        """Remote mode must NOT use '*'."""
        app = create_app(
            data_root=tmp_path,
            deploy_mode=DeploymentMode.REMOTE,
            api_token="test-token",
            allowed_origins=["https://abc123.ngrok-free.app"],
        )
        cors_mw = None
        for mw in app.user_middleware:
            if "CORSMiddleware" in str(mw.cls):
                cors_mw = mw
                break
        assert cors_mw is not None
        origins = cors_mw.kwargs.get("allow_origins", [])
        assert "*" not in origins
        assert "https://abc123.ngrok-free.app" in origins

    def test_lan_mode_cors_restrictive(self, tmp_path):
        app = create_app(
            data_root=tmp_path,
            deploy_mode=DeploymentMode.LAN,
            allowed_origins=["http://192.168.1.50:8080"],
        )
        cors_mw = None
        for mw in app.user_middleware:
            if "CORSMiddleware" in str(mw.cls):
                cors_mw = mw
                break
        assert cors_mw is not None
        origins = cors_mw.kwargs.get("allow_origins", [])
        assert "*" not in origins


# ===========================================================================
# End-to-end HTTP tests: local mode preserves API compatibility
# ===========================================================================


class TestLocalModeCompatibility:
    """Local default mode must preserve all existing API behavior."""

    def test_health_accessible(self, tmp_path):
        app = create_app(data_root=tmp_path)  # default = local
        client = TestClient(app)
        r = client.get("/health")
        assert r.status_code == 200

    def test_user_list_accessible_no_token(self, tmp_path):
        app = create_app(data_root=tmp_path)
        client = TestClient(app)
        r = client.get("/user/list")
        assert r.status_code == 200

    def test_info_accessible(self, tmp_path):
        app = create_app(data_root=tmp_path)
        client = TestClient(app)
        r = client.get("/info")
        assert r.status_code == 200


class TestRemoteModeHttpBehavior:
    """Remote mode HTTP-level checks."""

    def test_health_accessible_without_token(self, tmp_path):
        app = create_app(
            data_root=tmp_path,
            deploy_mode=DeploymentMode.REMOTE,
            api_token="secret",
        )
        client = TestClient(app)
        r = client.get("/health")
        assert r.status_code == 200

    def test_json_blocked_without_token(self, tmp_path):
        app = create_app(
            data_root=tmp_path,
            deploy_mode=DeploymentMode.REMOTE,
            api_token="secret",
        )
        client = TestClient(app)
        r = client.get("/json/version")
        assert r.status_code == 401

    def test_json_accessible_with_token(self, tmp_path):
        app = create_app(
            data_root=tmp_path,
            deploy_mode=DeploymentMode.REMOTE,
            api_token="secret",
        )
        client = TestClient(app)
        r = client.get("/json/version", headers={"Authorization": "Bearer secret"})
        assert r.status_code == 200

    def test_user_list_blocked_without_token(self, tmp_path):
        app = create_app(
            data_root=tmp_path,
            deploy_mode=DeploymentMode.REMOTE,
            api_token="secret",
        )
        client = TestClient(app)
        r = client.get("/user/list")
        assert r.status_code == 401

    def test_user_list_accessible_with_token(self, tmp_path):
        app = create_app(
            data_root=tmp_path,
            deploy_mode=DeploymentMode.REMOTE,
            api_token="secret",
        )
        client = TestClient(app)
        r = client.get("/user/list", headers={"Authorization": "Bearer secret"})
        assert r.status_code == 200

    def test_malicious_origin_blocked_even_with_token(self, tmp_path):
        app = create_app(
            data_root=tmp_path,
            deploy_mode=DeploymentMode.REMOTE,
            api_token="secret",
        )
        client = TestClient(app)
        r = client.get(
            "/user/list",
            headers={
                "Authorization": "Bearer secret",
                "Origin": "https://evil.com",
            },
        )
        assert r.status_code == 403

    def test_malicious_localhost_substring_origin_blocked(self, tmp_path):
        app = create_app(
            data_root=tmp_path,
            deploy_mode=DeploymentMode.REMOTE,
            api_token="secret",
        )
        client = TestClient(app)
        r = client.get(
            "/user/list",
            headers={
                "Authorization": "Bearer secret",
                "Origin": "http://localhost.evil.com",
            },
        )
        assert r.status_code == 403
