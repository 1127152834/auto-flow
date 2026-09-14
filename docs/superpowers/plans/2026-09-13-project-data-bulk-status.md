> 状态：superseded（2026-09-13）。原任务遗留草案保留作历史；实施和验收以 [修订PM2计划](2026-09-13-project-management-pm2.md) 为准，不能将本草案的未来任务占用约束当作已接入能力。

# Project Data Durable Bulk Status Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为项目数据表实现可查询、可取消、可在 sidecar 重启后继续收口的耐久批量状态修改；接受时冻结最多 1000 个目标，每条使用自己的 `statusRevision` 做 CAS，每个有限块全成或全冲突，并永久保留已提交、冲突、取消和未开始事实。

**Architecture:** 单条 `PUT .../records/{recordKey}/status` 继续负责单记录同步命令；批量命令使用新的应用服务、持久批次/批块账本和一个只执行本地数据库块的进程内协调器。接受命令先在短事务中保存 `ProjectOperation(setRecordStatuses)`、规范请求和冻结块；协调器逐块调用仓储，每块在一个 `BEGIN IMMEDIATE` 中完成所有行 CAS、状态修改、`DataChange`、块结果和 Operation 进度。进程退出不会留下不可解释的外部副作用；启动时只继续同一 Operation 的未终结本地块，不重新筛选目标、不创建第二 Operation。取消命令用独立 `ProjectOperation(cancelRecordStatuses)` 关闭尚未开始块。全局 quiesce 先阻止新批块开始，活动块仍由现有 API mutation 计数保护；已落库但未终结的批量操作作为 workspace 切换 blocker。

**Tech Stack:** Python 3、FastAPI、Pydantic v2、SQLAlchemy 2、SQLite/Alembic、pytest、Ruff、mypy。

**Spec:** `docs/project-management/design/data-and-state-rules.md` §4.1 `DATA-STATE-07`，`docs/project-management/implementation/api-contracts.md` §3.3 与 §3.9，`docs/project-management/implementation/contracts.md` `XE-C09`。

## Global Constraints

- 只实现人工管理面的批量状态操作；工作流写仍走注入 capability，不能调用公共 HTTP，也不能把本功能扩成 Task/lease 执行器。
- 请求只接受固定显式 `targets`，不能为空、最多 1000 条；不保存筛选器并在后台重新查询。
- `blockSize` 为 1–100，默认 100；输入顺序冻结，稳定块身份为 `(operationId, blockIndex)`。
- 每个块全成或全冲突；任何目标、代次、状态目录、占用或 `statusRevision` 失败时，该块一行也不写。
- 已提交块不因后续冲突、取消、进程退出或重试回滚。取消只关闭尚未开始块。
- 每个记录变化保存完整 before/after 快照；即使多个目标原状态相同，也不能用汇总计数替代原始状态与原始修订证据。
- 同一 idempotency key 先匹配 `kind + requestDigest`，再做生命周期、目标和 CAS 检查；原 key 重试返回同一 Operation。
- 项目、表、代次、状态和每个 RecordRef 都必须在事务内重新验证归属；目标状态必须是同表未删除状态或显式 `null`。
- 人工状态写要求无活动或归属未知的数据占用。PM2 尚无真实 Task/lease 表，因此本包只提供明确的 guard 端口并以“无占用”适配器接入；PM4 必须替换为真实占用查询后才可声称跨 Task 验收通过。
- 不新增通用后台任务框架、第二执行器、消息队列或新依赖；协调器只能推进 `setRecordStatuses` 的本地数据库块。
- root 负责最终 Alembic 迁移、HTTP/OpenAPI、bootstrap 与生成客户端类型汇合；本计划先精确定义它们，执行者不得改写既有 `pm01_projects.py`、`pm02_project_data.py` 或 `pm02_status_tombstones.py`。
- 每个任务先 RED、再最小实现、再定向检查；不得用前端循环调用单条状态接口替代后端耐久命令。

## 已核实基线与文件边界

