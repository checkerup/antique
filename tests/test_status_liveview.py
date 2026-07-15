"""Tests for account status, Live View (screenshot) and real-CDP helpers.

Status is pure data (no browser). Live View / CDP are tested at the launcher
level with a fake in-memory handle, and at the API level for the not-running
guard paths.
"""
import pytest
from fastapi.testclient import TestClient

from src.api.server import create_app
from src.core.browser import BrowserHandle, BrowserLauncher
from src.core.profile import ProfileStore


@pytest.fixture
def client(tmp_path):
    return TestClient(create_app(data_root=tmp_path))


def _create(client, name="P", **body):
    r = client.post("/user/create", json={"name": name, **body})
    assert r.status_code == 200, r.text
    return r.json()["data"]["user_id"]


# ---------------------------------------------------------------------------
# Account status (pure data via store)
# ---------------------------------------------------------------------------


def test_store_status_default_and_update(tmp_path):
    store = ProfileStore(db_path=tmp_path / "t.db")
    p = store.create(name="acc")
    assert p.account_status == "new"
    store.update(p.user_id, account_status="banned")
    assert store.get(p.user_id).account_status == "banned"


def test_store_status_filter(tmp_path):
    store = ProfileStore(db_path=tmp_path / "t.db")
    store.create(name="a", account_status="active")
    store.create(name="b", account_status="banned")
    store.create(name="c", account_status="active")
    assert len(store.list(account_status="active")) == 2
    assert len(store.list(account_status="banned")) == 1


# ---------------------------------------------------------------------------
# Status API
# ---------------------------------------------------------------------------


def test_status_list_endpoint(client):
    r = client.get("/status/list")
    assert r.status_code == 200
    st = r.json()["data"]["statuses"]
    assert "active" in st and "banned" in st


def test_create_and_set_status(client):
    uid = _create(client, "s", account_status="warming")
    p = client.get(f"/profile/{uid}").json()["data"]
    assert p["account_status"] == "warming"
    r = client.post(f"/user/{uid}/status", json={"account_status": "active"})
    assert r.status_code == 200
    assert r.json()["data"]["account_status"] == "active"
    assert client.get(f"/profile/{uid}").json()["data"]["account_status"] == "active"


def test_list_filter_by_status(client):
    _create(client, "a", account_status="active")
    _create(client, "b", account_status="banned")
    r = client.get("/user/list?account_status=active")
    rows = r.json()["data"]["list"]
    assert len(rows) == 1 and rows[0]["account_status"] == "active"


def test_set_status_missing_404(client):
    r = client.post("/user/nope/status", json={"account_status": "active"})
    assert r.status_code == 404


# ---------------------------------------------------------------------------
# Live View + CDP guard paths (API, not running)
# ---------------------------------------------------------------------------


def test_screenshot_not_running_409(client):
    uid = _create(client, "x")
    r = client.post(f"/user/{uid}/screenshot")
    assert r.status_code == 409


def test_cdp_not_running_409(client):
    uid = _create(client, "x")
    r = client.get(f"/user/{uid}/cdp")
    assert r.status_code == 409


# ---------------------------------------------------------------------------
# Launcher-level Live View + CDP with a fake handle (no real browser)
# ---------------------------------------------------------------------------


class _FakePage:
    async def screenshot(self, full_page=False):
        return b"\x89PNG\r\n\x1a\n-fake"


class _FakeContext:
    def __init__(self):
        self.pages = [_FakePage()]


@pytest.mark.asyncio
async def test_launcher_screenshot_with_fake_handle(tmp_path):
    store = ProfileStore(db_path=tmp_path / "t.db")
    launcher = BrowserLauncher(store, data_root=tmp_path)
    launcher._live["u1"] = BrowserHandle(
        user_id="u1", session_id="s", debug_port=0, ws_endpoint="", pid=None,
        context=_FakeContext(),
    )
    buf = await launcher.screenshot("u1")
    assert buf and buf.startswith(b"\x89PNG")
    # not running -> None
    assert await launcher.screenshot("nope") is None


def test_launcher_real_cdp_info_not_running(tmp_path):
    store = ProfileStore(db_path=tmp_path / "t.db")
    launcher = BrowserLauncher(store, data_root=tmp_path)
    assert launcher.real_cdp_info("nope") is None


# ---------------------------------------------------------------------------
# Sync API validation
# ---------------------------------------------------------------------------


def test_sync_bad_flow_400(client):
    r = client.post("/sync/run", json={"user_ids": ["a"], "flow": []})
    assert r.status_code == 400  # empty flow rejected by parse_flow


def test_sync_missing_profiles_reported(client):
    # Valid flow, but profiles aren't running -> each comes back failed, 200.
    r = client.post("/sync/run", json={
        "user_ids": ["ghost1", "ghost2"],
        "flow": [{"action": "goto", "url": "https://example.com"}],
    })
    assert r.status_code == 200, r.text
    d = r.json()["data"]
    assert d["total"] == 2 and d["succeeded"] == 0 and d["ok"] is False
