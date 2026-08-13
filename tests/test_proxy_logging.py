"""Test that proxy credentials are not leaked in logs."""
import pytest
import logging
import io
from pathlib import Path
from fastapi.testclient import TestClient
from src.api.server import create_app
from src.core.proxy import parse_proxy


@pytest.fixture
def client(tmp_path):
    """Create test client with isolated DB."""
    app = create_app(data_root=tmp_path)
    return TestClient(app)


@pytest.fixture
def log_capture():
    """Capture log output for inspection."""
    log_stream = io.StringIO()
    handler = logging.StreamHandler(log_stream)
    handler.setLevel(logging.DEBUG)
    
    # Capture logs from antique.api and adshield.server
    logger1 = logging.getLogger("antique.api")
    logger2 = logging.getLogger("adshield.server")
    
    logger1.addHandler(handler)
    logger2.addHandler(handler)
    logger1.setLevel(logging.DEBUG)
    logger2.setLevel(logging.DEBUG)
    
    yield log_stream
    
    logger1.removeHandler(handler)
    logger2.removeHandler(handler)


def test_proxy_password_not_in_proxy_parse_logs(log_capture):
    """F.15: Proxy credentials should not appear in logs during parsing."""
    proxy_dict = {
        "proxy_type": "http",
        "proxy_host": "proxy.example.com",
        "proxy_port": 8080,
        "proxy_user": "user",
        "proxy_password": "secret_password_123"
    }
    
    # Parse proxy
    config = parse_proxy(proxy_dict)
    
    # Verify config parsed correctly
    assert config.username == "user"
    assert config.password == "secret_password_123"
    
    # Get log output
    log_output = log_capture.getvalue()
    
    # Verify password is NOT in logs
    assert "secret_password_123" not in log_output
    assert "user:secret" not in log_output


def test_proxy_credentials_not_in_api_logs(client, log_capture):
    """F.15: Proxy credentials should not appear in API logs."""
    # Create profile with proxy
    uid = "test_proxy_123"
    proxy_config = {
        "proxy_type": "http",
        "proxy_host": "proxy.example.com",
        "proxy_port": 8080,
        "proxy_user": "testuser",
        "proxy_password": "secretpass"
    }
    
    profile = client.post("/user/create", json={
        "name": "Test Profile",
        "user_id": uid,
        "user_proxy_config": proxy_config
    })
    
    assert profile.status_code == 200
    
    # Update profile
    client.post("/user/update", json={
        "user_id": uid,
        "user_proxy_config": {
            "proxy_type": "http",
            "proxy_host": "proxy2.example.com",
            "proxy_port": 8080,
            "proxy_user": "newuser",
            "proxy_password": "newpass"
        }
    })
    
    # Get profile list
    client.get("/user/list")
    
    # Get log output
    log_output = log_capture.getvalue()
    
    # Verify passwords are NOT in logs
    assert "secretpass" not in log_output
    assert "newpass" not in log_output
    assert "testuser:secret" not in log_output
    assert "newuser:newpass" not in log_output


def test_proxy_credentials_not_in_profile_list_response(client):
    """F.15: Profile list should not expose raw proxy credentials."""
    uid = "test_cred_456"
    proxy_config = {
        "proxy_type": "http",
        "proxy_host": "proxy.example.com",
        "proxy_port": 8080,
        "proxy_user": "user",
        "proxy_password": "secretpass"
    }
    
    # Create profile
    created = client.post("/user/create", json={
        "name": "Test Profile",
        "user_id": uid,
        "user_proxy_config": proxy_config
    })
    assert created.status_code == 200
    
    # Get profile list
    profiles = client.get("/user/list").json()["data"]
    
    # Find our profile
    profile = next((p for p in profiles["list"] if p.get("user_id") == uid), None)
    assert profile is not None
    
    # Check that proxy field doesn't expose credentials in plain text
    # Serialize entire profile to string and check for password
    import json
    profile_str = json.dumps(profile).lower()
    assert "secretpass" not in profile_str


def test_proxy_check_endpoint_masks_credentials(client, log_capture):
    """F.15: Proxy check endpoint should not leak credentials in logs."""
    # Create profile with proxy
    uid = "test_check_789"
    proxy_config = {
        "proxy_type": "http",
        "proxy_host": "proxy.example.com",
        "proxy_port": 8080,
        "proxy_user": "checkuser",
        "proxy_password": "checkpass"
    }
    
    profile = client.post("/user/create", json={
        "name": "Test Profile",
        "user_id": uid,
        "user_proxy_config": proxy_config
    })
    assert profile.status_code == 200
    
    # Try to check proxy (may fail if network not available, but shouldn't leak)
    resp = client.post("/user/proxy/check", json={"user_id": uid})
    
    # Regardless of success/failure, check logs
    log_output = log_capture.getvalue()
    assert "checkpass" not in log_output
    assert "checkuser:checkpass@" not in log_output
    
    # Check response too
    import json
    resp_str = resp.text.lower()
    assert "checkpass" not in resp_str
