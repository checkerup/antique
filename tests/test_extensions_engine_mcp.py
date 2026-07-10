"""Tests for extensions, engine selection, client hints, and MCP server.

Run with:  pytest tests/test_extensions_engine_mcp.py -v
"""
import json
import os
import tempfile
import zipfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.core.extension import (
    Extension,
    ExtensionStore,
    _extract_crx,
    _generate_ext_id,
    _read_manifest,
)
from src.core.browser import (
    ENGINE_CAMOUFOX,
    ENGINE_CHROMIUM,
    ENGINE_FIREFOX,
    VALID_ENGINES,
    _build_client_hints_args,
)
from src.core.fingerprint import Fingerprint, generate_fingerprint


# ---------------------------------------------------------------------------
# Extension Store tests
# ---------------------------------------------------------------------------


class TestExtensionStore:
    @pytest.fixture
    def ext_store(self, tmp_path):
        return ExtensionStore(data_root=tmp_path)

    @pytest.fixture
    def sample_extension(self, tmp_path):
        """Create a minimal unpacked extension on disk."""
        ext_dir = tmp_path / "my_extension"
        ext_dir.mkdir()
        manifest = {
            "manifest_version": 3,
            "name": "Test Extension",
            "version": "1.0.0",
            "description": "A test extension",
        }
        (ext_dir / "manifest.json").write_text(json.dumps(manifest))
        (ext_dir / "background.js").write_text("console.log('loaded');")
        return ext_dir

    def test_install_unpacked(self, ext_store, sample_extension):
        ext = ext_store.install_from_unpacked(sample_extension)
        assert ext.name == "Test Extension"
        assert ext.version == "1.0.0"
        assert ext.source_type == "unpacked"
        assert Path(ext.path).exists()
        assert (Path(ext.path) / "manifest.json").exists()

    def test_list_extensions(self, ext_store, sample_extension):
        ext_store.install_from_unpacked(sample_extension)
        exts = ext_store.list()
        assert len(exts) == 1
        assert exts[0].name == "Test Extension"

    def test_get_extension(self, ext_store, sample_extension):
        ext = ext_store.install_from_unpacked(sample_extension)
        found = ext_store.get(ext.ext_id)
        assert found is not None
        assert found.ext_id == ext.ext_id

    def test_uninstall(self, ext_store, sample_extension):
        ext = ext_store.install_from_unpacked(sample_extension)
        assert ext_store.uninstall(ext.ext_id)
        assert ext_store.get(ext.ext_id) is None
        assert not Path(ext.path).exists()

    def test_uninstall_nonexistent(self, ext_store):
        assert not ext_store.uninstall("nonexistent_id")

    def test_install_crx(self, ext_store, tmp_path):
        """Test installing from a .crx file (simulated as zip with header)."""
        # Create a fake CRX (just a zip with PK magic at start)
        ext_content_dir = tmp_path / "crx_content"
        ext_content_dir.mkdir()
        manifest = {
            "manifest_version": 3,
            "name": "CRX Extension",
            "version": "2.0.0",
            "description": "From CRX",
        }
        (ext_content_dir / "manifest.json").write_text(json.dumps(manifest))

        # Create a zip (CRX is zip with header)
        crx_path = tmp_path / "test.crx"
        with zipfile.ZipFile(crx_path, "w") as zf:
            zf.writestr("manifest.json", json.dumps(manifest))
            zf.writestr("popup.html", "<h1>Hello</h1>")

        ext = ext_store.install_from_crx(crx_path)
        assert ext.name == "CRX Extension"
        assert ext.version == "2.0.0"
        assert ext.source_type == "crx"

    def test_get_extensions_for_profile(self, ext_store, sample_extension):
        ext = ext_store.install_from_unpacked(sample_extension)
        paths = ext_store.get_extensions_for_profile([ext.ext_id])
        assert len(paths) == 1
        assert paths[0] == ext.path

    def test_get_extensions_for_profile_ignores_missing(self, ext_store):
        paths = ext_store.get_extensions_for_profile(["nonexistent"])
        assert paths == []

    def test_persistence(self, tmp_path, sample_extension):
        """Extensions persist across store restarts."""
        store1 = ExtensionStore(data_root=tmp_path)
        ext = store1.install_from_unpacked(sample_extension)

        store2 = ExtensionStore(data_root=tmp_path)
        assert store2.get(ext.ext_id) is not None
        assert store2.get(ext.ext_id).name == "Test Extension"

    def test_install_with_custom_name(self, ext_store, sample_extension):
        ext = ext_store.install_from_unpacked(sample_extension, name="Custom Name")
        assert ext.name == "Custom Name"


# ---------------------------------------------------------------------------
# Client Hints tests
# ---------------------------------------------------------------------------


