# PM7 设计规格说明书：运行诊断、统计与失败后续

- **状态**：proposed（等待用户审阅）
- **日期**：2026-09-19
- **工作区**：`/Users/zhangtiancheng/Documents/projects/autoflow-project-management-pm7`
- **分支**：`codex/project-management-pm7`
- **基线 HEAD**：`309cdee1`（PM6 实网验收提交）
- **执行技能**：`superpowers:brainstorming`（本文件）、`superpowers:writing-plans`（实施计划）、`subagent-driven-development`、`verification-before-completion`
- **上游权威文档**：
  - `docs/superpowers/plans/2026-09-13-project-management-milestones.md`（PM7 范围）
  - `docs/project-management/design/functional-structure.md`（OV-01/02/03、RUN-01/02/03/06、ST-01/02/03、DT-11）
  - `docs/project-management/implementation/api-contracts.md`（§3.5 路由表、§2 共享对象）
  - `docs/project-management/implementation/contracts.md`（领域不变量）
  - `docs/project-management/implementation/coverage.json`（PM7 覆盖条目）

---

## 0. 一句话结论

PM7 的三包中，**PM7-A 是补强既有的完整工作**（证据端点与 `TaskEvidence.tsx` 已存在），**PM7-B 需要新建统计与概览聚合服务**（`application/projects/overview.py`、`statistics.py` 目前不存在，`overview` 路由是空壳），**PM7-C 需要新增一条受控的“原输入组重取”批次入口**（依赖 `project_claims.select_required` 增加候选限制能力）。三包都不需要新增数据库迁移。

---

## 1. 现场核对结果（2026-09-19，已验证）

| 项 | 实测值 | 验证方式 |
|---|---|---|
| HEAD | `309cdee1 docs(pm6): 记录实网 Google 验收结果` | `git log --oneline -5` |
| 工作树 | 干净；仅 4 个预期未跟踪 `reference/*` 只读符号链接 | `git status --porcelain` |
| Alembic head | 唯一 head `pm08_project_sync` | `tests/integration/test_migration_heads.py:18` 断言 + 迁移文件 `revision`/`down_revision` 扫描 |
| 引用 head 的测试文件 | 14 个 | `grep -rln pm08_project_sync apps/backend/tests/` |
| `application/project_runs/` | 已有 `coordinator.py` `events.py` `evidence.py` `presentation.py` `queries.py` `resources.py` `scheduler.py` | `ls` |
| `application/projects/` | 只有 `service.py`；**无** `overview.py` / `statistics.py` | `ls` |
| `application/dashboard/` | 空目录（仅 `.gitkeep`） | `ls -la` |
| `GET /projects/{projectId}/overview` | 空壳：`counts:{}`、`activity:[]`、`recent:[]` | `adapters/http/projects.py:110-122` |
| `ProjectOverview` schema | `counts: dict[str,int]`、`activity/recent: list[dict[str,Any]]` —— **弱类型，与契约 `AttentionItem[]`/`ActivityItem[]` 不一致** | `adapters/http/project_schemas.py:99-104` |
| `statistics` 可用性 | 硬编码 `notImplemented` | `application/projects/service.py:19-24` |
| 前端 `TaskEvidence.tsx` | 已存在 183 行，已渲染原始输入、写入、批次参数、输出、附件、错误、历史尝试 | `apps/desktop/src/renderer/domains/project-runs/components/TaskEvidence.tsx` |
| 前端 `TaskEvidence.test.tsx` | 已存在 | 同上目录 |
| 前端 `useProjectOverview` / `api.overview` | 已存在但页面未使用真实字段 | `domains/projects/hooks.ts:19`、`pages/ProjectOverviewPage.tsx` |
| 前端 `ProjectOverviewPage.tsx` | 概览页只渲染 6 项静态“项目资料”，无 counts/活动/关注/继续工作 | 同上 |
| 前端统计页 | **不存在**：`statistics` 页签落到 `ProjectCapabilityState` 占位 | `pages/ProjectOverviewPage.tsx:124` |
| `list_tasks` 搜索 | **已满足** PM7 的“搜索任务编号、冻结自动化名及输入语义值”：id/batchId/runId/`frozen_request.automation.name`/参数值/输入值/序号 | `application/project_runs/queries.py:236-276` |
| `node-attempts` / `logs` / `outputs` / `artifacts` 路由 | 全部已实现（`project_run_evidence.py`） | 该文件 21/39/59/77/104/112 行 |
| 终态不可变 | `_TRANSITIONS` 无 `succeeded/failed/cancelled/timed_out/interrupted` 出边；`transition_core_run` 对 `run.terminal` 直接抛 `RUN_TERMINAL`；`completed_at` 仅在进入终态时写入 | `domain/workflows/runtime.py:29-52, 438-460` |
| `project_data_changes` | 有 `resource`(ResourceLocator 形状)、`origin`、`before`、`after`、`created_at`，索引 `(project_id, created_at)` | `infrastructure/database/project_data_models.py:239-263` |
| 领取/回溯机制 | `select_required(..., candidate_offsets=...)` + `_next_candidate_offsets(selection_outcome)` 已实现候选回溯 | `project_claims.py:59-88`、`scheduler.py:43` |
| 数据型批次建任务时机 | `start()` 在 `has_data_inputs` 时**不建任务**（`range(0)`），由 scheduler 逐条领取 | `coordinator.py:331`、`claim_gate_state="open"` |

