"""Tests for Chrome Web Store search and install UI/API integration."""
import json
from pathlib import Path

import pytest

from src.core.extension import ExtensionStore


HTML = '''
<a href="/detail/aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa/u-block-origin">uBlock Origin</a>
<a href="/detail/bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb/password-manager">Password Manager</a>
<a href="/detail/aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa/u-block-origin">duplicate</a>
'''


class Response:
    def __enter__(self): return self
    def __exit__(self, *args): pass
    def read(self): return HTML.encode()


def test_search_webstore_extracts_unique_ids_and_limit(monkeypatch, tmp_path):
    seen = {}
    def fake_urlopen(request, timeout=0):
        seen["url"] = request.full_url
        seen["ua"] = request.headers.get("User-agent")
        return Response()
    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    store = ExtensionStore(tmp_path)
    results = store.search_webstore("u block", limit=1)
    assert len(results) == 1
    assert results[0]["webstore_id"] == "a" * 32
    assert "u%20block" in seen["url"]
    assert seen["ua"] == "antique-extension-search/1"


def test_search_requires_query(tmp_path):
    with pytest.raises(ValueError, match="query"):
        ExtensionStore(tmp_path).search_webstore("")


def test_search_limit_is_clamped(monkeypatch, tmp_path):
    monkeypatch.setattr("urllib.request.urlopen", lambda *args, **kwargs: Response())
    results = ExtensionStore(tmp_path).search_webstore("x", limit=999)
    assert len(results) == 2


def test_search_api(monkeypatch, tmp_path):
    from fastapi.testclient import TestClient
    from src.api.server import create_app
    monkeypatch.setattr("urllib.request.urlopen", lambda *args, **kwargs: Response())
    response = TestClient(create_app(data_root=tmp_path)).get("/extension/webstore/search?q=ublock&limit=5")
    assert response.status_code == 200
    assert response.json()["data"]["count"] == 2
    assert response.json()["data"]["results"][0]["webstore_id"] == "a" * 32


def test_search_api_rejects_blank_query(tmp_path):
    from fastapi.testclient import TestClient
    from src.api.server import create_app
    response = TestClient(create_app(data_root=tmp_path)).get("/extension/webstore/search?q=")
    assert response.status_code == 422


def test_dashboard_has_webstore_search():
    html = (Path(__file__).parent.parent / "src/ui/templates/index.html").read_text(encoding="utf-8") + "\n" + (Path(__file__).parent.parent / "src/ui/templates/assets/app.js").read_text(encoding="utf-8")
    assert "/extension/webstore/search" in html
    assert "searchWebStore" in html
    assert "installWebStore" in html
