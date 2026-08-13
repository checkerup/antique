"""Test encrypted snapshot export and restore."""
import pytest
from pathlib import Path
from fastapi.testclient import TestClient
from src.api.server import create_app


@pytest.fixture
def client(tmp_path):
    """Create test client with isolated DB."""
    app = create_app(data_root=tmp_path)
    return TestClient(app)


def _uid():
    import uuid
    return uuid.uuid4().hex[:12]


def test_encrypted_snapshot_export(client, tmp_path):
    """F.10: Export encrypted snapshot creates file."""
    # Create a profile first
    uid = _uid()
    profile = client.post("/user/create", json={"name": "Test Profile", "user_id": uid})
    assert profile.status_code == 200
    
    # Export snapshot
    snapshot_path = tmp_path / "snapshot.enc"
    resp = client.post("/user/snapshot/export", json={
        "path": str(snapshot_path),
        "password": "test_password_123"
    })
    
    assert resp.status_code == 200
    assert snapshot_path.exists()
    assert snapshot_path.stat().st_size > 0


def test_encrypted_snapshot_restore_correct_password(client, tmp_path):
    """F.11: Restore encrypted snapshot with correct password."""
    # Create profiles
    uid1, uid2 = _uid(), _uid()
    client.post("/user/create", json={"name": "Profile 1", "user_id": uid1})
    client.post("/user/create", json={"name": "Profile 2", "user_id": uid2})
    
    # Export snapshot
    snapshot_path = tmp_path / "snapshot.enc"
    password = "correct_password"
    
    resp = client.post("/user/snapshot/export", json={
        "path": str(snapshot_path),
        "password": password
    })
    assert resp.status_code == 200
    
    # Delete profiles
    client.post("/user/delete", json={"user_id": uid1})
    client.post("/user/delete", json={"user_id": uid2})
    
    # Verify deleted
    profiles = client.get("/user/list").json()["data"]
    assert len(profiles.get("list", [])) == 0
    
    # Restore snapshot
    resp = client.post("/user/snapshot/import", json={
        "path": str(snapshot_path),
        "password": password
    })
    
    assert resp.status_code == 200
    
    # Verify restored
    profiles = client.get("/user/list").json()["data"]
    assert len(profiles["list"]) == 2
    names = {p["name"] for p in profiles["list"]}
    assert "Profile 1" in names
    assert "Profile 2" in names


def test_encrypted_snapshot_wrong_password(client, tmp_path):
    """F.11: Restore encrypted snapshot with wrong password should fail."""
    # Create a profile
    client.post("/user/create", json={"name": "Test Profile"})
    
    # Export snapshot
    snapshot_path = tmp_path / "snapshot.enc"
    resp = client.post("/user/snapshot/export", json={
        "path": str(snapshot_path),
        "password": "correct_password"
    })
    assert resp.status_code == 200
    
    # Try to restore with wrong password
    resp = client.post("/user/snapshot/import", json={
        "path": str(snapshot_path),
        "password": "wrong_password"
    })
    
    assert resp.status_code in (400, 422, 500)


def test_encrypted_snapshot_missing_file(client, tmp_path):
    """F.11: Restore from nonexistent file should fail."""
    snapshot_path = tmp_path / "nonexistent.enc"
    
    resp = client.post("/user/snapshot/import", json={
        "path": str(snapshot_path),
        "password": "any_password"
    })
    
    assert resp.status_code in (400, 404, 500)


def test_encrypted_snapshot_overwrite_option(client, tmp_path):
    """F.11: Restore with overwrite=True updates existing profiles from snapshot."""
    # Create initial profile
    uid1 = _uid()
    client.post("/user/create", json={"name": "Original Name", "user_id": uid1})
    
    # Export snapshot
    snapshot_path = tmp_path / "snapshot.enc"
    resp = client.post("/user/snapshot/export", json={
        "path": str(snapshot_path),
        "password": "test"
    })
    assert resp.status_code == 200
    
    # Modify the profile after snapshot
    client.post("/user/update", json={"user_id": uid1, "name": "Modified Name"})
    
    # Create another profile (not in snapshot)
    uid2 = _uid()
    client.post("/user/create", json={"name": "New Profile", "user_id": uid2})
    
    # Restore with overwrite=True (updates existing profiles from snapshot)
    resp = client.post("/user/snapshot/import", json={
        "path": str(snapshot_path),
        "password": "test",
        "overwrite": True
    })
    
    assert resp.status_code == 200
    
    # Verify: uid1 restored to original name, uid2 still exists (restore is non-destructive)
    profiles = client.get("/user/list").json()["data"]
    names = {p["name"]: p["user_id"] for p in profiles["list"]}
    assert "Original Name" in names
    assert names["Original Name"] == uid1
    assert "New Profile" in names  # Restore doesn't delete, only updates
