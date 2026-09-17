# 项目管理共享领域与执行契约

- 日期：2026-09-13。
- 状态：confirmed design target（实施契约冻结；不表示现有代码已经实现或验收通过）。
- 权威来源：`docs/project-management/design/data-and-state-rules.md`、`data-flow-and-contracts.md`、`execution-and-environment.md`，以及完整设计确认 `906deda`。
- 范围：PM0-A 的共享对象、版本、状态、事务和 XE-C01–XE-C18 契约卡。具体 HTTP 路由、错误 envelope 映射及生成 DTO 由 `api-contracts.md` 负责。

## 1. 边界与共同语言

项目管理协调 Studio/core、项目数据、环境和 runtime；它不实现第二个执行器。`workflowId` 始终引用核心 `WorkflowDocument.document.id`（UUID），项目侧只保存引用、管理配置和固定的执行证据，不复制画布 IR。独立 Studio 继续能运行通用网页、变量、结果与日志能力；只有声明需要项目数据、项目环境或项目人工协调的文档在缺 capability 时不可运行。

传输字段使用 camelCase，错误复用现有统一 envelope；本文件定义其中稳定的领域 code，不另造第二种错误响应。所有命令带稳定操作身份；相同身份和相同规范请求返回原结果，相同身份和不同请求返回 `operation_payload_mismatch`。响应丢失后查询原身份，不生成新命令。

禁止项：消费类型、本批已消费/去重集合、任务终态隐式改变业务状态、变量或输出自动写回项目表、项目服务经 HTTP 自调用 core、`prepareRun` 自行提交、以日志/SSE/前端状态代替权威持久状态。查询记录不会取得写权；查询所得记录若要写，必须非阻塞取得动态 lease，再执行 CAS。

## 2. 共享对象与引用

下表是领域对象；可空字段均明确写出，不允许以未定义的空对象占位。时间为带时区 UTC instant。`projectId/tableId/fieldId/datasetGeneration/record UUID/environmentId` 等持久身份在传输层均编码为规范 UUID 字符串；业务整数身份以规范字符串传输，来源数值的安全精度仍须校验。

| 类型 | 必需字段 | 语义与不变量 |
|---|---|---|
| `Project` | `projectId`, `name`, `lifecycleState`, `managementRevision`, `createdAt`, `updatedAt` | `lifecycleState` 为 `active/closing/archived/deleting/deleted`；closing 关闭新工作但允许持既有身份的受控收尾。 |
| `Automation` | `automationId`, `projectId`, `workflowId`, `name`, `managementRevision`, `inputPlan`, `parameterSchema`, `environmentPolicy`, `capabilityRequirements`, `runPolicy` | `workflowId` 指向核心文档 UUID；这里只固定项目绑定和运行政策，不复制工作流内容。启动时再解析确定内容。 |
| `FieldRef` | `projectId`, `tableId`, `datasetGeneration`, `fieldId` | 字段改名不改引用；换数据身份代次后旧引用明确失效，不按名称或列号猜迁移。 |
| `DateScalar` | `kind:date`, `precision:date|datetime`, `value:string`, `offset:string|null` | date 的规范传输封装，不是允许业务字段存任意对象。纯日期value为YYYY-MM-DD；日期时间value保留来源的本地日期时间及小数精度，不强加offset，offset单独表示已知偏移；无时区来源offset=null，不补Z或按电脑时区转换。JSON请求须校验precision/value/offset一致。 |
| `FrozenFieldMapping` | `fieldId`, `sourceKey`, `sourceName`, `sourceType`, `inputFieldId`, `inputFieldAlias` | 在领取事务冻结实际字段ID、字面键、当时显示名/类型与工作流输入字段映射；重命名、删列、换代次后历史展示不查询当前字段来猜。业务字段仍仅四类标量，日期保留精度/时区语义。 |
| `RecordKey` | `type: text\|integer\|uuid`, `value: string` | `text` 原样保留前导零；`integer` 使用无小数、无指数、无多余前导零的规范十进制字符串，且来源值必须已在来源系统可靠整数范围及传输安全范围内得到验证；超限要求来源改为 text，禁止把已经舍入的数再转成字符串。`uuid` 是系统身份的规范 UUID 字符串。`text:"1"` 与 `integer:"1"` 不同；禁止 float、bool、日期、公式和行号作为业务身份。 |
| `RecordRef` | `projectId`, `tableId`, `datasetGeneration`, `recordKey` | 四部分共同构成记录身份；服务端逐项校验归属和代次。 |
| `RecordSnapshot` | `recordRef`, `recordSlots: {slotId,target:RecordRef|null}[]`, `fields: {fieldId, value}[]`, `statusId|null`, `currentEnvironmentId|null`, `contentRevision`, `statusRevision`, `linkRevision`, `sourceSummary`, `capturedAt` | `fieldId` 是规范 UUID 字符串，`value` 是 `ScalarValue`。这是完整只读事实；`ScalarValue` 为 string/number/boolean/DateScalar/null，即四类业务标量或空；日期时间属于 date 来源精度，不新增业务字段类型；数组中缺少某 fieldId 与该 fieldId 的 value 为 null 不等价。 |
| `InputSnapshot` | `recordRef`, `recordSlots: {slotId,target:RecordRef|null}[]`, `fields: {fieldId, value}[]`, `fieldMappings: FrozenFieldMapping[]`, `statusId|null`, `currentEnvironmentId|null`, `contentRevision`, `statusRevision`, `linkRevision`, `sourceSummary`, `capturedAt` | 只表示本次 Task 领取时取得的完整记录证据；字段项形状和标量规则同 `RecordSnapshot`。不得复用旧 Task 的快照或以当前记录覆写。 |
| `TaskInputSnapshot` | `inputSnapshotId`, `taskId`, `batchId`, `parameters`, `inputs: {inputId, inputAlias, value: InputSnapshot|null, unavailableReason: null|no_match|busy}[]`, `capturedAt` | 一经提交不可变；`inputId` 是自动化输入的稳定 UUID。已选输入的 `value` 非 null 且 `unavailableReason=null`；可选输入没有匹配时整个 `value=null, unavailableReason=no_match`，只有暂时占用候选时为 `value=null, unavailableReason=busy`。配置/读取错误不得编码成 null。相同记录的输入别名各留领取时证据，但 lease 按物理身份合并。 |
| `Batch` | `batchId`, `projectId`, `automationId`, `startOperationId`, `status`, `statusRevision`, `frozenRequest`, `counts`, `createdAt` | 管领取门闩、总量和聚合；不保存批内消费集合。终态 `completed/stopped/failed/interrupted` 不可逆。 |
| `Task` | `taskId`, `batchId`, `runRequestId`, `runId`, `inputSnapshotId`, `status`, `statusRevision`, `createdAt` | 项目侧投影 CoreRun 权威状态；不得独立判成功。原输入、当前记录、节点变量和输出彼此分离。 |
| `CoreRun` | `runId`, `runRequestId`, `preparedContentId`, `status`, `statusRevision`, `executionGeneration`, `capabilityBindings`, `resourceRequest`, `startedAt|null`, `finishedAt|null` | core 唯一拥有执行状态和终态；相同 `runRequestId` 唯一对应同一 Run。 |
| `Operation<T>` | `operationId`, `kind`, `requestDigest`, `status`, `statusRevision`, `result:T|null`, `error:null|DomainError`, `createdAt`, `updatedAt` | 状态 `accepted/running/succeeded/failed/reconciling`；特定操作可扩展可查询阶段，但同身份结果不可重写。 |
| `EnvironmentRef` | `projectId`, `environmentId`, `contentGeneration`, `metadataRevision` | `environmentId` 是稳定来源身份；`contentGeneration` 是 JSON 安全整数且 `>=1`，在同一 environmentId 内随已发布可恢复内容单调递增；名称/备注只推进独立 `metadataRevision`。运行工作副本另有 `instanceId` 和使用代次。 |
| `LeaseRef` | `leaseId`, `leaseKey`, `taskId`, `leaseGeneration`, `state` | `leaseKey` 按真实物理身份合并；`state` 为 `held/revoked/reconciling/released`。撤权后旧 generation 不能写。 |
| `CapabilityBinding` | `capability`, `provider`, `scope`, `bindingRevision` | 仅注入文档声明所需能力；项目数据节点调用端口，不 import Manager/仓储。 |
| `DomainError` | `code`, `message`, `details`, `retryable` | `details` 只能含可行动的稳定引用、当前/预期版本、阻断者或缺项，不含秘密。 |

