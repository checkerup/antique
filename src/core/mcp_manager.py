"""MCP subprocess lifecycle manager.

Manages the MCP server as a child process so the dashboard can start/stop it
and display its status without requiring the user to run a separate terminal.

The MCP server itself runs on stdio (JSON-RPC 2.0), which means:
  - It's launched as a subprocess with stdin/stdout piped.
  - External AI tools (Claude Desktop, Cursor, Windsurf) connect to it via
    the config entry that points to the executable + args.
  - This manager tracks whether the process is alive and provides the config
    snippet for easy integration.
"""
from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass
class MCPProcessState:
    """Live state of the managed MCP subprocess."""
    running: bool = False
    pid: Optional[int] = None
    started_at: Optional[float] = None
    transport: str = "stdio"
    error: Optional[str] = None

    @property
    def uptime_seconds(self) -> Optional[float]:
        if self.started_at and self.running:
            return time.time() - self.started_at
        return None

    def to_dict(self) -> Dict[str, Any]:
        uptime = self.uptime_seconds
        # Legacy compat: status means capability readiness, not process liveness.
        # The new `running` field is the source of truth for the Start/Stop UI.
        status_str = "error" if self.error else "available"
        return {
            "running": self.running,
            "status": status_str,
            "pid": self.pid,
            "started_at": self.started_at,
            "uptime_s": round(uptime, 1) if uptime else None,
            "transport": self.transport,
            "error": self.error,
        }


MCP_TOOLS_SUMMARY = [
    {"name": "list_profiles", "desc": "List all profiles with status"},
    {"name": "open_browser", "desc": "Start a profile's browser"},
    {"name": "close_browser", "desc": "Stop a profile's browser"},
    {"name": "create_profile", "desc": "Create a new profile"},
    {"name": "delete_profile", "desc": "Delete a profile"},
    {"name": "navigate", "desc": "Navigate to a URL"},
    {"name": "screenshot", "desc": "Take a screenshot"},
    {"name": "get_page_content", "desc": "Get page HTML"},
    {"name": "execute_script", "desc": "Run JS in page context"},
    {"name": "get_cookies", "desc": "Get browser cookies"},
    {"name": "set_cookies", "desc": "Set browser cookies"},
    {"name": "check_proxy", "desc": "Test proxy connectivity"},
]


class MCPManager:
    """Manages one MCP server subprocess.

    Thread-safe for the common start/stop/status pattern (no concurrent
    writes expected from the FastAPI event loop).
    """

    def __init__(self):
        self._process: Optional[subprocess.Popen] = None
        self._state = MCPProcessState()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def start(self) -> MCPProcessState:
        """Start the MCP server subprocess.

        Returns the new state. If already running, returns current state
        without restarting (idempotent).
        """
        if self._process is not None and self._process.poll() is None:
            self._state.running = True
            return self._state

        try:
            cmd = [sys.executable, "-m", "src.mcp"]
            # Inherit CWD from the API server (project root)
            self._process = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=self._project_root(),
                creationflags=self._creation_flags(),
            )
            self._state = MCPProcessState(
                running=True,
                pid=self._process.pid,
                started_at=time.time(),
                transport="stdio",
            )
        except Exception as exc:
            self._state = MCPProcessState(
                running=False,
                error=str(exc),
            )

        return self._state

    def stop(self) -> MCPProcessState:
        """Stop the MCP server subprocess.

        Returns the new state. If not running, returns current state.
        """
        if self._process is None:
            self._state = MCPProcessState(running=False)
            return self._state

        if self._process.poll() is None:
            try:
                # Graceful shutdown: close stdin so the server exits
                if self._process.stdin:
                    self._process.stdin.close()
                self._process.terminate()
                try:
                    self._process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    self._process.kill()
                    self._process.wait(timeout=3)
            except (OSError, ProcessLookupError):
                pass

        self._process = None
        self._state = MCPProcessState(running=False)
        return self._state

    def status(self) -> MCPProcessState:
        """Check and return current process state."""
        if self._process is not None:
            if self._process.poll() is not None:
                # Process exited unexpectedly
                exit_code = self._process.returncode
                stderr_tail = ""
                try:
                    if self._process.stderr:
                        stderr_tail = self._process.stderr.read(2048).decode(errors="replace")
                except Exception:
                    pass
                self._process = None
                self._state = MCPProcessState(
                    running=False,
                    error=f"process exited with code {exit_code}" + (f": {stderr_tail[:200]}" if stderr_tail else ""),
                )
            else:
                self._state.running = True
        else:
            if self._state.running:
                self._state = MCPProcessState(running=False)
        return self._state

    def config_json(self, include_env: bool = False) -> Dict[str, Any]:
        """Generate the MCP config snippet for Claude Desktop / Cursor.

        This is the JSON object the user pastes into their AI tool's config.
        """
        python_path = sys.executable
        project_root = str(self._project_root())

        config = {
            "mcpServers": {
                "antique": {
                    "command": python_path,
                    "args": ["-m", "src.mcp"],
                    "cwd": project_root,
                }
            }
        }

        if include_env:
            env = {}
            if os.environ.get("ANTIQUE_DATA_DIR"):
                env["ANTIQUE_DATA_DIR"] = os.environ["ANTIQUE_DATA_DIR"]
            if env:
                config["mcpServers"]["antique"]["env"] = env

        return config

    def tools_list(self) -> List[Dict[str, str]]:
        """Return the list of MCP tools with descriptions."""
        return MCP_TOOLS_SUMMARY

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    @staticmethod
    def _project_root() -> Path:
        """Resolve the project root (parent of src/)."""
        return Path(__file__).resolve().parent.parent.parent

    @staticmethod
    def _creation_flags() -> int:
        """Windows: CREATE_NEW_PROCESS_GROUP so the child doesn't get our
        Ctrl+C. Other platforms: 0."""
        if sys.platform == "win32":
            return subprocess.CREATE_NEW_PROCESS_GROUP
        return 0


# Singleton instance used by the API
_manager: Optional[MCPManager] = None


def get_mcp_manager() -> MCPManager:
    """Get (or create) the singleton MCPManager."""
    global _manager
    if _manager is None:
        _manager = MCPManager()
    return _manager
