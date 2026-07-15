"""Regression tests for imported AdsPower launches and smart randomization."""
from __future__ import annotations

import asyncio

import pytest
from fastapi.testclient import TestClient

from src.api.server import create_app
from src.core.fingerprint import generate_fingerprint
from src.core.fingerprint_ops import randomize_batch
from src.core.socks_bridge import Socks5AuthBridge


def test_partial_fingerprint_create_keeps_full_generated_values(tmp_path):
    client = TestClient(create_app(data_root=tmp_path))
    created = client.post("/user/create", json={
        "name": "engine-only",
        "fingerprint_config": {"browser_engine": "chromium"},
    })
    uid = created.json()["data"]["user_id"]
    fp = client.get(f"/profile/{uid}").json()["data"]["fingerprint_config"]
    assert fp["browser_engine"] == "chromium"
    assert fp["user_agent"].startswith("Mozilla/5.0")
    assert fp["noise"]
    assert fp["fonts"]


def test_partial_fingerprint_update_does_not_reset_omitted_fields(tmp_path):
    client = TestClient(create_app(data_root=tmp_path))
    uid = client.post("/user/create", json={"name": "merge"}).json()["data"]["user_id"]
    before = client.get(f"/profile/{uid}").json()["data"]["fingerprint_config"]
    client.post("/user/update", json={
        "user_id": uid,
        "fingerprint_config": {"screen_width": 1600},
    })
    after = client.get(f"/profile/{uid}").json()["data"]["fingerprint_config"]
    assert after["screen_width"] == 1600
    assert after["user_agent"] == before["user_agent"]
    assert after["webgl_renderer"] == before["webgl_renderer"]
    assert after["browser_engine"] == before["browser_engine"]


def test_smart_randomize_shared_screen_and_preserved_engine():
    a = generate_fingerprint(seed="a")
    b = generate_fingerprint(seed="b")
    a.browser_engine = "camoufox"
    b.browser_engine = "chromium"
    out = randomize_batch(
        {"a": a.canonical(), "b": b.canonical()},
        os_family="windows",
        shared_fields=["screen"],
        preserve_fields=["engine"],
        seed="batch",
    )
    assert out["a"].screen_width == out["b"].screen_width
    assert out["a"].screen_height == out["b"].screen_height
    assert out["a"].webgl_renderer != out["b"].webgl_renderer or out["a"].noise != out["b"].noise
    assert out["a"].browser_engine == "camoufox"
    assert out["b"].browser_engine == "chromium"


def test_bulk_randomize_api(tmp_path):
    client = TestClient(create_app(data_root=tmp_path))
    ids = [client.post("/user/create", json={"name": f"p{i}"}).json()["data"]["user_id"] for i in range(2)]
    response = client.post("/user/bulk/fingerprint/randomize", json={
        "user_ids": ids,
        "os_family": "linux",
        "shared_fields": ["screen"],
        "preserve_fields": ["engine"],
        "seed": "campaign",
    })
    assert response.status_code == 200, response.text
    assert response.json()["data"]["updated_count"] == 2
    fps = [client.get(f"/profile/{uid}").json()["data"]["fingerprint_config"] for uid in ids]
    assert fps[0]["platform"] == "Linux x86_64"
    assert fps[0]["screen_width"] == fps[1]["screen_width"]


@pytest.mark.asyncio
async def test_authenticated_socks_bridge_protocol_roundtrip():
    """A fake auth SOCKS upstream verifies credentials and echoes one payload."""
    seen = {}

    async def upstream(reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        assert await reader.readexactly(4) == b"\x05\x02\x00\x02"
        writer.write(b"\x05\x02"); await writer.drain()
        version, ulen = await reader.readexactly(2)
        user = await reader.readexactly(ulen)
        plen = (await reader.readexactly(1))[0]
        password = await reader.readexactly(plen)
        seen["auth"] = (version, user, password)
        writer.write(b"\x01\x00"); await writer.drain()
        request = await reader.readexactly(10)
        seen["request"] = request
        writer.write(b"\x05\x00\x00\x01\x7f\x00\x00\x01\x1f\x90"); await writer.drain()
        payload = await reader.readexactly(4)
        writer.write(payload.upper()); await writer.drain()
        writer.close()

    server = await asyncio.start_server(upstream, "127.0.0.1", 0)
    upstream_port = server.sockets[0].getsockname()[1]
    bridge = await Socks5AuthBridge("127.0.0.1", upstream_port, "alice", "secret").start()
    host, port = bridge.server_url.removeprefix("socks5://").split(":")
    reader, writer = await asyncio.open_connection(host, int(port))
    writer.write(b"\x05\x01\x00"); await writer.drain()
    assert await reader.readexactly(2) == b"\x05\x00"
    writer.write(b"\x05\x01\x00\x01\x01\x02\x03\x04\x01\xbb"); await writer.drain()
    reply = await reader.readexactly(10)
    assert reply[:2] == b"\x05\x00"
    writer.write(b"ping"); await writer.drain()
    assert await reader.readexactly(4) == b"PING"
    assert seen["auth"] == (1, b"alice", b"secret")
    writer.close(); await writer.wait_closed()
    await bridge.close()
    server.close(); await server.wait_closed()