## 3. 修订与代次

| 名称 | 所属事实 | 何时推进 | 不能代替 |
|---|---|---|---|
| `managementRevision` | Project/Automation 管理配置 | 对应管理配置条件写成功 | 记录、表、Run 或环境版本 |
| `contentRevision` | 一条记录的业务字段 | 字段值实际改变 | `statusRevision`、`linkRevision` |
| `statusRevision` | 一条记录当前业务状态 | 设置或清空状态实际提交 | Task/CoreRun 状态版本 |
| `linkRevision` | 一条记录的关系槽和 `currentEnvironmentId` | 关联实际改变；已是同一环境的幂等确认不推进 | 内容、状态版本 |
| `tableRevision` | 表配置、字段与状态目录 | 表结构/目录条件写成功 | 单记录修订 |
| `datasetGeneration` | 一张表的数据身份空间（UUID） | Excel 全量导入、真实换源或身份策略改变 | Sheets `bindingEpoch`、任意修订 |
| `contentGeneration` | 环境已发布持久内容（同 environmentId 单调的安全整数，首代 `1`） | 保存候选完整且当前指针 CAS 提交 | 环境 `metadataRevision`、实例使用代次 |
| `executionGeneration` | Run 的有效 Worker/派发权 | 首次派发或撤权后的新协调代次 | attempt、事件 sequence |
| `leaseGeneration` | 某 lease 的当前写权 | 发放/撤销合法写代次 | 记录 CAS 修订 |

跨领域显式命令可以在一个短事务检查并推进多个相关修订；没有变化就不凭空递增。`TaskInputSnapshot` 永远保留领取时版本；Task 内后续写通过该 Task 的“最新已确认版本游标”继续 CAS，但不改原始快照。

## 4. XE-C01–XE-C18 契约卡

每张卡都明确调用/提供、输入输出、操作身份、前提、错误、事务和恢复查询。`not_found`、`project_scope_mismatch`、`revision_conflict`、`operation_payload_mismatch` 为通用错误，下文只补该卡特有错误。

### XE-C01 · 工作流保存、读取与校验

