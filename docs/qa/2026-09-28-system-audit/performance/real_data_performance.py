"""Measure production HTTP/SQLite using actual tracked repository file metadata."""
from __future__ import annotations

import base64
import json
import math
import os
import platform
import secrets
import subprocess
import sys
import tempfile
import threading
import time
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import httpx

ROOT = Path(__file__).resolve().parents[4]
EVIDENCE = Path(__file__).resolve().parent


def encoded(value):
    return base64.urlsafe_b64encode(json.dumps(value, separators=(",", ":")).encode()).decode().rstrip("=")


def summary(values):
    ordered = sorted(values)
    return {"samples": len(values), "p50Ms": round(ordered[math.ceil(.50 * len(ordered)) - 1], 3),
            "p95Ms": round(ordered[math.ceil(.95 * len(ordered)) - 1], 3),
            "minMs": round(min(values), 3), "maxMs": round(max(values), 3)}


def main():
    files = []
    tracked = subprocess.check_output(["git", "ls-files", "-z"], cwd=ROOT).split(b"\0")
    for entry in tracked:
        if not entry:
            continue
        relative = entry.decode()
        source = ROOT / relative
        if source.is_file() and not source.is_symlink():
            files.append({"path": relative, "extension": source.suffix, "bytes": source.stat().st_size})
    files = files[:10000]
    (EVIDENCE / "tracked-file-sample.json").write_text(json.dumps(files, ensure_ascii=False, indent=2))
    token, host_token = secrets.token_hex(32), secrets.token_hex(32)
    result = {"startedAt": datetime.now(UTC).isoformat(), "gitHead": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
              "platform": platform.platform(), "python": platform.python_version(), "realSampleCount": len(files),
              "source": "git ls-files + actual filesystem stat; no duplicated rows", "timing": "TCP HTTP request through response body download; JSON decode excluded; nearest-rank percentiles; persistent client", "stages": []}
    process = None
    drain = None
    with tempfile.TemporaryDirectory(prefix="autoflow-real-data-perf-") as directory:
        workspace = Path(directory)
        result["temporaryWorkspace"] = str(workspace)
        with (EVIDENCE / "sidecar.log").open("w") as log:
            try:
                env = {**os.environ, "PYTHONPATH": str(ROOT / "apps/backend/src"), "AUTOFLOW_INSTANCE_TOKEN": token, "AUTOFLOW_HOST_TOKEN": host_token}
                process = subprocess.Popen([sys.executable, "-m", "autoflow", "--port", "0", "--instance-id", str(uuid4()), "--data-dir", str(workspace), "--parent-pid", str(os.getpid())], cwd=ROOT, env=env, stdout=subprocess.PIPE, stderr=log, text=True)
                line = process.stdout.readline()
                assert line.startswith("AUTOFLOW_READY "), line
                def drain_stdout():
                    for output in process.stdout:
                        log.write(output)
                drain = threading.Thread(target=drain_stdout, daemon=True)
                drain.start()
                url = "http://127.0.0.1:" + str(json.loads(line.split(" ", 1)[1])["port"])
                with httpx.Client(base_url=url, headers={"x-autoflow-token": token}, timeout=120) as client:
                    def api(method, path, body=None, params=None):
                        headers = {"Idempotency-Key": str(uuid4())} if method != "GET" else {}
                        began = time.perf_counter()
                        response = client.request(method, path, json=body, params=params, headers=headers)
                        elapsed = (time.perf_counter() - began) * 1000
                        assert response.status_code in {200, 201, 202}, (method, path, response.status_code, response.text[:600])
                        return response.json(), elapsed
                    for attempt in range(100):
                        try:
                            if client.get("/health").status_code == 200:
                                break
                        except httpx.TransportError:
                            pass
                        time.sleep(.1)
                    project, _ = api("POST", "/api/v1/projects", {"name": "真实仓库文件查询性能", "description": result["gitHead"]})
                    prefix = "/api/v1/projects/" + project["projectId"]
                    table, _ = api("POST", prefix + "/tables", {"name": "git实际跟踪文件", "description": "实际路径、扩展名及字节大小", "sourceKind": "local"})
                    base = prefix + "/tables/" + table["tableId"]
                    revision = table["tableRevision"]
                    fields = {}
                    for key, kind in [("path", "string"), ("extension", "string"), ("bytes", "number")]:
                        response, _ = api("POST", base + "/fields", {"definition": {"key": key, "name": key, "type": kind, "required": key != "extension", "validation": {}}, "expectedTableRevision": revision, "existingRecordDefault": files[0][key], "sourceColumnPolicy": "localOnly"})
                        fields[key], revision = response["field"]["ref"]["fieldId"], response["tableRevision"]
                    last = 0
                    for count in sorted({min(1000, len(files)), len(files)}):
                        write_times = []
                        for offset in range(last, count, 100):
                            batch = files[offset:min(offset + 100, count)]
                            response, elapsed = api("POST", base + "/records/batch", {"datasetGeneration": table["datasetGeneration"], "expectedTableRevision": revision,
                                "rows": [{"clientRowId": str(uuid4()), "values": [{"fieldId": fields[key], "value": value} for key, value in row.items()]} for row in batch]})
                            assert len(response["records"]) == len(batch)
                            write_times.append(elapsed)
                        source_rows = files[:count]
                        expected = {row["path"]: row for row in source_rows}
                        python_rows = [row for row in source_rows if row["extension"] == ".py"]
                        reverse_fields = {value: key for key, value in fields.items()}
                        def values(page):
                            return [{reverse_fields[cell["fieldId"]]: cell["value"] for cell in row["values"]} for row in page["items"]]
                        def validate(page, selection, query):
                            assert page["total"] == len(selection), (page["total"], len(selection))
                            found = values(page)
                            assert all(expected[row["path"]] == row for row in found)
                            selected_paths = {row["path"] for row in selection}
                            assert all(row["path"] in selected_paths for row in found)
                            assert len({row["path"] for row in found}) == len(found)
                            if query.get("orderBy") == sort_size:
                                wanted = sorted([row["bytes"] for row in selection], reverse=True)
                                start = (query.get("page", 1) - 1) * query["pageSize"]
                                assert [row["bytes"] for row in found] == wanted[start:start + query["pageSize"]]
                            assert len(found) == max(0, min(query["pageSize"], len(selection) - (query.get("page", 1) - 1) * query["pageSize"]))
                        all_params = {"datasetGeneration": table["datasetGeneration"], "pageSize": 200}
                        sort_size = encoded([{"fieldId": fields["bytes"], "direction": "desc"}])
                        python_filter = encoded({"type": "compare", "fieldId": fields["extension"], "operator": "eq", "value": ".py"})
                        scenarios = [
                            ("default_first_page", {}, source_rows),
                            ("bytes_desc_first_page", {"orderBy": sort_size}, source_rows),
                            ("python_filter_first_page", {"filter": python_filter}, python_rows),
                            ("python_filter_bytes_desc", {"filter": python_filter, "orderBy": sort_size}, python_rows),
                            ("default_last_page", {"page": math.ceil(count / 200)}, source_rows),
                        ]
                        stage = {"rows": count, "addedRows": count - last, "writeBatches": summary(write_times), "writeElapsedMs": round(sum(write_times), 3), "reads": {}, "rawTimingsMs": {}}
                        print(json.dumps({"rowsWritten": count, "writeElapsedMs": stage["writeElapsedMs"]}), flush=True)
                        for name, extra, selection in scenarios:
                            query = {**all_params, **extra}
                            warm, cold = api("GET", base + "/records", params=query)
                            validate(warm, selection, query)
                            timings = []
                            for _ in range(10):
                                response, elapsed = api("GET", base + "/records", params=query)
                                validate(response, selection, query)
                                timings.append(elapsed)
                            stage["reads"][name] = {**summary(timings), "firstObservedMs": round(cold, 3), "matchedRows": len(selection), "correct": True}
                            stage["rawTimingsMs"][name] = timings
                            print(json.dumps({"rows": count, "scenario": name, **stage["reads"][name]}), flush=True)
                        seen = {}
                        for page_number in range(1, math.ceil(count / 200) + 1):
                            page, _ = api("GET", base + "/records", params={**all_params, "page": page_number})
                            for row in values(page):
                                assert row["path"] not in seen
                                seen[row["path"]] = row
                        assert seen == expected
                        stage["fullPagination"] = {"pages": math.ceil(count / 200), "uniqueRows": len(seen), "exactSourceMatch": True}
                        result["stages"].append(stage)
                        (EVIDENCE / "results.json").write_text(json.dumps(result, ensure_ascii=False, indent=2))
                        last = count
                    result["allReadAssertionsPassed"] = True
                    client.post("/internal/lifecycle/shutdown", headers={"x-autoflow-host-token": host_token}, timeout=15)
                    process.wait(timeout=20)
            except Exception as error:
                result["error"] = f"{type(error).__name__}: {error}"
                raise
            finally:
                if process is not None and process.poll() is None:
                    process.terminate()
                    try:
                        process.wait(timeout=10)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait(timeout=5)
                result["sidecarStopped"] = process is not None and process.poll() is not None
                if drain is not None:
                    drain.join(timeout=3)
                result["finishedAt"] = datetime.now(UTC).isoformat()
                (EVIDENCE / "results.json").write_text(json.dumps(result, ensure_ascii=False, indent=2))
    result["temporaryWorkspaceRemoved"] = not workspace.exists()
    (EVIDENCE / "results.json").write_text(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
