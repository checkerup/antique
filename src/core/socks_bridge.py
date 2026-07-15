"""Local unauthenticated SOCKS5 bridge for authenticated upstream proxies.

Chromium does not support username/password authentication for SOCKS5 proxies.
AdsPower backups commonly contain authenticated SOCKS5 credentials, which made
Playwright abort profile launch and the API surface a generic HTTP 500.  This
module starts a tiny loopback-only SOCKS5 server. Chromium talks to it without
authentication; the bridge authenticates to the original upstream proxy and
relays the TCP stream.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Optional


class SocksBridgeError(RuntimeError):
    pass


async def _read_reply_address(reader: asyncio.StreamReader, atyp: int) -> bytes:
    if atyp == 1:
        return await reader.readexactly(4)
    if atyp == 4:
        return await reader.readexactly(16)
    if atyp == 3:
        size = await reader.readexactly(1)
        return size + await reader.readexactly(size[0])
    raise SocksBridgeError(f"unsupported SOCKS address type: {atyp}")


async def _pipe(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
    try:
        while True:
            chunk = await reader.read(65536)
            if not chunk:
                break
            writer.write(chunk)
            await writer.drain()
    except (ConnectionError, asyncio.CancelledError):
        pass
    finally:
        try:
            writer.close()
        except Exception:
            pass


@dataclass
class Socks5AuthBridge:
    upstream_host: str
    upstream_port: int
    username: str
    password: str
    connect_timeout: float = 15.0

    _server: Optional[asyncio.AbstractServer] = None
    _host: str = "127.0.0.1"
    _port: int = 0

    @property
    def server_url(self) -> str:
        if not self._server or not self._port:
            raise SocksBridgeError("bridge is not running")
        return f"socks5://{self._host}:{self._port}"

    async def start(self) -> "Socks5AuthBridge":
        if self._server:
            return self
        self._server = await asyncio.start_server(self._handle_client, self._host, 0)
        sock = self._server.sockets[0]
        self._port = int(sock.getsockname()[1])
        return self

    async def close(self) -> None:
        if self._server:
            self._server.close()
            await self._server.wait_closed()
            self._server = None
            self._port = 0

    async def _handle_client(self, client_r: asyncio.StreamReader, client_w: asyncio.StreamWriter) -> None:
        upstream_w: Optional[asyncio.StreamWriter] = None
        try:
            ver, nmethods = await client_r.readexactly(2)
            if ver != 5:
                raise SocksBridgeError("client is not SOCKS5")
            await client_r.readexactly(nmethods)
            client_w.write(b"\x05\x00")
            await client_w.drain()

            ver, cmd, _reserved, atyp = await client_r.readexactly(4)
            if ver != 5 or cmd != 1:
                client_w.write(b"\x05\x07\x00\x01\x00\x00\x00\x00\x00\x00")
                await client_w.drain()
                return
            raw_addr = await _read_reply_address(client_r, atyp)
            raw_port = await client_r.readexactly(2)

            upstream_r, upstream_w = await asyncio.wait_for(
                asyncio.open_connection(self.upstream_host, self.upstream_port),
                timeout=self.connect_timeout,
            )
            upstream_w.write(b"\x05\x02\x00\x02")
            await upstream_w.drain()
            reply = await upstream_r.readexactly(2)
            if reply[0] != 5 or reply[1] not in (0, 2):
                raise SocksBridgeError("upstream proxy rejected authentication methods")
            if reply[1] == 2:
                user = self.username.encode("utf-8")
                password = self.password.encode("utf-8")
                if len(user) > 255 or len(password) > 255:
                    raise SocksBridgeError("SOCKS credentials are too long")
                upstream_w.write(bytes((1, len(user))) + user + bytes((len(password),)) + password)
                await upstream_w.drain()
                auth_reply = await upstream_r.readexactly(2)
                if auth_reply != b"\x01\x00":
                    raise SocksBridgeError("upstream SOCKS authentication failed")

            upstream_w.write(bytes((5, 1, 0, atyp)) + raw_addr + raw_port)
            await upstream_w.drain()
            head = await upstream_r.readexactly(4)
            bound = await _read_reply_address(upstream_r, head[3])
            bound_port = await upstream_r.readexactly(2)
            client_w.write(head + bound + bound_port)
            await client_w.drain()
            if head[1] != 0:
                return

            await asyncio.gather(
                _pipe(client_r, upstream_w),
                _pipe(upstream_r, client_w),
                return_exceptions=True,
            )
        except (asyncio.IncompleteReadError, ConnectionError, OSError, SocksBridgeError):
            try:
                client_w.write(b"\x05\x01\x00\x01\x00\x00\x00\x00\x00\x00")
                await client_w.drain()
            except Exception:
                pass
        finally:
            try:
                client_w.close()
                await client_w.wait_closed()
            except Exception:
                pass
            if upstream_w is not None:
                try:
                    upstream_w.close()
                    await upstream_w.wait_closed()
                except Exception:
                    pass