- **调用方 → 提供方**：Studio/项目自动化编辑器 → Studio/core 文档服务。
- **输入 / 输出**：`getWorkflow(workflowId)`；`saveWorkflow(workflowId, expectedRevision, document, saveOperationId)`；`validateWorkflow(workflowId, revision, declaredInputs, availableCapabilities)`。返回当前文档及 revision、条件保存结果、结构化 validation issues、输入/输出契约和能力需求。
- **操作身份 / 前提**：写用 `saveOperationId`；读/校验不用操作身份。文档 ID 为核心 UUID；保存须匹配编辑 revision，项目管理草稿不能覆盖核心文档。
- **错误 / 事务边界**：`workflow_revision_conflict`, `workflow_invalid`, `capability_missing`。一次文档保存是 core 自己的短事务；项目关联不与文档内容强绑成长事务。
- **查询与恢复**：响应未知按 `saveOperationId` 查询或读取当前 revision；不另建文档、不按项目侧缓存覆盖。

### XE-C02 · 准备不可变执行内容

- **调用方 → 提供方**：项目运行协调或独立 Studio → Studio/core 内容准备服务。
- **输入 / 输出**：`prepareContent(workflowId, workflowRevision, entrypoint, dependencyRefs, availableCapabilities, prepareOperationId)`；返回 `preparedContentId`、内容摘要、固定根/子流程与资产 revision、入口、所需能力。
- **操作身份 / 前提**：`prepareOperationId` 幂等；文档及全部依赖可解析，能力满足。准备后编辑不改变该内容。
- **错误 / 事务边界**：`workflow_dependency_missing`, `workflow_dependency_cycle`, `capability_missing`, `workflow_not_runnable`。core 在自身短事务发布确定内容；不创建 Batch/Task/Run。
- **查询与恢复**：按操作身份或 `preparedContentId` 查询；未知时不重新解析成可能不同的内容。

### PM3 参数批次实施限定（2026-09-15，confirmed）

来源：已批准 PM3 规格与 Task 11 实现。本段限定 PM3 的参数型消费者；后续多表领取仍遵循 C04，不削减数据保护。

- 参数请求按稳定 `parameterId` 索引；冻结的自动化 schema 保存名称、类型、默认值，任务不随重命名改变。每个 Task 独立保存参数和 `inputs=[]`。
- 有界参数批次在**一次调用者 Session 的短事务**发布 PreparedContent、Batch、全部 Task、TaskInputSnapshot、queued CoreRun 和启动 Operation。C02 的既有独立调用仍自有事务；新增调用者 UoW 路径不自提交。同服务不绕 HTTP 拼事务。
- 启动 Operation `succeeded` 表示批次创建命令已提交；初始 Batch 为 `accepted`，Task 为 `queued`，不表示工作流执行成功。提交后才派发。
- 内部 Batch 保存 `frozenRequest/counts`；HTTP `managementRevision` 是启动时冻结的 Automation 修订投影，`statusRevision` 是批次自身状态修订。内容里另存 workflowRevision，不混为一个版本。查询的 Task 状态与终态时间来自唯一 CoreRun。
- 原键恢复返回原始接受快照；实时进度走 Batch/Task 查询。最终物理 COMMIT 失败时失效连接，防止未提交事务回池污染查询；若实际已提交而确认丢失，则原键仍可找回事实。

### XE-C03 · startBatch / queryStart

- **调用方 → 提供方**：项目 UI/调度入口 → 项目运行协调。
- **输入 / 输出**：`StartBatchRequest(projectId, automationId, expectedManagementRevision, parameterOverrides, runLimit, failurePolicy, startOperationId)`；返回同一 `batchId`、固定请求、预检问题和 Batch snapshot。
- **操作身份 / 前提**：`startOperationId`；项目 active，自动化 revision 匹配，输入/环境/能力预检通过，零必要输入时数量必须有限。
- **错误 / 事务边界**：`project_not_active`, `automation_revision_conflict`, `start_validation_failed`, `unbounded_without_required_input`。短事务仅接受 Batch 与冻结请求；校验失败可记录可查询拒绝结果，但不得创建 Task。
- **查询与恢复**：`queryStart(startOperationId)` 返回拒绝或原 Batch；启动响应丢失不创建第二身份。

### XE-C04 · prepareInputGroup / commitInputGroup

- **调用方 → 提供方**：项目运行协调 → 项目数据、环境预约和 core 事务参与端口。
- **输入 / 输出**：准备输入为 `batchId`、固定 input plan、剩余额度、候选游标与 `prepareOperationId`，返回候选 `RecordSnapshot[]`、物理 `leaseKey[]`、预期修订和环境预约需求；提交输入另含预分配 `taskId/runRequestId`、确定内容和资源/capability 绑定，返回 `Task`、不可变 `TaskInputSnapshot`、leases、环境预约及 queued `CoreRun`。
- **操作身份 / 前提**：准备和提交身份稳定；提交重新检查 Batch 领取门闩、额度、项目 active、条件、RecordRef/三修订、datasetGeneration、lease 和环境预约。
- **错误 / 事务边界**：`input_group_unavailable`, `input_ambiguous`, `dataset_generation_stale`, `lease_busy`, `environment_busy`, `batch_closed`。准备在事务外且无长期占用；**Task＋原始输入＋全部 leases＋环境预约＋queued CoreRun 在同一短 UoW 原子提交**。`prepareRun` 只登记 core 聚合，不自提交；不得 HTTP 自调用。网络、复制和浏览器启动在提交后。
- **查询与恢复**：未提交则五类事实全不存在；已提交按 `taskId/runRequestId` 查同一组。没有批内消费集合，释放后是否再领只看当前条件和占用。

