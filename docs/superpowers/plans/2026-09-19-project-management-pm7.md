# PM7 实施计划：运行诊断、统计与失败后续

- **状态**：proposed（等待用户确认）
- **日期**：2026-09-19
- **设计依据**：`docs/superpowers/specs/2026-09-19-project-management-pm7-design.md`
- **工作区**：`/Users/zhangtiancheng/Documents/projects/autoflow-project-management-pm7`（分支 `codex/project-management-pm7`）
- **基线 HEAD**：`309cdee1`
- **执行方式**：`subagent-driven-development` 分包；每包先规格审查、再工程审查；交付前 `verification-before-completion`
- **只读**：主项目 `/Users/zhangtiancheng/Documents/projects/autoflow`、旧项目 `browser-automation/autoflow-desktop`、PM3–PM6 工作区

---

## 1. 现场核对（2026-09-19）

| 项 | 结果 |
|---|---|
| HEAD / 分支 | `309cdee1` / `codex/project-management-pm7` |
| 工作树 | 干净，仅 4 个预期未跟踪 `reference/*` 只读符号链接（提交时必须用显式路径，禁止 `git add -A`） |
| Alembic head | 唯一 `pm08_project_sync`；14 个测试文件断言该值 |
| 后端缺口 | `application/projects/overview.py`、`statistics.py` 不存在；`application/dashboard/` 为空；`GET /overview` 是空壳；`statistics` 可用性硬编码 `notImplemented` |
| 后端已就绪 | 批次/任务/人工目录与详情、事件流、节点尝试/日志/输出/附件、输入领取与候选回溯、操作幂等 |
| 前端缺口 | 概览页是 6 项静态资料；统计页不存在；失败后续入口不存在 |
| 前端已就绪 | `TaskEvidence.tsx`（183 行）、`TaskLog.tsx`、`TaskDetailPage.tsx` 已接 `useRunEvents`、`useProjectOverview` hook、统一表格与小圆角体系 |
| 命名裁决 | 覆盖表写的 `TaskEvidencePanel.test.tsx` 不存在；沿用 `TaskEvidence.test.tsx`，验收时更正覆盖表 |

**已验证的基线命令**：`npm run test:structure`（此前 4/4）、`npm run build`、后端 `import autoflow`。这些只证明基线，不构成本次交付验收。

---

## 2. 目标与验收水位

**目标**：把概览、统计、任务证据与失败后续四类管理侧能力接到真实数据与真实页面，端到端可操作、可截图比对。

**验收水位（不得改写）**：

> 管理侧通过，真实执行核心接入待验收。

隔离测试执行器产出真实事件/尝试/输出/附件事实，因此 A/B/C 的管理侧行为可完整验证；生产工作流执行核心、Studio 联合执行不在本期验证范围。

**阶段门槛**（每包都必须同时满足，否则修复后复验）：
1. 功能接入真实页面，不是组件空转。
2. 该包必测端到端用例通过。
3. 逐画板截图对照通过，证据落盘。
4. 独立规格审查 + 工程审查无未闭合阻断。
5. 既有能力（PM2 数据/Excel、PM3 参数运行/停止恢复、PM4 领取、PM5 环境、PM6 Sheets）回归通过。
6. 提交、执行卡更新、问题闭合记录、手测方案齐全。

---

## 3. 交付包、文件所有权与顺序

执行顺序：**P0 → B1 → B2 → C1 → C2 → A1 → 前端（三块并行）→ F**。

主协调者独占：迁移与模型、服务装配、共享契约、事务与调度竞争、生成类型（`shared/api/generated.ts`）、锁文件、`ProjectOverviewPage.tsx` 装配、执行卡与覆盖表。子智能体不得同时改这些文件。

