# PM4 实施计划：多表领取、并发与工作流数据操作

> **状态：** confirmed，2026-09-15 用户批准实施并先交付 V1  
> **工作区：** `/Users/zhangtiancheng/Documents/projects/autoflow-project-management-pm4`  
> **分支：** `codex/project-management-pm4`  
> **基线：** `2bac1b14e45effef42fb27820eadff1043d1ceed`  
> **技能：** `writing-plans` 维护本执行卡；确认后用 `subagent-driven-development` 分包；交付前用 `verification-before-completion` 核验。

## 1. 目标、边界与本轮重要勘误

PM4 只交付项目管理侧的多表输入、原子领取、显式数据操作和完整批次调度。保留 PM0–PM3 的项目、数据、自动化、运行管理、停止与恢复能力，不重建已有模块，不进入 PM5。

本轮按用户最新要求调整执行验证边界：

- Electron、FastAPI、SQLite、项目数据、租约、Task、Batch、Operation、CoreRun 事实和所有管理页面均使用真实实现。
- 工作流执行使用**隔离的确定性假执行器**。它读取真实 Task 输入快照，通过真实项目 capability 服务执行数据操作，并模拟并发、暂停、失败、停止、响应丢失、重启与旧执行代次。
- 假执行器只存在于测试/QA 启动器，不进入生产默认装配，不通过环境变量悄悄替换生产核心。
- 不调用 Studio，不修改 Studio 画布、transport、bridge、节点配置或工作流 worker；不运行真实 CloakBrowser，不声称发生过网页打开、输入、点击或读取。
- 正常生产装配只有在执行端口真实声明 `project.data` 能力时才允许数据型运行。当前核心没有该能力，因此生产应用继续准确显示不可运行；QA 应用由假执行器声明能力，用于完成管理闭环验收。

这一边界能验证 PM4 的真正责任：数据选择、事务、占用、版本、幂等、调度、页面和恢复。真实工作流/浏览器执行留待执行核心具备项目 capability 后做单独集成核验，不能用假执行器证据替代。

## 2. 现场核对结论

### 2.1 基线事实

| 项目 | 当前事实 | 证据 |
|---|---|---|
| PM4 工作区 | 已从 PM3 正式提交创建，分支和工作树干净 | `git rev-parse HEAD`、`git status --short --branch` |
| PM3 交付 | 参数型自动化、批次/任务详情、日志与输出、普通停止/强停/未知结果恢复已交付 | `docs/project-management/implementation/pm3/verification.json` |
| 数据输入配置 | 独立、固定记录、关联、同表角色、别名、必要/可选、字段映射、筛选和排序可以保存 | `domain/project_automations/rules.py`、`InputPlanEditor.tsx` |
| 数据输入执行 | 后端和前端仍明确阻断 | `PROJECT_INPUTS_NOT_SUPPORTED`、`PM4_INPUTS_NOT_SUPPORTED` |
| 当前批次创建 | 启动事务一次预建全部 Task/InputSnapshot/queued CoreRun | `application/project_runs/coordinator.py` |
| 当前调度 | 单容量、并发固定为 1、只派发现有 queued Task | `domain/project_runs/rules.py`、`application/project_runs/scheduler.py` |
| PM2 数据能力 | 表、字段、状态、记录、查询、CAS、幂等、聚合结构保存均已有真实实现 | `application/project_data/*`、`infrastructure/database/project_data_*` |
| 占用模型 | 尚无记录 lease、物理排他键或 Task 写游标 | 当前 migration/model 扫描 |
| 迁移 head | 唯一 head 为 `pm04_project_runs` | `uv run --directory apps/backend alembic -c src/autoflow/infrastructure/database/alembic.ini heads` |
| 定向基线 | 项目自动化/运行/查询相关后端测试可运行 | 本工作区 `45 passed`，仅为基线，不代表 PM4 完成 |

### 2.2 可复用能力与明确缺口

