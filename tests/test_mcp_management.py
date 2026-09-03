"""Tests for the MCP server management feature (iteration 3).

Covers:
- MCPManager lifecycle (start/stop/status/config)
- API endpoints: GET /mcp/status, POST /mcp/start, POST /mcp/stop, GET /mcp/config
- Dashboard UI integration (the MCP panel renders correctly)

No network or browser required. Uses mocked subprocess for process tests.
"""
import json
import subprocess
import sys
import time
from pathlib import Path
from unittest.mock import MagicMock, patch, PropertyMock

import pytest

from src.core.mcp_manager import (
    MCPManager,
    MCPProcessState,
    MCP_TOOLS_SUMMARY,
    get_mcp_manager,
)


# ---------------------------------------------------------------------------
# Unit tests: MCPProcessState
# ---------------------------------------------------------------------------


class TestMCPProcessState:
    def test_default_state(self):
        state = MCPProcessState()
        assert state.running is False
        assert state.pid is None
        assert state.uptime_seconds is None

    def test_running_state_has_uptime(self):
        state = MCPProcessState(running=True, pid=12345, started_at=time.time() - 60)
        assert state.uptime_seconds is not None
        assert state.uptime_seconds >= 59

    def test_stopped_state_no_uptime(self):
        state = MCPProcessState(running=False, started_at=time.time() - 60)
        assert state.uptime_seconds is None

    def test_to_dict_stopped(self):
        state = MCPProcessState(running=False, error="test error")
        d = state.to_dict()
        assert d["running"] is False
        assert d["pid"] is None
        assert d["uptime_s"] is None
        assert d["error"] == "test error"
        assert d["transport"] == "stdio"

    def test_to_dict_running(self):
        state = MCPProcessState(running=True, pid=999, started_at=time.time() - 30)
        d = state.to_dict()
        assert d["running"] is True
        assert d["pid"] == 999
        assert d["uptime_s"] >= 29
        assert d["error"] is None


# ---------------------------------------------------------------------------
# Unit tests: MCPManager
# ---------------------------------------------------------------------------


class TestMCPManager:
    def setup_method(self):
        self.mgr = MCPManager()

    def test_initial_status_is_stopped(self):
        state = self.mgr.status()
        assert state.running is False

    def test_tools_list(self):
        tools = self.mgr.tools_list()
        assert len(tools) == 12
        names = [t["name"] for t in tools]
        assert "list_profiles" in names
        assert "open_browser" in names
        assert "screenshot" in names
        assert "check_proxy" in names

    def test_config_json_structure(self):
        config = self.mgr.config_json()
        assert "mcpServers" in config
        assert "antique" in config["mcpServers"]
        entry = config["mcpServers"]["antique"]
        assert "command" in entry
        assert entry["args"] == ["-m", "src.mcp"]
        assert "cwd" in entry

    def test_config_json_uses_current_python(self):
        config = self.mgr.config_json()
        assert config["mcpServers"]["antique"]["command"] == sys.executable

    @patch.dict("os.environ", {"ANTIQUE_DATA_DIR": "/custom/data"})
    def test_config_json_with_env(self):
        config = self.mgr.config_json(include_env=True)
        entry = config["mcpServers"]["antique"]
        assert "env" in entry
        assert entry["env"]["ANTIQUE_DATA_DIR"] == "/custom/data"

    def test_config_json_without_env(self):
        config = self.mgr.config_json(include_env=False)
        entry = config["mcpServers"]["antique"]
        assert "env" not in entry

    @patch("subprocess.Popen")
    def test_start_creates_subprocess(self, mock_popen):
        proc = MagicMock()
        proc.pid = 42
        proc.poll.return_value = None  # still running
        mock_popen.return_value = proc

        state = self.mgr.start()
        assert state.running is True
        assert state.pid == 42
        assert state.started_at is not None
        mock_popen.assert_called_once()

    @patch("subprocess.Popen")
    def test_start_is_idempotent(self, mock_popen):
        proc = MagicMock()
        proc.pid = 42
        proc.poll.return_value = None
        mock_popen.return_value = proc

        self.mgr.start()
        self.mgr.start()  # second call should not create new process
        assert mock_popen.call_count == 1

    @patch("subprocess.Popen")
    def test_stop_terminates_process(self, mock_popen):
        proc = MagicMock()
        proc.pid = 42
        proc.poll.return_value = None
        proc.wait.return_value = 0
        proc.stdin = MagicMock()
        mock_popen.return_value = proc

        self.mgr.start()
        state = self.mgr.stop()
        assert state.running is False
        proc.terminate.assert_called_once()

    def test_stop_when_not_running(self):
        state = self.mgr.stop()
        assert state.running is False
        assert state.error is None

    @patch("subprocess.Popen")
    def test_status_detects_crashed_process(self, mock_popen):
        proc = MagicMock()
        proc.pid = 42
        proc.poll.return_value = None
        proc.stderr = MagicMock()
        proc.stderr.read.return_value = b"ImportError: no module"
        mock_popen.return_value = proc

        self.mgr.start()
        # Now simulate crash
        proc.poll.return_value = 1
        proc.returncode = 1

        state = self.mgr.status()
        assert state.running is False
        assert "exited with code 1" in state.error

    @patch("subprocess.Popen")
    def test_start_failure_sets_error(self, mock_popen):
        mock_popen.side_effect = OSError("no such file")

        state = self.mgr.start()
        assert state.running is False
        assert "no such file" in state.error

    def test_project_root_is_valid(self):
        root = MCPManager._project_root()
        assert (root / "src" / "core" / "mcp_manager.py").exists()