### 1.1 与历史记录的差异（以本次源码为准）

1. 覆盖表 `coverage.json` 记录的 PM7 计划测试文件名 `TaskEvidencePanel.test.tsx` 与真实代码 `TaskEvidence.test.tsx` 不一致。**本规格裁决：沿用既有 `TaskEvidence` 命名，不新建 `TaskEvidencePanel`。** 覆盖表在验收时同步更正。
2. 历史计划假设 PM7 需要“Studio 真实日志/结果/attempt/变量快照”才能完整退出。该假设仍然成立，但**不构成本期可开发性的阻断**，见 §9.1。
3. PM6 遗留的两项挂起（远端受控增列、系统身份列 501）**不属于 PM7**，本规格只登记，不实现。

---

## 2. 范围

### 2.1 本期交付（PM7-A / B / C）

| 包 | 交付行为 | 原型依据 |
|---|---|---|
| **PM7-A** 完整证据与互查 | 任务详情四视图（输入 / 证据 / 日志 / 输出）在真实数据下完整可用：节点访问与重试链、输入快照与当前值对照、输出与附件、错误与变化来源；日志分页/筛选；迟到事件不覆盖终态；跳转返回保留上下文 | `03-runs/002` 任务详情、`03-runs/003` 节点日志 |
| **PM7-B** 概览与统计 | 概览页真实聚合：顶部统计条、项目活动（当前+最近）、需要关注、继续工作；统计页：四指标、按日处理量、失败任务去向、资源使用未采集、口径说明；同次结果标识下钻 | `01-overview/001-009`、`04-statistics/001-009,100` |
| **PM7-C** 失败后新批次快捷入口 | 从失败任务发起“原输入组重取”新批次：保留来源任务与原输入分组、明确候选范围、按当前状态/条件重新取数、202 OperationAccepted、不重放未知副作用 | `03-runs/004` 失败详情与后续动作 |

### 2.2 明确不做

- 不建第二份日志事实（复用 `project_workflow_run_events` 与 `RunEvent`）。
- 不建自定义 BI、资源监控仓库、通用快照平台。
- 不实现 PM8：归档/恢复/永久删除、生命周期影响、核对（reconciliation）工作台。
- 不实现 PM5 范围外的剩余画板；不实现 PM6 的远端增列与系统身份列。
- 不修改已交付迁移，不改 Studio demo 的画布 / transport / bridge。
- 不新增第二执行器；不引入新的通用任务队列。
- 不新增数据库迁移（理由见 §5.1）。

---

## 3. 现有可复用能力 → 差距清单

### 3.1 后端

| 能力 | 现状 | PM7 动作 |
|---|---|---|
| 批次/任务/人工目录与详情查询 | `project_runs/queries.py` 完整，`list_tasks` 搜索已满足 | **零改动**；只在统计下钻复用 `list_tasks` 的过滤语义 |
| 事件流 `useRunEvents` 支撑 | `application/project_runs/events.py` + `adapters/http/project_run_events.py` | 复用；PM7-A 只补前端订阅与隔离 |
| 节点尝试/日志/输出/附件读取 | `evidence.py` + `project_run_evidence.py` 全路由就绪 | 复用；补“当前数据对照”与“变化来源”的读取 |
| 概览聚合 | 空壳 | **新建** `application/projects/overview.py` |
| 统计聚合 | 不存在 | **新建** `application/projects/statistics.py` + `adapters/http/project_statistics.py` |
| 数据变化证据 | `project_data_changes` 已写入 | 复用为概览“最近活动/数据变化”唯一来源 |
| 输入领取与回溯 | `project_claims.select_required` + `candidate_offsets` | **扩展**：新增可选的候选限制入参（PM7-C） |
| 批次启动与操作幂等 | `coordinator.start` 模式可直接照搬 | **新建** `coordinator.follow_up`，复用同一 `project_operations` 幂等语义 |
| 调度推进 | `scheduler._claim_data_task` | 复用；跟随批次需识别受限候选 |

