"""Iteration 8: reminders, webhooks, SSH proxies, rotation schedules, bundle versioning."""
from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from src.api.server import create_app
from src.core import notify, rotation, ssh_tunnel
from src.core.portable import BUNDLE_VERSION, build_bundle, parse_bundle
from src.core.proxy import ProxyConfig, parse_proxy


@pytest.fixture
def client(tmp_path):
    return TestClient(create_app(data_root=tmp_path))


def _create(client, name="ops"):
    response = client.post("/user/create", json={"name": name})
    assert response.status_code == 200, response.text
    return response.json()["data"]["user_id"]


# --- A5: reminders ---------------------------------------------------------

def test_due_date_roundtrip_and_overdue_flag(client):
    uid = _create(client, "warm-me")
    past = (datetime.utcnow() - timedelta(days=1)).isoformat()
    response = client.post(f"/user/{uid}/due-date", json={"due_date": past})
    assert response.status_code == 200, response.text
    assert response.json()["data"]["overdue"] is True
    listed = client.get("/user/list").json()["data"]["list"][0]
    assert listed["due_date"] is not None
    assert listed["overdue"] is True


def test_reminders_endpoint_sorts_and_counts(client):
    soon = _create(client, "soon")
    later = _create(client, "later")
    client.post(f"/user/{later}/due-date", json={"due_date": (datetime.utcnow() + timedelta(days=5)).isoformat()})
    client.post(f"/user/{soon}/due-date", json={"due_date": (datetime.utcnow() - timedelta(hours=2)).isoformat()})
    data = client.get("/user/reminders").json()["data"]
    assert [item["name"] for item in data["list"]] == ["soon", "later"]
    assert data["overdue_count"] == 1
    only = client.get("/user/reminders?only_overdue=true").json()["data"]
    assert only["total"] == 1


def test_due_date_validation_and_clearing(client):
    uid = _create(client, "clear-me")
    assert client.post(f"/user/{uid}/due-date", json={"due_date": "not-a-date"}).status_code == 400
    assert client.post("/user/missing/due-date", json={"due_date": None}).status_code == 404
    client.post(f"/user/{uid}/due-date", json={"due_date": "2030-01-01"})
    cleared = client.post(f"/user/{uid}/due-date", json={"due_date": None})
    assert cleared.json()["data"]["due_date"] is None


# --- A6: webhooks ----------------------------------------------------------

@pytest.mark.parametrize("kind,expected_key", [("discord", "content"), ("telegram", "text"), ("generic", "message")])
def test_build_payload_per_provider(kind, expected_key):
    payload = notify.build_payload(kind, "profile_crash", {"name": "p1", "detail": "boom", "chat_id": "42"})
    assert expected_key in payload
    assert "p1" in str(payload)


def test_send_event_respects_config_and_uses_sender():
    calls = []
    cfg = notify.WebhookConfig(url="https://example.invalid/hook", kind="generic", enabled=True, events=["profile_crash"])
    sent = notify.send_event(cfg, "profile_crash", {"name": "p"}, sender=lambda url, body: calls.append((url, body)) or 204)
    assert sent["sent"] is True and sent["status"] == 204 and len(calls) == 1
    skipped = notify.send_event(cfg, "profile_start", {"name": "p"}, sender=lambda url, body: 200)
    assert skipped["sent"] is False
    disabled = notify.send_event(notify.WebhookConfig(), "profile_crash", {}, sender=lambda url, body: 200)
    assert disabled["sent"] is False


def test_send_event_never_raises_on_transport_error():
    cfg = notify.WebhookConfig(url="https://example.invalid/hook", enabled=True)

    def boom(url, body):
        raise TimeoutError("nope")

    result = notify.send_event(cfg, "profile_start", {"name": "p"}, sender=boom)
    assert result["sent"] is False and "TimeoutError" in result["reason"]


def test_webhook_settings_endpoints(client):
    assert client.get("/settings/webhook").json()["data"]["enabled"] is False
    ok = client.post("/settings/webhook", json={"url": "https://discord.test/hook", "kind": "discord", "enabled": True})
    assert ok.status_code == 200
    assert client.get("/settings/webhook").json()["data"]["kind"] == "discord"
    assert client.post("/settings/webhook", json={"kind": "carrier-pigeon"}).status_code == 400
    assert client.post("/settings/webhook", json={"kind": "telegram", "url": "x", "enabled": True}).status_code == 400


# --- A7: SSH proxies -------------------------------------------------------

def test_ssh_proxy_type_is_accepted_but_needs_a_tunnel():
    cfg = parse_proxy({"proxy_type": "ssh", "proxy_host": "gw.example", "proxy_port": 22, "proxy_user": "ops"})
    assert cfg.type == "ssh"
    with pytest.raises(ValueError):
        cfg.to_playwright()


