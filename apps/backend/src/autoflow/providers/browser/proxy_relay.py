from __future__ import annotations

import asyncio
import base64
import ipaddress
import select
import socket
import socketserver
import threading
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Self
from urllib.parse import SplitResult, urlsplit

import httpx

_MAX_HEADER = 64 * 1024
_MAX_CREDENTIAL = 4096
_CONNECT_TIMEOUT = 10.0


@dataclass(frozen=True)
class _Proxy:
    scheme: str
    host: str
    port: int
    username: str
    password: str


class BrowserProxyRelay:
    """Session-local HTTP proxy that keeps upstream credentials out of argv."""

    def __init__(self, proxy: dict[str, str]) -> None:
        self._proxy = _parse_proxy(proxy)
        self._server: _RelayServer | None = None
        self._thread: threading.Thread | None = None
        self._closed = threading.Event()
        self._connections: set[socket.socket] = set()
        self._connections_lock = threading.Lock()
        self._generation = 0

    @property
    def url(self) -> str:
        if self._server is None:
            raise RuntimeError("proxy relay is not running")
        return f"http://127.0.0.1:{self._server.server_address[1]}"

    def __enter__(self) -> Self:
        if self._server is not None:
            raise RuntimeError("proxy relay is already running")
        self._closed.clear()
        self._server = _RelayServer(("127.0.0.1", 0), _RelayHandler, self)
        self._thread = threading.Thread(
            target=self._server.serve_forever,
            name="autoflow-browser-proxy-relay",
            daemon=True,
        )
        self._thread.start()
        return self

    def __exit__(self, *_exc: object) -> None:
        self.close()

    def reset_connections(self) -> None:
        with self._connections_lock:
            self._generation += 1
            connections = tuple(self._connections)
            self._connections.clear()
        for connection in connections:
            _close_socket(connection)

    async def probe(self, reset: bool = False) -> dict:
        from autoflow.providers.proxy.probe import PROBE_URL
        if reset:
            self.reset_connections()
        try:
            async with (
                asyncio.timeout(10),
                httpx.AsyncClient(proxy=self.url, timeout=10, trust_env=False) as client,
                client.stream("GET", PROBE_URL) as response,
            ):
                response.raise_for_status()
                content = bytearray()
                async for chunk in response.aiter_bytes():
                    content.extend(chunk)
                    if len(content) > 4096:
                        raise ValueError("probe too large")
                import json
                address = ipaddress.ip_address(json.loads(content)["ip"])
                if not address.is_global:
                    raise ValueError("invalid probe address")
            return {"exitIp": str(address), "observedAt": datetime.now(UTC).isoformat(), "source": "session_relay", "error": None}
        except (httpx.HTTPError, TimeoutError, ValueError, KeyError, TypeError):
            return {"exitIp": None, "source": "session_relay", "error": {"code": "PROXY_PROBE_FAILED", "message": "会话出口检测失败"}}

    def close(self) -> None:
        server, thread = self._server, self._thread
        if server is None:
            return
        self._closed.set()
        server.shutdown()
        with self._connections_lock:
            connections = tuple(self._connections)
        for connection in connections:
            _close_socket(connection)
        server.server_close()
        if thread is not None:
            thread.join(timeout=2)
        self._server = None
        self._thread = None

    def _handle(self, client: socket.socket) -> None:
        generation = self._generation
        upstream: socket.socket | None = None
        try:
            client.settimeout(_CONNECT_TIMEOUT)
            self._track(client, generation)
            head, extra = _read_head(client)
            method, target, version = _request_line(head)
            if method == "CONNECT":
                host, port = _authority(target)
                upstream = self._connect(host, port, generation)
                tunnel_extra = b""
                if self._proxy.scheme == "http":
                    response, tunnel_extra = _http_connect(
                        upstream, target, self._proxy.username, self._proxy.password
                    )
                    if _status_code(response) != 200:
                        client.sendall(response)
                        return
                client.sendall(b"HTTP/1.1 200 Connection Established\r\n\r\n")
                _bridge(
                    client,
                    upstream,
                    to_upstream=extra,
                    to_client=tunnel_extra,
                    stopped=self._closed,
                )
                return

            parsed = _absolute_http_target(target)
            http_host = parsed.hostname
            assert http_host is not None
            upstream = self._connect(http_host, parsed.port or 80, generation)
            if self._proxy.scheme == "http":
                forwarded = _rewrite_head(
                    head,
                    method=method,
                    target=target,
                    version=version,
                    authorization=_basic(self._proxy.username, self._proxy.password),
                )
            else:
                origin = parsed.path or "/"
                if parsed.query:
                    origin += f"?{parsed.query}"
                forwarded = _rewrite_head(
                    head, method=method, target=origin, version=version
                )
            _bridge(
                client,
                upstream,
                to_upstream=forwarded + extra,
                stopped=self._closed,
            )
        except (OSError, ValueError):
            try:
                client.sendall(b"HTTP/1.1 502 Bad Gateway\r\nConnection: close\r\n\r\n")
            except OSError:
                pass
        finally:
            if upstream is not None:
                self._untrack(upstream)
                _close_socket(upstream)
            self._untrack(client)
            _close_socket(client)

    def _connect(self, host: str, port: int, generation: int | None = None) -> socket.socket:
        upstream = socket.create_connection(
            (self._proxy.host, self._proxy.port), timeout=_CONNECT_TIMEOUT
        )
        try:
            self._track(upstream, generation)
            upstream.settimeout(_CONNECT_TIMEOUT)
            if self._proxy.scheme == "socks5":
                _socks5_connect(
                    upstream,
                    host,
                    port,
                    self._proxy.username,
                    self._proxy.password,
                )
            return upstream
        except BaseException:
            self._untrack(upstream)
            _close_socket(upstream)
            raise

    def _track(self, connection: socket.socket, generation: int | None = None) -> None:
        with self._connections_lock:
            if self._closed.is_set() or generation is not None and generation != self._generation:
                raise OSError("proxy relay is closing")
            self._connections.add(connection)

    def _untrack(self, connection: socket.socket) -> None:
        with self._connections_lock:
            self._connections.discard(connection)


