# PM3 设计规格：自动化配置与首个真实参数批次

- 日期：2026-09-14
- 状态：design approved，written spec awaiting review
- 工作区：`/Users/zhangtiancheng/Documents/projects/autoflow-project-management-pm3`
- 分支：`codex/project-management-pm3`
- 实施基线：`c90b3d1`，已接入细网格 `8450601`、小圆角 `b9baa18` 和阶段审计 `95af9a4`
- 既定依据：PM0 契约、PM1/PM2/R1–R3 实施事实、项目管理最新原型集、Automation Studio 规划及归档执行核心

## 1. 目标

PM3 交付一个可实际运行的项目自动化闭环：用户在项目中创建并配置自动化，通过同一份 Studio 工作流文档编辑流程，填写一次批次参数，使用真实 CloakBrowser 执行，随后在项目中查看批次、任务、日志、输入输出和错误证据，并能安全停止、查询不明确结果及在应用重启后找回已提交事实。

PM3 完成后，项目的 `automations` 和 `runs` capability 才从 `notImplemented` 变为 `available`。能力开关必须由真实后端装配决定，不能由前端常量或空页面提前打开。

本阶段不实现多表原子领取与项目数据写入、持久环境、人工介入、Google Sheets、统计聚合、自动化删除的跨未来能力处置和项目归档删除。它们分别属于 PM4–PM8。自动化可以保存未来的数据输入配置，但只在没有项目数据输入时允许 PM3 参数型运行；包含数据输入的配置明确显示“需要后续数据执行能力”，不能静默忽略输入。

## 2. 已核对的真实基线

### 2.1 当前主线

- Studio 已迁入 WebRPA 冻结源码的前端 UI、交互、Store、HTTP/SSE transport 和 Mock 基线。
- 当前后端只通过 `workflow_studio_openapi.py` 发布 Studio schema，没有安装工作流 CRUD、Run、事件或执行 handler。
- `0005_workflow_documents`、`0006_workflow_runs`、`0007_workflow_artifacts`、`0008_workflow_debug` 和 `0009_merge_project_data` 仍在迁移链中，但对应服务代码已从当前主线移除；迁移存在不能视为功能可用。
- 项目后端目前只装配项目资料和 PM2 数据能力。`automations`、`runs`、`environments`、`statistics`、`sync` 均返回 `notImplemented`。
- 主目录仍有另一项 Studio 前端文档工作。本阶段只在 PM3 独立工作区实施，不覆盖主目录未提交文件。

### 2.2 可复用归档

`codex/studio-before-removal-20260913` 保存了已经运行过的工作流文档、校验、Run、事件、日志、调试、artifact、进程 worker 和 CloakBrowser 执行代码。归档代码提供实现来源，不直接整包恢复。

可以复用的核心算法和适配边界：

- `domain/workflows` 的文档结构校验、变量引用、控制流编译和运行准备；
- `application/workflows` 的文档 CRUD、运行事件、停止和完成持久化思路；
- `infrastructure/database/workflows.py`、`workflow_runs.py` 的仓储行为；
- `infrastructure/process/workflow_worker.py` 和 `providers/browser/workflow_*` 的进程隔离及浏览器执行；
- `adapters/events/workflows.py` 的断线补读和 SSE 投影；
- 运行 artifact 与诊断文件的受控读取方式。

必须改造后才能复用：

- 旧错误响应和路由需要接入当前认证、`ErrorEnvelope`、camelCase DTO 和唯一 OpenAPI 生成流程；
- 旧 `WorkflowRunService.start()` 自行取得资源、创建事务并立即启动，不能满足项目侧 Task、输入快照和 queued CoreRun 同事务提交；
- 旧 `active_slot` 只表达单工作区单运行，PM3 可继续把运行容量设为 1，但必须通过明确容量服务表达，不能把数据库唯一约束当产品状态；
- 旧 Run payload 混合工作流快照、资源快照、状态和结果，需要分离不可变 prepared content、CoreRun 状态与项目 Task 投影；
- 旧启动接口接收完整 renderer 文档，项目运行必须只接受 `workflowId`、期望修订和参数，由服务端读取并冻结内容；
- 旧 worker 节点目录必须受当前已冻结的 Studio 节点范围和服务端 runnable catalog 双重约束。

