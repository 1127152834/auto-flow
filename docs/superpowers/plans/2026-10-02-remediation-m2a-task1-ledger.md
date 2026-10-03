# M2A Task 1：主处理输入、完整身份与台账仓储 步骤级计划

- 日期：2026-10-02；状态：proposed → 执行中（按 M2 任务级计划 Task 1 细化；用户 2026-10-02 指示 M1 本机端到端后继续实施后续里程碑）
- 上位文档：[M2 规格](../specs/2026-09-30-remediation-m2-business-model-reliability.md) R2-01/02/06/07、§2；[M2 任务级计划](2026-09-30-remediation-m2-business-model-reliability.md) Task 1。
- 不做：领取过滤与退避（Task 4）、终态投影（Task 3）、失败分类（Task 2）、HTTP 台账接口与页面（Task 3）。本任务只交付领域规则、表、仓储、迁移和启动门禁，供后续任务挂接。

## 代码事实（2026-10-02 阅读）

- 自动化输入计划 `input_plan` 严格为 `{"inputs": [...]}`（`domain/project_automations/rules.py::_input_plan`），每项有 `inputId/mode/required/tableId/datasetGeneration`。代码中尚无 `claimMode`/`processingInputId`。
- 完整记录身份：`RecordRef(project_id, table_id, dataset_generation, RecordKey(type, value))`；Sheets 身份在租约键 `SheetsLeaseKey.identity_namespace`，任务快照 `project_task_input_snapshots.inputs[*]` 只存 `inputId/leaseId/recordRef…`，命名空间要经 `project_record_leases.lease_key` 取得。
- 未知结果：运行 `interrupted` + `WORKFLOW_RESULT_UNKNOWN`（`application/workflows/dispatcher.py::UNKNOWN_RESULT_ERROR`）。
- 迁移唯一 head：`rm1_app_settings`。

## 设计决定

1. **主处理输入存放在 `input_plan.processingInputId`**（可选键）。校验：必须指向本计划中 `required=true` 的输入；参数型自动化（无输入）不得设置。解析函数 `processing_input(plan) -> str | None | Ambiguous` 在领域层：显式值优先；未设置且恰有一个 required 输入时取该输入；无输入返回 None；多个 required 且未设置返回 `Ambiguous`。
2. **启动门禁**：批次启动（`coordinator._accept_batch` 前）对 `Ambiguous` 拒绝，错误码 `PROCESSING_INPUT_REQUIRED`（409，文案"请先在自动化里选择按哪份数据逐行处理"，不出现内部术语）。启动时把解析结果冻结进 `frozen_request.automation.inputPlan.processingInputId`，之后不再按现配置重解释。
3. **台账表 `automation_record_ledger`**：作用域列 automation_id、processing_input_id、project_id、table_id、dataset_generation、key_type、key_value、identity_namespace（本地表存空串，保证唯一约束对 NULL 也生效）；state、attempts、processing_cycle、cycle_attempts、last_outcome、last_error(JSON)、last_task_id、last_at、next_eligible_at、revision、review(JSON，保存 resolve 决定与原未知事实)、created_at、updated_at。唯一约束覆盖完整作用域。
4. **批次处理单位表 `project_batch_units`**：batch_id、ledger_id、first_task_id、created_at；(batch_id, ledger_id) 唯一。供历史批次统计，不从台账最新状态倒推。
5. **仓储 `SqlAlchemyRecordLedger`**：`get(scope)`、`ensure(scope, now)`（不存在则建 pending）、`list(automation_id, state=None, after=None, limit)`、`reset/skip/resolve(scope, expected_revision, actor_reason, now)`；只接受完整 `LedgerScope`，不接受裸 key。状态转换规则放领域纯函数（`domain/project_runs/ledger.py`），仓储只做持久化与修订检查（不匹配抛 `LEDGER_REVISION_CONFLICT` 409）。活动 Task 检查留到 Task 3 接入（需要终态投影），本任务的命令签名预留 `active_task` 判定参数。
6. **迁移 `rm2_record_ledger`**（down=rm1_app_settings）：建两表；对存量自动化：恰一个 required 输入 → 写入 `processingInputId`；多个 required → 不改，进入迁移报告；对存量 `interrupted`+`WORKFLOW_RESULT_UNKNOWN` 的项目任务，按其冻结的主处理输入记录写入 `needs_review` 台账（review 记录原 run/task 与原因），形成旧未知运行门禁。迁移可重入（已存在的作用域不重复写）。
7. **迁移报告**：领域/仓储函数 `processing_input_report(session)` 返回歧义自动化列表；HTTP 暴露放 Task 3。

## 步骤（每步先 RED 后 GREEN）

1. 领域纯规则 `domain/project_runs/ledger.py`：`LedgerScope`、`LedgerState`、`LedgerEntry`、`scope_for(automation_id, processing_input_id, record_ref, identity_namespace)`；`reset/skip/resolve` 转换（needs_review 拒绝 reset/skip；resolve 三种决定，只有 confirmedNotPerformed → pending，confirmedSucceeded → succeeded，abandon → skipped，保留原未知事实）。测试 `tests/unit/test_record_ledger_rules.py`（含 text "1" 与 integer 1 不同作用域、namespace 不同不同作用域）。
2. `processing_input` 解析 + `_input_plan` 接受并校验 `processingInputId`。测试扩展到 `tests/unit/test_record_ledger_rules.py` 与现有自动化规则测试；OpenAPI 重新生成。
3. 模型 + 迁移 `rm2_record_ledger` + 仓储 `infrastructure/database/record_ledger.py`；测试 `tests/integration/test_record_ledger_repository.py`（真实 SQLite：唯一作用域、修订冲突、分页、resolve 保留原事实、迁移回填与报告、可重入）。
4. 启动门禁与冻结：歧义自动化启动返回 `PROCESSING_INPUT_REQUIRED`；单输入冻结 processingInputId。测试接入现有批次启动集成测试文件。
5. 收尾：ruff、mypy、`npm run openapi:check`、受影响测试与 ratchets；更新 `.ai` 记录与程序索引。

## 风险

- `input_plan` 契约变化影响前端生成类型与保存表单；本任务前端只需透传（不提供选择界面，界面在 Task 4 RunPolicyEditor 一起做），歧义自动化在界面上表现为启动被拒并给出可读原因。
- 迁移在大量历史任务上扫描：按 batch 分页读取，避免一次加载。
