from pathlib import Path

from fastapi.testclient import TestClient

from src.api.server import create_app


def test_pwa_assets_are_served(tmp_path):
    client = TestClient(create_app(data_root=tmp_path))
    manifest = client.get("/manifest.json")
    worker = client.get("/sw.js")
    assert manifest.status_code == 200
    assert manifest.json()["short_name"] == "Antique"
    assert worker.status_code == 200
    assert "cache" in worker.text.lower()


def test_dashboard_registers_pwa():
    html = Path(__file__).parents[1].joinpath("src", "ui", "templates", "index.html").read_text(encoding="utf-8-sig")
    assert 'rel="manifest"' in html
    assert "serviceWorker.register" in html
