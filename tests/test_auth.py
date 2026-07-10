"""Tests for the API auth + origin guard (server.auth_check / is_local_origin).

Covers the DNS-rebinding guard, the optional Bearer token, and the new
``ANTIQUE_ALLOWED_ORIGINS`` allow-list used for remote/tunnel (ngrok) access.
"""
import pytest

from src.api.server import auth_check, is_local_origin


# ---------------------------------------------------------------------------
# is_local_origin
# ---------------------------------------------------------------------------


def test_empty_origin_is_allowed():
    # curl / scripts send no Origin.
    assert is_local_origin("") is True


@pytest.mark.parametrize("origin", [
    "http://127.0.0.1:8080",
    "http://localhost:8080",
    "https://localhost",
    "http://[::1]:8080",
    "http://0.0.0.0:8080",
])
def test_localhost_origins_allowed(origin):
    assert is_local_origin(origin) is True


def test_foreign_origin_blocked():
    assert is_local_origin("https://evil.com") is False


def test_allowlisted_origin_allowed():
    assert is_local_origin("https://abc123.ngrok-free.app", ["ngrok-free.app"]) is True


def test_allowlist_does_not_leak_to_others():
    assert is_local_origin("https://evil.com", ["ngrok-free.app"]) is False


def test_allowlist_empty_entries_ignored():
    assert is_local_origin("https://evil.com", ["", "  "]) is False


# ---------------------------------------------------------------------------
# auth_check
# ---------------------------------------------------------------------------


def test_exempt_paths_always_allowed():
    for path in ("/health", "/docs", "/openapi.json", "/json/version", "/"):
        ok, status, _ = auth_check(path, "GET", {}, token="")
        assert ok is True
        assert status == 200


def test_foreign_origin_rejected():
    ok, status, _ = auth_check(
        "/user/list", "GET", {"origin": "https://evil.com"}, token=""
    )
    assert ok is False
    assert status == 403


def test_local_origin_no_token_allowed():
    ok, status, _ = auth_check(
        "/user/list", "GET", {"origin": "http://127.0.0.1:8080"}, token=""
    )
    assert ok is True
    assert status == 200


def test_token_required_when_set():
    ok, status, _ = auth_check(
        "/user/list", "GET", {"origin": "http://localhost"}, token="secret"
    )
    assert ok is False
    assert status == 401


def test_token_accepted_when_correct():
    ok, status, _ = auth_check(
        "/user/list", "GET",
        {"origin": "http://localhost", "authorization": "Bearer secret"},
        token="secret",
    )
    assert ok is True
    assert status == 200


def test_token_wrong_value_rejected():
    ok, status, _ = auth_check(
        "/user/list", "GET",
        {"origin": "http://localhost", "authorization": "Bearer nope"},
        token="secret",
    )
    assert ok is False
    assert status == 401


def test_tunnel_origin_allowed_via_allowlist():
    # The ngrok scenario: dashboard served through a tunnel domain.
    ok, status, _ = auth_check(
        "/user/list", "GET",
        {"origin": "https://abc123.ngrok-free.app"},
        token="",
        allowed_origins=["ngrok-free.app"],
    )
    assert ok is True
    assert status == 200


def test_tunnel_origin_still_needs_token_when_set():
    ok, status, _ = auth_check(
        "/user/list", "GET",
        {"origin": "https://abc123.ngrok-free.app"},
        token="secret",
        allowed_origins=["ngrok-free.app"],
    )
    assert ok is False
    assert status == 401


def test_header_case_insensitive():
    ok, status, _ = auth_check(
        "/user/list", "GET",
        {"Origin": "http://localhost", "Authorization": "Bearer secret"},
        token="secret",
    )
    assert ok is True