### XE-C05 · prepareRun / dispatchRun / queryRun

- **调用方 → 提供方**：项目协调或独立 Studio → core；runtime dispatcher → core。
- **输入 / 输出**：`prepareRun(runRequestId, preparedContentId, parameters, inputSnapshotRef|null, resourceRequest, capabilityBindings, uow)` 返回 queued `CoreRun`（包含 runId）；`dispatchRun(runId, expectedStatusRevision, executionGeneration)` 返回接受的派发；`queryRun(runId|runRequestId)` 返回权威 CoreRun。
- **操作身份 / 前提**：`runRequestId` 全局稳定；dispatch 携有效 `executionGeneration`，并在创建资源/首节点前复验未停止、未撤权。
- **错误 / 事务边界**：`run_request_conflict`, `run_not_dispatchable`, `execution_generation_revoked`, `prepared_content_missing`。prepareRun 参加调用方 UoW 且禁止自提交；dispatch 是提交后的短状态事务，实际执行在事务外。
- **查询与恢复**：相同 runRequestId 唯一映射 runId。queued 可直接查询；服务重启不得把已派发且结果不明的旧 Task 重新派发。

### XE-C06 · cancelRun / forceStop / queryOperation

- **调用方 → 提供方**：项目 Batch 扇出协调或独立 Studio → core/runtime。
- **输入 / 输出**：`cancelRun(runId, expectedStatusRevision, reason, cancelOperationId)`；`forceStop(runId, expectedStatusRevision, reason, stopOperationId)`；返回 Operation 接受事实、当前 Run 和待核验资源，最终给出 cancelled/interrupted 或既有终态。
- **操作身份 / 前提**：每条 Run 命令独立稳定身份；Batch 停止先关领取，再逐 Run 发命令。终态命令只返回当前事实。
- **错误 / 事务边界**：`run_terminal`, `stop_already_superseded`, `resource_ownership_unknown`。接受命令的短事务不等于进程已停；撤权、终止和核验分阶段提交，网站副作用不回滚。
- **查询与恢复**：`queryOperation(operationId)` 直到结果确定；未知归属保持 reconciling/隔离和占用，不以按钮返回成功释放资源。

### XE-C07 · RunSnapshot / RunEvents / artifacts

- **调用方 → 提供方**：Manager/Studio 页面及项目投影器 → core 查询与事件服务。
- **输入 / 输出**：`getRunSnapshot(runId)`；`listRunEvents(runId, afterSequence, limit)`；`getArtifact(runId, artifactId)`。事件含 `runId, sequence, eventId, executionGeneration, nodeVisitId, attempt, committedAt`；snapshot 含其权威 `lastSequence`、状态和资源摘要；节点尝试/输出仅提供最多50项的预览及总数/续读标记，不返回完整无限历史。`listRunAttempts(runId, page, pageSize)` 与分页输出/日志查询按稳定身份排序续读，每页最多200项。
- **操作身份 / 前提**：只读；artifact 必须属于 Run 且经授权。sequence 是单 Run 持久递增序号。
- **错误 / 事务边界**：`event_cursor_invalid`, `artifact_unavailable`。事件和对应状态在 core 边界持久化后才发布；SSE 只是通知。
- **查询与恢复**：客户端持久保留自己的 `lastSeenSequence`；断线先用该游标调用 `listRunEvents(afterSequence=lastSeenSequence)` 补齐历史，再用 snapshot 核对权威状态和服务端 `lastSequence`。首次订阅没有游标时才以约定起点读取。不得先跳到新 snapshot 的 `lastSequence` 而漏掉断线期间日志；按 eventId/sequence 去重。乱序、重复、撤权 Worker 或终态后迟到事件不得改终态。

### XE-C08 · readProjectRecord / queryProjectRecords

- **调用方 → 提供方**：core 内已注入项目数据 capability → 项目数据服务。
- **输入 / 输出**：按允许的具名输入读取 `RecordRef`，或按已声明同项目 `tableId`、过滤器、稳定排序和分页查询；携 `readPurpose`。返回完整 `RecordSnapshot`、来源摘要和下一页游标。
- **操作身份 / 前提**：只读无 operation/lease；capability scope 必须允许该项目、表、字段与读取目的。
- **错误 / 事务边界**：`capability_scope_denied`, `record_identity_stale`, `query_invalid`。单次一致读取；不跨项目任意读取。
- **查询与恢复**：调用结果本身就是当次快照；重复读可观察新事实。**读取不授予写权，也不加入 End 默认目标。**

### XE-C09 · 项目表、字段、记录和状态操作