| 包 | 交付行为 | 独占文件 | 依赖 |
|---|---|---|---|
| **P0** 准备 | 冻结基线、更新执行卡、登记文件责任与当前阻断 | 执行卡、`.ai/` | — |
| **B1** 概览聚合 | `GET /overview` 返回真实 counts / activity / recent / dataChanges | `application/projects/overview.py`(新)、`adapters/http/projects.py`、`adapters/http/project_schemas.py`、`application/projects/service.py` | P0 |
| **B2** 统计聚合与下钻 | `GET /statistics`、`GET /statistics/{resultSetId}/tasks` | `application/projects/statistics.py`(新)、`adapters/http/project_statistics.py`(新)、`project_statistics_schemas.py`(新)、路由装配 | B1（共用可用性常量） |
| **C1** 领取候选限制 | `select_required(..., candidate_restriction=...)`；受限批次走同一领取路径 | `infrastructure/database/project_claims.py`、`application/project_runs/scheduler.py` | P0 |
| **C2** 后续批次入口 | `POST .../follow-up-batches` → 202 | `application/project_runs/coordinator.py`、`adapters/http/project_runs.py`、`project_run_schemas.py`(如涉及) | C1 |
| **A1** 证据补强 | 节点访问/重试链、当前数据对照、变化来源 | `application/project_runs/queries.py`（只加读取）、`application/project_runs/evidence.py`（如需）、`project_run_evidence*.py` | P0 |
| **FE-OV** 概览页 | 统计条、项目活动、需要关注、继续工作 | `domains/projects/components/OverviewCounts.tsx`、`ActivityFeed.tsx`、`AttentionList.tsx`、`ContinueWork.tsx` + 各自测试 | B1 |
| **FE-ST** 统计页 | 四指标、趋势条形图、失败去向、口径脚注、下钻 | `domains/projects/pages/StatisticsPage.tsx`、`components/StatisticsTrend.tsx`、`FailureDestinations.tsx`、`statistics-api.ts` + 各自测试 | B2 |
| **FE-EV** 证据与后续 | `TaskEvidence` 补强、`FailedRunFollowup` 入口 | `domains/project-runs/components/TaskEvidence.tsx`、`FailedRunFollowup.tsx`、`TaskDetail.tsx`、`pages/TaskDetailPage.tsx`、`pages/RunDirectoryPage.tsx` + 测试 | A1、C2 |
| **F** 集成与阶段验收 | 端到端、截图、全量检查、覆盖表与手测方案 | 执行卡、覆盖表、`docs/project-management/implementation/pm7/`、QA 脚本 | 全部 |

---

## 4. 每包的任务卡

### P0 准备

- **输入**：§1 核对结果。
- **动作**：更新 `docs/superpowers/plans/2026-09-14-project-management-pm3.md` 之后的 PM7 执行卡（本文件）状态；在 `.ai/sessions/` 记录基线；登记 4 个未跟踪 `reference/*` 为预期。
- **交付行为**：无业务代码改动。
- **通过条件**：`git status` 只有预期项；执行卡与实际代码一致。
- **工时**：0.25 小时。

### B1 概览聚合

- **输入合同**：`GET /projects/{projectId}/overview?timezone=`；`timezone` 为 IANA 名，非法 422；缺省主机本地时区。响应 = §5.1（spec）的 `ProjectOverview`。
- **可复用**：`application/projects/service.py` 的 `ProjectService`（取项目）、`project_data_models.DataChangeRow`、`project_run_models` 的 `ProjectBatchRow/ProjectTaskRow/ProjectTaskInputSnapshotRow`、`project_automations`、`project_data_models.DataTableRow`、`environment_models`。
- **修改文件**：见 §3 表。
- **交付行为**：
  - `counts` 取四个真实计数；
  - `dataChanges` 由 `project_data_changes` 按 `[dayStart, now]` 聚合，区分 `before IS NULL` 的新增与双向非空的更新；
  - `recent` 上限 20，来源为数据变化 + 批次终态 + 人工事项终态 + 已完成同步操作；
  - `activity` 按 spec D6 的六类判据产出（`cleanup` 本期不产出）；`resource` 只做冻结引用存在性检查；
  - `availability.statistics` 改为 `available`。
- **测试用例**（`tests/integration/test_project_overview.py` 新建）：
  1. 空项目：`counts` 真实为 0，`activity`/`recent` 为空数组，**不出现假数字**；
  2. 创建 2 自动化 + 3 表 → `counts.automations == 2`、`counts.tables == 3`；
  3. 造 3 条新增变化 + 2 条更新变化 → `dataChanges.newRecords == 3`、`updatedRecords == 2`；
  4. 变化落在 `dayStart` 之前 → 不计入；
  5. 一个失败任务 + 一个等待人工 → `activity` 同时含 `kind='task'` 与 `kind='manual'`；
  6. 非法 `timezone` → 422；
  7. `availability.statistics == 'available'`。
- **通过条件**：以上 7 项通过；`ruff` 与 `mypy src` 对改动文件无新增告警。
- **工时**：3–5 小时。

### B2 统计聚合与下钻