### 3.2 前端

| 能力 | 现状 | PM7 动作 |
|---|---|---|
| 任务详情页与实时订阅 | `TaskDetailPage.tsx` 已接 `useRunEvents`、断线补读、错误提示 | 复用；补“节点访问/重试链 + 当前数据对照 + 变化来源” |
| 证据面板 | `TaskEvidence.tsx` 已覆盖大部分字段 | **补强现有文件**，不新建 `TaskEvidencePanel` |
| 日志面板 | `TaskLog.tsx` 已有时间线 + 搜索 + 加载更多 | 复用；补筛选态与分页态断言 |
| 概览页 | 静态“项目资料”卡片 | **重写为原型结构**（保留项目头/页签） |
| 统计页 | 不存在 | **新建** `domains/projects/pages/StatisticsPage.tsx` |
| 下钻 | `RunDirectoryPage` 有 `RunPageContext` | **扩展**上下文携带 `resultSetId/result/intervalStart` |
| 失败后续入口 | 不存在 | **新建** `domains/project-runs/components/FailedRunFollowup.tsx` |
| 查询/表格/圆角/顶部导航 | R1–R3、全局表格与圆角体系已交付 | **强制复用**，不新增样式体系 |

---

## 4. 设计决策

### D1：不新增统计快照表，用**可验证的冻结标识 + 确定性重算**（置信度：高）

**论点。** 契约要求“同一 `resultSetId` 下的指标、趋势与下钻集合一致”，并允许在 `expiresAt` 后返回 410。

**证据。** 运行终态是**不可变**的：
- `domain/workflows/runtime.py:29-52`：`_TRANSITIONS` 只有 `queued/running/waiting_manual/resume_queued/finishing/stopping/reconciling` 七个键；五个终态没有出边，因此 `_TRANSITIONS.get(run.status, frozenset())` 对终态返回空集，任何离开终态的目标都会抛 `RUN_STATUS_TRANSITION_INVALID`。
- `runtime.py:438-440`：进入前先判 `run.terminal` 并抛 `RUN_TERMINAL`。
- `runtime.py:460`：`completed_at = now if target_status in TERMINAL_STATUSES else None`；终态既不可再转移，写入后的 `completed_at` 就不会被改写。

因此在冻结谓词 **`status ∈ TERMINAL ∧ from ≤ completed_at ≤ min(to, calculatedAt)`** 下：
- 查询时刻已结束的任务，此后不会被改写；
- 查询时刻未结束的任务，其 `completed_at` 必然 `> calculatedAt`，永远落在谓词之外；
- 结论：**同一标识在 `expiresAt` 前重算得到同一集合**。

**设计。**
- `resultSetId` 为不透明白标量，编码 `{projectId, from, to, timezone, automationId, tableId, interval, calculatedAt}` 并附 HMAC-SHA256 截断签名（密钥来自进程级 secret，未配置时由数据库路径派生）。客户端不得解析或构造。
- `expiresAt = calculatedAt + TTL`（TTL = 24 小时，常量）。
- 下钻先在服务端校验签名与过期；签名无效 → 404 `NOT_FOUND`；过期 → 410 `STATISTICS_RESULT_EXPIRED`；**不回落实时查询**。

**代价与升级路径（`ponytail:` 标记）。** 本实现没有“结果淘汰”动作，只有 TTL；不落盘因此也没有审计轨迹。若将来出现①任务终态可被修正、②需要结果集审计、③需要跨 TTL 复用同一集合，则升级为持久表 `project_statistics_results` + 一次追加迁移。该升级不改变任何对外 DTO。

### D2：不新增迁移（置信度：高）

14 个集成测试文件把 `pm08_project_sync` 断言为唯一 head（`test_migration_heads.py:18`、`test_merged_model_migrations.py:22`、`test_android_m4_migration.py:29` 等）。D1 消除了统计快照表需求；PM7-A 全是读；PM7-C 复用既有 `project_batches` / `project_operations` / `project_record_leases`，新批次信息写入既有 `frozen_request` JSON 列与 `selection_outcome`。

**结论：PM7 零新表、零新迁移、零 head 断言改动。** 这是本设计最大的成本削减项。

### D3：`ProjectOverview` 收紧类型并做**加法式**扩展（置信度：高）

- `activity: AttentionItem[]`、`recent: ActivityItem[]` 由弱类型 `list[dict[str,Any]]` 收紧为 DTO。这是纯类型收紧，字段名与契约完全一致。
- 为满足原型“今日数据变化”，需要日界时区。`GET /overview` 新增**可选** `timezone` 查询参数（IANA 名，非法 422；缺省用主机本地时区），响应新增**可选**字段 `dataChanges`。
- 依据 `api-contracts.md` 表下说明“后续包可扩展响应事实，但不能先建空端点”，加法扩展合规；但这是**对已冻结契约的字面扩展**，因此在 §10 列入需用户确认项。