- `application/project_data/records.py::DataRecordService.set_status` 和 `infrastructure/database/project_data_records.py::SqlAlchemyProjectDataRecords.set_status` 是单行同步命令；它们每次独立 `BEGIN IMMEDIATE`、独立 CAS、独立完成一个 `ProjectOperation`。循环调用会产生多个操作身份、不可定义的部分成功边界，也不能可靠取消或恢复，禁止作为批量实现。
- `infrastructure/database/models.py::ProjectOperationRow` 已有 `accepted/running/failed` 所需的通用字段，但 `adapters/http/project_schemas.py::ProjectOperationView` 目前把 `status` 限为 `succeeded`，kind/resource/result 也没有批量分支。
- `infrastructure/database/project_data_models.py` 目前只有表、代次、字段、状态、记录、变化和 impact；没有冻结批目标、块状态或取消门闩的耐久事实。
- `bootstrap/app.py` 的 middleware 用 `QuiesceGate.mutation()` 包裹公开写请求，但后台块不会自动进入该计数；`SettingsRuntimeService` 的外部 blocker 当前只看 kernel/test-browser process。
- `api-contracts.md` 已冻结 `setRecordStatuses`、`cancelRecordStatuses`、请求/块/outcome DTO 和三条 HTTP 路由，但 `ResourceLocator` 没有专用 status-batch 分支。最小一致选择是两种 Operation 都使用现有 `{type:'table',projectId,tableId}`；Operation 身份由 `operationId` 表达，避免擅自扩展冻结联合。若产品要在资源筛选中区分批量状态，须先单独修改契约，而不是在代码中发明 locator。

---

### Task 1: 冻结批量领域模型、校验与占用端口

**Files:**
- Create: `apps/backend/src/autoflow/domain/project_data/status_batches.py`
- Create: `apps/backend/src/autoflow/application/project_data/status_batches.py`
- Modify: `apps/backend/src/autoflow/domain/project_data/__init__.py`
- Test: `apps/backend/tests/unit/test_project_data_status_batches.py`

**Interfaces:**
- Consumes: `RecordKey`/`decode_record_key`、`MAX_SAFE_INTEGER`、`ProjectError`、现有 `_canonical_uuid` 与 Operation 规范摘要规则。
- Produces: `StatusBatchTarget(ref: RecordRef, expected_status_revision: int)`、`StatusBatchRequest(status_id: str | None, targets: tuple[StatusBatchTarget, ...], block_size: int)`；`ProjectDataStatusBatches` protocol；`RecordStatusOccupancyGuard.blockers(session, refs) -> list[dict[str, object]]`；`DataRecordStatusBatchService.preview/start/cancel`。

- [ ] **Step 1: 写领域校验失败测试**

在 `test_project_data_status_batches.py` 写表驱动测试，构造两个 typed key（文本 `"1"` 与整数 `1`）并断言它们不是重复目标；再覆盖：空列表、1001 行、`blockSize=0/101/bool`、非 JSON-safe revision、跨项目/跨表 target、非规范 UUID、重复同一完整 RecordRef 同版本、重复同一完整 RecordRef 不同版本。前六类返回字段级 `VALIDATION_ERROR`；同版本重复接受时按首次出现顺序去重；异版本重复返回 422，不能挑一个版本。

- [ ] **Step 2: 运行 RED 测试**

Run: `uv run --directory apps/backend pytest tests/unit/test_project_data_status_batches.py -q`

Expected: FAIL，`autoflow.domain.project_data.status_batches` 尚不存在。

- [ ] **Step 3: 实现不可变请求与分块函数**

在领域文件使用 frozen dataclass；提供 `parse_status_batch_request(project_id, table_id, payload) -> StatusBatchRequest` 和 `freeze_blocks(request) -> tuple[tuple[StatusBatchTarget, ...], ...]`。完整 RecordRef 包含 `projectId/tableId/datasetGeneration/recordKey:{type,value}`，revision 保持逐条证据。规范请求序列化为 camelCase，targets 保持冻结顺序，不能按 key 重排；只有 digest 计算使用现有稳定 JSON 序列化。

- [ ] **Step 4: 写应用服务失败测试**

使用 fake repository 验证：`preview` 不创建 Operation；`start` 创建 kind=`setRecordStatuses`、resource=`table`、状态 `accepted` 的 Operation；`cancel` 创建独立 kind=`cancelRecordStatuses` 且请求含原 operationId 与 expectedOperationRevision；同 cancel key 不得与 start key或另一原 Operation 复用。断言 start/cancel 调用仓储一次且返回原始 Operation，不在服务内逐行调用 `DataRecordService.set_status`。