- **输入合同**：`GET /statistics?from,to,timezone,automationId?,tableId?,interval=day|week|month`；`resultSetId` 不透明；`GET /statistics/{resultSetId}/tasks?result,intervalStart?,page,pageSize`。
- **可复用**：`queries.py::_page`、`queries._range` 的风格；`WorkflowRunRow.completed_at / started_at / status`；`standard library zoneinfo`（不新增依赖）。
- **修改文件**：见 §3 表。
- **交付行为**：
  - 冻结谓词 `status ∈ TERMINAL ∧ from ≤ completed_at ≤ min(to, calculatedAt)`；
  - `resultSetId = base64url(payload) + "." + hmac_sha256(payload)[:16]`，密钥未配置时由数据库路径派生；
  - 校验顺序：解析失败/签名不符 → 404；`now > expiresAt` → 410 `STATISTICS_RESULT_EXPIRED`；
  - 口径按 spec D7；零分母省略 `successRate`；无有效耗时省略 `averageDurationMs`；
  - `trend` 只返回非空桶；
  - `failuresByAutomation` 按自动化聚合失败任务并附最近一次失败原因摘要；
  - 下钻复用 `list_tasks` 的过滤语义读同一冻结集合，返回 `Page<Task>`。
- **测试用例**（`tests/integration/test_project_statistics.py` 新建；固定场景 **成功 2 / 失败 1 / 取消 1 / 中断 1**）：
  1. `sample` 五值正确；`successRate == 2/3`；
  2. `cancelled`/`timed_out`/`interrupted` 不进分母（把取消改成成功不影响否定断言：断言分母恒为 3）；
  3. 只有取消与中断 → `successRate` 字段**缺失**（不是 0、不是 1）；
  4. 无有效耗时（`started_at` 为空）→ 不参与均值；全部无效 → `averageDurationMs` 缺失；
  5. 跨午夜：23:59 与 00:01 两次完成按请求时区分入两个 `bucketStart`，且各只出现一次；
  6. 时区变更（`Asia/Shanghai` vs `UTC`）使同一批任务落入不同桶；
  7. 非法 `timezone`、`from > to`、非法 `interval` → 422；
  8. 同一 `resultSetId` 的 `sample` 与下钻集合一致；
  9. **报告生成后新任务完成** → 用旧 `resultSetId` 重取，`sample` 与下钻集合**均不变**；
  10. 篡改签名 → 404；TTL 注入过期 → 410 且**不回落实时数据**（断言过期后无新任务混入）；
  11. `failuresByAutomation` 计数与失败任务实际数一致。
- **通过条件**：11 项通过；`mypy src` 无新增告警。
- **工时**：5–8 小时。

### C1 领取候选限制

- **输入合同**：`SqlAlchemyProjectInputGroups.select_required(project_id, input_plan, *, candidate_offsets=None, candidate_restriction=None)`，`candidate_restriction: dict[inputId, list[RecordRef]]`。
- **可复用**：`_candidates(...)`（`project_claims.py:355`）、`_parse_record_ref`、`_record_ref`、`_claim_sort_value`。
- **修改文件**：`project_claims.py`、`scheduler.py`。
- **交付行为**：限制只作用于候选集合过滤，**不改变**排序、offset 回溯、`revalidate_selected`、`hold` 与占用语义；未提供 restriction 时行为与现状逐字节一致。
- **测试用例**：
  1. 无 restriction → 与既有领取结果一致（回归）；
  2. restriction 只含记录 A → 只可能领取 A；
  3. restriction 内记录被占用 → `temporarilyBusy`，**不**跳到 restriction 外的记录；
  4. restriction 内记录状态不再满足条件 → `noMatch`，不换行；
  5. restriction 指向已删除记录 → 不抛异常，按不可用处理；
  6. restriction 为空列表 → `noMatch`，不返回全部候选。
- **通过条件**：6 项通过，且既有 `test_project_claim*` 全绿。
- **工时**：3–5 小时。

### C2 后续批次入口

