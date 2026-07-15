"""Tests for profile sorting, clone and bulk status management."""
from fastapi.testclient import TestClient

from src.api.server import create_app
from src.core.profile import ProfileStore


def test_store_sorts_profiles_by_all_supported_keys(tmp_path):
    store = ProfileStore(tmp_path / "profiles.db")
    a = store.create(name="Zulu", group_id="2", tags=["z"], account_status="active")
    b = store.create(name="Alpha", group_id="1", tags=["a"], account_status="new")
    store.update(a.user_id, cookies=[{"name": "1"}, {"name": "2"}])
    store.update(b.user_id, cookies=[])
    for key in ("name", "id", "group", "status", "tags", "launches", "cookies", "created", "updated", "last_launched", "proxy", "engine", "live"):
        values = store.list(sort_by=key, sort_order="asc")
        assert len(values) == 2
        assert {p.user_id for p in values} == {a.user_id, b.user_id}


def test_api_sort_order_and_clone(tmp_path):
    client = TestClient(create_app(data_root=tmp_path))
    first = client.post("/user/create", json={"name": "Zulu", "tags": ["b"], "remark": "keep"}).json()["data"]["user_id"]
    second = client.post("/user/create", json={"name": "Alpha", "tags": ["a"]}).json()["data"]["user_id"]
    response = client.get("/user/list?sort_by=name&sort_order=asc&page_size=100")
    assert response.status_code == 200
    assert [p["name"] for p in response.json()["data"]["list"]] == ["Alpha", "Zulu"]
    response = client.get("/user/list?sort_by=name&sort_order=desc&page_size=100")
    assert [p["name"] for p in response.json()["data"]["list"]] == ["Zulu", "Alpha"]
    cloned = client.post("/user/clone", json={"user_id": first, "name": "Zulu copy"})
    assert cloned.status_code == 200, cloned.text
    clone_id = cloned.json()["data"]["user_id"]
    clone = client.get(f"/profile/{clone_id}").json()["data"]
    source = client.get(f"/profile/{first}").json()["data"]
    assert clone["name"] == "Zulu copy"
    assert clone["tags"] == source["tags"]
    assert clone["fingerprint_config"]["user_agent"] == source["fingerprint_config"]["user_agent"]
    assert clone["account_status"] == "new"


def test_bulk_status(tmp_path):
    client = TestClient(create_app(data_root=tmp_path))
    ids = [client.post("/user/create", json={"name": str(i)}).json()["data"]["user_id"] for i in range(2)]
    response = client.post("/user/bulk/status", json={"user_ids": ids, "account_status": "warming"})
    assert response.status_code == 200
    assert response.json()["data"]["updated_count"] == 2
    assert all(client.get(f"/profile/{uid}").json()["data"]["account_status"] == "warming" for uid in ids)
