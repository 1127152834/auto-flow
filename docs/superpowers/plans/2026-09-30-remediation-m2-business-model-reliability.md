# M2 业务模型与可靠性 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
>
> **本计划为任务级。** M1 通过退出评审后，先用 `superpowers:writing-plans` 把本文件细化为步骤级（每个任务写出测试代码、实现代码、命令与预期输出），经用户确认后再执行。细化时以 M1 结束时的代码为准，并吸收 M1 基准数据。

**Goal:** 让每一行数据的处理结果可预期：处理台账、失败分类与批次熔断、正式的节点出错策略、流程签名、写回自动版本、定时触发。

**Architecture:** 新增 `automation_record_ledger` 表，在 Task 终态投影的同一事务中更新；失败类别随执行器结果透传到运行错误；熔断是调度器推进批次时调用的纯函数；流程签名是流程文档的新顶层字段，解析与引用改写放在 `domain/workflows/signature.py`；定时复用 `application/workflows/schedules.py`。

**Tech Stack:** Python 3.11、SQLAlchemy 2 + Alembic（`rm2_*`）、pydantic（执行器配置 schema）、FastAPI；React + vitest（最小界面）。

**Spec:** [docs/superpowers/specs/2026-09-30-remediation-m2-business-model-reliability.md](../specs/2026-09-30-remediation-m2-business-model-reliability.md)

## Global Constraints

- 存量自动化迁移后 `claimMode = cycle`，行为不变；新建自动化默认 `unprocessed`、`retryBudget = 3`、退避 `[60, 300, 1800]` 秒。
- 台账更新必须与 Task 终态投影在同一事务；基础设施失败与已取消不增加 attempts。
- 旧出错键（retryCount、retryDelay、retryBackoff、retryExhaustedAction、timeoutAction、旧 errorPolicy.mode）在读取时迁移为新结构，前后端迁移函数有对照测试；原文档保存前不改写。
- 旧引用格式 `PROJECT_INPUTS[...]` 在 M2 与 M3 期间继续解析；M6 删除。
- 所有迁移前自动备份工作区；迁移文件前缀 `rm2_`。
- 不改领取性能（M3）；M2 的台账过滤在现有候选路径中实现。

## Review Focus

1. **同一行被两个自动化处理**：台账主键含 automation_id，两个自动化互不影响各自的尝试次数（Task 1 测试）。
2. **任务在终态投影前进程崩溃**：恢复流程把运行判为 interrupted 时，台账按 unknown / infrastructure 规则更新，不丢记录（Task 2 测试）。
3. **重试预算为 0 或用户把 quarantined 行重置**：重置后 attempts 归零、state=pending，可立即领取（Task 1 测试）。
4. **possible 副作用节点在点击后超时**：不自动重做，归为结果不明（Task 4 测试，黄金场景 G3）。
5. **定时触发时应用未运行**：重启后按 latestOnly 只补一次，不按错过次数补跑（Task 10 测试）。

---

### Task 1: 处理台账表与仓储

**Files:**
- Create: `apps/backend/src/autoflow/infrastructure/database/migrations/versions/rm2_record_ledger.py`
- Create: `apps/backend/src/autoflow/domain/project_runs/ledger.py`（状态、转移规则、退避计算，纯函数）
- Create: `apps/backend/src/autoflow/infrastructure/database/record_ledger.py`（`SqlAlchemyRecordLedger`）
- Test: `apps/backend/tests/unit/test_record_ledger_rules.py`、`apps/backend/tests/integration/test_record_ledger_repository.py`

**Interfaces:**
- Produces: `LedgerState = Literal["pending","succeeded","failed_retryable","quarantined","needs_review","skipped"]`；`next_ledger_entry(entry | None, outcome: TaskOutcome, *, budget: int, backoff: Sequence[int], now: datetime) -> LedgerEntry`；`SqlAlchemyRecordLedger(session).get(automation_id, table_id, record_key)`、`.upsert(entry)`、`.reset(automation_id, keys | state)`、`.skip(...)`、`.eligible_keys(automation_id, table_id, mode, now) -> set[str]`、`.counts(automation_id, batch_id) -> dict[LedgerState, int]`。

**测试要点：** 每种类别的转移（见规格 4.3 表）；预算耗尽进入 quarantined；退避时间按次数取值且超出列表长度时用最后一个；reset 清零；两个自动化互不影响。

---

### Task 2: 终态投影同事务更新台账

**Files:**
- Modify: `apps/backend/src/autoflow/application/project_runs/`（Task 终态投影所在用例；细化时用 `git grep -n "def .*terminal" application/project_runs` 定位）
- Modify: `apps/backend/src/autoflow/application/workflows/dispatcher.py`（恢复路径的 interrupted 结果带 category）
- Test: `apps/backend/tests/integration/test_record_ledger_projection.py`

**Interfaces:**
- Consumes: Task 1 的 `next_ledger_entry`、`SqlAlchemyRecordLedger`；Task 3 的错误 `category`（Task 3 未完成时默认 page）。
- Produces: 每个数据任务终态后台账有且仅有一条对应更新。