- **输入合同**：`POST /projects/{projectId}/tasks/{taskId}/follow-up-batches`，header `Idempotency-Key`，body `{mode:'originalInputGroup', expectedTaskStatusRevision, parameterOverrides}`。
- **可复用**：`coordinator.start` 的幂等/摘要/事务骨架（`coordinator.py:100-160, 290-380`）、`_operation_row`、`batch_to_dict`、`SqlAlchemyProjectRuns.batch`。
- **修改文件**：`coordinator.py`、`adapters/http/project_runs.py`。
- **交付行为**：spec D8 七步；`frozen_request.followUp` 与 `selection_outcome.followUp` 落库；返回 202 `OperationAccepted`。**不**在协调器内执行领取。
- **测试用例**（`tests/integration/test_project_failure_followup.py` 新建）：
  1. 失败任务 → 202，`operation.kind == 'followUpBatch'`，新批次 `frozen_request.followUp.sourceTaskId` 正确；
  2. 同 `Idempotency-Key` + 同 body 重发 → 返回同一批次，`project_batches` 行数不变；
  3. 同 key + 不同 body → 409 `OPERATION_PAYLOAD_MISMATCH`；
  4. `expectedTaskStatusRevision` 过期 → 409，且**零新增**批次/任务/占用；
  5. 源任务非失败（成功/运行中）→ 409 `FOLLOW_UP_NOT_ALLOWED`；
  6. 源任务属于其他项目 → 404；
  7. 候选记录被删除后推进批次 → 少建或不建任务，**不换行**，`selection_outcome` 记录原因；
  8. 后续批次执行后原失败任务历史（状态、`status_revision`、错误、输出）逐字段不变；
  9. 不自动修改任何业务状态（用状态表快照逐行比对）。
- **通过条件**：9 项通过；幂等与事务属性由测试直接断言，不靠人工检查。
- **工时**：6–9 小时。

### A1 证据补强

- **输入合同**：现有四路由的响应事实扩展；不新增路由。
- **可复用**：`evidence.py` 的 `logs` / `node_attempts` / `outputs` / `artifacts`；`queries.py::task_detail` 的 `dataWrites` 与 `inputSnapshot`。
- **修改文件**：`application/project_runs/queries.py`（只加读取函数）、`adapters/http/project_run_evidence*.py`（如需要）。
- **交付行为**：
  - 任务详情增加“关联数据当前值”：按输入快照中的 `RecordRef` 读取当前记录值，与快照值并列，**标明是当前值**；
  - 增加“变化来源”：把该任务已提交的 `project_data_changes`（`origin='workflow'`，按 `operation_id` 归属）与节点关联；
  - 节点访问与重试链：把 `node_attempts` 按 `nodeId` 聚合为访问序列，同一节点多次尝试合并显示但计数独立。
- **测试用例**（`tests/integration/test_project_run_evidence.py` 扩展或新增）：
  1. 快照值 vs 当前值：任务领取后人工改字段 → 快照不变、当前值更新；
  2. 记录已删除 → 当前值显示“记录已不存在”，不伪造；
  3. 变化来源只含本任务的写入；其他任务的写入不出现；
  4. 同节点三次尝试 → 一条访问 + 尝试计数 3（不是三个任务）；
  5. 日志分页：`afterSequence` 游标不漏不重；新增事件不造成已加载页错位；
  6. 终态后到达迟到事件 → 任务状态字段不变。
- **通过条件**：6 项通过。
- **工时**：4–6 小时。

### FE-OV 概览页

- **组件先于页面**：先完成 4 个组件 + 测试，再由主协调接入 `ProjectOverviewPage.tsx`。
- **视觉依据**：`01-overview/001`（修订候选）、`002`–`009`。
- **测试用例**（每组件各自 `.test.tsx`）：
  1. 统计条：4 个计数 + 今日新增/更新，数值来自 props，不内置演示数字；
  2. 统计条空项目：显示 0 与“暂无数据”文案，不显示原型示例值；
  3. 活动时间线：当前区与最近区分离；每条渲染 title/subtitle/时间/动作；
  4. 活动动作：`resource` 决定跳转目标，对象已删除时按钮禁用并说明；
  5. 需要关注：`severity` 映射视觉；空时不渲染该卡；
  6. 继续工作：真实批次入口可点击；**不出现“执行记录尚未接入”占位**；
  7. 分区独立降级：某一分区传入 error → 该区显示错误，其他区正常；
  8. 长文本：名称 36 字符 + 描述 120 字符不撑宽（断言容器类与换行行为）。
- **通过条件**：8 项通过；`npm run typecheck` 与 `lint` 对该范围无新增告警。
- **工时**：6–9 小时。

### FE-ST 统计页