```ts
type ProjectOverview = {
  project: Project
  counts: {automations?: number; tables?: number; batches?: number; environments?: number}
  availability: ProjectCapabilities
  activity: AttentionItem[]
  recent: ActivityItem[]
  dataChanges?: {          // PM7 新增（本次契约扩展）
    timezone: string
    dayStart: string
    newRecords: number
    updatedRecords: number
  }
}
```

### D4：`statistics` 可用性由 `notImplemented` 改为 `available`（置信度：高）

`application/projects/service.py:19-24` 的 `AVAILABILITY` 常量把 `statistics` 硬编码为 `notImplemented`，会同时影响项目目录、项目详情与概览。PM7-B 交付后改为 `available`。这是行为修正，不是新能力。

### D5：概览只呈现**已提交事实**，不合成推断（置信度：高）

| 原型区域 | 真实来源 |
|---|---|
| 自动化 / 数据表计数 | `project_automations` / `project_data_tables` 按 `project_id` 计数 |
| 批次 / 环境计数 | `project_batches` / `project_environments` 计数 |
| 今日数据变化（新增 / 更新） | `project_data_changes` 按 `created_at ≥ dayStart` 聚合：`before IS NULL AND after IS NOT NULL` 计新增；`before IS NOT NULL AND after IS NOT NULL` 计更新 |
| 项目活动 · 当前 | `status ∈ {queued,running,waiting_manual,resume_queued,finishing,stopping,reconciling}` 的批次；`waiting_manual` 的人工事项；`status ∈ {running, stopping, reconciling}` 的任务 |
| 项目活动 · 最近 | `project_data_changes`（数据创建/编辑/导入）+ 批次终态 + 人工事项终态 + 已完成的同步操作，按 `occurredAt` 倒序，上限 20 条 |
| 需要关注 | 见 D6 |
| 继续工作 | 最近被编辑的自动化、最近被编辑/访问的数据表、最近的活动批次（真实运行记录，**不再使用原型中的“尚未接入”占位**） |
| 资源使用 — 尚未采集 | 统计页按原型保留该行并标注“尚未采集”，不填估算值 |

**证据要求。** 每条 `summary` 必须由已提交行直接生成，禁止出现原型示例中的演示数字（120 / 24 / 6 / 3）。空事实显示空态文案，不显示 0 冒充实测。

### D6：`AttentionItem` 的 kind 与真实判据（置信度：中）

| `kind` | 判据 | `severity` |
|---|---|---|
| `batch` | 批次处于非终态且 `updated_at` 超过停滞阈值 | `info` / `warning` |
| `task` | 任务终态为 `failed` | `error` |
| `manual` | `project_manual_items` 中 `status='waiting'` 且未过期 | `warning` |
| `sync` | PM6 同步操作处于失败或结果未核验 | `error` / `warning` |
| `resource` | 批次 `frozen_request.resourceRequest` 引用的浏览器配置/代理在当前工作区已不存在 | `warning` |
| `cleanup` | 本期不产出（属 PM8） | — |

**边界与不确定性（明确登记）。** `resource` 只做“冻结引用是否仍存在”的存在性检查，**不做资源健康探测**（不做连通性、登录态、占用率）。原型的“账号数据表连接失败 / 检查连接”属于同步连接健康，PM6 已交付 `project_sheets_connections` 状态，`sync` 类直接取该事实。若用户要求完整资源健康，属新增能力，不在本期。

### D7：统计口径（置信度：高）

- 计入总体样本的状态：`succeeded`、`failed`、`cancelled`、`timed_out`、`interrupted`（即全部终态）。
- `successRate = succeeded / (succeeded + failed)`；分母为 0 时**省略字段**（不是 0，不是 100%）。
- `averageDurationMs = mean(completed_at − started_at)`，仅对 `succeeded`/`failed` 中两端时间均存在的样本求均值；无样本时省略字段。
  - 契约要求“含人工与重试、不含启动前排队”：`started_at` 只在首次进入 `running` 时写入（`runtime.py:457-459`：`started_at = run.started_at`，仅当为 `None` 才赋 `now`），`resume_queued → running` 因此不重置，人工等待与节点重试天然包含，排队时间天然排除。**该实现直接满足口径，不需要额外计算。**
