"""SSH proxy support: expose ``ssh://user@host`` as a local SOCKS5 endpoint.

Private networks often only hand out SSH access, so we spawn ``ssh -D`` as a
subprocess and point the browser at the resulting loopback SOCKS5 port.

Command building and port selection are pure helpers so the whole feature is
unit-testable without ever spawning ``ssh``.
"""
from __future__ import annotations

import socket
import subprocess
import time
from dataclasses import dataclass
from typing import Dict, List, Optional

from .proxy import ProxyConfig


class SSHTunnelError(RuntimeError):
    """Raised when an SSH tunnel cannot be described or started."""


def pick_free_port() -> int:
    """Ask the OS for an unused loopback port."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def build_ssh_command(cfg: ProxyConfig, local_port: int) -> List[str]:
    """Build the ``ssh -D`` argument vector for a dynamic SOCKS5 tunnel."""
    if cfg.type != "ssh":
        raise SSHTunnelError(f"expected an ssh proxy, got {cfg.type!r}")
    if not cfg.host:
        raise SSHTunnelError("ssh proxy needs a host")
    if local_port <= 0:
        raise SSHTunnelError("local_port must be a positive port number")
    target = f"{cfg.username}@{cfg.host}" if cfg.username else cfg.host
    command = [
        "ssh",
        "-N",
        "-T",
        "-o", "ExitOnForwardFailure=yes",
        "-o", "StrictHostKeyChecking=accept-new",
        "-o", "ServerAliveInterval=30",
        "-D", f"127.0.0.1:{local_port}",
    ]
    if cfg.port:
        command += ["-p", str(cfg.port)]
    command.append(target)
    return command


def local_socks_config(local_port: int) -> ProxyConfig:
    """The loopback SOCKS5 config the browser should actually use."""
    return ProxyConfig(type="socks5", host="127.0.0.1", port=int(local_port))


@dataclass
class SSHTunnel:
    local_port: int
    command: List[str]
    process: Optional[subprocess.Popen] = None

    @property
    def proxy(self) -> ProxyConfig:
        return local_socks_config(self.local_port)

    def is_alive(self) -> bool:
        return self.process is not None and self.process.poll() is None

    def close(self) -> None:
        if self.process is None:
            return
        try:
            self.process.terminate()
            self.process.wait(timeout=5)
        except Exception:
            try:
                self.process.kill()
            except Exception:
                pass
        finally:
            self.process = None


class SSHTunnelManager:
    """Keeps one tunnel per profile and reuses it while it stays alive."""

    def __init__(self, spawn=None, port_picker=None):
        self._spawn = spawn or (lambda cmd: subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL))
        self._port_picker = port_picker or pick_free_port
        self._tunnels: Dict[str, SSHTunnel] = {}

    def ensure(self, key: str, cfg: ProxyConfig, *, wait: float = 0.0) -> SSHTunnel:
        existing = self._tunnels.get(key)
        if existing is not None and existing.is_alive():
            return existing
        if existing is not None:
            existing.close()
        port = self._port_picker()
        command = build_ssh_command(cfg, port)
        process = self._spawn(command)
        tunnel = SSHTunnel(local_port=port, command=command, process=process)
        if wait:
            time.sleep(wait)
        if process is not None and process.poll() not in (None, 0):
            raise SSHTunnelError("ssh exited immediately; check credentials or host reachability")
        self._tunnels[key] = tunnel
        return tunnel

    def close(self, key: str) -> bool:
        tunnel = self._tunnels.pop(key, None)
        if tunnel is None:
            return False
        tunnel.close()
        return True

    def close_all(self) -> None:
        for key in list(self._tunnels):
            self.close(key)

    @property
    def active(self) -> Dict[str, int]:
        return {key: tunnel.local_port for key, tunnel in self._tunnels.items() if tunnel.is_alive()}
