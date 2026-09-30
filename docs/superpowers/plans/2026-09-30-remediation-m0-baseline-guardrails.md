# M0 基准与守门 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让批量执行的关键指标可测量（离线基准、主循环延迟、黄金场景），并用守门检查阻止问题继续增加；不改变任何用户可见行为。

**Architecture:** 离线基准与黄金场景都放在 `apps/backend/tests/` 下，复用现有测试夹具，输出统一 JSON；`LoopLagMonitor` 是纯 asyncio 组件，由 `create_app` 创建并挂到 `app.state.loop_lag`；守门检查是一个无依赖的 Node 脚本，基线文件入库。

**Tech Stack:** Python 3.11、pytest + pytest-asyncio、SQLAlchemy 2、FastAPI、httpx；Node 22 `node:test`；GitHub Actions。

**Spec:** [docs/superpowers/specs/2026-09-30-remediation-m0-baseline-guardrails.md](../specs/2026-09-30-remediation-m0-baseline-guardrails.md)

## Global Constraints

- 本里程碑不修改任何生产行为；`apps/backend/src` 中只新增 `infrastructure/observability/` 并在 `bootstrap/app.py` 中接入监测器。
- 基准结果写入 `apps/backend/tests/benchmarks/results/`，该目录进 `.gitignore`，不入库；QA 截图不再新增到 `docs/`。
- JSON 结构固定为 `{"schemaVersion":1,"commit":"<sha>","platform":"<os-arch>","metrics":{"<name>":{"value":<number|null>,"unit":"ms|count|per_node|ratio|rows_per_min|tasks_per_min"}}}`。
- 黄金场景在未设置 `AUTOFLOW_TEST_CLOAKBROWSER` 时必须 skip，不能 fail。
- pytest 标记 `benchmark`、`golden` 默认被排除（`addopts = -m "not benchmark and not golden"`）。
- 分支：`codex/remediation-m0`；每个任务一次清晰提交；不写不存在的协作者或其他工具会话标记。
- 所有命令从仓库根目录执行。后端命令形如 `uv run --directory apps/backend pytest ...`。

## Review Focus

1. **从别的目录或没有 git 的环境运行基准**：`git rev-parse` 失败时 `commit` 必须为 `"unknown"` 而不是抛异常（Task 1 覆盖）。
2. **Windows 路径分隔符**：守门脚本判断"测试文件"时要按平台分隔符拆路径，CI 在 windows-2022 上运行（Task 7 的 `isTest` 使用 `path.sep`）。
3. **重复领取与超过 100 行**：每行使用公开 debugSelection 固定输入的单任务批次；完整身份集合无漏行/重复，等待终态，绝不按任务创建数停批（Task 6）。
4. **监测器被重复启动或在未启动时停止**：`start()` 幂等、`stop()` 可重复调用（Task 4 覆盖）。
5. **基准结果目录不存在**：`write_report` 自动创建目录（Task 1 覆盖）。

---

### Task 1: 基准骨架与领取基准（R0-01、R0-04）

**Files:**
- Modify: `apps/backend/pyproject.toml`（`[tool.pytest.ini_options]`）
- Modify: `.gitignore`
- Create: `apps/backend/tests/benchmarks/__init__.py`（空文件）
- Create: `apps/backend/tests/benchmarks/report.py`
- Create: `apps/backend/tests/benchmarks/bench_claims.py`
- Test: `apps/backend/tests/benchmarks/test_offline_benchmarks.py`

**Interfaces:**
- Produces: `report.build_report(metrics: dict[str, tuple[float | None, Unit]]) -> dict`、`report.write_report(name: str, metrics, directory: Path = RESULTS_DIR, *, manifest: dict) -> Path`、`report.Unit = Literal["ms","count","per_node","ratio","rows_per_min","tasks_per_min"]`、`report.RESULTS_DIR`；`bench_claims.run(rows: int) -> dict[str, tuple[float | None, Unit]]`（键：`rows`、`claim_ms_key_order`、`claim_ms_field_order`）；`bench_claims._seed(directory: Path, rows: int)`（M1 Task 10 的主循环延迟基准会复用）。

- [x] **Step 1: 注册 pytest 标记并忽略结果目录**

`apps/backend/pyproject.toml`：

```toml
[tool.pytest.ini_options]
pythonpath = ["src"]
addopts = "-m \"not benchmark and not golden\""
markers = [
  "benchmark: offline remediation benchmarks (run with -m benchmark)",
  "golden: real-browser golden scenarios (run with -m golden)",
]
```

`.gitignore` 末尾追加：

```gitignore
# Remediation benchmark output (spec M0 R0-04)
apps/backend/tests/benchmarks/results/
```

- [x] **Step 2: 写失败的测试**

`apps/backend/tests/benchmarks/test_offline_benchmarks.py`：

```python
"""Small-scale smoke of the offline benchmarks; CI runs it with -m benchmark."""

import json

import pytest

from . import bench_claims
from . import report as report_module
from .report import build_manifest, build_report, write_report

pytestmark = pytest.mark.benchmark


def test_claim_benchmark_reports_both_orderings(tmp_path):
    metrics = bench_claims.run(200)
    assert metrics["rows"] == (200, "count")
    assert metrics["claim_ms_key_order"][1] == "ms"
    assert metrics["claim_ms_field_order"][0] > 0
    path = write_report("claims-200", metrics, tmp_path / "nested" / "results", manifest=build_manifest("claims-v1", {"rows": 200}))
    report = json.loads(path.read_text(encoding="utf-8"))
    assert set(report) == {"schemaVersion", "commit", "platform", "metrics"}
    assert report["schemaVersion"] == 1
    assert report["metrics"]["claim_ms_key_order"]["unit"] == "ms"


def test_report_survives_missing_git(monkeypatch):
    def no_git(*_args, **_kwargs):
        raise FileNotFoundError("git")

    monkeypatch.setattr(report_module.subprocess, "run", no_git)
    assert build_report({"rows": (1, "count")})["commit"] == "unknown"
```

- [x] **Step 3: 运行，确认失败**

Run: `uv run --directory apps/backend pytest -q -m benchmark tests/benchmarks/test_offline_benchmarks.py`
Expected: FAIL，`ImportError`（`bench_claims` / `report` 不存在）。

- [x] **Step 4: 实现 report.py**

实现 `build_report(metrics)` 和 `write_report(name, metrics, directory=RESULTS_DIR, *, manifest)`；保留schemaVersion=1的数值报告结构，manifest为必填参数，同目录写独立JSON。`build_report` 对数值保留三位小数、None写null，终端摘要显示n/a，不能float(None)。git不可用时commit=unknown，不伪造版本。

同时提供 `build_manifest(scenario_version, dataset, *, execution_profile="offline-v1", browser_kernel="not-applicable", concurrency=1, repetitions=1, fault_seed="none")`：采集实际OS/arch、逻辑CPU、内存（复用现有系统信息查询，不可得时unknown）、Python/SQLite版本；记录全部入参。`write_report`补本报告文件名及与数值报告相同的commit，使用微秒时间戳/唯一后缀避免并发覆盖。硬件或版本unknown的报告可保存，但标记不可作提升比例比较；“not-applicable”只用于离线确实未用的浏览器内核等维度。

增加测试：缺manifest/缺字段拒绝；数值文件与manifest相互对应；无失败覆盖率为null；新增单位合法；连续/并发写不覆盖；离线三个入口和黄金入口都生成manifest。单次报告repetitions=1，不能填计划运行的次数冒充实际重复数；比较器另校验至少5份相同维度样本。