不会恢复的旧行为：任意浏览器品牌、renderer 提供文件路径、项目专用执行器、服务内部 HTTP 自调用、进程重启后自动重跑网页、以 SSE 或日志代替权威 Run 状态。

## 3. 方案选择

### 3.1 未采用方案

1. **整包恢复旧后端**：速度最快，但会带回过期的启动事务、错误协议和运行状态模型，后续 PM4 无法安全加入多表领取。
2. **项目页面继续调用 Mock**：可以较快做出列表和弹窗，但没有可验收业务结果，会制造“页面可用、系统不可运行”的假交付。

### 3.2 采用方案

采用“选择性恢复核心 + 项目层组合”的垂直实现：

```text
Manager 项目页面
  ├── ProjectAutomationService ── Automation 配置与校验
  ├── ProjectRunCoordinator ───── Batch / Task / 输入快照
  └── CoreRunPort ─────────────── prepare / dispatch / query / stop
                                      │
Automation Studio                    │
  └── WorkflowDocumentService ── PreparedContent ── CoreRunService
                                                      │
                                              CloakBrowser Worker
```

Studio/core 不依赖项目领域。项目模块只通过 application port 组合工作流文档和 CoreRun。项目页面和 Studio 使用同一 `workflowId`；不存在项目版工作流副本、第二套执行状态或第二套事件流。

## 4. 领域模型与所有权

### 4.1 Studio/core 所有

| 对象 | 关键字段 | 规则 |
|---|---|---|
| `WorkflowDocument` | `workflowId, source, format, content, revision` | `source={product:'WebRPA',commit}`、`format={kind:'webrpa-workflow',version:1}`；content 是当前 Studio 导出模型的受控投影。CAS 保存；同内容且当前修订保存不推进修订；保存命令以 `saveOperationId` 持久恢复。 |
| `PreparedContent` | `preparedContentId, prepareOperationId, requestDigest, workflowId, sourceRevision, checksum, document, executionPlan, adapterVersion, capabilityRequirements` | `sourceRevision` 是数字 workflowRevision；启动时服务端校验并冻结文档、确定执行计划和适配器版本。创建后不可变；Run 不读取后来编辑的文档或按新代码重新编译。旧运行迁移的 `sourceRevision=null`，并保存明确 legacy provenance。 |
| `CoreRun` | `runId, runRequestId, requestDigest, preparedContentId, parameters, inputSnapshotRef, status, statusRevision, executionGeneration, resourceRequest, capabilityBindings, lastSequence, createdAt, updatedAt, startedAt?, completedAt?, error?` | core 唯一拥有执行状态和终态；`runRequestId` 幂等唯一。 |
| `RunEvent` | `eventId, runId, sequence, executionGeneration, kind, nodeId?, nodeVisitId?, attempt?, occurredAt, payload` | 单 Run 单调序号由核心持久层分配；事件可重复投递，消费者按 eventId/sequence 去重并补缺口；旧 executionGeneration 不能提交。 |
| `RunArtifact` | `runId, artifactId, ordinal, purpose, nodeId, eventSequence, metadata` | 文件由后端受控目录管理，公开接口只返回受控下载入口。 |

`CoreRun` 的 PM3 状态集合为：

```text
queued → running → finishing → succeeded | failed
queued | running → stopping → cancelled
活动状态在进程事实无法确认时 → reconciling → interrupted | 已提交终态
运行预算耗尽 → timed_out
```

终态不可逆。`executionGeneration` 在每次合法执行所有权建立时递增；已撤权 worker 的事件和完成提交被拒绝。

### 4.2 项目模块所有

