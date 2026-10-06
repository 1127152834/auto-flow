"""Restore + save of a typical saved browser environment (remediation M3 AC3-06).

The fixture mimics a Chromium profile after a few logins: small login stores, an IndexedDB, and
rebuildable HTTP / code / GPU caches that make up most of its size. ``keepCache`` is the path an
environment takes when it keeps its caches (and the only path before R3-09). Target: < 2 s.

Run: uv run --directory apps/backend python -m tests.benchmarks.bench_environment_roundtrip
"""

from __future__ import annotations

import argparse
import os
import statistics
import tempfile
import time
from pathlib import Path

from autoflow.infrastructure.filesystem.environment_store import EnvironmentStore

from .report import Unit, build_manifest, write_report

# (directory, files, bytes per file)
FIXTURE = (
    ("Default", 1, 64 * 1024),  # Cookies-sized login store
    ("Default/Local Storage/leveldb", 200, 8 * 1024),
    ("Default/IndexedDB/https_example.com_0.indexeddb.leveldb", 60, 32 * 1024),
    ("Default/Service Worker/ScriptCache", 20, 16 * 1024),
    ("Default/Cache/Cache_Data", 1500, 20 * 1024),
    ("Default/Code Cache/js", 300, 30 * 1024),
    ("Default/GPUCache", 40, 50 * 1024),
)


def _fixture(directory: Path) -> None:
    for relative, count, size in FIXTURE:
        folder = directory / relative
        folder.mkdir(parents=True, exist_ok=True)
        for index in range(count):
            (folder / f"f{index:05d}").write_bytes(os.urandom(size))


def _round_trip(store: EnvironmentStore, environment_id: str, generation: int, *, keep_cache: bool) -> float:
    """Restore the generation into a work copy, then save the copy as the next generation."""
    instance_id = f"instance-{generation}"
    started = time.perf_counter()
    store.restore_generation(environment_id, generation, instance_id)
    save_id = f"save-{environment_id}-{generation + 1}"
    store.stage_candidate(save_id, instance_id, keep_browser_cache=keep_cache)
    store.publish(environment_id, generation + 1, save_id)
    elapsed = (time.perf_counter() - started) * 1000
    store.close_instance(instance_id)
    return elapsed


def run(samples: int) -> dict[str, tuple[float | None, Unit]]:
    metrics: dict[str, tuple[float | None, Unit]] = {}
    with tempfile.TemporaryDirectory() as temporary:
        for label, keep_cache in (("keepCache", True), ("slim", False)):
            store = EnvironmentStore(Path(temporary) / label)
            environment_id = f"bench-{label}"
            source = store.instance_dir("source")
            _fixture(source)
            store.stage_candidate("seed", "source", keep_browser_cache=True)
            store.publish(environment_id, 1, "seed")
            # The first save produces the slim generation every later round trip starts from.
            durations = [_round_trip(store, environment_id, generation, keep_cache=keep_cache) for generation in range(1, samples + 2)][1:]
            metrics[f"roundtrip_ms_{label}"] = (statistics.median(durations), "ms")
            metrics[f"generation_mb_{label}"] = (store.generation_bytes(environment_id, samples + 1) / 1024 / 1024, "count")
    return metrics


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--samples", type=int, default=5)
    parser.add_argument("--budget-ms", type=float, default=None, help="fail when the slim round trip is slower")
    arguments = parser.parse_args()
    metrics = run(arguments.samples)
    for name, (value, unit) in metrics.items():
        print(f"{name}: {value:.1f} {unit}")
    write_report(
        "environment-roundtrip", metrics,
        manifest=build_manifest("environment-roundtrip-v1", {"fixture": "chromium-profile-45mb"}, repetitions=arguments.samples),
    )
    slim = metrics["roundtrip_ms_slim"][0]
    if arguments.budget_ms is not None and slim is not None and slim > arguments.budget_ms:
        message = f"environment round trip {slim:.0f} ms exceeds {arguments.budget_ms:.0f} ms"
        if os.environ.get("GITHUB_ACTIONS"):
            print(f"::error title=environment round trip::{message}")  # an annotation, readable without the raw log
        raise SystemExit(message)


if __name__ == "__main__":
    main()
