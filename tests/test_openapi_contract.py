"""OpenAPI contract checks against the actual wired application."""
from fastapi.testclient import TestClient

from src.api.server import create_app


EXPECTED_PATHS = {
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


def test_real_app_exposes_stable_v1_contract(tmp_path):
    client = TestClient(create_app(data_root=tmp_path))
    schema = client.get("/openapi.json").json()
    assert EXPECTED_PATHS <= set(schema["paths"])
    assert "post" in schema["paths"]["/api/v1/user/create"]
    assert "get" in schema["paths"]["/api/v1/user/list"]
    assert "post" in schema["paths"]["/api/v1/user/start"]


def test_v1_request_schemas_are_real_route_schemas(tmp_path):
    client = TestClient(create_app(data_root=tmp_path))
    schema = client.get("/openapi.json").json()
    create_schema = schema["paths"]["/api/v1/user/create"]["post"]["requestBody"]["content"]["application/json"]["schema"]
    component = schema["components"]["schemas"][create_schema["$ref"].split("/")[-1]]
    assert "name" in component["properties"]
    assert "name" in component["required"]


def test_v1_operations_document_success_responses(tmp_path):
    client = TestClient(create_app(data_root=tmp_path))
    schema = client.get("/openapi.json").json()
    for path in EXPECTED_PATHS:
        for operation in schema["paths"][path].values():
            if isinstance(operation, dict) and "responses" in operation:
                assert "200" in operation["responses"]
