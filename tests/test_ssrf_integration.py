"""Tests that SSRF guard is wired into provider and webhook fetches.

These verify that ``ProxyProvider._fetch_remote_json`` and ``notify._post``
reject URLs that the outbound guard flags, before any network call happens.
"""
import json
import pytest

from src.core.notify import WebhookConfig, _post, send_event
from src.core.providers import ProviderConfig, ProxyProvider


class TestProviderSSRFGuard:
    """Provider remote fetch must reject internal/metadata URLs."""

    def test_metadata_url_rejected_before_network(self, monkeypatch):
        """If the guard fires, urlopen must never be called."""
        called = {"urlopen": False}

        def fake_urlopen(*args, **kwargs):
            called["urlopen"] = True
            raise AssertionError("urlopen should not be called for SSRF-blocked URL")

        monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

        cfg = ProviderConfig(
            "aws-md", "http-json",
            "http://169.254.169.254/latest/meta-data/",
        )
        from src.core.outbound_guard import SSRFError
        with pytest.raises(SSRFError):
            ProxyProvider(cfg).fetch()

        assert not called["urlopen"], "urlopen was called despite SSRF guard"

    def test_localhost_provider_url_rejected(self):
        cfg = ProviderConfig("local", "http-json", "http://127.0.0.1:8080/admin")
        from src.core.outbound_guard import SSRFError
        with pytest.raises(SSRFError):
            ProxyProvider(cfg).fetch()

    def test_private_range_url_rejected(self):
        cfg = ProviderConfig("internal", "http-json", "http://10.0.0.1/proxies")
        from src.core.outbound_guard import SSRFError
        with pytest.raises(SSRFError):
            ProxyProvider(cfg).fetch()

    def test_public_url_still_works(self, monkeypatch):
        """Public URL must still pass the guard and reach urlopen."""
        class Response:
            def __enter__(self): return self
            def __exit__(self, *a): pass
            def read(self): return json.dumps({"proxies": ["http://proxy.test:8080"]}).encode()

        monkeypatch.setattr("urllib.request.urlopen", lambda *a, **kw: Response())
        cfg = ProviderConfig("ok", "http-json", "https://api.example.com/v1/proxies")
        result = ProxyProvider(cfg).fetch()
        assert result == ["http://proxy.test:8080"]

    def test_file_provider_not_affected_by_guard(self, tmp_path):
        """file-based providers must not be filtered by the SSRF guard."""
        path = tmp_path / "pool.txt"
        path.write_text("http://1.2.3.4:8080\nhttp://5.6.7.8:8080\n", encoding="utf-8")
        cfg = ProviderConfig("file", "file", str(path))
        result = ProxyProvider(cfg).fetch()
        assert len(result) == 2


class TestWebhookSSRFGuard:
    """Webhook delivery must reject internal/metadata URLs."""

    def test_metadata_webhook_url_rejected(self):
        from src.core.outbound_guard import SSRFError
        cfg = WebhookConfig(
            url="http://169.254.169.254/latest/meta-data/",
            kind="generic",
            enabled=True,
        )
        result = send_event(cfg, "profile_start", {"name": "test"})
        assert result["sent"] is False
        assert "SSRF" in result.get("reason", "") or "blocked" in result.get("reason", "").lower()

    def test_localhost_webhook_url_rejected(self):
        cfg = WebhookConfig(
            url="http://127.0.0.1:8080/admin",
            kind="generic",
            enabled=True,
        )
        result = send_event(cfg, "profile_start", {"name": "test"})
        assert result["sent"] is False

    def test_private_range_webhook_url_rejected(self):
        cfg = WebhookConfig(
            url="http://192.168.1.1/internal",
            kind="discord",
            enabled=True,
        )
        result = send_event(cfg, "profile_crash", {"name": "test"})
        assert result["sent"] is False

    def test_public_webhook_url_works(self, monkeypatch):
        """Public URL must still attempt delivery."""
        seen = {}

        def fake_post(url, payload):
            seen["url"] = url
            seen["payload"] = payload
            return 200

        cfg = WebhookConfig(
            url="https://discord.com/api/webhooks/123/abc",
            kind="discord",
            enabled=True,
        )
        result = send_event(cfg, "profile_start", {"name": "test"}, sender=fake_post)
        assert result["sent"] is True
        assert result["status"] == 200
        assert "discord.com" in seen["url"]

    def test_ssrf_blocked_url_never_calls_sender(self):
        """The sender (network function) must never be called for blocked URLs."""
        called = {"sender": False}

        def fake_sender(url, payload):
            called["sender"] = True
            return 200

        cfg = WebhookConfig(
            url="http://169.254.169.254/",
            kind="generic",
            enabled=True,
        )
        send_event(cfg, "profile_start", {"name": "test"}, sender=fake_sender)
        assert not called["sender"], "sender was called despite SSRF guard"