| 可复用能力 | 复用方式 | PM4 缺口 |
|---|---|---|
| `InputPlan` 保存与校验 | 保留现有 DTO、稳定 inputId、alias、FieldRef、RecordRef 和查询表达式 | 缺依赖图执行顺序、运行时预览、候选回溯和错误分类 |
| PM2 查询语言及稳定排序 | 选择器直接调用领域查询/数据库表达式，不另建查询 DSL | 缺候选游标、扫描预算和关联约束组合 |
| PM2 记录/状态/结构 CAS | 复用校验规则和变化证据 | 现有服务各自持有事务，缺 capability 调用者 UoW、lease 与 Task 写游标 |
| PM3 Batch/Task/CoreRun/Operation | 保留身份、事件、停止和恢复协议 | 数据批次需改成 Batch 先接受、Task 按可用并发逐组原子创建 |
| PM3 页面和统一 UI | 扩展现有自动化输入、启动、批次和任务详情 | 缺输入预检、占用/耗尽、数据写证据和有限/不限模式 |
| 旧项目条件与预览代码 | 只读参考谓词、字段/状态校验和只读预览语义 | 旧项目没有可证明的原子领取/lease；不复制其事务架构 |

### 2.3 PM3 实际时间校准

本计划不再使用“人类开发日”推导智能体交付时间。现有证据只能可靠计算提交之间的墙钟跨度和个别测试耗时，不能还原每个智能体的累计运行时间。

| PM3 证据 | 可确认事实 | 可用于 PM4 的结论 | 置信度 |
|---|---|---|---|
| `b74441a` 详细计划 2026-09-14 13:39 → `2bac1b1` 最终交付 2026-09-15 16:07 | 总墙钟跨度 26 小时 28 分 | 这是包含暂停、等待、返工和验证的完整外部跨度，不能叫工程工时 | 高 |
| 执行卡 2026-09-15 05:32 暂停 → 下一提交 12:44 | 7 小时 12 分内没有提交证据，恢复的准确时刻未记录 | 全部扣除该间隔得到 19 小时 16 分，只是第二个墙钟口径，不等于真实活跃时间 | 中 |
| `0d30fbe` 15:28 → `bd5aba5` 次日 02:52 | 真实工作流 runtime/worker/CloakBrowser 连续提交跨度约 11 小时 24 分 | PM4 使用 fake executor，不应继承这段真实执行核心成本 | 中 |
| `b0f1d93` 03:40 → `8aabc69` 04:54 | 自动化管理、资源检查、页面和参数批次提交跨度约 1 小时 14 分 | 现成项目组件/API 的增量装配很快；提交前准备时间未知，不能直接当总耗时 | 低 |
| 12:44 QA 提交 → 16:07 最终交付 | 运行管理 E2E、视觉修复、恢复与文档跨度约 3 小时 22 分 | PM4 每个完整可演示切片应为集成和复验保留至少 1.5–3 小时 | 中 |
| Task 3 全量后端 1193 项 | 131.32 秒 | 单次全量后端等待约 2–3 分钟；GUI、构建、截图和失败重跑才是更大的等待项 | 高 |

因此后文分别报告：

- **预计实际耗时：** 在用户持续授权、机器可用的情况下，从切片开工到满足门槛的墙钟时间，包含并行和必要测试等待，不包含等待用户回复。
- **智能体累计工作量：** 所有智能体运行时间的粗略总和，只用于解释并行度；本环境没有完整计量，均为低置信度估算。
- **工具等待：** 测试、构建、Electron 启停和截图的等待，已经包含在实际耗时中，不再重复相加。
- **人工时间：** 没有人工开发工时；用户最终手测预计 45–90 分钟，既不计入实现时间，也不会在用户执行前标记通过。

## 3. 固定架构与核心契约

### 3.1 执行端口与假执行器

项目运行层新增两个窄端口，避免项目调度器直接依赖具体 Studio/worker：

```python
class ProjectRunPreparationPort(Protocol):
    def prepare_content(..., uow: Session) -> PreparedContent: ...
    def prepare_run(..., input_snapshot_ref: str | None,
                    capability_bindings: list[dict], uow: Session) -> CoreRun: ...

class ProjectRunExecutionPort(Protocol):
    def capabilities(self, prepared_content_id: str) -> ExecutionCapabilities: ...
    def capacity(self) -> int: ...
    def query_run(self, run_id: str) -> CoreRun: ...
    async def dispatch(...): ...
    async def cancel(...): ...
    async def force_stop(...): ...
```

