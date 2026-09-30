# M1 止血：消除静默失效 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 消除"设置了却不生效""出错看不到原因""已处理的失败仍算失败""并发写死为 2""人工等待占名额""录制的回车跑不起来"等静默失效。

**Architecture:** 全部在现有结构内修改：运行时（`application/workflows/runtime.py`）增加出错语义参数；项目 worker 适配器（`providers/browser/project_graph.py`）透传真实原因并报告未生效设置；派发器 / worker 管理器 / 调度器把"执行名额"和"存活浏览器"分开计数，容量由新的 `ExecutionSettingsService` 按机器配置并可在线调整；SQLite 连接统一配置 WAL；前端用 `featureFlags` 隐藏未实现控件、新增按键节点与执行语义字段。

**Tech Stack:** Python 3.11、FastAPI、SQLAlchemy 2 + Alembic、pytest-asyncio、psutil；React 19 + zustand + vitest；OpenAPI 生成类型。

**Spec:** [docs/superpowers/specs/2026-09-30-remediation-m1-stop-silent-failures.md](../specs/2026-09-30-remediation-m1-stop-silent-failures.md)

> 本计划中的代码在 2026-09-30 以基线 ea2cc5b 为底逐项原型实现并运行过测试：后端相关测试（含 `test_workflow_dispatch.py`、`test_project_data_scheduler.py`、`test_migration_heads.py`、契约测试）与前端 `domains/workflows`、`project-automations`、`settings` 全部 vitest（4,169 个）及 `tsc --noEmit` 通过；因环境缺少 `reference/WebRPA`、OpenCV、摄像头而失败的测试与本计划无关，在基线上同样失败。补丁以统一 diff 给出，可直接 `git apply`；若主线已变导致上下文不匹配，按 diff 的语义手工修改。

## Global Constraints

- 前置：M0 已合并（`tests/benchmarks/`、`app.state.loop_lag`、`scripts/ratchets.mjs` 可用）。
- 旧文档行为不变：缺少 `executionSemantics` 的文档保持 WebRPA 出错语义；已保存的 errorPolicy / retry* / timeoutAction / onTimeout 值原样保留，不迁移、不删除。
- 容量：推荐值 = min(⌊逻辑 CPU × 3 / 4⌋, ⌊总内存 / 1.5 GiB⌋)，下限 1、上限 64；存活浏览器上限 = 2 × 执行名额；内存水位阈值 85%，5 秒后重试。
- 调低容量不中止正在运行的任务；人工继续可暂时超出执行名额。
- 数据库迁移文件名前缀 `rm1_`，`down_revision = "0025_merge_studio_credential_environment"`，只增不改。
- 新增依赖只有 `psutil>=7,<8`（锁文件中已有 7.2.2）。
- 错误信息不得包含凭据值：节点使用凭据派生值时沿用 `_reported_result` 的脱敏结果。
- 分支 `remediation/m1-stop-silent-failures`；每个任务一次提交，提交信息末尾附会话要求的 Co-Authored-By / Claude-Session 两行。
- 命令从仓库根目录执行：后端 `uv run --directory apps/backend pytest ...`，前端 `npm --workspace @autoflow/desktop test -- <路径>`。

## Review Focus

1. **开启 WAL 后按文件复制数据库**：未 checkpoint 的写入只在 `-wal` 文件里，直接复制主文件会丢数据。任何复制 / 备份数据库文件的代码与测试必须先调用 `checkpoint_wal`（Task 1 修正了 `test_identical_ids_in_two_workspaces_do_not_share_stop_or_claim_gate`，并要求执行者 grep 全仓库确认没有其他复制点）。
2. **运行中调低并发**：`set_capacity` 只影响之后的派发，不停止已有 owner（Task 7 的 `test_capacity_accepts_machine_sized_limits_and_rejects_invalid_values` 与契约测试覆盖）。
3. **人工继续时名额已满**：继续直接恢复，暂时超出执行名额，期间不派发新任务（Task 7 的 `test_waiting_manual_frees_its_execution_slot_but_keeps_its_live_browser`）。
4. **失败原因里含凭据**：节点使用凭据派生值时原因为"节点执行失败（错误包含凭据派生值）"（既有测试 `tests/unit/workflows/test_executor_registry.py::test_runtime_propagates_sensitive_values_without_persisting_them_in_events` 固定该行为；Task 2 不改变 `_reported_result`）。
5. **旧流程被静默改变出错语义**：无标记文档仍按旧语义失败（Task 3 的 `test_legacy_document_still_fails_after_error_branch`、`test_legacy_handled_failure_keeps_failing_the_batch_task`）。

---

### Task 1: SQLite 统一配置与单一引擎（R1-13）

**Files:**
- Modify: `apps/backend/src/autoflow/infrastructure/database/session.py`
- Modify: `apps/backend/src/autoflow/bootstrap/proxies.py`
- Modify: `apps/backend/src/autoflow/bootstrap/app.py`
- Modify: `apps/backend/tests/integration/test_project_data_scheduler.py`
- Test: `apps/backend/tests/unit/test_sqlite_session.py`

**Interfaces:**
- Produces: `session.SQLITE_PRAGMAS: tuple[str, ...]`、`session.checkpoint_wal(factory) -> None`；`configure_proxy_management(app, database, references=None, *, session_factory=None)`。

- [ ] **Step 1: 写失败的测试**

`apps/backend/tests/unit/test_sqlite_session.py`：

```python
"""Remediation M1 R1-13: every connection is configured for concurrent local use."""

from sqlalchemy import text

from autoflow.infrastructure.database.session import checkpoint_wal, create_session_factory, migrate_database


def test_every_connection_uses_wal_normal_sync_and_busy_timeout(tmp_path):
    path = tmp_path / "db.sqlite3"
    migrate_database(path)
    factory = create_session_factory(path)
    try:
        for _ in range(2):  # a second pooled connection gets the same settings
            with factory() as session:
                assert session.execute(text("PRAGMA journal_mode")).scalar() == "wal"
                assert session.execute(text("PRAGMA synchronous")).scalar() == 1
                assert session.execute(text("PRAGMA busy_timeout")).scalar() == 5000
                assert session.execute(text("PRAGMA foreign_keys")).scalar() == 1
        checkpoint_wal(factory)
        wal = path.with_name(path.name + "-wal")
        assert not wal.exists() or wal.stat().st_size == 0
    finally:
        factory.dispose()
```

- [ ] **Step 2: 运行，确认失败**

Run: `uv run --directory apps/backend pytest -q tests/unit/test_sqlite_session.py`
Expected: FAIL，`ImportError: cannot import name 'checkpoint_wal'`。

- [ ] **Step 3: 实现连接配置与 checkpoint**

`apps/backend/src/autoflow/infrastructure/database/session.py`：

```diff
diff --git a/apps/backend/src/autoflow/infrastructure/database/session.py b/apps/backend/src/autoflow/infrastructure/database/session.py
--- a/apps/backend/src/autoflow/infrastructure/database/session.py
+++ b/apps/backend/src/autoflow/infrastructure/database/session.py
@@ -3,7 +3,7 @@ from pathlib import Path
 
 from alembic import command
 from alembic.config import Config
-from sqlalchemy import create_engine, event
+from sqlalchemy import create_engine, event, text
 from sqlalchemy.exc import OperationalError
 from sqlalchemy.orm import sessionmaker
 
@@ -20,14 +20,31 @@ def migrate_database(path: Path) -> None:
     command.upgrade(config, "head")
 
 
+SQLITE_PRAGMAS = (
+    "PRAGMA journal_mode=WAL",
+    "PRAGMA synchronous=NORMAL",
+    "PRAGMA busy_timeout=5000",
+    "PRAGMA foreign_keys=ON",
+)
+
+
+def checkpoint_wal(factory) -> None:
+    """Fold the WAL back into the main file, e.g. before shutdown or a workspace copy."""
+    with factory() as session:
+        session.execute(text("PRAGMA wal_checkpoint(TRUNCATE)"))
+
+
 def create_session_factory(path: Path):
     engine = create_engine(_url(path), future=True)
 
     @event.listens_for(engine, "connect")
-    def enable_foreign_keys(connection, _record):
+    def configure_connection(connection, _record):
+        # Remediation M1 R1-13: WAL lets readers proceed during writes; NORMAL is durable
+        # across application crashes in WAL mode; busy_timeout absorbs short lock waits.
         cursor = connection.cursor()
         try:
-            cursor.execute("PRAGMA foreign_keys=ON")
+            for pragma in SQLITE_PRAGMAS:
+                cursor.execute(pragma)
         finally:
             cursor.close()
 
```

- [ ] **Step 4: 代理管理复用主会话工厂，关闭时 checkpoint**

`apps/backend/src/autoflow/bootstrap/proxies.py`：

```diff
diff --git a/apps/backend/src/autoflow/bootstrap/proxies.py b/apps/backend/src/autoflow/bootstrap/proxies.py
--- a/apps/backend/src/autoflow/bootstrap/proxies.py
+++ b/apps/backend/src/autoflow/bootstrap/proxies.py
@@ -2,7 +2,7 @@ from collections.abc import Awaitable, Callable
 from dataclasses import dataclass
 from functools import cached_property
 from pathlib import Path
-from typing import Literal
+from typing import Any, Literal
 
 from fastapi import FastAPI
 
@@ -61,8 +61,13 @@ def configure_proxy_management(
     app: FastAPI,
     database: Path,
     references: ProjectResourceReferences | None = None,
+    *,
+    session_factory: Any | None = None,
 ) -> ProxyManagementRuntime:
-    session_factory = create_session_factory(database)
+    # Remediation M1 R1-13: share the application's engine; only a factory created here is disposed here.
+    owns_factory = session_factory is None
+    if session_factory is None:
+        session_factory = create_session_factory(database)
     credentials = LazySystemCredentialStore()
     provider = ProxyPanelReadProvider()
     loader = ProxyCredentialLoader(
@@ -140,5 +145,6 @@ def configure_proxy_management(
         try:
             await remote.close()
         finally:
-            session_factory.dispose()
+            if owns_factory:
+                session_factory.dispose()
     return ProxyManagementRuntime(resolve_profile, close, workflow)
```

`apps/backend/src/autoflow/bootstrap/app.py`：

```diff
diff --git a/apps/backend/src/autoflow/bootstrap/app.py b/apps/backend/src/autoflow/bootstrap/app.py
--- a/apps/backend/src/autoflow/bootstrap/app.py
+++ b/apps/backend/src/autoflow/bootstrap/app.py
@@ -1,3 +1,4 @@
+import contextlib
 import secrets
 from concurrent.futures import ThreadPoolExecutor
 from functools import partial
@@ -173,6 +174,7 @@ from autoflow.infrastructure.database.project_sync_impacts import (
 from autoflow.infrastructure.database.projects import SqlAlchemyProjects
 from autoflow.infrastructure.database.proxy_options import SqlAlchemyProxyOptions
 from autoflow.infrastructure.database.session import (
+    checkpoint_wal,
     create_session_factory,
     migrate_database,
 )
@@ -340,7 +342,9 @@ def create_app(
     app.state.status_batch_service = status_batch_service
     app.state.status_batch_coordinator = status_batch_coordinator
     app.router.add_event_handler("startup", status_batch_coordinator.resume)
-    proxy_runtime = configure_proxy_management(app, paths.database, resource_references)
+    proxy_runtime = configure_proxy_management(
+        app, paths.database, resource_references, session_factory=session_factory
+    )
     # ponytail: unknown legacy owners block all proxies until their existing cleanup removes evidence.
     # Per-proxy recovery can replace this conservative guard once legacy runs persist binding identity.
     legacy_proxy_directories = tuple(
@@ -649,6 +653,8 @@ def create_app(
                 if isawaitable(closing):
                     await closing
             finally:
+                with contextlib.suppress(Exception):
+                    checkpoint_wal(session_factory)
                 session_factory.dispose()
 
     app.router.add_event_handler("shutdown", shutdown)
```

- [ ] **Step 5: 修正按文件复制数据库的测试，并排查其他复制点**

`apps/backend/tests/integration/test_project_data_scheduler.py`：

```diff
diff --git a/apps/backend/tests/integration/test_project_data_scheduler.py b/apps/backend/tests/integration/test_project_data_scheduler.py
--- a/apps/backend/tests/integration/test_project_data_scheduler.py
+++ b/apps/backend/tests/integration/test_project_data_scheduler.py
@@ -1144,11 +1144,12 @@ async def test_identical_ids_in_two_workspaces_do_not_share_stop_or_claim_gate(
     """Fails if a scheduler writes by logical ID outside its own workspace factory."""
     from shutil import copy2
 
-    from autoflow.infrastructure.database.session import create_session_factory
+    from autoflow.infrastructure.database.session import checkpoint_wal, create_session_factory
 
     factory, project, _, _, _, _, scheduler = data_services
     batch = start(data_services)
     other_path = tmp_path / "other-workspace.sqlite3"
+    checkpoint_wal(factory)  # WAL (M1 R1-13): a file copy only sees checkpointed pages
     copy2(factory.kw["bind"].url.database, other_path)
     other = create_session_factory(other_path)
     try:
```

Run: `git grep -nE "copy2|copyfile|copytree" -- apps/backend | grep -iE "sqlite|database|\.db"`
Expected: 除上面这处测试外没有复制数据库文件的代码；若有，同样先调用 `checkpoint_wal(factory)`。

- [ ] **Step 6: 运行**

Run: `uv run --directory apps/backend pytest -q tests/unit/test_sqlite_session.py tests/integration/test_project_data_scheduler.py tests/contract/test_settings_dashboard.py`
Expected: 全部通过。
Run: `uv run --directory apps/backend python -m tests.benchmarks.bench_event_commit`
Expected: `event_commit_ms_p50` 相对 `.ai/knowledge/2026-09-30-remediation-baseline.md` 中的 M0 基线下降 ≥ 50%（原型：4.1 → 1.4 毫秒）。把数字追加到该文件。

- [ ] **Step 7: 提交**

```bash
git add apps/backend/src/autoflow/infrastructure/database/session.py apps/backend/src/autoflow/bootstrap/proxies.py apps/backend/src/autoflow/bootstrap/app.py apps/backend/tests/unit/test_sqlite_session.py apps/backend/tests/integration/test_project_data_scheduler.py .ai/knowledge/2026-09-30-remediation-baseline.md
git commit -m "fix(db): SQLite 开启 WAL、NORMAL 同步与 busy_timeout，代理管理共用主引擎"
```

---

### Task 2: 失败日志带上真实原因（R1-03、R1-04）

**Files:**
- Modify: `apps/backend/src/autoflow/providers/browser/project_graph.py`（失败分支）
- Modify: `apps/backend/src/autoflow/infrastructure/process/project_workflow_worker.py`（项目能力被拒）
- Test: `apps/backend/tests/unit/test_project_graph_failure_reason.py`

**Interfaces:**
- Produces: 运行错误 `message` 形如 `工作流节点执行失败：<原因>` / `工作流节点执行超时：<原因>`，`code` 不变。

- [ ] **Step 1: 写失败的测试**（新文件，只含本任务的第一个用例；Task 3、Task 5 会向同一文件追加）

```python
"""Remediation M1 R1-03/R1-05 through the project worker adapter."""

import pytest

from autoflow.providers.browser.project_graph import ProjectGraphExecutor


def node(identity, kind, **config):
    return {'id': identity, 'data': {'moduleType': kind, **config}}


@pytest.mark.asyncio
async def test_batch_failure_log_carries_the_executor_reason():
    events = []

    async def emit(*event):
        events.append(event)

    executor = ProjectGraphExecutor(None, {}, emit, lambda: False)
    document = {'nodes': [node('parse', 'json_parse', jsonString='{not json', variableName='parsed')], 'edges': []}
    result = await executor.run({'document': document})
    assert result['status'] == 'failed'
    assert result['error']['code'] == 'WORKFLOW_NODE_FAILED'
    assert result['error']['message'].startswith('工作流节点执行失败：')
    assert len(result['error']['message']) > len('工作流节点执行失败：')
    error_logs = [event[3]['message'] for event in events if event[0] == 'log' and event[3].get('level') == 'error']
    assert error_logs == [result['error']['message']]
```

- [ ] **Step 2: 运行，确认失败**

Run: `uv run --directory apps/backend pytest -q tests/unit/test_project_graph_failure_reason.py`
Expected: FAIL，message 为 `工作流节点执行失败`（不含原因）。

- [ ] **Step 3: 实现**

`providers/browser/project_graph.py` 中，把

```python
            timeout = event.get('isTimeout') is True or event.get('error') == 'WORKFLOW_NODE_TIMEOUT'
            self.error = {'code': 'WORKFLOW_NODE_TIMEOUT' if timeout else 'WORKFLOW_NODE_FAILED', 'message': '工作流节点执行超时' if timeout else '工作流节点执行失败'}
```

替换为

```python
            timeout = event.get('isTimeout') is True or event.get('error') == 'WORKFLOW_NODE_TIMEOUT'
            reason = str(event.get('error') or event.get('message') or '').strip()
            if reason == 'WORKFLOW_NODE_TIMEOUT':
                reason = ''
            headline = '工作流节点执行超时' if timeout else '工作流节点执行失败'
            detail = reason[:1000] + '…' if len(reason) > 1000 else reason
            self.error = {'code': 'WORKFLOW_NODE_TIMEOUT' if timeout else 'WORKFLOW_NODE_FAILED', 'message': f'{headline}：{detail}' if detail else headline}
```

`infrastructure/process/project_workflow_worker.py` 中，把

```python
                    reply["error"] = {"code": rejected.code, "message": "项目能力请求未完成"}
```

替换为

```python
                    reply["error"] = {"code": rejected.code, "message": f"项目能力请求未完成：{rejected.message}"}
```

（`event['error']` 已经过运行时 `_reported_result`：节点使用凭据派生值时内容是固定的脱敏文案，见 Review Focus 4。）

- [ ] **Step 4: 运行**

Run: `uv run --directory apps/backend pytest -q tests/unit/test_project_graph_failure_reason.py tests/unit/test_project_graph_executor.py tests/unit/test_workflow_worker.py tests/integration/test_project_credential_worker.py`
Expected: 全部通过。

- [ ] **Step 5: 提交**

```bash
git add apps/backend/src/autoflow/providers/browser/project_graph.py apps/backend/src/autoflow/infrastructure/process/project_workflow_worker.py apps/backend/tests/unit/test_project_graph_failure_reason.py
git commit -m "fix(runs): 批量运行失败日志与项目能力拒绝带上真实原因"
```

---

### Task 3: 已处理的失败不算失败——后端（R1-05）

**Files:**
- Modify: `apps/backend/src/autoflow/application/workflows/runtime.py`
- Modify: `apps/backend/src/autoflow/providers/browser/project_graph.py`
- Modify: `apps/backend/src/autoflow/domain/workflows/validation.py`
- Test: `apps/backend/tests/unit/workflows/test_handled_failure_semantics.py`
- Test: `apps/backend/tests/unit/test_project_graph_failure_reason.py`（追加）

**Interfaces:**
- Produces: `runtime.ERROR_SEMANTICS_WEBRPA = "webrpa"`、`runtime.ERROR_SEMANTICS_V2 = "autoflow-v2"`、`runtime.document_error_semantics(document: Mapping) -> str`；`WorkflowRuntime.execute(document, context, *, start_node_id=None, detached=False, error_semantics: str | None = None)`；`WorkflowRuntimeResult.handled_failure_node_ids: tuple[str, ...]`。Task 4 的前端写入 `executionSemantics: "autoflow-v2"`。

- [ ] **Step 1: 写失败的测试**

`apps/backend/tests/unit/workflows/test_handled_failure_semantics.py`：

```python
"""Remediation M1 R1-05: failures caught by an error edge do not fail a v2 run."""

import pytest

from autoflow.application.workflows.runtime import (
    ERROR_SEMANTICS_V2,
    ERROR_SEMANTICS_WEBRPA,
    document_error_semantics,
)
from tests.differential.workflows.test_b3_control_flow_runtime_contract import (
    ControlContext,
    document,
    edge,
    node,
    runtime_with_probes,
)


def _handled_document(semantics: str | None) -> dict:
    value = document(
        [node("fails", "set_variable", action="fail"), node("handler", "set_variable")],
        [edge("fails", "handler", "error")],
    )
    if semantics is not None:
        value["executionSemantics"] = semantics
    return value


def test_documents_without_marker_keep_webrpa_semantics() -> None:
    assert document_error_semantics({}) == ERROR_SEMANTICS_WEBRPA
    assert document_error_semantics({"executionSemantics": "other"}) == ERROR_SEMANTICS_WEBRPA
    assert document_error_semantics({"executionSemantics": "autoflow-v2"}) == ERROR_SEMANTICS_V2


@pytest.mark.asyncio
async def test_v2_failure_caught_by_error_edge_does_not_fail_the_run() -> None:
    runtime, state = runtime_with_probes()
    result = await runtime.execute(_handled_document(ERROR_SEMANTICS_V2), ControlContext())
    assert state.trace == ["fails", "handler"]
    assert result.success is True
    assert result.failed_node_id is None
    assert result.handled_failure_node_ids == ("fails",)


@pytest.mark.asyncio
async def test_legacy_document_still_fails_after_error_branch() -> None:
    runtime, state = runtime_with_probes()
    result = await runtime.execute(_handled_document(None), ControlContext())
    assert state.trace == ["fails", "handler"]
    assert result.success is False
    assert result.failed_node_id == "fails"


@pytest.mark.asyncio
async def test_explicit_semantics_argument_overrides_the_document_marker() -> None:
    runtime, _state = runtime_with_probes()
    result = await runtime.execute(
        _handled_document(None), ControlContext(), error_semantics=ERROR_SEMANTICS_V2
    )
    assert result.success is True


@pytest.mark.asyncio
async def test_v2_failure_inside_the_error_handler_still_fails_the_run() -> None:
    runtime, state = runtime_with_probes()
    value = document(
        [node("fails", "set_variable", action="fail"), node("handler", "set_variable", action="fail")],
        [edge("fails", "handler", "error")],
    )
    value["executionSemantics"] = ERROR_SEMANTICS_V2
    result = await runtime.execute(value, ControlContext())
    assert state.trace == ["fails", "handler"]
    assert result.success is False
    assert result.failed_node_id == "handler"
    assert result.handled_failure_node_ids == ("fails",)


@pytest.mark.asyncio
async def test_v2_unhandled_failure_still_halts() -> None:
    runtime, state = runtime_with_probes()
    value = document(
        [node("fails", "set_variable", action="fail"), node("next", "set_variable")],
        [edge("fails", "next")],
    )
    value["executionSemantics"] = ERROR_SEMANTICS_V2
    result = await runtime.execute(value, ControlContext())
    assert state.trace == ["fails"]
    assert result.success is False
```

向 `tests/unit/test_project_graph_failure_reason.py` 追加：

```python
def _bad_json_then_handler(semantics=None):
    document = {
        'nodes': [
            node('parse', 'json_parse', jsonString='{not json', variableName='parsed'),
            node('handler', 'set_variable', variableName='handled', variableValue='yes'),
        ],
        'edges': [{'id': 'e', 'source': 'parse', 'target': 'handler', 'sourceHandle': 'error'}],
    }
    if semantics:
        document['executionSemantics'] = semantics
    return document


@pytest.mark.asyncio
async def test_v2_handled_failure_lets_the_batch_task_succeed():
    async def emit(*_event):
        return None

    executor = ProjectGraphExecutor(None, {}, emit, lambda: False)
    result = await executor.run({'document': _bad_json_then_handler('autoflow-v2')})
    assert result == {'status': 'succeeded', 'error': None}
    assert executor.context.variables['handled'] == 'yes'


@pytest.mark.asyncio
async def test_legacy_handled_failure_keeps_failing_the_batch_task():
    async def emit(*_event):
        return None

    executor = ProjectGraphExecutor(None, {}, emit, lambda: False)
    result = await executor.run({'document': _bad_json_then_handler()})
    assert result['status'] == 'failed'
    assert executor.context.variables['handled'] == 'yes'
```

- [ ] **Step 2: 运行，确认失败**

Run: `uv run --directory apps/backend pytest -q tests/unit/workflows/test_handled_failure_semantics.py tests/unit/test_project_graph_failure_reason.py`
Expected: FAIL，`ImportError: cannot import name 'ERROR_SEMANTICS_V2'`。

- [ ] **Step 3: 运行时实现**

`apps/backend/src/autoflow/application/workflows/runtime.py`：

```diff
diff --git a/apps/backend/src/autoflow/application/workflows/runtime.py b/apps/backend/src/autoflow/application/workflows/runtime.py
--- a/apps/backend/src/autoflow/application/workflows/runtime.py
+++ b/apps/backend/src/autoflow/application/workflows/runtime.py
@@ -90,6 +90,18 @@ class WorkflowRuntimeResult:
     issues: tuple[WorkflowScopeIssue, ...] = ()
     failed_node_id: str | None = None
     node_result: ModuleResult | None = None
+    handled_failure_node_ids: tuple[str, ...] = ()
+
+
+ERROR_SEMANTICS_WEBRPA = "webrpa"
+ERROR_SEMANTICS_V2 = "autoflow-v2"
+
+
+def document_error_semantics(document: Mapping[str, Any]) -> str:
+    """Documents without the explicit v2 marker keep the WebRPA semantics."""
+    if document.get("executionSemantics") == ERROR_SEMANTICS_V2:
+        return ERROR_SEMANTICS_V2
+    return ERROR_SEMANTICS_WEBRPA
 
 
 class WorkflowRuntime:
@@ -159,6 +171,7 @@ class WorkflowRuntime:
         *,
         start_node_id: str | None = None,
         detached: bool = False,
+        error_semantics: str | None = None,
     ) -> WorkflowRuntimeResult:
         issues = self.preflight(document)
         if issues:
@@ -177,7 +190,12 @@ class WorkflowRuntime:
         # background pauses cannot change the caller's action duration.
         token = _node_timings.set(()) if detached else None
         try:
-            return await _WorkflowScheduler(self._registry, graph, context).run(
+            return await _WorkflowScheduler(
+                self._registry,
+                graph,
+                context,
+                error_semantics=error_semantics or document_error_semantics(document),
+            ).run(
                 [start_node_id] if start_node_id is not None else None
             )
         finally:
@@ -259,6 +277,8 @@ class _WorkflowScheduler:
     halted: bool = False
     failed_node_id: str | None = None
     failed_result: ModuleResult | None = None
+    error_semantics: str = ERROR_SEMANTICS_WEBRPA
+    handled_failure_node_ids: list[str] = field(default_factory=list)
     loop_local_restores: dict[int, dict[str, tuple[bool, Any, bool]]] = field(
         default_factory=dict
     )
@@ -272,6 +292,7 @@ class _WorkflowScheduler:
             executed_node_ids=tuple(self.executed_order),
             failed_node_id=self.failed_node_id,
             node_result=self.failed_result,
+            handled_failure_node_ids=tuple(self.handled_failure_node_ids),
         )
 
     async def _execute_parallel(self, node_ids: list[str]) -> None:
@@ -330,12 +351,17 @@ class _WorkflowScheduler:
             self.executed_order.append(node_id)
 
         if not result.success:
-            self._remember_failure(node_id, result)
             error_nodes = self.graph.get_error_nodes(node_id)
-            if error_nodes:
-                await self._execute_parallel(error_nodes)
-            else:
+            if not error_nodes:
+                self._remember_failure(node_id, result)
                 self.halted = True
+                return
+            if self.error_semantics == ERROR_SEMANTICS_V2:
+                # Spec M1 R1-05: a failure caught by an error edge is handled.
+                self.handled_failure_node_ids.append(node_id)
+            else:
+                self._remember_failure(node_id, result)
+            await self._execute_parallel(error_nodes)
             return
         if self.halted or self.context.project_end.accepted or self.context.stop_workflow:
             return
```