- `trend` 桶边界按请求 `timezone` 计算（`zoneinfo`，标准库）；`bucketStart` 为 ISO8601 带偏移。**只返回至少有一个已结束任务的桶**；空桶由前端按原型渲染成“无已结束任务”说明行（`04-statistics/001` 的“09月04日 — 09月08日 无已结束任务。”）。
- `interval`：`day` / `week`（ISO 周一）/ `month`。
- `from`/`to` 为闭区间；`to` 缺省为请求时刻；`from` 缺省为 `to − 7 天`。
- “本期已结束任务”卡 = 五个终态计数之和。

### D8：失败后续批次（PM7-C）语义（置信度：中）

请求：`POST /api/v1/projects/{projectId}/tasks/{taskId}/follow-up-batches`

```jsonc
{
  "mode": "originalInputGroup",
  "expectedTaskStatusRevision": 3,
  "parameterOverrides": {}
}
```

处理步骤（单个 `BEGIN IMMEDIATE` 事务内完成新建，随后交由既有调度器领取）：

1. 幂等：`Idempotency-Key` 头 + `SHA-256(kind='followUpBatch', projectId, taskId, payload)`；同键不同摘要 → 409 `OPERATION_PAYLOAD_MISMATCH`；同键同摘要且已有结果 → 返回原结果（不重复建批次）。
2. 校验 `expectedTaskStatusRevision` 与源任务当前 `status_revision`；不一致 → 409 `TASK_REVISION_CONFLICT`，不建任何对象。
3. 源任务必须处于 `failed` 终态且属于本项目 → 否则 409 `FOLLOW_UP_NOT_ALLOWED`。
4. 读取源任务的 `ProjectTaskInputSnapshotRow`，为每个 `inputId` 抽出**原输入组关系**作为固定候选：`alias → {tableId, datasetGeneration, 候选 RecordRef 列表}`。原始输入组的具体候选来源是“该输入在源任务创建时的候选集”，实现上取 `selection_outcome` 中记录的候选偏移与当时的候选定义，取不到时退化为“源任务已选记录 + 同源定义下当前仍满足条件的候选”，并在 `selection_outcome.followUp` 中如实记录退化。
5. 新建 `ProjectBatchRow`，`frozen_request` 增加：
   ```jsonc
   "followUp": {
     "mode": "originalInputGroup",
     "sourceTaskId": "...",
     "sourceBatchId": "...",
     "sourceTaskRevision": 3,
     "candidateRestriction": {"<inputId>": [/* RecordRef */]}
   }
   ```
6. `status='accepted'`，`claim_gate_state='open'`，`selection_outcome={"status":"pending","followUp":{...}}`。
7. 返回 202 `OperationAccepted`，`operation.kind='followUpBatch'`，`resource` 指向新批次。

调度侧改动：`scheduler._claim_data_task` 读取 `frozen_request.followUp.candidateRestriction`，传给 `SqlAlchemyProjectInputGroups.select_required(..., candidate_restriction=...)`，限制 `_candidates` 的候选集合，再走既有 `revalidate_selected` + `hold` 路径。**候选已失效（记录被删/状态不再满足/代次变化）时不换行**：该组视为本次不可领取，按既有 `noMatch` / `temporarilyBusy` / `configurationError` 语义落 `selection_outcome`，允许少建或不建 Task。

不变量：
- 不自动修改任何业务状态；不重放源任务的网页动作。
- 已匹配的行仍可被同批或后续批次重复取得（无隐藏去重）。
- 未知副作用（源任务 `error.code` 属于结果不明类）时，入口**可见但需二次确认**，且文案明确“不会重放网页动作”。

### D9：前端结构（置信度：高）

- **顶部导航保持不变**；原型中的左侧栏不移植，其余主体布局、信息层级、控件位置按原型对齐。
- 统一细网格表格与小圆角：全部新表复用 `shared/components/ui/table`（`Table` / `TableScroll` / `data-variant`）。
- 概览页布局：`顶部统计条` → 两栏（左：项目活动；右：需要关注 + 继续工作）。`继续工作` 中的“执行记录尚未接入”占位删除，替换为真实批次入口。
- 统计页布局：页头（标题 + 口径副标题 + 右对齐控件行）→ 四指标条（带竖分隔）→ 两栏（左：按日处理量条形图；右：失败任务去向）→ 资源使用未采集行 → 口径说明脚注。
- 条形图为**纯 DOM/CSS**（轨道 + 成功/失败两段），不引入图表库。
- 下钻：统计卡与“查看记录”沿用 `RunDirectoryPage` 的 `RunPageContext`，新增可选 `resultSetId` / `result` / `intervalStart`；返回统计时恢复筛选、区间与滚动位置（工作区作用域内保存）。

### D10：迟到事件与终态（置信度：高）

