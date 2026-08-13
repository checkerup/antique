"""Tests for first-class proxy provider adapters."""
import json

import pytest

from src.core.providers import ProviderConfig, ProxyProvider, list_provider_kinds


def test_provider_kinds_include_vendor_adapters():
    kinds = list_provider_kinds()
    assert {"brightdata", "decodo", "smartproxy"}.issubset(kinds)


def test_disabled_provider_returns_empty(tmp_path):
    path = tmp_path / "pool.txt"
    path.write_text("http://1.2.3.4:8080\n", encoding="utf-8")
    assert ProxyProvider(ProviderConfig("off", "file", str(path), enabled=False)).fetch() == []


@pytest.mark.parametrize("kind,env_name", [
    ("brightdata", "BRIGHTDATA_API_KEY"),
    ("decodo", "DECODO_API_KEY"),
    ("smartproxy", "SMARTPROXY_API_KEY"),
])
def test_vendor_adapter_sends_bearer_token(monkeypatch, kind, env_name):
    seen = {}

    class Response:
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def read(self): return json.dumps({"data": [{"host": "proxy.test", "port": 9000, "protocol": "http"}]}).encode()

    def fake_urlopen(request, timeout=0):
        seen["url"] = request.full_url
        seen["auth"] = request.headers.get("Authorization")
        return Response()

    monkeypatch.setenv(env_name, "secret")
    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    values = ProxyProvider(ProviderConfig("vendor", kind, "https://vendor.test/pool", params={"limit": "2"})).fetch()
    assert values == ["http://proxy.test:9000"]
    assert seen["auth"] == "Bearer secret"
    assert "limit=2" in seen["url"]


def test_explicit_api_key_overrides_environment(monkeypatch):
    seen = {}

    class Response:
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def read(self): return b'{"proxies": ["socks5://proxy:1"]}'

    def fake_urlopen(request, timeout=0):
        seen["auth"] = request.headers.get("Authorization")
        return Response()

    monkeypatch.setenv("DECODO_API_KEY", "env-secret")
    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    values = ProxyProvider(ProviderConfig("d", "decodo", "https://x", api_key="explicit")).fetch()
    assert values == ["socks5://proxy:1"]
    assert seen["auth"] == "Bearer explicit"


def test_vendor_requires_api_key(monkeypatch):
    monkeypatch.delenv("SMARTPROXY_API_KEY", raising=False)
    with pytest.raises(ValueError, match="requires api_key"):
        ProxyProvider(ProviderConfig("s", "smartproxy", "https://x")).fetch()


def test_normalizes_nested_host_port_payload():
    payload = {"results": [{"host": "h", "port": 2, "type": "socks5", "username": "u", "password": "p"}]}
    assert ProxyProvider._extract_proxy_urls(payload) == ["socks5://u:p@h:2"]


def test_normalizes_common_payload_shapes():
    assert ProxyProvider._extract_proxy_urls({"url": "http://a:1"}) == ["http://a:1"]
    assert ProxyProvider._extract_proxy_urls(["http://a:1", {"url": "http://b:2"}]) == ["http://a:1", "http://b:2"]


def test_api_accepts_vendor_provider(monkeypatch, tmp_path):
    from fastapi.testclient import TestClient
    from src.api.server import create_app

    class Response:
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def read(self): return b'{"proxies": ["http://proxy:8"]}'

    monkeypatch.setattr("urllib.request.urlopen", lambda *args, **kwargs: Response())
    response = TestClient(create_app(data_root=tmp_path)).post(
        "/proxy/providers/test",
        json={"name": "b", "kind": "brightdata", "source": "https://x", "api_key": "k"},
    )
    assert response.status_code == 200
    assert response.json()["data"]["proxies"] == ["http://proxy:8"]