Task1–3及M1新增基准入口都从report导入build_manifest并传参；下面的入口调用同步更新。黄金场景额外传入真实browser_kernel、受控execution_profile、并发和故障种子。CI须上传manifest与数值报告；缺manifest的历史结果不参与倍数计算。


- [x] **Step 5: 实现 bench_claims.py**

```python
"""Claim latency benchmark (remediation M0, R0-01).

Run: uv run --directory apps/backend python -m tests.benchmarks.bench_claims --rows 10000
"""

from __future__ import annotations

import argparse
import copy
import tempfile
import time
import uuid
from pathlib import Path

from sqlalchemy import select

from autoflow.application.projects.service import ProjectService
from autoflow.infrastructure.database.project_claims import SqlAlchemyProjectInputGroups
from autoflow.infrastructure.database.project_data_models import DataRecordRow
from autoflow.infrastructure.database.projects import SqlAlchemyProjects
from autoflow.infrastructure.database.session import create_session_factory, migrate_database
from tests.integration.test_project_input_groups import _add_record, _empty_table, _input, uid

from .report import Unit, build_manifest, write_report


def _seed(directory: Path, rows: int):
    """One real record through the services, then cloned rows for speed."""
    path = directory / "bench.sqlite3"
    migrate_database(path)
    factory = create_session_factory(path)
    project_id = ProjectService(SqlAlchemyProjects(factory)).create(uid(), {"name": "bench"})[0].project_id
    table, field = _empty_table(factory, project_id, "账号")
    _add_record(factory, project_id, table, field, "acct-00000")
    field_id = field["ref"]["fieldId"]
    with factory() as session:
        template = session.scalars(select(DataRecordRow)).one()
        columns = {column.name: getattr(template, column.key) for column in DataRecordRow.__table__.columns}
        for index in range(1, rows):
            values = dict(template.values_json)
            values[field_id] = f"acct-{index:05d}"
            session.execute(
                DataRecordRow.__table__.insert().values(
                    **{**columns, "key_value": str(uuid.uuid4()), "values_json": values}
                )
            )
        session.commit()
    return factory, project_id, table, field


def plans(project_id: str, table: dict, field: dict) -> dict[str, dict]:
    key_order = {"inputs": [_input(project_id, table, field, "账号")]}
    field_order = copy.deepcopy(key_order)
    field_order["inputs"][0]["orderBy"] = [{"fieldId": field["ref"]["fieldId"], "direction": "desc"}]
    return {"claim_ms_key_order": key_order, "claim_ms_field_order": field_order}


def run(rows: int) -> dict[str, tuple[float | None, Unit]]:
    with tempfile.TemporaryDirectory() as raw:
        factory, project_id, table, field = _seed(Path(raw), rows)
        metrics: dict[str, tuple[float | None, Unit]] = {"rows": (rows, "count")}
        for name, plan in plans(project_id, table, field).items():
            started = time.perf_counter()
            with factory() as session:
                selection = SqlAlchemyProjectInputGroups(session).select_required(project_id, plan)
            metrics[name] = ((time.perf_counter() - started) * 1000, "ms")
            if selection.status != "ready":
                raise RuntimeError(f"{name}: unexpected selection status {selection.status}")
        factory.dispose()
    return metrics


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--rows", type=int, default=2000)
    arguments = parser.parse_args()
    write_report(f"claims-{arguments.rows}", run(arguments.rows), manifest=build_manifest("claims-v1", {"rows": arguments.rows}))


if __name__ == "__main__":
    main()
```

- [x] **Step 6: 运行测试与脚本**

Run: `uv run --directory apps/backend pytest -q -m benchmark tests/benchmarks/test_offline_benchmarks.py`
Expected: 2 passed。
Run: `uv run --directory apps/backend python -m tests.benchmarks.bench_claims --rows 2000`
Expected: 打印 `[claims-2000] claim_ms_field_order=…ms claim_ms_key_order=…ms rows=2000.0count -> …/results/claims-2000-….json`（原型：500 行约 70 毫秒）。

- [x] **Step 7: 确认默认测试排除基准**

Run: `uv run --directory apps/backend pytest -q tests/benchmarks tests/integration/test_project_input_groups.py`
Expected: 既有输入选择测试通过，基准被排除；仅跑全被排除目录时pytest退出5，不算失败测试或验收通过。

- [x] **Step 8: 提交**

```bash
git add apps/backend/pyproject.toml .gitignore apps/backend/tests/benchmarks/__init__.py apps/backend/tests/benchmarks/report.py apps/backend/tests/benchmarks/bench_claims.py apps/backend/tests/benchmarks/test_offline_benchmarks.py
git commit -m "test(bench): 领取耗时基准与统一结果格式"
```

---

### Task 2: G4 执行开销基准（R0-02）

**Files:**
- Create: `apps/backend/tests/benchmarks/bench_runtime_overhead.py`
- Modify: `apps/backend/tests/benchmarks/test_offline_benchmarks.py`

**Interfaces:**
- Consumes: `report.Unit`、`report.write_report`（Task 1）。
- Produces: `bench_runtime_overhead.run(iterations: int) -> dict[str, tuple[float | None, Unit]]`（键：`nodes_executed`、`framework_ms_per_node`、`events_per_node`）；`bench_runtime_overhead.g4_document(iterations: int) -> dict`。

- [x] **Step 1: 写失败的测试**（追加到 `test_offline_benchmarks.py`，并在文件顶部 import 中加入 `bench_runtime_overhead`）

```python
def test_runtime_overhead_benchmark_records_current_event_volume():
    metrics = bench_runtime_overhead.run(50)
    assert metrics["nodes_executed"] == (250, "count")
    assert metrics["framework_ms_per_node"][1] == "ms"
    assert metrics["events_per_node"][0] >= 4  # AC0-02: records the current volume (≈5.0)
```

- [x] **Step 2: 运行，确认失败**

Run: `uv run --directory apps/backend pytest -q -m benchmark tests/benchmarks/test_offline_benchmarks.py -k runtime_overhead`
Expected: FAIL，`ImportError: cannot import name 'bench_runtime_overhead'`。

- [x] **Step 3: 实现**

```python
"""Runtime framework overhead benchmark, golden scenario G4 (remediation M0, R0-02).

Run: uv run --directory apps/backend python -m tests.benchmarks.bench_runtime_overhead --iterations 1000
"""

from __future__ import annotations

import argparse
import asyncio
import time
from collections import Counter
from typing import Any

from autoflow.providers.browser.project_graph import ProjectGraphExecutor

from .report import Unit, build_manifest, write_report

WIDTH = 5


def _node(identity: str, kind: str, **config: Any) -> dict[str, Any]:
    return {"id": identity, "data": {"moduleType": kind, **config}}


def g4_document(iterations: int) -> dict[str, Any]:
    nodes = [_node("loop", "loop", count=iterations, indexVariable="i")] + [
        _node(f"s{k}", "set_variable", variableName=f"v{k}", variableValue="{i}")
        for k in range(WIDTH)
    ]
    edges = [{"id": "e-loop", "source": "loop", "target": "s0", "sourceHandle": "loop"}] + [
        {"id": f"e{k}", "source": f"s{k}", "target": f"s{k + 1}"} for k in range(WIDTH - 1)
    ]
    return {"nodes": nodes, "edges": edges}


async def _run(iterations: int) -> dict[str, tuple[float | None, Unit]]:
    kinds: Counter[str] = Counter()

    async def emit(kind: str, _node_id: str, _visit: str, _payload: dict[str, Any]) -> None:
        kinds[kind] += 1

    executor = ProjectGraphExecutor(None, {}, emit, lambda: False)
    started = time.perf_counter()
    result = await executor.run({"document": g4_document(iterations)})
    elapsed_ms = (time.perf_counter() - started) * 1000
    if result != {"status": "succeeded", "error": None}:
        raise RuntimeError(f"G4 did not succeed: {result}")
    nodes = iterations * WIDTH
    return {
        "nodes_executed": (nodes, "count"),
        "framework_ms_per_node": (elapsed_ms / nodes, "ms"),
        "events_per_node": (sum(kinds.values()) / nodes, "per_node"),
    }


def run(iterations: int) -> dict[str, tuple[float | None, Unit]]:
    return asyncio.run(_run(iterations))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--iterations", type=int, default=1000)
    arguments = parser.parse_args()
    write_report("runtime-overhead", run(arguments.iterations), manifest=build_manifest("runtime-overhead-v1", {"iterations": arguments.iterations}))


if __name__ == "__main__":
    main()
```