- [ ] **Step 4: 项目 worker 在文档被改写前读取语义**

`providers/browser/project_graph.py`：import 块改为

```python
from autoflow.application.workflows.runtime import (
    ERROR_SEMANTICS_WEBRPA,
    WorkflowRuntime,
    document_error_semantics,
    execution_context_snapshot,
)
```

在 `run()` 中 `self.graph_adapter = isinstance(document, dict)` 之后加一行：

```python
        semantics = document_error_semantics(document) if isinstance(document, dict) else ERROR_SEMANTICS_WEBRPA
```

并把 `result = await WorkflowRuntime(registry).execute(document, self.context)` 改为：

```python
        result = await WorkflowRuntime(registry).execute(document, self.context, error_semantics=semantics)
```

（`canvas_subflows.top_level_document()` 会重建文档，所以语义必须在它之前读取。）

- [ ] **Step 5: 保存与运行快照保留该字段**

`apps/backend/src/autoflow/domain/workflows/validation.py`：

```diff
diff --git a/apps/backend/src/autoflow/domain/workflows/validation.py b/apps/backend/src/autoflow/domain/workflows/validation.py
--- a/apps/backend/src/autoflow/domain/workflows/validation.py
+++ b/apps/backend/src/autoflow/domain/workflows/validation.py
@@ -239,7 +239,7 @@ def project_document(value: object) -> dict[str, Any]:
         "content": {
             "id": content["id"],
             "name": content["name"],
-            **{key: deepcopy(content[key]) for key in ("schemaVersion", "projectId", "browserEnvironmentVersion", "traceMode") if key in content},
+            **{key: deepcopy(content[key]) for key in ("schemaVersion", "projectId", "browserEnvironmentVersion", "traceMode", "executionSemantics") if key in content},
             "nodes": projected_nodes,
             "edges": projected_edges,
             "variables": projected_variables,
```

- [ ] **Step 6: 运行**

Run: `uv run --directory apps/backend pytest -q tests/unit/workflows tests/unit/test_project_graph_failure_reason.py tests/unit/test_project_graph_executor.py tests/differential/workflows/test_b3_control_flow_runtime_contract.py tests/contract/test_workflow_runs_api.py tests/contract/test_local_workflows.py`
Expected: 全部通过（B3 对照测试不改：它的文档没有标记，验证的是旧语义）。

- [ ] **Step 7: 提交**

```bash
git add apps/backend/src/autoflow/application/workflows/runtime.py apps/backend/src/autoflow/providers/browser/project_graph.py apps/backend/src/autoflow/domain/workflows/validation.py apps/backend/tests/unit/workflows/test_handled_failure_semantics.py apps/backend/tests/unit/test_project_graph_failure_reason.py
git commit -m "feat(runtime): v2 出错语义——错误分支接住的失败不决定运行结果"
```

---

### Task 4: 已处理的失败不算失败——Studio（R1-06）

**Files:**
- Modify: `apps/desktop/src/renderer/domains/workflows/types/workflow.ts`
- Modify: `apps/desktop/src/renderer/domains/workflows/editor-store.ts`
- Modify: `apps/desktop/src/renderer/domains/workflows/components/Toolbar.tsx`（运行文档）
- Modify: `apps/desktop/src/renderer/domains/workflows/components/WorkflowEditor.tsx`（挂载提示条）
- Create: `apps/desktop/src/renderer/domains/workflows/components/ExecutionSemanticsBanner.tsx`
- Test: `apps/desktop/src/renderer/domains/workflows/tests/execution-semantics.test.tsx`

**Interfaces:**
- Consumes: 后端接受 `executionSemantics: "autoflow-v2"`（Task 3）。
- Produces: `ExecutionSemantics` 类型、`EXECUTION_SEMANTICS_V2`；store 字段 `executionSemantics?: ExecutionSemantics` 与动作 `upgradeExecutionSemantics()`；`<ExecutionSemanticsBanner />`。

- [ ] **Step 1: 写失败的测试**

`apps/desktop/src/renderer/domains/workflows/tests/execution-semantics.test.tsx`：

```tsx
import '@testing-library/jest-dom/vitest'
import { act, cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, beforeEach, expect, it } from 'vitest'
import { ExecutionSemanticsBanner } from '../components/ExecutionSemanticsBanner'
import { useWorkflowStore as store } from '../editor-store'

beforeEach(() => store.getState().clearWorkflow())
afterEach(cleanup)

const legacyDocument = {
  id: 'legacy', name: '旧流程',
  nodes: [
    { id: 'a', type: 'moduleNode', position: { x: 0, y: 0 }, data: { moduleType: 'click_element', label: '点击', selector: '#a' } },
    { id: 'b', type: 'moduleNode', position: { x: 0, y: 100 }, data: { moduleType: 'close_page', label: '关闭' } },
  ],
  edges: [{ id: 'e', source: 'a', target: 'b', sourceHandle: 'error' }],
  variables: [],
}

it('new workflows are saved with the v2 error semantics', () => {
  expect(JSON.parse(store.getState().exportWorkflow()).executionSemantics).toBe('autoflow-v2')
})

it('imported documents keep their semantics and legacy ones with error edges offer an upgrade', () => {
  act(() => { expect(store.getState().importWorkflow(legacyDocument)).toBe(true) })
  expect(JSON.parse(store.getState().exportWorkflow()).executionSemantics).toBeUndefined()
  render(<ExecutionSemanticsBanner />)
  fireEvent.click(screen.getByRole('button', { name: '改用新规则' }))
  expect(store.getState().hasUnsavedChanges).toBe(true)
  expect(JSON.parse(store.getState().exportWorkflow()).executionSemantics).toBe('autoflow-v2')
  expect(screen.queryByRole('status')).toBeNull()
})

it('legacy documents without error edges show no banner', () => {
  act(() => { store.getState().importWorkflow({ ...legacyDocument, edges: [{ id: 'e', source: 'a', target: 'b' }] }) })
  render(<ExecutionSemanticsBanner />)
  expect(screen.queryByRole('status')).toBeNull()
})
```

- [ ] **Step 2: 运行，确认失败**

Run: `npm --workspace @autoflow/desktop test -- src/renderer/domains/workflows/tests/execution-semantics.test.tsx`
Expected: FAIL，找不到 `../components/ExecutionSemanticsBanner`。

- [ ] **Step 3: 类型与 store**

`apps/desktop/src/renderer/domains/workflows/types/workflow.ts`：

```diff
diff --git a/apps/desktop/src/renderer/domains/workflows/types/workflow.ts b/apps/desktop/src/renderer/domains/workflows/types/workflow.ts
--- a/apps/desktop/src/renderer/domains/workflows/types/workflow.ts
+++ b/apps/desktop/src/renderer/domains/workflows/types/workflow.ts
@@ -711,6 +712,9 @@ export type BrowserEnvironment =
   | {source:'inputEnvironment';inputId:string}
 
 export type TraceMode = 'off' | 'standard' | 'enhanced'
+// Remediation M1 R1-05: absent means the imported WebRPA semantics (a handled failure still fails the run).
+export type ExecutionSemantics = 'autoflow-v2'
+export const EXECUTION_SEMANTICS_V2: ExecutionSemantics = 'autoflow-v2'
 
 export interface Workflow {
   traceMode?: TraceMode
```

`apps/desktop/src/renderer/domains/workflows/editor-store.ts`：

```diff
diff --git a/apps/desktop/src/renderer/domains/workflows/editor-store.ts b/apps/desktop/src/renderer/domains/workflows/editor-store.ts
--- a/apps/desktop/src/renderer/domains/workflows/editor-store.ts
+++ b/apps/desktop/src/renderer/domains/workflows/editor-store.ts
@@ -1,6 +1,7 @@
 // Source: WebRPA@5ccb900e, store/workflowStore.ts; see SOURCE.md for license and adaptation boundaries.
 import { create } from 'zustand'
-import type { BrowserEnvironment, TraceMode } from './types/workflow'
+import type { BrowserEnvironment, ExecutionSemantics, TraceMode } from './types/workflow'
+import { EXECUTION_SEMANTICS_V2 } from './types/workflow'
 import { nanoid } from 'nanoid'
 import type { Node, Edge, Connection, NodeChange, EdgeChange } from '@xyflow/react'
 import { applyNodeChanges, applyEdgeChanges, addEdge } from '@xyflow/react'
@@ -244,6 +245,8 @@ export type DataRow = Record<string, unknown>
 interface WorkflowState {
   traceMode?: TraceMode
   setTraceMode: (mode: TraceMode) => void
+  executionSemantics?: ExecutionSemantics
+  upgradeExecutionSemantics: () => void
   browserEnvironmentVersion: number | undefined
   migrateBrowserEnvironment(nodeId:string, configuration:BrowserEnvironment): void
   // 工作流基本信息
@@ -396,7 +399,7 @@ interface WorkflowState {
   setWorkflowName: (name: string) => void
   setWorkflowNameWithHistory: (name: string) => void  // 设置名称并保存历史
   clearWorkflow: () => void
-  loadWorkflow: (workflow: { traceMode?: TraceMode; browserEnvironmentVersion?: number; nodes: Node<NodeData>[]; edges: Edge[]; name: string; variables?: Variable[] }) => void
+  loadWorkflow: (workflow: { traceMode?: TraceMode; executionSemantics?: string; browserEnvironmentVersion?: number; nodes: Node<NodeData>[]; edges: Edge[]; name: string; variables?: Variable[] }) => void
   // 回滚：把画布完整恢复到某个快照（含节点、连线、名称、全局变量）
   restoreSnapshot: (snapshot: { traceMode?: TraceMode; browserEnvironmentVersion?: number; nodes: Node<NodeData>[]; edges: Edge[]; name?: string; variables?: Variable[] }, options?: { resetHistory?: boolean }) => void
   
@@ -1444,6 +1449,7 @@ export const useWorkflowStore = create<WorkflowState>((set, get) => ({
   id: nanoid(),
   name: '未命名工作流',
   traceMode: undefined,
+  executionSemantics: EXECUTION_SEMANTICS_V2,
   browserEnvironmentVersion: 1,
   nodes: [],
   edges: [],
@@ -3235,6 +3241,11 @@ export const useWorkflowStore = create<WorkflowState>((set, get) => ({
     set({ traceMode: mode, hasUnsavedChanges: true })
   },
 
+  upgradeExecutionSemantics: () => {
+    if (get().executionSemantics === EXECUTION_SEMANTICS_V2) return
+    set({ executionSemantics: EXECUTION_SEMANTICS_V2, hasUnsavedChanges: true })
+  },
+
   setWorkflowName: (name) => {
     if (get().name !== name) set({ name, hasUnsavedChanges: true })
   },
@@ -3262,6 +3273,7 @@ export const useWorkflowStore = create<WorkflowState>((set, get) => ({
       id: nanoid(),
       name: '未命名工作流',
       traceMode: undefined,
+      executionSemantics: EXECUTION_SEMANTICS_V2,
       browserEnvironmentVersion: 1,
       nodes: [],
       edges: [],
@@ -3298,6 +3310,7 @@ export const useWorkflowStore = create<WorkflowState>((set, get) => ({
       name: workflow.name,
       browserEnvironmentVersion: workflow.browserEnvironmentVersion,
       traceMode: workflow.traceMode,
+      executionSemantics: workflow.executionSemantics === EXECUTION_SEMANTICS_V2 ? EXECUTION_SEMANTICS_V2 : undefined,
       variables: structuredClone(workflow.variables ?? []),
       selectedNodeId: null,
       clipboard: [],
@@ -3372,6 +3385,7 @@ export const useWorkflowStore = create<WorkflowState>((set, get) => ({
       name: state.name,
       browserEnvironmentVersion: state.browserEnvironmentVersion,
       traceMode: state.traceMode,
+      ...(state.executionSemantics ? { executionSemantics: state.executionSemantics } : {}),
       nodes: convertedNodes,
       edges: state.edges,
       variables: state.variables,
@@ -3446,6 +3460,7 @@ export const useWorkflowStore = create<WorkflowState>((set, get) => ({
         name: workflow.name || '导入的工作流',
         browserEnvironmentVersion: workflow.browserEnvironmentVersion,
         traceMode: workflow.traceMode,
+        executionSemantics: workflow.executionSemantics === EXECUTION_SEMANTICS_V2 ? EXECUTION_SEMANTICS_V2 : undefined,
         nodes: safeNodes,
         edges: safeEdges,
         variables: importedVariables,  // 恢复变量
```

- [ ] **Step 4: 提示条组件**

`apps/desktop/src/renderer/domains/workflows/components/ExecutionSemanticsBanner.tsx`：

```tsx
import { useWorkflowStore } from '../editor-store'
import { EXECUTION_SEMANTICS_V2 } from '../types/workflow'

// Remediation M1 R1-06: old documents keep WebRPA error semantics until the user switches.
export function ExecutionSemanticsBanner() {
  const legacy = useWorkflowStore(state => state.executionSemantics !== EXECUTION_SEMANTICS_V2)
  const hasErrorEdges = useWorkflowStore(state => state.edges.some(edge => edge.sourceHandle === 'error'))
  const upgrade = useWorkflowStore(state => state.upgradeExecutionSemantics)
  if (!legacy || !hasErrorEdges) return null
  return (
    <div role="status" className="absolute left-1/2 top-3 z-10 flex -translate-x-1/2 items-center gap-3 rounded-control border border-line bg-surface px-3 py-2 text-sm text-ink shadow-sm">
      <span>这个流程沿用旧的出错规则：错误分支处理后仍算失败。</span>
      <button type="button" className="font-medium text-clay" onClick={upgrade}>改用新规则</button>
    </div>
  )
}
```

在 `components/WorkflowEditor.tsx` 顶部 import 区加入 `import { ExecutionSemanticsBanner } from './ExecutionSemanticsBanner'`，并在 `{/* 模块条视图：覆盖在画布之上（流程图保持挂载以维持实例与状态） */}` 之前插入：

```tsx
          {/* 整改 M1 R1-06：旧出错规则提示 */}
          <ExecutionSemanticsBanner />

```

- [ ] **Step 5: Studio 运行时把语义带给后端**

`components/Toolbar.tsx` 的 `executeWorkflow` 中构造 `document` 时，在 `browserEnvironmentVersion: 1,` 之后加：

```tsx
        ...(source.executionSemantics ? { executionSemantics: source.executionSemantics } : {}),
```

- [ ] **Step 6: 运行**

Run: `npm --workspace @autoflow/desktop test -- src/renderer/domains/workflows/tests/execution-semantics.test.tsx src/renderer/domains/workflows/tests/run-start-boundary.test.tsx src/renderer/domains/workflows/tests/common-advanced-config.test.tsx`
Expected: 全部通过。
Run: `npm run typecheck`
Expected: 无错误。

- [ ] **Step 7: 提交**

```bash
git add apps/desktop/src/renderer/domains/workflows/types/workflow.ts apps/desktop/src/renderer/domains/workflows/editor-store.ts apps/desktop/src/renderer/domains/workflows/components/Toolbar.tsx apps/desktop/src/renderer/domains/workflows/components/WorkflowEditor.tsx apps/desktop/src/renderer/domains/workflows/components/ExecutionSemanticsBanner.tsx apps/desktop/src/renderer/domains/workflows/tests/execution-semantics.test.tsx
git commit -m "feat(studio): 新建流程使用 v2 出错语义，旧流程可一键切换"
```

---

### Task 5: 未生效设置——后端报告（R1-02、R1-17）

**Files:**
- Create: `apps/backend/src/autoflow/domain/workflows/inert_settings.py`
- Modify: `apps/backend/src/autoflow/providers/browser/project_graph.py`
- Test: `apps/backend/tests/unit/workflows/test_inert_settings.py`
- Test: `apps/backend/tests/unit/test_project_graph_failure_reason.py`（追加）

**Interfaces:**
- Produces: `inert_settings.INERT_SETTING_KEYS`、`inert_keys(data: Mapping, module_type: str) -> list[str]`、`describe_inert_keys(label: str, keys: list[str]) -> str`。与 Task 6 的前端 `lib/inertSettings.ts` 保持同一键列表（测试互相对照，Task 6 之后该对照测试才能通过——见 Step 2）。

- [ ] **Step 1: 写失败的测试**

`apps/backend/tests/unit/workflows/test_inert_settings.py`：

```python
"""Remediation M1 R1-02: backend and Studio agree on which saved settings are inert."""

import re
from pathlib import Path

from autoflow.domain.workflows.inert_settings import INERT_SETTING_KEYS, describe_inert_keys, inert_keys

FRONTEND = Path(__file__).parents[5] / "apps/desktop/src/renderer/domains/workflows/lib/inertSettings.ts"


def test_rules_report_only_settings_that_would_have_changed_behaviour():
    assert inert_keys({"retryCount": 2, "retryDelay": 1, "timeoutAction": "retry"}, "click_element") == [
        "retryCount", "retryDelay", "timeoutAction",
    ]
    assert inert_keys({"retryCount": 0, "retryDelay": 5, "timeoutAction": "stop", "errorPolicy": {"mode": "stop"}}, "click_element") == []
    assert inert_keys({"config": {"onTimeout": "skip", "errorPolicy": {"mode": "continue"}}}, "loop") == ["errorPolicy", "onTimeout"]
    assert inert_keys({"onTimeout": "skip"}, "open_page") == []
    assert inert_keys({"retryCount": "{n}"}, "click_element") == []


def test_description_names_the_node_and_settings():
    assert describe_inert_keys("点击提交", ["retryCount", "timeoutAction"]) == "「点击提交」的以下设置尚未生效，运行时会被忽略：重试次数、运行超时后"


def test_frontend_mirror_lists_the_same_keys():
    declared = re.search(r"INERT_SETTING_KEYS = \[(.*?)\] as const", FRONTEND.read_text(encoding="utf-8")).group(1)
    assert tuple(re.findall(r"'(\w+)'", declared)) == INERT_SETTING_KEYS
```

向 `tests/unit/test_project_graph_failure_reason.py` 追加：

```python
@pytest.mark.asyncio
async def test_inert_retry_settings_are_reported_once_per_node():
    events = []

    async def emit(*event):
        events.append(event)

    executor = ProjectGraphExecutor(None, {}, emit, lambda: False)
    document = {
        'nodes': [
            node('loop', 'loop', count=2, indexVariable='i'),
            node('set', 'set_variable', variableName='x', variableValue='{i}', label='赋值', retryCount=3, timeoutAction='skip'),
        ],
        'edges': [{'id': 'e', 'source': 'loop', 'target': 'set', 'sourceHandle': 'loop'}],
    }
    assert (await executor.run({'document': document}))['status'] == 'succeeded'
    warnings = [event[3]['message'] for event in events if event[0] == 'log' and event[3].get('level') == 'warning']
    assert warnings == ['「赋值」的以下设置尚未生效，运行时会被忽略：重试次数、运行超时后']
```

- [ ] **Step 2: 运行，确认失败**

Run: `uv run --directory apps/backend pytest -q tests/unit/workflows/test_inert_settings.py tests/unit/test_project_graph_failure_reason.py`
Expected: FAIL，`ModuleNotFoundError: autoflow.domain.workflows.inert_settings`。（`test_frontend_mirror_lists_the_same_keys` 在 Task 6 创建前端文件之前会一直失败，这是预期的交叉检查。）

- [ ] **Step 3: 实现规则模块**

`apps/backend/src/autoflow/domain/workflows/inert_settings.py`：

```python
"""Settings the Studio saves but the runtime does not execute yet (remediation M1, R1-02 / spec §5.1).

Mirrors apps/desktop/src/renderer/domains/workflows/lib/inertSettings.ts; M2 replaces both with the
real node error policy.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

INERT_SETTING_KEYS = (
    "errorPolicy", "retryCount", "retryDelay", "retryBackoff",
    "retryExhaustedAction", "timeoutAction", "onTimeout",
)
LOOP_TYPES = frozenset({"loop", "foreach", "foreach_dict", "infinite_loop"})
LABELS = {
    "errorPolicy": "出错时", "retryCount": "重试次数", "retryDelay": "重试间隔",
    "retryBackoff": "退避策略", "retryExhaustedAction": "重试耗尽后",
    "timeoutAction": "运行超时后", "onTimeout": "循环超时后",
}


def inert_keys(data: Mapping[str, Any], module_type: str) -> list[str]:
    nested = data.get("config")
    config = {**data, **nested} if isinstance(nested, Mapping) else dict(data)
    keys: list[str] = []
    policy = config.get("errorPolicy")
    if isinstance(policy, Mapping) and policy.get("mode") not in (None, "stop"):
        keys.append("errorPolicy")
    try:
        retry_count = float(config.get("retryCount") or 0)
    except (TypeError, ValueError):
        retry_count = 0
    if retry_count > 0:
        keys.append("retryCount")
        keys.extend(
            key for key in ("retryDelay", "retryBackoff", "retryExhaustedAction")
            if config.get(key) not in (None, "")
        )
    if config.get("timeoutAction") in ("retry", "skip"):
        keys.append("timeoutAction")
    if module_type in LOOP_TYPES and config.get("onTimeout") in ("retry", "skip"):
        keys.append("onTimeout")
    return keys


def describe_inert_keys(label: str, keys: list[str]) -> str:
    return f"「{label}」的以下设置尚未生效，运行时会被忽略：{'、'.join(LABELS[key] for key in keys)}"
```

- [ ] **Step 4: 节点首次开始时报告**

`providers/browser/project_graph.py`：
1. 在 `from autoflow.domain.workflows.execution import (...)` 块之后加 `from autoflow.domain.workflows.inert_settings import describe_inert_keys, inert_keys`。
2. `__init__` 中 `self.manual_outcome: str | None = None` 之后加 `self.inert_reported: set[str] = set()`。
3. `publish()` 的 `execution:node_start` 分支中，把

```python
            await emit('log', {'level': 'info', 'message': '开始执行节点'})
            self.cancellation.raise_if_cancelled()
            return
```

替换为

```python
            await emit('log', {'level': 'info', 'message': '开始执行节点'})
            inert = inert_keys(node_data, str(module_type or '')) if node_id not in self.inert_reported else []
            if inert:
                # Spec M1 R1-02: say once per node that saved retry / timeout settings are ignored.
                self.inert_reported.add(node_id)
                await emit('log', {'level': 'warning', 'message': describe_inert_keys(str(node_data.get('label') or module_type or node_id), inert)})
            self.cancellation.raise_if_cancelled()
            return
```

- [ ] **Step 5: 运行**

Run: `uv run --directory apps/backend pytest -q tests/unit/workflows/test_inert_settings.py tests/unit/test_project_graph_failure_reason.py -k "not frontend_mirror"`
Expected: 通过。

- [ ] **Step 6: 提交**

```bash
git add apps/backend/src/autoflow/domain/workflows/inert_settings.py apps/backend/src/autoflow/providers/browser/project_graph.py apps/backend/tests/unit/workflows/test_inert_settings.py apps/backend/tests/unit/test_project_graph_failure_reason.py
git commit -m "feat(runs): 批量运行日志提示尚未生效的重试与超时设置"
```

---

### Task 6: 未生效设置——Studio 隐藏与预检（R1-01、R1-02）

**Files:**
- Create: `apps/desktop/src/renderer/domains/workflows/lib/featureFlags.ts`
- Create: `apps/desktop/src/renderer/domains/workflows/lib/inertSettings.ts`
- Modify: `components/ConfigPanel.tsx`、`components/BlockFlowView.tsx`、`components/WorkflowEditor.tsx`、`components/config-panels/ControlModuleConfigs.tsx`、`components/Toolbar.tsx`（均在 `apps/desktop/src/renderer/domains/workflows/` 下）
- Modify: `tests/common-advanced-config.test.tsx`（显式打开开关，保留对隐藏控件的覆盖，供 M2 复用）
- Test: `tests/inert-settings.test.tsx`、`tests/run-start-boundary.test.tsx`（追加）

**Interfaces:**
- Produces: `featureFlags.nodeRetryPolicy: boolean`（默认 false，M2 删除）；`INERT_SETTING_KEYS`、`inertKeys(data, moduleType)`、`findInertSettings(nodes) -> InertNodeSettings[]`、`describeInertSettings(found) -> string`。

- [ ] **Step 1: 写失败的测试**

`apps/desktop/src/renderer/domains/workflows/tests/inert-settings.test.tsx`：

```tsx
import '@testing-library/jest-dom/vitest'
import { cleanup, render, screen } from '@testing-library/react'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
vi.hoisted(() => {
  const values = new Map<string, string>()
  vi.stubGlobal('localStorage', { getItem: (k: string) => values.get(k) ?? null, setItem: (k: string, v: string) => values.set(k, v), removeItem: (k: string) => values.delete(k) })
  Object.defineProperty(window, 'innerWidth', { configurable: true, value: 1440 })
})
import { ConfigPanel } from '../components/ConfigPanel'
import { useWorkflowStore as store } from '../editor-store'
import { featureFlags } from '../lib/featureFlags'
import { describeInertSettings, findInertSettings } from '../lib/inertSettings'

Element.prototype.scrollIntoView = vi.fn()
beforeEach(() => { featureFlags.nodeRetryPolicy = false; store.getState().clearWorkflow() })
afterEach(cleanup)

it('hides retry, error policy and timeout actions by default but keeps the timeout itself', () => {
  store.getState().addNode('close_page', { x: 0, y: 0 })
  const id = store.getState().nodes[0].id
  store.getState().updateNodeData(id, { retryCount: 3, timeoutAction: 'skip', errorPolicy: { mode: 'retry-self', maxRetries: 2, interval: 0, onExhausted: 'stop' } })
  render(<ConfigPanel selectedNodeId={id} />)
  expect(screen.getByText('超时时间 (秒)')).toBeInTheDocument()
  for (const label of ['出错时', '运行超时后', '重试次数', '重试耗尽后', '重试间隔（秒）', '退避策略']) expect(screen.queryByText(label)).toBeNull()
  const saved = JSON.parse(store.getState().exportWorkflow()).nodes[0].data
  expect(saved).toMatchObject({ retryCount: 3, timeoutAction: 'skip', errorPolicy: { mode: 'retry-self' } })
})

it('reports only settings that would have changed behaviour', () => {
  const found = findInertSettings([
    { id: 'a', data: { moduleType: 'click_element', label: '点击提交', retryCount: 2, retryDelay: 1, timeoutAction: 'retry' } },
    { id: 'b', data: { moduleType: 'click_element', retryCount: 0, retryDelay: 5, timeoutAction: 'stop', errorPolicy: { mode: 'stop' } } },
    { id: 'c', data: { moduleType: 'loop', config: { onTimeout: 'skip', errorPolicy: { mode: 'continue' } } } },
    { id: 'd', data: { moduleType: 'open_page', onTimeout: 'skip' } },
  ])
  expect(found).toEqual([
    { nodeId: 'a', label: '点击提交', keys: ['retryCount', 'retryDelay', 'timeoutAction'] },
    { nodeId: 'c', label: 'loop', keys: ['errorPolicy', 'onTimeout'] },
  ])
  expect(describeInertSettings(found)).toBe('以下设置尚未生效，运行时会被忽略：「点击提交」重试次数、重试间隔、运行超时后；「loop」出错时、循环超时后')
})
```