- [ ] **Step 5: 实现最小应用服务和协议**

`preview(project_id, table_id, payload)` 只规范化并调用 `repository.preview(request)`；`start(..., idempotency_key, payload)` 生成稳定 Operation 与完整 request digest 后调用 `repository.accept(request, operation)`；`cancel(..., batch_operation_id, idempotency_key, payload)` 严格只接受 `expectedOperationRevision` 并调用 `repository.cancel(...)`。仓储 protocol 明确定义 `claim_next_block(operation_id)`, `commit_block(claim)`, `fail_block(claim, blockers)`, `recoverable_operation_ids()` 和 `active_operation_count()`，供后续协调器使用。

- [ ] **Step 6: 验证领域与应用边界**

Run: `uv run --directory apps/backend pytest tests/unit/test_project_data_status_batches.py -q`

Run: `uv run --directory apps/backend ruff check src/autoflow/domain/project_data/status_batches.py src/autoflow/application/project_data/status_batches.py tests/unit/test_project_data_status_batches.py`

Run: `uv run --directory apps/backend mypy src/autoflow/domain/project_data/status_batches.py src/autoflow/application/project_data/status_batches.py`

- [ ] **Step 7: 提交本任务**

```bash
git add apps/backend/src/autoflow/domain/project_data/status_batches.py apps/backend/src/autoflow/application/project_data/status_batches.py apps/backend/src/autoflow/domain/project_data/__init__.py apps/backend/tests/unit/test_project_data_status_batches.py
git commit -m "feat(project-data): define durable status batch commands"
```

### Task 2: 增加耐久批次/批块表与迁移

**Files:**
- Modify: `apps/backend/src/autoflow/infrastructure/database/project_data_models.py`
- Create: `apps/backend/src/autoflow/infrastructure/database/migrations/versions/pm02_status_batches.py`
- Modify: `apps/backend/tests/integration/test_project_data_migrations.py`
- Create: `apps/backend/tests/integration/test_project_data_status_batch_migration.py`

**Interfaces:**
- Consumes: `project_operations(project_id,id)` 与 `projects.id`，当前 Alembic head `pm02_status_tombstones`。
- Produces: `ProjectDataStatusBatchRow`（一条对应一个 set 操作）和 `ProjectDataStatusBlockRow`（主键 `operation_id,block_index`）的 ORM 与数据库约束。

- [ ] **Step 1: 写迁移 RED 测试**

覆盖空库升级、从 `pm02_status_tombstones` 有项目/表/状态/记录数据的库升级、重复 operation/block 拒绝、跨项目 operation FK 拒绝、块索引负数拒绝、非法 state 拒绝、目标 JSON 和 committed revisions 原样保存。更新既有 migration head 断言为 `pm02_status_batches`，不得删除旧 migration 验证。

- [ ] **Step 2: 运行迁移 RED**

Run: `uv run --directory apps/backend pytest tests/integration/test_project_data_migrations.py tests/integration/test_project_data_status_batch_migration.py -q`

Expected: FAIL，revision/table/ORM 尚不存在。

- [ ] **Step 3: 实现最小持久模型**

`project_data_status_batches` 保存 `operation_id`、`project_id`、`table_id`、`dataset_generation`、`status_id`（nullable）、`request_json`、`block_size`、`cancel_requested`、`created_at/updated_at`；`operation_id` 一对一 FK 到 `(project_id,id)`。`project_data_status_batch_blocks` 保存 `operation_id`、`block_index`、冻结 `targets_json`、`state`（`notStarted|claimed|committed|conflicted|cancelled`）、`blockers_json`、`committed_revisions_json`、`claim_token` nullable、时间戳，并以 `(operation_id,block_index)` 为主键。数据库 check 限制 block size、index 与 state；目标数量/形状由领域层与仓储复验。

- [ ] **Step 4: 实现 Alembic migration**

revision=`pm02_status_batches`、down_revision=`pm02_status_tombstones`。只新增两表及按 `project_id/state`、`operation_id/state/block_index` 的恢复索引。downgrade 只删本 revision 新表，不改项目、记录、Operation 或 DataChange 历史。

