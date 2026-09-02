"""TDD tests for P0/P1 security hardening.

Covers:
1. Constant-time token comparison (hmac.compare_digest) in auth_check.
2. WebSocket auth on /devtools/page/{user_id}/{target_id}.
3. Credential masking on API response endpoints (proxy_user + proxy_password).
4. Eval endpoint guard — eval automation step gated by ANTIQUE_ALLOW_EVAL.

These tests are written FIRST (RED), then code is changed to make them GREEN.
"""
from __future__ import annotations

import os
import hmac
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from src.api.server import auth_check, create_app
from src.core.security import DeploymentMode


# ===========================================================================
# P0-1: Constant-time token comparison
# ===========================================================================


class TestConstantTimeTokenCompare:
    """auth_check must use hmac.compare_digest, not ==, for token comparison."""

    def test_correct_token_succeeds(self):
        ok, status, _ = auth_check(
            "/user/list", "GET",
            {"origin": "http://localhost", "authorization": "Bearer secret"},
            token="secret",
        )
        assert ok is True
        assert status == 200

    def test_wrong_token_rejected(self):
        ok, status, _ = auth_check(
            "/user/list", "GET",
            {"origin": "http://localhost", "authorization": "Bearer wrong"},
            token="secret",
        )
        assert ok is False
        assert status == 401

    def test_partial_prefix_token_rejected(self):
        """A token that is a prefix of the expected token must NOT pass."""
        ok, status, _ = auth_check(
            "/user/list", "GET",
            {"origin": "http://localhost", "authorization": "Bearer sec"},
            token="secret",
        )
        assert ok is False
        assert status == 401

    def test_token_with_extra_chars_rejected(self):
        """A token that has the expected as prefix + extra must NOT pass."""
        ok, status, _ = auth_check(
            "/user/list", "GET",
            {"origin": "http://localhost", "authorization": "Bearer secretx"},
            token="secret",
        )
        assert ok is False
        assert status == 401

    def test_no_authorization_header_rejected_when_token_set(self):
        ok, status, _ = auth_check(
            "/user/list", "GET",
            {"origin": "http://localhost"},
            token="secret",
        )
        assert ok is False
        assert status == 401

    def test_uses_compare_digest_not_eq(self):
        """Verify the implementation calls hmac.compare_digest by monkeypatching."""
        called = {"compare_digest": False}
        orig = hmac.compare_digest

        def spy(a, b):
            called["compare_digest"] = True
            return orig(a, b)

        with patch.object(hmac, "compare_digest", side_effect=spy):
            auth_check(
                "/user/list", "GET",
                {"origin": "http://localhost", "authorization": "Bearer secret"},
                token="secret",
            )
        assert called["compare_digest"] is True, "auth_check must use hmac.compare_digest"


# ===========================================================================
# P0-2: WebSocket auth on /devtools/page/{user_id}/{target_id}
# ===========================================================================


class TestWebSocketAuth:
    """The CDP WebSocket endpoint must enforce auth in remote mode."""

    def test_ws_rejected_without_token_in_remote(self, tmp_path):
        """In remote mode, the WS handshake must fail without a Bearer token.
        Must get 4401 (auth failure), NOT 4404 (target not found)."""
        app = create_app(
            data_root=tmp_path,
            deploy_mode=DeploymentMode.REMOTE,
            api_token="secret",
        )
        client = TestClient(app)
        try:
            with client.websocket_connect("/devtools/page/u1/t1") as ws:
                pytest.fail("WebSocket should have been rejected without token")
        except Exception as e:
            code = getattr(e, "code", None)
            assert code == 4401, (
                f"Expected 4401 (auth required) but got code={code}. "
                f"WebSocket auth is not enforced before target lookup."
            )

    def test_ws_rejected_with_wrong_token_in_remote(self, tmp_path):
        """Wrong token must also yield 4401."""
        app = create_app(
            data_root=tmp_path,
            deploy_mode=DeploymentMode.REMOTE,
            api_token="secret",
        )
        client = TestClient(app)
        try:
            with client.websocket_connect(
                "/devtools/page/u1/t1",
                headers={"Authorization": "Bearer wrong"},
            ) as ws:
                pytest.fail("WebSocket should have been rejected with wrong token")
        except Exception as e:
            code = getattr(e, "code", None)
            assert code == 4401, (
                f"Expected 4401 (auth required) but got code={code}."
            )

    def test_ws_accepted_with_token_then_4404_in_remote(self, tmp_path):
        """With a valid token, auth passes; then 4404 because target doesn't exist."""
        app = create_app(
            data_root=tmp_path,
            deploy_mode=DeploymentMode.REMOTE,
            api_token="secret",
        )
        client = TestClient(app)
        try:
            with client.websocket_connect(
                "/devtools/page/u1/t1",
                headers={"Authorization": "Bearer secret"},
            ) as ws:
                pytest.fail("Expected 4404 (target not found)")
        except Exception as e:
            code = getattr(e, "code", None)
            assert code == 4404, (
                f"Expected 4404 (target not found) but got code={code}. "
                f"Auth passed but target lookup should fail."
            )

    def test_ws_no_auth_needed_in_local(self, tmp_path):
        """In local mode, WS is exempt (like /json and /devtools HTTP).
        Should get 4404 (target not found), not 4401 (auth)."""
        app = create_app(data_root=tmp_path)  # local
        client = TestClient(app)
        try:
            with client.websocket_connect("/devtools/page/u1/t1") as ws:
                pytest.fail("Expected 4404 (target not found)")
        except Exception as e:
            code = getattr(e, "code", None)
            assert code == 4404, (
                f"Expected 4404 (target not found) in local mode but got code={code}."
            )