向 `tests/run-start-boundary.test.tsx` 末尾追加：

```tsx
it('warns about saved retry settings that do not run yet and still starts with v2 error semantics (remediation M1)', async () => {
  const nodeId = store.getState().nodes[0].id
  store.getState().updateNodeData(nodeId, { label: '打开首页', retryCount: 2 })
  render(<Toolbar />)
  fireEvent.keyDown(window, { key: 'F5' })
  await waitFor(() => expect(workflowApi.execute).toHaveBeenCalledTimes(1))
  expect(store.getState().logs.some(log => log.level === 'warning' && log.message === '以下设置尚未生效，运行时会被忽略：「打开首页」重试次数')).toBe(true)
  expect(workflowApi.execute).toHaveBeenCalledWith(store.getState().id, expect.objectContaining({
    document: expect.objectContaining({ executionSemantics: 'autoflow-v2' }),
  }))
})
```

- [ ] **Step 2: 运行，确认失败**

Run: `npm --workspace @autoflow/desktop test -- src/renderer/domains/workflows/tests/inert-settings.test.tsx`
Expected: FAIL，找不到 `../lib/featureFlags`。

- [ ] **Step 3: 开关与规则**

`apps/desktop/src/renderer/domains/workflows/lib/featureFlags.ts`：

```ts
// Remediation M1 R1-01: settings the backend does not execute yet stay hidden until M2 implements them.
// Mutable so tests of the preserved (hidden) controls can switch them on explicitly.
export const featureFlags = {
  nodeRetryPolicy: false,
}
```

`apps/desktop/src/renderer/domains/workflows/lib/inertSettings.ts`：

```ts
// Remediation M1 R1-02 / spec §5.1. Mirrors apps/backend/src/autoflow/domain/workflows/inert_settings.py.
export const INERT_SETTING_KEYS = ['errorPolicy', 'retryCount', 'retryDelay', 'retryBackoff', 'retryExhaustedAction', 'timeoutAction', 'onTimeout'] as const
export type InertSettingKey = typeof INERT_SETTING_KEYS[number]
export type InertNodeSettings = { nodeId: string; label: string; keys: InertSettingKey[] }

const LOOP_TYPES = new Set(['loop', 'foreach', 'foreach_dict', 'infinite_loop'])
type Record_ = Record<string, unknown>
const isRecord = (value: unknown): value is Record_ => typeof value === 'object' && value !== null && !Array.isArray(value)

export function inertKeys(data: Record_, moduleType: string): InertSettingKey[] {
  const config = isRecord(data.config) ? { ...data, ...data.config } : data
  const keys: InertSettingKey[] = []
  const policy = config.errorPolicy
  if (isRecord(policy) && policy.mode !== undefined && policy.mode !== 'stop') keys.push('errorPolicy')
  const retryCount = Number(config.retryCount)
  if (Number.isFinite(retryCount) && retryCount > 0) {
    keys.push('retryCount')
    for (const key of ['retryDelay', 'retryBackoff', 'retryExhaustedAction'] as const) if (config[key] !== undefined && config[key] !== '') keys.push(key)
  }
  if (config.timeoutAction === 'retry' || config.timeoutAction === 'skip') keys.push('timeoutAction')
  if (LOOP_TYPES.has(moduleType) && (config.onTimeout === 'retry' || config.onTimeout === 'skip')) keys.push('onTimeout')
  return keys
}

export function findInertSettings(nodes: readonly { id: string; data?: unknown }[]): InertNodeSettings[] {
  return nodes.flatMap(node => {
    if (!isRecord(node.data)) return []
    const moduleType = String(node.data.moduleType ?? '')
    const keys = inertKeys(node.data, moduleType)
    return keys.length ? [{ nodeId: node.id, label: String(node.data.label || moduleType || node.id), keys }] : []
  })
}

const LABELS: Record<InertSettingKey, string> = {
  errorPolicy: '出错时', retryCount: '重试次数', retryDelay: '重试间隔', retryBackoff: '退避策略',
  retryExhaustedAction: '重试耗尽后', timeoutAction: '运行超时后', onTimeout: '循环超时后',
}

export function describeInertSettings(found: InertNodeSettings[]): string {
  return `以下设置尚未生效，运行时会被忽略：${found.map(item => `「${item.label}」${item.keys.map(key => LABELS[key]).join('、')}`).join('；')}`
}
```

- [ ] **Step 4: 隐藏控件**

`apps/desktop/src/renderer/domains/workflows/components/ConfigPanel.tsx`：

```diff
diff --git a/apps/desktop/src/renderer/domains/workflows/components/ConfigPanel.tsx b/apps/desktop/src/renderer/domains/workflows/components/ConfigPanel.tsx
--- a/apps/desktop/src/renderer/domains/workflows/components/ConfigPanel.tsx
+++ b/apps/desktop/src/renderer/domains/workflows/components/ConfigPanel.tsx
@@ -4,6 +4,7 @@ import { ProjectLifecycleConfig } from './config-panels/ProjectLifecycleConfig'
 import { ProjectDataConfig } from './config-panels/ProjectDataConfig'
 import { ProxyControlConfig } from './config-panels/ProxyControlConfig'
 import { excludedModuleTypes } from '../lib/moduleCatalog'
+import { featureFlags } from '../lib/featureFlags'
 // Source: WebRPA@5ccb900e, components/workflow/ConfigPanel.tsx; see SOURCE.md for license and adaptation boundaries.
 import { useWorkflowStore, moduleTypeLabels, getModuleDefaultTimeout, getNodeConfigData, type NodeData, type ErrorPolicy } from '../editor-store'
 import { useGlobalConfigStore } from '../hooks/stores/globalConfigStore'
@@ -1603,8 +1606,8 @@ export function ConfigPanel({ selectedNodeId: propSelectedNodeId }: ConfigPanelP
                 {/* 模块特定配置 */}
                 {renderModuleConfig()}
 
-                {/* 错误处理（错误回流 / 重试 / 跳过）——与模块条视图共用同一份 errorPolicy */}
-                {(() => {
+                {/* 错误处理（错误回流 / 重试 / 跳过）——与模块条视图共用同一份 errorPolicy；M2 实现前隐藏（M1 R1-01） */}
+                {featureFlags.nodeRetryPolicy && (() => {
                   const pol: ErrorPolicy = (nodeData.errorPolicy as ErrorPolicy) || { mode: 'stop', maxRetries: 1, interval: 0, onExhausted: 'stop' }
                   const setPol = (patch: Partial<ErrorPolicy>) => {
                     const next: ErrorPolicy = { maxRetries: 1, interval: 0, onExhausted: 'stop', ...pol, ...patch }
@@ -1687,7 +1690,7 @@ export function ConfigPanel({ selectedNodeId: propSelectedNodeId }: ConfigPanelP
                       0 表示不限制超时，当前模块建议: {(getModuleDefaultTimeout(nodeData.moduleType as import('../types/index').ModuleType) / 1000).toFixed(0)}秒
                     </p>
                   </div>
-                  <div className="space-y-2">
+                  {featureFlags.nodeRetryPolicy && <div className="space-y-2">
                     <Label htmlFor="timeoutAction">运行超时后</Label>
                     <Select
                       id="timeoutAction"
@@ -1705,8 +1708,8 @@ export function ConfigPanel({ selectedNodeId: propSelectedNodeId }: ConfigPanelP
                         ? '超时后立即停止整个工作流执行'
                         : '超时后按重试次数进行重试'}
                     </p>
-                  </div>
-                  <div className="space-y-2">
+                  </div>}
+                  {featureFlags.nodeRetryPolicy && <div className="space-y-2">
                     <Label htmlFor="retryCount">重试次数</Label>
                     <NumberInput
                       id="retryCount"
@@ -1716,8 +1719,8 @@ export function ConfigPanel({ selectedNodeId: propSelectedNodeId }: ConfigPanelP
                       min={0}
                       max={10}
                     />
-                  </div>
-                  {((nodeData.retryCount as number) ?? 0) > 0 && (
+                  </div>}
+                  {featureFlags.nodeRetryPolicy && ((nodeData.retryCount as number) ?? 0) > 0 && (
                     <div className="space-y-2">
                       <Label htmlFor="retryExhaustedAction">重试耗尽后</Label>
                       <Select
@@ -1735,7 +1738,7 @@ export function ConfigPanel({ selectedNodeId: propSelectedNodeId }: ConfigPanelP
                       </p>
                     </div>
                   )}
-                  {((nodeData.retryCount as number) ?? 0) > 0 && (
+                  {featureFlags.nodeRetryPolicy && ((nodeData.retryCount as number) ?? 0) > 0 && (
                     <div className="space-y-2">
                       <Label htmlFor="retryDelay">重试间隔（秒）</Label>
                       <NumberInput
@@ -1750,7 +1753,7 @@ export function ConfigPanel({ selectedNodeId: propSelectedNodeId }: ConfigPanelP
                       </p>
                     </div>
                   )}
-                  {((nodeData.retryCount as number) ?? 0) > 0 && ((nodeData.retryDelay as number) ?? 0) > 0 && (
+                  {featureFlags.nodeRetryPolicy && ((nodeData.retryCount as number) ?? 0) > 0 && ((nodeData.retryDelay as number) ?? 0) > 0 && (
                     <div className="space-y-2">
                       <Label htmlFor="retryBackoff">退避策略</Label>
                       <Select
```

`apps/desktop/src/renderer/domains/workflows/components/BlockFlowView.tsx`：

```diff
diff --git a/apps/desktop/src/renderer/domains/workflows/components/BlockFlowView.tsx b/apps/desktop/src/renderer/domains/workflows/components/BlockFlowView.tsx
--- a/apps/desktop/src/renderer/domains/workflows/components/BlockFlowView.tsx
+++ b/apps/desktop/src/renderer/domains/workflows/components/BlockFlowView.tsx
@@ -23,6 +23,7 @@ import {
 } from './blockFlowModel'
 import { collectNodeVarNames } from '../lib/moduleDefaultVars'
 import { moduleMatchesQuery } from '../lib/pinyin'
+import { featureFlags } from '../lib/featureFlags'
 
 // 模块条复制粘贴的会话级剪贴板（跨组件重渲染保留；存的是已换新 id 的快照，
 // 每次粘贴时再 clone 一次，保证可重复粘贴且 id 不冲突）
@@ -223,7 +224,7 @@ export function BlockFlowView() {
   }
   // 行内徽标摘要（仅在设置了非默认策略时显示）
   const policyText = (p?: ErrorPolicy): string => {
-    if (!p || !p.mode || p.mode === 'stop') return ''
+    if (!featureFlags.nodeRetryPolicy || !p || !p.mode || p.mode === 'stop') return ''
     if (p.mode === 'continue') return '出错跳过'
     if (p.mode === 'retry-self') return `出错重试 ${p.maxRetries ?? 1} 次`
     if (p.mode === 'retry-from') return `出错回流「${p.targetId ? nodeLabel(p.targetId) : '上层'}」×${p.maxRetries ?? 1}`
@@ -595,7 +596,7 @@ export function BlockFlowView() {
           {isCollapsed && childCount ? <span className="text-[10.5px] text-[hsl(var(--slate-400))] flex-shrink-0">· 已折叠 {childCount} 步</span> : null}
         </div>
         <div className="flex basis-full @[32rem]/blocks:basis-auto justify-end items-center gap-0.5 opacity-0 group-hover/row:opacity-100 focus-within:opacity-100 transition-opacity flex-shrink-0">
-          <button
+          {featureFlags.nodeRetryPolicy && <button
             onClick={(e) => {
               e.stopPropagation()
               const r = (e.currentTarget as HTMLElement).getBoundingClientRect()
@@ -603,7 +604,7 @@ export function BlockFlowView() {
             }}
             className={'p-1 rounded-[6px] transition-colors hover:bg-[hsl(var(--warning-500)/0.12)] ' + (policyText(data.errorPolicy as ErrorPolicy) ? 'text-[hsl(var(--warning-600))]' : 'text-[hsl(var(--slate-400))] hover:text-[hsl(var(--warning-600))]')}
             title="出错处理（原地重试 / 回流上层重试 / 跳过继续）"
-          ><RotateCcw className="w-3.5 h-3.5" /></button>
+          ><RotateCcw className="w-3.5 h-3.5" /></button>}
           <button onClick={(e) => { e.stopPropagation(); handleMove(block.id, -1) }} className="p-1 rounded-[6px] text-[hsl(var(--slate-400))] hover:text-[hsl(var(--brand-600))] hover:bg-[hsl(var(--brand-50))] transition-colors" title="上移"><ChevronUp className="w-3.5 h-3.5" /></button>
           <button onClick={(e) => { e.stopPropagation(); handleMove(block.id, 1) }} className="p-1 rounded-[6px] text-[hsl(var(--slate-400))] hover:text-[hsl(var(--brand-600))] hover:bg-[hsl(var(--brand-50))] transition-colors" title="下移"><ChevronDown className="w-3.5 h-3.5" /></button>
           <button onClick={(e) => { e.stopPropagation(); toggleNodesDisabled([node.id]) }} className={'p-1 rounded-[6px] transition-colors hover:bg-[hsl(var(--slate-100))] ' + (disabled ? 'text-[hsl(var(--brand-600))]' : 'text-[hsl(var(--slate-400))] hover:text-[hsl(var(--slate-700))]')} title={disabled ? '启用 (Ctrl+D)' : '禁用 (Ctrl+D)'}><Ban className="w-3.5 h-3.5" /></button>
```

`apps/desktop/src/renderer/domains/workflows/components/config-panels/ControlModuleConfigs.tsx`：

```diff
diff --git a/apps/desktop/src/renderer/domains/workflows/components/config-panels/ControlModuleConfigs.tsx b/apps/desktop/src/renderer/domains/workflows/components/config-panels/ControlModuleConfigs.tsx
--- a/apps/desktop/src/renderer/domains/workflows/components/config-panels/ControlModuleConfigs.tsx
+++ b/apps/desktop/src/renderer/domains/workflows/components/config-panels/ControlModuleConfigs.tsx
@@ -3,6 +3,7 @@ import { Label } from '../controls/label'
 import { VariableInput } from '../controls/variable-input'
 import { SelectNative as Select } from '../controls/select-native'
 import { getNodeConfigData, useWorkflowStore, type NodeData } from '../../editor-store'
+import { featureFlags } from '../../lib/featureFlags'
 
 interface ConfigProps {
   data: NodeData
@@ -283,7 +284,7 @@ export function LoopConfig({ data, onChange }: ConfigProps) {
         </p>
       </div>
       
-      <div className="space-y-2">
+      {featureFlags.nodeRetryPolicy && <div className="space-y-2">
         <Label htmlFor="onTimeout">运行超时后</Label>
         <Select
           id="onTimeout"
@@ -294,7 +295,7 @@ export function LoopConfig({ data, onChange }: ConfigProps) {
           <option value="skip">跳过</option>
           <option value="stop">停止</option>
         </Select>
-      </div>
+      </div>}
     </div>
   )
 }
```

`components/WorkflowEditor.tsx`：import 区加入 `import { featureFlags } from '../lib/featureFlags'`，并把错误回流连线条件

```tsx
                if (p && p.mode === 'retry-from' && p.targetId && nodes.some((t) => t.id === p.targetId)) {
```

改为

```tsx
                if (featureFlags.nodeRetryPolicy && p && p.mode === 'retry-from' && p.targetId && nodes.some((t) => t.id === p.targetId)) {
```

- [ ] **Step 5: 运行前提示**

`components/Toolbar.tsx`：import 区加入 `import { describeInertSettings, findInertSettings } from '../lib/inertSettings'`；在 `executeWorkflow` 里 `clearLogs()` 之后写入"正在准备执行工作流"那条 `addLog(...)` 的下一行加：

```tsx
    // 整改 M1 R1-02：保存过但后端尚未执行的设置，运行前明确提示（不阻止运行）
    const inertSettings = findInertSettings(nodes)
    if (inertSettings.length) addLog({ level: 'warning', message: describeInertSettings(inertSettings) })
```

（必须在 `clearLogs()` 之后，否则提示会被清掉。）

- [ ] **Step 6: 既有高级配置测试显式打开开关**

`apps/desktop/src/renderer/domains/workflows/tests/common-advanced-config.test.tsx`：

```diff
diff --git a/apps/desktop/src/renderer/domains/workflows/tests/common-advanced-config.test.tsx b/apps/desktop/src/renderer/domains/workflows/tests/common-advanced-config.test.tsx
--- a/apps/desktop/src/renderer/domains/workflows/tests/common-advanced-config.test.tsx
+++ b/apps/desktop/src/renderer/domains/workflows/tests/common-advanced-config.test.tsx
@@ -8,10 +8,12 @@ vi.hoisted(() => {
 import { ConfigPanel } from '../components/ConfigPanel'
 import { useWorkflowStore as store, type ErrorPolicy } from '../editor-store'
 import { mockRequest } from '../api/mock-server'
+import { featureFlags } from '../lib/featureFlags'
 Element.prototype.scrollIntoView = vi.fn()
 let id: string
-beforeEach(() => { store.getState().clearWorkflow(); store.getState().addNode('close_page', { x: 0, y: 0 }); id = store.getState().nodes[0].id })
-afterEach(cleanup)
+// These controls stay in the code but are hidden until M2 implements them (remediation M1 R1-01).
+beforeEach(() => { featureFlags.nodeRetryPolicy = true; store.getState().clearWorkflow(); store.getState().addNode('close_page', { x: 0, y: 0 }); id = store.getState().nodes[0].id })
+afterEach(() => { cleanup(); featureFlags.nodeRetryPolicy = false })
 const data = () => store.getState().nodes.find(n => n.id === id)!.data
 function labelled(text: string, role: 'combobox' | 'textbox') {
   return within(screen.getAllByText(text, { exact: true }).find(e => e.tagName === 'LABEL')!.parentElement!).getByRole(role)
```

- [ ] **Step 7: 运行**

Run: `npm --workspace @autoflow/desktop test -- src/renderer/domains/workflows`
Expected: 除依赖 `reference/WebRPA` 的 `recording-source-parity.test.ts`（本地无该目录时报错，CI 会检出）外全部通过。
Run: `uv run --directory apps/backend pytest -q tests/unit/workflows/test_inert_settings.py`
Expected: 3 passed（前后端键列表一致）。

- [ ] **Step 8: 收紧守门基线**

Run: `node scripts/ratchets.mjs`
Expected: 提示 `unreadConfigKeys` 已减少（7 个键 errorPolicy、onTimeout、retryBackoff、retryCount、retryDelay、retryExhaustedAction、timeoutAction 现在出现在后端 `inert_settings.py` 中）。
Run: `node scripts/ratchets.mjs --write-baseline && node scripts/ratchets.mjs`
Expected: 通过，`unreadConfigKeys` 比 M0 基线少 7。

- [ ] **Step 9: 提交**

```bash
git add apps/desktop/src/renderer/domains/workflows scripts/ratchets-baseline.json
git commit -m "fix(studio): 隐藏后端尚未执行的出错策略、重试与超时动作，运行前提示已保存的旧设置"
```

---

### Task 7: 执行名额与存活浏览器分开计数（R1-08、R1-09、R1-10）

**Files:**
- Modify: `apps/backend/src/autoflow/application/workflows/dispatcher.py`
- Modify: `apps/backend/src/autoflow/infrastructure/process/project_workflow_worker.py`（容量校验与 `set_capacity`）
- Modify: `apps/backend/src/autoflow/application/project_runs/scheduler.py`
- Modify: `apps/backend/tests/integration/test_workflow_dispatch.py`
- Test: `apps/backend/tests/integration/test_project_capacity_counts.py`

**Interfaces:**
- Produces: `dispatcher.MAX_RUN_CAPACITY = 64`、`dispatcher.MEMORY_RECHECK_SECONDS = 5.0`、`dispatcher.validate_capacity(capacity, live_capacity) -> tuple[int, int]`；`WorkflowRunDispatcher(..., capacity=1, live_capacity=None, memory_pressure=lambda: False, ...)`、属性 `capacity`、`live_capacity`、方法 `executing_count() -> int`、`set_capacity(capacity, live_capacity=None)`；`ProjectWorkflowWorkerManager.set_capacity(capacity: int)`（1–128）；`scheduler.CapacityCounts(executing, live, automation, batch)`、`scheduler._core_limits(core) -> tuple[int, int]`；`ProjectBatchScheduler.claim_data_task(..., core_live_capacity: int | None = None)`。Task 8 使用 `set_capacity`。

- [ ] **Step 1: 写失败的测试**

`apps/backend/tests/integration/test_project_capacity_counts.py`：

```python
"""Remediation M1 R1-09: waiting-for-person runs keep a live browser, not an execution slot."""

from autoflow.application.project_runs.scheduler import _capacity_counts, _core_limits
from autoflow.infrastructure.database.session import create_session_factory, migrate_database
from autoflow.infrastructure.database.workflow_runtime_models import WorkflowRunRow
from tests.fixtures.workflow_runs import create_queued_run


def test_waiting_manual_runs_count_as_live_but_not_executing(tmp_path):
    database = tmp_path / "counts.sqlite3"
    migrate_database(database)
    factory = create_session_factory(database)
    try:
        running, _ = create_queued_run(factory)
        waiting, _ = create_queued_run(factory)
        queued, _ = create_queued_run(factory)
        with factory.begin() as session:
            session.get(WorkflowRunRow, running.run_id).status = "running"
            session.get(WorkflowRunRow, waiting.run_id).status = "waiting_manual"
        with factory() as session:
            counts = _capacity_counts(session, "no-batch", "no-automation")
        assert (counts.executing, counts.live, counts.automation, counts.batch) == (1, 2, 0, 0)
        assert queued.status == "queued"
    finally:
        factory.dispose()


def test_core_limits_default_live_capacity_to_twice_the_execution_capacity():
    class LegacyCore:
        capacity = 3

    class SplitCore:
        capacity = 2
        live_capacity = 5

    assert _core_limits(LegacyCore()) == (3, 6)
    assert _core_limits(SplitCore()) == (2, 5)
```

`tests/integration/test_workflow_dispatch.py` 的改动（旧用例改为显式 `live_capacity=2`，保留"存活上限"断言；新增三个用例）：

`apps/backend/tests/integration/test_workflow_dispatch.py`：

```diff
diff --git a/apps/backend/tests/integration/test_workflow_dispatch.py b/apps/backend/tests/integration/test_workflow_dispatch.py
--- a/apps/backend/tests/integration/test_workflow_dispatch.py
+++ b/apps/backend/tests/integration/test_workflow_dispatch.py
@@ -862,7 +862,7 @@ async def test_two_run_owners_keep_manual_budget_cancellation_and_leases_indepen
     second, _ = create_queued_run(runtime, resource_request={'automaticExecutionTimeoutSeconds': 1})
     third, _ = create_queued_run(runtime)
     workers, resources = ConcurrentWorkers(), ConcurrentResources()
-    dispatcher = make_dispatcher(runtime, workers, resources, capacity=2)
+    dispatcher = make_dispatcher(runtime, workers, resources, capacity=2, live_capacity=2)
     try:
         await dispatcher.dispatch(first.run_id, expected_status_revision=1, execution_generation=0)
         await dispatcher.dispatch(second.run_id, expected_status_revision=1, execution_generation=0)
@@ -961,3 +961,69 @@ async def test_unknown_cleanup_keeps_its_slot_without_stopping_another_owner(run
     finally:
         workers.cleanup_fail.clear()
         await dispatcher.shutdown()
+
+
+@pytest.mark.asyncio
+async def test_waiting_manual_frees_its_execution_slot_but_keeps_its_live_browser(runtime):
+    first, _ = create_queued_run(runtime)
+    second, _ = create_queued_run(runtime)
+    third, _ = create_queued_run(runtime)
+    workers, resources = ConcurrentWorkers(), ConcurrentResources()
+    dispatcher = make_dispatcher(runtime, workers, resources, capacity=1, live_capacity=2)
+    try:
+        await dispatcher.dispatch(first.run_id, expected_status_revision=1, execution_generation=0)
+        while len(workers.calls) != 1: await asyncio.sleep(.001)
+        with pytest.raises(WorkflowRuntimeError, match='容量'):
+            await dispatcher.dispatch(second.run_id, expected_status_revision=1, execution_generation=0)
+        dispatcher.pause_manual(first.run_id, 1)
+        assert dispatcher.executing_count() == 0
+        await dispatcher.dispatch(second.run_id, expected_status_revision=1, execution_generation=0)
+        while len(workers.calls) != 2: await asyncio.sleep(.001)
+        assert workers.busy(first.run_id) and not resources.leases[first.run_id].released
+        with pytest.raises(WorkflowRuntimeError, match='容量'):
+            await dispatcher.dispatch(third.run_id, expected_status_revision=1, execution_generation=0)
+        dispatcher.resume_manual(first.run_id, 1)
+        assert dispatcher.executing_count() == 2  # resume may exceed the limit; no new dispatch until it drops
+        for run in (first, second): await workers.stop(run.run_id)
+        await dispatcher.wait_idle()
+        assert dispatcher.query_run(first.run_id).status == 'succeeded'
+        assert dispatcher.query_run(second.run_id).status == 'succeeded'
+    finally: await dispatcher.shutdown()
+
+
+def test_capacity_accepts_machine_sized_limits_and_rejects_invalid_values(runtime):
+    workers, resources = ConcurrentWorkers(), ConcurrentResources()
+    dispatcher = make_dispatcher(runtime, workers, resources, capacity=6)
+    assert (dispatcher.capacity, dispatcher.live_capacity) == (6, 12)
+    dispatcher.set_capacity(3, 4)
+    assert (dispatcher.capacity, dispatcher.live_capacity) == (3, 4)
+    for capacity, live in ((0, None), (65, None), (4, 3), (True, None)):
+        with pytest.raises(ValueError):
+            make_dispatcher(runtime, workers, resources, capacity=capacity, live_capacity=live)
+
+
+@pytest.mark.asyncio
+async def test_memory_pressure_pauses_new_dispatch_and_rewakes_the_scheduler(runtime, monkeypatch):
+    from autoflow.application.workflows import dispatcher as dispatcher_module
+
+    monkeypatch.setattr(dispatcher_module, 'MEMORY_RECHECK_SECONDS', 0.01)
+    run, _ = create_queued_run(runtime)
+    pressure = {'high': True}
+    workers, resources = ConcurrentWorkers(), ConcurrentResources()
+    dispatcher = make_dispatcher(runtime, workers, resources, capacity=2, memory_pressure=lambda: pressure['high'])
+    woken = asyncio.Event()
+    dispatcher.subscribe_idle(woken.set)
+    try:
+        with pytest.raises(WorkflowRuntimeError, match='内存') as rejected:
+            await dispatcher.dispatch(run.run_id, expected_status_revision=1, execution_generation=0)
+        assert rejected.value.code == 'WORKFLOW_CAPACITY_FULL'
+        assert workers.calls == []
+        async with asyncio.timeout(1):
+            await woken.wait()
+        pressure['high'] = False
+        await dispatcher.dispatch(run.run_id, expected_status_revision=1, execution_generation=0)
+        while not workers.calls: await asyncio.sleep(.001)
+        await workers.stop(run.run_id)
+        await dispatcher.wait_idle()
+        assert dispatcher.query_run(run.run_id).status == 'succeeded'
+    finally: await dispatcher.shutdown()
```

- [ ] **Step 2: 运行，确认失败**