- [ ] **Step 5: 验证迁移与模型**

Run: `uv run --directory apps/backend pytest tests/integration/test_project_data_migrations.py tests/integration/test_project_data_status_batch_migration.py -q`

Run: `uv run --directory apps/backend ruff check src/autoflow/infrastructure/database/project_data_models.py src/autoflow/infrastructure/database/migrations/versions/pm02_status_batches.py tests/integration/test_project_data_status_batch_migration.py`

- [ ] **Step 6: 提交本任务**

```bash
git add apps/backend/src/autoflow/infrastructure/database/project_data_models.py apps/backend/src/autoflow/infrastructure/database/migrations/versions/pm02_status_batches.py apps/backend/tests/integration/test_project_data_migrations.py apps/backend/tests/integration/test_project_data_status_batch_migration.py
git commit -m "feat(project-data): persist status batch blocks"
```

### Task 3: 原子接受、预览、块提交、冲突和取消

**Files:**
- Create: `apps/backend/src/autoflow/infrastructure/database/project_data_status_batches.py`
- Create: `apps/backend/tests/integration/test_project_data_status_batches.py`
- Modify: `apps/backend/src/autoflow/domain/project_data/status_batches.py`

**Interfaces:**
- Consumes: Task 1 的 protocol/model、Task 2 的 ORM、`SqlAlchemyProjectData._guard_project_write`、`SqlAlchemyProjectDataRecords._snapshot`、`ProjectOperationRow`、`DataChangeRow`。
- Produces: `SqlAlchemyProjectDataStatusBatches(session_factory, occupancy_guard)`；每个方法只完成一次短事务，不在仓储内部启动线程或循环全部块。

- [ ] **Step 1: 写接受与预览 RED 集成测试**

创建 active 项目、local/excel 表、同表状态及至少 205 条不同 typed RecordRef。断言 preview 返回冻结 request 和按 blockSize 分块的 `notStarted` blocks，且数据库无 Operation/批次/块；accept 在一个事务写入一条 accepted Operation、一条 batch、三个 blocks。注入 Operation/第二块写入失败，断言三类记录全部回滚。相同 key/相同 body 返回同 operationId 和同冻结目标；相同 key/不同顺序、状态、revision 或 blockSize 返回 `OPERATION_PAYLOAD_MISMATCH`。

- [ ] **Step 2: 写块原子性 RED 集成测试**

覆盖：一块全部成功并逐行推进 statusRevision；设置同一个非 null 状态是 no-op 且不推进，但显式 `null` 按现有单条契约每次推进；块中一行 revision 冲突导致全块 `conflicted` 且其他行不变；旧 generation、删除记录、跨表/跨项目 ref、墓碑/跨表状态、项目 archived/closing、local/excel 可写和 sheets/unconfigured 拒绝。每个 committed 行各写 sequence 稳定且唯一的 `DataChange`，before 保留原 statusId/statusRevision，after 保留新值/新 revision；conflicted 不写 DataChange。

- [ ] **Step 3: 写 claim、并发与崩溃恢复 RED 测试**

两个仓储实例并发 claim 同一 operation，只有一个获得 `(operationId,blockIndex,claimToken)`；提交要求 token 匹配。模拟 claim 后进程退出：新实例把 `claimed` 恢复为可重领，随后同一块仅提交一次。这里安全成立是因为 claim 不修改业务记录，业务写与块 committed 同事务；禁止把“记录已写、块未记”拆成两个事务。

- [ ] **Step 4: 写取消与终态 RED 测试**

取消校验原操作属于同 project/table、kind 正确、expectedOperationRevision 匹配。取消事务设置门闩并把所有 `notStarted` 块改 `cancelled`；`claimed` 块可完成，其后不再 claim 新块。取消 Operation 自身 succeeded，result 精确为 `{operationId,subsequentBlocksClosed:true}`。原批操作：全 committed → succeeded/completed；任一 conflicted → failed/conflicted + `BATCH_STATUS_CONFLICT`；取消且存在未开始关闭块 → failed/cancelled + `BATCH_STATUS_CANCELLED`。result 始终含所有 blocks、原 request、changed/conflict/notStarted 计数和 cancelled；`statusRevision` 每次持久进度变化递增。

