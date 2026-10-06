"""Environment work for k consecutive tasks of one identity (remediation M4 S8-3, AGENTS rule 4).

perTask restores a work copy and saves it as the next version for every task (the path before S8);
perIdentity restores once, lets the following k-1 tasks re-attach the held copy (a database update,
not measured here), and saves once at release. Browser start-up is the same in both and not measured.
Same fixture as bench_environment_roundtrip.

Run: uv run --directory apps/backend python -m tests.benchmarks.bench_identity_session
"""

from __future__ import annotations

import argparse
import statistics
import tempfile
import time
from pathlib import Path

from autoflow.infrastructure.filesystem.environment_store import EnvironmentStore

from .bench_environment_roundtrip import _fixture
from .report import Unit, build_manifest, write_report


def _seeded_store(directory: Path, label: str) -> tuple[EnvironmentStore, str]:
    store = EnvironmentStore(directory / label)
    environment_id = f"bench-{label}"
    _fixture(store.instance_dir("source"))
    store.stage_candidate("seed", "source", keep_browser_cache=True)
    store.publish(environment_id, 1, "seed")
    return store, environment_id


def _per_task(store: EnvironmentStore, environment_id: str, tasks: int) -> float:
    started = time.perf_counter()
    for generation in range(1, tasks + 1):
        instance_id = f"task-{generation}"
        store.restore_generation(environment_id, generation, instance_id)
        save_id = f"save-{generation + 1}"
        store.stage_candidate(save_id, instance_id)
        store.publish(environment_id, generation + 1, save_id)
        store.close_instance(instance_id)
    return (time.perf_counter() - started) * 1000


def _per_identity(store: EnvironmentStore, environment_id: str, tasks: int) -> float:
    started = time.perf_counter()
    store.restore_generation(environment_id, 1, "held")
    # tasks 2..k re-attach the held copy: no file work
    store.stage_candidate("release", "held")
    store.publish(environment_id, 2, "release")
    store.close_instance("held")
    return (time.perf_counter() - started) * 1000


def run(samples: int, task_counts: tuple[int, ...] = (1, 3, 10)) -> dict[str, tuple[float | None, Unit]]:
    metrics: dict[str, tuple[float | None, Unit]] = {}
    for tasks in task_counts:
        for label, mode in (("perTask", _per_task), ("perIdentity", _per_identity)):
            durations = []
            for sample in range(samples):
                with tempfile.TemporaryDirectory() as temporary:
                    store, environment_id = _seeded_store(Path(temporary), f"{label}{tasks}-{sample}")
                    durations.append(mode(store, environment_id, tasks))
            metrics[f"environment_ms_{label}_k{tasks}"] = (statistics.median(durations), "ms")
    return metrics


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--samples", type=int, default=3)
    arguments = parser.parse_args()
    metrics = run(arguments.samples)
    for name, (value, unit) in metrics.items():
        print(f"{name}: {value:.1f} {unit}")
    write_report(
        "identity-session", metrics,
        manifest=build_manifest("identity-session-v1", {"fixture": "chromium-profile-45mb", "tasks": [1, 3, 10]}, repetitions=arguments.samples),
    )


if __name__ == "__main__":
    main()