**测试要点：** 投影事务回滚时台账也回滚；参数型批次（无数据输入）不写台账；崩溃恢复为 interrupted 的任务按 unknown 规则进入 needs_review。

---

### Task 3: 失败分类贯通

**Files:**
- Modify: `apps/backend/src/autoflow/application/workflows/executors/base.py`（`ModuleResult` 增加可选 `error_code`、`error_category`）
- Modify: 网页类执行器（`web_basic.py`、`web_actions` 相关文件）映射 ELEMENT_NOT_FOUND、NAVIGATION_TIMEOUT 等
- Modify: `apps/backend/src/autoflow/providers/browser/project_graph.py`（运行错误带 category；未知为 page）
- Modify: `apps/backend/src/autoflow/infrastructure/process/project_workflow_worker.py`、`dispatcher.py`（WORKER_LOST、BROWSER_LAUNCH_FAILED、PROXY_CONNECT_FAILED → infrastructure）
- Test: `apps/backend/tests/unit/workflows/test_error_categories.py`、`apps/backend/tests/integration/test_error_category_projection.py`

**Interfaces:**
- Produces: 运行错误 `{code, category, message, hint?, nodeId?, attempt?}`；`ErrorCategory = Literal["infrastructure","page","business","unknown","cancelled"]`。

**测试要点：** 每个稳定编码映射到类别；日志保留原始异常类型；凭据脱敏不受影响。

---

### Task 4: 节点出错策略正式实现

**Files:**
- Create: `apps/backend/src/autoflow/domain/workflows/error_policy.py`（新结构、旧键迁移、退避计算）
- Modify: `apps/backend/src/autoflow/application/workflows/runtime.py`（`_execute_claimed` / `_dispatch`：retry、goto、onExhausted；每次重试新 attempt 事件）
- Modify: 各执行器声明 `side_effect`
- Create: `apps/desktop/src/renderer/domains/workflows/lib/errorPolicy.ts`（同一迁移函数）
- Modify: `ConfigPanel.tsx`、`BlockFlowView.tsx`、`WorkflowEditor.tsx`（新的统一"出错时"控件；删除 `featureFlags.nodeRetryPolicy` 与 M1 的 `inertSettings`，后端删除 `domain/workflows/inert_settings.py`）
- Test: `apps/backend/tests/unit/workflows/test_error_policy.py`、`apps/backend/tests/unit/workflows/test_runtime_retry.py`、`apps/desktop/src/renderer/domains/workflows/tests/error-policy.test.tsx`、前后端迁移对照测试（后端读取前端导出的样例 JSON）

**Interfaces:**
- Produces: `ErrorPolicy`（规格 R2-08）；`migrate_legacy_error_settings(data) -> ErrorPolicy | None`（前端同名 `migrateLegacyErrorSettings`）；执行器类属性 `side_effect: Literal["none","possible"]`。

**测试要点：** 首次加载超时注入后 retry 节点恢复且有两个 attempt；possible 节点动作后超时不重做而是 unknown；goto 受全局调度上限保护；旧文档打开后显示为等价的新设置。

---

### Task 5: 执行器配置 schema 与精确守门

**Files:**
- Create: `apps/backend/src/autoflow/application/workflows/executors/config_schemas.py`（pydantic 模型注册表）
- Modify: `WorkflowRuntime.preflight`（未知配置键 → 警告 issue）
- Modify: `scripts/ratchets.mjs`（配置键检查改为读取 `python -m autoflow.bootstrap.executor_schema_export` 的输出做精确比较）
- Test: `apps/backend/tests/unit/workflows/test_config_schemas.py`、`scripts/ratchets.test.mjs`

**测试要点：** 每个可执行节点都有 schema；前端面板写入的每个键都在对应 schema 中；`unreadConfigKeys` 为 0。

---

### Task 6: End 节点业务结果

**Files:**
- Modify: `apps/backend/src/autoflow/domain/workflows/project_end.py`、End 执行器、`project_graph.py`（业务失败 → 任务结果 business）
- Modify: `apps/desktop/.../config-panels/ProjectEndConfig.tsx`（业务结果下拉 + 原因）
- Test: `apps/backend/tests/unit/test_project_end_business_result.py`、前端面板测试

**测试要点：** "登录失败 → End(业务失败)"任务结果为 business，台账 skipped，批次继续。

---

### Task 7: 领取模式与台账过滤、maxRows

**Files:**
- Modify: `apps/backend/src/autoflow/domain/project_automations/rules.py`（`claimMode`、`retryBudget`、`retryBackoffSeconds`、`maxRows`；取消 1–100 上限）
- Modify: `apps/backend/src/autoflow/domain/project_runs/rules.py`
- Modify: `apps/backend/src/autoflow/infrastructure/database/project_claims.py`（候选按 `eligible_keys` 过滤）
- Create: `rm2_automation_claim_mode.py`（存量 → cycle）
- Modify: 自动化运行设置界面（`RunPolicyEditor.tsx`：领取模式单选、重试预算）
- Test: `apps/backend/tests/integration/test_claim_modes.py`、`RunPolicyEditor.test.tsx`

