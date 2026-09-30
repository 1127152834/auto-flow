"""Local golden-scenario site with fault injection (remediation M0, spec §5.4)."""

from __future__ import annotations

import html
import threading
from collections import Counter
from contextlib import suppress
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Self
from urllib.parse import parse_qs, urlsplit

FIELDS = ("title", "price", "sku", "stock", "seller")
FIRST_LOAD_DELAY_SECONDS = 20.0
LOST_RESPONSE_HOLD_SECONDS = 30.0


class GoldenSite:
    """Serve /item/<id>, /form and /submit on a random local port."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._stopping = threading.Event()
        self._hits: Counter[str] = Counter()
        self._submissions: Counter[str] = Counter()
        self._delayed: set[str] = set()
        self._server: ThreadingHTTPServer | None = None
        self._thread: threading.Thread | None = None

    @property
    def base_url(self) -> str:
        assert self._server is not None, "site is not running"
        return f"http://127.0.0.1:{self._server.server_port}"

    def hits(self, prefix: str) -> int:
        with self._lock:
            return sum(
                count for path, count in self._hits.items() if path.startswith(prefix)
            )

    def submissions(self, name: str) -> int:
        with self._lock:
            return self._submissions[name]

    def __enter__(self) -> Self:
        site = self
        self._stopping.clear()

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *_args: object) -> None:
                return None

            def _send(self, status: int, body: str) -> None:
                content = body.encode("utf-8")
                with suppress(BrokenPipeError, ConnectionResetError):
                    self.send_response(status)
                    self.send_header("Content-Type", "text/html; charset=utf-8")
                    self.send_header("Content-Length", str(len(content)))
                    self.end_headers()
                    self.wfile.write(content)

            def do_GET(self) -> None:
                url = urlsplit(self.path)
                with site._lock:
                    site._hits[url.path] += 1
                if url.path.startswith("/item/"):
                    self._item(url.path.removeprefix("/item/"))
                elif url.path == "/form":
                    name = html.escape(
                        (parse_qs(url.query).get("name") or [""])[0], quote=True
                    )
                    action = html.escape(
                        "/submit" + (f"?{url.query}" if url.query else ""), quote=True
                    )
                    self._send(
                        200,
                        f"<form method=post action='{action}'>"
                        f"<input id=name name=name value='{name}'>"
                        "<button id=submit type=submit>提交</button></form>",
                    )
                else:
                    self._send(404, "<h1>not found</h1>")

            def do_POST(self) -> None:
                url = urlsplit(self.path)
                with site._lock:
                    site._hits[url.path] += 1
                if url.path != "/submit":
                    self._send(404, "<h1>not found</h1>")
                    return
                length = int(self.headers.get("Content-Length") or 0)
                name = (
                    parse_qs(self.rfile.read(length).decode("utf-8")).get("name")
                    or [""]
                )[0]
                with site._lock:
                    site._submissions[name] += 1
                if name.startswith("lose-") or parse_qs(url.query).get("lose") == ["1"]:
                    site._stopping.wait(LOST_RESPONSE_HOLD_SECONDS)
                    self.close_connection = True
                    return
                self._send(200, f"<p id=result>ok:{html.escape(name)}</p>")

            def _item(self, identity: str) -> None:
                if identity.startswith("gone-"):
                    self._send(404, "<h1>gone</h1>")
                    return
                if identity.startswith("timeout-"):
                    with site._lock:
                        first = identity not in site._delayed
                        site._delayed.add(identity)
                    if first:
                        site._stopping.wait(FIRST_LOAD_DELAY_SECONDS)
                safe = html.escape(identity)
                spans = "".join(
                    f"<span id={field}>{field}-{safe}</span>" for field in FIELDS
                )
                self._send(200, f"<main>{spans}</main>")

        self._server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self._server.daemon_threads = True
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()
        return self

    def __exit__(self, *_exc: object) -> None:
        self._stopping.set()
        if self._server is not None:
            self._server.shutdown()
            self._server.server_close()
        if self._thread is not None:
            self._thread.join(timeout=5)
