"""MCP Server for antidetect-local.

Provides tools for AI agents to interact with the browser farm:
- list_profiles: List all profiles with status
- open_browser: Start a profile's browser, return CDP endpoint
- close_browser: Stop a profile's browser
- create_profile: Create a new profile
- delete_profile: Delete a profile
- navigate: Navigate a page to a URL
- screenshot: Take a screenshot of the current page
- get_page_content: Get page HTML content
- execute_script: Run JS in the page context
- set_cookies: Set cookies in the browser
- get_cookies: Get cookies from the browser

Launch:
    python -m src.mcp.server [--port 8765]

Or from the main server:
    POST /mcp/start → starts MCP on a port

Protocol: JSON-RPC 2.0 over stdio (compatible with Claude Desktop, Cursor, etc.)
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional


log = logging.getLogger("antique.mcp")


# ---------------------------------------------------------------------------
# Tool definitions (MCP schema)
# ---------------------------------------------------------------------------

TOOLS = [
    {
        "name": "list_profiles",
        "description": "List all browser profiles with their status (active/inactive), name, group, proxy, and tags.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "group_id": {"type": "string", "description": "Filter by group ID"},
                "search": {"type": "string", "description": "Search by name"},
            },
        },
    },
    {
        "name": "open_browser",
        "description": "Start a browser profile. Returns the CDP websocket endpoint and debug port for automation.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "user_id": {"type": "string", "description": "Profile user_id to start"},
            },
            "required": ["user_id"],
        },
    },
    {
        "name": "close_browser",
        "description": "Stop a running browser profile.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "user_id": {"type": "string", "description": "Profile user_id to stop"},
            },
            "required": ["user_id"],
        },
    },
    {
        "name": "create_profile",
        "description": "Create a new browser profile with optional proxy and group.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Profile name"},
                "group_id": {"type": "string", "description": "Group ID", "default": "0"},
                "proxy_type": {"type": "string", "enum": ["direct", "http", "https", "socks5"]},
                "proxy_host": {"type": "string"},
                "proxy_port": {"type": "integer"},
                "proxy_user": {"type": "string"},
                "proxy_password": {"type": "string"},
                "tags": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["name"],
        },
    },
    {
        "name": "delete_profile",
        "description": "Delete a browser profile permanently.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "user_id": {"type": "string", "description": "Profile user_id to delete"},
            },
            "required": ["user_id"],
        },
    },
    {
        "name": "navigate",
        "description": "Navigate the active page of a running profile to a URL.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "user_id": {"type": "string", "description": "Profile user_id (must be running)"},
                "url": {"type": "string", "description": "URL to navigate to"},
                "wait_until": {"type": "string", "enum": ["load", "domcontentloaded", "networkidle"], "default": "load"},
            },
            "required": ["user_id", "url"],
        },
    },
    {
        "name": "screenshot",
        "description": "Take a screenshot of the current page of a running profile. Returns base64 PNG.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "user_id": {"type": "string", "description": "Profile user_id (must be running)"},
                "full_page": {"type": "boolean", "default": False},
            },
            "required": ["user_id"],
        },
    },
    {
        "name": "get_page_content",
        "description": "Get the HTML content of the current page.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "user_id": {"type": "string", "description": "Profile user_id (must be running)"},
            },
            "required": ["user_id"],
        },
    },
    {
        "name": "execute_script",
        "description": "Execute JavaScript in the page context of a running profile.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "user_id": {"type": "string", "description": "Profile user_id (must be running)"},
                "script": {"type": "string", "description": "JavaScript code to execute"},
            },
            "required": ["user_id", "script"],
        },
    },
    {
        "name": "get_cookies",
        "description": "Get all cookies from a running profile's browser context.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "user_id": {"type": "string", "description": "Profile user_id (must be running)"},
                "urls": {"type": "array", "items": {"type": "string"}, "description": "Filter cookies by URLs"},
            },
            "required": ["user_id"],
        },
    },
    {
        "name": "set_cookies",
        "description": "Set cookies in a running profile's browser context.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "user_id": {"type": "string", "description": "Profile user_id (must be running)"},
                "cookies": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string"},
                            "value": {"type": "string"},
                            "domain": {"type": "string"},
                            "path": {"type": "string"},
                            "secure": {"type": "boolean"},
                            "httpOnly": {"type": "boolean"},
                        },
                        "required": ["name", "value", "domain"],
                    },
                },
            },
            "required": ["user_id", "cookies"],
        },
    },
    {
        "name": "check_proxy",
        "description": "Check the proxy of a profile: tests connectivity, returns IP and latency.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "user_id": {"type": "string", "description": "Profile user_id"},
            },
            "required": ["user_id"],
        },
    },
    {
        "name": "chain_monitor_wallets",
        "description": "Monitor EVM wallets on Robinhood Chain (or another preset): ETH balance + tx-history summary per address.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "addresses": {"type": "array", "items": {"type": "string"}, "description": "Wallet addresses (0x...)"},
                "chain": {"type": "string", "description": "Chain preset", "default": "robinhood"},
                "tx_limit": {"type": "integer", "default": 50},
            },
            "required": ["addresses"],
        },
    },
    {
        "name": "chain_early_buyers",
        "description": "Find the earliest distinct buyers of a token on Robinhood Chain via its Transfer events.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "token": {"type": "string", "description": "Token contract address (0x...)"},
                "chain": {"type": "string", "default": "robinhood"},
                "limit": {"type": "integer", "default": 20},
                "from_block": {"description": "Start block (int or 'earliest')", "default": "earliest"},
                "to_block": {"description": "End block (int or 'latest')", "default": "latest"},
                "exclude": {"type": "array", "items": {"type": "string"}, "description": "Addresses to skip (LP/router/deployer)"},
            },
            "required": ["token"],
        },
    },
]


# ---------------------------------------------------------------------------
# MCP Server (stdio JSON-RPC)
# ---------------------------------------------------------------------------


class MCPServer:
    """JSON-RPC 2.0 over stdio MCP server."""

    def __init__(self):
        self._store = None
        self._launcher = None
        self._ext_store = None

    def _get_store(self):
        if self._store is None:
            from ..core.profile import ProfileStore
            self._store = ProfileStore()
        return self._store

    def _get_launcher(self):
        if self._launcher is None:
            from ..core.browser import BrowserLauncher
            self._launcher = BrowserLauncher(self._get_store())
        return self._launcher

    async def handle_request(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Handle a single JSON-RPC request."""
        method = request.get("method", "")
        req_id = request.get("id")
        params = request.get("params", {})

        if method == "initialize":
            return self._response(req_id, {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}},
                "serverInfo": {
                    "name": "antidetect-local",
                    "version": "0.2.0",
                },
            })

        elif method == "tools/list":
            return self._response(req_id, {"tools": TOOLS})

        elif method == "tools/call":
            tool_name = params.get("name", "")
            arguments = params.get("arguments", {})
            try:
                result = await self._call_tool(tool_name, arguments)
                return self._response(req_id, {
                    "content": [{"type": "text", "text": json.dumps(result, indent=2, default=str)}],
                })
            except Exception as e:
                return self._response(req_id, {
                    "content": [{"type": "text", "text": f"Error: {e}"}],
                    "isError": True,
                })

        elif method == "notifications/initialized":
            return None  # no response for notifications

        else:
            return self._error(req_id, -32601, f"Method not found: {method}")

    async def _call_tool(self, name: str, args: Dict[str, Any]) -> Any:
        store = self._get_store()
        launcher = self._get_launcher()

        if name == "list_profiles":
            profiles = store.list(
                group_id=args.get("group_id"),
                search=args.get("search"),
            )
            return [
                {
                    "user_id": p.user_id,
                    "name": p.name,
                    "group_id": p.group_id,
                    "tags": p.tags,
                    "status": "active" if launcher.is_running(p.user_id) else "inactive",
                    "proxy": p.proxy,
                    "launch_count": p.launch_count,
                }
                for p in profiles
            ]

        elif name == "open_browser":
            uid = args["user_id"]
            p = store.get(uid)
            if p is None:
                raise ValueError(f"Profile {uid} not found")
            handle = await launcher.start(p)
            return {
                "user_id": uid,
                "debug_port": handle.debug_port,
                "ws_endpoint": handle.ws_endpoint,
                "status": "started",
            }

        elif name == "close_browser":
            uid = args["user_id"]
            ok = await launcher.stop(uid)
            return {"user_id": uid, "stopped": ok}

        elif name == "create_profile":
            from ..core.fingerprint import generate_fingerprint
            proxy = {"proxy_type": args.get("proxy_type", "direct")}
            if args.get("proxy_host"):
                proxy["proxy_host"] = args["proxy_host"]
                proxy["proxy_port"] = args.get("proxy_port", 0)
            if args.get("proxy_user"):
                proxy["proxy_user"] = args["proxy_user"]
                proxy["proxy_password"] = args.get("proxy_password", "")
            fp = generate_fingerprint()
            p = store.create(
                name=args["name"],
                group_id=args.get("group_id", "0"),
                proxy=proxy,
                fingerprint=fp,
                tags=args.get("tags", []),
            )
            return {"user_id": p.user_id, "name": p.name}

        elif name == "delete_profile":
            uid = args["user_id"]
            ok = store.delete(uid)
            return {"user_id": uid, "deleted": ok}

        elif name == "navigate":
            uid = args["user_id"]
            handle = launcher.get_handle(uid)
            if not handle:
                raise ValueError(f"Profile {uid} is not running")
            pages = handle.context.pages
            page = pages[0] if pages else await handle.context.new_page()
            await page.goto(args["url"], wait_until=args.get("wait_until", "load"))
            return {"url": page.url, "title": await page.title()}

        elif name == "screenshot":
            uid = args["user_id"]
            handle = launcher.get_handle(uid)
            if not handle:
                raise ValueError(f"Profile {uid} is not running")
            pages = handle.context.pages
            page = pages[0] if pages else await handle.context.new_page()
            import base64
            buf = await page.screenshot(full_page=args.get("full_page", False))
            return {"base64_png": base64.b64encode(buf).decode()}

        elif name == "get_page_content":
            uid = args["user_id"]
            handle = launcher.get_handle(uid)
            if not handle:
                raise ValueError(f"Profile {uid} is not running")
            pages = handle.context.pages
            page = pages[0] if pages else await handle.context.new_page()
            content = await page.content()
            return {"html": content[:50000]}  # limit to 50KB

        elif name == "execute_script":
            uid = args["user_id"]
            handle = launcher.get_handle(uid)
            if not handle:
                raise ValueError(f"Profile {uid} is not running")
            pages = handle.context.pages
            page = pages[0] if pages else await handle.context.new_page()
            result = await page.evaluate(args["script"])
            return {"result": result}

        elif name == "get_cookies":
            uid = args["user_id"]
            handle = launcher.get_handle(uid)
            if not handle:
                raise ValueError(f"Profile {uid} is not running")
            cookies = await handle.context.cookies(args.get("urls", []))
            return {"cookies": cookies}

        elif name == "set_cookies":
            uid = args["user_id"]
            handle = launcher.get_handle(uid)
            if not handle:
                raise ValueError(f"Profile {uid} is not running")
            await handle.context.add_cookies(args["cookies"])
            return {"set": len(args["cookies"])}

        elif name == "check_proxy":
            uid = args["user_id"]
            p = store.get(uid)
            if p is None:
                raise ValueError(f"Profile {uid} not found")
            from ..core.proxy import parse_proxy, check_proxy
            cfg = parse_proxy(p.proxy)
            result = await check_proxy(cfg)
            return result

        elif name == "chain_monitor_wallets":
            from ..core.chain import ChainClient, get_chain, is_valid_address
            cfg = get_chain(args.get("chain", "robinhood"))
            addresses = args["addresses"]
            bad = [a for a in addresses if not is_valid_address(a)]
            if bad:
                raise ValueError(f"invalid address(es): {', '.join(bad)}")
            client = ChainClient(cfg)
            summaries = client.monitor_wallets(addresses, tx_limit=args.get("tx_limit", 50))
            return {"chain": cfg.name, "wallets": [s.to_dict() for s in summaries]}

        elif name == "chain_early_buyers":
            from ..core.chain import ChainClient, get_chain, is_valid_address
            cfg = get_chain(args.get("chain", "robinhood"))
            token = args["token"]
            if not is_valid_address(token):
                raise ValueError(f"invalid token address: {token}")
            client = ChainClient(cfg)
            buyers = client.early_buyers(
                token,
                from_block=args.get("from_block", "earliest"),
                to_block=args.get("to_block", "latest"),
                exclude=args.get("exclude"),
                limit=args.get("limit", 20),
            )
            return {"chain": cfg.name, "token": token, "buyers": [b.to_dict() for b in buyers]}

        else:
            raise ValueError(f"Unknown tool: {name}")

    def _response(self, req_id: Any, result: Any) -> Dict[str, Any]:
        return {"jsonrpc": "2.0", "id": req_id, "result": result}

    def _error(self, req_id: Any, code: int, message: str) -> Dict[str, Any]:
        return {"jsonrpc": "2.0", "id": req_id, "error": {"code": code, "message": message}}