def test_build_ssh_command_shape():
    cfg = ProxyConfig(type="ssh", host="gw.example", port=2222, username="ops")
    command = ssh_tunnel.build_ssh_command(cfg, 15001)
    assert command[0] == "ssh"
    assert "-D" in command and "127.0.0.1:15001" in command
    assert command[-1] == "ops@gw.example"
    assert "2222" in command
    with pytest.raises(ssh_tunnel.SSHTunnelError):
        ssh_tunnel.build_ssh_command(ProxyConfig(type="socks5", host="h"), 1080)


def test_ssh_tunnel_manager_reuses_and_closes():
    class FakeProcess:
        def __init__(self):
            self.killed = False

        def poll(self):
            return None if not self.killed else 0

        def terminate(self):
            self.killed = True

        def wait(self, timeout=None):
            return 0

    spawned = []
    manager = ssh_tunnel.SSHTunnelManager(
        spawn=lambda cmd: spawned.append(cmd) or FakeProcess(),
        port_picker=lambda: 15002,
    )
    cfg = ProxyConfig(type="ssh", host="gw.example", username="ops")
    first = manager.ensure("u1", cfg)
    second = manager.ensure("u1", cfg)
    assert first is second and len(spawned) == 1
    assert first.proxy.type == "socks5" and first.proxy.port == 15002
    assert manager.active == {"u1": 15002}
    assert manager.close("u1") is True
    assert manager.active == {}


# --- 2.2: rotation schedules ----------------------------------------------

def test_rotation_due_calculation_is_pure():
    fresh = rotation.RotationSchedule(pool_id="pool", interval_min=30)
    assert rotation.is_due(fresh) is True
    now = datetime(2026, 8, 10, 12, 0, 0)
    ran = rotation.RotationSchedule(pool_id="pool", interval_min=30, last_run_at=(now - timedelta(minutes=10)).isoformat())
    assert rotation.is_due(ran, now) is False
    assert rotation.is_due(rotation.RotationSchedule(pool_id="p", interval_min=30, last_run_at=(now - timedelta(minutes=31)).isoformat()), now) is True
    paused = rotation.RotationSchedule(pool_id="pool", interval_min=30, enabled=False)
    assert rotation.is_due(paused) is False
    assert [s.pool_id for s in rotation.due_schedules([fresh, paused])] == ["pool"]


def test_rotation_persistence_roundtrip(tmp_path):
    rotation.upsert_schedule(tmp_path, rotation.RotationSchedule(pool_id="pool-a", interval_min=15))
    rotation.upsert_schedule(tmp_path, rotation.RotationSchedule(pool_id="pool-a", interval_min=45))
    stored = rotation.load_schedules(tmp_path)
    assert len(stored) == 1 and stored[0].interval_min == 45
    assert rotation.mark_ran(tmp_path, "pool-a") is not None
    assert rotation.load_schedules(tmp_path)[0].last_run_at is not None
    assert rotation.remove_schedule(tmp_path, "pool-a") is True
    assert rotation.remove_schedule(tmp_path, "pool-a") is False
    with pytest.raises(rotation.RotationScheduleError):
        rotation.upsert_schedule(tmp_path, rotation.RotationSchedule(pool_id="bad", interval_min=0))


def test_rotation_api_endpoints(client):
    assert client.post("/proxy/pool/pool-a/schedule", json={"interval_min": 0}).status_code == 400
    assert client.post("/proxy/pool/pool-a/schedule", json={"interval_min": 20}).status_code == 200
    listed = client.get("/proxy/rotation/schedules").json()["data"]
    assert listed["total"] == 1 and listed["due_count"] == 1
    ran = client.post("/proxy/rotation/run-due").json()["data"]
    assert ran["rotated"] == ["pool-a"]
    assert client.get("/proxy/rotation/schedules").json()["data"]["due_count"] == 0
    assert client.delete("/proxy/pool/pool-a/schedule").status_code == 200
    assert client.delete("/proxy/pool/pool-a/schedule").status_code == 404


def test_ssh_tunnels_endpoint(client):
    assert client.get("/proxy/ssh/tunnels").json()["data"]["total"] == 0


# --- 3.1: bundle format versioning ----------------------------------------

def test_bundle_carries_format_version(client):
    uid = _create(client, "portable")
    bundle = client.post(f"/user/{uid}/export/portable").json()["data"]["bundle"]
    assert bundle["format_version"] == BUNDLE_VERSION
    parsed = parse_bundle(bundle)
    assert parsed["format_version"] == BUNDLE_VERSION


def test_bundle_rejects_unknown_future_version():
    class FakeProfile:
        user_id = "x"
        name = "x"
        group_id = "0"
        proxy = {}
        fingerprint = {}
        cookies = []
        tags = []
        remark = ""
        account_status = "new"

    bundle = build_bundle(FakeProfile())
    bundle["format_version"] = BUNDLE_VERSION + 99
    with pytest.raises(Exception):
        parse_bundle(bundle)

