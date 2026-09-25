from __future__ import annotations

import base64
import socket
import threading
import time
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import urlsplit

import pytest
from autoflow.providers.browser.proxy_relay import BrowserProxyRelay


class _TargetHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def do_GET(self) -> None:
        body = f"target:{self.path}".encode()
        self.send_response(200)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Connection", "close")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *_args: Any) -> None:
        pass


@contextmanager
def _target_server():
    server = ThreadingHTTPServer(("127.0.0.1", 0), _TargetHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield server.server_address[1]
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


@contextmanager
def _one_connection_server(handler):
    listener = socket.socket()
    listener.bind(("127.0.0.1", 0))
    listener.listen()
    listener.settimeout(2)
    errors: list[BaseException] = []

    def serve() -> None:
        try:
            connection, _ = listener.accept()
            with connection:
                connection.settimeout(2)
                handler(connection)
        except BaseException as error:  # noqa: BLE001 - surfaced in the test thread.
            errors.append(error)

    thread = threading.Thread(target=serve, daemon=True)
    thread.start()
    try:
        yield listener.getsockname()[1]
    finally:
        listener.close()
        thread.join(timeout=3)
        if errors:
            raise errors[0]


def _recv_exact(connection: socket.socket, length: int) -> bytes:
    content = bytearray()
    while len(content) < length:
        chunk = connection.recv(length - len(content))
        if not chunk:
            raise AssertionError("connection closed")
        content.extend(chunk)
    return bytes(content)


def _read_head(connection: socket.socket) -> bytes:
    content = bytearray()
    while b"\r\n\r\n" not in content:
        content.extend(connection.recv(4096))
    return bytes(content)


def _read_all(connection: socket.socket) -> bytes:
    content = bytearray()
    while chunk := connection.recv(4096):
        content.extend(chunk)
    return bytes(content)


def _request(relay_url: str, request: bytes) -> bytes:
    relay = urlsplit(relay_url)
    assert relay.hostname == "127.0.0.1" and relay.port is not None
    with socket.create_connection((relay.hostname, relay.port), timeout=2) as client:
        client.settimeout(2)
        client.sendall(request)
        return _read_all(client)


def _forward_one_http_request(connection: socket.socket, port: int) -> None:
    request = _read_head(connection)
    with socket.create_connection(("127.0.0.1", port), timeout=2) as target:
        target.sendall(request)
        response = _read_all(target)
    connection.sendall(response)


def test_socks5_upstream_authenticates_in_memory_and_forwards_http() -> None:
    observed = {}
    with _target_server() as target_port:

        def socks(connection: socket.socket) -> None:
            assert _recv_exact(connection, 3) == b"\x05\x01\x02"
            connection.sendall(b"\x05\x02")
            assert _recv_exact(connection, 1) == b"\x01"
            username = _recv_exact(connection, _recv_exact(connection, 1)[0])
            password = _recv_exact(connection, _recv_exact(connection, 1)[0])
            observed["credentials"] = (username, password)
            connection.sendall(b"\x01\x00")
            assert _recv_exact(connection, 4) == b"\x05\x01\x00\x01"
            host = socket.inet_ntoa(_recv_exact(connection, 4))
            port = int.from_bytes(_recv_exact(connection, 2), "big")
            observed["target"] = (host, port)
            connection.sendall(b"\x05\x00\x00\x01\x7f\x00\x00\x01\x00\x00")
            _forward_one_http_request(connection, target_port)

        with _one_connection_server(socks) as socks_port, BrowserProxyRelay(
            {
                "server": f"socks5://127.0.0.1:{socks_port}",
                "username": "socks-user",
                "password": "socks-pass",
            }
        ) as relay:
            assert "socks-user" not in relay.url and "socks-pass" not in relay.url
            relay_port = urlsplit(relay.url).port
            response = _request(
                relay.url,
                (
                    f"GET http://127.0.0.1:{target_port}/socks HTTP/1.1\r\n"
                    f"Host: 127.0.0.1:{target_port}\r\nConnection: close\r\n\r\n"
                ).encode(),
            )

    assert b"target:/socks" in response
    assert observed == {
        "credentials": (b"socks-user", b"socks-pass"),
        "target": ("127.0.0.1", target_port),
    }
    assert relay_port is not None
    with pytest.raises(OSError):
        socket.create_connection(("127.0.0.1", relay_port), timeout=0.2)


def test_http_upstream_authenticates_connect_and_forwards_tunnel() -> None:
    observed = {}
    with _target_server() as target_port:

        def http_proxy(connection: socket.socket) -> None:
            request = _read_head(connection)
            observed["request"] = request
            expected = base64.b64encode(b"http-user:http-pass")
            assert b"CONNECT 127.0.0.1:" + str(target_port).encode() in request
            assert b"Proxy-Authorization: Basic " + expected in request
            with socket.create_connection(("127.0.0.1", target_port), timeout=2) as target:
                connection.sendall(b"HTTP/1.1 200 Connection Established\r\n\r\n")
                target.sendall(_read_head(connection))
                connection.sendall(_read_all(target))

        with _one_connection_server(http_proxy) as proxy_port, BrowserProxyRelay(
            {
                "server": f"http://127.0.0.1:{proxy_port}",
                "username": "http-user",
                "password": "http-pass",
            }
        ) as relay:
            assert "http-user" not in relay.url and "http-pass" not in relay.url
            relay_address = urlsplit(relay.url)
            assert relay_address.hostname == "127.0.0.1" and relay_address.port
            relay_port = relay_address.port
            with socket.create_connection(
                (relay_address.hostname, relay_address.port), timeout=2
            ) as client:
                client.settimeout(2)
                client.sendall(
                    f"CONNECT 127.0.0.1:{target_port} HTTP/1.1\r\n\r\n".encode()
                )
                assert _read_head(client).startswith(b"HTTP/1.1 200")
                client.sendall(
                    f"GET /http HTTP/1.1\r\nHost: 127.0.0.1:{target_port}\r\nConnection: close\r\n\r\n".encode()
                )
                response = _read_all(client)

    assert b"target:/http" in response
    assert b"http-user:http-pass" not in observed["request"]
    with pytest.raises(OSError):
        socket.create_connection(("127.0.0.1", relay_port), timeout=0.2)


def test_http_connect_keeps_server_first_bytes_on_the_client_side() -> None:
    upstream_received = []

    def http_proxy(connection: socket.socket) -> None:
        _read_head(connection)
        connection.sendall(
            b"HTTP/1.1 200 Connection Established\r\n\r\nSERVER-FIRST"
        )
        upstream_received.append(connection.recv(64))

    with _one_connection_server(http_proxy) as proxy_port, BrowserProxyRelay(
        {
            "server": f"http://127.0.0.1:{proxy_port}",
            "username": "http-user",
            "password": "http-pass",
        }
    ) as relay:
        address = urlsplit(relay.url)
        assert address.hostname is not None and address.port is not None
        with socket.create_connection((address.hostname, address.port), timeout=2) as client:
            client.settimeout(2)
            client.sendall(b"CONNECT example.test:443 HTTP/1.1\r\n\r\n")
            response = bytearray()
            while not response.endswith(b"SERVER-FIRST"):
                response.extend(client.recv(4096))
            assert response.endswith(b"SERVER-FIRST")

    assert upstream_received == [b""]


def test_failed_socks_handshake_closes_the_tracked_upstream() -> None:
    upstream_closed = threading.Event()

    def socks(connection: socket.socket) -> None:
        assert _recv_exact(connection, 3) == b"\x05\x01\x02"
        connection.sendall(b"\x05\xff")
        while connection.recv(64):
            pass
        upstream_closed.set()

    with _one_connection_server(socks) as socks_port, BrowserProxyRelay(
        {
            "server": f"socks5://127.0.0.1:{socks_port}",
            "username": "socks-user",
            "password": "socks-pass",
        }
    ) as relay:
        response = _request(
            relay.url,
            b"CONNECT example.test:443 HTTP/1.1\r\nConnection: close\r\n\r\n",
        )
        assert response.startswith(b"HTTP/1.1 502")
        deadline = time.monotonic() + 2
        while not upstream_closed.is_set() and time.monotonic() < deadline:
            time.sleep(0.01)

    assert upstream_closed.is_set()


def test_reset_connections_keeps_listener_and_closes_existing_tunnels():
    relay = BrowserProxyRelay({'server': 'http://127.0.0.1:12345', 'username': 'u', 'password': 'p'})
    with relay:
        url = relay.url
        left, right = socket.socketpair()
        try:
            relay._track(left)
            relay.reset_connections()
            assert left.fileno() == -1
            assert relay.url == url
            assert not relay._closed.is_set()
        finally:
            left.close()
            right.close()
