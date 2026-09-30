"""Shared numeric reports with mandatory comparison metadata (M0 R0-04)."""

from __future__ import annotations

import json
import math
import os
import platform
import sqlite3
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal, get_args
from uuid import uuid4

Unit = Literal["ms", "count", "per_node", "ratio", "rows_per_min", "tasks_per_min"]
RESULTS_DIR = Path(__file__).with_name("results")
REPO_ROOT = Path(__file__).resolve().parents[4]


def _commit() -> str:
    try:
        return (
            subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=REPO_ROOT,
                check=True,
                capture_output=True,
                text=True,
                timeout=5,
            ).stdout.strip()
            or "unknown"
        )
    except (OSError, subprocess.SubprocessError):
        return "unknown"


def _source_dirty() -> bool | None:
    try:
        return bool(
            subprocess.run(
                ["git", "status", "--porcelain"],
                cwd=REPO_ROOT,
                check=True,
                capture_output=True,
                text=True,
                timeout=5,
            ).stdout.strip()
        )
    except (OSError, subprocess.SubprocessError):
        return None


def build_report(metrics: dict[str, tuple[float | None, Unit]]) -> dict:
    values = {}
    for name, (value, unit) in sorted(metrics.items()):
        if unit not in get_args(Unit):
            raise ValueError(f"Invalid unit: {unit}")
        if value is None:
            if name != "failure_reason_ratio" or unit != "ratio":
                raise ValueError("Only an absent failure denominator permits null")
        elif isinstance(value, bool) or not math.isfinite(value):
            raise ValueError(f"Invalid metric: {name}")
        values[name] = {
            "value": None if value is None else round(float(value), 3),
            "unit": unit,
        }
    return {
        "schemaVersion": 1,
        "commit": _commit(),
        "platform": f"{platform.system().lower()}-{platform.machine().lower()}",
        "metrics": values,
    }


def build_manifest(
    scenario_version: str,
    dataset: dict,
    *,
    execution_profile: str = "offline-v1",
    browser_kernel: str = "not-applicable",
    concurrency: int = 1,
    repetitions: int = 1,
    fault_seed: str = "none",
) -> dict:
    try:
        memory = os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES")
        if memory <= 0:
            memory = "unknown"
    except (AttributeError, OSError, ValueError):
        memory = "unknown"
    return {
        "scenarioVersion": scenario_version,
        "executionProfile": execution_profile,
        "dataset": dataset,
        "faultSeed": fault_seed,
        "hardware": {
            "os": platform.platform(),
            "arch": platform.machine(),
            "logicalCpu": os.cpu_count() or "unknown",
            "totalMemoryBytes": memory,
        },
        "pythonVersion": platform.python_version(),
        "sqliteVersion": sqlite3.sqlite_version,
        "browserKernel": browser_kernel,
        "concurrency": concurrency,
        "repetitions": repetitions,
    }


def write_report(
    name: str,
    metrics: dict[str, tuple[float | None, Unit]],
    directory: Path = RESULTS_DIR,
    *,
    manifest: dict,
) -> Path:
    required = {
        "scenarioVersion",
        "executionProfile",
        "dataset",
        "faultSeed",
        "hardware",
        "pythonVersion",
        "sqliteVersion",
        "browserKernel",
        "concurrency",
        "repetitions",
    }
    if not required <= manifest.keys():
        raise ValueError(f"Incomplete manifest: {sorted(required - manifest.keys())}")
    for key in ("concurrency", "repetitions"):
        if type(manifest[key]) is not int or manifest[key] < 1:
            raise ValueError(f"Invalid {key}")
    if not isinstance(manifest["dataset"], dict) or not manifest["dataset"]:
        raise ValueError("Dataset dimensions are required")
    hardware = manifest["hardware"]
    if (
        not isinstance(hardware, dict)
        or not {"os", "arch", "logicalCpu", "totalMemoryBytes"} <= hardware.keys()
    ):
        raise ValueError("Incomplete hardware metadata")
    for key in (
        "scenarioVersion",
        "executionProfile",
        "faultSeed",
        "pythonVersion",
        "sqliteVersion",
        "browserKernel",
    ):
        if not isinstance(manifest[key], str) or not manifest[key]:
            raise ValueError(f"Missing {key}")
    if Path(name).name != name or not name:
        raise ValueError("Report name must be a filename")
    raw = build_report(metrics)
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
    path = directory / f"{name}-{stamp}-{uuid4().hex}.json"
    metadata = {
        **manifest,
        "commit": raw["commit"],
        "reports": [path.name],
        "sourceDirty": _source_dirty(),
    }
    metadata["comparable"] = (
        raw["commit"] != "unknown"
        and metadata["sourceDirty"] is False
        and all(value not in ("unknown", None, "") for value in hardware.values())
        and all(
            manifest[key] != "unknown"
            for key in ("pythonVersion", "sqliteVersion", "browserKernel")
        )
    )
    directory.mkdir(parents=True, exist_ok=True)
    # A manifest is written last: interrupted pairs are not valid comparison inputs.
    path.write_text(
        json.dumps(raw, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    path.with_suffix(".manifest.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    summary = " ".join(
        f"{key}={item['value'] if item['value'] is not None else 'n/a'}{item['unit']}"
        for key, item in raw["metrics"].items()
    )
    print(f"[{name}] {summary} -> {path}")
    return path