Run: `uv run --directory apps/backend pytest -q tests/integration/test_project_capacity_counts.py tests/integration/test_workflow_dispatch.py`
Expected: FAIL，`TypeError: ... unexpected keyword argument 'live_capacity'` 与 `ImportError: cannot import name '_core_limits'`。

- [ ] **Step 3: 派发器**

`apps/backend/src/autoflow/application/workflows/dispatcher.py`：

```diff
diff --git a/apps/backend/src/autoflow/application/workflows/dispatcher.py b/apps/backend/src/autoflow/application/workflows/dispatcher.py
--- a/apps/backend/src/autoflow/application/workflows/dispatcher.py
+++ b/apps/backend/src/autoflow/application/workflows/dispatcher.py
@@ -96,9 +96,23 @@ class _RunOwner:
     automatic_remaining: float | None = None
     cleanup_unknown: bool = False
     browser_command_id: str | None = None
+    waiting_manual: bool = False
     control: asyncio.Lock = field(default_factory=asyncio.Lock)
 
 
+MAX_RUN_CAPACITY = 64
+MEMORY_RECHECK_SECONDS = 5.0
+
+
+def validate_capacity(capacity: int, live_capacity: int | None) -> tuple[int, int]:
+    live = 2 * capacity if live_capacity is None and type(capacity) is int else live_capacity
+    if type(capacity) is not int or not 1 <= capacity <= MAX_RUN_CAPACITY:
+        raise ValueError(f'Run capacity must be an integer from 1 to {MAX_RUN_CAPACITY}')
+    if type(live) is not int or not capacity <= live <= 2 * MAX_RUN_CAPACITY:
+        raise ValueError('Live browser capacity must be at least the run capacity')
+    return capacity, live
+
+
 class WorkflowRunDispatcher:
     """Bounded owners for explicitly dispatched, frozen workflow runs."""
 
@@ -113,6 +127,8 @@ class WorkflowRunDispatcher:
         project_end: Any | None = None,
         on_fenced: Callable[[str], None] = lambda _run_id: None,
         capacity: int = 1,
+        live_capacity: int | None = None,
+        memory_pressure: Callable[[], bool] = lambda: False,
         resolve_model: Callable[[str], ModelExecutionBinding] | None = None,
         resolve_default_model: Callable[[str], str] | None = None,
         force_stop_grace: timedelta = timedelta(seconds=30),
@@ -130,9 +146,8 @@ class WorkflowRunDispatcher:
         self._resolve_default_model = resolve_default_model
         self._force_stop_grace = force_stop_grace
         self._now = now
-        if type(capacity) is not int or capacity not in {1, 2}:
-            raise ValueError('Supported Run capacity is 1 or 2')
-        self._capacity = capacity
+        self._capacity, self._live_capacity = validate_capacity(capacity, live_capacity)
+        self._memory_pressure = memory_pressure
         self._owners: dict[str, _RunOwner] = {}
         self._recovering = False
         self._closed = False
@@ -150,9 +165,21 @@ class WorkflowRunDispatcher:
 
     @property
     def capacity(self) -> int:
-        """Maximum simultaneous runs supported by this concrete core owner."""
+        """Maximum runs executing automatically at the same time (spec M1 R1-08)."""
         return self._capacity
 
+    @property
+    def live_capacity(self) -> int:
+        """Maximum live browsers, including runs waiting for a person (spec M1 R1-09)."""
+        return self._live_capacity
+
+    def executing_count(self) -> int:
+        return sum(1 for owner in self._owners.values() if not owner.waiting_manual)
+
+    def set_capacity(self, capacity: int, live_capacity: int | None = None) -> None:
+        """Apply a new limit; lowering it never stops runs that already own a slot."""
+        self._capacity, self._live_capacity = validate_capacity(capacity, live_capacity)
+
     def subscribe_idle(self, listener: Callable[[], None]) -> Callable[[], None]:
         self._idle_listeners.add(listener)
 
@@ -209,11 +236,18 @@ class WorkflowRunDispatcher:
             ]
             if (
                 self._recovering
-                or len(self._owners) >= self.capacity
+                or self.executing_count() >= self.capacity
+                or len(self._owners) >= self.live_capacity
                 or any(run.status != "queued" and run.run_id not in self._owners for run in other_runs)
                 or (not self._owners and self._worker.busy())
             ):
                 raise WorkflowRuntimeError("WORKFLOW_CAPACITY_FULL", "当前运行容量已满")
+            if self._memory_pressure():
+                # Spec M1 R1-10: pause new dispatch; re-offer capacity once pressure may have eased.
+                asyncio.get_running_loop().call_later(MEMORY_RECHECK_SECONDS, self._wake_idle_listeners)
+                raise WorkflowRuntimeError(
+                    "WORKFLOW_CAPACITY_FULL", "本机内存占用超过 85%，暂停派发新任务"
+                )
             with self._gate.mutation() as admitted:
                 if not admitted:
                     raise WorkflowRuntimeError(
@@ -233,6 +267,7 @@ class WorkflowRunDispatcher:
         if owner is None or owner.generation != generation or run.status != 'running' or run.execution_generation != generation:
             raise WorkflowRuntimeError('EXECUTION_GENERATION_REVOKED', '执行代次已失效')
         self._transition(run, 'waiting_manual')
+        owner.waiting_manual = True
         if owner.automatic_timeout is not None:
             deadline = owner.automatic_timeout.when()
             owner.automatic_remaining = max(0, deadline - asyncio.get_running_loop().time()) if deadline is not None else None
@@ -246,6 +281,7 @@ class WorkflowRunDispatcher:
         # Same live owner continues; resume_queued -> running is reserved for
         # dispatching a new owner and deliberately increments the generation.
         self._transition(run, 'running')
+        owner.waiting_manual = False
         if owner.automatic_timeout is not None and owner.automatic_remaining is not None:
             owner.automatic_timeout.reschedule(asyncio.get_running_loop().time() + owner.automatic_remaining)
 
@@ -654,8 +690,11 @@ class WorkflowRunDispatcher:
                         and not self._worker.busy(dispatched.run_id)
                     ):
                         self._clear_owner(owner)
-            for listener in tuple(self._idle_listeners):
-                listener()
+            self._wake_idle_listeners()
+
+    def _wake_idle_listeners(self) -> None:
+        for listener in tuple(self._idle_listeners):
+            listener()
 
     async def _finish_end(self, run_id: str, *, recovering: bool = False) -> bool:
         async with self._control:
```

- [ ] **Step 4: worker 管理器的容量是存活进程数**

`infrastructure/process/project_workflow_worker.py` 中，把

```python
        if type(capacity) is not int or capacity not in {1, 2}:
            raise ValueError("Supported worker capacity is 1 or 2")
        self._capacity = capacity
```

替换为

```python
        if type(capacity) is not int or not 1 <= capacity <= 128:
            raise ValueError("Worker capacity must be an integer from 1 to 128")
        self._capacity = capacity
```

并在 `def busy(self, run_id: str | None = None) -> bool:` 之前加：

```python
    def set_capacity(self, capacity: int) -> None:
        """Live-browser limit; lowering it never stops running workers."""
        if type(capacity) is not int or not 1 <= capacity <= 128:
            raise ValueError("Worker capacity must be an integer from 1 to 128")
        self._capacity = capacity

```

- [ ] **Step 5: 调度器区分执行中与存活**

`apps/backend/src/autoflow/application/project_runs/scheduler.py`：

```diff
diff --git a/apps/backend/src/autoflow/application/project_runs/scheduler.py b/apps/backend/src/autoflow/application/project_runs/scheduler.py
--- a/apps/backend/src/autoflow/application/project_runs/scheduler.py
+++ b/apps/backend/src/autoflow/application/project_runs/scheduler.py
@@ -4,6 +4,7 @@ import asyncio
 import hashlib
 import json
 import logging
+from dataclasses import dataclass
 from datetime import UTC, datetime
 from typing import Any
 from uuid import UUID, uuid4
@@ -313,7 +314,7 @@ class ProjectBatchScheduler:
                     self.wake()
                     return
                 available = _claim_capacity_available(
-                    session, row, batch_id, max(1, int(getattr(self._core, "capacity", 1)))
+                    session, row, batch_id, *_core_limits(self._core)
                 )
             if not available:
                 self._set_status(project_id, batch_id, "running" if any(
@@ -391,17 +392,16 @@ class ProjectBatchScheduler:
                 )
             )
             with self._factory() as session:
-                global_active, automation_active, _ = _capacity_counts(
-                    session, batch_id, batch.automation_id
-                )
-            core_capacity = max(1, int(getattr(self._core, "capacity", 1)))
+                counts = _capacity_counts(session, batch_id, batch.automation_id)
+            core_capacity, core_live_capacity = _core_limits(self._core)
             slots = max(
                 0,
                 min(
                     requested_concurrency - len(active),
                     configured_concurrency - len(active),
-                    configured_capacity - automation_active,
-                    core_capacity - global_active,
+                    configured_capacity - counts.automation,
+                    core_capacity - counts.executing,
+                    core_live_capacity - counts.live,
                 ),
             )
             if slots == 0 and not active:
@@ -561,6 +564,7 @@ class ProjectBatchScheduler:
         core_capacity: int = 1,
         environments: Any | None = None,
         resource_resolver: ProjectRunResourceResolver | None = None,
+        core_live_capacity: int | None = None,
     ) -> str:
         """Prepare outside the write lock, then atomically commit one data Task."""
         prepared = ProjectBatchScheduler._prepare_data_claim(
@@ -596,6 +600,7 @@ class ProjectBatchScheduler:
             core_capacity=core_capacity,
             environments=environments,
             resource_resolver=resource_resolver,
+            core_live_capacity=core_live_capacity,
         )
         return result
 
@@ -604,7 +609,8 @@ class ProjectBatchScheduler:
             self._factory,
             project_id,
             batch_id,
-            core_capacity=max(1, int(getattr(self._core, "capacity", 1))),
+            core_capacity=_core_limits(self._core)[0],
+            core_live_capacity=_core_limits(self._core)[1],
             environments=self._environments,
             resource_resolver=self._resource_resolver,
         )
@@ -739,6 +745,7 @@ class ProjectBatchScheduler:
         core_capacity: int = 1,
         environments: Any | None = None,
         resource_resolver: ProjectRunResourceResolver | None = None,
+        core_live_capacity: int | None = None,
     ) -> str:
         with factory() as session:
             session.execute(text("BEGIN IMMEDIATE"))
@@ -806,6 +813,7 @@ class ProjectBatchScheduler:
                 row,
                 batch_id,
                 core_capacity,
+                core_live_capacity,
             ):
                 row.selection_outcome = {
                     "status": "capacityFull",
@@ -1231,13 +1239,28 @@ class ProjectBatchScheduler:
             raise
 
 
+@dataclass(frozen=True)
+class CapacityCounts:
+    executing: int
+    live: int
+    automation: int
+    batch: int
+
+
+def _core_limits(core: Any) -> tuple[int, int]:
+    capacity = max(1, int(getattr(core, "capacity", 1)))
+    return capacity, max(capacity, int(getattr(core, "live_capacity", 2 * capacity)))
+
+
 def _capacity_counts(
     session: Session, batch_id: str, automation_id: str,
-) -> tuple[int, int, int]:
+) -> CapacityCounts:
     # Parameter batches pre-create their entire queue, without reserving slots.
     # Data tasks already hold input leases when queued and must keep their slots.
+    # Runs waiting for a person keep a live browser but no execution slot (M1 R1-09).
     counts = session.execute(
         select(
+            func.count().filter(WorkflowRunRow.status != "waiting_manual"),
             func.count(),
             func.count().filter(ProjectBatchRow.automation_id == automation_id),
             func.count().filter(ProjectTaskRow.batch_id == batch_id),
@@ -1255,7 +1278,7 @@ def _capacity_counts(
             ),
         )
     ).one()
-    return int(counts[0]), int(counts[1]), int(counts[2])
+    return CapacityCounts(int(counts[0]), int(counts[1]), int(counts[2]), int(counts[3]))
 
 
 def _claim_capacity_available(
@@ -1263,19 +1286,21 @@ def _claim_capacity_available(
     row: ProjectBatchRow,
     batch_id: str,
     core_capacity: int,
+    core_live_capacity: int | None = None,
 ) -> bool:
     request_concurrency = int(row.frozen_request.get("concurrency") or 1)
     run_policy = row.frozen_request["automation"]["runPolicy"]
     configured_concurrency = int(run_policy.get("concurrency", 1))
     configured_capacity = int(run_policy.get("maxLiveInstances", 1))
-    global_active, automation_active, batch_active = _capacity_counts(
-        session, batch_id, row.automation_id
-    )
+    counts = _capacity_counts(session, batch_id, row.automation_id)
+    core_capacity = max(1, core_capacity)
+    live_capacity = core_live_capacity if core_live_capacity is not None else 2 * core_capacity
     return (
-        batch_active < request_concurrency
-        and batch_active < configured_concurrency
-        and automation_active < configured_capacity
-        and global_active < max(1, core_capacity)
+        counts.batch < request_concurrency
+        and counts.batch < configured_concurrency
+        and counts.automation < configured_capacity
+        and counts.executing < core_capacity
+        and counts.live < live_capacity
     )
 
 
```

- [ ] **Step 6: 运行**

Run: `uv run --directory apps/backend pytest -q tests/integration/test_project_capacity_counts.py tests/integration/test_workflow_dispatch.py tests/integration/test_project_parameter_concurrency.py tests/integration/test_project_data_scheduler.py tests/integration/test_project_run_evidence.py`
Expected: 全部通过。

- [ ] **Step 7: 提交**

```bash
git add apps/backend/src/autoflow/application/workflows/dispatcher.py apps/backend/src/autoflow/infrastructure/process/project_workflow_worker.py apps/backend/src/autoflow/application/project_runs/scheduler.py apps/backend/tests/integration/test_workflow_dispatch.py apps/backend/tests/integration/test_project_capacity_counts.py
git commit -m "feat(dispatch): 执行名额与存活浏览器分开计数，人工等待不占执行名额，内存高水位暂停派发"
```

---

### Task 8: 并发上限按机器配置并可在线调整（R1-07）

**Files:**
- Modify: `apps/backend/pyproject.toml`、`apps/backend/uv.lock`
- Create: `apps/backend/src/autoflow/domain/settings/execution_capacity.py`
- Create: `apps/backend/src/autoflow/infrastructure/database/app_settings.py`
- Create: `apps/backend/src/autoflow/infrastructure/database/migrations/versions/rm1_app_settings.py`
- Create: `apps/backend/src/autoflow/application/settings/execution.py`
- Create: `apps/backend/src/autoflow/adapters/http/execution_settings.py`
- Modify: `apps/backend/src/autoflow/bootstrap/workflows.py`、`apps/backend/src/autoflow/bootstrap/schema_export.py`
- Modify: `apps/backend/tests/integration/test_migration_heads.py`
- Modify: `apps/desktop/src/renderer/shared/api/generated.ts`（生成）
- Test: `apps/backend/tests/unit/test_execution_capacity.py`、`apps/backend/tests/contract/test_execution_settings.py`

**Interfaces:**
- Consumes: `WorkflowRunDispatcher.set_capacity`、`ProjectWorkflowWorkerManager.set_capacity`（Task 7）。
- Produces: `HardwareProfile(logical_cpus, total_memory_bytes)`、`recommended_capacity(hw) -> int`、`resolve_capacity(configured, hw) -> ExecutionCapacity(configured, recommended, effective, live)`；`SqlAlchemyAppSettings.get(key) -> (value, revision)`、`.put(key, value, expected_revision) -> int`、`AppSettingConflict(current_revision)`；`ExecutionSettingsService.read() -> ExecutionSettingsView`、`.update(configured, expected_revision)`、`.bind(dispatcher, worker)`；`app.state.execution_settings`；接口 `GET/PUT /api/v1/settings/execution`（schema `ExecutionSettingsRead`、`ExecutionSettingsUpdate`）。Task 9 的前端使用该接口。

- [ ] **Step 1: 依赖**

`apps/backend/pyproject.toml` 的 `dependencies` 中（`"mss>=10,<11",` 之后）加入 `"psutil>=7,<8",`，然后：
Run: `uv lock --directory apps/backend`
Expected: 锁文件只在 `autoflow-backend` 的依赖列表中加入 psutil，版本仍为 7.2.2。

- [ ] **Step 2: 写失败的测试**

`apps/backend/tests/unit/test_execution_capacity.py`：

```python
import pytest

from autoflow.domain.settings.execution_capacity import (
    GIB,
    HardwareProfile,
    recommended_capacity,
    resolve_capacity,
)


@pytest.mark.parametrize(
    ("cpus", "memory_gib", "expected"),
    [(8, 16, 6), (4, 8, 3), (2, 4, 1), (1, 1, 1), (16, 8, 5), (128, 512, 64)],
)
def test_recommended_capacity_uses_the_smaller_of_cpu_and_memory(cpus, memory_gib, expected):
    assert recommended_capacity(HardwareProfile(cpus, memory_gib * GIB)) == expected


def test_configured_value_overrides_recommendation_and_live_is_double():
    capacity = resolve_capacity(10, HardwareProfile(8, 16 * GIB))
    assert (capacity.configured, capacity.recommended, capacity.effective, capacity.live) == (10, 6, 10, 20)
    assert resolve_capacity(None, HardwareProfile(8, 16 * GIB)).effective == 6


@pytest.mark.parametrize("configured", [0, 65, -1])
def test_out_of_range_configuration_is_rejected(configured):
    with pytest.raises(ValueError):
        resolve_capacity(configured, HardwareProfile(8, 16 * GIB))
```

`apps/backend/tests/contract/test_execution_settings.py`：

```python
"""Remediation M1 R1-07: machine-sized capacity is readable, adjustable and applied live."""


def test_default_capacity_follows_hardware_and_replaces_the_fixed_two(client):
    body = client.get("/api/v1/settings/execution").json()
    assert body["maxRunningBrowsers"] is None
    assert body["effectiveMaxRunningBrowsers"] == body["recommendedMaxRunningBrowsers"] >= 1
    assert body["maxLiveBrowsers"] == 2 * body["effectiveMaxRunningBrowsers"]
    assert body["revision"] == 0
    dispatcher = client.app.state.project_workflow_dispatcher
    assert dispatcher.capacity == body["effectiveMaxRunningBrowsers"]
    assert dispatcher.live_capacity == body["maxLiveBrowsers"]


def test_saving_a_limit_applies_to_the_running_dispatcher_and_rejects_stale_revisions(client):
    dispatcher = client.app.state.project_workflow_dispatcher
    saved = client.put("/api/v1/settings/execution", json={"maxRunningBrowsers": 7, "expectedRevision": 0})
    assert saved.status_code == 200, saved.text
    assert saved.json()["effectiveMaxRunningBrowsers"] == 7
    assert saved.json()["revision"] == 1
    assert (dispatcher.capacity, dispatcher.live_capacity) == (7, 14)
    stale = client.put("/api/v1/settings/execution", json={"maxRunningBrowsers": 3, "expectedRevision": 0})
    assert stale.status_code == 409
    assert stale.json()["error"]["code"] == "SETTINGS_REVISION_CONFLICT"
    reset = client.put("/api/v1/settings/execution", json={"maxRunningBrowsers": None, "expectedRevision": 1})
    assert reset.json()["maxRunningBrowsers"] is None
    assert dispatcher.capacity == reset.json()["recommendedMaxRunningBrowsers"]


def test_out_of_range_limits_are_rejected_without_changing_capacity(client):
    dispatcher = client.app.state.project_workflow_dispatcher
    before = dispatcher.capacity
    for value in (0, 65, "4"):
        response = client.put("/api/v1/settings/execution", json={"maxRunningBrowsers": value, "expectedRevision": 0})
        assert response.status_code == 422, value
    assert dispatcher.capacity == before
```

`tests/integration/test_migration_heads.py`：

`apps/backend/tests/integration/test_migration_heads.py`：

```diff
diff --git a/apps/backend/tests/integration/test_migration_heads.py b/apps/backend/tests/integration/test_migration_heads.py
--- a/apps/backend/tests/integration/test_migration_heads.py
+++ b/apps/backend/tests/integration/test_migration_heads.py
@@ -18,7 +18,8 @@ def _config(database: Path) -> Config:
 def test_studio_backend_history_has_one_merged_head(tmp_path: Path) -> None:
     scripts = ScriptDirectory.from_config(_config(tmp_path / "heads.sqlite3"))
 
-    assert scripts.get_heads() == ["0025_merge_studio_credential_environment"]
+    assert scripts.get_heads() == ["rm1_app_settings"]
+    assert scripts.get_revision("rm1_app_settings").down_revision == "0025_merge_studio_credential_environment"
     assert scripts.get_revision("0025_merge_studio_credential_environment").down_revision == (
         "0024_studio_credential_namespace", "0024_environment_identity",
     )
@@ -116,7 +117,7 @@ def test_android_pm9_merge_upgrades_each_published_head_without_losing_data(tmp_
 
     with sqlite3.connect(database) as connection:
         assert connection.execute("SELECT version_num FROM alembic_version").fetchall() == [
-            ("0025_merge_studio_credential_environment",)
+            ("rm1_app_settings",)
         ]
         assert connection.execute("SELECT * FROM workflow_documents").fetchall() == before
         if previous_head == "am01_management_operations":
@@ -151,7 +152,7 @@ def test_integrated_workspace_history_is_recognized_and_preserved(
     with sqlite3.connect(database) as connection:
         assert connection.execute(
             "SELECT version_num FROM alembic_version"
-        ).fetchall() == [("0025_merge_studio_credential_environment",)]
+        ).fetchall() == [("rm1_app_settings",)]
         assert connection.execute(
             "SELECT value FROM preserved_workspace_data"
         ).fetchall() == [("keep-me",)]
```

- [ ] **Step 3: 运行，确认失败**

Run: `uv run --directory apps/backend pytest -q tests/unit/test_execution_capacity.py tests/contract/test_execution_settings.py tests/integration/test_migration_heads.py`
Expected: FAIL（模块不存在、接口 404、迁移头仍为 0025）。

- [ ] **Step 4: 推荐值规则**

`apps/backend/src/autoflow/domain/settings/execution_capacity.py`：

```python
"""Machine-sized run capacity (remediation M1, R1-07)."""

from __future__ import annotations

from dataclasses import dataclass

MAX_RUN_CAPACITY = 64
GIB = 1024**3
BROWSER_MEMORY_BYTES = int(1.5 * GIB)
MEMORY_PRESSURE_PERCENT = 85.0


@dataclass(frozen=True)
class HardwareProfile:
    logical_cpus: int
    total_memory_bytes: int


def recommended_capacity(hardware: HardwareProfile) -> int:
    """Three browsers per four logical CPUs, 1.5 GiB each, clamped to 1..64."""
    by_cpu = (max(1, hardware.logical_cpus) * 3) // 4
    by_memory = hardware.total_memory_bytes // BROWSER_MEMORY_BYTES
    return max(1, min(MAX_RUN_CAPACITY, by_cpu, by_memory))


@dataclass(frozen=True)
class ExecutionCapacity:
    configured: int | None
    recommended: int
    effective: int
    live: int


def resolve_capacity(configured: int | None, hardware: HardwareProfile) -> ExecutionCapacity:
    recommended = recommended_capacity(hardware)
    effective = configured if configured is not None else recommended
    if not 1 <= effective <= MAX_RUN_CAPACITY:
        raise ValueError(f"run capacity must be between 1 and {MAX_RUN_CAPACITY}")
    return ExecutionCapacity(configured, recommended, effective, 2 * effective)
```

- [ ] **Step 5: 设置表与迁移**

`apps/backend/src/autoflow/infrastructure/database/migrations/versions/rm1_app_settings.py`：

```python
"""Remediation M1: small key/value store for machine-level execution settings."""

import sqlalchemy as sa
from alembic import op

revision = "rm1_app_settings"
down_revision = "0025_merge_studio_credential_environment"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "app_settings",
        sa.Column("key", sa.String(120), primary_key=True),
        sa.Column("value", sa.JSON(), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("app_settings")
```

`apps/backend/src/autoflow/infrastructure/database/app_settings.py`：

```python
"""Versioned key/value settings owned by this workspace (remediation M1)."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import JSON, DateTime, Integer, String, update
from sqlalchemy.orm import Mapped, Session, mapped_column, sessionmaker

from .models import Base


class AppSettingRow(Base):
    __tablename__ = "app_settings"
    key: Mapped[str] = mapped_column(String(120), primary_key=True)
    value: Mapped[Any] = mapped_column(JSON, nullable=False)
    revision: Mapped[int] = mapped_column(Integer, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class AppSettingConflict(Exception):
    def __init__(self, current_revision: int) -> None:
        super().__init__("app setting revision conflict")
        self.current_revision = current_revision


class SqlAlchemyAppSettings:
    def __init__(
        self,
        factory: sessionmaker[Session],
        now: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._factory = factory
        self._now = now

    def get(self, key: str) -> tuple[Any, int]:
        """Return (value, revision); a missing key is (None, 0)."""
        with self._factory() as session:
            row = session.get(AppSettingRow, key)
            return (None, 0) if row is None else (row.value, row.revision)

    def put(self, key: str, value: Any, expected_revision: int) -> int:
        with self._factory.begin() as session:
            row = session.get(AppSettingRow, key)
            current = 0 if row is None else row.revision
            if current != expected_revision:
                raise AppSettingConflict(current)
            if row is None:
                session.add(AppSettingRow(key=key, value=value, revision=1, updated_at=self._now()))
                return 1
            changed = session.execute(
                update(AppSettingRow)
                .where(AppSettingRow.key == key, AppSettingRow.revision == expected_revision)
                .values(value=value, revision=expected_revision + 1, updated_at=self._now())
            ).rowcount
            if changed != 1:
                raise AppSettingConflict(current)
            return expected_revision + 1
```

- [ ] **Step 6: 应用服务与接口**

`apps/backend/src/autoflow/application/settings/execution.py`：

```python
"""Execution capacity settings applied to the live dispatcher (remediation M1, R1-07/R1-08)."""

from __future__ import annotations

import os
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Protocol

import psutil

from autoflow.domain.settings.execution_capacity import (
    MEMORY_PRESSURE_PERCENT,
    ExecutionCapacity,
    HardwareProfile,
    resolve_capacity,
)
from autoflow.infrastructure.database.app_settings import SqlAlchemyAppSettings

SETTING_KEY = "execution.maxRunningBrowsers"


class CapacityTarget(Protocol):
    def set_capacity(self, capacity: int, live_capacity: int | None = None) -> None: ...


class LiveTarget(Protocol):
    def set_capacity(self, capacity: int) -> None: ...


def detect_hardware() -> HardwareProfile:
    return HardwareProfile(os.cpu_count() or 1, int(psutil.virtual_memory().total))


def memory_pressure() -> bool:
    return float(psutil.virtual_memory().percent) >= MEMORY_PRESSURE_PERCENT


@dataclass(frozen=True)
class ExecutionSettingsView:
    capacity: ExecutionCapacity
    revision: int
    hardware: HardwareProfile
    memory_pressure: bool


class ExecutionSettingsService:
    def __init__(
        self,
        store: SqlAlchemyAppSettings,
        *,
        hardware: Callable[[], HardwareProfile] = detect_hardware,
        pressure: Callable[[], bool] = memory_pressure,
    ) -> None:
        self._store = store
        self._hardware = hardware
        self._pressure = pressure
        self._targets: list[Any] = []

    def bind(self, dispatcher: CapacityTarget, worker: LiveTarget) -> None:
        """Later updates resize these owners; running work keeps its slot."""
        self._targets = [dispatcher, worker]

    def read(self) -> ExecutionSettingsView:
        value, revision = self._store.get(SETTING_KEY)
        configured = value if isinstance(value, int) and not isinstance(value, bool) else None
        hardware = self._hardware()
        return ExecutionSettingsView(resolve_capacity(configured, hardware), revision, hardware, self._pressure())

    def update(self, configured: int | None, expected_revision: int) -> ExecutionSettingsView:
        capacity = resolve_capacity(configured, self._hardware())  # validates before writing
        self._store.put(SETTING_KEY, configured, expected_revision)
        self._apply(capacity)
        return self.read()

    def _apply(self, capacity: ExecutionCapacity) -> None:
        if not self._targets:
            return
        dispatcher, worker = self._targets
        worker.set_capacity(capacity.live)
        dispatcher.set_capacity(capacity.effective, capacity.live)
```