- **调用方 → 提供方**：项目 UI 或 core 项目数据 capability → 项目数据服务。
- **输入 / 输出**：显式 CRUD 动作，以及 `writeRecordFields(recordRef, changes, expectedContentRevision, leaseRef, writeOperationId)`、`setRecordStatus(recordRef, statusId|null, expectedStatusRevision, expectedContentRevisionWhenDerived, allowedFrom, leaseRef, writeOperationId)`。结构动作携 `expectedTableRevision/datasetGeneration` 和 impact confirmation。返回稳定引用、新修订、事件、同步意图及本 Task 可继续使用的写权/最新游标。
- **操作身份 / 前提**：每个逻辑写有稳定 ID。初始输入使用有效 Task lease；查询结果写入前执行非阻塞动态 lease 检查并 CAS。动态 lease 与初始 lease 一并收尾。人工普通字段编辑在身份可靠、来源归属明确并匹配 expectedContentRevision 时允许，即使活动 Task 已固定旧输入；人工状态或关联写仍受活动 lease/占用阻挡，不能绕过 Task 的业务结论与 End 关联。
- **错误 / 事务边界**：`lease_busy`, `lease_revoked`, `record_revision_conflict`, `table_revision_conflict`, `impact_changed`, `field_reference_in_use`, `status_reference_in_use`。对于此前未持有的查询结果，动态 lease 的原子取得、全部预期修订 CAS、实际写、变化事件、幂等结果与同步意图必须在**同一个短事务**；任一步失败则全组不写且不留下新 lease。已有 lease 的一次本地写同样把写、修订、事件、幂等结果与同步意图原子提交；外部推送不在事务内。字段/状态/内容各自只推进实际修改版本。
- **查询与恢复**：按 writeOperationId 返回原结果；新增响应丢失不得新增第二行。失败不自动升级版本重试；Task 失败不回滚已提交节点写，也不自动改状态或写回结果。

### XE-C10 · bindRecordEnvironment（End 内部）

- **调用方 → 提供方**：C18 End 协调/明确管理命令 → 项目数据服务，并向环境服务校验存在性。
- **输入 / 输出**：`BindEnvironmentRequest(bindOperationId, projectId, environmentRef, targets:{recordRef,expectedLinkRevision,replaceAllowed,leaseRef}[])`；返回全部 target 的当前/新 linkRevision 和事件。
- **操作身份 / 前提**：目标去重且同项目；环境已发布；每条记录存在并有有效写权。空引用或同环境可确认；替换不同环境必须逐项授权。
- **错误 / 事务边界**：`environment_scope_mismatch`, `association_target_missing`, `association_replace_forbidden`, `link_revision_conflict`, `lease_revoked`。全组在一个短本地事务全成或全冲突；只改关联，不改字段/状态/原输入证据。
- **查询与恢复**：按 bindOperationId 查询；End 同身份续做未完成阶段。这是 End 内部能力，不增加用户必须配置的 Bind 节点。

### XE-C11 · resolveEnvironment / reserveEnvironment / openInstance

- **调用方 → 提供方**：项目协调或 core → 环境服务/runtime。
- **输入 / 输出**：解析输入含来源策略、显式输入关联、固定资源引用；返回唯一 `EnvironmentRef|null`、身份包、内核/代理策略摘要。预约含 owner Run/维护身份与 operationId，返回 reservation；打开含 reservation、使用代次，返回 `instanceId` 和受控句柄。
- **操作身份 / 前提**：来源策略只能产生一个明确结果；持久身份独占。恢复固定 environmentId/contentGeneration/身份包/兼容内核，代理仅按已确认覆盖链解析。
- **错误 / 事务边界**：`environment_not_found`, `environment_busy`, `environment_unavailable`, `environment_incompatible`, `environment_source_ambiguous` 必须区分。预约在 C04 短事务；文件复制、进程启动在提交后，不持数据库事务。
- **查询与恢复**：按 reservation/instanceId 查询。暂占是 blocked，不是假数据耗尽；启动失败形成真实 failed Task。归属不明不得另开同身份实例。

### XE-C12 · checkpoint / validateResume / resumeRun

- **调用方 → 提供方**：core 执行器建立 checkpoint；人工页面经项目协调 → core。
- **输入 / 输出**：checkpoint 固定 `runId, checkpointRevision, nodeVisitId, allowedTargets, contextSummary, expiresAt`；校验输入目标节点和人工输入，返回可继续位置或缺项；resume 含 `resumeOperationId, expectedCheckpointRevision, targetNodeId, validatedManualInput`，返回同 Run 的 `resume_queued/running`。
- **操作身份 / 前提**：resumeOperationId 幂等；现场仍属同 Run，检查点、期限、停止/撤权均有效，目标所需变量/子流程栈存在。
- **错误 / 事务边界**：`checkpoint_stale`, `resume_prerequisite_missing`, `manual_expired`, `run_stopping`, `instance_lost`。接受 resume 与人工项转换短事务 CAS；等待执行额度不占长事务。
- **查询与恢复**：查同 Run/checkpoint/operation。continue 的接受 CAS 只建立 `resume_requested`；在真正开始恢复前 TTL、现场丢失或停止仍可撤销它，真正开始恢复与这些终结事件只有一个 CAS 胜者。不得创建新 Run 或重做初始化。

### XE-C13 · finishManual / expireManual

- **调用方 → 提供方**：人工页面或 TTL 项目协调 → core；选择保存并结束时转 C18。
- **输入 / 输出**：`manualItemId, runId, expectedCheckpointRevision, disposition:succeeded|failed|expired|lost, reason, manualOperationId`，可携固定 End 保留选项；返回人工项和 CoreRun 权威状态。
- **操作身份 / 前提**：同一 `waiting`，或恢复请求已接受但尚未真正开始的 `resume_requested` 人工项；调用者有权限。接受 continue 只进入排队且期限继续有效；只有恢复真正开始的 CAS 已胜出后，旧 TTL/现场丢失才不能再终结该等待项。stop 仍可按停止契约竞争。
- **错误 / 事务边界**：`manual_transition_lost`, `checkpoint_stale`, `manual_already_resolved`。人工项与 core 状态在短事务 CAS；业务记录状态不变。
- **查询与恢复**：按 manualOperationId 或 runId 查询。`resume_requested` 期间 TTL/现场丢失可撤销尚未开始的恢复并使 Run 失败；若 resume 真正开始先胜出，则人工项 resolved、期限停止计时，旧 expire/lost 返回当前事实。保存并结束先进入 finishing 并复用 C18，保存/关联未完整前不能成功。