- 生产适配器只包装 PM3 已有 runtime/dispatcher，不修改 workflow worker 或 Studio。
- capability bindings 在 Task 创建事务中冻结；至少包含允许的 project/table/field、操作种类和 readPurpose。项目 capability 服务只信任数据库中冻结的 Run/Task/generation/bindings，不信任调用者临时传入的 scope。
- QA 假执行器通过专用测试启动器注入。它使用真实 runtime 仓储提交 Run 状态和事件，再直接调用真实项目 capability application port；不经 HTTP 自调用。
- 假执行脚本由测试 workflowId 映射到只读 manifest，manifest 位于 QA fixtures。生产数据库不保存“假网页动作”，正常应用也不能选择该适配器。

### 3.2 数据批次接受与任务领取

- 参数型批次保留 PM3 行为和接口兼容。
- 数据型批次启动只在短事务中提交 Batch、冻结请求、PreparedContent 和启动 Operation；初始任务数为 0。
- 调度器按可用槽执行 `prepareInputGroup`，再在一个 `BEGIN IMMEDIATE` 中执行 `commitInputGroup`：重新检查项目、批次领取门闩、数量、自动化/表结构/代次、条件、三个记录修订、lease、执行能力；随后共同提交 Task、不可变 InputSnapshot、去重后的 leases、适用资源请求和 queued CoreRun。
- 任一必要输入失败，Task、InputSnapshot、lease 和 CoreRun 全部不存在。可选输入只有在合法的 `noMatch` 或 `busy` 时写 `value=null` 与对应 `unavailableReason`；配置、结构和权限错误必须阻断。
- 相同物理记录可由多个输入别名引用；快照逐别名保存，lease 只保留一份。

### 3.3 选择器与结果分类

- 输入先按 relation source 建 DAG；环、缺来源、失效字段/状态/记录、类型不兼容为 `configurationError`。
- 按拓扑顺序使用确定排序的深度优先回溯。固定记录先验证；独立输入按其 filter/orderBy 枚举；关联输入基于已选来源追加 exact 约束。
- 选择器不能贪心锁死首个候选。固定反例必须得到 `X=R2/Y=R1`。
- 每次准备最多评估 **10,000 个候选绑定**。这是 PM4 的拟定保护值；达到上限返回 `scanBudgetExceeded`，不当作无数据。后续只能通过有证据的性能修改调整，不静默截断。
- 结果固定为：`ready`、`noMatch`、`temporarilyBusy`、`ambiguous`、`configurationError`、`scanBudgetExceeded`。`noMatch` 才能作为真实耗尽依据。
- 预览不取得 lease、不保证提交成功。提交必须重查全部事实。

### 3.4 RecordRef、物理 lease key 与写游标

本地记录排他键编码为版本化结构：

```text
source=local | projectId | tableId | datasetGeneration | recordKey.type | canonical(recordKey.value)
```

RecordRef 仍是业务引用；lease key 是来源排他身份，两者分别存储。文本 `"001"`、文本 `"1"`、整数 `1` 的 canonical encoding 不同。

新增持久事实：

- `project_record_leases`：leaseId、leaseKey、project/batch/task/run、leaseGeneration、state、created/releasedAt。`held|reconciling` 对 leaseKey 有部分唯一约束。
- `project_task_record_cursors`：Task 对每个 RecordRef 当前确认的 content/status/link revision、leaseId、来源 `initial|dynamic`。它允许本 Task 从 v5 写到 v6 后继续使用 v6；不修改原始输入快照。

Task 终态已确认后释放 lease。停止或运行结果未知时转 `reconciling`，直到权威 Run 结果确定；不能提前释放。旧 executionGeneration 的能力调用一律拒绝。

### 3.5 显式项目数据能力

内部 capability 提供：

- `readProjectRecord`、`queryProjectRecords`
- `createProjectRecord`、`writeRecordFields`、`deleteProjectRecord`
- `setRecordStatus`（含清空）
- `addProjectField`、`ensureProjectField`、`modifyProjectFieldSafely`

规则：