# ---------------------------------------------------------------------------
# Unit tests: singleton
# ---------------------------------------------------------------------------


def test_get_mcp_manager_singleton():
    # Reset
    import src.core.mcp_manager as mod
    mod._manager = None
    m1 = get_mcp_manager()
    m2 = get_mcp_manager()
    assert m1 is m2


# ---------------------------------------------------------------------------
# API integration tests (TestClient, no network)
# ---------------------------------------------------------------------------


@pytest.fixture
def client():
    """Create a FastAPI TestClient with a fresh app."""
    from src.api.server import create_app
    from starlette.testclient import TestClient
    app = create_app()
    return TestClient(app)


class TestMCPAPI:
    def test_get_status(self, client):
        r = client.get("/mcp/status")
        assert r.status_code == 200
        data = r.json()["data"]
        assert "running" in data
        assert "tools" in data
        assert "tool_count" in data
        assert data["tool_count"] == 12
        assert data["transport"] == "stdio"

    def test_get_config(self, client):
        r = client.get("/mcp/config")
        assert r.status_code == 200
        data = r.json()["data"]
        assert "config" in data
        config = data["config"]
        assert "mcpServers" in config
        assert "antique" in config["mcpServers"]
        entry = config["mcpServers"]["antique"]
        assert entry["args"] == ["-m", "src.mcp"]

    def test_get_config_with_env(self, client):
        r = client.get("/mcp/config?include_env=true")
        assert r.status_code == 200

    @patch("src.core.mcp_manager.MCPManager.start")
    def test_post_start(self, mock_start, client):
        mock_start.return_value = MCPProcessState(running=True, pid=1234, started_at=time.time())
        r = client.post("/mcp/start")
        assert r.status_code == 200
        data = r.json()["data"]
        assert data["running"] is True
        assert data["pid"] == 1234

    @patch("src.core.mcp_manager.MCPManager.start")
    def test_post_start_failure(self, mock_start, client):
        mock_start.return_value = MCPProcessState(running=False, error="spawn failed")
        r = client.post("/mcp/start")
        assert r.status_code == 500

    @patch("src.core.mcp_manager.MCPManager.stop")
    def test_post_stop(self, mock_stop, client):
        mock_stop.return_value = MCPProcessState(running=False)
        r = client.post("/mcp/stop")
        assert r.status_code == 200
        data = r.json()["data"]
        assert data["running"] is False

    def test_status_tools_list_is_complete(self, client):
        r = client.get("/mcp/status")
        tools = r.json()["data"]["tools"]
        names = {t["name"] for t in tools}
        expected = {"list_profiles", "open_browser", "close_browser", "create_profile",
                    "delete_profile", "navigate", "screenshot", "get_page_content",
                    "execute_script", "get_cookies", "set_cookies", "check_proxy"}
        assert expected == names


# ---------------------------------------------------------------------------
# Dashboard UI tests (check HTML contains MCP management elements)
# ---------------------------------------------------------------------------


class TestMCPDashboard:
    def test_dashboard_has_mcp_functions(self):
        html_path = Path(__file__).parent.parent / "src" / "ui" / "templates" / "index.html"
        html = html_path.read_text(encoding="utf-8") + "\n" + (html_path.parent / "assets" / "app.js").read_text(encoding="utf-8")
        assert "mcpStart" in html
        assert "mcpStop" in html
        assert "mcpCopyConfig" in html
        assert "/mcp/start" in html
        assert "/mcp/stop" in html
        assert "/mcp/config" in html
        assert "Copy Config" in html

    def test_dashboard_mcp_button_exists(self):
        html_path = Path(__file__).parent.parent / "src" / "ui" / "templates" / "index.html"
        html = html_path.read_text(encoding="utf-8") + "\n" + (html_path.parent / "assets" / "app.js").read_text(encoding="utf-8")
        assert "loadMcp" in html
        assert "MCP status" in html