`apps/backend/src/autoflow/adapters/http/execution_settings.py`：

```python
"""GET/PUT /api/v1/settings/execution (remediation M1, R1-07)."""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel, Field, StrictInt

from autoflow.application.settings.execution import ExecutionSettingsService, ExecutionSettingsView
from autoflow.infrastructure.database.app_settings import AppSettingConflict

from .errors import error_response


class ExecutionHardwareRead(BaseModel):
    logicalCpus: int
    totalMemoryGb: float


class ExecutionSettingsRead(BaseModel):
    maxRunningBrowsers: int | None
    recommendedMaxRunningBrowsers: int
    effectiveMaxRunningBrowsers: int
    maxLiveBrowsers: int
    memoryPressure: bool
    hardware: ExecutionHardwareRead
    revision: int


class ExecutionSettingsUpdate(BaseModel):
    maxRunningBrowsers: StrictInt | None = Field(default=None, ge=1, le=64)
    expectedRevision: StrictInt = Field(ge=0)


def _read(view: ExecutionSettingsView) -> ExecutionSettingsRead:
    return ExecutionSettingsRead(
        maxRunningBrowsers=view.capacity.configured,
        recommendedMaxRunningBrowsers=view.capacity.recommended,
        effectiveMaxRunningBrowsers=view.capacity.effective,
        maxLiveBrowsers=view.capacity.live,
        memoryPressure=view.memory_pressure,
        hardware=ExecutionHardwareRead(
            logicalCpus=view.hardware.logical_cpus,
            totalMemoryGb=round(view.hardware.total_memory_bytes / 1024**3, 1),
        ),
        revision=view.revision,
    )


def execution_settings_router(service: ExecutionSettingsService) -> APIRouter:
    router = APIRouter()

    @router.get("/api/v1/settings/execution", response_model=ExecutionSettingsRead)
    def read() -> ExecutionSettingsRead:
        return _read(service.read())

    @router.put("/api/v1/settings/execution", response_model=ExecutionSettingsRead)
    def update(body: ExecutionSettingsUpdate):
        try:
            return _read(service.update(body.maxRunningBrowsers, body.expectedRevision))
        except AppSettingConflict as conflict:
            return error_response(
                409, "SETTINGS_REVISION_CONFLICT", "设置已被修改，请刷新后重试",
                {"currentRevision": conflict.current_revision},
            )

    return router
```

- [ ] **Step 7: 启动时按设置定容量，并注册路由（含 OpenAPI 导出）**

`apps/backend/src/autoflow/bootstrap/workflows.py`：

```diff
diff --git a/apps/backend/src/autoflow/bootstrap/workflows.py b/apps/backend/src/autoflow/bootstrap/workflows.py
--- a/apps/backend/src/autoflow/bootstrap/workflows.py
+++ b/apps/backend/src/autoflow/bootstrap/workflows.py
@@ -562,8 +562,17 @@ def configure_project_workflow_runtime(
     )
 
     capabilities = ProjectWorkerCapabilities(session_factory, environments)
+    from autoflow.adapters.http.execution_settings import execution_settings_router
+    from autoflow.application.settings.execution import (
+        ExecutionSettingsService,
+        memory_pressure,
+    )
+    from autoflow.infrastructure.database.app_settings import SqlAlchemyAppSettings
+
+    execution_settings = ExecutionSettingsService(SqlAlchemyAppSettings(session_factory))
+    capacity = execution_settings.read().capacity
     worker = ProjectWorkflowWorkerManager(
-        temp_dir, on_capability=capabilities.handle, capacity=2,
+        temp_dir, on_capability=capabilities.handle, capacity=capacity.live,
         resolve_credential=resolve_credential, proxy_service=proxy_service,
     )
 
@@ -596,13 +605,18 @@ def configure_project_workflow_runtime(
         raise KernelNotFound()
 
     dispatcher = WorkflowRunDispatcher(
-        session_factory, worker, resources, gate, recover, capacity=2,
+        session_factory, worker, resources, gate, recover,
+        capacity=capacity.effective, live_capacity=capacity.live,
+        memory_pressure=memory_pressure,
         project_end=capabilities.project_end,
         on_fenced=capabilities.manual.cancel_run if capabilities.manual else lambda _run_id: None,
         resolve_model=models.execution_binding if models is not None else None,
         resolve_default_model=models.default_model_id if models is not None else None,
     )
     capabilities.browser_dispatcher = dispatcher
+    execution_settings.bind(dispatcher, worker)
+    app.state.execution_settings = execution_settings
+    app.include_router(execution_settings_router(execution_settings))
     if capabilities.manual is not None:
         capabilities.manual.dispatcher = dispatcher
     runtime = WorkflowRuntimeService(
```

`apps/backend/src/autoflow/bootstrap/schema_export.py`：

```diff
diff --git a/apps/backend/src/autoflow/bootstrap/schema_export.py b/apps/backend/src/autoflow/bootstrap/schema_export.py
--- a/apps/backend/src/autoflow/bootstrap/schema_export.py
+++ b/apps/backend/src/autoflow/bootstrap/schema_export.py
@@ -8,6 +8,7 @@ from fastapi import FastAPI
 from autoflow.adapters.http.android import android_router
 from autoflow.adapters.http.android_fleet import android_fleet_router
 from autoflow.adapters.http.android_management import android_management_router
+from autoflow.adapters.http.execution_settings import execution_settings_router
 from autoflow.adapters.http.image_assets import image_assets_router
 from autoflow.adapters.http.local_workflows import local_workflows_router
 from autoflow.adapters.http.openapi import configure_openapi
@@ -78,6 +79,7 @@ def export_schema(*, api_version: str = 'v1') -> dict[str, Any]:
     app.include_router(studio_credentials_router(unavailable))
     app.include_router(studio_retention_router(unavailable))
     app.include_router(workflow_schedules_router(unavailable))
+    app.include_router(execution_settings_router(unavailable))
     return app.openapi()
 
 
```

- [ ] **Step 8: 运行并生成前端类型**

Run: `uv run --directory apps/backend pytest -q tests/unit/test_execution_capacity.py tests/contract/test_execution_settings.py tests/integration/test_migration_heads.py tests/contract/test_schema_export.py tests/integration/test_workflow_dispatch.py`
Expected: 全部通过。
Run: `npm run openapi:generate && npm run openapi:check`
Expected: `generated.ts` 新增 `ExecutionSettingsRead`、`ExecutionSettingsUpdate`、`ExecutionHardwareRead` 与路径 `/api/v1/settings/execution`；check 通过。
Run: `uv run --directory apps/backend mypy src && uv run --directory apps/backend ruff check .`
Expected: 无错误。

- [ ] **Step 9: 提交**

```bash
git add apps/backend/pyproject.toml apps/backend/uv.lock apps/backend/src/autoflow/domain/settings/execution_capacity.py apps/backend/src/autoflow/infrastructure/database/app_settings.py apps/backend/src/autoflow/infrastructure/database/migrations/versions/rm1_app_settings.py apps/backend/src/autoflow/application/settings/execution.py apps/backend/src/autoflow/adapters/http/execution_settings.py apps/backend/src/autoflow/bootstrap/workflows.py apps/backend/src/autoflow/bootstrap/schema_export.py apps/backend/tests/unit/test_execution_capacity.py apps/backend/tests/contract/test_execution_settings.py apps/backend/tests/integration/test_migration_heads.py apps/desktop/src/renderer/shared/api/generated.ts
git commit -m "feat(settings): 同时运行的浏览器数按本机 CPU 与内存推荐，可在线调整"
```

---

### Task 9: 设置页与自动化运行设置显示本机上限（R1-11）

**Files:**
- Create: `apps/desktop/src/renderer/domains/settings/executionApi.ts`
- Create: `apps/desktop/src/renderer/domains/settings/components/ExecutionCapacityCard.tsx`
- Modify: `apps/desktop/src/renderer/domains/settings/pages/SettingsPage.tsx`、`apps/desktop/src/renderer/app/App.tsx`
- Modify: `apps/desktop/src/renderer/domains/project-automations/components/RunPolicyEditor.tsx`、`components/AutomationEditor.tsx`、`pages/AutomationDetailPage.tsx`
- Test: `apps/desktop/src/renderer/domains/settings/tests/ExecutionCapacityCard.test.tsx`、`apps/desktop/src/renderer/domains/project-automations/components/RunPolicyEditor.test.tsx`（追加）

**Interfaces:**
- Consumes: `components['schemas']['ExecutionSettingsRead']`（Task 8 生成）。
- Produces: `createExecutionSettingsApi(client) -> ExecutionSettingsApi { read(); save(maxRunningBrowsers: number | null, expectedRevision: number) }`；`SettingsPage` 可选属性 `executionApi`；`RunPolicyEditor` / `AutomationEditor` 可选属性 `machineLimit?: number | null`。

- [ ] **Step 1: 写失败的测试**

`apps/desktop/src/renderer/domains/settings/tests/ExecutionCapacityCard.test.tsx`：

```tsx
import '@testing-library/jest-dom/vitest'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, expect, it, vi } from 'vitest'
import { ExecutionCapacityCard } from '../components/ExecutionCapacityCard'
import type { ExecutionSettings, ExecutionSettingsApi } from '../executionApi'

afterEach(cleanup)
const recommended: ExecutionSettings = {
  maxRunningBrowsers: null, recommendedMaxRunningBrowsers: 6, effectiveMaxRunningBrowsers: 6,
  maxLiveBrowsers: 12, memoryPressure: false, hardware: { logicalCpus: 8, totalMemoryGb: 16 }, revision: 0,
}

function api(overrides: Partial<ExecutionSettingsApi> = {}): ExecutionSettingsApi {
  return {
    read: vi.fn(async () => recommended),
    save: vi.fn(async (value: number | null, revision: number) => ({
      ...recommended, maxRunningBrowsers: value, effectiveMaxRunningBrowsers: value ?? 6,
      maxLiveBrowsers: 2 * (value ?? 6), revision: revision + 1,
    })),
    ...overrides,
  }
}

it('explains the recommendation and saves a custom limit with the current revision', async () => {
  const client = api()
  render(<ExecutionCapacityCard api={client} />)
  expect(await screen.findByText(/推荐 6 个（依据：8 个逻辑 CPU、16 GB 内存）/)).toBeInTheDocument()
  const input = screen.getByLabelText('最多同时运行的浏览器')
  expect(input).toHaveValue('6')
  fireEvent.change(input, { target: { value: '10' } })
  fireEvent.click(screen.getByRole('button', { name: '保存' }))
  await waitFor(() => expect(client.save).toHaveBeenCalledWith(10, 0))
  expect(await screen.findByText('当前使用自定义值')).toBeInTheDocument()
  fireEvent.click(screen.getByRole('button', { name: '恢复推荐值' }))
  await waitFor(() => expect(client.save).toHaveBeenLastCalledWith(null, 1))
})

it('rejects values outside 1–64 before calling the service and shows service errors', async () => {
  const client = api({ save: vi.fn(async () => { throw new Error('设置已被修改，请刷新后重试') }) })
  render(<ExecutionCapacityCard api={client} />)
  const input = await screen.findByDisplayValue('6')
  fireEvent.change(input, { target: { value: '65' } })
  expect(screen.getByRole('alert')).toHaveTextContent('请输入 1–64 的整数')
  expect(screen.getByRole('button', { name: '保存' })).toBeDisabled()
  fireEvent.change(input, { target: { value: '4' } })
  fireEvent.click(screen.getByRole('button', { name: '保存' }))
  expect(await screen.findByText('设置已被修改，请刷新后重试')).toBeInTheDocument()
})
```

向 `RunPolicyEditor.test.tsx` 追加：

```tsx
it('shows the machine-wide limit next to concurrency and warns when the request exceeds it (remediation M1 R1-11)', () => {
  render(<RunPolicyEditor value={{ ...policy, concurrency: 20 }} onChange={vi.fn()} machineLimit={6} />)
  expect(screen.getByText('范围 1–100；本机当前最多同时运行 6 个浏览器，实际同时运行不超过 6 个')).toBeInTheDocument()
})
```

- [ ] **Step 2: 运行，确认失败**

Run: `npm --workspace @autoflow/desktop test -- src/renderer/domains/settings src/renderer/domains/project-automations/components/RunPolicyEditor.test.tsx`
Expected: FAIL，找不到 `../components/ExecutionCapacityCard`；RunPolicyEditor 新用例找不到文字。

- [ ] **Step 3: 接口与卡片**

`apps/desktop/src/renderer/domains/settings/executionApi.ts`：

```ts
import type { ApiClient } from '../../shared/api/client'
import type { components } from '../../shared/api/generated'

export type ExecutionSettings = components['schemas']['ExecutionSettingsRead']

export type ExecutionSettingsApi = {
  read(): Promise<ExecutionSettings>
  save(maxRunningBrowsers: number | null, expectedRevision: number): Promise<ExecutionSettings>
}

// Remediation M1 R1-07/R1-11: machine-level browser limit.
export function createExecutionSettingsApi(client: ApiClient): ExecutionSettingsApi {
  return {
    read: () => client.request<ExecutionSettings>('/api/v1/settings/execution'),
    save: (maxRunningBrowsers, expectedRevision) => client.request<ExecutionSettings>('/api/v1/settings/execution', {
      method: 'PUT',
      body: { maxRunningBrowsers, expectedRevision },
    }),
  }
}
```

`apps/desktop/src/renderer/domains/settings/components/ExecutionCapacityCard.tsx`：

```tsx
import { Cpu } from '@phosphor-icons/react'
import { useEffect, useState } from 'react'
import { Button } from '../../../shared/components/ui/button'
import { Input } from '../../../shared/components/ui/input'
import type { ExecutionSettings, ExecutionSettingsApi } from '../executionApi'
import { SettingsCard } from './SettingsCard'

const message = (cause: unknown, fallback: string) => cause instanceof Error ? cause.message : fallback

export function ExecutionCapacityCard({ api }: { api: ExecutionSettingsApi }) {
  const [settings, setSettings] = useState<ExecutionSettings | null>(null)
  const [draft, setDraft] = useState('')
  const [error, setError] = useState('')
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    let active = true
    api.read().then(value => { if (active) { setSettings(value); setDraft(String(value.effectiveMaxRunningBrowsers)) } })
      .catch(cause => { if (active) setError(message(cause, '读取失败')) })
    return () => { active = false }
  }, [api])

  async function save(value: number | null) {
    if (!settings) return
    setSaving(true); setError('')
    try {
      const saved = await api.save(value, settings.revision)
      setSettings(saved); setDraft(String(saved.effectiveMaxRunningBrowsers))
    } catch (cause) { setError(message(cause, '保存失败，请刷新后重试')) } finally { setSaving(false) }
  }

  const parsed = Number(draft)
  const draftError = draft.trim() && Number.isInteger(parsed) && parsed >= 1 && parsed <= 64 ? '' : '请输入 1–64 的整数'
  const description = settings
    ? `推荐 ${settings.recommendedMaxRunningBrowsers} 个（依据：${settings.hardware.logicalCpus} 个逻辑 CPU、${settings.hardware.totalMemoryGb} GB 内存）。等待人工处理的任务不占这里的名额。`
    : '正在读取本机配置…'
  return <SettingsCard icon={Cpu} title="同时运行的浏览器" description={description}>
    <div className="grid gap-3">
      <label className="grid items-center gap-2 sm:grid-cols-[1fr_13rem]">
        <span><strong className="block">最多同时运行</strong><small className="text-muted">{settings?.maxRunningBrowsers === null ? '当前使用推荐值' : '当前使用自定义值'}</small></span>
        <Input inputMode="numeric" aria-label="最多同时运行的浏览器" value={draft} disabled={!settings || saving} aria-invalid={Boolean(draftError)} onChange={event => setDraft(event.target.value)} />
      </label>
      {draftError ? <p role="alert" className="m-0 text-sm text-danger">{draftError}</p> : null}
      {settings?.memoryPressure ? <p role="status" className="m-0 text-sm text-muted">本机内存占用较高，新任务会暂缓启动。</p> : null}
      {error ? <p role="alert" className="m-0 text-sm text-danger">{error}</p> : null}
      <div className="flex flex-wrap gap-2">
        <Button variant="primary" disabled={!settings || saving || Boolean(draftError)} onClick={() => void save(parsed)}>保存</Button>
        <Button disabled={!settings || saving || settings.maxRunningBrowsers === null} onClick={() => void save(null)}>恢复推荐值</Button>
      </div>
    </div>
  </SettingsCard>
}
```

`apps/desktop/src/renderer/domains/settings/pages/SettingsPage.tsx`：

```diff
diff --git a/apps/desktop/src/renderer/domains/settings/pages/SettingsPage.tsx b/apps/desktop/src/renderer/domains/settings/pages/SettingsPage.tsx
--- a/apps/desktop/src/renderer/domains/settings/pages/SettingsPage.tsx
+++ b/apps/desktop/src/renderer/domains/settings/pages/SettingsPage.tsx
@@ -8,12 +8,14 @@ import { Select } from '../../../shared/components/ui/select'
 import { Tabs, TabsContent, TabsList, TabsTrigger } from '../../../shared/components/ui/tabs'
 import { DetailGrid, SettingsCard } from '../components/SettingsCard'
 import { DiagnosticDialog } from '../components/DiagnosticDialog'
+import { ExecutionCapacityCard } from '../components/ExecutionCapacityCard'
+import type { ExecutionSettingsApi } from '../executionApi'
 
-type Props = { bridge: SettingsBridge; restartService(): Promise<unknown>; onServiceChanged?(): void }
+type Props = { bridge: SettingsBridge; restartService(): Promise<unknown>; onServiceChanged?(): void; executionApi?: ExecutionSettingsApi }
 function unwrap<T>(result: { ok: true; value: T } | { ok: false; error: { message: string } }): T { if (!result.ok) throw new Error(result.error.message); return result.value }
 const serviceCopy = { starting: ['正在启动', '本地服务正在启动，请稍候。'], ready: ['运行正常', '本地服务已连接。'], failed: ['启动失败', '请查看错误信息并重试。'], stopped: ['已停止', '本地服务当前未运行。'] } as const
 
-export function SettingsPage({ bridge, restartService, onServiceChanged }: Props) {
+export function SettingsPage({ bridge, restartService, onServiceChanged, executionApi }: Props) {
   const [data, setData] = useState<DesktopSettingsSnapshot | null>(null)
   const [loadError, setLoadError] = useState('')
   const [operationError, setOperationError] = useState('')
@@ -45,7 +47,7 @@ export function SettingsPage({ bridge, restartService, onServiceChanged }: Props
   const status = serviceCopy[data.service.state]
   return <main className="min-h-dvh bg-canvas px-4 py-7 text-ink sm:px-6 lg:px-8"><div className="mx-auto w-full max-w-[1050px]"><header><h1 className="m-0 text-3xl font-semibold">设置</h1><p className="mb-0 mt-1 text-muted">管理本机应用与工作区</p></header>{loadError ? <div role="alert" className="mt-4 rounded-control border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900">状态更新失败：{loadError}</div> : null}{operationError ? <div role="alert" className="mt-4 flex items-center justify-between gap-3 rounded-control border border-red-200 bg-red-50 p-3 text-sm text-red-800"><span>{operationError}</span><Button className="h-8" onClick={() => setOperationError('')}>关闭</Button></div> : null}{data.workspace.recovery ? <div role="status" className="mt-4 rounded-control border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900">{data.workspace.recovery}</div> : null}
     <Tabs value={tab} onValueChange={setTab} className="mt-5"><TabsList className="w-full justify-start gap-5"><TabsTrigger value="general">常规</TabsTrigger><TabsTrigger value="workspace">工作区</TabsTrigger><TabsTrigger value="about">关于</TabsTrigger></TabsList>
-      <TabsContent value="general" className="grid gap-5"><SettingsCard icon={PlugsConnected} title="本地服务" description={status[1]} action={<span className="flex items-center gap-3"><span className={`rounded-control px-3 py-1 text-sm font-medium ${data.service.state === 'ready' ? 'bg-sage-soft text-sage-strong' : data.service.state === 'failed' ? 'bg-red-50 text-red-800' : 'bg-surface-subtle text-muted'}`}>{status[0]}</span><Button disabled={busy || data.workspace.blocked || data.service.state === 'starting'} onClick={() => void restart()}><ArrowClockwise />{action === 'restart' ? '正在重启…' : data.service.state === 'stopped' ? '启动服务' : '重启服务'}</Button></span>}><DetailGrid items={[{ label: '访问范围', value: data.service.baseUrl ? '仅限本机' : '不可用' }, { label: 'API 版本', value: data.service.apiVersion ?? '不可用' }]} />{data.service.message ? <p className="mt-4 text-sm text-muted">{data.service.message}</p> : null}<button type="button" aria-expanded={details} onClick={() => setDetails(!details)} className="mt-4 flex items-center gap-1 border-0 bg-transparent p-0 text-sm text-muted">连接详情<CaretDown className={details ? 'rotate-180' : ''} /></button>{details ? <DetailGrid items={[{ label: '监听地址', value: data.service.baseUrl ?? '不可用' }, { label: '连接方式', value: data.service.baseUrl ? 'Loopback HTTP' : '不可用' }]} /> : null}</SettingsCard>
+      <TabsContent value="general" className="grid gap-5">{executionApi ? <ExecutionCapacityCard api={executionApi} /> : null}<SettingsCard icon={PlugsConnected} title="本地服务" description={status[1]} action={<span className="flex items-center gap-3"><span className={`rounded-control px-3 py-1 text-sm font-medium ${data.service.state === 'ready' ? 'bg-sage-soft text-sage-strong' : data.service.state === 'failed' ? 'bg-red-50 text-red-800' : 'bg-surface-subtle text-muted'}`}>{status[0]}</span><Button disabled={busy || data.workspace.blocked || data.service.state === 'starting'} onClick={() => void restart()}><ArrowClockwise />{action === 'restart' ? '正在重启…' : data.service.state === 'stopped' ? '启动服务' : '重启服务'}</Button></span>}><DetailGrid items={[{ label: '访问范围', value: data.service.baseUrl ? '仅限本机' : '不可用' }, { label: 'API 版本', value: data.service.apiVersion ?? '不可用' }]} />{data.service.message ? <p className="mt-4 text-sm text-muted">{data.service.message}</p> : null}<button type="button" aria-expanded={details} onClick={() => setDetails(!details)} className="mt-4 flex items-center gap-1 border-0 bg-transparent p-0 text-sm text-muted">连接详情<CaretDown className={details ? 'rotate-180' : ''} /></button>{details ? <DetailGrid items={[{ label: '监听地址', value: data.service.baseUrl ?? '不可用' }, { label: '连接方式', value: data.service.baseUrl ? 'Loopback HTTP' : '不可用' }]} /> : null}</SettingsCard>
         <SettingsCard icon={Database} title="本地数据" description="业务数据保存在当前工作区。" action={<Button disabled={busy} onClick={() => setTab('workspace')}>管理工作区</Button>}><DetailGrid items={[{ label: '存储方式', value: 'SQLite' }, { label: '当前工作区', value: data.workspace.path }]} /></SettingsCard>
         <SettingsCard icon={Desktop} title="界面体验"><div className="grid gap-4"><label className="grid items-center gap-2 sm:grid-cols-[1fr_13rem]"><span><strong className="block">界面缩放</strong><small className="text-muted">调整文字和控件的显示大小。</small></span><Select clearable={false} aria-label="界面缩放" disabled={busy} value={String(data.preferences.zoom)} onValueChange={value => void preference({ ...data.preferences, zoom: Number(value ?? '100') as UiPreferences['zoom'] })} options={[90,100,110,125].map(value => ({ value: String(value), label: `${value}%` }))} /></label><label className="grid items-center gap-2 border-t border-line pt-4 sm:grid-cols-[1fr_13rem]"><span><strong className="block">减少动效</strong><small className="text-muted">调整弹窗、提示和加载动画。</small></span><Select clearable={false} aria-label="减少动效" disabled={busy} value={data.preferences.motion} onValueChange={value => void preference({ ...data.preferences, motion: (value ?? 'system') as UiPreferences['motion'] })} options={[{ value: 'system', label: '跟随系统' }, { value: 'reduce', label: '减少动效' }, { value: 'full', label: '完整动效' }]} /></label></div></SettingsCard></TabsContent>
       <TabsContent value="workspace"><div className="grid gap-5"><SettingsCard icon={FolderOpen} title="当前工作区" description={data.workspace.blocked ? `任务进行中，暂时无法切换：${data.workspace.blockers.join('；')}` : '切换工作区不会搬迁当前数据。'} action={<span className="flex flex-wrap gap-2"><Button onClick={() => void open('workspace')}>打开目录</Button><Button variant="primary" disabled={busy || !canChoose} onClick={() => void choose('choose')}>切换工作区</Button>{data.workspace.previousPath ? <Button disabled={busy || !canChoose} onClick={() => void choose('previous')}>切回上一个</Button> : null}</span>}><code className="block overflow-auto rounded-control bg-surface-subtle p-3 text-sm">{data.workspace.path}</code></SettingsCard><SettingsCard icon={Database} title="工作区位置" description="当前工作区内的主要文件与目录。"><div className="divide-y divide-line">{([['database','数据库'],['profiles','浏览器配置'],['kernels','浏览器内核'],['logs','运行日志']] as Array<[SettingsDirectory,string]>).map(([key,label]) => <div key={key} className="grid items-center gap-3 py-3 sm:grid-cols-[9rem_1fr_auto]"><strong>{label}</strong><code className="min-w-0 overflow-hidden text-ellipsis text-xs text-muted">{data.workspace.paths[key]}</code><Button onClick={() => void open(key)}>打开目录</Button></div>)}</div></SettingsCard></div></TabsContent>
```

`apps/desktop/src/renderer/app/App.tsx`：

```diff
diff --git a/apps/desktop/src/renderer/app/App.tsx b/apps/desktop/src/renderer/app/App.tsx
--- a/apps/desktop/src/renderer/app/App.tsx
+++ b/apps/desktop/src/renderer/app/App.tsx
@@ -11,6 +11,7 @@ import type { ProjectRoute } from '../domains/projects/types'
 import { Button } from '../shared/components/ui/button'
 import { DashboardPage } from '../domains/dashboard/pages/DashboardPage'
 import { SettingsPage } from '../domains/settings/pages/SettingsPage'
+import { createExecutionSettingsApi } from '../domains/settings/executionApi'
 import { ProxyManagementPage } from '../domains/proxies/pages/ProxyManagementPage'
 import { BrowserManagementPage } from '../domains/profiles/pages/BrowserManagementPage'
 import { AndroidPage } from '../domains/android/pages/AndroidPage'
@@ -27,6 +28,7 @@ export function App() {
   const navigate = useCallback((target: AppRoute) => { void navigateHash(`#/${target}`) }, [navigateHash])
   const navigateProject = useCallback((target: ProjectRoute, options?: { replace?: boolean }) => { if (options?.replace) replace(projectHash(target), { preserveGuard: true }); else void navigateHash(projectHash(target)) }, [navigateHash, replace])
   const modelApi = useMemo(() => session ? createModelApi(session.client) : null, [session])