- 读不取得写权。写查询结果时，在同一短事务非阻塞取得动态 lease、校验 scope/CAS、写入、变化证据、幂等 Operation 结果并推进 Task 写游标；任何失败不留下 lease。
- 初始输入使用已有 Task lease。新增记录/字段返回稳定引用；同 operationId 同请求返回原结果，异请求冲突。
- 节点输出不自动写表；Task 成败不自动改业务状态。后续失败不回滚已经提交的显式写。
- 字段修改只允许通过现有结构预检能安全完成的候选；影响变化、超过回填限制或引用受保护时整次拒绝。
- 人工内容写沿用 PM2 规则；人工状态、关联和删除必须检查活动或结果未知 lease。

### 3.6 调度语义

- 有限模式沿用 `maxTasks` 1–100；显式 `maxTasks:null` 表示不限次数。省略字段继续使用自动化默认有限值。没有必要数据输入时禁止不限次数。
- 有效并发为请求值、自动化 `concurrency`、`maxLiveInstances` 与执行端口容量的最小值；每项都必须为正整数。
- 数据 Task 按槽懒创建。释放 lease、Run 终态、停止命令和服务启动会唤醒调度；`temporarilyBusy` 使用事件唤醒并保留 30 秒低频兜底核验，不高频空转。
- 首个确认失败且 `continueAfterFailure=false` 时先关闭领取门闩，不再创建新 Task；已经原子创建的 queued/running Task 继续到权威终态。显式继续策略仍可领取。
- `noMatch` 且当前无活动 Task 才能形成真实耗尽；`temporarilyBusy` 是 blocked。最终状态不变的可复用记录释放后仍可再次领取，因此不限批次需要用户主动停止。
- stop 的事务先关闭领取门闩，再扇出 PM3 cancel；force-stop、撤权、未知结果和恢复沿用 PM3。lease 释放服从权威 CoreRun 事实。

## 4. HTTP 与前端传输变更

### 4.1 接口

新增一个只读预检入口，扩展既有运行 DTO，不建立第二套执行接口：

| 接口 | 变更 |
|---|---|
| `POST /api/v1/projects/{projectId}/automations/{automationId}/input-preview` | `{expectedAutomationRevision}`；返回 per-input 结果、候选组摘要、扫描计数、当前 busy 信息和 runnable。无 Operation、无 lease |
| `POST .../automations/{automationId}/batches` | `maxTasks` 接受整数或显式 null；`concurrency` 允许能力范围内正整数；其余兼容 PM3 |
| `GET .../batches/{batchId}` | 增加 claim gate、selection outcome、阻断原因、有限/不限模式和领取进度 |
| `GET .../tasks/{taskId}` | 输入快照增加完整别名/RecordRef/三个修订/unavailableReason；增加写入事实摘要和当前版本差异 |

工作流 capability 只走内部端口，不暴露“伪装成 Task”的公共 HTTP。所有 HTTP 继续使用现有认证、camelCase、错误 envelope、Idempotency-Key、工作区/实例隔离和 Operation 查询。

### 4.2 前端

- `InputPlanEditor` 保留现有四种配置能力，增加依赖顺序、失效引用、预检结果和各错误类型的清晰展示；仅在服务声明 `project.data` 可用后移除“暂未开放”。
- `BatchStartDialog` 增加有限/不限、并发、失败策略摘要和真实输入预检。预检失败不提交；预览变旧时启动接口仍以服务端重查为准。
- `BatchDetailPage` 展示已创建/活动/目标数量、领取状态、真实耗尽、暂占、停止领取和部分失败。
- `TaskDetailPage` 展示不可变输入、当前记录差异、显式写操作、冲突和未确认事实；读取失败不能伪装成空。
- 继续使用顶部导航、gallery 主体布局、统一细网格表格和小圆角；不新增侧栏，不进入 Studio 页面。

## 5. 调整后的交付顺序与时间

每个切片仍执行失败测试 → 最小实现 → 定向回归 → 规格审查 → 工程审查 → 修复复核 → 独立提交。第一条链只缩小一次性交付面，不削减事务、身份、版本和幂等保护；完整回溯、字段操作与调度策略在后续切片全部补齐。

### 5.1 交付简表