# ===========================================================================
# P1-1: Credential masking — proxy_user must be masked in API responses
# ===========================================================================


class TestCredentialMasking:
    """proxy_user must be masked in API responses just like proxy_password."""

    def test_profile_response_masks_proxy_user(self, tmp_path):
        """_profile_to_adspower_shape must mask proxy_user."""
        from src.api.routes import _profile_to_adspower_shape
        from types import SimpleNamespace

        p = SimpleNamespace(
            user_id="u1", name="test", group_id="0",
            due_date=None, created_at=None, updated_at=None,
            last_launched_at=None, launch_count=0,
            remark="", tags=[], account_status="new",
            proxy={
                "proxy_type": "http",
                "proxy_host": "1.2.3.4",
                "proxy_port": 8080,
                "proxy_user": "mysecretuser",
                "proxy_password": "mysecretpass",
            },
            fingerprint={}, cookies=[],
            running_debug_port=None, running_ws=None,
        )
        result = _profile_to_adspower_shape(p)
        proxy = result["user_proxy_config"]
        assert proxy["proxy_password"] == "****"
        assert proxy["proxy_user"] == "****"

    def test_proxy_pool_next_masks_credentials(self, tmp_path):
        """The /proxy/pool/next response must not leak proxy_user/password."""
        app = create_app(data_root=tmp_path)
        client = TestClient(app)
        r = client.post("/proxy/pool/next", json={
            "proxy_list": "http://secretuser:secretpass@1.2.3.4:8080",
            "strategy": "round_robin",
        })
        assert r.status_code == 200, r.text
        proxy = r.json()["data"]["proxy"]
        assert proxy.get("proxy_user") == "****"
        assert proxy.get("proxy_password") == "****"

    def test_proxy_check_does_not_leak_credentials(self, tmp_path):
        """The /proxy/check response must not echo proxy_user/password."""
        app = create_app(data_root=tmp_path)
        client = TestClient(app)
        r = client.post("/proxy/check", json={
            "user_proxy_config": {
                "proxy_type": "http",
                "proxy_host": "1.2.3.4",
                "proxy_port": 8080,
                "proxy_user": "leakeduser",
                "proxy_password": "leakedpass",
            },
        })
        # The response should not echo credentials. It may return an error
        # (proxy unreachable) but the body must not contain the raw credentials.
        body_text = r.text
        assert "leakeduser" not in body_text
        assert "leakedpass" not in body_text

    def test_user_proxy_check_masks_credentials(self, tmp_path):
        """The /user/{user_id}/proxy/check response must not leak credentials."""
        app = create_app(data_root=tmp_path)
        client = TestClient(app)
        # Create a profile with proxy credentials
        r = client.post("/user/create", json={
            "name": "proxytest",
            "user_proxy_config": {
                "proxy_type": "http",
                "proxy_host": "1.2.3.4",
                "proxy_port": 8080,
                "proxy_user": "secretuser",
                "proxy_password": "secretpass",
            },
        })
        uid = r.json()["data"]["user_id"]
        r2 = client.post(f"/user/{uid}/proxy/check")
        body_text = r2.text
        assert "secretuser" not in body_text
        assert "secretpass" not in body_text


# ===========================================================================
# P1-2: Eval endpoint guard — eval step gated by ANTIQUE_ALLOW_EVAL
# ===========================================================================


class TestEvalGuard:
    """The 'eval' automation step must be disabled unless ANTIQUE_ALLOW_EVAL=1."""

    def test_eval_step_rejected_by_default(self):
        """Without ANTIQUE_ALLOW_EVAL, parse_flow must reject eval steps."""
        from src.core.automation import parse_flow, FlowValidationError
        with patch.dict(os.environ, {}, clear=True):
            # Ensure ANTIQUE_ALLOW_EVAL is not set
            os.environ.pop("ANTIQUE_ALLOW_EVAL", None)
            with pytest.raises(FlowValidationError, match="eval.*disabled"):
                parse_flow([
                    {"action": "goto", "url": "https://example.com"},
                    {"action": "eval", "script": "document.title"},
                ])

    def test_eval_step_allowed_when_env_set(self):
        """With ANTIQUE_ALLOW_EVAL=1, eval steps are accepted."""
        from src.core.automation import parse_flow
        with patch.dict(os.environ, {"ANTIQUE_ALLOW_EVAL": "1"}):
            steps = parse_flow([
                {"action": "goto", "url": "https://example.com"},
                {"action": "eval", "script": "document.title"},
            ])
            assert len(steps) == 2
            assert steps[1].action == "eval"

    def test_other_steps_unaffected(self):
        """Non-eval steps must work regardless of the flag."""
        from src.core.automation import parse_flow
        with patch.dict(os.environ, {}, clear=True):
            os.environ.pop("ANTIQUE_ALLOW_EVAL", None)
            steps = parse_flow([
                {"action": "goto", "url": "https://example.com"},
                {"action": "wait", "ms": 500},
                {"action": "scroll", "to": "bottom"},
            ])
            assert len(steps) == 3

    def test_sync_run_rejects_eval_by_default(self, tmp_path):
        """The /sync/run endpoint must reject flows containing eval by default."""
        app = create_app(data_root=tmp_path)
        client = TestClient(app)
        r = client.post("/sync/run", json={
            "user_ids": [],
            "flow": [
                {"action": "goto", "url": "https://example.com"},
                {"action": "eval", "script": "1+1"},
            ],
        })
        assert r.status_code == 400
        assert "eval" in r.text.lower()
