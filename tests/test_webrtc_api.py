"""HTTP-level tests for the WebRTC mode endpoints (iteration 2).

Covers GET /webrtc/modes, POST /user/{id}/webrtc, and POST /user/bulk/webrtc.
Uses FastAPI's TestClient with an isolated tmp data dir. No live browser and
no network are used: the proxy-auto-detect path is only exercised for its
validation (400) branch, never a real check_proxy call.
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


def _fp(client, uid):
    return client.get(f"/profile/{uid}").json()["data"]["fingerprint_config"]


# ---------------------------------------------------------------------------
# /webrtc/modes
# ---------------------------------------------------------------------------


def test_webrtc_modes_list(client):
    r = client.get("/webrtc/modes")
    assert r.status_code == 200, r.text
    modes = r.json()["data"]["modes"]
    assert modes == ["block", "real", "proxy"]


# ---------------------------------------------------------------------------
# POST /user/{id}/webrtc
# ---------------------------------------------------------------------------


def test_set_webrtc_real(client):
    uid = _create(client, "wrtc-real")
    r = client.post(f"/user/{uid}/webrtc", json={"mode": "real"})
    assert r.status_code == 200, r.text
    data = r.json()["data"]
    assert data["mode"] == "real"
    fp = _fp(client, uid)
    assert fp["webrtc_mode"] == "real"
    # Legacy flag kept coherent (real -> not blocking).
    assert fp["block_webrtc_ip"] is False


def test_set_webrtc_block(client):
    uid = _create(client, "wrtc-block")
    r = client.post(f"/user/{uid}/webrtc", json={"mode": "block"})
    assert r.status_code == 200, r.text
    fp = _fp(client, uid)
    assert fp["webrtc_mode"] == "block"
    assert fp["block_webrtc_ip"] is True


def test_set_webrtc_proxy_with_explicit_ip(client):
    uid = _create(client, "wrtc-proxy")
    r = client.post(f"/user/{uid}/webrtc", json={"mode": "proxy", "public_ip": "203.0.113.7"})
    assert r.status_code == 200, r.text
    data = r.json()["data"]
    assert data["mode"] == "proxy"
    assert data["public_ip"] == "203.0.113.7"
    assert data["detected_ip"] is None
    fp = _fp(client, uid)
    assert fp["webrtc_mode"] == "proxy"
    assert fp["webrtc_public_ip"] == "203.0.113.7"
    assert fp["block_webrtc_ip"] is False


def test_set_webrtc_unknown_mode_400(client):
    uid = _create(client, "wrtc-bad")
    r = client.post(f"/user/{uid}/webrtc", json={"mode": "tunnel"})
    assert r.status_code == 400, r.text


def test_set_webrtc_missing_profile_404(client):
    r = client.post("/user/does-not-exist/webrtc", json={"mode": "real"})
    assert r.status_code == 404, r.text


def test_proxy_autodetect_without_proxy_400(client):
    """proxy + detect_from_proxy on a direct profile must 400, not hit network."""
    uid = _create(client, "wrtc-direct")  # default proxy is empty/direct
    r = client.post(
        f"/user/{uid}/webrtc",
        json={"mode": "proxy", "detect_from_proxy": True},
    )
    assert r.status_code == 400, r.text


def test_webrtc_does_not_disturb_other_fingerprint_fields(client):
    """Setting the mode must preserve UA/screen/etc. (merge-safe)."""
    uid = _create(client, "wrtc-preserve")
    before = _fp(client, uid)
    client.post(f"/user/{uid}/webrtc", json={"mode": "real"})
    after = _fp(client, uid)
    for key in ("user_agent", "screen_width", "webgl_vendor", "timezone", "fonts"):
        assert before[key] == after[key]


# ---------------------------------------------------------------------------
# POST /user/bulk/webrtc
# ---------------------------------------------------------------------------


def test_bulk_webrtc_sets_all(client):
    a = _create(client, "a")
    b = _create(client, "b")
    r = client.post("/user/bulk/webrtc", json={"user_ids": [a, b], "mode": "real"})
    assert r.status_code == 200, r.text
    data = r.json()["data"]
    assert data["updated_count"] == 2
    assert _fp(client, a)["webrtc_mode"] == "real"
    assert _fp(client, b)["webrtc_mode"] == "real"


def test_bulk_webrtc_reports_missing(client):
    a = _create(client, "a")
    r = client.post("/user/bulk/webrtc", json={"user_ids": [a, "ghost"], "mode": "block"})
    assert r.status_code == 200, r.text
    data = r.json()["data"]
    assert data["updated_count"] == 1
    by_id = {row["user_id"]: row for row in data["results"]}
    assert by_id[a]["ok"] is True
    assert by_id["ghost"]["ok"] is False


def test_bulk_webrtc_proxy_ip(client):
    a = _create(client, "a")
    r = client.post(
        "/user/bulk/webrtc",
        json={"user_ids": [a], "mode": "proxy", "public_ip": "198.51.100.9"},
    )
    assert r.status_code == 200, r.text
    fp = _fp(client, a)
    assert fp["webrtc_mode"] == "proxy"
    assert fp["webrtc_public_ip"] == "198.51.100.9"


def test_bulk_webrtc_unknown_mode_400(client):
    a = _create(client, "a")
    r = client.post("/user/bulk/webrtc", json={"user_ids": [a], "mode": "xxx"})
    assert r.status_code == 400, r.text


# ---------------------------------------------------------------------------
# Backward-compat: existing update path still accepts webrtc fields directly
# ---------------------------------------------------------------------------


def test_update_fingerprint_config_carries_webrtc(client):
    uid = _create(client, "via-update")
    r = client.post("/user/update", json={
        "user_id": uid,
        "fingerprint_config": {"webrtc_mode": "proxy", "webrtc_public_ip": "192.0.2.5"},
    })
    assert r.status_code == 200, r.text
    fp = _fp(client, uid)
    assert fp["webrtc_mode"] == "proxy"
    assert fp["webrtc_public_ip"] == "192.0.2.5"