**测试要点：** unprocessed 下永远失败的行在第 3 次后不再领取、其余行继续；cycle 与现状一致（复用 `test_reuse_count_uses_physical_input_identity_not_revision_tuple`）；retryFailed 只领失败行；maxRows 为空时直到无可领取行结束。

---

### Task 8: 批次熔断与暂停状态

**Files:**
- Create: `apps/backend/src/autoflow/domain/project_runs/circuit_breaker.py`（纯函数：输入最近任务类别与错误码序列，输出是否暂停及原因）
- Modify: `apps/backend/src/autoflow/application/project_runs/scheduler.py`（推进时评估；新状态 `paused`；继续 / 结束命令）
- Create: `rm2_batch_failure_policy.py`（`continueAfterFailure` → 阈值）
- Modify: 批次详情接口与页面（暂停原因、继续 / 结束按钮、按台账 state 的计数）
- Test: `apps/backend/tests/unit/test_circuit_breaker.py`、`apps/backend/tests/integration/test_batch_pause_resume.py`

**测试要点：** 三条阈值各自触发；业务失败与 unknown 不计入；暂停后进度保留、继续后从台账接着领。

---

### Task 9: 坏行隔离

**Files:**
- Modify: `apps/backend/src/autoflow/infrastructure/database/project_claims.py`（约 555 行的行级错误改为隔离该行）
- Test: `apps/backend/tests/integration/test_bad_row_quarantine.py`（含 Sheets 行校验失败场景，复用 `tests/fixtures/sheets.py`）

---

### Task 10: 定时与 Webhook 启动项目批次

**Files:**
- Modify: `apps/backend/src/autoflow/application/workflows/schedules.py`（`target.kind = automation`、重叠策略、错过补跑）
- Create: `rm2_automation_schedules.py`
- Modify: `apps/backend/src/autoflow/adapters/http/workflow_schedules.py`（或新增自动化调度路由）、OpenAPI
- Modify: 自动化详情"调度"页签
- Test: `apps/backend/tests/integration/test_automation_schedules.py`（可注入时钟）、前端页签测试

**测试要点：** 幂等键 = 调度 ID + 触发时间；skip 下无重叠批次；重启后 latestOnly 只补一次；Webhook 密钥错误返回 401 且不启动。

---

### Task 11: 流程签名（后端）

**Files:**
- Create: `apps/backend/src/autoflow/domain/workflows/signature.py`（模型、校验、`{input.组.字段}` 解析、旧格式兼容）
- Modify: `domain/workflows/validation.py`、`document.py`（接受 `signature`）
- Modify: 项目 worker 输入上下文构建（由签名 + 绑定生成变量）
- Modify: `domain/project_automations/rules.py`（`bindings` 替代 `inputPlan.inputs` 的字段映射部分，旧结构读时转换）
- Test: `apps/backend/tests/unit/workflows/test_signature.py`、`apps/backend/tests/integration/test_signature_binding_run.py`

**测试要点：** 同一流程被两个绑定到不同表的自动化复用；绑定缺字段时启动被拒并指出字段；敏感标记来自签名或表字段。

---

### Task 12: 签名迁移脚本与报告

**Files:**
- Create: `apps/backend/src/autoflow/application/workflows/signature_migration.py`
- Create: `GET /api/v1/migrations/signature-report`
- Test: `apps/backend/tests/integration/test_signature_migration.py`（对 `tests/fixtures/workflows.py` 与项目夹具中的全部流程运行）

---

### Task 13: 写回自动版本与移除运行时表结构操作

**Files:**
- Modify: `apps/backend/src/autoflow/domain/project_data/capabilities.py`（移除 addField / modifyField / deleteField / previewFieldDeletion；预检报错）
- Modify: 写回路径（省略 `expectedContentRevision` 时用领取时冻结版本；按字段判断冲突）
- Test: `apps/backend/tests/integration/test_writeback_auto_revision.py`、`test_runtime_schema_ops_rejected.py`

---

### Task 14: 其余网页原语

**Files:**
- Modify: `web_basic.py`（或新建 `web_storage.py`、`web_intercept.py`）、`scope.py`、`catalog.py`、前端登记点（同 M1 Task 12–13 的清单）
- Test: 单元测试 + 真实浏览器测试（Cookie 读写、localStorage、屏蔽图片请求）

---

### Task 15: 黄金场景与里程碑验收

- 把 G2 扩展为写结果表（使用 Task 13 的写回）；G3 的 xfail 转正（结果不明 → needs_review）。
- 运行全部检查与黄金场景，逐条勾选 AC2-01 至 AC2-10；更新 `.ai`、`docs/PROJECT_STRUCTURE.md`；把 `execution-and-environment.md` §4.1、XE-A21/A22、`.ai/decisions/2026-09-12-project-data-workflow-semantics.md` 标记 superseded（指向本里程碑）。
- 独立评审者做退出评审。