- **视觉依据**：`04-statistics/001`（v1 approved 旧审查快照）为主，`002`–`009`、`100-*` 为交互态。
- **测试用例**：
  1. 四指标渲染：本期已结束任务（含“成功 x · 失败 y”副行）、成功率、失败任务、平均耗时；
  2. `successRate` 缺失 → 显示“无样本”，**不显示 100%**；
  3. `averageDurationMs` 缺失 → 显示“无有效样本”；
  4. 趋势：只渲染非空桶；桶间空档渲染“无已结束任务”说明行；
  5. 失败去向：按自动化分组、数量、原因摘要、查看记录入口；
  6. 口径脚注逐字包含“成功率 = 成功 /（成功 + 失败）”“不计运行中与等待人工”“任务数不等于数据新增量”；
  7. 加载/空/错误/过期四态：错误保留上次数值与时间标题；过期显示刷新动作；
  8. 筛选变更后整组指标与趋势一起更新；刷新失败不出现新标题配旧数值；
  9. 下钻携带 `resultSetId` 与 `result`；返回后筛选、区间与滚动位置恢复。
- **通过条件**：9 项通过。
- **工时**：6–9 小时。

### FE-EV 证据与后续入口

- **测试用例**：
  1. `TaskEvidence`：节点访问与重试链渲染（同节点三次尝试一条访问）；
  2. 当前值与快照值并列，标签明确区分；
  3. 变化来源只显示本任务写入；
  4. 记录已删除 → 显示事实，不显示可点按钮；
  5. `FailedRunFollowup`：仅失败任务显示入口；成功/运行中不显示；
  6. 二次确认文案明确“不会重放网页动作”；
  7. 修订冲突 → 保留输入并提示，不清空表单；
  8. 提交后响应丢失 → 显示“结果待核验”，按原操作身份查询，不生成新 key；
  9. 未保存离开 → 提示且不静默丢弃。
- **通过条件**：9 项通过。
- **工时**：6–9 小时。

### F 集成与阶段验收

- **动作**：执行 spec §8.2 的 E2E-1…E2E-6；逐画板截图对照；跑全量检查；更新覆盖表（`PM-03`/`OV-01..03`/`RUN-01..03`/`RUN-06`/`ST-01..03`/`DT-11` 状态与证据）与实施账本；编写 `docs/project-management/implementation/pm7/manual-test.md`；更正 `TaskEvidencePanel` 命名。
- **手测方案必须含**：启动命令、隔离工作区路径、界面创建的样例、逐步点击与逐步预期、异常复现工具（TTL 注入、修订冲突、响应丢失）、结果记录表（用例号/通过/失败/未执行/截图位置）、清理方法。
- **通过条件**：spec §8 全部必测项通过 + §4 阶段门槛 6 条全部满足。
- **工时**：8–12 小时。

---

## 5. 验证命令

**每包定向**：

```bash
uv run --directory apps/backend pytest tests/integration/<目标文件> -q
uv run --directory apps/backend ruff check .
uv run --directory apps/backend mypy src
npm --workspace @autoflow/desktop test -- --run src/renderer/domains/<目标路径>
```

**阶段全量（F 包）**：

```bash
uv run --directory apps/backend pytest
uv run --directory apps/backend ruff check .
uv run --directory apps/backend mypy src
npm test
npm run openapi:check          # 新增路由后必须先 npm run openapi:generate
npm run typecheck
npm run lint
npm run build
npm run test:scripts
npm run test:structure
node scripts/qa-project-management-pm3.mjs      # PM3 回归
node scripts/qa-project-management-pm4.mjs      # PM4 回归
git diff --check
```

**注意**：`npm --workspace @autoflow/desktop test` 的路径参数必须相对 `apps/desktop`，用仓库绝对路径会报 `No test files found`。

---

## 6. 端到端与截图验收

### 6.1 端到端环境

真实 Electron + FastAPI + SQLite + 隔离测试执行器。核心项目、表、字段、记录与自动化必须通过**界面**创建；API 仅用于规模资料、竞争修改与事实查询，并明确标注。不调用真实 Studio。

新增 QA 工具 `scripts/qa-project-management-pm7.mjs`，复用既有 PM3/PM4 QA 启动辅助，提供：
- 自动模式：跑完 E2E-1…E2E-6 并落盘结果 JSON；
- `--manual` 模式：保持应用打开供用户操作；
- 故障注入：统计 TTL 过期、后续批次修订冲突、提交后响应丢失、服务重启；
- 截图：按画板编号命名，输出到 `docs/project-management/implementation/pm7/qa-runs/<runId>/`；
- 清理：只清理带本次 runId 标记的测试工作区。