| 交付切片 | 用户能操作什么 | 复用哪些现成能力 | 必要新增 | 负责人 | 预计实际耗时 | 不确定性 |
|---|---|---|---|---|---|---|
| **V1 首条三表链** | UI 配置两个必要输入并启动 1 个 Task；在批次/任务页查看输入；fake 明确修改邮箱状态并新增账号 | InputPlanEditor、BatchLauncher、PM2 查询/状态/新增记录、PM3 Batch/Task/Operation/Run 页面和 QA 启动辅助 | 两输入确定选择、typed lease、原子 Task 提交、最小 capability scope、setStatus/createRecord 幂等、fake adapter、结果投影 | 主协调；选择/前端/QA 三个独立智能体 | **5.5–9 小时** | 中；PM2 session-bound 写原语抽取可能扩大回归 |
| **A 完整输入选择** | 固定记录、关联、同表不同角色、可选输入、复杂条件和预检错误均可用 | 已保存 InputPlan、查询 DSL、字段/状态引用 | DAG、回溯、ambiguity、扫描预算、preview 完整状态 | 数据选择智能体；主协调集成 | 3–5 小时 | 中；recordSlot 旧数据样例质量 |
| **B 完整显式数据能力** | fake 可查询、编辑、删除记录，设置/清空状态，新增/确保/安全修改字段；页面查看冲突和写入证据 | PM2 CAS、结构预检、Operation 查询、Task 输入页面 | 动态 lease、Task 写游标、全部 capability action、稳定引用和错误投影 | capability 智能体；主协调事务接线；前端智能体 | 4–7 小时 | 高；结构保存与已有 aggregate schema 的事务整合 |
| **C 完整批次调度** | 并发、有限/不限次数、失败停止/继续、暂占等待、真实耗尽、停止与恢复 | PM3 scheduler/stop/force/unknown、QuiesceGate | 懒创建、多槽容量、领取门闩、事件唤醒、lease 终结与重启恢复 | 主协调 | 5–8 小时 | 高；竞争时序是 PM3 无直接可比的新复杂度 |
| **F 最终验收** | 完整三表链、第二自动化读取、异常复现、截图和手测 | PM2/PM3 smoke、现有 gallery/统一 UI | PM4 QA 故障控制、全量回归、视觉证据、交付文档 | 主协调；QA 与独立审查智能体 | 3.5–6 小时 | 中；GUI 焦点和截图失败可能增加重跑 |

**总预计实际耗时：21–35 小时。** 这是连续授权后的墙钟区间，包含约 3.5–7.5 小时工具等待；不包含等待用户确认和最终用户手测。智能体累计工作量粗估 41–74 小时，由并行折叠为上述实际时间，置信度低。整体实际时间置信度为低，第一条链完成后必须以实测重新计算 A/B/C/F，不沿用原区间。

### 5.2 第一条链的关键路径

| 顺序 | 工作 | 并行安排 | 墙钟区间 |
|---|---|---|---|
| 1 | 冻结最小 wire contract、执行端口和 migration shape | QA 智能体同时搭 fake 契约测试 | 0.5–1 小时 |
| 2 | 两个 independent 必要输入的确定选择、typed lease 和原子 commitInputGroup | 前端智能体同时接最小 preview/启动状态 | 2–3 小时 |
| 3 | 真实 setStatus/createRecord capability、稳定 operationId 和 ACK 丢失恢复 | QA 智能体接 fake script；前端接 Task 写入摘要 | 1.5–2.5 小时 |
| 4 | Electron 三表链、故障反例、截图、有限审查和修复复验 | 串行关键门槛 | 1.5–2.5 小时 |

并行重叠后首链目标为 **5.5–9 小时实际耗时**。其中智能体累计工作量粗估 12–20 小时（低置信度），自动测试、构建、Electron 启停和截图等待约 0.75–1.5 小时且已包含在实际耗时内；人工开发为 0，用户手测不在首链交付计时内。提交前准备、代码生成和失败修复也已包含；若超过 9 小时，检查点必须报告新增原因和重新估算，不能继续沿用旧数字。

### V1-0：最小合同、迁移与执行 seam

**负责人：主协调者；QA 智能体只修改 tests/qa 和脚本。**