- [ ] **Step 5: 实现仓储事务**

accept 首先按 idempotency key 查 Operation 并匹配 kind/digest，然后在 `BEGIN IMMEDIATE` 中复验项目、表、current generation、source kind、目标范围和目标状态；保存冻结 targets 与块。`claim_next_block` 只选最小 `notStarted` block，并在同事务复验 cancel 门闩后写随机 claim token。`commit_block` 在同一个 `BEGIN IMMEDIATE` 内按冻结顺序读取全部行、调用 occupancy guard、验证所有 CAS；先完成所有检查，再修改任何行。冲突时保存结构化 Blocker（resource 使用完整 RecordRef，state/message/code 明确），不混入部分写。每次块结算重建完整 outcome 并更新同一 ProjectOperation，不覆盖已经提交的块证据。

- [ ] **Step 6: 验证仓储行为**

Run: `uv run --directory apps/backend pytest tests/integration/test_project_data_status_batches.py -q`

Run: `uv run --directory apps/backend ruff check src/autoflow/infrastructure/database/project_data_status_batches.py tests/integration/test_project_data_status_batches.py`

Run: `uv run --directory apps/backend mypy src/autoflow/infrastructure/database/project_data_status_batches.py`

- [ ] **Step 7: 提交本任务**

```bash
git add apps/backend/src/autoflow/domain/project_data/status_batches.py apps/backend/src/autoflow/infrastructure/database/project_data_status_batches.py apps/backend/tests/integration/test_project_data_status_batches.py
git commit -m "feat(project-data): commit durable status blocks atomically"
```

### Task 4: 用专用协调器推进并在重启后恢复

**Files:**
- Create: `apps/backend/src/autoflow/application/project_data/status_batch_coordinator.py`
- Create: `apps/backend/tests/unit/test_project_data_status_batch_coordinator.py`
- Modify: `apps/backend/src/autoflow/infrastructure/database/project_data_status_batches.py`

**Interfaces:**
- Consumes: `recoverable_operation_ids()`、`claim_next_block()`、`commit_block()`、`fail_block()`。
- Produces: `StatusBatchCoordinator.start()`、`wake(operation_id)`、`shutdown()`、`active()`；它只调度 status batch，不接受任意 callable/job kind。

- [ ] **Step 1: 写协调器 RED 单元测试**

用 fake repository 验证：启动枚举旧 `accepted/running` 操作；同 operation 多次 wake 只有一个 drain task；每次只 claim/commit 一个块后让出事件循环；无块即退出；块冲突后仍结算 Operation 但不启动新 Operation；取消后不 claim 后续块；shutdown 停止新 claim 并等待当前数据库调用结束。仓储暂时异常时保留可恢复状态并退出当前 drain，不能把未知错误改成业务冲突或无限忙循环。

- [ ] **Step 2: 运行 RED**

Run: `uv run --directory apps/backend pytest tests/unit/test_project_data_status_batch_coordinator.py -q`

Expected: FAIL，协调器尚不存在。

- [ ] **Step 3: 实现窄协调器**

使用 `asyncio.Task` 集合按 operationId 去重。同步 SQL 仓储调用通过现有 Starlette/AnyIO 线程工具执行，不能阻塞 event loop；不创建子进程、队列或通用 worker。`start()` 只恢复本 kind；`wake()` 只接收已持久 operationId；`shutdown()` 设置停止领取门闩并有界等待当前块事务结束。进程被硬杀时依赖 Task 3 的 claimed 恢复规则，不依赖内存 future 判定完成。

- [ ] **Step 4: 增加真实 SQLite 恢复集成测试**

在 `test_project_data_status_batches.py` 接受三块，只推进第一块，销毁协调器/仓储实例，再创建新实例并 `start()`；断言同一 operationId 最终完成、第一块未重复写/未重复 revision，后两块按原 targets 顺序处理。另测第一块提交后第二块冲突，重启不重试 committed/conflicted 块；以及 cancel 后重启仍保持 cancelled blocks。

- [ ] **Step 5: 验证协调器和恢复**

Run: `uv run --directory apps/backend pytest tests/unit/test_project_data_status_batch_coordinator.py tests/integration/test_project_data_status_batches.py -q`