- 任务终态后停止订阅；已到达的迟到事件不得把终态改回非终态。
- 实现口径：页面渲染的状态源仍为**服务端查询结果**；事件只触发失效重取，不直接写入状态。终态后 `useRunEvents` 以 `disabled` 关闭。
- 分页列表采用“主键/序号游标”，新增事件不会造成已加载页错位或漏读。

---

## 5. 接口设计

### 5.1 新增/变更路由（对应 `api-contracts.md` §3.5）

| 方法 / 路径 | 状态 | 请求 | 响应 |
|---|---|---|---|
| `GET /projects/{projectId}/overview` | **变更**（现有空壳 → 真实聚合；可选 `timezone`） | `timezone?` | `ProjectOverview`（含可选 `dataChanges`） |
| `GET /projects/{projectId}/statistics` | **新增** | `from,to,timezone,automationId?,tableId?,interval` | `ProjectStatistics` |
| `GET /projects/{projectId}/statistics/{resultSetId}/tasks` | **新增** | `result,intervalStart?,page,pageSize` | `Page<Task>` |
| `POST /projects/{projectId}/tasks/{taskId}/follow-up-batches` | **新增** | header `Idempotency-Key`；`{mode,expectedTaskStatusRevision,parameterOverrides}` | 202 `OperationAccepted` |

错误码：`STATISTICS_RESULT_EXPIRED`(410)、`STATISTICS_RANGE_INVALID`/非法时区(422)、`TASK_REVISION_CONFLICT`(409)、`FOLLOW_UP_NOT_ALLOWED`(409)、`OPERATION_PAYLOAD_MISMATCH`(409)、`OPERATION_RESULT_UNKNOWN`(409)。

### 5.2 复用、不新增

- 任务列表搜索：`list_tasks` 已支持任务编号、冻结自动化名、参数值与输入语义值 —— **零后端改动**。
- 任务的节点尝试 / 日志 / 输出 / 附件：沿用既有四路由。
- 操作查询与核验：沿用 `GET /projects/{projectId}/operations/{operationId}` 与既有 reconcile 契约。

### 5.3 DTO（与契约同名同字段）

```ts
type ProjectStatistics = {
  from: string
  to: string
  timezone: string
  sample: {succeeded: number; failed: number; cancelled: number; timed_out: number; interrupted: number}
  successRate?: number
  averageDurationMs?: number
  trend: {bucketStart: string; succeeded: number; failed: number; cancelled: number; timed_out: number; interrupted: number; averageDurationMs?: number}[]
  resultSetId: string
  calculatedAt: string
  expiresAt: string
}
```

外加 PM7 需要的、同为加法式的扩展字段（不替换上述任何字段）：
- `failuresByAutomation: {automationId: string; name: string; count: number; reasonSummary?: string}[]` —— 支撑原型“失败任务去向”。
- `resourceUsage?: never` —— 本期不返回该字段，前端固定渲染“尚未采集”。

`failuresByAutomation` 属新增响应事实，与 `dataChanges` 一并列入 §10 待确认项。

---

## 6. 前端组件与文件设计

### 6.1 新增

| 文件 | 职责 |
|---|---|
| `domains/projects/pages/StatisticsPage.tsx` | 统计页装配：筛选控件、四指标、趋势、失败去向、空/错/加载态 |
| `domains/projects/components/OverviewCounts.tsx` | 顶部统计条 |
| `domains/projects/components/ActivityFeed.tsx` | 项目活动（当前 + 最近）时间线 |
| `domains/projects/components/AttentionList.tsx` | 需要关注卡片与动作 |
| `domains/projects/components/ContinueWork.tsx` | 继续工作列表 |
| `domains/projects/components/StatisticsTrend.tsx` | 按日处理量纯 CSS 条形图 |
| `domains/projects/components/FailureDestinations.tsx` | 失败任务去向分组 |
| `domains/project-runs/components/FailedRunFollowup.tsx` | 失败后续入口与二次确认 |
| `domains/projects/statistics-api.ts` | 统计与下钻 API 客户端 |

### 6.2 修改