**输入：** XE-C04/C08/C09、两个 independent required inputs、一个有限 Task。  
**生产文件：** `application/project_runs/ports.py`、`core_adapter.py`、`project_run_models.py`、migration `pm05_project_claims.py`、`bootstrap/app.py`。  
**QA 文件：** `tests/qa/pm4_fake_executor.py`、`tests/qa/pm4_app.py`、`scripts/qa-project-management-pm4.mjs`。  
**必要行为：** 生产 adapter 保持 PM3；fake 只能由专用 QA app 注入；新增 lease/cursor 表一次到位，避免后续改 migration 历史。  
**通过条件：** PM3 参数运行回归；fake 不可从生产 bootstrap 选择；报告固定 `executor=fake`、`browser=notExecuted`、`studio=notExecuted`。

### V1-1：两个必要输入与一个 Task 的原子领取

**负责人：gpt-5.6-sol 只实现纯选择函数和测试；主协调者实现数据库 UoW。**

**第一切片仅实现：** 两个 `independent + required` 输入、现有 filter/orderBy、确定首组候选、typed RecordRef、相同物理记录 lease 去重。关系、可选输入和回溯随后在 A 补齐。  
**文件：** `domain/project_runs/input_selection.py`、`models.py`、`application/project_runs/input_groups.py`、`infrastructure/database/project_claims.py`、`project_runs.py`、`coordinator.py`。  
**不可后移的保护：** 项目/表/代次/typed key 身份；三修订重查；两个必要输入和全部 lease、Task、InputSnapshot、queued CoreRun 同一事务；重复 commit 和提交响应丢失找回；任一失败零半任务。  
**反例：** 第二输入 noMatch/busy、代次变化、文本 `"1"` 与整数 `1`、并发抢同邮箱、数据库提交故障。  
**通过条件：** 一个 Task 包含两个不可变输入；任一必要输入失败时 Task/snapshot/run/lease 均为零。

### V1-2：最小显式写入与 fake 执行

**负责人：capability 智能体实现 application service；主协调者接事务；QA 智能体接 fake script。**

**第一切片仅实现：** 对初始 lease 记录执行 `setRecordStatus`，对声明的账号表执行 `createProjectRecord`。完整查询/编辑/删除/字段能力随后在 B 补齐。  
**文件：** `domain/project_data/capabilities.py`、`application/project_data/capabilities.py`、`infrastructure/database/project_capabilities.py`、PM2 record repository 的 session-bound 写原语、`tests/integration/test_project_node_writes.py`。  
**不可后移的保护：** 冻结 capability scope；executionGeneration；expected status revision；稳定 operationId；同键同载荷返回原结果、异载荷拒绝；状态写和新增记录各自短事务；第二步失败不回滚第一步。  
**反例：** ACK 丢失后重试只存在一个账号；旧 generation 拒绝；邮箱人工先改状态后 fake 写冲突；越权表拒绝。  
**通过条件：** 人员不变、邮箱显式改变、账号新增一次；InputSnapshot 未被改写。

### V1-3：最小 UI 与首链门槛

**负责人：前端智能体拥有组件；主协调者拥有页面装配、生成类型和 E2E。**

**文件：** `InputPlanEditor.tsx`、`BatchStartDialog.tsx`、`BatchLauncher.tsx`、`BatchDetailPage.tsx`、`TaskDetailPage.tsx` 及对应测试/API types。  
**行为：** QA 能力下移除数据输入阻断；预览两个必要输入；启动 1 Task；批次页显示领取/运行；任务页显示两个原始输入、邮箱写入和账号引用。生产无 capability 时继续准确阻断。  
**E2E：** UI 创建项目、三表、字段、状态、记录和自动化；workflow/fake manifest 仅作标记 fixture；API 只查询最终事实，不创建项目/自动化。  
**通过条件：** 首条链及 ACK 丢失反例通过，截图和实际数据库事实一致。首链完成后记录各步骤真实开始/结束时间、智能体并行区间和测试等待，并重算剩余切片。

### A：补齐 PM4-A 全部选择能力

**负责人：数据选择智能体；主协调者集成。**

增加 fixedRecord、fieldEquals、sameRecord、recordSlot、同表不同角色、optional、DAG、回溯、ambiguity 和 10,000 候选评估预算；完成 `input-preview` 全错误分类和前端展示。固定反例必须得到 X=R2/Y=R1。预览仍零写入，commit 全量重查。