| 对象 | 关键字段 | 规则 |
|---|---|---|
| `Automation` | `automationId, projectId, workflowId, name, description, managementRevision, inputPlan, parameterSchema, environmentPolicy, runPolicy` | 工作流内容不复制；一个 `workflowId` 最多绑定一个项目自动化。 |
| `Batch` | `batchId, projectId, automationId, automationRevision, workflowRevision, status, statusRevision, requestedCount` | 固定一次启动的配置；不随自动化后续编辑变化。 |
| `Task` | `taskId, batchId, runRequestId, runId, inputSnapshotId, status, statusRevision` | CoreRun 状态的项目投影，不自行判定成功。 |
| `TaskInputSnapshot` | `inputSnapshotId, taskId, parameters, inputs, capturedAt` | PM3 的 `inputs=[]`；参数值不可变；PM4 扩展真实项目数据输入。 |
| `Operation` | `operationId, kind, status, resource, result, error` | 复用项目持久操作体系；`startBatch/stopBatch/forceStopBatch` 均可按原身份查询。 |

修订保持分离：Studio 文档使用 `workflowRevision`；自动化配置使用 `managementRevision`；Batch/Task/CoreRun 使用各自 `statusRevision`。任何通用 `revision` 都不能跨对象复用。

WorkflowDocument 只保留可恢复编辑所需的节点、连线和变量字段。显式用户尺寸使用 `width/height/style`，React Flow 的 `selected/dragging/resizing/measured/dimensions`、运行高亮及 AI 生成瞬态不落库；`data.moduleType` 与导出的节点 `type` 必须遵守 WebRPA 映射。当前 Studio 已知凭据字段（含 `apiKey/azureApiKey/authCode/password/accessToken/appSecret/token/secret/privateKey` 及现存 snake_case 变体）的非空明文拒绝进入文档，错误不得回显值；后续通过 secretRef 或宿主资源解析。未知节点允许保存和再次编辑，但 PM3 运行预检只接受由 `open_page/input_text/click_element/get_element_info` 组成的非空、单入口、无分支单链；所有节点必须恰好遍历一次，执行顺序从连线推导，并在冻结前验证四类节点的必填字段、类型、适用枚举和有限非负 timeout。`get_element_info.attribute` 沿用源执行器语义，接受任意非空属性名；`0` timeout 表示不限制。

## 5. 自动化配置

### 5.1 列表和生命周期

项目自动化目录支持搜索、排序、分页、打开和编辑；活动项目可创建和编辑，归档项目只读。列表每项显示名称、说明、工作流校验状态、输入概况、默认资源和最近修改。更多菜单在 PM3 只提供编辑和打开 Studio。删除及其影响查询按照已冻结公共契约留到 PM8；PM3 不提供无后端守卫的假删除入口。

### 5.2 四个配置页签

1. **基本信息**：名称、说明、关联工作流、打开 Studio。关联建立后 `workflowId` 不通过普通编辑换成另一个工作流；需要显式重建或后续影响流程。
2. **输入与参数**：稳定 `inputId` 的项目数据输入定义，以及稳定 `parameterId`、名称、类型、必填、默认值和说明。PM3 保存输入定义，但只有 `inputPlan.inputs=[]` 可运行。
3. **资源与环境**：Profile、代理覆盖、模型提供方和环境策略。PM3 只实现从 Profile 新建临时环境；固定持久环境和从记录关联环境显示能力未开放。
4. **运行设置**：有限任务数、并发、失败后是否停止创建后续任务、超时和结束时环境处理。PM3 任务数为 1–100，默认 1；并发能力固定为 1 并如实显示。无限运行在 PM4 有必要输入和耗尽语义后开放。

四页签共用一个自动化配置草稿和一次聚合保存。保存前校验全部页签；错误页签显示计数并将焦点移动到首个错误。后台刷新不覆盖脏草稿；CAS 冲突保留输入并显示服务端最新事实。自动化配置保存不会隐式保存 Studio 工作流，Studio 保存也不会改动自动化配置。

### 5.3 校验状态

自动化详情返回独立 validation projection：

- `ready`：工作流可运行、参数完整、资源可解析、PM3 没有项目数据输入；
- `draft`：配置可保存但信息未完整；
- `blocked`：工作流不存在、文档修订不可运行、资源缺失或包含 PM4 输入；
- `unavailable`：核心运行服务没有装配或正在关闭。

