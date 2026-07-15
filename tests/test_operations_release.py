"""Offline tests for the competitor-parity operations release."""
import json

from fastapi.testclient import TestClient

from src.api.server import create_app
from src.core.operations import create_from_template, list_activity
from src.core.profile import ProfileStore
from src.core.providers import ProviderConfig, ProxyProvider


def test_template_create_makes_coherent_batch(tmp_path):
    store = ProfileStore(tmp_path / "db.sqlite")
    profiles = create_from_template(store, {"name": "batch", "group_id": "g", "tags": ["seed"]}, 3, seed="x")
    assert [p.name for p in profiles] == ["batch-001", "batch-002", "batch-003"]
    assert all(p.fingerprint for p in profiles)


def test_activity_table_and_provider_file(tmp_path):
    store = ProfileStore(tmp_path / "db.sqlite")
    p = store.create(name="audit")
    from src.core.operations import record_activity
    record_activity(store, p.user_id, "test", {"ok": True})
    events = list_activity(store, p.user_id)
    assert events[0].action == "test"
    proxy_file = tmp_path / "proxies.txt"
    proxy_file.write_text("http://1.2.3.4:8080\n# skip\n", encoding="utf-8")
    assert ProxyProvider(ProviderConfig("local", "file", str(proxy_file))).fetch() == ["http://1.2.3.4:8080"]


def test_operations_endpoints_template_resource_mcp_and_group(tmp_path):
    client = TestClient(create_app(data_root=tmp_path))
    response = client.post("/user/template/create", json={"template": {"name": "mass"}, "count": 2, "seed": "t"})
    assert response.status_code == 200
    assert response.json()["data"]["created_count"] == 2
    resource = client.get("/resource/status")
    assert resource.status_code == 200
    assert "rss_kb" in resource.json()["data"]
    assert client.get("/mcp/status").json()["data"]["status"] == "available"
    assert client.post("/group/create", json={"group_id": "x", "name": "X"}).status_code == 200
    assert any(g["group_id"] == "x" for g in client.get("/group/list").json()["data"]["list"])


def test_provider_http_json(monkeypatch):
    class Response:
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def read(self): return b'{"data": [{"url": "http://x:1"}]}'
    monkeypatch.setattr("urllib.request.urlopen", lambda *args, **kwargs: Response())
    assert ProxyProvider(ProviderConfig("remote", "http-json", "https://provider.test/pool")).fetch() == ["http://x:1"]


def test_provider_json(tmp_path):
    path = tmp_path / "pool.json"
    path.write_text(json.dumps({"proxies": [{"url": "socks5://u:p@x:1"}]}), encoding="utf-8")
    client = TestClient(create_app(data_root=tmp_path / "data"))
    response = client.post("/proxy/providers/test", json={"name": "p", "kind": "json", "source": str(path)})
    assert response.status_code == 200
    assert response.json()["data"]["count"] == 1


def test_backup_schedule_roundtrip(tmp_path):
    from src.core.backup_scheduler import add_schedule, list_schedules
    store = ProfileStore(tmp_path / "db.sqlite")
    item = add_schedule(store, str(tmp_path / "backup.enc"), 60)
    assert item.schedule_id
    assert list_schedules(store)[0].destination.endswith("backup.enc")


def test_api_actions_are_audited(tmp_path):
    client = TestClient(create_app(data_root=tmp_path))
    uid = client.post("/user/create", json={"name": "audited"}).json()["data"]["user_id"]
    client.post("/user/update", json={"user_id": uid, "remark": "changed"})
    events = client.get(f"/activity?user_id={uid}").json()["data"]["events"]
    assert [event["action"] for event in events[:2]] == ["update", "create"]