- [x] **Step 4: 运行**

Run: `uv run --directory apps/backend pytest -q -m benchmark tests/benchmarks/test_offline_benchmarks.py`
Expected: 3 passed。
Run: `uv run --directory apps/backend python -m tests.benchmarks.bench_runtime_overhead`
Expected: `events_per_node≈5.0`，`framework_ms_per_node` 约 0.2 毫秒量级。

- [x] **Step 5: 提交**

```bash
git add apps/backend/tests/benchmarks/bench_runtime_overhead.py apps/backend/tests/benchmarks/test_offline_benchmarks.py
git commit -m "test(bench): G4 长循环执行开销与每节点事件数基准"
```

---

### Task 3: 事件提交基准（R0-03）

**Files:**
- Create: `apps/backend/tests/benchmarks/bench_event_commit.py`
- Modify: `apps/backend/tests/benchmarks/test_offline_benchmarks.py`

**Interfaces:**
- Consumes: `tests.fixtures.workflow_runs.create_queued_run(factory) -> (CoreRun, content)`；`SqlAlchemyWorkflowRuntimeRepository(session).append_event(dict)`。
- Produces: `bench_event_commit.run(events: int) -> dict[str, tuple[float | None, Unit]]`（键：`events`、`event_commit_ms_p50`、`event_commit_ms_p99`）。M1 用它验证 WAL 效果。

- [ ] **Step 1: 写失败的测试**（import 中加入 `bench_event_commit`）

```python
def test_event_commit_benchmark_reports_percentiles():
    metrics = bench_event_commit.run(50)
    assert metrics["events"] == (50, "count")
    assert metrics["event_commit_ms_p99"][0] >= metrics["event_commit_ms_p50"][0] > 0
```

- [ ] **Step 2: 运行，确认失败**

Run: `uv run --directory apps/backend pytest -q -m benchmark tests/benchmarks/test_offline_benchmarks.py -k event_commit`
Expected: FAIL，`ImportError`。

- [ ] **Step 3: 实现**

```python
"""Run-event commit latency benchmark (remediation M0, R0-03).

Run: uv run --directory apps/backend python -m tests.benchmarks.bench_event_commit --events 1000
"""

from __future__ import annotations

import argparse
import tempfile
import time
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from autoflow.infrastructure.database.session import create_session_factory, migrate_database
from autoflow.infrastructure.database.workflow_runtime import SqlAlchemyWorkflowRuntimeRepository
from tests.fixtures.workflow_runs import create_queued_run

from .report import Unit, build_manifest, write_report


def _percentile(ordered: list[float], fraction: float) -> float:
    return ordered[min(len(ordered) - 1, round(fraction * (len(ordered) - 1)))]


def run(events: int) -> dict[str, tuple[float | None, Unit]]:
    with tempfile.TemporaryDirectory() as raw:
        path = Path(raw) / "events.sqlite3"
        migrate_database(path)
        factory = create_session_factory(path)
        run_row, _content = create_queued_run(factory)
        samples: list[float] = []
        for index in range(events):
            event = {
                "eventId": str(uuid4()), "runId": run_row.run_id, "executionGeneration": 0,
                "kind": "log", "nodeId": "open", "nodeVisitId": "visit-1", "attempt": 1,
                "occurredAt": datetime.now(UTC).isoformat(),
                "payload": {"level": "info", "message": f"benchmark {index}"},
            }
            started = time.perf_counter()
            with factory.begin() as session:
                SqlAlchemyWorkflowRuntimeRepository(session).append_event(event)
            samples.append((time.perf_counter() - started) * 1000)
        factory.dispose()
    samples.sort()
    return {
        "events": (events, "count"),
        "event_commit_ms_p50": (_percentile(samples, 0.50), "ms"),
        "event_commit_ms_p99": (_percentile(samples, 0.99), "ms"),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--events", type=int, default=1000)
    arguments = parser.parse_args()
    write_report("event-commit", run(arguments.events), manifest=build_manifest("event-commit-v1", {"events": arguments.events}))


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: 运行**

Run: `uv run --directory apps/backend pytest -q -m benchmark tests/benchmarks/test_offline_benchmarks.py`
Expected: 4 passed。
Run: `uv run --directory apps/backend python -m tests.benchmarks.bench_event_commit`
Expected: p50 数毫秒量级（原型 Linux 4.1 毫秒）。

- [ ] **Step 5: 提交**

```bash
git add apps/backend/tests/benchmarks/bench_event_commit.py apps/backend/tests/benchmarks/test_offline_benchmarks.py
git commit -m "test(bench): 运行事件同步提交延迟基准"
```

---

### Task 4: LoopLagMonitor 与 sidecar 接入（R0-05）

**Files:**
- Create: `apps/backend/src/autoflow/infrastructure/observability/__init__.py`
- Create: `apps/backend/src/autoflow/infrastructure/observability/loop_lag.py`
- Modify: `apps/backend/src/autoflow/bootstrap/app.py`（`app.state.config = settings` 之后；`shutdown()` 最外层 `finally`）
- Test: `apps/backend/tests/unit/test_loop_lag.py`
- Test: `apps/backend/tests/contract/test_loop_lag_wiring.py`

**Interfaces:**
- Produces: `LoopLagMonitor(*, interval: float = 0.05, warn_ms: float = 100.0, capacity: int = 6000)`，方法 `async start()`（幂等）、`async stop()`（可重复）、`snapshot() -> LoopLagSnapshot`、`reset()`、属性 `running: bool`；`LoopLagSnapshot(p50_ms, p99_ms, max_ms, samples)`；日志记录器名 `autoflow.loop_lag`；`app.state.loop_lag`。

- [ ] **Step 1: 写失败的单元测试**

```python
import asyncio
import logging
import time

import pytest

from autoflow.infrastructure.observability import LoopLagMonitor


@pytest.mark.asyncio
async def test_blocking_the_loop_is_measured_and_logged(caplog):
    monitor = LoopLagMonitor(interval=0.01, warn_ms=100)
    await monitor.start()
    try:
        await asyncio.sleep(0.05)
        with caplog.at_level(logging.WARNING, logger="autoflow.loop_lag"):
            time.sleep(0.3)
            await asyncio.sleep(0.05)
        snapshot = monitor.snapshot()
    finally:
        await monitor.stop()
    assert snapshot.max_ms >= 250
    assert snapshot.samples >= 3
    assert any("event loop lag" in record.getMessage() for record in caplog.records)