### XE-C14 · saveEnvironment / querySave / discardCandidate

- **调用方 → 提供方**：C18 End、维护窗口或保留副本处理 → 环境服务。
- **输入 / 输出**：`SaveRequest(saveOperationId, projectId, instanceId, mode:update|save_as, targetEnvironmentId|null, expectedContentGeneration|null, instanceUseGeneration, metadataForNew|null, endOperationId|null)`；返回阶段、已提交 `EnvironmentRef|null`、候选身份和可行动结果。放弃请求带 `discardOperationId/candidateId`。
- **操作身份 / 前提**：实例归属明确且已静止，使用代次有效；update 的来源当前代次匹配，save_as 不靠名称识别身份。
- **错误 / 事务边界**：`instance_not_quiescent`, `save_generation_conflict`, `candidate_incomplete`, `storage_failed`, `instance_ownership_unknown`。关闭/候选文件准备在事务外；候选完整后短事务 CAS 发布当前指针；旧文件清理独立记账。
- **查询与恢复**：`querySave(saveOperationId)` 区分接受、候选、已提交和清理。提交响应丢失先查询；冲突保留 `retained_unsaved`，可另存或明确放弃，不默认改预期重写。

### XE-C15 · maintenance / environment CRUD / impact

- **调用方 → 提供方**：环境管理 UI → 环境服务/runtime。
- **输入 / 输出**：环境元数据 CRUD 带 expectedMetadataRevision；`openMaintenance(maintenanceOperationId, environmentRef)`；删除/改绑前 `queryEnvironmentImpact(environmentId)` 返回自动化引用、记录关联、活动使用、维护、待决保存与未知清理。
- **操作身份 / 前提**：项目 active（专门生命周期收尾除外）；维护先取得稳定环境独占并创建副本；预览只读不占用。删除需影响已明确处理且无活动/未知依赖。
- **错误 / 事务边界**：`environment_busy`, `environment_metadata_conflict`, `environment_referenced`, `environment_delete_blocked`。元数据/删除状态各为短事务；浏览器、文件操作在事务外且以 Operation 记账。
- **查询与恢复**：按 maintenance/delete operation 查询。意外退出不自动发布；关闭副本可进入待处理保存。清理失败保持可见操作，不虚报删除完成。

### XE-C16 · reconcileRun / reconcileInstance / releaseInputGroup

- **调用方 → 提供方**：启动恢复、失联/强停协调器 → core、runtime、数据和环境服务。
- **输入 / 输出**：携原 `runId, instanceId, leaseRefs, reservationId, executionGeneration` 及进程/目录/提交核验证据和 `reconcileOperationId`；返回每项 `confirmed_stopped|isolated|committed|unknown`、Run 结论与可释放项。release 只接收已证明安全的 lease/预约。
- **操作身份 / 前提**：先撤销旧执行/lease generation；证据必须来自权威持久提交或可验证 runtime 归属，不能信迟到 Worker 自述。
- **错误 / 事务边界**：`ownership_unknown`, `termination_unconfirmed`, `commit_fact_unknown`, `release_not_safe`。撤权短事务，外部核验在事务外，确定结果再短事务终结和释放；不跨外部动作持锁。
- **查询与恢复**：同 reconcileOperationId 可继续。未知时保留隔离和占用；确认旧执行终止后才释放。恢复不得重做网页动作，queued 已派发未知也不得重派。

### XE-C17 · projectClosing / workspaceQuiesce

- **调用方 → 提供方**：项目归档/删除与现有设置工作区切换 → 项目生命周期协调和 QuiesceGate。
- **输入 / 输出**：`beginClosing(scope, reason, closingOperationId)`，返回门闩、活动 Run/维护/保存/同步/清理 blocker 与子操作；`queryClosing` 返回实时账本；完成后返回 archived/deleted 或工作区可切换事实。
- **操作身份 / 前提**：scope 精确；closing 后拒绝新 Batch、领取、维护和无关编辑，允许原身份取消、保存、数据结算、同步核验与清理。
- **错误 / 事务边界**：`closing_blocked`, `sync_outcome_unknown`, `save_pending`, `runtime_ownership_unknown`, `delete_impact_unresolved`。建立门闩是短事务；收尾分操作执行；所有 blocker 清零后再短事务提交生命周期结果。
- **查询与恢复**：按 closingOperationId 恢复账本。重启不自动继续旧批次、不发送未发送同步队列；未知外部结果先核验。工作区切换失败保持当前工作区。

### XE-C18 · finalizeEnd / queryEnd / repairEndAssociation