资源缺失允许保存草稿，但启动必须返回结构化 blocker。前端不以禁用按钮代替服务端校验。

## 6. 参数型批次与事务

### 6.1 启动请求

`POST /api/v1/projects/{projectId}/automations/{automationId}/batches` 使用 UUID `Idempotency-Key`，请求包含：

```ts
type StartBatch = {
  expectedAutomationRevision: number
  parameters: Record<string, JsonScalar>
  maxTasks?: number
  environmentOverride?: EnvironmentPolicy
}
```

省略 `maxTasks` 使用自动化 `runPolicy.maxTasks`。PM3 要求最终值为 1–100。工作流修订由服务端在启动事务中读取并冻结，不信任页面缓存的 revision。参数根据服务端 parameter schema 严格校验，不把字符串 `"1"` 自动转成数字，不把空字符串当 null。

### 6.2 原子接受

同一短数据库工作单元依次完成：

1. 查询相同幂等键；同请求返回原结果，不同请求返回 `OPERATION_PAYLOAD_MISMATCH`。
2. 校验项目 active、自动化修订、工作流修订和 capability；服务端编译并保存不可变 `PreparedContent`。
3. 冻结自动化、参数、任务数和资源请求，创建 Batch。
4. 为每个任务预分配 `taskId`、`runRequestId` 和 `runId`，保存空数据输入的 `TaskInputSnapshot`。
5. 调用 `CoreRunPort.prepareRun(..., uow)` 创建 queued CoreRun；该调用不提交。
6. 保存 Task 和 startBatch Operation 结果，一次提交。

数据库提交后才派发 Run。事务失败不能留下孤立 Task 或 Run。派发失败必须把 CoreRun 和 Task 收敛为真实失败，保留 Batch 及错误；不能删除已接受事实或自动再执行网页。

PM3 允许一个 Batch 创建多个参数相同但身份独立的 Task；执行容量为 1，协调器按顺序派发。每个 Task 都有独立变量空间、浏览器临时环境和 Run，不继承前一 Task 输出。

### 6.3 聚合状态

Batch 使用 PM0 已冻结状态：`accepted → running ↔ blocked → draining → completed|failed`；停止为 `stopping → stopped`，归属不明为 `reconciling → interrupted`。聚合计数来自 Task 权威投影；只要存在失败、取消或中断，界面必须显示部分结果，不能把 `completed` 翻译成“全部成功”。Batch 终态不会修改任何项目数据业务状态。

## 7. 派发、停止与恢复

- `dispatchRun` 只接受 queued Run 的当前 `statusRevision` 和 `executionGeneration`；派发接受后进入 running。重复派发相同所有权是幂等查询，旧代次被拒绝。
- 普通停止关闭尚未派发的 Task，并要求活动 worker 在当前节点安全点停止；已经提交的节点事实不回滚。
- 强制停止仅在普通停止超过明确时限或浏览器处置失败后开放；它撤销执行代次并强制回收进程和 CloakBrowser，会留下 `cancelled` 或需要核验的 `interrupted`。
- HTTP 202 只表示停止命令被接受。页面通过 Operation 和 CoreRun 查询确认结果。
- 服务启动时，queued Run 可以继续派发；原进程拥有的 running/stopping Run 进入 `reconciling`，核对持久事件、worker 和浏览器事实后收敛。不得自动重新执行最后一个网页动作。
- 应用退出和工作区切换通过 QuiesceGate 检查 queued、running、stopping、reconciling Run。用户必须先停止或明确留在当前工作区，不能只依赖活动 HTTP 数量。

## 8. HTTP、事件与桌面边界

### 8.1 PM3 新增项目接口

| 能力 | 接口 |
|---|---|
| 自动化目录与创建 | `GET/POST /api/v1/projects/{projectId}/automations` |
| 自动化详情与保存 | `GET/PUT /api/v1/projects/{projectId}/automations/{automationId}` |
| 启动校验 | `GET /api/v1/projects/{projectId}/automations/{automationId}/validation` |
| 批次启动与目录 | `POST .../{automationId}/batches`、`GET /api/v1/projects/{projectId}/batches` |
| 批次与任务详情 | `GET .../batches/{batchId}`、`GET .../batches/{batchId}/tasks`、`GET .../tasks/{taskId}` |
| 日志与事件 | `GET .../tasks/{taskId}/events`、`GET .../tasks/{taskId}/artifacts` |
| 停止 | `POST .../batches/{batchId}/stop`、`POST .../batches/{batchId}/force-stop` |