@pytest.mark.asyncio
async def test_start_is_idempotent_and_stop_can_repeat():
    monitor = LoopLagMonitor(interval=0.01)
    await monitor.stop()  # never started
    await monitor.start()
    await monitor.start()
    assert monitor.running
    await asyncio.sleep(0.2)
    await monitor.stop()
    await monitor.stop()
    assert not monitor.running
    snapshot = monitor.snapshot()
    assert snapshot.samples >= 5
    assert snapshot.p50_ms < 50
    monitor.reset()
    assert monitor.snapshot().samples == 0
```

- [ ] **Step 2: 运行，确认失败**

Run: `uv run --directory apps/backend pytest -q tests/unit/test_loop_lag.py`
Expected: FAIL，`ModuleNotFoundError: autoflow.infrastructure.observability`。

- [ ] **Step 3: 实现**

`observability/__init__.py`：

```python
from .loop_lag import LoopLagMonitor, LoopLagSnapshot

__all__ = ["LoopLagMonitor", "LoopLagSnapshot"]
```

`observability/loop_lag.py`：

```python
"""Event-loop lag monitor (remediation M0, R0-05)."""

from __future__ import annotations

import asyncio
import logging
from collections import deque
from dataclasses import dataclass
from time import perf_counter

LOGGER = logging.getLogger("autoflow.loop_lag")


@dataclass(frozen=True)
class LoopLagSnapshot:
    p50_ms: float
    p99_ms: float
    max_ms: float
    samples: int


def _percentile(ordered: list[float], fraction: float) -> float:
    if not ordered:
        return 0.0
    return ordered[min(len(ordered) - 1, max(0, round(fraction * (len(ordered) - 1))))]


class LoopLagMonitor:
    """Schedules a heartbeat and records how late the event loop ran it."""

    def __init__(self, *, interval: float = 0.05, warn_ms: float = 100.0, capacity: int = 6000) -> None:
        self._interval = interval
        self._warn_ms = warn_ms
        self._samples: deque[float] = deque(maxlen=capacity)
        self._task: asyncio.Task[None] | None = None

    @property
    def running(self) -> bool:
        return self._task is not None and not self._task.done()

    async def start(self) -> None:
        if not self.running:
            self._task = asyncio.create_task(self._run(), name="autoflow-loop-lag")

    async def stop(self) -> None:
        task, self._task = self._task, None
        if task is not None:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)

    def snapshot(self) -> LoopLagSnapshot:
        ordered = sorted(self._samples)
        return LoopLagSnapshot(
            p50_ms=_percentile(ordered, 0.50),
            p99_ms=_percentile(ordered, 0.99),
            max_ms=ordered[-1] if ordered else 0.0,
            samples=len(ordered),
        )

    def reset(self) -> None:
        self._samples.clear()

    async def _run(self) -> None:
        while True:
            expected = perf_counter() + self._interval
            await asyncio.sleep(self._interval)
            lag_ms = max(0.0, (perf_counter() - expected) * 1000)
            self._samples.append(lag_ms)
            if lag_ms > self._warn_ms:
                LOGGER.warning("event loop lag %.0f ms", lag_ms)
```

- [ ] **Step 4: 运行单元测试**

Run: `uv run --directory apps/backend pytest -q tests/unit/test_loop_lag.py`
Expected: 2 passed。

- [ ] **Step 5: 写失败的接入测试**

`tests/contract/test_loop_lag_wiring.py`（使用 `tests/contract/conftest.py` 的 `client` 夹具；`TestClient` 会执行启动与关闭钩子）：

```python
from autoflow.infrastructure.observability import LoopLagMonitor


def test_sidecar_runs_one_loop_lag_monitor_for_its_lifetime(client):
    monitor = client.app.state.loop_lag
    assert isinstance(monitor, LoopLagMonitor)
    assert monitor.running
```

Run: `uv run --directory apps/backend pytest -q tests/contract/test_loop_lag_wiring.py`
Expected: FAIL，`AttributeError: 'State' object has no attribute 'loop_lag'`。

- [ ] **Step 6: 在 create_app 中接入**

`bootstrap/app.py` 顶部 import 区加入：

```python
from autoflow.infrastructure.observability import LoopLagMonitor
```

紧跟 `app.state.config = settings` 之后：

```python
    loop_lag = LoopLagMonitor()
    app.state.loop_lag = loop_lag
    app.router.add_event_handler("startup", loop_lag.start)
```

`shutdown()` 最外层 `finally` 中，把

```python
            finally:
                session_factory.dispose()
```

改为

```python
            finally:
                await loop_lag.stop()
                session_factory.dispose()
```

- [ ] **Step 7: 运行**

Run: `uv run --directory apps/backend pytest -q tests/unit/test_loop_lag.py tests/contract/test_loop_lag_wiring.py tests/contract/test_settings_dashboard.py`
Expected: 全部通过。
Run: `uv run --directory apps/backend ruff check src tests/unit/test_loop_lag.py && uv run --directory apps/backend mypy src`
Expected: 无错误。

- [ ] **Step 8: 提交**

```bash
git add apps/backend/src/autoflow/infrastructure/observability apps/backend/src/autoflow/bootstrap/app.py apps/backend/tests/unit/test_loop_lag.py apps/backend/tests/contract/test_loop_lag_wiring.py
git commit -m "feat(observability): 服务主循环延迟监测，超过 100 毫秒记警告"
```

---

### Task 5: 黄金场景站点（R0-06 站点部分）

**Files:**
- Create: `apps/backend/tests/golden/__init__.py`（空文件）
- Create: `apps/backend/tests/golden/site.py`
- Test: `apps/backend/tests/golden/test_golden_site.py`

**Interfaces:**
- Produces: `GoldenSite`（上下文管理器）：`base_url: str`、`hits(prefix: str) -> int`、`submissions(name: str) -> int`；模块常量 `FIELDS = ("title","price","sku","stock","seller")`、`FIRST_LOAD_DELAY_SECONDS = 20.0`、`LOST_RESPONSE_HOLD_SECONDS = 30.0`。规则：`/item/timeout-*` 首次请求延迟、`/item/gone-*` 固定 404、提交名以 `lose-` 开头时不返回响应。

- [ ] **Step 1: 写失败的测试**（站点测试不需要浏览器，不加 golden 标记，普通 CI 会运行）

```python
"""The golden site itself; runs without a browser."""

import httpx
import pytest

from . import site as site_module
from .site import FIELDS, GoldenSite


def test_item_pages_expose_five_fields_and_inject_faults(monkeypatch):
    monkeypatch.setattr(site_module, "FIRST_LOAD_DELAY_SECONDS", 0.2)
    with GoldenSite() as site:
        ok = httpx.get(f"{site.base_url}/item/a1")
        assert ok.status_code == 200
        for field in FIELDS:
            assert f"id={field}>{field}-a1<" in ok.text
        assert httpx.get(f"{site.base_url}/item/gone-1").status_code == 404
        with pytest.raises(httpx.ReadTimeout):
            httpx.get(f"{site.base_url}/item/timeout-1", timeout=0.05)
        assert httpx.get(f"{site.base_url}/item/timeout-1", timeout=2).status_code == 200
        assert site.hits("/item/") == 4