| 文件 | 改动 |
|---|---|
| `application/projects/overview.py`（新） | 概览聚合服务 |
| `application/projects/statistics.py`（新） | 统计聚合 + 结果标识签发/校验 |
| `adapters/http/project_statistics.py` + `_schemas.py`（新） | 统计路由与响应模型 |
| `adapters/http/projects.py` | `overview` 接真实服务；新增 `timezone` 参数 |
| `adapters/http/project_schemas.py` | `ProjectOverview` 收紧 + `dataChanges`；新增 `AttentionItem` / `ActivityItem` |
| `application/projects/service.py` | `AVAILABILITY` 的 `statistics` → `available` |
| `application/project_runs/coordinator.py` | 新增 `follow_up(...)`；抽出与 `start` 共用的批次落库步骤 |
| `application/project_runs/queries.py` | 仅在需要时补“当前数据对照”查询；不重写既有过滤 |
| `infrastructure/database/project_claims.py` | `select_required` 支持 `candidate_restriction` |
| `application/project_runs/scheduler.py` | 受限候选批次走同一领取路径 |
| `adapters/http/project_runs.py` | 新增 follow-up 路由 |
| `domains/projects/pages/ProjectOverviewPage.tsx` | 概览页签接入真实聚合；`statistics` 页签接 `StatisticsPage` |
| `domains/projects/hooks.ts` / `api.ts` / `types.ts` | 统计查询 hook 与类型 |
| `domains/project-runs/components/TaskEvidence.tsx` | 补节点访问/重试链、当前数据对照、变化来源 |
| `domains/project-runs/components/TaskDetail.tsx` | 四视图标签与返回上下文透传 |
| `domains/project-runs/pages/TaskDetailPage.tsx` | 下钻上下文与返回恢复 |
| `domains/project-runs/pages/RunDirectoryPage.tsx` | `RunPageContext` 扩展 `resultSetId/result/intervalStart` |
| `shared/api/generated.ts` | `npm run openapi:generate` 重新生成 |

---

## 7. 状态与边界语义

| 场景 | 必须表现 |
|---|---|
| 统计零任务 | 四指标显示 0 或“无样本”，趋势区显示空态文案，**不显示 100%** |
| 成功率分母为 0 | `successRate` 字段省略，UI 显示“无样本” |
| 无有效耗时 | `averageDurationMs` 省略，UI 显示“无有效样本” |
| 统计区间非法 / 时区非法 | 422，保留上一次结果并标注过期 |
| 刷新失败 | 保留上次数值与标题，明确标注“上次刷新时间”，不出现新标题配旧数值 |
| 下钻结果集过期 | 410 → 页面提示“结果已过期，请刷新统计”，提供刷新动作，不静默换数据 |
| 归档项目 | 统计与概览只读可查 |
| 概览分区读取失败 | **只降级该分区**，其他分区保留；不整体显示 0 |
| 加载中 | 骨架/进行中，不显示 0 或“无数据” |
| 迟到事件 | 不覆盖已确认终态；分页不错位 |
| 跳转返回 | 恢复原节点日志位置、原统计范围与页码 |
| 后续批次候选失效 | 明确说明“候选已失效”，可少建或不建任务；不换行、不凑组 |

---

## 8. 验证方案

### 8.1 自动验收

| 文件 | 覆盖 |
|---|---|
| `tests/integration/test_project_statistics.py`（新） | 固定场景“成功 2 / 失败 1 / 取消 1 / 中断 1”：`successRate = 2/3`；取消与中断单列且不进分母；分母为 0 时字段省略；无有效耗时不计入均值；跨日边界按请求时区且唯一归属；非法时区与非法范围 422；同一 `resultSetId` 在下钻与指标间一致；篡改标识 404；超过 TTL 410；报告生成后再有任务完成，旧标识下钻结果不变 |
| `tests/integration/test_project_overview.py`（新） | 计数取真实行；`dataChanges` 只统计时间窗内变化且区分新增/更新；`availability.statistics='available'`；空项目不填假数字；分区失败不影响其他字段 |
| `tests/integration/test_project_failure_followup.py`（新） | 幂等重发返回同一批次；修订冲突 409 且不产生任何对象；非失败任务 409；候选失效少建/不建任务且不换行；不自动改业务状态；原任务历史不变 |
| `apps/desktop/src/renderer/domains/project-runs/components/TaskEvidence.test.tsx`（扩展） | 节点访问与重试链、当前数据对照、变化来源、错误来源 |
| `apps/desktop/src/renderer/domains/projects/pages/StatisticsPage.test.tsx`（新） | 四指标、口径脚注、零分母“无样本”、加载/空/错误/过期、筛选与刷新保持 |
| `apps/desktop/src/renderer/domains/projects/pages/ProjectOverviewPage.test.tsx`（扩展） | 统计条、活动时间线、需要关注、继续工作、分区独立降级 |
| `apps/desktop/src/renderer/domains/project-runs/components/FailedRunFollowup.test.tsx`（新） | 入口可见性、二次确认、冲突保留输入、提交后查询原操作 |

### 8.2 端到端（真实 Electron + FastAPI + SQLite + 隔离测试执行器）

固定三张表场景沿用 PM7 上游既有资料：**人员表**（可重复使用）、**邮箱表**（按状态选取）、**账号表**（由写入产生）。