class _RelayServer(socketserver.ThreadingTCPServer):
    allow_reuse_address = False
    daemon_threads = True

    def __init__(
        self,
        address: tuple[str, int],
        handler: type[socketserver.BaseRequestHandler],
        relay: BrowserProxyRelay,
    ) -> None:
        self.relay = relay
        super().__init__(address, handler, bind_and_activate=True)


class _RelayHandler(socketserver.BaseRequestHandler):
    def handle(self) -> None:
        server = self.server
        assert isinstance(server, _RelayServer)
        server.relay._handle(self.request)


def _parse_proxy(value: dict[str, str]) -> _Proxy:
    if not isinstance(value, dict) or set(value) != {"server", "username", "password"}:
        raise ValueError("proxy must contain server, username and password")
    server, username, password = value["server"], value["username"], value["password"]
    if not all(isinstance(item, str) for item in (server, username, password)):
        raise ValueError("proxy values must be strings")
    parsed = urlsplit(server)
    try:
        port = parsed.port
    except ValueError:
        port = None
    if (
        parsed.scheme not in {"http", "socks5"}
        or parsed.hostname is None
        or port is None
        or parsed.username is not None
        or parsed.password is not None
        or parsed.path not in {"", "/"}
        or parsed.query
        or parsed.fragment
        or not 1 <= port <= 65535
        or not username
        or not password
        or len(username.encode()) > _MAX_CREDENTIAL
        or len(password.encode()) > _MAX_CREDENTIAL
    ):
        raise ValueError("proxy configuration is invalid")
    if parsed.scheme == "socks5" and (
        len(username.encode()) > 255 or len(password.encode()) > 255
    ):
        raise ValueError("SOCKS5 credentials are too long")
    return _Proxy(parsed.scheme, parsed.hostname, port, username, password)


def _read_head(connection: socket.socket) -> tuple[bytes, bytes]:
    content = bytearray()
    while b"\r\n\r\n" not in content:
        chunk = connection.recv(4096)
        if not chunk:
            raise ValueError("connection closed before request header")
        content.extend(chunk)
        if len(content) > _MAX_HEADER:
            raise ValueError("request header is too large")
    end = content.index(b"\r\n\r\n") + 4
    return bytes(content[:end]), bytes(content[end:])


def _request_line(head: bytes) -> tuple[str, str, str]:
    try:
        line = head.split(b"\r\n", 1)[0].decode("ascii")
        method, target, version = line.split(" ")
    except (UnicodeDecodeError, ValueError):
        raise ValueError("invalid proxy request") from None
    if not method.isalpha() or version not in {"HTTP/1.0", "HTTP/1.1"}:
        raise ValueError("invalid proxy request")
    return method.upper(), target, version


def _authority(value: str) -> tuple[str, int]:
    try:
        parsed = urlsplit(f"//{value}")
        host, port = parsed.hostname, parsed.port
    except ValueError:
        host = port = None
    if host is None or port is None or parsed.path or not 1 <= port <= 65535:
        raise ValueError("invalid CONNECT authority")
    return host, port