async def run_stdio_server():
    """Run the MCP server on stdin/stdout (for Claude Desktop, Cursor, etc.)."""
    server = MCPServer()
    reader = asyncio.StreamReader()
    protocol = asyncio.StreamReaderProtocol(reader)
    await asyncio.get_event_loop().connect_read_pipe(lambda: protocol, sys.stdin.buffer)

    writer_transport, writer_protocol = await asyncio.get_event_loop().connect_write_pipe(
        asyncio.streams.FlowControlMixin, sys.stdout.buffer
    )
    writer = asyncio.StreamWriter(writer_transport, writer_protocol, None, asyncio.get_event_loop())

    log.info("MCP server started on stdio")

    while True:
        try:
            line = await reader.readline()
            if not line:
                break
            line = line.decode("utf-8").strip()
            if not line:
                continue
            request = json.loads(line)
            response = await server.handle_request(request)
            if response is not None:
                out = json.dumps(response) + "\n"
                writer.write(out.encode("utf-8"))
                await writer.drain()
        except json.JSONDecodeError:
            continue
        except Exception as e:
            log.error(f"MCP error: {e}")
            continue


def main():
    """Entry point for `python -m src.mcp.server`."""
    logging.basicConfig(level=logging.INFO, stream=sys.stderr)
    asyncio.run(run_stdio_server())


if __name__ == "__main__":
    main()