+  const executionApi = useMemo(() => session ? createExecutionSettingsApi(session.client) : undefined, [session])
 
   useEffect(() => {
     void window.autoflow.getSettings?.().then(result => {
@@ -47,7 +49,7 @@ export function App() {
     <ApplicationHeader route={route} onNavigate={navigate} status={status} />
     {session ? <ProjectInteractionHost key={JSON.stringify([session.workspaceKey, session.instanceId])} client={session.client} connected={status === 'connected' && !workspaceChanging} /> : null}
     {route === 'settings' ? settingsAvailable
-      ? <SettingsPage bridge={window.autoflow as SettingsBridge} restartService={() => window.autoflow.restartSidecar()} onServiceChanged={() => void reconnect(false)} />
+      ? <SettingsPage bridge={window.autoflow as SettingsBridge} restartService={() => window.autoflow.restartSidecar()} onServiceChanged={() => void reconnect(false)} executionApi={executionApi} />
       : <State title="桌面设置不可用" description="请使用 AutoFlow 桌面应用打开设置。" />
     : <>
       {status === 'loading' ? <div role="status" className="border-b border-line bg-surface-subtle px-8 py-3 text-sm">正在连接服务…</div> : status === 'offline' ? <div role="alert" className="flex items-center justify-between gap-4 border-b border-red-200 bg-red-50 px-8 py-3 text-sm text-red-900"><span>{message}</span><button type="button" onClick={() => void reconnect()}>重新连接</button></div> : null}
```

- [ ] **Step 4: 自动化运行设置显示本机上限**

`apps/desktop/src/renderer/domains/project-automations/components/RunPolicyEditor.tsx`：

```diff
diff --git a/apps/desktop/src/renderer/domains/project-automations/components/RunPolicyEditor.tsx b/apps/desktop/src/renderer/domains/project-automations/components/RunPolicyEditor.tsx
--- a/apps/desktop/src/renderer/domains/project-automations/components/RunPolicyEditor.tsx
+++ b/apps/desktop/src/renderer/domains/project-automations/components/RunPolicyEditor.tsx
@@ -12,9 +12,11 @@ export type RunPolicyEditorProps = {
   errors?: FieldErrors
   resetKey?: string | number
   onDraftStateChange?(state: DraftState): void
+  /** Remediation M1 R1-11: machine-wide running-browser limit, when known. */
+  machineLimit?: number | null
 }
 
-export function RunPolicyEditor({ value, onChange, dataBatch = false, disabled = false, errors = {}, resetKey, onDraftStateChange }: RunPolicyEditorProps) {
+export function RunPolicyEditor({ value, onChange, dataBatch = false, disabled = false, errors = {}, resetKey, onDraftStateChange, machineLimit }: RunPolicyEditorProps) {
   const [maxTasksDraft, setMaxTasksDraft] = useState(String(value.maxTasks ?? ''))
   const [timeoutDraft, setTimeoutDraft] = useState(String(value.automaticExecutionTimeoutSeconds / 60))
   const pendingMaxTasks = useRef<number | undefined>(undefined), pendingTimeout = useRef<number | undefined>(undefined)
@@ -69,7 +71,7 @@ export function RunPolicyEditor({ value, onChange, dataBatch = false, disabled =
         setLimits(previous => ({ ...previous, [key]: draft }))
         if (draft.trim() && Number.isInteger(parsed) && parsed >= 1 && parsed <= 100) onChange({ ...value, [key]: parsed })
       }}/>
-      {limitErrors[key] ? <span role="alert" id={`run-policy-${key}-error`} className="text-xs text-danger">{limitErrors[key]}</span> : <span className="text-xs text-muted">范围 1–100</span>}
+      {limitErrors[key] ? <span role="alert" id={`run-policy-${key}-error`} className="text-xs text-danger">{limitErrors[key]}</span> : <span className="text-xs text-muted">范围 1–100{key === 'concurrency' && machineLimit ? `；本机当前最多同时运行 ${machineLimit} 个浏览器${Number(limits.concurrency) > machineLimit ? `，实际同时运行不超过 ${machineLimit} 个` : ''}` : ''}</span>}
     </label>)}
     <label className="grid gap-2 text-sm md:grid-cols-[11rem_minmax(0,1fr)] md:items-center"><span className="font-medium">失败处理</span><span className="flex items-center gap-3">
       <Switch aria-label="任务失败后继续下一个任务" checked={value.continueAfterFailure} disabled={disabled} onCheckedChange={continueAfterFailure => onChange({ ...value, continueAfterFailure })}/>
```

`apps/desktop/src/renderer/domains/project-automations/components/AutomationEditor.tsx`：

```diff
diff --git a/apps/desktop/src/renderer/domains/project-automations/components/AutomationEditor.tsx b/apps/desktop/src/renderer/domains/project-automations/components/AutomationEditor.tsx
--- a/apps/desktop/src/renderer/domains/project-automations/components/AutomationEditor.tsx
+++ b/apps/desktop/src/renderer/domains/project-automations/components/AutomationEditor.tsx
@@ -27,6 +27,7 @@ export type AutomationEditorProps = {
   error?: string
   serverErrors?: Record<string, string | undefined>
   validationNotice?: ReactNode
+  machineLimit?: number | null
   environmentOptions: Pick<EnvironmentPolicyEditorProps, 'profiles' | 'proxies' | 'pools' | 'modelProviders' | 'projectDefaults' | 'environments'>
   renderInputPlan(value: AutomationWrite['inputPlan'], onChange: (value: AutomationWrite['inputPlan']) => void, disabled: boolean, draft: { resetKey: string; errors: Record<string, string | undefined>; onDraftStateChange(state: DraftState): void }): ReactNode
   onSubmit(value: AutomationWrite): void | Promise<void>
@@ -47,7 +48,7 @@ const tabFor = (field: string): Tab => field.startsWith('inputPlan') || field.st
 const valueAt = (value: unknown, path: string) => path.split('.').reduce<unknown>((current, part) => current && typeof current === 'object' ? (current as Record<string, unknown>)[part] : undefined, value)
 const typedSnapshot = (value: unknown) => JSON.stringify([value])
 
-export function AutomationEditor({ initialValue, resetKey, workflowOptions, isNew = false, disabled = false, saving = false, recovering = false, error, serverErrors = {}, validationNotice, environmentOptions, renderInputPlan, onSubmit, onCancel, onDraftStateChange, onOpenStudio, onStartRun }: AutomationEditorProps) {
+export function AutomationEditor({ machineLimit, initialValue, resetKey, workflowOptions, isNew = false, disabled = false, saving = false, recovering = false, error, serverErrors = {}, validationNotice, environmentOptions, renderInputPlan, onSubmit, onCancel, onDraftStateChange, onOpenStudio, onStartRun }: AutomationEditorProps) {
   const locked = disabled || saving || recovering
   const [activeTab, setActiveTab] = useState<Tab>('overview')
   const [inputDraft, setInputDraft] = useState<DraftState>({ dirty: false, valid: true })
@@ -135,7 +136,7 @@ export function AutomationEditor({ initialValue, resetKey, workflowOptions, isNe
       </TabsContent>
       <TabsContent forceMount value="inputs" hidden={activeTab !== 'inputs'} data-tab-panel="inputs" className="min-h-[22rem] py-5"><div className="grid gap-7">{renderInputPlan(value.inputPlan, next => change('inputPlan', next), locked, { resetKey, onDraftStateChange: setInputDraft, errors: Object.fromEntries(Object.entries(errors).flatMap(([path, message]) => { const match = /^inputPlan\.inputs\.(\d+)(?:\.(.*))?$/.exec(path); const item = match ? value.inputPlan.inputs[Number(match[1])] : undefined; return item ? [[`${item.inputId}.${match?.[2] ?? 'configuration'}`, message]] : [] })) })}<ParameterEditor value={value.parameterSchema} onChange={next => change('parameterSchema', next)} disabled={locked} errors={parameterErrors} resetKey={resetKey} onDraftStateChange={setParameterDraft}/></div></TabsContent>
       <TabsContent forceMount value="resources" hidden={activeTab !== 'resources'} data-tab-panel="resources" className="min-h-[22rem] py-5"><EnvironmentPolicyEditor nodeBrowserMode={nodeBrowserMode} value={value.environmentPolicy} inputs={value.inputPlan.inputs} onChange={next => change('environmentPolicy', next)} disabled={locked} errors={fieldErrors('environmentPolicy.')} {...environmentOptions}/></TabsContent>
-      <TabsContent forceMount value="run" hidden={activeTab !== 'run'} data-tab-panel="run" className="min-h-[22rem] py-5"><RunPolicyEditor dataBatch={value.inputPlan.inputs.length > 0} value={value.runPolicy} onChange={next => change('runPolicy', { ...next, maxTasks: next.maxTasks ?? value.runPolicy.maxTasks })} disabled={locked} errors={fieldErrors('runPolicy.')} resetKey={resetKey} onDraftStateChange={setRunDraft}/></TabsContent>
+      <TabsContent forceMount value="run" hidden={activeTab !== 'run'} data-tab-panel="run" className="min-h-[22rem] py-5"><RunPolicyEditor dataBatch={value.inputPlan.inputs.length > 0} value={value.runPolicy} onChange={next => change('runPolicy', { ...next, maxTasks: next.maxTasks ?? value.runPolicy.maxTasks })} disabled={locked} errors={fieldErrors('runPolicy.')} resetKey={resetKey} onDraftStateChange={setRunDraft} machineLimit={machineLimit}/></TabsContent>
     </Tabs>
     {activeTab !== 'resources' ? <aside aria-label="配置摘要" className="mx-5 flex flex-wrap items-center gap-4 border-t border-line py-4 text-sm"><strong className="mr-4">配置摘要</strong><span className="flex items-center gap-2 border-l border-line pl-4"><SlidersHorizontal size={21} aria-hidden/>{value.parameterSchema.length} 个参数</span><span className="flex items-center gap-2 border-l border-line pl-4"><Browser size={21} aria-hidden/>{nodeBrowserMode ? '由工作流节点配置环境' : value.environmentPolicy.source === 'newFromProfile' ? '临时浏览器环境' : '已保存的环境策略'}</span><span className="flex items-center gap-2 border-l border-line pl-4"><FileText size={21} aria-hidden/>最多 {value.runPolicy.maxTasks} 个任务</span><span className="flex items-center gap-2 border-l border-line pl-4"><Lightning size={21} aria-hidden/>{`配置并发上限 ${Math.min(value.runPolicy.concurrency, value.runPolicy.maxLiveInstances)}`}</span></aside> : null}
     <footer className="sticky bottom-0 z-10 rounded-b-card bg-surface flex flex-wrap items-center justify-between gap-3 border-t border-line px-5 py-4"><span className="flex items-center gap-2 text-sm text-muted"><Info size={18} aria-hidden/>{recovering ? '正在核对保存结果…' : saving ? '正在保存配置…' : dirty ? '有未保存的修改' : '没有未保存的修改'}</span><div className="flex gap-2"><Button disabled={locked || !dirty} onClick={onCancel}>取消修改</Button><Button variant="primary" loading={saving || recovering} loadingText={recovering ? '正在核对…' : '正在保存…'} disabled={locked || !dirty} onClick={() => void submit()}>保存配置</Button></div></footer>
```

`apps/desktop/src/renderer/domains/project-automations/pages/AutomationDetailPage.tsx`：

```diff
diff --git a/apps/desktop/src/renderer/domains/project-automations/pages/AutomationDetailPage.tsx b/apps/desktop/src/renderer/domains/project-automations/pages/AutomationDetailPage.tsx
--- a/apps/desktop/src/renderer/domains/project-automations/pages/AutomationDetailPage.tsx
+++ b/apps/desktop/src/renderer/domains/project-automations/pages/AutomationDetailPage.tsx
@@ -17,6 +17,7 @@ import { useAutomationCommand } from '../use-automation-command'
 import { BatchLauncher } from '../../project-runs/components/BatchLauncher'
 import { safeProjectError } from '../../projects/presentation-error'
 import { createEnvironmentApi } from '../../environments/api'
+import { createExecutionSettingsApi } from '../../settings/executionApi'
 
 export type AutomationDetailPageProps = {
   projectDefaults?: ProjectView['defaultResources'];
@@ -50,6 +51,7 @@ function Detail({ projectDefaults, workspaceKey, instanceId, projectId, automati
   const proxies = useQuery({ queryKey: [workspaceKey, instanceId, 'automation-proxies'], queryFn: ({ signal }) => resources.proxies(signal), enabled: !disabled })
   const models = useQuery({ queryKey: [workspaceKey, instanceId, 'automation-models'], queryFn: ({ signal }) => resources.models(signal), enabled: !disabled })
   const tables = useQuery({ queryKey: [...prefix, 'input-tables'], queryFn: ({ signal }) => resources.tables(signal), enabled: !disabled })
+  const executionSettings = useQuery({ queryKey: ['execution-settings', workspaceKey], queryFn: () => createExecutionSettingsApi(client).read(), enabled: !disabled })
   const environments = useQuery({ queryKey: [...prefix, 'saved-environments'], queryFn: ({ signal }) => createEnvironmentApi(client, projectId).list({ query: '', page: 1, pageSize: 200, sort: 'name' }, signal), enabled: !disabled })
   const validation = useQuery({ queryKey: [...prefix, 'validation', automationId], queryFn: ({ signal }) => api.validation(automationId!, signal), enabled: Boolean(automationId) && !disabled })
   const [baseline, setBaseline] = useState<Baseline | null>(() => automationId ? null : { value: emptyAutomationForm(), revision: 0, resetKey: crypto.randomUUID() })
@@ -123,7 +125,7 @@ function Detail({ projectDefaults, workspaceKey, instanceId, projectId, automati
     {readErrors.length > 0 ? <div role="alert" className="rounded-control border border-warning/40 bg-surface p-3 text-sm"><p>部分资料读取失败，当前草稿已保留。{readErrors.map(safeProjectError).join('；')}</p><Button size="sm" onClick={() => { void workflows.refetch(); void profiles.refetch(); void proxies.refetch(); void models.refetch(); void tables.refetch(); void environments.refetch(); if (automationId) void result.refetch(); if (recordTable) void records.refetch() }}>重新读取资料</Button></div> : null}
     {command.recovering ? <div role="alert" className="flex flex-wrap items-center gap-3 border border-warning/40 bg-surface p-3 text-sm"><span>{command.notAccepted ? '原请求尚未接受，可以重试原请求或继续编辑。' : '保存结果尚未确认，请先核对原操作。'}</span><Button size="sm" disabled={disabled || command.busy} onClick={() => void command.lookup()}>核对保存结果</Button>{command.notAccepted ? <><Button size="sm" disabled={disabled || readOnly || command.busy} onClick={() => void command.retry()}>重试原请求</Button><Button size="sm" variant="ghost" disabled={command.busy} onClick={command.discardNotAccepted}>继续编辑</Button></> : null}</div> : null}
     {command.conflict ? <div role="alert" className="flex flex-wrap items-center gap-3 border border-warning/40 bg-surface p-3 text-sm"><p>自动化资料已变化，你的输入已保留。最新名称：{latestConflict?.name ?? '尚未读取'}。</p><Button size="sm" disabled={disabled || result.isFetching} onClick={() => setReloadConflict(value => value + 1)}>读取最新资料</Button><Button size="sm" disabled={!latestConflict || disabled} onClick={() => setConfirmation('latest')}>载入最新资料重新编辑</Button></div> : null}
-    <AutomationEditor onOpenStudio={onOpenStudio} onStartRun={automationId && onBatchCreated ? () => { setStartOpen(true); void validation.refetch() } : undefined} validationNotice={automationId && validation.data && !validation.data.runnable ? <details className="mx-5 border-b border-line py-2 text-sm"><summary className="cursor-pointer text-muted">查看运行条件 · 尚未满足</summary><ul className="mb-0 mt-2 pl-5">{validation.data.issues.map((issue, index) => <li key={`${issue.code}:${index}`}>{safeProjectError(issue)}</li>)}</ul><p className="mb-0 text-muted">可以继续维护配置，保存配置不代表开始运行。</p></details> : null} initialValue={baseline.value} resetKey={baseline.resetKey} isNew={!automationId} disabled={disabled || readOnly} saving={command.busy} recovering={command.recovering} error={command.error} serverErrors={command.fields}
+    <AutomationEditor machineLimit={executionSettings.data?.effectiveMaxRunningBrowsers} onOpenStudio={onOpenStudio} onStartRun={automationId && onBatchCreated ? () => { setStartOpen(true); void validation.refetch() } : undefined} validationNotice={automationId && validation.data && !validation.data.runnable ? <details className="mx-5 border-b border-line py-2 text-sm"><summary className="cursor-pointer text-muted">查看运行条件 · 尚未满足</summary><ul className="mb-0 mt-2 pl-5">{validation.data.issues.map((issue, index) => <li key={`${issue.code}:${index}`}>{safeProjectError(issue)}</li>)}</ul><p className="mb-0 text-muted">可以继续维护配置，保存配置不代表开始运行。</p></details> : null} initialValue={baseline.value} resetKey={baseline.resetKey} isNew={!automationId} disabled={disabled || readOnly} saving={command.busy} recovering={command.recovering} error={command.error} serverErrors={command.fields}
       workflowOptions={(workflows.data?.items ?? []).map(workflow => ({ id: workflow.workflowId, name: workflow.name, browserEnvironmentVersion: workflow.browserEnvironmentVersion, revision: workflow.revision, updatedAt: workflow.updatedAt, runnable: workflow.validation.runnable, validationMessage: workflow.validation.issues.map(safeProjectError).join('；') }))}
       environmentOptions={{ projectDefaults, profiles: profiles.data?.items ?? [], proxies: (proxies.data?.proxies ?? []).filter(proxy => proxy.enabled), pools: proxies.data?.pools ?? [], modelProviders: (models.data?.items ?? []).filter(provider => provider.enabled).map(provider => ({ id: provider.id, name: provider.name })), environments: (environments.data?.items ?? []).map(item => ({ id: item.ref.environmentId, name: item.name })) }}
       renderInputPlan={(value, onChange, locked, draft) => <><InputPlanEditor {...draft} value={value} onChange={onChange} disabled={locked} tables={options} onLoadRecords={id => { setRecordTableId(id); setRecordPage(1) }} />{records.isFetching ? <p role="status" className="text-sm text-muted">正在读取记录…</p> : null}{records.data && records.data.total > 200 ? <Pagination offset={(recordPage - 1) * 200} limit={200} count={records.data.items.length} total={records.data.total} disabled={records.isFetching || locked} showPage onOffsetChange={offset => setRecordPage(Math.floor(offset / 200) + 1)} /> : null}</>}
```

- [ ] **Step 5: 运行**

Run: `npm --workspace @autoflow/desktop test -- src/renderer/domains/settings src/renderer/domains/project-automations`
Expected: 全部通过。
Run: `npm run typecheck && npm run lint`
Expected: 无错误。

- [ ] **Step 6: 提交**

```bash
git add apps/desktop/src/renderer/domains/settings apps/desktop/src/renderer/app/App.tsx apps/desktop/src/renderer/domains/project-automations
git commit -m "feat(settings): 设置页可调整同时运行的浏览器数，自动化显示本机实际上限"
```

---

### Task 10: 领取移出服务主循环（R1-12）

**Files:**
- Modify: `apps/backend/src/autoflow/application/project_runs/scheduler.py`
- Create: `apps/backend/tests/benchmarks/bench_claim_loop_lag.py`
- Modify: `apps/backend/tests/benchmarks/test_offline_benchmarks.py`
- Test: `apps/backend/tests/integration/test_project_claim_off_loop.py`

**Interfaces:**
- Consumes: `LoopLagMonitor`（M0）、`bench_claims._seed`、`bench_claims.plans`（M0 Task 1）。
- Produces: `bench_claim_loop_lag.run(rows: int) -> dict`（键：`rows`、`claim_ms`、`loop_lag_p50_ms`、`loop_lag_max_ms`）。

- [ ] **Step 1: 写失败的测试**

`apps/backend/tests/integration/test_project_claim_off_loop.py`：

```python
"""Remediation M1 R1-12: data claims never run on the event-loop thread."""

import threading

import pytest

from tests.integration.test_project_data_scheduler import data_services, start  # noqa: F401 - fixture reuse


@pytest.mark.asyncio
async def test_data_claims_run_off_the_event_loop(data_services, monkeypatch):  # noqa: F811
    _factory, _project, _automation, _coordinator, _worker, core, scheduler = data_services
    loop_thread = threading.get_ident()
    seen: list[int] = []
    original = scheduler._claim_data_task

    def spy(project_id, batch_id):
        seen.append(threading.get_ident())
        return original(project_id, batch_id)

    monkeypatch.setattr(scheduler, "_claim_data_task", spy)
    start(data_services, 1)
    await scheduler.tick()
    await core.wait_idle()
    assert seen, "the batch never claimed a row"
    assert all(ident != loop_thread for ident in seen)
```

- [ ] **Step 2: 运行，确认失败**

Run: `uv run --directory apps/backend pytest -q tests/integration/test_project_claim_off_loop.py`
Expected: FAIL，`seen` 中的线程等于事件循环线程。

- [ ] **Step 3: 实现**

`application/project_runs/scheduler.py` 的 `_advance_data` 中，把

```python
                claim_outcome = self._claim_data_task(project_id, batch_id)
```

替换为

```python
                # Spec M1 R1-12: a claim may scan thousands of rows; keep it off the event loop.
                claim_outcome = await asyncio.to_thread(
                    self._claim_data_task, project_id, batch_id
                )
```

- [ ] **Step 4: 主循环延迟基准**

`tests/benchmarks/bench_claim_loop_lag.py`：

```python
"""Loop lag while a large claim runs through the scheduler's thread path (remediation M1, AC1-09).

Run: uv run --directory apps/backend python -m tests.benchmarks.bench_claim_loop_lag --rows 10000
"""

from __future__ import annotations

import argparse
import asyncio
import tempfile
import time
from pathlib import Path

from autoflow.infrastructure.database.project_claims import SqlAlchemyProjectInputGroups
from autoflow.infrastructure.observability import LoopLagMonitor

from .bench_claims import _seed, plans
from .report import Unit, write_report


async def _run(rows: int) -> dict[str, tuple[float, Unit]]:
    with tempfile.TemporaryDirectory() as raw:
        factory, project_id, table, field = _seed(Path(raw), rows)
        plan = plans(project_id, table, field)["claim_ms_key_order"]

        def claim() -> str:
            with factory() as session:
                return SqlAlchemyProjectInputGroups(session).select_required(project_id, plan).status

        monitor = LoopLagMonitor()
        await monitor.start()
        try:
            await asyncio.sleep(0.3)
            monitor.reset()
            started = time.perf_counter()
            status = await asyncio.to_thread(claim)
            elapsed_ms = (time.perf_counter() - started) * 1000
            await asyncio.sleep(0.1)
            snapshot = monitor.snapshot()
        finally:
            await monitor.stop()
            factory.dispose()
    if status != "ready":
        raise RuntimeError(f"unexpected selection status {status}")
    return {
        "rows": (rows, "count"),
        "claim_ms": (elapsed_ms, "ms"),
        "loop_lag_p50_ms": (snapshot.p50_ms, "ms"),
        "loop_lag_max_ms": (snapshot.max_ms, "ms"),
    }


def run(rows: int) -> dict[str, tuple[float, Unit]]:
    return asyncio.run(_run(rows))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--rows", type=int, default=10000)
    arguments = parser.parse_args()
    write_report(f"claim-loop-lag-{arguments.rows}", run(arguments.rows))


if __name__ == "__main__":
    main()
```

在 `test_offline_benchmarks.py` 的 import 中加入 `bench_claim_loop_lag`，并追加：

```python
def test_claim_loop_lag_benchmark_keeps_the_loop_responsive():
    metrics = bench_claim_loop_lag.run(2000)
    assert metrics["loop_lag_p50_ms"][0] < 10
    assert metrics["loop_lag_max_ms"][0] < 250  # AC1-09
```

- [ ] **Step 5: 运行**

Run: `uv run --directory apps/backend pytest -q tests/integration/test_project_claim_off_loop.py tests/integration/test_project_data_scheduler.py tests/integration/test_project_parameter_concurrency.py`
Expected: 全部通过。
Run: `uv run --directory apps/backend pytest -q -m benchmark tests/benchmarks && uv run --directory apps/backend python -m tests.benchmarks.bench_claim_loop_lag --rows 10000`
Expected: 通过；1 万行时 `loop_lag_max_ms` < 250（原型：领取 2.4 秒期间最大延迟 129 毫秒；同样的领取放在主循环内是 1,935 毫秒）。

- [ ] **Step 6: 提交**

```bash
git add apps/backend/src/autoflow/application/project_runs/scheduler.py apps/backend/tests/benchmarks/bench_claim_loop_lag.py apps/backend/tests/benchmarks/test_offline_benchmarks.py apps/backend/tests/integration/test_project_claim_off_loop.py
git commit -m "perf(scheduler): 数据领取在线程中执行，不再阻塞服务主循环"
```

---

### Task 11: worker 标准错误保存为诊断日志（R1-14）

**Files:**
- Create: `apps/backend/src/autoflow/infrastructure/process/stderr_sink.py`
- Modify: `apps/backend/src/autoflow/infrastructure/process/project_workflow_worker.py`
- Test: `apps/backend/tests/unit/test_stderr_sink.py`、`apps/backend/tests/integration/test_worker_stderr_diagnostics.py`

**Interfaces:**
- Produces: `StderrSink(path, *, limit_bytes=5*1024*1024, tail_lines=200)`、`async drain(stream)`、`tail(lines=50) -> list[str]`、`TRUNCATED_MARKER`；`WorkflowWorkerError(code, message, details=None)` 增加 `details`；`project_workflow_worker.STDERR_LOG_NAME = "worker-stderr.log"`；`WORKFLOW_WORKER_LOST` 的 `details = {"diagnosticLog": "runs/<runId>/generation-<n>/worker-stderr.log", "stderrTail": [...最后 50 行]}`。

- [ ] **Step 1: 写失败的测试**

`tests/unit/test_stderr_sink.py`：

```python
import asyncio
import sys

import pytest

from autoflow.infrastructure.process.stderr_sink import TRUNCATED_MARKER, StderrSink


async def _drain(sink: StderrSink, script: str) -> int:
    process = await asyncio.create_subprocess_exec(sys.executable, "-c", script, stderr=asyncio.subprocess.PIPE)
    assert process.stderr is not None
    await sink.drain(process.stderr)
    return await process.wait()


@pytest.mark.asyncio
async def test_worker_stderr_is_kept_on_disk_with_a_tail(tmp_path):
    sink = StderrSink(tmp_path / "run" / "worker-stderr.log")
    code = await _drain(sink, "import sys\nfor i in range(300): print(f'line {i}', file=sys.stderr)\nsys.exit(3)")
    assert code == 3
    lines = (tmp_path / "run" / "worker-stderr.log").read_text(encoding="utf-8").splitlines()
    assert lines[0] == "line 0" and lines[-1] == "line 299"
    assert sink.tail(50) == [f"line {i}" for i in range(250, 300)]


@pytest.mark.asyncio
async def test_oversized_stderr_is_truncated_but_tail_keeps_the_end(tmp_path):
    path = tmp_path / "worker-stderr.log"
    sink = StderrSink(path, limit_bytes=100, tail_lines=5)
    await _drain(sink, "import sys\nfor i in range(50): print('x' * 20 + str(i), file=sys.stderr)")
    content = path.read_text(encoding="utf-8")
    assert content.endswith(TRUNCATED_MARKER)
    assert len(content.encode("utf-8")) <= 100 + len(TRUNCATED_MARKER.encode("utf-8"))
    assert sink.tail(1) == ["x" * 20 + "49"]
```

`apps/backend/tests/integration/test_worker_stderr_diagnostics.py`：

```python
"""Remediation M1 R1-14: a crashing worker leaves a diagnostic log."""

import asyncio
import sys
from uuid import uuid4

import pytest

from autoflow.infrastructure.process.project_workflow_worker import (
    ProjectWorkflowWorkerManager,
    WorkflowWorkerError,
)

CRASH = (
    "import sys\n"
    "sys.stdin.readline()\n"
    "print('worker exploded: KeyError token', file=sys.stderr, flush=True)\n"
    "sys.exit(7)\n"
)


@pytest.mark.asyncio
async def test_lost_worker_points_to_its_stderr_log(tmp_path):
    manager = ProjectWorkflowWorkerManager(tmp_path / "tmp" / "worker", command=(sys.executable, "-c", CRASH))
    run_id = str(uuid4())

    async def ignore(_event):
        return None

    try:
        with pytest.raises(WorkflowWorkerError) as lost:
            await asyncio.wait_for(manager.run(
                run_id=run_id, execution_generation=1, execution_plan={}, parameters={},
                variables={}, browser={}, executable=None, on_event=ignore,
            ), 15)
    finally:
        await manager.shutdown()
    error = lost.value
    assert error.code == "WORKFLOW_WORKER_LOST"
    log = f"runs/{run_id}/generation-1/worker-stderr.log"
    assert f"诊断日志：{log}" in error.message
    assert error.details["stderrTail"] == ["worker exploded: KeyError token"]
    written = tmp_path / "tmp" / "workspace" / log
    assert written.read_text(encoding="utf-8") == "worker exploded: KeyError token\n"
```

- [ ] **Step 2: 运行，确认失败**

Run: `uv run --directory apps/backend pytest -q tests/unit/test_stderr_sink.py tests/integration/test_worker_stderr_diagnostics.py`
Expected: FAIL，`ModuleNotFoundError: ...stderr_sink`。

- [ ] **Step 3: 实现 StderrSink**

`apps/backend/src/autoflow/infrastructure/process/stderr_sink.py`：

```python
"""Bounded capture of a worker's standard error (remediation M1, R1-14)."""

from __future__ import annotations

import asyncio
from collections import deque
from pathlib import Path

TRUNCATED_MARKER = "\n[已截断：诊断日志超过上限]\n"


class StderrSink:
    def __init__(self, path: Path, *, limit_bytes: int = 5 * 1024 * 1024, tail_lines: int = 200) -> None:
        self.path = path
        self._limit = limit_bytes
        self._written = 0
        self._truncated = False
        self._tail: deque[str] = deque(maxlen=tail_lines)

    def tail(self, lines: int = 50) -> list[str]:
        return list(self._tail)[-lines:]

    async def drain(self, stream: asyncio.StreamReader) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("ab") as output:
            while True:
                line = await stream.readline()
                if not line:
                    return
                self._tail.append(line.decode("utf-8", "replace").rstrip("\r\n"))
                if self._truncated:
                    continue
                if self._written + len(line) > self._limit:
                    output.write(TRUNCATED_MARKER.encode("utf-8"))
                    output.flush()
                    self._truncated = True
                    continue
                output.write(line)
                output.flush()
                self._written += len(line)
```

- [ ] **Step 4: 接入 worker 管理器**

`infrastructure/process/project_workflow_worker.py`：
1. `import asyncio` 之后加 `import contextlib`；`from .proxy_worker_requests import ProxyWorkerRequests` 之后加：

```python
from .stderr_sink import StderrSink

STDERR_LOG_NAME = "worker-stderr.log"
```

2. `WorkflowWorkerError.__init__` 改为：

```python
    def __init__(self, code: str, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details or {}
```

3. `_Worker` 末尾加两个字段：

```python
    stderr: StderrSink | None = None
    stderr_task: asyncio.Task[None] | None = None
```

4. 启动子进程时 `stderr=asyncio.subprocess.DEVNULL` 改为 `stderr=asyncio.subprocess.PIPE`。
5. `_capture_birth` 改为下面的实现，并在其后新增 `_lost`（两条启动路径都会调用 `_capture_birth`，因此都会挂上诊断日志）：

```python
    def _capture_birth(self, worker: _Worker) -> None:
        assert worker.process is not None
        worker.birth = process_birth(worker.process.pid)
        if worker.process.stderr is not None and worker.stderr_task is None:
            worker.stderr = StderrSink(worker.artifact_directory / STDERR_LOG_NAME)
            worker.stderr_task = asyncio.create_task(worker.stderr.drain(worker.process.stderr))

    async def _lost(self, worker: _Worker, message: str) -> WorkflowWorkerError:
        """Spec M1 R1-14: a lost worker points at its diagnostic log and carries its last lines."""
        if worker.stderr_task is not None:
            with contextlib.suppress(Exception):
                await asyncio.wait_for(asyncio.shield(worker.stderr_task), 1)
        if worker.stderr is None:
            return WorkflowWorkerError("WORKFLOW_WORKER_LOST", message)
        log = f"{worker.relative_artifact_directory}/{STDERR_LOG_NAME}"
        return WorkflowWorkerError(
            "WORKFLOW_WORKER_LOST", f"{message}（诊断日志：{log}）",
            {"diagnosticLog": log, "stderrTail": worker.stderr.tail(50)},
        )
```

6. 三处 `raise WorkflowWorkerError("WORKFLOW_WORKER_LOST", "<消息>")` 改为 `raise await self._lost(worker, "<消息>")`（消息文字不变：一处"执行进程异常退出，需核验运行结果"，两处"执行进程失联，运行结果待核验"）。

- [ ] **Step 5: 运行**

Run: `uv run --directory apps/backend pytest -q tests/unit/test_stderr_sink.py tests/integration/test_worker_stderr_diagnostics.py tests/integration/test_project_browserless_end.py tests/integration/test_workflow_worker_process.py tests/integration/test_workflow_dispatch.py`
Expected: 全部通过。

- [ ] **Step 6: 提交**

```bash
git add apps/backend/src/autoflow/infrastructure/process/stderr_sink.py apps/backend/src/autoflow/infrastructure/process/project_workflow_worker.py apps/backend/tests/unit/test_stderr_sink.py apps/backend/tests/integration/test_worker_stderr_diagnostics.py
git commit -m "fix(worker): 保存 worker 标准错误为诊断日志，失联时附日志位置与最后几行"
```

---

### Task 12: 按键节点——后端（R1-15）

**Files:**
- Modify: `apps/backend/src/autoflow/application/workflows/executors/web_basic.py`
- Modify: `apps/backend/src/autoflow/providers/browser/workflow_session.py`、`apps/backend/src/autoflow/domain/workflows/browser.py`
- Modify: `apps/backend/src/autoflow/domain/workflows/scope.py`、`apps/backend/src/autoflow/domain/workflows/catalog.py`、`apps/backend/src/autoflow/providers/assistant/langgraph.py`
- Modify: `apps/backend/tests/unit/workflows/test_executor_registry.py`
- Test: `apps/backend/tests/unit/workflows/test_press_key_executor.py`、`apps/backend/tests/integration/test_press_key_real_cloakbrowser.py`

**Interfaces:**
- Produces: 节点类型 `press_key`，配置 `key`、`targetType`（focused / element，默认 focused）、`selector`、`timeout`（秒，默认 30，0 表示不限）；`BrowserLocatorPort.press(key, *, timeout_ms=None)`；`scope.WEB_EXTENSION_NODE_TYPES = frozenset({'press_key'})`。Task 13 的前端与录制器生成该节点。

- [ ] **Step 1: 写失败的测试**

`apps/backend/tests/unit/workflows/test_press_key_executor.py`：

```python
"""Remediation M1 R1-15: the web press_key node."""

from typing import Any

import pytest

from autoflow.application.workflows.executors.production import build_production_executor_registry
from autoflow.application.workflows.executors.web_basic import PressKeyExecutor
from autoflow.domain.workflows.execution import ExecutionContext


class FakeLocator:
    def __init__(self, page: "FakePage", selector: str) -> None:
        self.page, self.selector = page, selector

    async def wait_for(self, **options: Any) -> None:
        if self.selector == "#missing":
            raise TimeoutError("waiting for #missing")
        self.page.calls.append(("wait", self.selector, options["state"]))

    async def press(self, key: str, *, timeout_ms: float | None = None) -> None:
        self.page.calls.append(("press", self.selector, key, timeout_ms))


class FakePage:
    id = "page-1"
    url = "about:blank"
    closed = False

    def __init__(self) -> None:
        self.calls: list[tuple[Any, ...]] = []

    def locator(self, selector: str) -> FakeLocator:
        return FakeLocator(self, selector)

    async def keyboard_press(self, key: str) -> None:
        self.calls.append(("keyboard", key))


class FakeSession:
    def __init__(self, page: FakePage) -> None:
        self.page = page

    def active_page(self) -> FakePage:
        return self.page


def _context(page: FakePage) -> ExecutionContext:
    return ExecutionContext(browser=FakeSession(page))  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_element_mode_waits_for_the_element_then_presses_on_it():
    page = FakePage()
    result = await PressKeyExecutor().execute(
        {"key": "Enter", "targetType": "element", "selector": "#name", "timeout": 5}, _context(page)
    )
    assert result.success, result.error
    assert page.calls == [("wait", "#name", "visible"), ("press", "#name", "Enter", 5000)]


@pytest.mark.asyncio
async def test_focused_mode_presses_on_the_page_and_supports_combinations():
    page = FakePage()
    result = await PressKeyExecutor().execute({"key": "Control+A"}, _context(page))
    assert result.success
    assert page.calls == [("keyboard", "Control+A")]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("config", "reason"),
    [
        ({"key": ""}, "按键不能为空"),
        ({"key": "Enter", "targetType": "element"}, "元素模式需要选择器"),
        ({"key": "Enter", "targetType": "window"}, "不支持的按键目标"),
        ({"key": "Enter", "targetType": "element", "selector": "#missing"}, "waiting for #missing"),
    ],
)
async def test_invalid_or_failing_presses_report_the_reason(config, reason):
    result = await PressKeyExecutor().execute(config, _context(FakePage()))
    assert not result.success
    assert reason in (result.error or "")


def test_press_key_is_a_production_web_node():
    registry = build_production_executor_registry()
    assert "press_key" in registry.get_all_types()
    assert PressKeyExecutor().requires_browser
```

真实浏览器用例（未设置 `AUTOFLOW_TEST_CLOAKBROWSER` 时跳过），`tests/integration/test_press_key_real_cloakbrowser.py`：

```python
"""Remediation M1 AC1-13: press_key against a real CloakBrowser page."""

import os
from pathlib import Path

import pytest
import pytest_asyncio

from autoflow.application.workflows.executors.web_basic import PressKeyExecutor
from autoflow.domain.workflows.execution import ExecutionContext
from autoflow.providers.browser.workflow_session import CloakBrowserWorkflowSession

FORM = (
    "data:text/html,<form onsubmit=\"document.title='sent';return false\">"
    "<input id=q autofocus><input id=next></form>"
)


@pytest_asyncio.fixture
async def real_cloak_context(tmp_path, monkeypatch):
    configured = os.environ.get("AUTOFLOW_TEST_CLOAKBROWSER")
    if not configured:
        pytest.skip("set AUTOFLOW_TEST_CLOAKBROWSER to an installed real CloakBrowser executable")
    monkeypatch.setenv("CLOAKBROWSER_BINARY_PATH", str(Path(configured).resolve(strict=True)))
    monkeypatch.setenv("CLOAKBROWSER_CACHE_DIR", str(tmp_path / "cache"))
    from cloakbrowser import launch_context_async  # type: ignore[import-untyped]

    context = await launch_context_async(headless=True)
    try:
        yield context
    finally:
        await context.close()


@pytest.mark.asyncio
async def test_enter_on_an_element_submits_and_tab_moves_focus(real_cloak_context):
    page = real_cloak_context.pages[0] if real_cloak_context.pages else await real_cloak_context.new_page()
    await page.goto(FORM)
    context = ExecutionContext(browser=CloakBrowserWorkflowSession(real_cloak_context))
    tab = await PressKeyExecutor().execute({"key": "Tab"}, context)
    assert tab.success, tab.error
    assert await page.evaluate("document.activeElement.id") == "next"
    enter = await PressKeyExecutor().execute({"key": "Enter", "targetType": "element", "selector": "#q"}, context)
    assert enter.success, enter.error
    assert await page.title() == "sent"
```

- [ ] **Step 2: 运行，确认失败**

Run: `uv run --directory apps/backend pytest -q tests/unit/workflows/test_press_key_executor.py`
Expected: FAIL，`ImportError: cannot import name 'PressKeyExecutor'`。

- [ ] **Step 3: 执行器与定位器**

`apps/backend/src/autoflow/application/workflows/executors/web_basic.py`：

```diff
diff --git a/apps/backend/src/autoflow/application/workflows/executors/web_basic.py b/apps/backend/src/autoflow/application/workflows/executors/web_basic.py
--- a/apps/backend/src/autoflow/application/workflows/executors/web_basic.py
+++ b/apps/backend/src/autoflow/application/workflows/executors/web_basic.py
@@ -29,6 +29,8 @@ class _Locator(Protocol):
 
     async def hover(self, **options: Any) -> None: ...
 
+    async def press(self, key: str, *, timeout_ms: float | None = None) -> None: ...
+
 
 class _ElementHandle(Protocol):
     async def content_frame(self) -> _Page | None: ...
@@ -328,6 +330,44 @@ class HoverElementExecutor(ModuleExecutor):
             return ModuleResult(success=False, error=f"悬停元素失败: {error}")
 
 
+@register_executor
+class PressKeyExecutor(ModuleExecutor):
+    """Web key press on an element or the focused page (remediation M1, R1-15)."""
+
+    requires_browser = True
+
+    @property
+    def module_type(self) -> str:
+        return "press_key"
+
+    async def execute(
+        self, config: dict[str, Any], context: ExecutionContext
+    ) -> ModuleResult:
+        key = str(context.resolve_value(config.get("key", "")) or "").strip()
+        target = str(config.get("targetType") or "focused")
+        selector = str(context.resolve_value(config.get("selector", "")) or "").strip()
+        timeout_seconds = to_int(config.get("timeout", 30), 30, context)
+        timeout = None if timeout_seconds == 0 else timeout_seconds * 1000
+        if not key:
+            return ModuleResult(success=False, error="按键不能为空")
+        if target not in {"focused", "element"}:
+            return ModuleResult(success=False, error=f"不支持的按键目标: {target}")
+        if target == "element" and not selector:
+            return ModuleResult(success=False, error="元素模式需要选择器")
+        page = _active_page(context)
+        if page is None:
+            return ModuleResult(success=False, error="没有打开的页面")
+        try:
+            if target == "element":
+                locator = await _wait_for_element(page, selector, state="visible", timeout=timeout)
+                await locator.press(key, timeout_ms=timeout)
+                return ModuleResult(success=True, message=f"已在元素 {selector} 上按下 {key}")
+            await cast(Any, page).keyboard_press(key)
+            return ModuleResult(success=True, message=f"已按下 {key}")
+        except Exception as error:  # noqa: BLE001 -- the reason becomes the node error (R1-03).
+            return ModuleResult(success=False, error=f"按键失败（{key}）: {error}")
+
+
 @register_executor
 class WaitElementExecutor(ModuleExecutor):
     requires_browser = True
@@ -920,6 +960,7 @@ WEB_BASIC_EXECUTORS: tuple[type[ModuleExecutor], ...] = (
     SwitchIframeExecutor,
     SwitchToMainExecutor,
     HoverElementExecutor,
+    PressKeyExecutor,
     HandleDialogExecutor,
     InjectJavaScriptExecutor,
     WaitElementExecutor,
```

`apps/backend/src/autoflow/providers/browser/workflow_session.py`：

```diff
diff --git a/apps/backend/src/autoflow/providers/browser/workflow_session.py b/apps/backend/src/autoflow/providers/browser/workflow_session.py
--- a/apps/backend/src/autoflow/providers/browser/workflow_session.py
+++ b/apps/backend/src/autoflow/providers/browser/workflow_session.py
@@ -70,6 +70,10 @@ class CloakBrowserWorkflowLocator(BrowserLocatorPort):
     async def double_click(self, **options: Any) -> None:
         await self._raw.dblclick(**options)
 
+    async def press(self, key: str, *, timeout_ms: float | None = None) -> None:
+        options: dict[str, Any] = {} if timeout_ms is None else {"timeout": timeout_ms}
+        await self._raw.press(key, **options)
+
     async def clear(self) -> None:
         await self._raw.clear()
 
```

`apps/backend/src/autoflow/domain/workflows/browser.py`：

```diff
diff --git a/apps/backend/src/autoflow/domain/workflows/browser.py b/apps/backend/src/autoflow/domain/workflows/browser.py
--- a/apps/backend/src/autoflow/domain/workflows/browser.py
+++ b/apps/backend/src/autoflow/domain/workflows/browser.py
@@ -44,6 +44,8 @@ class BrowserLocatorPort(Protocol):
 
     async def double_click(self, **options: Any) -> None: ...
 
+    async def press(self, key: str, *, timeout_ms: float | None = None) -> None: ...
+
     async def clear(self) -> None: ...
 
     async def fill(self, value: str) -> None: ...
```

- [ ] **Step 4: 登记为 AutoFlow 网页扩展节点**

`apps/backend/src/autoflow/domain/workflows/scope.py`：

```diff
diff --git a/apps/backend/src/autoflow/domain/workflows/scope.py b/apps/backend/src/autoflow/domain/workflows/scope.py
--- a/apps/backend/src/autoflow/domain/workflows/scope.py
+++ b/apps/backend/src/autoflow/domain/workflows/scope.py
@@ -9,6 +9,9 @@ from typing import Any
 # AutoFlow extensions are separate from the frozen WebRPA source catalog.
 DIAGNOSTIC_NODE_TYPES = frozenset({'trace_mark', 'capture_diagnostics', 'save_trace_segment'})
 
+# AutoFlow web primitives added by remediation M1 (R1-15); not part of the frozen WebRPA catalog.
+WEB_EXTENSION_NODE_TYPES = frozenset({'press_key'})
+
 PROJECT_NODE_TYPES = frozenset({'project_data', 'project_end', 'project_manual'})
 
 APPROVED_NODE_TYPES: frozenset[str] = frozenset(
@@ -385,7 +388,7 @@ def validate_workflow_scope(
                 if module is not None:
                     visit(_module_nodes(module), f"customModules.{module_id}.nodes")
                 continue
-            if node_type not in APPROVED_NODE_TYPES | PROJECT_NODE_TYPES | DIAGNOSTIC_NODE_TYPES:
+            if node_type not in APPROVED_NODE_TYPES | PROJECT_NODE_TYPES | DIAGNOSTIC_NODE_TYPES | WEB_EXTENSION_NODE_TYPES:
                 issues.append(
                     WorkflowScopeIssue(
                         node_id=node_id,
```

`apps/backend/src/autoflow/domain/workflows/catalog.py`：

```diff
diff --git a/apps/backend/src/autoflow/domain/workflows/catalog.py b/apps/backend/src/autoflow/domain/workflows/catalog.py
--- a/apps/backend/src/autoflow/domain/workflows/catalog.py
+++ b/apps/backend/src/autoflow/domain/workflows/catalog.py
@@ -105,6 +105,7 @@ _RUNNABLE_MODULES = (
     ("switch_to_main", "切回主页面"),
     ("switch_tab", "切换标签页"),
     ("hover_element", "悬停元素"),
+    ("press_key", "按键"),
     ("handle_dialog", "处理弹窗"),
     ("inject_javascript", "注入 JavaScript"),
     ("wait_element", "等待元素"),
```

`apps/backend/src/autoflow/providers/assistant/langgraph.py`：

```diff
diff --git a/apps/backend/src/autoflow/providers/assistant/langgraph.py b/apps/backend/src/autoflow/providers/assistant/langgraph.py
--- a/apps/backend/src/autoflow/providers/assistant/langgraph.py
+++ b/apps/backend/src/autoflow/providers/assistant/langgraph.py
@@ -18,7 +18,11 @@ from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
 from langgraph.graph import END, START, StateGraph
 from langgraph.types import Command, interrupt
 
-from autoflow.domain.workflows.scope import APPROVED_NODE_TYPES, DIAGNOSTIC_NODE_TYPES
+from autoflow.domain.workflows.scope import (
+    APPROVED_NODE_TYPES,
+    DIAGNOSTIC_NODE_TYPES,
+    WEB_EXTENSION_NODE_TYPES,
+)
 
 
 @dataclass(frozen=True, slots=True)
@@ -237,7 +241,7 @@ def _validate_tool_call(call: AssistantToolCall) -> str | None:
         replacement = payload.get("new_type")
         if isinstance(replacement, str):
             node_types.append(replacement)
-    excluded = sorted({item for item in node_types if item not in APPROVED_NODE_TYPES | DIAGNOSTIC_NODE_TYPES})
+    excluded = sorted({item for item in node_types if item not in APPROVED_NODE_TYPES | DIAGNOSTIC_NODE_TYPES | WEB_EXTENSION_NODE_TYPES})
     if excluded:
         return f"助手请求包含未批准的节点类型: {', '.join(excluded)}"
     return None
```

`apps/backend/tests/unit/workflows/test_executor_registry.py`：

```diff
diff --git a/apps/backend/tests/unit/workflows/test_executor_registry.py b/apps/backend/tests/unit/workflows/test_executor_registry.py
--- a/apps/backend/tests/unit/workflows/test_executor_registry.py
+++ b/apps/backend/tests/unit/workflows/test_executor_registry.py
@@ -216,6 +216,7 @@ def test_production_registry_contains_every_migrated_executor() -> None:
         "switch_iframe",
         "switch_to_main",
         "hover_element",
+        "press_key",
         "handle_dialog",
         "inject_javascript",
         "wait_element",
```

- [ ] **Step 5: 运行**

Run: `uv run --directory apps/backend pytest -q tests/unit/workflows tests/contract/test_workflow_catalog.py tests/migration`
Expected: 全部通过（`tests/migration` 需要 CI 检出的 `reference/WebRPA`）。
Run（装有 CloakBrowser 时）: `AUTOFLOW_TEST_CLOAKBROWSER=<路径> uv run --directory apps/backend pytest -q tests/integration/test_press_key_real_cloakbrowser.py`
Expected: 通过。

- [ ] **Step 6: 提交**

```bash
git add apps/backend/src/autoflow/application/workflows/executors/web_basic.py apps/backend/src/autoflow/providers/browser/workflow_session.py apps/backend/src/autoflow/domain/workflows/browser.py apps/backend/src/autoflow/domain/workflows/scope.py apps/backend/src/autoflow/domain/workflows/catalog.py apps/backend/src/autoflow/providers/assistant/langgraph.py apps/backend/tests/unit/workflows/test_executor_registry.py apps/backend/tests/unit/workflows/test_press_key_executor.py apps/backend/tests/integration/test_press_key_real_cloakbrowser.py
git commit -m "feat(nodes): 新增网页按键节点，支持元素上按键与组合键"
```

---

### Task 13: 按键节点——Studio 与录制器（R1-15、R1-16）

**Files:**
- Modify（均在 `apps/desktop/src/renderer/domains/workflows/` 下）: `types/workflow.ts`、`lib/moduleCatalog.ts`、`editor-store.ts`、`components/ModuleSidebar.tsx`、`components/ConfigPanel.tsx`、`components/config-panels/BasicModuleConfigs.tsx`、`lib/recordingGeneration.ts`
- Modify（清单与计数）: `tests/recording-source-parity.test.ts`、`tests/module-scope.test.ts`、`lib/__tests__/moduleColors.audit.test.ts`、`tests/audits/audit-module-docs.mjs`、`scripts/inventory-studio-completion.mjs`、`scripts/inventory-studio-completion.test.mjs`、`scripts/studio-docs.test.mjs`
- Test: `tests/recorder-press-key.test.ts`

**Interfaces:**
- Consumes: 后端 `press_key`（Task 12）。
- Produces: `ModuleType` 增加 `'press_key'`；`PressKeyConfig` 面板；录制器对 `keypress` 事件生成 `{ moduleType: 'press_key', key, targetType, selector? }`。

- [ ] **Step 1: 写失败的测试**

`apps/desktop/src/renderer/domains/workflows/tests/recorder-press-key.test.ts`：

```ts
import { expect, it } from 'vitest'
import { excludedModuleTypes, moduleCategories } from '../lib/moduleCatalog'
import { buildRecordedNodes, type RecEvent } from '../lib/recordingGeneration'

it('maps recorded key presses to the runnable web press_key node (remediation M1 R1-16)', () => {
  const { nodes } = buildRecordedNodes([
    { type: 'keypress', key: 'Enter', selector: '#input' },
    { type: 'keypress', key: 'Tab' },
  ], false)
  expect(nodes.map(node => [node.data.moduleType, node.data.key, node.data.targetType, node.data.selector]))
    .toEqual([['press_key', 'Enter', 'element', '#input'], ['press_key', 'Tab', 'focused', undefined]])
})

it('every node the recorder can generate is in the runnable catalog', () => {
  const events: RecEvent[] = [
    { type: 'navigate', url: 'https://local.test/a', ts: 1 },
    { type: 'click', selector: '#go', ts: 2 },
    { type: 'dblclick', selector: '#go', ts: 3 },
    { type: 'input', selector: '#name', value: 'x', ts: 4 },
    { type: 'select', selector: '#s', value: 'one', ts: 5 },
    { type: 'check', selector: '#c', value: true, ts: 6 },
    { type: 'keypress', key: 'Enter', selector: '#name', ts: 7 },
    { type: 'drag', selector: '#from', targetSelector: '#to', ts: 8 },
    { type: 'upload', selector: '#file', fileName: 'a.txt', ts: 9 },
    { type: 'scroll', dy: 300, ts: 10 },
    { type: 'click', selector: '#in-frame', _frame: { selector: 'iframe#one' }, ts: 11 },
    { type: 'click', selector: '#main', _frame: { main: true }, ts: 12 },
  ]
  const catalog = new Set(moduleCategories.flatMap(category => category.modules))
  for (const autoWait of [true, false]) {
    for (const node of buildRecordedNodes(events, autoWait).nodes) {
      const type = node.data.moduleType
      expect(excludedModuleTypes.has(type), type).toBe(false)
      expect(catalog.has(type), type).toBe(true)
    }
  }
})
```

- [ ] **Step 2: 运行，确认失败**

Run: `npm --workspace @autoflow/desktop test -- src/renderer/domains/workflows/tests/recorder-press-key.test.ts`
Expected: FAIL，生成的是 `keyboard_action`（已排除节点）。

- [ ] **Step 3: 登记节点类型、面板与图标**

`apps/desktop/src/renderer/domains/workflows/types/workflow.ts`：

```diff
diff --git a/apps/desktop/src/renderer/domains/workflows/types/workflow.ts b/apps/desktop/src/renderer/domains/workflows/types/workflow.ts
--- a/apps/desktop/src/renderer/domains/workflows/types/workflow.ts
+++ b/apps/desktop/src/renderer/domains/workflows/types/workflow.ts
@@ -19,6 +19,7 @@ export type ModuleType =
   | 'use_opened_page'
   | 'click_element'
   | 'hover_element'
+  | 'press_key'
   | 'input_text'
   | 'get_element_info'
   | 'wait'
```

`apps/desktop/src/renderer/domains/workflows/lib/moduleCatalog.ts`：

```diff
diff --git a/apps/desktop/src/renderer/domains/workflows/lib/moduleCatalog.ts b/apps/desktop/src/renderer/domains/workflows/lib/moduleCatalog.ts
--- a/apps/desktop/src/renderer/domains/workflows/lib/moduleCatalog.ts
+++ b/apps/desktop/src/renderer/domains/workflows/lib/moduleCatalog.ts
@@ -12,7 +12,7 @@ const sourceModuleCategories = [
   {
     name: '网页元素交互',
     color: 'bg-indigo-500',
-    modules: ['click_element', 'hover_element', 'input_text', 'select_dropdown', 'set_checkbox', 'drag_element', 'scroll_page', 'handle_dialog', 'upload_file', 'inject_javascript'] as ModuleType[],
+    modules: ['click_element', 'hover_element', 'press_key', 'input_text', 'select_dropdown', 'set_checkbox', 'drag_element', 'scroll_page', 'handle_dialog', 'upload_file', 'inject_javascript'] as ModuleType[],
   },
   {
     name: '网页元素查询',
```

`apps/desktop/src/renderer/domains/workflows/editor-store.ts`：

```diff
diff --git a/apps/desktop/src/renderer/domains/workflows/editor-store.ts b/apps/desktop/src/renderer/domains/workflows/editor-store.ts
--- a/apps/desktop/src/renderer/domains/workflows/editor-store.ts
+++ b/apps/desktop/src/renderer/domains/workflows/editor-store.ts
@@ -429,6 +432,7 @@ export const moduleTypeLabels: Record<ModuleType, string> = {
   use_opened_page: '操作已打开的网页',
   click_element: '点击元素',
   hover_element: '悬停元素',
+  press_key: '按键',
   input_text: '输入文本',
   get_element_info: '提取数据',
   wait: '固定等待',
@@ -1079,6 +1083,7 @@ export const moduleDefaultTimeouts: Partial<Record<ModuleType, number>> = {
   open_page: 60,        // 60秒，网页加载可能慢
   click_element: 60,    // 60秒
   hover_element: 60,    // 60秒
+  press_key: 30,
   input_text: 60,       // 60秒
   get_element_info: 60, // 60秒
   proxy_change_ip: 0,
```

`apps/desktop/src/renderer/domains/workflows/components/ModuleSidebar.tsx`：

```diff
diff --git a/apps/desktop/src/renderer/domains/workflows/components/ModuleSidebar.tsx b/apps/desktop/src/renderer/domains/workflows/components/ModuleSidebar.tsx
--- a/apps/desktop/src/renderer/domains/workflows/components/ModuleSidebar.tsx
+++ b/apps/desktop/src/renderer/domains/workflows/components/ModuleSidebar.tsx
@@ -222,6 +222,7 @@ const moduleIcons: Record<ModuleType, React.ElementType> = {
   // 元素交互
   click_element: MousePointerClick,
   hover_element: MousePointer,
+  press_key: Keyboard,
   input_text: Type,
   select_dropdown: ChevronDown,
   set_checkbox: CheckSquare,
@@ -876,6 +877,7 @@ const moduleKeywords: Record<ModuleType, string[]> = {
   dp_close: ['drissionpage', 'dp', '关闭', '浏览器', 'close'],
   click_element: ['点击', '单击', '双击', '右键', 'click', '按钮'],
   hover_element: ['悬停', '鼠标', '移动', 'hover', 'mouse', '移入', '经过', '停留'],
+  press_key: ['按键', '回车', '键盘', 'enter', 'tab', 'key', 'press', '快捷键'],
   input_text: ['输入', '文本', '填写', 'input', 'text', '表单'],
   get_element_info: ['提取', '数据', '获取', '元素', '信息', 'get', 'element', '采集'],
   wait: ['等待', '延迟', '暂停', 'wait', 'delay', '时间', '固定'],
```

`apps/desktop/src/renderer/domains/workflows/components/ConfigPanel.tsx`：

```diff
diff --git a/apps/desktop/src/renderer/domains/workflows/components/ConfigPanel.tsx b/apps/desktop/src/renderer/domains/workflows/components/ConfigPanel.tsx
--- a/apps/desktop/src/renderer/domains/workflows/components/ConfigPanel.tsx
+++ b/apps/desktop/src/renderer/domains/workflows/components/ConfigPanel.tsx
@@ -30,7 +31,7 @@ import {
 import { RunWorkflowFileConfig } from './config-panels/RunWorkflowFileConfig'
 import { SimilarSelectorDialog } from './config-panels/SimilarSelectorDialog'
 import { UrlInputDialog } from './config-panels/UrlInputDialog'
-import { OpenPageConfig, UseOpenedPageConfig, ClickElementConfig, HoverElementConfig, InputTextConfig, GetElementInfoConfig, WaitConfig, WaitElementConfig, WaitPageLoadConfig, PageLoadCompleteConfig, SetVariableConfig, IncrementDecrementConfig, PrintLogConfig, PlaySoundConfig, SystemNotificationConfig, InputPromptConfig, TextToSpeechConfig, JsScriptConfig, PythonScriptConfig, ExtractTableDataConfig, SwitchTabConfig, GroupConfig, SubflowHeaderConfig, RefreshPageConfig, GoBackConfig, GoForwardConfig, HandleDialogConfig, InjectJavaScriptConfig, SwitchIframeConfig, SwitchToMainConfig } from './config-panels/BasicModuleConfigs'
+import { OpenPageConfig, UseOpenedPageConfig, ClickElementConfig, HoverElementConfig, PressKeyConfig, InputTextConfig, GetElementInfoConfig, WaitConfig, WaitElementConfig, WaitPageLoadConfig, PageLoadCompleteConfig, SetVariableConfig, IncrementDecrementConfig, PrintLogConfig, PlaySoundConfig, SystemNotificationConfig, InputPromptConfig, TextToSpeechConfig, JsScriptConfig, PythonScriptConfig, ExtractTableDataConfig, SwitchTabConfig, GroupConfig, SubflowHeaderConfig, RefreshPageConfig, GoBackConfig, GoForwardConfig, HandleDialogConfig, InjectJavaScriptConfig, SwitchIframeConfig, SwitchToMainConfig } from './config-panels/BasicModuleConfigs'
 import { SelectDropdownConfig, SetCheckboxConfig, DragElementConfig, ScrollPageConfig, UploadFileConfig, DownloadFileConfig, SaveImageConfig, GetChildElementsConfig, GetSiblingElementsConfig, ScreenshotConfig, OCRCaptchaConfig, SliderCaptchaConfig, SendEmailConfig, SetClipboardConfig, GetClipboardConfig, ShutdownSystemConfig, LockScreenConfig, RunCommandConfig, NetworkCaptureConfig, ElementExistsConfig, ElementVisibleConfig, NetworkMonitorStartConfig, NetworkMonitorWaitConfig, NetworkMonitorStopConfig } from './config-panels/AdvancedModuleConfigs'
 import {
   AIChatConfig,
@@ -809,6 +810,8 @@ export function ConfigPanel({ selectedNodeId: propSelectedNodeId }: ConfigPanelP
         return <ClickElementConfig {...props} />
       case 'hover_element':
         return <HoverElementConfig {...props} />
+      case 'press_key':
+        return <PressKeyConfig {...props} />
       case 'input_text':
         return <InputTextConfig {...props} />
       case 'get_element_info':
```

`apps/desktop/src/renderer/domains/workflows/components/config-panels/BasicModuleConfigs.tsx`：

```diff
diff --git a/apps/desktop/src/renderer/domains/workflows/components/config-panels/BasicModuleConfigs.tsx b/apps/desktop/src/renderer/domains/workflows/components/config-panels/BasicModuleConfigs.tsx
--- a/apps/desktop/src/renderer/domains/workflows/components/config-panels/BasicModuleConfigs.tsx
+++ b/apps/desktop/src/renderer/domains/workflows/components/config-panels/BasicModuleConfigs.tsx
@@ -188,6 +188,40 @@ export function HoverElementConfig({
   )
 }
 
+// 按键配置（整改 M1 R1-15）
+export function PressKeyConfig({
+  data,
+  onChange,
+  renderSelectorInput
+}: {
+  data: NodeData
+  onChange: (key: string, value: unknown) => void
+  renderSelectorInput: RenderSelectorInput
+}) {
+  const target = (data.targetType as string) || 'focused'
+  return (
+    <>
+      <div className="space-y-2">
+        <Label htmlFor="key">按键</Label>
+        <VariableInput
+          value={(data.key as string) || ''}
+          onChange={(v) => onChange('key', v)}
+          placeholder="例如: Enter、Tab、Control+A"
+        />
+        <p className="text-xs text-muted-foreground">组合键用 + 连接，如 Control+A、Shift+Tab</p>
+      </div>
+      <div className="space-y-2">
+        <Label htmlFor="targetType">按在</Label>
+        <Select id="targetType" value={target} onChange={(e) => onChange('targetType', e.target.value)}>
+          <option value="focused">当前焦点</option>
+          <option value="element">指定元素</option>
+        </Select>
+      </div>
+      {target === 'element' && renderSelectorInput('selector', '元素选择器', '例如: #search-input')}
+    </>
+  )
+}
+
 // 输入文本配置
 export function InputTextConfig({ 
   data, 
```

- [ ] **Step 4: 录制器生成按键节点**

`apps/desktop/src/renderer/domains/workflows/lib/recordingGeneration.ts`：

```diff
diff --git a/apps/desktop/src/renderer/domains/workflows/lib/recordingGeneration.ts b/apps/desktop/src/renderer/domains/workflows/lib/recordingGeneration.ts
--- a/apps/desktop/src/renderer/domains/workflows/lib/recordingGeneration.ts
+++ b/apps/desktop/src/renderer/domains/workflows/lib/recordingGeneration.ts
@@ -173,8 +173,9 @@ export function buildRecordedNodes(evs: RecEvent[], autoWait: boolean) {
         // 回车/Tab 可能触发表单提交跳转，视为"可致跳转的交互"
         if (ev.key === 'Enter' || ev.key === 'Tab' || /Enter$/.test(ev.key)) lastActionTs = ev.ts || 0
         // 若按键发生在具体输入元素上，用 element 目标模式（先聚焦该元素再按键），忠实还原作用目标
-        const keyCfg = ev.selector ? { keySequence: ev.key, targetType: 'element', selector: ev.selector } : { keySequence: ev.key }
-        mkNode('keyboard_action', keyCfg, ev.key)
+        // 整改 M1 R1-16：生成后端可执行的网页按键节点（原 keyboard_action 属于已排除的桌面键盘类别）
+        const keyCfg = ev.selector ? { key: ev.key, targetType: 'element', selector: ev.selector } : { key: ev.key, targetType: 'focused' }
+        mkNode('press_key', keyCfg, ev.key)
       }
     }
 
```

对照测试中按键用例改由 Step 1 的新测试覆盖（这是对冻结来源的一次显式评审修改）：

`apps/desktop/src/renderer/domains/workflows/tests/recording-source-parity.test.ts`：

```diff
diff --git a/apps/desktop/src/renderer/domains/workflows/tests/recording-source-parity.test.ts b/apps/desktop/src/renderer/domains/workflows/tests/recording-source-parity.test.ts
--- a/apps/desktop/src/renderer/domains/workflows/tests/recording-source-parity.test.ts
+++ b/apps/desktop/src/renderer/domains/workflows/tests/recording-source-parity.test.ts
@@ -21,7 +21,6 @@ const cases:RecEvent[][]=[
  [{type:'drag',selector:'#slider',endX:100,endY:50}],
  [{type:'upload',selector:'#upload',fileName:'fixture.txt'}],
  [{type:'scroll',dy:-450}],
- [{type:'keypress',key:'Enter',selector:'#input'}],
  [{type:'click',selector:'#frame',_frame:{selector:'iframe#one'}},{type:'click',selector:'#main',_frame:{main:true}}],
  [{type:'click',selector:'#frame',_frame:{name:'named'}},{type:'click',selector:'#other',_frame:{index:2}}],
  [{type:'navigate',url:'https://local.test/a',ts:1},{type:'click',selector:'#next',ts:100},{type:'navigate',url:'https://local.test/b',ts:500},{type:'navigate',url:'https://local.test/c',ts:11000}],
```

- [ ] **Step 5: 更新"213 冻结 + 扩展"清单（扩展节点从 9 个变为 10 个）**

`scripts/inventory-studio-completion.mjs`：

```diff
diff --git a/scripts/inventory-studio-completion.mjs b/scripts/inventory-studio-completion.mjs
--- a/scripts/inventory-studio-completion.mjs
+++ b/scripts/inventory-studio-completion.mjs
@@ -30,9 +30,9 @@ const nativeCategories = [
   {name:'项目能力',types:['project_data','project_manual','project_end']},
 ]
 const retained=[...nativeCategories,...categories.filter(c=>!excluded.has(c.name))].flatMap(c=>c.types.filter(t=>!extra.has(t)).map(type=>({type,category:c.name})))
-const nativeTypes = new Set(['proxy_change_ip', 'proxy_change_location', 'proxy_query', ...nativeCategories.flatMap(category=>category.types)])
+const nativeTypes = new Set(['press_key', 'proxy_change_ip', 'proxy_change_location', 'proxy_query', ...nativeCategories.flatMap(category=>category.types)])
 const frozen = retained.filter(node => !nativeTypes.has(node.type))
-if(frozen.length!==213 || new Set(frozen.map(n=>n.type)).size!==213 || retained.length!==222 || new Set(retained.map(n=>n.type)).size!==222 || nativeTypes.size!==9)throw Error('Approved frozen/native node scope changed')
+if(frozen.length!==213 || new Set(frozen.map(n=>n.type)).size!==213 || retained.length!==223 || new Set(retained.map(n=>n.type)).size!==223 || nativeTypes.size!==10)throw Error('Approved frozen/native node scope changed')
 const files=fs.readdirSync(path.join(root,domain,'components/config-panels')).filter(f=>f.endsWith('.tsx')).map(f=>`${domain}/components/config-panels/${f}`)
 files.push(`${domain}/components/ConfigPanel.tsx`,`${domain}/editor-store.ts`)
 const evidence=new Map(retained.map(n=>[n.type,[]]))
```

`scripts/inventory-studio-completion.test.mjs`：

```diff
diff --git a/scripts/inventory-studio-completion.test.mjs b/scripts/inventory-studio-completion.test.mjs
--- a/scripts/inventory-studio-completion.test.mjs
+++ b/scripts/inventory-studio-completion.test.mjs
@@ -12,10 +12,10 @@ execFileSync(process.execPath, ['scripts/inventory-studio-completion.mjs', '--ou
 const rows = JSON.parse(fs.readFileSync(path.join(directory, 'capabilities.json')))
 const dependency = type => rows.find(row => row.type === type).toolDependencies
 const prefix = 'apps/desktop/src/renderer/domains/workflows/components/'
-const nativeTypes = ['trace_mark','capture_diagnostics','save_trace_segment','proxy_change_ip','proxy_change_location','proxy_query','project_data','project_manual','project_end']
+const nativeTypes = ['press_key','trace_mark','capture_diagnostics','save_trace_segment','proxy_change_ip','proxy_change_location','proxy_query','project_data','project_manual','project_end']
 test('retains the approved scope and resolves an imported alias to its actual component file', () => {
-  assert.equal(rows.length, 222)
-  assert.equal(new Set(rows.map(row => row.type)).size, 222)
+  assert.equal(rows.length, 223)
+  assert.equal(new Set(rows.map(row => row.type)).size, 223)
   assert.ok(dependency('open_page').resolved.includes(prefix + 'controls/select-native.tsx#SelectNative'))
   assert.ok(dependency('open_page').external.includes('@radix-ui/react-select#Trigger'))
   assert.deepEqual(dependency('open_page').unresolved, [])
```

`scripts/studio-docs.test.mjs`：

```diff
diff --git a/scripts/studio-docs.test.mjs b/scripts/studio-docs.test.mjs
--- a/scripts/studio-docs.test.mjs
+++ b/scripts/studio-docs.test.mjs
@@ -7,10 +7,10 @@ test('Studio Chinese documentation audit covers exactly the retained catalog', (
   const extensionTypes = [
     'project_data', 'project_manual', 'project_end',
     'proxy_change_ip', 'proxy_change_location', 'proxy_query',
-    'trace_mark', 'capture_diagnostics', 'save_trace_segment',
+    'trace_mark', 'capture_diagnostics', 'save_trace_segment', 'press_key',
   ]
-  assert.equal(modules.length, 222)
-  assert.equal(new Set(modules.map(module => module.type)).size, 222)
+  assert.equal(modules.length, 223)
+  assert.equal(new Set(modules.map(module => module.type)).size, 223)
   for (const type of extensionTypes) assert.ok(modules.some(module => module.type === type))
   assert.ok(modules.some(module => module.type === 'text_to_speech'))
   assert.ok(!modules.some(module => module.type === 'read_excel' || module.type === 'notify_feishu' || module.type === 'db_connect' || module.type === 'dp_open_page'))
```

`apps/desktop/src/renderer/domains/workflows/tests/audits/audit-module-docs.mjs`：

```diff
diff --git a/apps/desktop/src/renderer/domains/workflows/tests/audits/audit-module-docs.mjs b/apps/desktop/src/renderer/domains/workflows/tests/audits/audit-module-docs.mjs
--- a/apps/desktop/src/renderer/domains/workflows/tests/audits/audit-module-docs.mjs
+++ b/apps/desktop/src/renderer/domains/workflows/tests/audits/audit-module-docs.mjs
@@ -26,9 +26,9 @@ export function realModules() {
   const extensionTypes = [
     'project_data', 'project_manual', 'project_end',
     'proxy_change_ip', 'proxy_change_location', 'proxy_query',
-    'trace_mark', 'capture_diagnostics', 'save_trace_segment',
+    'trace_mark', 'capture_diagnostics', 'save_trace_segment', 'press_key',
   ]
-  if (types.length !== 222 || new Set(types).size !== 222 || !extensionTypes.every(type => types.includes(type))) {
+  if (types.length !== 223 || new Set(types).size !== 223 || !extensionTypes.every(type => types.includes(type))) {
     throw new Error('已批准的 213 冻结节点加 9 个 AutoFlow 扩展节点范围发生变化')
   }
   return types.map(type => {
```

`apps/desktop/src/renderer/domains/workflows/tests/module-scope.test.ts`：

```diff
diff --git a/apps/desktop/src/renderer/domains/workflows/tests/module-scope.test.ts b/apps/desktop/src/renderer/domains/workflows/tests/module-scope.test.ts
--- a/apps/desktop/src/renderer/domains/workflows/tests/module-scope.test.ts
+++ b/apps/desktop/src/renderer/domains/workflows/tests/module-scope.test.ts
@@ -8,16 +8,17 @@ const extensionModuleTypes = new Set<string>([
   ...projectModuleTypes,
   ...proxyModuleTypes,
   ...diagnosticModuleTypes,
+  'press_key', // remediation M1 R1-15
 ])
 
-it('keeps 213 frozen nodes plus the nine approved AutoFlow extensions', () => {
+it('keeps 213 frozen nodes plus the ten approved AutoFlow extensions', () => {
   const types = getAllAvailableModules()
     .filter(module => !module.isCustom)
     .map(module => module.type)
   const frozenTypes = types.filter(type => !extensionModuleTypes.has(type))
 
-  expect(types).toHaveLength(222)
-  expect(new Set(types).size).toBe(222)
+  expect(types).toHaveLength(223)
+  expect(new Set(types).size).toBe(223)
   expect(frozenTypes).toHaveLength(213)
   expect(new Set(frozenTypes).size).toBe(213)
   expect(types.filter(type => projectModuleTypes.includes(type as typeof projectModuleTypes[number]))).toEqual(projectModuleTypes)
```

`apps/desktop/src/renderer/domains/workflows/lib/__tests__/moduleColors.audit.test.ts`：

```diff
diff --git a/apps/desktop/src/renderer/domains/workflows/lib/__tests__/moduleColors.audit.test.ts b/apps/desktop/src/renderer/domains/workflows/lib/__tests__/moduleColors.audit.test.ts
--- a/apps/desktop/src/renderer/domains/workflows/lib/__tests__/moduleColors.audit.test.ts
+++ b/apps/desktop/src/renderer/domains/workflows/lib/__tests__/moduleColors.audit.test.ts
@@ -232,7 +232,7 @@ describe('模块配色三处同源审计 - module-integrity-audit Property 7', (
 
     // 防空跑：分类清单为空或解析异常时，上面的循环不会报错却什么也没测。
     // 213 个批准迁入节点、3 个代理节点、3 个项目节点和 3 个诊断节点。
-    expect(checked, '被核验的模块数异常偏少，审计可能空跑').toBe(222)
+    expect(checked, '被核验的模块数异常偏少，审计可能空跑').toBe(223)
     expect(
       mismatches,
       `存在三处取色不同源的模块：\n${JSON.stringify(mismatches, null, 2)}`,
```

- [ ] **Step 6: 运行**

Run: `npm --workspace @autoflow/desktop test -- src/renderer/domains/workflows && npm run test:scripts && npm run typecheck`
Expected: 全部通过（CI 中 `recording-source-parity` 会与检出的 WebRPA 对照）。

- [ ] **Step 7: 提交**

```bash
git add apps/desktop/src/renderer/domains/workflows scripts/inventory-studio-completion.mjs scripts/inventory-studio-completion.test.mjs scripts/studio-docs.test.mjs
git commit -m "feat(studio): 按键节点进入模块库，录制到的回车等按键可以直接运行"
```

---

### Task 14: 黄金场景改用回车、文档与里程碑验收

**Files:**
- Modify: `apps/backend/tests/golden/test_g3_form_entry.py`
- Modify: `.ai/decisions/2026-09-30-remediation-program.md`、`.ai/plans/2026-09-30-remediation-program.md`、`.ai/knowledge/2026-09-30-remediation-baseline.md`
- Modify: `docs/PROJECT_STRUCTURE.md`
- Modify: `docs/superpowers/plans/2026-09-26-parameter-batch-concurrency.md`（在"全局约束"中"不提高 core 的两个槽上限"一条后注明：`superseded by remediation M1（2026-09-30）`）

- [ ] **Step 1: G3 改为按回车提交**

`test_g3_form_entry.py` 的 `build` 中，把

```python
                flow_node("submit", "click_element", 2, selector="#submit", timeout=10),
```

替换为

```python
                flow_node("submit", "press_key", 2, key="Enter", targetType="element", selector="#name", timeout=10),
```

并在文档 `nodes` 构造后加上 v2 语义不影响本场景（无错误分支），无需其他改动。

Run（装有 CloakBrowser 时）: `AUTOFLOW_TEST_CLOAKBROWSER=<路径> uv run --directory apps/backend pytest -q -m golden tests/golden -s`
Expected: G2 通过，`failure_reason_ratio` = 1.0（M0 为 0）；G3 通过至 xfail（结果不明的行仍待 M2），`lose-` 行各只提交 1 次。

- [ ] **Step 2: 全量检查**

Run:
```bash
uv run --directory apps/backend ruff check . && uv run --directory apps/backend mypy src
uv run --directory apps/backend pytest -q
uv run --directory apps/backend pytest -q -m benchmark tests/benchmarks
npm run typecheck && npm run lint && npm test && npm run test:scripts && npm run openapi:check
node scripts/ratchets.mjs
```
Expected: 全部通过。

- [ ] **Step 3: 记录**

- `.ai/knowledge/2026-09-30-remediation-baseline.md` 追加 M1 列：`event_commit_ms_p50`、`bench_claim_loop_lag`（1 万行）、G2 `failure_reason_ratio`。
- `.ai/decisions/2026-09-30-remediation-program.md`：把总纲第 5 节中 M1 的三条替代关系（容量 {1,2}、人工等待占名额、WebRPA 出错语义）标记为 confirmed 并注明生效提交。
- `.ai/plans/2026-09-30-remediation-program.md`：M1 状态改为 done，M2 状态改为"细化中"。
- `docs/PROJECT_STRUCTURE.md` 目录职责表追加：`domain/settings/execution_capacity.py`（容量推荐规则）、`application/settings/execution.py`（容量设置服务）、`infrastructure/database/app_settings.py`（工作区键值设置）、`infrastructure/process/stderr_sink.py`（worker 诊断日志）、`domain/workflows/inert_settings.py`（未生效设置规则，M2 删除）。

- [ ] **Step 4: 对照验收标准**

| AC | 证明 |
| --- | --- |
| AC1-01 | `tests/inert-settings.test.tsx` 第一个用例 |
| AC1-02 | `run-start-boundary.test.tsx` 新用例、`test_inert_retry_settings_are_reported_once_per_node` |
| AC1-03 | `test_batch_failure_log_carries_the_executor_reason`；凭据：既有 `test_runtime_propagates_sensitive_values_without_persisting_them_in_events` |
| AC1-04 | `test_handled_failure_semantics.py`、`test_project_graph_failure_reason.py` |
| AC1-05 | `execution-semantics.test.tsx` |
| AC1-06 | `tests/contract/test_execution_settings.py` |
| AC1-07 | `test_waiting_manual_frees_its_execution_slot_but_keeps_its_live_browser`、`test_project_capacity_counts.py` |
| AC1-08 | `test_memory_pressure_pauses_new_dispatch_and_rewakes_the_scheduler` |
| AC1-09 | `bench_claim_loop_lag`（1 万行） |
| AC1-10 | `bench_event_commit` 对比 M0 |
| AC1-11 | `test_sqlite_session.py`、`configure_proxy_management(..., session_factory=...)` |
| AC1-12 | `test_stderr_sink.py`、`test_worker_stderr_diagnostics.py` |
| AC1-13 | `test_press_key_real_cloakbrowser.py` |
| AC1-14 | `recorder-press-key.test.ts` |
| AC1-15 | 黄金场景 G3（Step 1） |
| AC1-16 | `node scripts/ratchets.mjs`（`unreadConfigKeys` 比 M0 少 7） |

- [ ] **Step 5: 提交并退出评审**

```bash
git add apps/backend/tests/golden/test_g3_form_entry.py .ai docs/PROJECT_STRUCTURE.md docs/superpowers/plans/2026-09-26-parameter-batch-concurrency.md
git commit -m "docs: M1 验收记录，黄金场景 G3 改为回车提交"
```

派一个未参与实现的评审者，输入本计划、M1 规格与 `git diff main...remediation/m1-stop-silent-failures`，逐条核对 AC 与 Review Focus，给出通过 / 不通过。