Run: `uv run --directory apps/backend ruff check src/autoflow/application/project_data/status_batch_coordinator.py tests/unit/test_project_data_status_batch_coordinator.py`

Run: `uv run --directory apps/backend mypy src/autoflow/application/project_data/status_batch_coordinator.py`

- [ ] **Step 6: 提交本任务**

```bash
git add apps/backend/src/autoflow/application/project_data/status_batch_coordinator.py apps/backend/src/autoflow/infrastructure/database/project_data_status_batches.py apps/backend/tests/unit/test_project_data_status_batch_coordinator.py apps/backend/tests/integration/test_project_data_status_batches.py
git commit -m "feat(project-data): resume durable status batches"
```

### Task 5: 接入 HTTP、Operation 查询和 Quiesce

**Files:**
- Create: `apps/backend/src/autoflow/adapters/http/project_data_status_batches.py`
- Create: `apps/backend/src/autoflow/adapters/http/project_data_status_batch_schemas.py`
- Modify: `apps/backend/src/autoflow/adapters/http/project_schemas.py`
- Modify: `apps/backend/src/autoflow/bootstrap/app.py`
- Modify: `apps/backend/src/autoflow/application/settings/runtime.py`
- Create: `apps/backend/tests/contract/test_project_data_status_batches.py`
- Modify: `apps/backend/tests/contract/test_projects.py`
- Modify: `apps/backend/tests/contract/test_settings_dashboard.py`

**Interfaces:**
- Consumes: Tasks 1–4 的 service/repository/coordinator；现有三条 Operation GET 路由。
- Produces: 规格冻结的 preview/start/cancel 三路由；OpenAPI 中 `setRecordStatuses`/`cancelRecordStatuses` 和完整 result/resource/status 联合；workspace blocker `project_data_status_batch_active`。

- [ ] **Step 1: 写 HTTP/OpenAPI RED 契约测试**

精确覆盖：preview 200 且无 Operation；start 202 `{operation}`；同 key replay 返回同 operation（仍为 202）；cancel 202。验证 camelCase、extra forbid、UUID/revision/数量/blockSize 边界、401、project/table scope、404/409/410/412/422/423。检查 OpenAPI 的请求、preview、block、outcome、cancel result 均可达；Operation kind 含两项，status 至少含 `accepted/running/succeeded/failed`，resource 为 table，failed result 仍允许完整 outcome 且 error 必填由运行时测试保证。

- [ ] **Step 2: 写查询恢复 RED 契约测试**

start 后立即按 operationId 与 idempotency key 查询同一非终态 Operation；处理一块后查询能看到该块 committed 和原始 revisions；全部完成、冲突、取消分别得到冻结 outcome。`GET /operations?kind=setRecordStatuses&status=running&resourceType=table` 可列出。历史 Operation 查询不因记录后续人工修改而改变 before/committed revision 证据。

- [ ] **Step 3: 写 Quiesce RED 测试**

构造已接受且仍有 `notStarted/claimed` block 的操作，断言 runtime blockers 含 `project_data_status_batch_active`，workspace quiesce 返回该 blocker 且不切换。先暂停 gate 再唤醒协调器，断言没有新块被 claim；当前块完成后仍保持 blocker，直到操作终态。终态后 blocker 消失，可成功 quiesce。读取 preview/Operation 不应被当成活动写 blocker。

- [ ] **Step 4: 实现 schema 与路由**

Pydantic 模型逐字映射冻结 DTO，`targets` 最大 1000、`blockSize` 默认 100；更复杂的 typed identity/重复规则仍由领域层统一校验。start handler 持久接受后调用 `coordinator.wake(operationId)`，只返回已持久 Operation；即使 wake 失败，accepted 事实仍可由启动恢复。cancel handler 持久关闭门闩后 wake 原 Operation 以完成结算。不要使用 FastAPI `BackgroundTasks` 作为耐久事实来源。

- [ ] **Step 5: 扩展 Operation 投影**

`ProjectOperationView.status` 从仅 `succeeded` 改成当前契约五态；kind 增加两项；result 联合增加 `RecordStatusBatchOutcome/CancelRecordStatusesResult`。resource 沿用 `TableResourceLocator`。项目 operation 列表过滤枚举同步增加两 kind；查询继续使用现有 `SqlAlchemyProjects.get_operation/list_operations`，不另建批量查询 API。

