"""All public interfaces must report the installed package version."""
from fastapi.testclient import TestClient

from src import __version__
from src.api.server import create_app
from src.mcp.server import MCPServer


def test_http_version_is_single_source_of_truth(tmp_path):
    client = TestClient(create_app(data_root=tmp_path))
    assert client.get("/health").json()["version"] == __version__
    assert client.get("/info").json()["version"] == __version__
    assert client.app.version == __version__


def test_mcp_version_is_single_source_of_truth():
    import asyncio

    result = asyncio.run(
        MCPServer().handle_request({"jsonrpc": "2.0", "id": 1, "method": "initialize"})
    )
    assert result["result"]["serverInfo"]["version"] == __version__