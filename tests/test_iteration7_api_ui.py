from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from src.api.server import create_app


@pytest.fixture
def client(tmp_path):
    return TestClient(create_app(data_root=tmp_path))


def _create(client, name="audit-profile"):
    response = client.post("/user/create", json={"name": name})
    assert response.status_code == 200, response.text
    return response.json()["data"]["user_id"]


def test_detect_score_endpoint_shape(client):
    uid = _create(client)
    response = client.get(f"/user/{uid}/detect-score")
    assert response.status_code == 200, response.text
    data = response.json()["data"]
    assert data["user_id"] == uid
    assert 0 <= data["score"] <= 100
    assert data["grade"] in "ABCDEF"
    assert isinstance(data["checks"], list)
    assert isinstance(data["failures"], list)


def test_fingerprint_preview_endpoint_shape(client):
    uid = _create(client)
    response = client.get(f"/user/{uid}/fingerprint/preview")
    assert response.status_code == 200, response.text
    data = response.json()["data"]
    assert data["user_id"] == uid
    assert data["groups"]
    assert "report" in data
    assert {group["title"] for group in data["groups"]} >= {"Identity", "Graphics"}


def test_bulk_detect_score_summary_and_validation(client):
    ids = [_create(client, f"audit-{i}") for i in range(2)]
    response = client.post("/user/bulk/detect-score", json={"user_ids": ids})
    assert response.status_code == 200, response.text
    data = response.json()["data"]
    assert len(data["results"]) == 2
    assert data["summary"]["avg"] >= 0
    assert sum(data["summary"]["count_by_grade"].values()) == 2
    assert client.post("/user/bulk/detect-score", json={"user_ids": []}).status_code == 400
    assert client.post("/user/bulk/detect-score", json={"user_ids": ["missing"]}).status_code == 400


def test_audit_routes_return_404_for_unknown_profile(client):
    assert client.get("/user/missing/detect-score").status_code == 404
    assert client.get("/user/missing/fingerprint/preview").status_code == 404


def test_dashboard_contains_iteration7_audit_ui():
    html = Path(__file__).parents[1].joinpath("src", "ui", "templates", "index.html").read_text(encoding="utf-8-sig")
    assert "Stealth" in html
    assert "auditProfile" in html
    assert "auditModal" in html
    assert "/detect-score" in html
    # Bug #3 check: no literal backslash-n BETWEEN function definitions (inside JS code blocks)
    # Legitimate \n inside HTML placeholders or JS template literals is OK.
    import re
    # Find all JS function definitions and check none are separated by literal \n
    js_section = html[html.find("<script"):html.find("</script>")]
    # Look for pattern: }<newline>function or ;<newline>function with literal \n
    bad_pattern = re.search(r'\}\\n(function|async)', js_section)
    assert bad_pattern is None, f"Found literal backslash-n between functions: {bad_pattern.group()}"


def test_user_list_remark_filter(client):
    _create(client, "with-note")
    response = client.post("/user/update", json={"user_id": _create(client, "note-target"), "remark": "warm campaign"})
    assert response.status_code == 200
    filtered = client.get("/user/list?remark=warm").json()["data"]["list"]
    assert len(filtered) == 1
    assert filtered[0]["name"] == "note-target"


def test_dashboard_has_bulk_audit_and_notes_filter():
    html = Path(__file__).parents[1].joinpath("src", "ui", "templates", "index.html").read_text(encoding="utf-8-sig")
    assert "bulkAudit" in html
    assert "remark-filter" in html
    assert "Filter notes" in html