def test_form_submits_once_and_lost_responses_never_answer(monkeypatch):
    monkeypatch.setattr(site_module, "LOST_RESPONSE_HOLD_SECONDS", 0.3)
    with GoldenSite() as site:
        form = httpx.get(f"{site.base_url}/form?name=row-1")
        assert "action='/submit'" in form.text
        assert "value='row-1'" in form.text
        done = httpx.post(f"{site.base_url}/submit", data={"name": "row-1"})
        assert done.text == "<p id=result>ok:row-1</p>"
        with pytest.raises(httpx.HTTPError):
            httpx.post(f"{site.base_url}/submit", data={"name": "lose-1"}, timeout=2)
        assert site.submissions("row-1") == 1
        assert site.submissions("lose-1") == 1
```

- [ ] **Step 2: 运行，确认失败**

Run: `uv run --directory apps/backend pytest -q tests/golden/test_golden_site.py`
Expected: FAIL，`ModuleNotFoundError: tests.golden.site`。

- [ ] **Step 3: 实现 site.py**

```python
"""Local golden-scenario site with fault injection (remediation M0, spec §5.4)."""

from __future__ import annotations

import html
import threading
import time
from collections import Counter
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlsplit

FIELDS = ("title", "price", "sku", "stock", "seller")
FIRST_LOAD_DELAY_SECONDS = 20.0
LOST_RESPONSE_HOLD_SECONDS = 30.0