### 6.2 截图对照清单

| 画板组 | 数量 | 状态标注 |
|---|---|---|
| `01-overview/001–009` | 9 | `001` 修订候选（未找到批准记录）；其余旧审查快照 |
| `04-statistics/001–009,100` | 11 | `001` v1 approved 旧审查快照；`006/007/100-*` 修订候选；其余旧审查快照 |
| `03-runs/002–004` | 3 | 任务详情、节点日志、失败后续 |

每画面独立评分 ≥ 85；记录 viewport、缩放、DPR、字体与源码提交哈希。顶部导航与侧栏差异属已批准偏离，不计入扣分。

---

## 7. 风险与不确定性

| 风险 | 影响 | 处置 |
|---|---|---|
| 契约加法式扩展未获批准 | 原型“今日数据变化”“失败任务去向”两块需按缺口登记 | §10 第 1 项待确认；默认按已批准实现，未获批准则降级为缺口并如实登记 |
| 概览“需要关注”只覆盖已提交事实 | 资源健康类关注项缺失 | 已在 spec D6 登记为明确边界；用户确认后不做资源健康探测 |
| 候选限制的语义与既有回溯耦合 | 可能改变既有领取行为 | C1 强制：无 restriction 时行为逐字节一致 + 既有 claim 测试全绿 |
| `failuresByAutomation` 无契约定义 | 属新增响应事实 | 列入待确认项；不批准则删除该字段并如实登记缺口 |
| PM7-A 完整退出依赖真实执行核心 | 无法给出“完整退出” | 交付声明固定为“管理侧通过，真实执行核心接入待验收” |
| 统计聚合在超大项目上的开销 | 响应时间 | `ponytail:` 标记：本期直接聚合，不对 `completed_at` 之外新增索引；出现实测瓶颈再加索引 |
| OpenAPI 生成文件 | 手改会与 `openapi:check` 冲突 | 必须 `npm run openapi:generate` 生成，禁止手改 |

---

## 8. 交付物

1. 独立提交（每包一个）。
2. 更新后的执行卡（本文件）与 `.ai` 记录。
3. 覆盖表更新（PM7 条目状态与证据路径）。
4. `docs/project-management/implementation/pm7/verification.json`（机器核验报告）。
5. `docs/project-management/implementation/pm7/manual-test.md`（可执行手测方案）。
6. `docs/project-management/implementation/pm7/qa-runs/<runId>/`（截图与结果 JSON）。
7. 问题闭合记录。

**PM7 完成后停在 PM7 验收点，不进入 PM8。**

---

## 9. 执行记录（2026-09-19 收口）

| 包 | 状态 | 提交 | 证据 |
|---|---|---|---|
| P0 / B1 / B2 / C1 / C2 / A1 / FE-OV / FE-ST / FE-EV | delivered | `837f9576`、`0ae21ba8` 等前置包 | 见 §4 各包测试文件与 `pm7/verification.json` |
| F 缺陷修复 | delivered | `6e26c6bd`、`5ad992de`、`19823f1e`、`5144079c`、`38a9f983`、`3a52182b` | 三个真实缺陷先补失败用例再修复；三个缺陷写入 `.ai/knowledge/2026-09-19-pm7-management-defects.md` |
| F 下钻/D15 修复 | delivered | `56112678` | 统计下钻改独立页面（评分 62 → 88）；冻结标识长度与过期文案修复；失败运行 `20260918202945`、`20260918203241` 保留 |
| F 端点与文档收口 | delivered（管理侧） | `10fc7b4d` + 本节文档提交 | `pm7/qa-runs/20260918203625/report.json`（passed，16 检查点 / 16 截图，visualReview passed）；`pm7/verification.json`、`pm7/visual-review.md`、`pm7/manual-test.md` |

**自动化检查**：后端 3085 passed / 16 skipped；Ruff 通过；mypy 383 源文件通过；前端 399 文件 / 5417 项通过；openapi:check、typecheck、lint、build 通过；test:scripts 78/0；test:structure 4/0；PM7 self-test 与脚本测试通过；`git diff --check` 干净。

**回归**：PM3 `pm3/qa-runs/run-mjhCtH/result.json`、PM4 `pm4/qa-runs/v1-f52SNQ/result.json`，均以当前 HEAD 真实重跑。

**退出**：固定声明「管理侧通过，真实执行核心接入待验收」；停在 PM7 验收点，不进入 PM8。