### B：补齐 PM4-B 全部数据能力

**负责人：capability 智能体和前端智能体分离；主协调者负责 UoW。**

增加 read/query、update/delete record、status clear、add/ensure/safe modify field、查询结果动态 lease、Task 当前写游标、稳定引用、结构影响和冲突页面。覆盖 v5→Task v6→人工 v7→旧写冲突及后续 fake 失败不回滚早先事实。

### C：补齐 PM4-C 调度与恢复

**负责人：主协调者。**

数据 Task 懒创建；完成 concurrency、有限/不限、无批内去重、busy/true exhaustion、默认失败关领取/显式继续、事件唤醒、30 秒低频核验、stop/claim 竞争、unknown lease、重启、旧 generation 和双工作区。不限模式没有隐藏上限，停止后不创建新 Task。

### F：最终集成、视觉与交付

**负责人：主协调者；QA、规格审查和工程审查智能体边界独立。**

完成第二自动化读取账号、全部异常链、PM2/PM3 回归、全量工程检查、同视口截图、`manual-test.md`、`verification.json`、coverage、ledger、PROJECT_STRUCTURE 和 `.ai`。Windows、打包、真实 Studio/CloakBrowser 和用户手测如实保持未执行。

## 6. 自动验收矩阵

| 范围 | 必须通过的反例 |
|---|---|
| 输入选择 | FX/SC-02/03/04/06；回溯；同表角色；typed key；optional 与配置错误分离；预算边界 |
| 原子领取 | 必要输入竞争、代次变化、CAS、重复 commit、COMMIT ACK 丢失、停止竞争均无半任务 |
| 数据写 | SC-05/07/08；新增幂等；Task 自写游标；人工新值冲突；动态 lease 失败零残留 |
| 调度 | 有限/不限、并发、默认停止新领取/显式继续、busy/耗尽、重启、旧代次、工作区切换 |
| 前端 | 预检分类、迟到响应、草稿、启动恢复、输入/写入差异、加载失败不冒充空、键盘/200% |
| 回归 | PM2 数据/Excel/批状态；PM3 参数批次/事件/停止/强停/unknown；其他顶部导航入口 |

日常只跑改动范围的定向测试。F 最终验收执行：

```bash
uv run --directory apps/backend pytest
uv run --directory apps/backend ruff check .
uv run --directory apps/backend mypy src
npm test
npm run openapi:check
npm run typecheck
npm run lint
npm run build
npm run test:scripts
npm run test:structure
node scripts/smoke-project-data.mjs
node scripts/smoke-pm2-detail-flows.mjs
node scripts/qa-project-management-pm3.mjs
node scripts/qa-project-management-pm4.mjs
git diff --check
```

`qa-project-management-pm3.mjs` 只回归管理页面及参数批次事实；不启动 Studio demo。若其固定包含浏览器步骤，改为运行其管理子集并在报告中列明跳过原因，不能把跳过写成通过。

## 7. 真实 QA 与截图验收

### 7.1 V1 第一条业务链

1. 通过 UI 创建“PM4 验收”项目。
2. 通过 UI 创建人员、邮箱、账号三张表和业务状态。
3. 通过 UI 新增人员/邮箱记录；人员满足最终状态且保持不变，邮箱为待使用。
4. 通过 UI 创建自动化、配置两个必要输入、字段映射、邮箱状态条件，并启动有限 1 Task。
5. 启动 fake QA server 和真实 Electron；从启动弹窗检查候选组并启动。
6. 查看 Batch/Task/日志/输入输出；确认账号新增、邮箱改状态、人员未变。
7. 核对启动 Operation、Task/InputSnapshot/leases/queued CoreRun 的原子事实，以及账号新增 Operation 的幂等恢复。

第二条自动化读取账号、连续复用、复杂关联与并发运行在 A/B/C 完成后的 F 最终链执行，不阻塞 V1 提前展示。

### 7.2 异常链