- [ ] **Step 6: 接入 bootstrap 生命周期与 Quiesce**

创建单例 repository/service/coordinator，注册 router；FastAPI startup 调 `coordinator.start()`，shutdown 先 `coordinator.shutdown()` 再 dispose session factory。给 `QuiesceGate` 增加只读 `accepting_mutations() -> bool` 或等价受锁检查，协调器每次 claim 前检查，避免 pause 成功后启动后台块。将 `repository.active_operation_count()>0` 映射为 `project_data_status_batch_active` 加入 SettingsRuntimeService 外部 blockers。这里的 blocker 表示同一 workspace 内仍有耐久工作待收口，不因当前没有 SQL 事务就允许换库。

- [ ] **Step 7: 运行契约与设置回归**

Run: `uv run --directory apps/backend pytest tests/contract/test_project_data_status_batches.py tests/contract/test_projects.py tests/contract/test_settings_dashboard.py -q`

Run: `uv run --directory apps/backend pytest tests/integration/test_project_data_status_batches.py tests/integration/test_project_data_records.py -q`

Run: `uv run --directory apps/backend ruff check src/autoflow/adapters/http/project_data_status_batches.py src/autoflow/adapters/http/project_data_status_batch_schemas.py src/autoflow/adapters/http/project_schemas.py src/autoflow/bootstrap/app.py src/autoflow/application/settings/runtime.py`

Run: `uv run --directory apps/backend mypy src/autoflow/application/project_data/status_batches.py src/autoflow/application/project_data/status_batch_coordinator.py src/autoflow/infrastructure/database/project_data_status_batches.py src/autoflow/adapters/http/project_data_status_batches.py`

- [ ] **Step 8: 提交本任务**

```bash
git add apps/backend/src/autoflow/adapters/http/project_data_status_batches.py apps/backend/src/autoflow/adapters/http/project_data_status_batch_schemas.py apps/backend/src/autoflow/adapters/http/project_schemas.py apps/backend/src/autoflow/bootstrap/app.py apps/backend/src/autoflow/application/settings/runtime.py apps/backend/tests/contract/test_project_data_status_batches.py apps/backend/tests/contract/test_projects.py apps/backend/tests/contract/test_settings_dashboard.py
git commit -m "feat(project-data): expose durable status batches"
```

### Task 6: 故障矩阵、全量验证与交付证据

**Files:**
- Modify: `apps/backend/tests/integration/test_project_data_status_batches.py`
- Modify: `apps/backend/tests/contract/test_project_data_status_batches.py`
- Modify: `docs/project-management/implementation/execution-ledger.md`
- Modify: `docs/superpowers/plans/2026-09-13-project-management-pm2.md`
- Modify: `.ai/memory/project-context.md`

**Interfaces:**
- Consumes: 完整批量实现与冻结 `DATA-STATE-07` / API 契约。
- Produces: 可复核的故障注入证据；只更新实际通过范围，不提前声称 PM4 lease 或完整 PM2 UI 已验收。

- [ ] **Step 1: 补齐提交点故障注入测试**

逐点注入并断言原子结果：accept 写 Operation 后失败；写 batch 后失败；写部分 blocks 后失败；块修改第一行后失败；写 DataChange 中途失败；写 block outcome 后 Operation 更新失败。每个 accept 故障都无孤立事实；每个 block 故障都保持块可重试且所有记录/revision/change 未写。再运行一次同 operation，结果只能有一份 committed 事实。

- [ ] **Step 2: 补齐竞争与范围矩阵**

覆盖 cancel 与 claim 竞争、cancel 与最后一块提交竞争、两个 cancel key、同 expectedOperationRevision 仅一个生效、另一个项目猜 operationId、另一表猜 operationId、状态删除与块提交竞争、记录删除与块提交竞争、quiesce 与下一块 claim 竞争。每次断言稳定终态、完整 outcome 和无跨 scope 变化。

- [ ] **Step 3: 跑后端完整验证**

Run: `uv run --directory apps/backend pytest -q`

Run: `uv run --directory apps/backend ruff check .`

Run: `uv run --directory apps/backend mypy src`

Run: `uv run --directory apps/backend python -m alembic -c src/autoflow/infrastructure/database/alembic.ini upgrade head`