- **调用方 → 提供方**：core 到达 End/人工保存并结束 → 项目 End 协调；协调调用 C14、C10 并把完整结果回 core。
- **输入 / 输出**：`FinalizeEndRequest(endOperationId, runId, nodeVisitId, accessGeneration, retainEnvironment, intendedBusinessResult, saveTarget, expectedSourceGeneration, deduplicatedTargets:{recordRef,expectedLinkRevision,replaceAllowed,leaseRef}[])`。返回阶段 `accepted/prechecking/quiescing/saving/linking/completed/saved_unlinked/failed`、EnvironmentRef、逐目标结果和原定业务结果。修复输入含新 `repairOperationId`、原 endOperationId、用户确认后的目标/替换选择、新预期版本及新 leases。
- **操作身份 / 前提**：到达 End 时一次固定 endOperationId 和所有目标；目标只来自具写权的声明输入、本 Task 新建或显式写返回记录，纯查询不升级。无记录时可只保存环境。后续编辑工作流不改请求。
- **错误 / 事务边界**：`end_target_precheck_failed`, `end_save_failed`, `end_association_conflict`, `end_target_missing`, `end_access_revoked`。顺序固定为预检 → 停自动控制并关闭一致 → C14 发布环境 → C10 原子关联组 → 核验 → core 提交终态 → 释放/清理。文件保存与数据库关联不是长事务；各阶段用同一 End 身份幂等。
- **查询与恢复**：`queryEnd(endOperationId)` 只返回阶段和既有事实，不触发推进；协调器按原操作身份核验并续做未完成阶段，已完成保存不重复。**保存加关联才算完整**；保存成功关联失败为 `saved_unlinked`，Run 以失败终结并保留原定结果。修复只重新授权关联，不重跑网页、不重复保存、不改历史 Run；放弃关联也保留历史失败与已保存环境事实。

## 5. 状态转换

### 5.1 Batch

`accepted → running ↔ blocked → draining → completed|failed`；任一非终态可因停止进入 `stopping → stopped`，因重启/归属不明进入 `reconciling → interrupted`。存活 sidecar 对单 Worker 失联完成核验后，可按原失败政策回到领取阶段或 draining。`completed/stopped/failed/interrupted` 不可逆。blocked 表示资源暂占，不能伪装为数据耗尽；失败后默认关闭新领取但不更改任何业务状态。

### 5.2 CoreRun 与 Task

`queued → running → [finishing] → succeeded|failed`；`running → waiting_manual → resume_queued → running`；任一活动态可进入 `stopping → cancelled` 或 `reconciling → interrupted|既有已提交终态`；自动执行预算耗尽为 `timed_out`。五个终态 `succeeded/failed/cancelled/timed_out/interrupted` 不可逆。Task 只投影 CoreRun，Run 的结束时间只由 core 首次接受终态写入。

### 5.3 Instance、lease 与 End

- Instance：`reserved → starting → active ↔ waiting_manual → closing → closed → cleaning → cleaned`；异常为 `unknown`，保存路径为 `closed → saving → 已发布/retained_unsaved`，清理失败为 `cleanup_failed`。
- Lease：正常 Task 收尾在已提交本地写对账完成后走 `held → released`；失联/强停先走 `held → revoked → reconciling → released`，且只有确认旧执行终止或隔离后才释放。旧 leaseGeneration 一经 revoked 永不恢复。
- End：`accepted → prechecking → quiescing → saving → linking → completed`；保存前失败为 failed，保存成功后关联失败为 `saved_unlinked`。Run 终态后 repair 不把 End 历史 completed 化，也不改变历史 Run；它只追加“关联已修复/已放弃”的处置事实。

## 6. 提交、丢响应与失败矩阵

| 边界 | 提交前事实 | 提交后/响应丢失事实 | 唯一恢复动作 | 禁止行为 |
|---|---|---|---|---|
| 启动 Batch | 无 Batch；同 startOperationId 可重试 | 同身份已有唯一 Batch 或拒绝原因 | `queryStart` | 新建 operationId 规避未知 |
| 领取 + prepareRun | 无 Task、snapshot、lease、环境预约、queued Run | 五类事实同 UoW 全部存在 | 查 taskId/runRequestId；未派发可确认取消 | 部分释放、补建 Run、登记消费标记 |
| 派发 | queued 且浏览器动作未开始 | 派发代次可能已执行，边界不明 | 撤权、核验进程/实例/事件 | 因无成功事件重做网页动作 |
| 数据写 | 记录与修订不变 | 写、事件、同步意图可能已提交 | 查原 writeOperationId | 用旧版本或新身份再次写 |
| 动态 lease | 未取得则记录不变、立即返回 busy | 已取得则只有其 generation 可写 | 查 lease/原写操作，统一收尾 | 阻塞等待同时长期占住其他资源 |
| 普通停止 | 只接受命令，Run 仍可能 stopping | 终止确认后才有 cancelled 和可释放事实 | queryOperation/reconcile | 把命令接受当资源已停 |
| 强停/失联 | 先撤权；网站既有副作用不撤回 | 终止或隔离确认后终结 | C16 核验；未知保持 reconciling | 释放未知占用、重派原 Task |
| 人工继续/到期 | waiting/checkpoint 未变 | continue 接受后为 resume_requested，期限仍有效；真正开始恢复与 expire/lost 的 CAS 只有一个胜者 | 查 manualOperation/run；过期可撤销未开始恢复 | 把“已接受”当“已开始”、创建第二待办/新 Run |
| End 保存 | 环境当前指针不变 | contentGeneration 可能已发布，返回可能丢失 | `queryEnd/querySave` | 再保存、按名称找目标 |
| End 关联 | 保存结果保留；关联组尚未提交 | 全组已提交或全组未变；失败为 saved_unlinked | 同 End 查询；终态后新授权 repair | 清理唯一环境、部分改绑、改历史 Run |
| Run 终态 | 仍为活动/finishing | core 终态只提交一次，Task 投影或事件可能滞后 | queryRun 补投影 | 项目侧重算成功、自动写业务状态 |
| 归档/切工作区 | 新工作仍可进入 | closing 门闩先成立，受控收尾继续 | queryClosing 并核验 blocker | 提前只读卡死结算、未知即完成 |