- 同候选并发领取，一组成功、一组 busy；没有半任务。
- 在 preview 与 commit 之间替换数据代次，启动明确失败且旧引用不串新代次。
- fake 在数据写 COMMIT 后丢 ACK；重启后原 operationId 找回，账号不重复。
- fake 在第一项写后、第二项前失败；第一项保留，第二项不存在。
- stop 与 claim 同时发生；门闩胜出后无新 Task。
- force-stop/旧 generation 的迟到 capability 调用被拒。
- unknown Run 保留 lease；核验终态后才释放。
- 两个工作区分别运行，查询、通知、草稿、lease 和 operation 不串。

### 7.3 截图

对照主项目只读 gallery 的自动化输入、启动弹窗、批次详情、任务输入/输出画板，使用相同 viewport 保存：正常、预检 loading、noMatch、busy、configurationError、运行中、部分失败、冲突、停止中和恢复后状态。只允许顶部导航替代原侧栏，以及已批准的统一细网格和小圆角调整。每个画面单独满足现有 85 分门槛，不能用平均值掩盖失败。

截图元数据记录 commit、构建 hash、viewport、DPR、缩放、平台、executor=fake。不得出现“浏览器已验证”或“Studio 已验证”。

## 8. 手动测试交付

`docs/project-management/implementation/pm4/manual-test.md` 必须包含：

- 一条命令启动隔离 fake QA server 与 Electron；显示专用工作区路径和 marker。
- UI 创建项目/表/自动化的逐步点击说明，批量竞争资料可由 QA 工具生成并单独标识。
- 每步预期的 Batch/Task、表记录、业务状态、lease/冲突产品提示。
- 工具按钮或命令制造 busy、ACK 丢失、失败、stop 竞争、服务重启和旧 generation；不要求用户改数据库。
- 通过/失败/未执行、截图路径、反馈格式和只清理带 marker 的测试目录的方法。
- 明确说明 fake 执行器不执行网页；用户手测结果在用户实际执行前保持“未执行”。

## 9. 退出条件

PM4 只有同时满足以下条件才可完成：

1. 数据输入可在 fake QA 能力下通过真实管理 UI 配置、预检、启动和查看。
2. C04 原子领取、C08 只读、C09 显式写入均有数据库故障与并发证据。
3. 三表链和第二自动化读取链通过，且账号新增的 ACK 丢失不会重复。
4. 有限/不限、并发、失败策略、停止、强停、unknown、重启和旧代次撤权通过。
5. PM2/PM3 管理回归、全量工程检查、逐图截图审查通过。
6. 假执行器边界和未验证项表述准确；生产没有虚假解锁数据执行能力。
7. 独立提交、执行卡、审查闭合、verification、截图和手测方案齐全。

完成后停在 PM4 验收点，不进入 PM5。

## 10. 2026-09-15 V1 实施检查点

V1 首条三表链已完成实现、真实管理端端到端、异常反例、有限工程审查和独立视觉复审。权威机器证据为 `docs/project-management/implementation/pm4/qa-runs/v1-mnj43N/result.json`，详细核验见 `docs/project-management/implementation/pm4/v1-verification.md`。

| 检查项 | 实际状态 |
|---|---|
| UI 创建项目、三表、字段、状态、记录和自动化 | 通过 |
| 两个 independent + required 输入原子领取 | 通过 |
| 邮箱显式状态变更、账号幂等新增、人员保持不变 | 通过 |
| 管理页面查看不可变原始输入和写入结果 | 通过 |
| 停止、强停、ACK 丢失、缺 grant、旧执行代次反例 | 通过自动集成验证；用户手测未执行 |
| 六个同视口画面独立视觉评分 | 87–92，全部达到 85 分门槛 |
| 执行边界 | fake executor；真实浏览器、Studio、生产执行核心未执行 |

有限工程复审结论为 PASS，无剩余 V1 工程阻断。V1 后续顺序保持 A → B → C → F，不扩写另一套计划。基于 V1 实测，剩余墙钟估算收敛为 **15–26 小时**：A 3–5 小时、B 4–7 小时、C 5–8 小时、F 3–6 小时。该估算置信度仍为低，主要不确定性是完整回溯的候选规模、动态 lease 与结构操作的事务整合，以及数据型懒调度的竞争恢复；不以缩短估算为由后移数据保护要求。
