"""HTTP-level tests for the REST API, including the new geo/proxy-pool/portable/
detect endpoints and a regression test for the ExtensionStore wiring bug.

Uses FastAPI's TestClient against a freshly-built app with an isolated tmp
data dir. No live browser is started (we don't hit /user/start).
"""
import pytest
from fastapi.testclient import TestClient

from src.api.server import create_app


@pytest.fixture
def client(tmp_path):
    app = create_app(data_root=tmp_path)
    return TestClient(app)


def _create(client, name="P", **body):
    r = client.post("/user/create", json={"name": name, **body})
    assert r.status_code == 200, r.text
    return r.json()["data"]["user_id"]


# ---------------------------------------------------------------------------
# Regression: /extension/* must not 500 due to unwired ExtensionStore
# ---------------------------------------------------------------------------


def test_extension_list_wired(client):
    """Before the fix, this 500'd on `assert _ext_store is not None`."""
    r = client.get("/extension/list")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["code"] == 0
    assert "list" in body["data"]


# ---------------------------------------------------------------------------
# Health / info version consistency
# ---------------------------------------------------------------------------


def test_health_version(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["version"] == "0.5.0"


def test_info_version(client):
    r = client.get("/info")
    assert r.status_code == 200
    assert r.json()["version"] == "0.4.0"


# ---------------------------------------------------------------------------
# Geo matching
# ---------------------------------------------------------------------------


def test_geo_countries(client):
    r = client.get("/geo/countries")
    assert r.status_code == 200
    countries = r.json()["data"]["countries"]
    assert "US" in countries and "DE" in countries


def test_geo_match_explicit_country(client):
    uid = _create(client, "geo")
    r = client.post(f"/user/{uid}/geo/match", json={"country": "DE"})
    assert r.status_code == 200, r.text
    data = r.json()["data"]
    assert data["country"] == "DE"
    assert data["timezone"] == "Europe/Berlin"
    # Persisted onto the fingerprint
    p = client.get(f"/profile/{uid}").json()["data"]
    assert p["fingerprint_config"]["timezone"] == "Europe/Berlin"
    assert p["fingerprint_config"]["spoof_geolocation"] is True


def test_geo_match_without_country_or_proxy_400(client):
    uid = _create(client, "nogeo")
    r = client.post(f"/user/{uid}/geo/match", json={})
    assert r.status_code == 400


def test_geo_match_from_proxy_country(client):
    uid = _create(client, "proxgeo", user_proxy_config={
        "proxy_type": "http", "proxy_host": "1.2.3.4", "proxy_port": 8080, "country": "JP",
    })
    r = client.post(f"/user/{uid}/geo/match", json={})
    assert r.status_code == 200, r.text
    assert r.json()["data"]["timezone"] == "Asia/Tokyo"


# ---------------------------------------------------------------------------
# Proxy pool rotation
# ---------------------------------------------------------------------------


def test_proxy_pool_next_returns_proxy(client):
    r = client.post("/proxy/pool/next", json={
        "proxy_list": "http://1.1.1.1:8080\nhttp://2.2.2.2:8080",
        "strategy": "round_robin",
    })
    assert r.status_code == 200, r.text
    assert r.json()["data"]["proxy"]["proxy_host"] in ("1.1.1.1", "2.2.2.2")


def test_proxy_pool_next_assigns_to_profile(client):
    uid = _create(client, "rot")
    r = client.post("/proxy/pool/next", json={
        "proxy_list": "socks5://9.9.9.9:1080",
        "strategy": "sticky",
        "user_id": uid,
    })
    assert r.status_code == 200, r.text
    assert r.json()["data"]["assigned"] is True
    p = client.get(f"/profile/{uid}").json()["data"]
    assert p["user_proxy_config"]["proxy_host"] == "9.9.9.9"


def test_proxy_pool_empty_list_400(client):
    r = client.post("/proxy/pool/next", json={"proxy_list": "# nothing\n", "strategy": "sticky"})
    assert r.status_code == 400


# ---------------------------------------------------------------------------
# Portable export / import round-trip
# ---------------------------------------------------------------------------


def test_portable_export_import_roundtrip(client):
    uid = _create(client, "Portable Src", tags=["a", "b"])
    exp = client.post(f"/user/{uid}/export/portable")
    assert exp.status_code == 200, exp.text
    bundle = exp.json()["data"]["bundle"]
    assert bundle["format"] == "antique-profile"
    imp = client.post("/user/import/portable", json={"bundle": bundle, "name": "Copied"})
    assert imp.status_code == 200, imp.text
    new_uid = imp.json()["data"]["user_id"]
    assert new_uid != uid
    copied = client.get(f"/profile/{new_uid}").json()["data"]
    assert copied["name"] == "Copied"
    assert copied["tags"] == ["a", "b"]


def test_portable_import_bad_bundle_400(client):
    r = client.post("/user/import/portable", json={"bundle": {"format": "nope"}})
    assert r.status_code == 400


# ---------------------------------------------------------------------------
# Detect scoring
# ---------------------------------------------------------------------------


def test_detect_score_clean_profile(client):
    signals = {
        "webdriver": False, "has_chrome": True, "has_chrome_runtime": True,
        "plugins_count": 3, "languages_count": 2, "language": "en-US",
        "platform": "Win32",
        "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/125.0.0.0",
        "hardware_concurrency": 8, "device_memory": 8,
        "timezone": "America/New_York",
        "webgl_vendor": "Google Inc. (NVIDIA)", "webgl_renderer": "ANGLE",
        "has_webgpu": True, "permission_mismatch": False,
    }
    r = client.post("/detect/score", json={"signals": signals})
    assert r.status_code == 200, r.text
    data = r.json()["data"]
    assert data["score"] == 100
    assert data["grade"] == "A"
    assert data["ok"] is True


def test_detect_score_flags_webdriver(client):
    signals = {
        "webdriver": True, "has_chrome": True, "has_chrome_runtime": True,
        "plugins_count": 3, "languages_count": 2, "platform": "Win32",
        "user_agent": "Mozilla/5.0 (Windows NT 10.0) Chrome/125",
        "hardware_concurrency": 8, "timezone": "America/New_York",
        "webgl_vendor": "Google Inc. (NVIDIA)", "permission_mismatch": False,
    }
    r = client.post("/detect/score", json={"signals": signals})
    assert r.status_code == 200
    data = r.json()["data"]
    assert data["ok"] is False
    assert any(c["name"] == "webdriver_false" for c in data["failures"])


# ---------------------------------------------------------------------------
# Browser engines
# ---------------------------------------------------------------------------


def test_engine_list(client):
    r = client.get("/engine/list")
    assert r.status_code == 200, r.text
    keys = [e["key"] for e in r.json()["data"]["list"]]
    for k in ("chromium", "chrome", "firefox", "camoufox", "webkit"):
        assert k in keys
    camo = next(e for e in r.json()["data"]["list"] if e["key"] == "camoufox")
    assert camo["stealth"] == "deep"
    assert camo["needs_install"] is True


def test_create_with_engine_persists(client):
    uid = _create(client, "eng", fingerprint_config={"browser_engine": "camoufox"})
    p = client.get(f"/profile/{uid}").json()["data"]
    assert p["fingerprint_config"]["browser_engine"] == "camoufox"


# ---------------------------------------------------------------------------
# AdsPower backup import (synthetic backup dir)
# ---------------------------------------------------------------------------


def _make_fake_backup(tmp_path):
    """Build a minimal AdsPower-shaped backup dir: index + json cookies."""
    import json
    root = tmp_path / "ads_backup"
    root.mkdir()
    (root / "all_profiles_list.json").write_text(json.dumps([
        {"user_id": "aaa11111", "name": "Acc One", "group_id": "5",
         "fbcc_user_tag": ["warm"], "user_proxy_config": {"proxy_soft": "no_proxy"}},
        {"user_id": "bbb22222", "name": "Acc Two", "group_id": "5",
         "user_proxy_config": {"proxy_type": "http", "proxy_host": "1.2.3.4", "proxy_port": 8080}},
    ]), encoding="utf-8")
    jc = root / "json_cookies"
    jc.mkdir()
    (jc / "aaa11111_cookies.json").write_text(json.dumps([
        {"name": "sid", "value": "x", "domain": ".example.com", "path": "/"}
    ]), encoding="utf-8")
    return root


def test_adspower_backup_import(client, tmp_path):
    root = _make_fake_backup(tmp_path)
    r = client.post("/user/import/backup", json={"source_path": str(root)})
    assert r.status_code == 200, r.text
    d = r.json()["data"]
    assert d["imported_count"] == 2
    # AdsPower user_id preserved
    p = client.get("/profile/aaa11111").json()["data"]
    assert p["name"] == "Acc One"
    assert p["group_id"] == "5"
    assert "warm" in p["tags"]
    assert len(p["cookies"]) == 1
    # second profile got its proxy
    p2 = client.get("/profile/bbb22222").json()["data"]
    assert p2["user_proxy_config"]["proxy_host"] == "1.2.3.4"


def test_adspower_backup_import_skips_existing(client, tmp_path):
    root = _make_fake_backup(tmp_path)
    client.post("/user/import/backup", json={"source_path": str(root)})
    r = client.post("/user/import/backup", json={"source_path": str(root)})
    d = r.json()["data"]
    assert d["skipped_count"] == 2 and d["imported_count"] == 0
    r2 = client.post("/user/import/backup", json={"source_path": str(root), "overwrite": True})
    assert r2.json()["data"]["updated_count"] == 2

