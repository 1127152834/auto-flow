"""Real loopback HTTP and real files; no fixtures or production data.

Run from repo root: PYTHONPATH=apps/backend/src apps/backend/.venv/bin/python
docs/qa/2026-09-28-system-audit/security/real_share_probe.py
"""
import http.client
import json
import tempfile
import threading
from pathlib import Path

from autoflow.infrastructure.sharing.file_share import FileShareHandler, ThreadedHTTPServer


def main():
    with tempfile.TemporaryDirectory(prefix="autoflow-security-share-") as directory:
        root = Path(directory)
        shared = root / "published"
        shared.mkdir()
        (shared / "report.txt").write_text("Published report", encoding="utf-8")
        outside = root / "private-report.txt"
        outside.write_text("QA-only outside-share sentinel", encoding="utf-8")
        (shared / "linked-report.txt").symlink_to(outside)
        written_outside = root / "outside-created.txt"
        (shared / "report_1.txt").symlink_to(written_outside)
        config = {"path": str(shared), "type": "folder", "name": "QA", "allow_write": True}
        handler = type("IsolatedShareHandler", (FileShareHandler,), {"share_config": config, "allow_write": True})
        # Same production HTTP server and handler, restricted to loopback for QA.
        server = ThreadedHTTPServer(("127.0.0.1", 0), handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        def request(method, path, body=None, headers=None):
            connection = http.client.HTTPConnection("127.0.0.1", server.server_port, timeout=5)
            try:
                connection.request(method, path, body=body, headers=headers or {})
                response = connection.getresponse()
                return response.status, response.read().decode("utf-8", errors="replace")
            finally:
                connection.close()
        try:
            direct_status, direct_body = request("GET", "/linked-report.txt")
            guarded_status, _ = request("GET", "/download/linked-report.txt")
            boundary = "autoflowQaBoundary20260928"
            body = (f"--{boundary}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"report.txt\"\r\nContent-Type: text/plain\r\n\r\nQA upload outside marker\r\n--{boundary}--\r\n").encode()
            upload_status, upload_body = request("POST", "/api/upload", body, {"Content-Type": f"multipart/form-data; boundary={boundary}"})
            preview_status, preview_body = request("GET", "/preview/report.txt")
            report = {
                "real_http": True,
                "bound_address": "127.0.0.1",
                "direct_symlink_read": {"status": direct_status, "outside_bytes_returned": direct_body == outside.read_text()},
                "guarded_symlink_read": {"status": guarded_status},
                "duplicate_name_upload": {"status": upload_status, "response": json.loads(upload_body), "created_outside_share": written_outside.exists(), "outside_content_matches": written_outside.exists() and written_outside.read_text() == "QA upload outside marker"},
                "document_preview": {"status": preview_status, "missing_module_in_response": "No module named" in preview_body and "file_preview" in preview_body},
            }
            print(json.dumps(report, ensure_ascii=False, indent=2))
            assert direct_status == 200 and report["direct_symlink_read"]["outside_bytes_returned"]
            assert guarded_status == 403
            assert upload_status == 200 and report["duplicate_name_upload"]["outside_content_matches"]
            assert preview_status == 500 and report["document_preview"]["missing_module_in_response"]
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=3)


if __name__ == "__main__":
    main()