class TestClientHints:
    def test_builds_args_from_fingerprint(self):
        fp = Fingerprint(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/125.0.6200.150 Safari/537.36",
            platform="Win32",
        )
        args = _build_client_hints_args(fp)
        assert any("125" in a for a in args)
        assert any("Windows" in a for a in args)
        assert any("brand" in a for a in args)

    def test_extracts_correct_major_version(self):
        fp = Fingerprint(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/130.0.6800.100 Safari/537.36",
            platform="Win32",
        )
        args = _build_client_hints_args(fp)
        # Should contain version 130
        full_version_arg = [a for a in args if "full-version" in a][0]
        assert "130" in full_version_arg

    def test_platform_mapping_macos(self):
        fp = Fingerprint(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) Chrome/125.0.0.0 Safari/537.36",
            platform="MacIntel",
        )
        args = _build_client_hints_args(fp)
        platform_arg = [a for a in args if "client-hint-platform=" in a][0]
        assert "macOS" in platform_arg

    def test_platform_mapping_linux(self):
        fp = Fingerprint(
            user_agent="Mozilla/5.0 (X11; Linux x86_64) Chrome/125.0.0.0 Safari/537.36",
            platform="Linux x86_64",
        )
        args = _build_client_hints_args(fp)
        platform_arg = [a for a in args if "client-hint-platform=" in a][0]
        assert "Linux" in platform_arg

    def test_mobile_is_false(self):
        fp = generate_fingerprint()
        args = _build_client_hints_args(fp)
        mobile_arg = [a for a in args if "mobile" in a][0]
        assert "?0" in mobile_arg

    def test_bitness_64(self):
        fp = generate_fingerprint()
        args = _build_client_hints_args(fp)
        bitness_arg = [a for a in args if "bitness" in a][0]
        assert "64" in bitness_arg


# ---------------------------------------------------------------------------
# Engine selection tests
# ---------------------------------------------------------------------------


class TestEngineSelection:
    def test_valid_engines_defined(self):
        assert ENGINE_CHROMIUM in VALID_ENGINES
        assert ENGINE_FIREFOX in VALID_ENGINES
        assert ENGINE_CAMOUFOX in VALID_ENGINES

    def test_default_is_chromium(self):
        from src.core.profile import Profile
        from src.core.browser import BrowserLauncher
        from src.core.profile import ProfileStore

        store = ProfileStore(db_path=Path(tempfile.mkdtemp()) / "test.db")
        launcher = BrowserLauncher(store)
        p = Profile(user_id="test1", name="Test")
        assert launcher._get_engine(p) == ENGINE_CHROMIUM

    def test_engine_from_fingerprint(self):
        from src.core.profile import Profile
        from src.core.browser import BrowserLauncher
        from src.core.profile import ProfileStore

        store = ProfileStore(db_path=Path(tempfile.mkdtemp()) / "test.db")
        launcher = BrowserLauncher(store)
        p = Profile(user_id="test2", name="Test", fingerprint={"browser_engine": "firefox"})
        assert launcher._get_engine(p) == ENGINE_FIREFOX

    def test_engine_from_env(self):
        from src.core.profile import Profile
        from src.core.browser import BrowserLauncher
        from src.core.profile import ProfileStore

        store = ProfileStore(db_path=Path(tempfile.mkdtemp()) / "test.db")
        launcher = BrowserLauncher(store)
        p = Profile(user_id="test3", name="Test")

        with patch.dict(os.environ, {"ANTIDETECT_ENGINE": "camoufox"}):
            assert launcher._get_engine(p) == ENGINE_CAMOUFOX

    def test_invalid_engine_falls_back_to_chromium(self):
        from src.core.profile import Profile
        from src.core.browser import BrowserLauncher
        from src.core.profile import ProfileStore

        store = ProfileStore(db_path=Path(tempfile.mkdtemp()) / "test.db")
        launcher = BrowserLauncher(store)
        p = Profile(user_id="test4", name="Test", fingerprint={"browser_engine": "invalid_engine"})
        assert launcher._get_engine(p) == ENGINE_CHROMIUM


# ---------------------------------------------------------------------------
# MCP server tests
# ---------------------------------------------------------------------------


