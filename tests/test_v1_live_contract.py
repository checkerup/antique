"""Behavioral contract for the v1 API mounted by the real application."""
from fastapi.testclient import TestClient

from src.api.server import create_app


def test_v1_create_and_list_use_real_store(tmp_path):
    client = TestClient(create_app(data_root=tmp_path))
    created = client.post("/api/v1/user/create", json={"name": "real-v1"})
    assert created.status_code == 200
    user_id = created.json()["data"]["user_id"]
    assert user_id != "v1-stub"

    listed = client.get("/api/v1/user/list").json()["data"]["list"]
    assert any(item["user_id"] == user_id for item in listed)


def test_v1_version_and_health_are_available_on_real_app(tmp_path):
    client = TestClient(create_app(data_root=tmp_path))
    assert client.get("/api/v1/version").status_code == 200
    health = client.get("/api/v1/health")
    assert health.status_code == 200
    assert health.json()["status"] == "ok"
