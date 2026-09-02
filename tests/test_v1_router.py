"""Behavioral tests for the v1 API on the real application."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from src.api.server import create_app
from src.api.v1_router import API_VERSION


@pytest.fixture
def v1_client(tmp_path):
    return TestClient(create_app(data_root=tmp_path))


def test_version_endpoint(v1_client):
    data = v1_client.get("/api/v1/version").json()
    assert data["api_version"] == API_VERSION
    assert data["status"] == "stable"
    assert data["server_version"]


def test_health_returns_ok(v1_client):
    data = v1_client.get("/api/v1/health").json()
    assert data["status"] == "ok"
    assert data["service"] == "antique"
    assert data["api_version"] == API_VERSION


def test_create_list_and_delete_are_real(v1_client):
    created = v1_client.post("/api/v1/user/create", json={"name": "test"})
    assert created.status_code == 200
    user_id = created.json()["data"]["user_id"]
    assert user_id != "v1-stub"

    listed = v1_client.get("/api/v1/user/list").json()["data"]["list"]
    assert any(profile["user_id"] == user_id for profile in listed)

    deleted = v1_client.post("/api/v1/user/delete", json={"user_id": user_id})
    assert deleted.status_code == 200
    assert deleted.json()["data"]["deleted"] is True


def test_start_unknown_profile_is_not_fake_success(v1_client):
    response = v1_client.post("/api/v1/user/start", json={"user_id": "missing"})
    assert response.status_code == 404


def test_stop_unknown_profile_uses_real_launcher(v1_client):
    response = v1_client.post("/api/v1/user/stop", json={"user_id": "missing"})
    assert response.status_code == 200
    assert response.json()["data"]["stopped"] is False


def test_active_uses_real_store(v1_client):
    response = v1_client.get("/api/v1/user/active")
    assert response.status_code == 200
    assert response.json()["data"]["list"] == []


def test_import_preview_rejects_missing_source(v1_client, tmp_path):
    source = tmp_path / "missing"
    response = v1_client.post(
        "/api/v1/user/import/backup/preview",
        json={"source_path": str(source)},
    )
    assert response.status_code in {400, 404}


def test_real_app_openapi_contains_v1_business_paths(v1_client):
    paths = v1_client.get("/openapi.json").json()["paths"]
    expected = {
        "/api/v1/version",
        "/api/v1/health",
        "/api/v1/user/create",
        "/api/v1/user/list",
        "/api/v1/user/start",
        "/api/v1/user/stop",
        "/api/v1/user/active",
        "/api/v1/user/import/backup",
        "/api/v1/user/import/backup/preview",
    }
    assert expected <= set(paths)