Expected: 全部退出码 0；Alembic head 为 `pm02_status_batches`。

- [ ] **Step 4: 核对 OpenAPI 与静态计划**

Run: `uv run --directory apps/backend python -c "from autoflow.bootstrap.app import create_app; s=create_app().openapi(); p=s['paths']; assert '/api/v1/projects/{projectId}/tables/{tableId}/record-status-batches' in p; assert '/api/v1/projects/{projectId}/tables/{tableId}/record-status-batches/preview' in p; assert '/api/v1/projects/{projectId}/tables/{tableId}/record-status-batches/{operationId}/cancel' in p"`

Run: `uv run python docs/project-management/implementation/verify-pm0.py`

Expected: 退出码 0。若 verify-pm0 对新增文档状态有刻意限制，先核对其规则并由 root 更新覆盖账本，不能删检查绕过。

- [ ] **Step 5: 更新真实证据边界**

在 execution ledger 与 PM2 执行卡记录提交、测试数、OS/架构、迁移 head 和故障场景。`.ai/memory/project-context.md` 只写已验证稳定事实：耐久批量后端完成、真实 lease guard 仍待 PM4、renderer 页面/生成类型/真实 Electron 是否完成按实际结果描述。不要把本后端包写成 PM2 整体交付。

- [ ] **Step 6: 提交验证记录**

```bash
git add apps/backend/tests/integration/test_project_data_status_batches.py apps/backend/tests/contract/test_project_data_status_batches.py docs/project-management/implementation/execution-ledger.md docs/superpowers/plans/2026-09-13-project-management-pm2.md .ai/memory/project-context.md
git commit -m "test(project-data): verify durable status batch recovery"
```

## 不确定点与实施裁定

1. **真实 lease/占用来源尚不存在（高置信）**：PM2 代码中没有 Project Task/DataLease 持久模型。此包应定义并注入 occupancy guard，当前默认实现只在“系统没有该实体”时返回空；PM4 接入真实 guard 后重跑 `DATA-STATE-08` 并发验收。不能用这个空实现宣称“活动 Task 阻断”已完成。
2. **Operation resource 无专用批状态分支（高置信）**：冻结 `ResourceLocator` 只有 table/record/batch 等，`batch` 明确是执行 Batch。建议 status batch 使用 table locator；不要滥用 `{type:'batch'}`，否则会把数据维护 Operation 与执行 Batch 身份混淆。
3. **`cancelled` 不是当前 OperationStatus（高置信）**：契约要求原批量操作以 `failed + BATCH_STATUS_CANCELLED` 结束，outcome 才是 `cancelled`；不要私加 Operation `cancelled` 状态。
4. **显式 null 的 no-op 语义看似反常但已冻结（高置信）**：现有单条实现和 PM2 执行卡规定 `statusId=null` 每次推进 statusRevision；批量实现保持一致，除非用户先修改业务规格。
5. **后台协调器与 quiesce 的锁顺序需验证（中置信）**：不能在持有 QuiesceGate 的进程锁时进入 SQLite，也不能在持有 `BEGIN IMMEDIATE` 时调用可能阻塞的外部 guard。当前 occupancy guard 必须是同一数据库 session 内的只读事实查询；未来 PM4 接入时若占用由另一数据库/进程拥有，需先调整契约为可在事务内验证的本地投影。

## 自检

- 规格覆盖：固定目标、每条 CAS、块原子性、部分完成、取消、重启恢复、Operation 身份/查询、原始状态证据、scope/lifecycle、Quiesce 均有明确任务和失败测试。
- 反例覆盖：未将单条接口循环、筛选重算、无限事务、内存 BackgroundTasks、第二执行器或隐式状态业务规则列为实现方式。
- 类型一致：`setRecordStatuses` 对应 `RecordStatusBatchOutcome`；`cancelRecordStatuses` 对应 `{operationId,subsequentBlocksClosed:true}`；两者 resource 均为 table；原批取消以 `failed/BATCH_STATUS_CANCELLED` 表达。
- 交付边界：迁移/HTTP/bootstrap/生成类型由 root 汇合；本文没有修改业务代码，也没有把 PM4 lease、renderer 页面或真实 Electron 验收算作已完成。