def _absolute_http_target(value: str) -> SplitResult:
    try:
        parsed = urlsplit(value)
        port = parsed.port
    except ValueError:
        raise ValueError("invalid HTTP proxy target") from None
    if (
        parsed.scheme != "http"
        or parsed.hostname is None
        or parsed.username is not None
        or parsed.password is not None
        or (port is not None and not 1 <= port <= 65535)
    ):
        raise ValueError("invalid HTTP proxy target")
    return parsed


def _rewrite_head(
    head: bytes,
    *,
    method: str,
    target: str,
    version: str,
    authorization: str | None = None,
) -> bytes:
    headers = []
    for line in head.split(b"\r\n")[1:]:
        if not line:
            continue
        name = line.split(b":", 1)[0].strip().lower()
        if name in {b"proxy-authorization", b"proxy-connection"}:
            continue
        headers.append(line)
    if authorization is not None:
        headers.append(f"Proxy-Authorization: Basic {authorization}".encode("ascii"))
    return b"\r\n".join(
        [f"{method} {target} {version}".encode("ascii"), *headers, b"", b""]
    )


def _http_connect(
    upstream: socket.socket, target: str, username: str, password: str
) -> tuple[bytes, bytes]:
    authorization = _basic(username, password)
    upstream.sendall(
        (
            f"CONNECT {target} HTTP/1.1\r\n"
            f"Host: {target}\r\n"
            f"Proxy-Authorization: Basic {authorization}\r\n"
            "Proxy-Connection: Keep-Alive\r\n\r\n"
        ).encode("ascii")
    )
    return _read_head(upstream)


def _status_code(head: bytes) -> int:
    try:
        return int(head.split(b"\r\n", 1)[0].split(b" ", 2)[1])
    except (IndexError, ValueError):
        raise ValueError("invalid upstream proxy response") from None


def _basic(username: str, password: str) -> str:
    return base64.b64encode(f"{username}:{password}".encode()).decode("ascii")


def _socks5_connect(
    upstream: socket.socket,
    host: str,
    port: int,
    username: str,
    password: str,
) -> None:
    user, secret = username.encode(), password.encode()
    upstream.sendall(b"\x05\x01\x02")
    if _recv_exact(upstream, 2) != b"\x05\x02":
        raise OSError("SOCKS5 authentication method rejected")
    upstream.sendall(b"\x01" + bytes([len(user)]) + user + bytes([len(secret)]) + secret)
    if _recv_exact(upstream, 2) != b"\x01\x00":
        raise OSError("SOCKS5 authentication failed")
    address = _socks_address(host)
    upstream.sendall(b"\x05\x01\x00" + address + port.to_bytes(2, "big"))
    reply = _recv_exact(upstream, 4)
    if reply[:2] != b"\x05\x00":
        raise OSError("SOCKS5 connection failed")
    _recv_exact(upstream, _socks_address_length(upstream, reply[3]) + 2)


def _socks_address(host: str) -> bytes:
    try:
        value = ipaddress.ip_address(host)
    except ValueError:
        encoded = host.encode("idna")
        if not encoded or len(encoded) > 255:
            raise ValueError("SOCKS5 hostname is invalid") from None
        return b"\x03" + bytes([len(encoded)]) + encoded
    return (b"\x01" if value.version == 4 else b"\x04") + value.packed


def _socks_address_length(connection: socket.socket, address_type: int) -> int:
    if address_type == 1:
        return 4
    if address_type == 4:
        return 16
    if address_type == 3:
        return _recv_exact(connection, 1)[0]
    raise OSError("SOCKS5 returned an invalid address")


def _recv_exact(connection: socket.socket, length: int) -> bytes:
    content = bytearray()
    while len(content) < length:
        chunk = connection.recv(length - len(content))
        if not chunk:
            raise OSError("connection closed")
        content.extend(chunk)
    return bytes(content)


def _bridge(
    left: socket.socket,
    right: socket.socket,
    *,
    to_upstream: bytes = b"",
    to_client: bytes = b"",
    stopped: threading.Event,
) -> None:
    if to_upstream:
        right.sendall(to_upstream)
    if to_client:
        left.sendall(to_client)
    peers = {left: right, right: left}
    while peers and not stopped.is_set():
        readable, _, _ = select.select(tuple(peers), (), (), 0.25)
        for source in readable:
            target = peers[source]
            try:
                content = source.recv(64 * 1024)
                if content:
                    target.sendall(content)
                    continue
            except OSError:
                pass
            peers.pop(source, None)
            try:
                target.shutdown(socket.SHUT_WR)
            except OSError:
                pass


def _close_socket(connection: socket.socket) -> None:
    try:
        connection.shutdown(socket.SHUT_RDWR)
    except OSError:
        pass
    connection.close()
