"""Read-only public-advisory audit; writes evidence only alongside this script."""
from __future__ import annotations

import concurrent.futures
import hashlib
import importlib.metadata
import json
from pathlib import Path
import platform
import subprocess
import time
import tomllib
from datetime import datetime, timezone

from packaging.markers import default_environment
from packaging.requirements import Requirement
from packaging.utils import canonicalize_name

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[3]
BACKEND = ROOT / "apps/backend"
SITE = BACKEND / ".venv/lib/python3.11/site-packages"


def save(name, value):
    (OUT / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def snapshot():
    return {
        "files": {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
                  for p in [BACKEND / "uv.lock", BACKEND / "pyproject.toml"]},
        "installed": sorted(
            [{"name": canonicalize_name(d.metadata["Name"]), "version": d.version}
             for d in importlib.metadata.distributions(path=[str(SITE)])],
            key=lambda d: (d["name"], d["version"])),
    }


before = snapshot()
save("backend-before.json", before)
project = tomllib.loads((BACKEND / "pyproject.toml").read_text())
direct = {canonicalize_name(Requirement(s).name) for s in project["project"]["dependencies"]}
export_path = OUT / "backend-production-requirements.txt"
export_command = ["uv", "export", "--project", str(BACKEND), "--frozen", "--no-dev",
                  "--no-default-groups", "--no-emit-project", "--no-hashes", "--no-annotate",
                  "--no-header", "--output-file", str(export_path)]
export = subprocess.run(export_command, capture_output=True, text=True, timeout=60)
(OUT / "backend-export.log").write_text(export.stderr)
if export.returncode:
    save("backend-export-failure.json", {"command": export_command, "exit_code": export.returncode})
    raise SystemExit(export.returncode)

environment = default_environment()
environment["extra"] = ""
requirements = []
for line in export_path.read_text().splitlines():
    if not line.strip() or line.lstrip().startswith("#"):
        continue
    r = Requirement(line)
    pins = list(r.specifier)
    assert len(pins) == 1 and pins[0].operator == "==", line
    requirements.append({"name": canonicalize_name(r.name), "version": pins[0].version,
                         "requirement": line, "marker": str(r.marker) if r.marker else None,
                         "active_on_host": r.marker.evaluate(environment) if r.marker else True,
                         "direct": canonicalize_name(r.name) in direct})
all_pins = sorted({(r["name"], r["version"]) for r in requirements})
union_path = OUT / "backend-production-union-pins.txt"
union_path.write_text("".join(f"{n}=={v}\n" for n, v in all_pins))
save("backend-production-scope.json", {
    "python_platform": platform.platform(), "marker_environment": environment,
    "production_direct_names": sorted(direct), "requirement_rows": requirements,
    "unique_pins": len(all_pins), "active_on_host_pins": len({(r["name"], r["version"])
                                                                  for r in requirements if r["active_on_host"]}),
    "export_command": export_command,
    "note": "Audit the frozen production lock export union across platform markers. This does not install or resolve dependencies. Conditional non-host packages are classified separately.",
})

common = ["uvx", "--index-url", "https://pypi.org/simple", "pip-audit==2.10.1",
          "--format", "json", "--progress-spinner", "off", "--timeout", "10",
          "--vulnerability-service", "pypi", "--aliases", "on", "--desc", "on"]


def audit(label, arguments):
    command = common + arguments + ["--output", str(OUT / f"backend-{label}.json")]
    start = time.monotonic()
    started = datetime.now(timezone.utc).isoformat()
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=240)
        (OUT / f"backend-{label}.log").write_text(result.stdout + result.stderr)
        status = {"exit_code": result.returncode, "timed_out": False}
    except subprocess.TimeoutExpired as error:
        def decoded(value):
            return value.decode(errors="replace") if isinstance(value, bytes) else (value or "")
        (OUT / f"backend-{label}.log").write_text(decoded(error.stdout) + decoded(error.stderr))
        status = {"exit_code": None, "timed_out": True}
    status.update({"command": command, "started_utc": started,
                   "elapsed_seconds": round(time.monotonic() - start, 3)})
    save(f"backend-{label}-execution.json", status)
    return {"label": label, **status}


with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
    scans = [pool.submit(audit, "installed", ["--path", str(SITE), "--skip-editable"]),
             pool.submit(audit, "production", ["--requirement", str(union_path), "--no-deps", "--disable-pip"])]
    executions = [scan.result() for scan in scans]
after = snapshot()
save("backend-after.json", after)
save("backend-execution-summary.json", {"executions": executions,
                                        "repo_dependency_files_unchanged": before["files"] == after["files"],
                                        "installed_packages_unchanged": before["installed"] == after["installed"]})
print(json.dumps({"executions": [{k: v for k, v in e.items() if k != "command"} for e in executions],
                  "installed_count": len(before["installed"]), "production_union_pins": len(all_pins),
                  "dependency_files_unchanged": before["files"] == after["files"],
                  "installed_unchanged": before["installed"] == after["installed"]}, indent=2))