必测链：
1. **E2E-1 概览事实**：界面创建项目 → 三表 → 自动化 → 跑出成功/失败/取消 → 概览计数、活动、需要关注、继续工作逐项与数据库事实核对。
2. **E2E-2 统计与下钻**：统计页选近 7 天 → 四指标与口径脚注核对 → 点“失败任务”下钻 → 只看到该结果集内的失败任务 → 返回统计范围与位置不变 → 刷新后全部同步更新。
3. **E2E-3 失败后续**：失败任务详情 → 发起后续批次 → 保留来源任务与原输入组 → 新批次按当前条件重取 → 中间修改邮箱状态后再发起，候选按新状态变化且不自动改状态 → 原失败历史不变。
4. **E2E-4 任务证据**：失败任务 → 节点访问与重试链 → 输入快照与当前值对照 → 输出与附件 → 日志分页与筛选 → 迟到事件到达后终态不变。
5. **E2E-5 异常**：统计读取失败、下钻结果过期（TTL 注入）、后续批次修订冲突、响应丢失后按原操作身份找回、服务重启后重新查询。
6. **E2E-6 隔离**：双工作区切换不串数据；归档项目统计只读；200% 缩放与长文本不撑宽。

### 8.3 截图比对

- 逐画板对照：`01-overview/001–009`、`04-statistics/001–009`、`100-*`、`03-runs/002–004`。
- 每个画面记录：viewport、缩放、DPR、字体、源码提交哈希、原型画板编号。
- 每画面独立评分 ≥ 85 且满足全部强制结构项；不用平均分掩盖单页失败。
- **如实标注原型状态**：`04-statistics/001` 是 v1 approved 旧审查快照；`001-*`（概览主页）、`006/007/100-*` 为“修订候选；未找到批准记录”；其余为旧审查快照。候选不等于已确认。
- 保留差异说明：原型为左侧栏，本期按用户长期约束改顶部导航；该差异属**已批准偏离**，不计入扣分。

---

## 9. 交付边界与已知限制

### 9.1 验收水位（必须如实声明）

PM7-A 的**完整**退出依赖 Studio 真实执行核心提供的日志、结果、attempt 与变量快照，而 PM3–PM6 均以“管理侧通过，真实执行核心接入待验收”交付。因此：

> **PM7 交付声明固定为：“管理侧通过，真实执行核心接入待验收。”**

隔离测试执行器能产出真实的事件、节点尝试、输出与附件事实，因此 A/B/C 的**管理侧行为可以完整验证**；但不得据此宣称生产工作流执行可用。

### 9.2 未执行清单（交付时逐项落实）

Windows、其他 CPU 架构、packaged 构建、用户手测 —— 未执行即标注未执行。

### 9.3 登记但不实现

- PM6 远端受控增列（冻结契约无路由/kind）。
- PM6 系统身份列（501 `SYNC_NOT_IMPLEMENTED`）与同表重复远端键不报错。
- 资源健康探测（连通性 / 登录态 / 占用率）。
- PM6 → main 合并未完成；PM7 从 `309cdee1` 这条未合入点长出。

---

## 10. 待你确认的事项（3 项）

1. **契约加法式扩展**：`ProjectOverview.dataChanges`（今日数据变化所需的时区与日界）与 `ProjectStatistics.failuresByAutomation`（失败任务去向）都是已冻结契约之外的新增响应字段。是否批准？不批准则原型中“今日数据变化”与“失败任务去向”两块按缺口登记，不做。
2. **概览的“需要关注”深度**：本期只取已提交事实（失败任务、等待人工、停滞批次、同步失败/未核验、冻结引用失效），**不做资源健康探测**。是否接受这一水位？
3. **失败后续入口的默认可见性**：源任务错误属于“结果不明”类时，入口是否直接可见（点击后二次确认），还是先隐藏直到核对完成？本规格默认**可见 + 二次确认**。

置信度：对 §1 事实、D1、D2、D4、D7、D10 为**高**；对 D3、D5、D6、D8、D9 为**中**；对 §10 第 1、3 项取决于你的答复，当前为**未知**。

---

## 11. 自审记录（spec self-review）

| 检查 | 结果 |
|---|---|
| 占位符扫描 | 无 `TBD`/`TODO`/未填章节 |
| 内部一致性 | §2 交付表、§4 决策、§5 接口、§6 文件表、§8 验证逐项对应；`TaskEvidence` 命名冲突已在 §1.1 裁决 |
| 范围检查 | 未包含 PM8/PM9 内容；未包含远端增列与系统身份列；未新增迁移 |
| 歧义检查 | 统计口径、零分母、空桶、TTL、下钻过期、候选失效均有确定行为 |
| 与契约一致性 | DTO 名称与字段逐字对齐 `api-contracts.md`；两处扩展已显式登记为待确认 |
| 事实可验证性 | 每条源码结论均附文件与行号 |