所有父路径重新校验项目归属。真实 handler、DTO、错误和 Operation kind 同包进入 OpenAPI；不先添加未来 PM4–PM8 空接口。

### 8.2 core 接口

Studio 可使用 `/api/v1/workflows` CRUD、校验、Run 查询和事件接口；项目运行不通过 HTTP 调用同一 sidecar，而是调用 application port。外部 Run 启动接口不得允许 renderer 提交任意完整文档覆盖服务端保存内容。

SSE 事件只用于及时刷新。连接后先读取 Run 快照，再从 `latestSequence` 续订；重复序号丢弃，发现缺口时暂停应用后续事件并用分页 GET 补读。终态和日志均来自持久仓储。

### 8.3 Studio 窗口

扩展现有 `AutomationStudioBridge`：

```ts
type OpenStudioRequest = {
  workflowId: string
  projectContext?: {
    projectId: string
    automationId: string
    managementRevision: number
  }
}
```

主进程只允许打开已存在且属于当前工作区的工作流。Studio 显示返回项目入口，但编辑和保存仍走 WorkflowDocument 服务。打开 Studio 不启动 Run，关闭 Studio 不停止后台 Run。

## 9. 页面与视觉基准

保持当前应用顶部导航、项目页头和六个项目页签。原型中的左侧应用导航只替换为顶部导航，其余内容结构、信息层级、操作位置和状态应保持一致。统一使用已经接入的细网格表格、小圆角、暖灰背景和黏土棕强调色。

现有最新原型的直接对应关系：

- 自动化目录和状态：`latest/02-automation/001–003`、`006–011`；删除确认与冲突画板 `004–005` 留给 PM8；
- 运行批次、任务、详情、日志、输入输出、错误证据和停止：`latest/03-runs/001–017` 中适用于 PM3 的画板；
- `018–021` 人工处理状态属于 PM5，本阶段不做假入口；
- 项目页头、加载、错误及能力状态继续复用当前 R1–R3 页面模式。

当前 gallery 没有完整的“四页签自动化详情”和“参数启动弹窗”画板。实现这两个页面前先补一组基于既定设计系统的高保真 B0 图稿，并单独确认；这不是重新设计已有目录和运行记录页面。

关键交互：

- 目录搜索输入后按 Enter 或点击搜索才请求；排序、页码和滚动按工作区与项目恢复。
- 配置四页签共用草稿；关闭、顶部导航、项目页签、前进后退和 Studio 打开均进入统一未保存保护。
- 启动按钮打开参数与资源确认弹窗；保存配置不等于启动。
- 运行列表刷新失败保留旧内容；停止中、结果不明和部分失败使用持久状态区，不用短 Toast 代替。
- 日志使用细网格或紧凑虚拟列表，长文本内部滚动；200% 缩放不撑宽窗口。

## 10. 错误处理

沿用 PM0 `ErrorEnvelope` 和当前项目错误适配。至少区分：

- 422：参数/配置/工作流不可运行；
- 409：自动化或工作流修订冲突、幂等载荷冲突、Run 状态冲突；
- 423：项目 closing、运行容量或资源占用；
- 410：执行代次撤销；
- 429：运行容量耗尽并带可选重试时间；
- 503：核心、CloakBrowser、内核、代理或存储不可用；
- 504：操作结果尚不能确认，返回可查询的 `operationId`。

未知结果先查询原 Operation、Batch、Task 和 CoreRun，不换 key 盲重发。日志、路径、错误响应和 artifact 元数据不得暴露 License、代理凭据、Cookie、本地绝对路径或堆栈。

## 11. 测试与验收

### 11.1 自动测试