class TestMCPServer:
    @pytest.fixture
    def mcp_server(self):
        from src.mcp.server import MCPServer
        return MCPServer()

    @pytest.mark.asyncio
    async def test_initialize(self, mcp_server):
        response = await mcp_server.handle_request({
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {},
        })
        assert response["result"]["protocolVersion"] == "2024-11-05"
        assert response["result"]["serverInfo"]["name"] == "antidetect-local"

    @pytest.mark.asyncio
    async def test_tools_list(self, mcp_server):
        response = await mcp_server.handle_request({
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/list",
            "params": {},
        })
        tools = response["result"]["tools"]
        tool_names = [t["name"] for t in tools]
        assert "list_profiles" in tool_names
        assert "open_browser" in tool_names
        assert "close_browser" in tool_names
        assert "navigate" in tool_names
        assert "screenshot" in tool_names
        assert "execute_script" in tool_names
        assert "get_cookies" in tool_names
        assert "set_cookies" in tool_names
        assert "check_proxy" in tool_names

    @pytest.mark.asyncio
    async def test_unknown_method(self, mcp_server):
        response = await mcp_server.handle_request({
            "jsonrpc": "2.0",
            "id": 3,
            "method": "unknown/method",
            "params": {},
        })
        assert "error" in response
        assert response["error"]["code"] == -32601

    @pytest.mark.asyncio
    async def test_notification_no_response(self, mcp_server):
        response = await mcp_server.handle_request({
            "jsonrpc": "2.0",
            "method": "notifications/initialized",
            "params": {},
        })
        assert response is None

    @pytest.mark.asyncio
    async def test_list_profiles_tool(self, mcp_server, tmp_path):
        from src.core.profile import ProfileStore
        store = ProfileStore(db_path=tmp_path / "test.db")
        store.create(name="Test Profile")
        mcp_server._store = store

        from src.core.browser import BrowserLauncher
        mcp_server._launcher = BrowserLauncher(store, data_root=tmp_path)

        response = await mcp_server.handle_request({
            "jsonrpc": "2.0",
            "id": 4,
            "method": "tools/call",
            "params": {
                "name": "list_profiles",
                "arguments": {},
            },
        })
        content = response["result"]["content"][0]["text"]
        data = json.loads(content)
        assert len(data) == 1
        assert data[0]["name"] == "Test Profile"

    @pytest.mark.asyncio
    async def test_create_profile_tool(self, mcp_server, tmp_path):
        from src.core.profile import ProfileStore
        from src.core.browser import BrowserLauncher
        store = ProfileStore(db_path=tmp_path / "test.db")
        mcp_server._store = store
        mcp_server._launcher = BrowserLauncher(store, data_root=tmp_path)

        response = await mcp_server.handle_request({
            "jsonrpc": "2.0",
            "id": 5,
            "method": "tools/call",
            "params": {
                "name": "create_profile",
                "arguments": {"name": "MCP Created"},
            },
        })
        content = response["result"]["content"][0]["text"]
        data = json.loads(content)
        assert data["name"] == "MCP Created"
        assert "user_id" in data

    @pytest.mark.asyncio
    async def test_delete_profile_tool(self, mcp_server, tmp_path):
        from src.core.profile import ProfileStore
        from src.core.browser import BrowserLauncher
        store = ProfileStore(db_path=tmp_path / "test.db")
        p = store.create(name="To Delete")
        mcp_server._store = store
        mcp_server._launcher = BrowserLauncher(store, data_root=tmp_path)

        response = await mcp_server.handle_request({
            "jsonrpc": "2.0",
            "id": 6,
            "method": "tools/call",
            "params": {
                "name": "delete_profile",
                "arguments": {"user_id": p.user_id},
            },
        })
        content = response["result"]["content"][0]["text"]
        data = json.loads(content)
        assert data["deleted"] is True


# ---------------------------------------------------------------------------
# Utility tests
# ---------------------------------------------------------------------------


class TestHelpers:
    def test_generate_ext_id_deterministic(self):
        id1 = _generate_ext_id("test", "/path")
        id2 = _generate_ext_id("test", "/path")
        assert id1 == id2
        assert len(id1) == 12

    def test_generate_ext_id_different_inputs(self):
        id1 = _generate_ext_id("ext1", "/a")
        id2 = _generate_ext_id("ext2", "/b")
        assert id1 != id2

    def test_read_manifest(self, tmp_path):
        manifest = {"name": "test", "version": "1.0"}
        (tmp_path / "manifest.json").write_text(json.dumps(manifest))
        result = _read_manifest(tmp_path)
        assert result["name"] == "test"

    def test_read_manifest_missing(self, tmp_path):
        with pytest.raises(ValueError):
            _read_manifest(tmp_path)

    def test_extract_crx_valid_zip(self, tmp_path):
        # Create a simple zip file (CRX without header)
        crx_path = tmp_path / "test.crx"
        dest = tmp_path / "extracted"
        dest.mkdir()

        with zipfile.ZipFile(crx_path, "w") as zf:
            zf.writestr("manifest.json", '{"name": "test"}')

        _extract_crx(crx_path, dest)
        assert (dest / "manifest.json").exists()
