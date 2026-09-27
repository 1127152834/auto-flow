"""Reuse the audited production-worker harness with a new evidence directory."""
from __future__ import annotations

import asyncio
import importlib.util
import shlex
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
HARNESS = ROOT / "docs/qa/2026-09-28-system-audit/nodes/run_real_nodes.py"
spec = importlib.util.spec_from_file_location("remediation_node_harness", HARNESS)
assert spec and spec.loader
qa = importlib.util.module_from_spec(spec)
spec.loader.exec_module(qa)
qa.OUT = Path(__file__).with_name("nodes-native")
qa.OUT.mkdir(exist_ok=False)


async def main():
    with tempfile.TemporaryDirectory(prefix="autoflow-node-remediation-") as temporary:
        directory = Path(temporary)
        source = directory / "真实 package file.json"
        source.write_bytes((ROOT / "package.json").read_bytes())
        script = directory / "reader script.py"
        script.write_text('import json,sys\nfrom pathlib import Path\nprint(json.loads(Path(sys.argv[1]).read_text())["name"])\n')
        await qa.worker(
            "Python 文件模式读取带空格的真实仓库文件", [("python_script", {
                "scriptMode": "file", "scriptPath": str(script),
                "scriptArgs": shlex.quote(str(source)), "stdoutVariable": "out",
            })], directory,
            verify=lambda events, *_: qa.equals(events[0]["data"]["stdout"], qa.PKG["name"]),
        )
        header = (ROOT / "docs/qa/2026-09-28-system-audit/nodes/source-files.csv").read_text().splitlines()[0] + "\n"
        await qa.worker(
            "真实 CSV 导出仅剩表头", [("csv_parse", {
                "csvContent": header, "hasHeader": True, "resultVariable": "out",
            })], directory, verify=lambda events, *_: qa.equals(events[0]["data"], []),
        )
        await qa.worker(
            "未知 SHA 明确失败且不执行后继", [
                ("sha_encrypt", {"inputText": "${text}", "shaType": "sha999", "resultVariable": "out"}),
                ("print_log", {"logMessage": "must-not-run"}),
            ], directory, expected_success=False,
            verify=lambda events, *_: qa.equals(len(events), 1),
        )
        assert all(item["status"] == "pass" for item in qa.RESULTS), qa.RESULTS


asyncio.run(main())