class GoldenSite:
    """Serve /item/<id>, /form and /submit on a random local port."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
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
            return sum(count for path, count in self._hits.items() if path.startswith(prefix))

    def submissions(self, name: str) -> int:
        with self._lock:
            return self._submissions[name]

    def __enter__(self) -> GoldenSite:
        site = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *_args: object) -> None:
                return None

            def _send(self, status: int, body: str) -> None:
                content = body.encode("utf-8")
                self.send_response(status)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(content)))
                self.end_headers()
                self.wfile.write(content)

            def do_GET(self) -> None:  # noqa: N802 - http.server API
                url = urlsplit(self.path)
                with site._lock:
                    site._hits[url.path] += 1
                if url.path.startswith("/item/"):
                    self._item(url.path.removeprefix("/item/"))
                elif url.path == "/form":
                    name = html.escape((parse_qs(url.query).get("name") or [""])[0], quote=True)
                    self._send(
                        200,
                        "<form method=post action='/submit'>"
                        f"<input id=name name=name value='{name}'>"
                        "<button id=submit type=submit>提交</button></form>",
                    )
                else:
                    self._send(404, "<h1>not found</h1>")

            def do_POST(self) -> None:  # noqa: N802 - http.server API
                url = urlsplit(self.path)
                with site._lock:
                    site._hits[url.path] += 1
                if url.path != "/submit":
                    self._send(404, "<h1>not found</h1>")
                    return
                length = int(self.headers.get("Content-Length") or 0)
                name = (parse_qs(self.rfile.read(length).decode("utf-8")).get("name") or [""])[0]
                with site._lock:
                    site._submissions[name] += 1
                if name.startswith("lose-"):
                    time.sleep(LOST_RESPONSE_HOLD_SECONDS)
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
                        time.sleep(FIRST_LOAD_DELAY_SECONDS)
                safe = html.escape(identity)
                spans = "".join(f"<span id={field}>{field}-{safe}</span>" for field in FIELDS)
                self._send(200, f"<main>{spans}</main>")

        self._server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self._server.daemon_threads = True
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()
        return self

    def __exit__(self, *_exc: object) -> None:
        if self._server is not None:
            self._server.shutdown()
            self._server.server_close()
        if self._thread is not None:
            self._thread.join(timeout=5)
```

说明：`time.sleep` 读取的是模块全局常量，测试通过 `monkeypatch.setattr(site_module, ...)` 缩短等待。

- [ ] **Step 4: 运行**

Run: `uv run --directory apps/backend pytest -q tests/golden/test_golden_site.py`
Expected: 2 passed。

- [ ] **Step 5: 提交**

```bash
git add apps/backend/tests/golden/__init__.py apps/backend/tests/golden/site.py apps/backend/tests/golden/test_golden_site.py
git commit -m "test(golden): 带故障注入的本地黄金场景站点"
```

---

### Task 6: 黄金场景 harness 与 G2、G3（R0-06，r2 替换旧示例）

**Files:**
- Create: `apps/backend/tests/golden/conftest.py`、`harness.py`、`test_golden_metrics.py`、`test_g2_scrape.py`、`test_g3_form_entry.py`
- Reuse: `tests/integration/test_workflow_real_cloakbrowser.py::real_cloak_page`、`tests/integration/test_project_debug_inputs.py` 的公开调试选择契约、`tests/fixtures/profiles.py`；不把生产领取器替换为 fake。

**Interfaces:**
- Consumes: GoldenSite、report.write_report、app.state.loop_lag、现有项目数据/调试预检/批次启动与任务查询接口。
- Produces: `golden_rows(scenario: str, default: int = 30) -> int`（必须 >0）；`flow_node(identity, kind, index, **config)`、`chain(nodes)`、`input_reference(input_spec)`（保留 M1 Task 14 的调用）；`async run_golden(tmp_path, executable, profile_values, *, values, build, concurrency=2, timeout_seconds=3600) -> GoldenRun`；`GoldenRun.details`、`.metrics()`、`.expected_refs`、`.verified_success_refs`。refs 使用现有完整 RecordRef 的规范序列化，不能只取显示值。
- 指标：tasks_attempted=len(details)；distinct_rows_processed=唯一完整 refs 数；rows_succeeded=经输出/站点验证且任务成功的唯一 refs 数；throughput_rows_per_min=rows_succeeded×60/elapsed；attempts_per_min=tasks_attempted×60/elapsed；有原因失败要求非空非通用 message（M2 后还需稳定 category）；失败分母 0 时 failure_reason_ratio=null。

- [ ] **Step 1: 先写无需浏览器的反例测试。** `test_golden_metrics.py` 用30条同身份、status=failed、error=None 的 detail，断言 distinct_rows_processed=1、rows_succeeded=0、throughput_rows_per_min=0、attempts_per_min=30、failure_reason_ratio=0；无失败样本断言覆盖率为 None；一条成功行重复两次只能计一条。`assert_complete_coverage(expected_refs, details)` 遇缺行或重复抛 AssertionError。这些测试不标 golden。
- [ ] **Step 2: 验证 RED。** `uv run --directory apps/backend pytest -q tests/golden/test_golden_metrics.py`；应因新模块缺失失败，不把夹具缺失当作 skip。
- [ ] **Step 3: 实现指标与显式 fixture 注册。** golden/conftest.py 导入并暴露 real_cloak_page（复用现有 fixture，若有耦合则提到 tests/fixtures 后由两个范围共同导入）；不依赖兄弟测试模块自动发现。report 允许 None 且输出合法 JSON null。同目录 manifest 保存总纲第4节维度，硬件或版本未知要显式记录并禁止用于收益比较。
- [ ] **Step 4: 实现受控输入 harness。** 创建真实项目、表、流程和自动化；枚举每个完整输入身份，通过现有调试预检获取该行 debugSelection；每行调用公开启动批次接口，maxTasks=1、concurrency=1、独立幂等键。用 Semaphore 限制并行批次为 concurrency，重试查询只能重用原命令身份。每个批次等待终态并查询唯一 Task；聚合结果后断言 refs 集合恰好等于输入全集且无重复。取消/超时记录为无效基准并停止自建批次、等待清理，不算已处理成功。禁止为此改动生产代码、筛选器或台账。
- [ ] **Step 5: G2/G3 行为验收。** G2：普通行五个字段逐值校验；timeout/gone 样本确认站点收到指定请求和预期失败。G3：所有正常行返回正确 result，站点对正常/lose 每行均恰好收到一次提交。运行时丢失响应的当前终态如实记录；另一个小规模独立测试用 xfail(strict=True) 声明尚缺 needs_review，不能将基准覆盖/副作用断言放进 xfail。
- [ ] **Step 6: 核验两种环境。** 未配置浏览器：`uv run --directory apps/backend pytest -q -m golden tests/golden` 应仅跳过浏览器用例，不得有 fixture not found；`uv run --directory apps/backend pytest -q tests/golden` 应通过全部指标与站点测试。配置浏览器：`AUTOFLOW_TEST_CLOAKBROWSER=<真实路径> AUTOFLOW_GOLDEN_ROWS=30 uv run --directory apps/backend pytest -q -m golden tests/golden -s`，正确性用例必须通过；独立已知缺口为 xfail，其余失败不可豁免。再用101行验证没有100行上限/提前停止。上传数值报告、manifest、逐行预期与实际摘要，不入库。
- [ ] **Step 7: 记录 controlled-one-row-batches-v1 基线并提交。** 当前单任务批次的调度开销计入端到端数据；不声称代表原生万行批次吞吐。`git add apps/backend/tests/golden apps/backend/tests/benchmarks/report.py` 后提交 `test(golden): verify unique row coverage and truthful metrics`。

---

### Task 7: 守门检查脚本（R0-07）

**Files:**
- Create: `scripts/ratchets.mjs`
- Create: `scripts/ratchets-baseline.json`（由脚本生成）
- Test: `scripts/ratchets.test.mjs`（被根目录 `npm run test:scripts` 自动包含）

**Interfaces:**
- Produces: `measure(root: string) -> { unreadConfigKeys: string[], paletteClasses: number, secondIconLibraryFiles: number, docsPng: number }`；`compare(current, baseline) -> { failures: string[], improvements: string[] }`；CLI：`node scripts/ratchets.mjs`（比较）与 `node scripts/ratchets.mjs --write-baseline`（写基线）。M1 起每个里程碑在基线下降时运行 `--write-baseline`。

- [ ] **Step 1: 写失败的测试**

```javascript
import assert from 'node:assert/strict'
import { mkdirSync, mkdtempSync, rmSync, writeFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { dirname, join } from 'node:path'
import { test } from 'node:test'
import { compare, measure } from './ratchets.mjs'

function measured(files) {
  const root = mkdtempSync(join(tmpdir(), 'ratchets-'))
  try {
    for (const [path, content] of Object.entries(files)) {
      mkdirSync(dirname(join(root, path)), { recursive: true })
      writeFileSync(join(root, path), content)
    }
    return measure(root)
  } finally {
    rmSync(root, { recursive: true, force: true })
  }
}

const panel = 'apps/desktop/src/renderer/domains/workflows/components/ConfigPanel.tsx'
const node = 'apps/desktop/src/renderer/domains/workflows/components/Node.tsx'
const base = {
  [panel]: "handleChange('selector', v); handleChange('retryCount', v)",
  'apps/desktop/src/renderer/domains/workflows/components/config-panels/Loop.test.tsx': "onChange('onlyInTests', v)",
  'apps/backend/src/autoflow/executor.py': "config.get('selector')",
  [node]: "<div className='bg-blue-500' />",
  'apps/desktop/src/renderer/app/Icon.tsx': "import { X } from '@phosphor-icons/react'",
  'docs/qa/shot.png': 'png',
}

test('measures the four ratchet counters and ignores test files', () => {
  assert.deepEqual(measured(base), { unreadConfigKeys: ['retryCount'], paletteClasses: 1, secondIconLibraryFiles: 1, docsPng: 1 })
})

test('fails on each new unread key, palette class, icon import and PNG, naming the item', () => {
  const current = measured({
    ...base,
    [panel]: base[panel] + "; onChange('timeoutAction', v)",
    [node]: "<div className='bg-blue-500 text-red-700' />",
    'apps/desktop/src/renderer/app/Other.tsx': "import { Y } from '@phosphor-icons/react'",
    'docs/qa/another.PNG': 'png',
  })
  const { failures } = compare(current, measured(base))
  assert.equal(failures.length, 4)
  assert.match(failures[0], /timeoutAction/)
  assert.match(failures.join('\n'), /paletteClasses 从 1 增加到 2/)
  assert.match(failures.join('\n'), /secondIconLibraryFiles 从 1 增加到 2/)
  assert.match(failures.join('\n'), /docsPng 从 1 增加到 2/)
})

test('reports improvements without failing', () => {
  const current = measured({ ...base, [panel]: "handleChange('selector', v)" })
  assert.deepEqual(compare(current, measured(base)), { failures: [], improvements: ['unreadConfigKeys'] })
})
```

- [ ] **Step 2: 运行，确认失败**

Run: `node --test scripts/ratchets.test.mjs`
Expected: FAIL，`Cannot find module .../scripts/ratchets.mjs`。

- [ ] **Step 3: 实现 scripts/ratchets.mjs**

```javascript
#!/usr/bin/env node
// Ratchet checks: existing debt may only shrink.
// Spec: docs/superpowers/specs/2026-09-30-remediation-m0-baseline-guardrails.md §5.5
import { readFileSync, readdirSync, statSync, writeFileSync } from 'node:fs'
import { dirname, join, relative, resolve, sep } from 'node:path'
import { fileURLToPath } from 'node:url'

const PALETTE = /\b(?:bg|text|border|ring|from|to|via)-(?:gray|slate|zinc|neutral|stone|red|orange|amber|yellow|lime|green|emerald|teal|cyan|sky|blue|indigo|violet|purple|fuchsia|pink|rose)-(?:50|[1-9]00|950)\b/g
const CONFIG_KEY = /\b(?:handleChange|onChange)\(\s*'([A-Za-z_][A-Za-z0-9_]*)'/g
const SKIP = new Set(['node_modules', '.git', '__pycache__', 'dist', 'out'])

function walk(root, accept, out = []) {
  let entries
  try { entries = readdirSync(root) } catch { return out }
  for (const name of entries) {
    if (SKIP.has(name)) continue
    const path = join(root, name)
    if (statSync(path).isDirectory()) walk(path, accept, out)
    else if (accept(path)) out.push(path)
  }
  return out
}

const isTest = path => /\.test\.[cm]?[jt]sx?$/.test(path) || path.split(sep).includes('tests')
const read = path => { try { return readFileSync(path, 'utf8') } catch { return '' } }

export function measure(root) {
  const workflows = join(root, 'apps/desktop/src/renderer/domains/workflows')
  const panels = [join(workflows, 'components/ConfigPanel.tsx'),
    ...walk(join(workflows, 'components/config-panels'), p => p.endsWith('.tsx') && !isTest(p))]
  const keys = new Set()
  for (const file of panels) for (const match of read(file).matchAll(CONFIG_KEY)) keys.add(match[1])
  const backend = walk(join(root, 'apps/backend/src/autoflow'), p => p.endsWith('.py')).map(read).join('\n')
  const unreadConfigKeys = [...keys].filter(key => !backend.includes(`'${key}'`) && !backend.includes(`"${key}"`)).sort()
  let paletteClasses = 0
  for (const file of walk(workflows, p => /\.(?:tsx?|css)$/.test(p))) paletteClasses += (read(file).match(PALETTE) ?? []).length
  const secondIconLibraryFiles = walk(join(root, 'apps/desktop/src'), p => /\.[cm]?[jt]sx?$/.test(p))
    .filter(p => read(p).includes("from '@phosphor-icons/react'")).length
  const docsPng = walk(join(root, 'docs'), p => p.toLowerCase().endsWith('.png')).length
  return { unreadConfigKeys, paletteClasses, secondIconLibraryFiles, docsPng }
}

export function compare(current, baseline) {
  const failures = []
  const improvements = []
  const newKeys = current.unreadConfigKeys.filter(key => !baseline.unreadConfigKeys.includes(key))
  if (newKeys.length) failures.push(`新增了后端未读取的配置键：${newKeys.join(', ')}`)
  if (current.unreadConfigKeys.length < baseline.unreadConfigKeys.length) improvements.push('unreadConfigKeys')
  for (const name of ['paletteClasses', 'secondIconLibraryFiles', 'docsPng']) {
    if (current[name] > baseline[name]) failures.push(`${name} 从 ${baseline[name]} 增加到 ${current[name]}`)
    if (current[name] < baseline[name]) improvements.push(name)
  }
  return { failures, improvements }
}

function main() {
  const root = resolve(dirname(fileURLToPath(import.meta.url)), '..')
  const baselinePath = join(root, 'scripts/ratchets-baseline.json')
  const current = measure(root)
  if (process.argv.includes('--write-baseline')) {
    writeFileSync(baselinePath, JSON.stringify(current, null, 2) + '\n')
    console.log(`已写入基线 ${relative(root, baselinePath)}`)
    return
  }
  const { failures, improvements } = compare(current, JSON.parse(readFileSync(baselinePath, 'utf8')))
  for (const failure of failures) console.error(`✗ ${failure}`)
  if (improvements.length) console.log(`↓ 以下指标已减少，请运行 node scripts/ratchets.mjs --write-baseline 收紧基线：${improvements.join(', ')}`)
  console.log(`unreadConfigKeys=${current.unreadConfigKeys.length} paletteClasses=${current.paletteClasses} secondIconLibraryFiles=${current.secondIconLibraryFiles} docsPng=${current.docsPng}`)
  if (failures.length) process.exitCode = 1
}

if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) main()
```

- [ ] **Step 4: 运行测试**

Run: `node --test scripts/ratchets.test.mjs`
Expected: 3 pass。

- [ ] **Step 5: 生成并检查基线**

Run: `node scripts/ratchets.mjs --write-baseline && node scripts/ratchets.mjs`
Expected: 第二条输出 `unreadConfigKeys=127 paletteClasses=2008 secondIconLibraryFiles=80 docsPng=3247`（ea2cc5b 实测；若主线已变，以实际为准），退出码 0。人工确认 `scripts/ratchets-baseline.json` 的 `unreadConfigKeys` 含 errorPolicy、onTimeout、retryBackoff、retryCount、retryDelay、retryExhaustedAction、timeoutAction。

- [ ] **Step 6: 提交**

```bash
git add scripts/ratchets.mjs scripts/ratchets.test.mjs scripts/ratchets-baseline.json
git commit -m "chore(ratchet): 未读取配置键、写死颜色、第二套图标、仓库截图只减不增"
```

---

### Task 8: CI 接入（R0-08）

**Files:**
- Modify: `.github/workflows/ci.yml`（`checks` job）
- Create: `.github/workflows/golden.yml`

**Interfaces:**
- Consumes: Task 1–3 的基准模块、Task 6 的 `-m golden` 场景、Task 7 的脚本。

- [ ] **Step 1: 在 ci.yml 的 `checks` job 中加入守门检查**

紧跟 `- run: npm run test:scripts` 之后：

```yaml
      - name: Ratchet checks (debt may only shrink)
        run: node scripts/ratchets.mjs
```

- [ ] **Step 2: 加入离线基准（只记录）**

紧跟 `- run: uv run --directory apps/backend pytest -q --maxfail=20` 之后：

```yaml
      - name: Offline benchmarks (record only, spec M0 R0-08)
        shell: bash
        run: |
          uv run --directory apps/backend pytest -q -m benchmark tests/benchmarks
          uv run --directory apps/backend python -m tests.benchmarks.bench_claims --rows 10000
          uv run --directory apps/backend python -m tests.benchmarks.bench_runtime_overhead --iterations 1000
          uv run --directory apps/backend python -m tests.benchmarks.bench_event_commit --events 1000
      - uses: actions/upload-artifact@v4
        if: always()
        with:
          name: benchmarks-${{ matrix.os }}
          path: apps/backend/tests/benchmarks/results/
          if-no-files-found: ignore
```

- [ ] **Step 3: 新建 golden.yml**

```yaml
name: Golden scenarios

on:
  workflow_dispatch:
    inputs:
      rows:
        description: 每个场景的行数（留空时 G2=10000、G3=1000）
        required: false
        default: ''
  schedule:
    - cron: '17 18 * * *'

concurrency:
  group: golden-${{ github.ref }}
  cancel-in-progress: false

jobs:
  golden:
    runs-on: macos-15
    timeout-minutes: 360
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      - uses: astral-sh/setup-uv@v5
      - run: uv sync --directory apps/backend --locked
      - name: Install pinned real browser
        shell: bash
        run: |
          uv run --directory apps/backend python - <<'PYTHON'
          import os
          from cloakbrowser import ensure_binary
          executable = ensure_binary(browser_version='145.0.7632.109.2')
          with open(os.environ['GITHUB_ENV'], 'a', encoding='utf-8') as output:
              output.write(f'GOLDEN_BROWSER_EXECUTABLE={executable}\n')
          PYTHON
      - name: Run golden scenarios
        run: uv run --directory apps/backend pytest -q -m golden tests/golden -s
        env:
          AUTOFLOW_TEST_CLOAKBROWSER: ${{ env.GOLDEN_BROWSER_EXECUTABLE }}
          AUTOFLOW_GOLDEN_ROWS: ${{ inputs.rows }}
          AUTOFLOW_GOLDEN_G2_ROWS: ${{ inputs.rows || '10000' }}
          AUTOFLOW_GOLDEN_G3_ROWS: ${{ inputs.rows || '1000' }}
      - uses: actions/upload-artifact@v4
        if: always()
        with:
          name: golden-${{ github.run_id }}
          path: apps/backend/tests/benchmarks/results/
          if-no-files-found: ignore
```

- [ ] **Step 4: 本地校验 YAML**

Run: `node -e "for (const f of ['.github/workflows/ci.yml','.github/workflows/golden.yml']) { const t=require('fs').readFileSync(f,'utf8'); if (/\t/.test(t)) throw new Error(f+' has tabs'); } console.log('ok')"`
Expected: `ok`。推送分支后在 Actions 页面确认 `checks` 出现两个新步骤、`Golden scenarios` 可手动触发（填 rows=30 试跑一次）。

- [ ] **Step 5: 提交**

```bash
git add .github/workflows/ci.yml .github/workflows/golden.yml
git commit -m "ci: 每次推送运行守门检查与离线基准，新增夜间黄金场景"
```

---

### Task 9: 协作规则与文档（R0-09）

**Files:**
- Modify: `AGENTS.md`（"完成定义"之前新增一节）
- Modify: `docs/PROJECT_STRUCTURE.md`（目录职责清单）
- Create: `.ai/knowledge/2026-09-30-remediation-baseline.md`

- [ ] **Step 1: 在 AGENTS.md 中加入规则**

在 `## 完成定义` 之前插入：

```markdown
## 整改期硬性规则（2026-09-30 起，来源：docs/superpowers/specs/2026-09-30-remediation-roadmap.md）

1. 界面上新增的每个配置项，必须有后端读取它的代码和测试；`node scripts/ratchets.mjs` 会拦截新增的未读取键。
2. 任何失败路径必须把原始原因传递到用户可见的日志，除非涉及凭据。
3. 不得在事件循环上直接调用同步数据库操作；需要时用线程（`asyncio.to_thread`），主循环延迟由 `app.state.loop_lag` 监测。
4. 涉及批量执行的改动，必须附 `tests/benchmarks` 基准（必要时加黄金场景）的前后对比数字。
5. 新增节点类型需要说明服务哪一类业务场景（多账号运营、数据采集、批量录入、定时巡检、人机协作）。
6. 界面文案不得出现内部术语（数据集代次、RecordRef、执行代次等，见整改方案 M 节）。
7. QA 截图与证据不再提交到 `docs/`；放 CI 产物，仓库只留汇总与链接。
```

- [ ] **Step 2: 更新 PROJECT_STRUCTURE**

在"目录职责清单"表格末尾追加三行：

```markdown
| `apps/backend/tests/benchmarks/` | 整改基准（领取、执行开销、事件提交），结果写 `results/`（不入库）。2026-09-30，confirmed。 |
| `apps/backend/tests/golden/` | 黄金场景：本地故障注入站点、真实 API + 浏览器的 G2/G3，`-m golden` 运行。 |
| `apps/backend/src/autoflow/infrastructure/observability/` | 运行期可观测组件；`loop_lag.py` 监测服务主循环延迟。 |
```

- [ ] **Step 3: 记录基线**

`.ai/knowledge/2026-09-30-remediation-baseline.md`：

```markdown
# 整改基线（M0）

日期：2026-09-30；状态：confirmed（数值来自本里程碑实际运行，按运行环境分列）。

| 指标 | 本机（填系统与芯片） | CI macos-15 | 来源 |
| --- | --- | --- | --- |
| claim_ms_key_order（10,000 行） | 填 | 填 | bench_claims |
| claim_ms_field_order（10,000 行） | 填 | 填 | bench_claims |
| framework_ms_per_node | 填 | 填 | bench_runtime_overhead |
| events_per_node | 填 | 填 | bench_runtime_overhead |
| event_commit_ms_p50 / p99 | 填 | 填 | bench_event_commit |
| G2 throughput_rows_per_min / failure_reason_ratio | 填 | 填 | golden-g2 |
| G3 throughput_rows_per_min / 丢失响应行重复提交数 | 填 | 填 | golden-g3 |
| 守门：127 / 2008 / 80 / 3247（按实际） | — | — | scripts/ratchets-baseline.json |

后续里程碑以此为对照：M1 事件提交 p50 下降 ≥ 50%；M3 领取 < 20 毫秒、主循环 p99 < 50 毫秒。
```

表中"填"由执行者用 Task 1–3、6 的实际输出替换；这是记录实测值的步骤，不是占位——不得填写估计值。

- [ ] **Step 4: 提交**

```bash
git add AGENTS.md docs/PROJECT_STRUCTURE.md .ai/knowledge/2026-09-30-remediation-baseline.md
git commit -m "docs: 整改期硬性规则、目录职责与 M0 基线记录"
```

---

### 独立维护 Task 11: QA 资产迁出与历史清理（不阻塞 M0）

本任务仅定义后续操作，不在 M0 验收中自动执行。旧的 docs PNG 全通配符清理和 force mirror 指令已 superseded。

- [ ] **Step 1: 资产清单。** 从 Git 跟踪路径区分 QA 截图、有效原型、产品/文档资产；输出精确路径、哈希、引用位置与迁出目标。原型默认保留；需要迁出时先更新引用并验证可访问，不能接受“链接失效属预期”。
- [ ] **Step 2: 可恢复归档。** 用独立镜像备份全仓库，git fsck --full 验证对象和全部 refs；在临时副本验证恢复。把选中资产放到有保留策略的外部归档（尚未确定目标时停在清单，不删除）；下载复核哈希和访问权限。单纯 count-objects 有输出不算备份可用。
- [ ] **Step 3: 演练历史改写。** 仅在新镜像上按审核后的精确路径清单过滤；记录改写前后 refs/大小和commit映射，不操作当前工作副本。验证保留资产、文档链接及依赖图片的脚本；普通测试和构建结果与基线对照。
- [ ] **Step 4: 提交具体推送方案待确认。** 向用户呈现归档/备份位置、哈希验证、精确 refs 和推送策略、受影响的克隆/PR、回退步骤。得到当时明确同意后，只推送核对过的 refs并核验远端；不用无差别 force mirror。给协作者发消息须单独明确授权，未授权时提供通知草稿。
- [ ] **Step 5: 更新 ADR、引用与迁出清单。** 保留恢复证据；未完成历史维护不阻塞 M0→M1。

---

### Task 10: 里程碑验收

- [ ] **Step 1: 全量检查**

Run:
```bash
uv run --directory apps/backend ruff check .
uv run --directory apps/backend mypy src
uv run --directory apps/backend pytest -q
uv run --directory apps/backend pytest -q -m benchmark tests/benchmarks
npm run test:scripts
node scripts/ratchets.mjs
```
Expected: 全部通过；默认 pytest 不包含 benchmark / golden。

- [ ] **Step 2: 对照验收标准逐条勾选**

| AC | 证明 |
| --- | --- |
| AC0-01 | Task 1 Step 6 输出 |
| AC0-02 | Task 2 Step 4 输出（events_per_node ≥ 4） |
| AC0-03 | Task 3 Step 4 输出 |
| AC0-04 | `tests/unit/test_loop_lag.py`、`tests/contract/test_loop_lag_wiring.py` |
| AC0-05 | Task 6 Step 1/5/6（指标反例、行为与真实运行；skip不算通过） |
| AC0-06 | `scripts/ratchets.test.mjs` |
| AC0-07 | 推送后的 Actions 记录与构件 |
| AC0-08 | AGENTS.md diff |

- [ ] **Step 3: 退出评审**

派一个未参与实现的评审者（新会话或子代理），输入：本计划、M0 规格、`git diff main...remediation/m0-baseline-guardrails`，要求逐条核对 AC 与 Review Focus，给出通过 / 不通过。不通过项修复后再评审。

## r2 补充：报告与验证边界

Task 1 的 report 函数扩展 value 为 float | None；摘要格式化时 None 显示 n/a，JSON 为 null。新增 `write_manifest(context, reports, directory)`：必填 scenarioVersion、executionProfile、datasetSeed、faultSeed、hardware、browserVersion、concurrency、repetitions、commit；拒绝缺项，未知值显式标 unavailable 并禁止收益比较。离线 CLI 和 golden harness 每轮调用，CI 上传整个结果目录；测试覆盖 null、缺元数据、多个报告同属一轮和禁止不可比结果算倍数。

Task 8 的 YAML 校验不能只查制表符：复用仓库现有 YAML 解析能力，并实际手动触发30行运行，核验用例没有意外 skip且全部产物存在。Task 10 中真实浏览器不具备时登记 blocked，不以 skip 关闭 AC0-05；Task 11 不属于退出条件。所有预期测试数量以实际收集为准，不抄写旧“2 skipped”数字。