- 工作流：CRUD CAS、同内容保存、服务端编译、非法节点、参数引用和 prepared content 不可变。
- CoreRun：queued 原子创建、派发、事件序号、终态不可逆、停止、旧代次拒绝、进程重启收敛。
- 自动化：项目归属、一个工作流一个绑定、四页签聚合保存、草稿可保存但启动受阻、归档只读。
- 批次：同键重发、异载荷冲突、事务回滚无孤立对象、响应丢失找回、多 Task 串行、派发失败保留事实。
- 前端：目录全部状态、四页签脏草稿、校验定位、参数类型、迟到响应隔离、运行日志补读和停止确认。
- 迁移：空库和现有 `0009`/PM2 数据库升级；浏览器、代理、模型、项目和数据表事实不变。

### 11.2 真实端到端

在隔离工作区使用真实 Electron、FastAPI、SQLite、已安装 CloakBrowser 内核和本地 fixture 页面执行：

1. 从项目创建自动化并创建/关联工作流。
2. 在 Studio 保存“打开本地页面 → 输入参数 → 点击 → 读取结果”。
3. 回项目启动一次，核对页面提交计数、参数、Task、Run、节点日志及输出。
4. 双击启动和模拟响应丢失，确认只有一个 Batch 和对应数量的 Run。
5. 启动长等待，执行普通停止和强制停止，确认之后不再发生网页动作。
6. 运行中重启 sidecar 和应用，确认不会重跑网页，已提交事实可找回并收敛到明确状态。
7. 在两个工作区分别创建同名自动化，确认配置、运行、事件和草稿不串。

### 11.3 视觉与可访问性

按原型画板逐页保存正常、空、加载、失败、冲突、运行中、停止中和结果不明截图。记录 viewport、缩放、DPR、字体和构建提交；每个适用画面单独达到既有 85 分门槛并满足顶部导航、主标题、操作位置和信息层级强制项。

键盘验收覆盖 Tab、Shift+Tab、Enter、Space、Escape、焦点恢复和对话框默认焦点。检查 100%/200% 缩放、长名称、长日志、嵌套 Select/Popover、滚动和下拉展开宽度。Windows 和未实际运行的架构如实标记未执行。

## 12. 实施切片与退出门槛

1. **PM3.0 核心恢复**：恢复并适配文档、prepared content、Run、事件、worker 和 CloakBrowser；真实最小流程通过。
2. **PM3.1 自动化管理**：补详情/启动 B0 图稿，交付自动化目录、四页签、校验和 Studio 关联。
3. **PM3.2 参数批次**：交付原子 Batch/Task/CoreRun、参数启动和串行调度。
4. **PM3.3 运行与恢复**：交付运行页面、日志、artifact、停止、强停、断线和重启收敛。
5. **PM3.4 总体验收**：执行全量工程检查、真实 E2E、截图对照、独立审查和手动测试文档。

每个切片必须完成实现、定向测试、规格审查、工程审查和独立提交后才进入下一切片。PM3.4 完成前 `automations/runs` 不对正式项目标记 available。PM3 完成后停在验收点，不自动进入 PM4。

## 13. 明确取舍

- PM3 运行并发固定为 1，先与归档核心能力和单 CloakBrowser 生命周期一致；配置模型保留并发字段，未来扩容不改变 Automation 身份。
- 多次参数任务按独立 Task 串行执行，不共享变量和临时浏览器环境。
- 项目数据输入可以配置、不能在 PM3 运行；不以空数组替换用户已保存输入。
- 旧运行代码作为复用来源，当前契约、项目事务和安全边界优先。
- 原型导航适配仅替换全局侧栏为顶部导航，不重排原型主体内容。

## 14. 自审结论

- 未发现待定标记、未完成条目、空接口或占位页面要求。
- Studio/core 与项目所有权分开，且原子接受没有 HTTP 自调用或双重提交。
- PM3 范围覆盖参数型真实执行，同时明确排除 PM4–PM8 能力。
- 自动化详情和参数弹窗缺少原型的事实已显式处理，不把不存在的画板写成已批准。
- 迁移的实际文件名和 down revision 留给实施计划在开工时依据 Alembic head 精确确定，业务依赖顺序已经固定。