## 7. 错误分类与调用方动作

| 类别 | 代表 code | 调用方动作 |
|---|---|---|
| 条件冲突 | `revision_conflict`, `link_revision_conflict`, `save_generation_conflict` | 刷新权威事实，保留草稿，让用户重新确认；不得自动提升 expected 值。 |
| 暂时占用 | `lease_busy`, `environment_busy` | 显示持有者/阻断，释放事件后重新求值；不算耗尽。 |
| 身份失效 | `dataset_generation_stale`, `record_identity_stale`, `environment_not_found` | 明确旧来源并要求修复引用；不按名称、行号或近似值迁移。 |
| 能力/配置 | `capability_missing`, `workflow_not_runnable`, `start_validation_failed` | 文档仍可编辑，禁止真实运行并列出缺项。 |
| 归属未知 | `resource_ownership_unknown`, `commit_fact_unknown` | 撤权、隔离、保持占用，进入可查询 reconcile。 |
| 操作重复 | `operation_payload_mismatch` | 相同请求取原结果；不同请求要求显式新操作，不能复用身份。 |

## 8. 当前实现事实与验收声明

本文件是**规范目标，不是已有代码说明**。初读f3fe376的Studio M1工作已在交付前由另一任务提交为 `b2e95b3`：`/api/v1/workflows` 已出现 CRUD 与 node catalog，`workflow_schemas.py` 的 `document.id` 为 UUID，并使用 `revision/expectedRevision`；已提交迁移 `0005_workflow_documents.py` 从 `0004` 派生，成为主线唯一head；节点仍 `runnable=false`，没有 Run 执行。它只支持把这里的 `workflowId` 对齐到核心文档身份，不能据此声称 XE-C01–C18 已实现。独立 UI 分支 `1fb58e1` 也仅作只读集成来源。

PM0 不计算任何项目管理业务测试通过。后续实现必须把本契约映射到唯一 OpenAPI、领域端口、事务测试、崩溃/丢响应测试和真实平台证据后，才可逐项更新交付状态。

## PM4 本地数据能力实现状态（2026-09-16）

本节记录实现证据，不改变 XE-C01–C18 的规范含义。

| 契约 | 当前已实现事实 | 当前验证边界 |
|---|---|---|
| XE-C04 | 数据型 Batch 按稳定候选游标准备输入组；提交前重查领取门闩、有效并发、表/数据代次、结构守卫和记录三修订，并在同一短事务写入 Task、不可变输入快照、合并后的 typed lease 与 queued CoreRun。必要输入失败不产生半 Task；可选空、暂占、无匹配、歧义、配置错误和扫描预算耗尽保持不同事实。有限/不限调度不保存批内排除集合。 | 本地数据、FastAPI、SQLite 与 fake executor 已验证；Sheets 物理来源排他身份在 PM6，真实生产执行核心 capability 绑定尚未验收，因此该契约保持部分验证。 |
| XE-C08 | `readProjectRecord` 与 `queryProjectRecords` 通过已冻结的记录/表读取授权限制项目、表、数据代次、字段与用途；返回独立快照及版本，读取不创建 lease，也不授予写权。 | fake executor 通过真实 capability 服务调用；未验证真实生产执行核心调用链。 |
| XE-C09 | 已交付本地记录查询、新增、编辑、删除、状态设置/清空，以及字段新增、确保存在和安全修改。动态写在短事务内取得 lease、校验 Task/Run/执行代次与 CAS、提交业务变化、Operation 结果和 Task 写游标；失败不遗留新增 lease。新增对象返回稳定 RecordRef/FieldRef，同操作同载荷恢复原结果。人工删除在预览和最终事务都阻止 `held/reconciling` lease；Excel 重新导入在预览、接受和最终发布都阻止当前数据代次的活动 lease。 | 本地表能力已验证；两项 lease 保护修复分别在 `d3a397cf`、`f07bb83b` 完成定向回归，当前源码 PM4-F 管理链也已重跑通过；19 张截图同视口视觉复审和阶段全量检查均已通过。环境关联属于 PM5，Sheets 同步意图与远端结构属于 PM6，真实生产执行核心调用尚未验收，因此完整 XE-C09 仍为部分验证。 |

权威阶段证据为 `pm4/a-verification.md`、`pm4/b-verification.md`、`pm4/c-verification.md` 与 `pm4/verification.json`。PM4-F 已用第二自动化确认第一自动化新增账号可被后续管理链读取。当前源码管理链 `f-QHALLW` 已通过；`f-4QcXFG` 保留前一提交候选的跨包工程回归和视觉审查，当前源码的视觉复审与阶段全量检查均已通过。PM4 管理功能已交付，验证状态仍为 `partially_verified`。PM3 管理前端定向回归 16 文件/121 项、管理后端定向回归 139 项通过；会启动真实 CloakBrowser/生产执行核心的 PM3 QA 未执行；真实生产执行核心、CloakBrowser、Studio、Windows、其他架构、打包及用户手测未执行。边界固定为“管理侧通过，真实执行核心接入待验收”。
