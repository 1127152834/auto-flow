"""Real loopback TLS mail transport through production worker and executors.

The only transport redirect is smtp.qq.com:465 -> fixture random loopback port.
The production SMTP/IMAP clients, MIME codecs, executors and worker run unchanged.
This verifies local protocol behavior, not delivery by an external mail provider.
"""

from __future__ import annotations

import asyncio
import base64
import socket
import ssl
import sys
from datetime import UTC, datetime, timedelta
from email import policy
from email.message import EmailMessage
from email.parser import BytesParser
from pathlib import Path
from threading import Event, Thread
from typing import Any

import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID

from autoflow.infrastructure.process.workflow_worker import WorkflowWorkerManager


class LocalMailServer:
    def __init__(self, root: Path, protocol: str, behavior: str = "ok") -> None:
        root.mkdir()
        key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "localhost")])
        cert = (
            x509.CertificateBuilder()
            .subject_name(name)
            .issuer_name(name)
            .public_key(key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(datetime.now(UTC) - timedelta(minutes=1))
            .not_valid_after(datetime.now(UTC) + timedelta(hours=1))
            .sign(key, hashes.SHA256())
        )
        (root / "key.pem").write_bytes(
            key.private_bytes(
                serialization.Encoding.PEM,
                serialization.PrivateFormat.PKCS8,
                serialization.NoEncryption(),
            )
        )
        (root / "cert.pem").write_bytes(cert.public_bytes(serialization.Encoding.PEM))
        self.tls = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        self.tls.load_cert_chain(root / "cert.pem", root / "key.pem")
        self.listener = socket.socket()
        self.listener.bind(("127.0.0.1", 0))
        self.listener.listen()
        self.listener.settimeout(0.1)
        self.port = self.listener.getsockname()[1]
        self.protocol = protocol
        self.behavior = behavior
        self.closed = Event()
        self.blocked = Event()
        self.disconnected = Event()
        self.commands: list[str] = []
        self.messages: list[bytes] = []
        self.envelopes: list[str] = []
        self.errors: list[str] = []
        self.connections: list[ssl.SSLSocket] = []
        self.handlers: list[Thread] = []
        self.thread = Thread(target=self._listen, daemon=True)
        self.thread.start()

    def _listen(self) -> None:
        while not self.closed.is_set():
            try:
                raw, _ = self.listener.accept()
            except TimeoutError:
                continue
            except OSError:
                break
            thread = Thread(target=self._handle, args=(raw,), daemon=True)
            self.handlers.append(thread)
            thread.start()

    def _handle(self, raw: socket.socket) -> None:
        try:
            with self.tls.wrap_socket(raw, server_side=True) as connection:
                self.connections.append(connection)
                connection.settimeout(10)
                with connection.makefile("rwb", buffering=0) as stream:
                    if self.protocol == "smtp":
                        self._smtp(stream)
                    else:
                        self._imap(stream)
        except (OSError, ssl.SSLError) as error:
            if not self.closed.is_set():
                self.errors.append(type(error).__name__)
        finally:
            raw.close()
            self.disconnected.set()

    def _stall(self, stream: socket.SocketIO) -> None:
        self.blocked.set()
        # Observe actual client EOF after cancellation, not fixture shutdown.
        assert stream.read(1) == b""

    def _smtp(self, stream: socket.SocketIO) -> None:
        stream.write(b"220 localhost controlled SMTP\r\n")
        while line := stream.readline():
            verb = line.split()[0].decode().upper()
            self.commands.append(verb)
            if verb == "EHLO":
                stream.write(b"250-localhost\r\n250 AUTH PLAIN\r\n")
            elif verb == "AUTH":
                assert (
                    base64.b64decode(line.split()[2])
                    == b"\x00sender@qq.com\x00fixture-secret"
                )
                stream.write(
                    b"535 auth rejected\r\n"
                    if self.behavior == "auth"
                    else b"235 authenticated\r\n"
                )
            elif verb == "MAIL":
                self.envelopes.append(line.decode().strip())
                stream.write(b"250 sender accepted\r\n")
            elif verb == "RCPT":
                self.envelopes.append(line.decode().strip())
                stream.write(
                    b"550 recipient rejected\r\n"
                    if self.behavior == "recipient"
                    else b"250 recipient accepted\r\n"
                )
            elif verb == "DATA":
                if self.behavior == "stall":
                    self._stall(stream)
                    return
                stream.write(b"354 send data\r\n")
                chunks = []
                while (chunk := stream.readline()) != b".\r\n":
                    assert chunk
                    chunks.append(chunk[1:] if chunk.startswith(b"..") else chunk)
                self.messages.append(b"".join(chunks))
                stream.write(b"250 queued locally\r\n")
            elif verb == "RSET":
                stream.write(b"250 reset\r\n")
            elif verb == "QUIT":
                stream.write(b"221 bye\r\n")
                return
            else:
                raise AssertionError(f"Unexpected SMTP verb {verb}")

    def _imap(self, stream: socket.SocketIO) -> None:
        stream.write(b"* OK controlled IMAP4rev1\r\n")
        while line := stream.readline():
            tag, verb, *args = line.decode().strip().split()
            verb = verb.upper()
            self.commands.append(verb)
            response = b""
            if verb == "CAPABILITY":
                response = b"* CAPABILITY IMAP4rev1\r\n"
            elif verb == "LOGIN":
                assert args == ["reader@example.test", '"fixture-secret"']
                if self.behavior == "auth":
                    stream.write(f"{tag} NO auth rejected\r\n".encode())
                    continue
            elif verb == "SELECT":
                assert args == ["INBOX"]
                response = b"* 4 EXISTS\r\n"
            elif verb == "SEARCH":
                assert args == ["UNSEEN"]
                if self.behavior == "stall":
                    self._stall(stream)
                    return
                response = (
                    b"* SEARCH\r\n"
                    if self.behavior == "empty"
                    else b"* SEARCH 1 2 3 4\r\n"
                )
            elif verb == "FETCH":
                number = int(args[0])
                message = EmailMessage()
                message["From"] = (
                    "other@example.test"
                    if number == 1
                    else "Sender <sender@example.test>"
                )
                message["Subject"] = "忽略" if number == 2 else f"订单完成 {number}"
                message["Date"] = "Wed, 23 Sep 2026 10:00:00 +0800"
                message.set_content(f"中文正文 {number}\n第二行")
                message.add_alternative("<b>HTML 不取代纯文本</b>", subtype="html")
                raw = message.as_bytes(policy=policy.SMTP)
                response = (
                    f"* {number} FETCH (RFC822 {{{len(raw)}}}\r\n".encode()
                    + raw
                    + b")\r\n"
                )
            elif verb == "STORE":
                self.envelopes.append(" ".join(args))
            elif verb == "CLOSE":
                pass
            elif verb == "LOGOUT":
                stream.write(b"* BYE logged out\r\n" + f"{tag} OK logout\r\n".encode())
                return
            else:
                raise AssertionError(f"Unexpected IMAP verb {verb}")
            stream.write(response + f"{tag} OK {verb}\r\n".encode())

    def close(self) -> None:
        self.closed.set()
        self.listener.close()
        for connection in self.connections:
            try:
                connection.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
        self.thread.join(2)
        for handler in self.handlers:
            handler.join(2)


def worker(
    tmp_path: Path, server: LocalMailServer, events: list[dict[str, object]]
) -> WorkflowWorkerManager:
    # A child-local address rewrite exercises the hard-coded original QQ endpoint
    # without DNS, outside connections, monkeypatched SMTP clients or fake results.
    boot = f"""import socket, runpy, sys
original = socket.create_connection
def local_connection(address, *args, **kwargs):
    if address == ("smtp.qq.com", 465):
        address = ("127.0.0.1", {server.port})
    if address[0] != "127.0.0.1":
        raise OSError("External network forbidden in mail fixture")
    return original(address, *args, **kwargs)
socket.create_connection = local_connection
sys.argv = ["autoflow", "--workflow-worker"]
runpy.run_module("autoflow", run_name="__main__")
"""
    return WorkflowWorkerManager(
        tmp_path,
        command=(sys.executable, "-c", boot),
        termination_timeout=0.3,
        on_event=events.append,
    )


def payload(tmp_path: Path, server: LocalMailServer) -> dict[str, Any]:
    config: dict[str, Any] = (
        {
            "senderEmail": "sender@qq.com",
            "authCode": "fixture-secret",
            "recipientEmail": "recipient@example.test",
            "emailSubject": "中文主题",
            "emailContent": "正文第一行\n.正文第二行",
            "timeout": 30,
        }
        if server.protocol == "smtp"
        else {
            "emailServer": "127.0.0.1",
            "emailPort": server.port,
            "emailAccount": "reader@example.test",
            "emailPassword": "fixture-secret",
            "fromFilter": "sender@",
            "subjectFilter": "完成",
            "checkInterval": 1,
            "timeout": 2,
            "saveToVariable": "mail",
        }
    )
    return {
        "runId": "mail-run",
        "workflowId": "mail-flow",
        "profileId": "profile-1",
        "requiresBrowser": False,
        "artifactRoot": str(tmp_path / "artifacts"),
        "document": {
            "nodes": [
                {
                    "id": "mail",
                    "type": "moduleNode",
                    "data": {
                        "moduleType": "send_email"
                        if server.protocol == "smtp"
                        else "email_trigger",
                        "config": config,
                    },
                },
                {
                    "id": "after",
                    "type": "moduleNode",
                    "data": {
                        "moduleType": "print_log",
                        "config": {
                            "logMessage": "邮件后续步骤"
                            if server.protocol == "smtp"
                            else "收到 {mail}"
                        },
                    },
                },
            ],
            "edges": [{"id": "next", "source": "mail", "target": "after"}],
            "variables": [],
        },
    }


async def finished(manager: WorkflowWorkerManager) -> None:
    async with asyncio.timeout(12):
        while manager.busy():
            await asyncio.sleep(0.02)


@pytest.mark.asyncio
@pytest.mark.parametrize("protocol", ["smtp", "imap"])
async def test_real_mail_worker_mime_and_cleanup(tmp_path: Path, protocol: str) -> None:
    server = LocalMailServer(tmp_path / "mail-server", protocol)
    events: list[dict[str, object]] = []
    manager = worker(tmp_path, server, events)
    try:
        await manager.start("mail-run", "profile-1", None, payload(tmp_path, server))
        await finished(manager)
        complete = [
            event for event in events if event.get("type") == "execution:node_complete"
        ]
        assert len(complete) == 2, events
        assert all(event.get("success") is True for event in complete), events
        assert manager.active_processes() == []
        assert server.disconnected.is_set()
        assert not server.errors
        assert "fixture-secret" not in str(events)
        if protocol == "smtp":
            assert len(server.messages) == 1
            message = BytesParser(policy=policy.default).parsebytes(server.messages[0])
            assert message["Subject"] == "中文主题"
            assert message["From"] == "sender@qq.com"
            assert message["To"] == "recipient@example.test"
            assert (
                message.get_content().replace("\r\n", "\n")
                == "正文第一行\n.正文第二行\n"
            )
            assert server.envelopes == [
                "mail FROM:<sender@qq.com>",
                "rcpt TO:<recipient@example.test>",
            ]
            assert server.commands[-1] == "QUIT"
        else:
            data = complete[0]["data"]
            assert isinstance(data, dict)
            assert data["subject"] == "订单完成 4"
            assert data["body"].replace("\r\n", "\n") == "中文正文 4\n第二行\n"
            assert data["from"] == "sender@example.test"
            assert server.envelopes == ["3 +FLAGS (\\Seen)", "4 +FLAGS (\\Seen)"]
            assert server.commands[-2:] == ["CLOSE", "LOGOUT"]
            assert "订单完成 4" in str(complete[1]["data"])
            assert "{mail}" not in str(complete[1]["data"])
    finally:
        await manager.shutdown()
        server.close()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("protocol", "behavior", "error"),
    [
        ("smtp", "auth", "邮箱认证失败"),
        ("smtp", "recipient", "发送邮件失败"),
        ("imap", "auth", "邮件监控等待超时"),
        ("imap", "empty", "邮件监控等待超时"),
    ],
)
async def test_real_mail_worker_errors_do_not_run_successor(
    tmp_path: Path, protocol: str, behavior: str, error: str
) -> None:
    server = LocalMailServer(tmp_path / "mail-server", protocol, behavior)
    events: list[dict[str, object]] = []
    manager = worker(tmp_path, server, events)
    try:
        await manager.start("mail-run", "profile-1", None, payload(tmp_path, server))
        await finished(manager)
        assert any(error in str(event) for event in events), events
        assert not any(event.get("nodeId") == "after" for event in events)
        assert manager.active_processes() == []
        assert server.disconnected.is_set()
        assert not server.messages
        assert not server.errors
        assert "fixture-secret" not in str(events)
    finally:
        await manager.shutdown()
        server.close()


@pytest.mark.asyncio
@pytest.mark.parametrize("protocol", ["smtp", "imap"])
async def test_real_mail_worker_stop_closes_blocked_tls_socket(
    tmp_path: Path, protocol: str
) -> None:
    server = LocalMailServer(tmp_path / "mail-server", protocol, "stall")
    events: list[dict[str, object]] = []
    manager = worker(tmp_path, server, events)
    try:
        await manager.start("mail-run", "profile-1", None, payload(tmp_path, server))
        async with asyncio.timeout(6):
            while not server.blocked.is_set():
                await asyncio.sleep(0.02)
        started = asyncio.get_running_loop().time()
        await manager.stop("mail-run")
        assert asyncio.get_running_loop().time() - started < 3
        async with asyncio.timeout(3):
            while not server.disconnected.is_set():
                await asyncio.sleep(0.02)
        assert manager.active_processes() == []
        assert not manager.busy()
        assert not any(event.get("nodeId") == "after" for event in events)
        assert not any(event.get("type") == "execution:completed" for event in events)
        assert not server.messages
        assert not server.errors
    finally:
        await manager.shutdown()
        server.close()
