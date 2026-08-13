"""Tests for the persona API endpoints."""
import pytest
from fastapi.testclient import TestClient

from src.api.server import create_app


def test_persona_generate_endpoint(tmp_path):
    client = TestClient(create_app(data_root=tmp_path))
    r = client.get("/persona/generate")
    assert r.status_code == 200, r.text
    data = r.json()["data"]["persona"]
    for key in ("age", "gender", "occupation", "income_bracket", "country", "device_type"):
        assert key in data


def test_persona_generate_with_constraints(tmp_path):
    client = TestClient(create_app(data_root=tmp_path))
    r = client.get("/persona/generate?occupation=developer&country=DE&age=30")
    assert r.status_code == 200
    p = r.json()["data"]["persona"]
    assert p["occupation"] == "developer"
    assert p["country"] == "DE"
    assert p["age"] == 30


def test_user_create_with_persona(tmp_path):
    client = TestClient(create_app(data_root=tmp_path))
    r = client.post("/user/create", json={
        "name": "persona-user",
        "persona": {"occupation": "developer", "country": "US", "age": 28},
    })
    assert r.status_code == 200, r.text
    data = r.json()["data"]
    assert "persona" in data
    p = data["persona"]
    assert p["occupation"] == "developer"
    assert p["country"] == "US"
    # Fingerprint should reflect the persona
    fp = client.get(f"/profile/{data['user_id']}").json()["data"]["fingerprint_config"]
    assert fp["locale"] == "en-US"
    assert fp["timezone"] == "America/New_York"
    assert fp["hardware_concurrency"] >= 12  # developer trait


def test_user_create_with_persona_fill_missing(tmp_path):
    """Persona with missing fields gets them filled coherently."""
    client = TestClient(create_app(data_root=tmp_path))
    r = client.post("/user/create", json={
        "name": "persona-partial",
        "persona": {"occupation": "student"},  # age, country, etc. missing
    })
    assert r.status_code == 200
    p = r.json()["data"]["persona"]
    assert p["occupation"] == "student"
    assert p["age"] >= 18  # filled by generator
    assert p["country"]  # filled by generator


def test_user_create_without_persona_unchanged(tmp_path):
    """Without persona, create behaves exactly as before."""
    client = TestClient(create_app(data_root=tmp_path))
    r = client.post("/user/create", json={"name": "no-persona"})
    assert r.status_code == 200
    data = r.json()["data"]
    assert "persona" not in data
