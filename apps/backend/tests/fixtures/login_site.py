from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread
from urllib.parse import parse_qs

SESSION_COOKIE = "autoflow_login"
SESSION_VALUE = "fixture-session"
PAGE = Path(__file__).with_name("login-site.html")


class LoginSite:
    def __init__(self) -> None:
        self.requests: list[str] = []
        site = self

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                site.requests.append(self.path)
                cookies = self.headers.get("Cookie", "")
                signed_in = f"{SESSION_COOKIE}=" in cookies
                if self.path == "/me":
                    body = ("已登录" if signed_in else "未登录").encode("utf-8")
                    self.send_response(200 if signed_in else 401)
                    self.send_header("Content-Type", "text/plain; charset=utf-8")
                    self.send_header("Content-Length", str(len(body)))
                    self.end_headers()
                    self.wfile.write(body)
                    return
                html = PAGE.read_text(encoding="utf-8")
                if signed_in:
                    html = html.replace("未登录", "已登录")
                content = html.encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(content)))
                self.end_headers()
                self.wfile.write(content)

            def do_POST(self):
                site.requests.append(self.path)
                length = int(self.headers.get("Content-Length") or 0)
                form = parse_qs(self.rfile.read(length).decode("utf-8"))
                user = (form.get("user") or [""])[0]
                password = (form.get("password") or [""])[0]
                if self.path != "/login" or user != "demo" or password != "pass":
                    self.send_response(401)
                    self.end_headers()
                    return
                self.send_response(303)
                self.send_header(
                    "Set-Cookie",
                    f"{SESSION_COOKIE}={SESSION_VALUE}; Path=/; Max-Age=86400; HttpOnly; SameSite=Lax",
                )
                self.send_header("Location", "/")
                self.end_headers()

            def log_message(self, *_args):
                return

        self._server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self._thread = Thread(target=self._server.serve_forever, daemon=True)

    @property
    def url(self) -> str:
        return f"http://127.0.0.1:{self._server.server_port}/"

    def start(self) -> "LoginSite":
        self._thread.start()
        return self

    def close(self) -> None:
        self._server.shutdown()
        self._server.server_close()
        self._thread.join(timeout=2)
