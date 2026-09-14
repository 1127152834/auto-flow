# 项目管理 HTTP、事件与桌面 IPC 契约

- 日期：2026-09-13。
- 状态：§1–8 保留 PM0 冻结时点的 planned 契约；后续 PM1/PM2 勘误及文末 R3 实施事实分别标明当前实现范围。不能用历史计划推断其余 handler 已实现。
- 依据：[功能结构](../design/functional-structure.md)、[数据与状态规则](../design/data-and-state-rules.md)、[数据传递契约](../design/data-flow-and-contracts.md)、[执行与环境规则](../design/execution-and-environment.md)、[共享领域契约](contracts.md)和[里程碑计划](../../superpowers/plans/2026-09-13-project-management-milestones.md)。
- 范围：公开 `/api/v1/projects` 项目子资源、项目聚合所需操作查询与事件、Studio/core Run 的消费边界、桌面文件选择 IPC、迁移及 OpenAPI 集成。本文不创建 handler、DTO、迁移或生成类型。
- 基线：交付前主目录已由另一任务提交为 `b2e95b3`。`/api/v1/workflows` CRUD 与 node catalog、`workflow_schemas.py`、`0005_workflow_documents.py` 均已提交；初读f3fe376+WIP的当前描述 superseded。核心 Run 路由尚不存在。`WorkflowDocument.document.id` 已校验为 UUID，保存使用 `expectedRevision`，当前节点目录均为 `runnable: false`。这些事实不是运行能力验收。

## 1. 传输惯例

### 1.1 命名、标量与时间

JSON 字段统一 `camelCase`，服务端继续继承现有 `ApiModel`。路径参数和查询参数也使用本文拼写。本地持久资源 ID、`*OperationId`、`runRequestId`、`datasetGeneration` 和 `Idempotency-Key` 是规范小写 UUID 字符串；核心的 node/input-field/visit 身份及供应商的 spreadsheet/sheet/column 身份按其权威契约传输，不因 `Id` 后缀强转 UUID。`workflowId` 就是核心 `WorkflowDocument.document.id`，不建立项目版工作流 ID 或第二份 IR。系统事件时间是带时区 RFC 3339 字符串；业务 `date` 标量另行保留纯日期或日期时间的精度：DateScalar.value 保存纯日期或不带 offset 的来源日期时间字符串（保留小数精度），offset 单独保存来源已知偏移；来源无时区时 `offset=null`，禁止强补 `Z`。修订和 sequence 是 JSON 安全整数；可从“尚无变化/尚无事件”的 `0` 开始，只有明确规定首代为 1 的值（如 `contentGeneration`）才从 1 开始。长编号和记录身份不经浮点数传输。

`null` 只用于业务上明确允许缺省的字段。请求字段若可省略，本文标作 `field?`；省略表示“不修改/使用默认”，显式 `null` 表示清空。列表始终返回数组，详情对象不存在返回 404，不用 `null` 冒充不存在。所有分页列表返回：

```ts
type Page<T> = {
  items: T[]
  page: number
  pageSize: number
  total: number
  sort: string
}
```

通用查询参数为 `page`（默认 1）、`pageSize`（默认 50，上限 200）、`sort`、`q`；每个目录另列筛选。普通目录使用确定的稳定排序（排序值相同以稳定身份收尾），返回当次 `items/page/pageSize/total/sort`；非法筛选返回 422。本文不虚构覆盖所有目录的快照修订或目录级结果保留能力。只有统计查询按已确认口径返回带有效期的 `resultSetId`，并保证该结果标识下的指标、趋势和下钻集合一致。

### 1.2 错误

所有非 2xx 响应复用现有 envelope：

```ts
type ErrorEnvelope = {
  error: {
    code: string
    message: string
    details: Record<string, JsonValue>
    requestId: string
  }
}
```

领域 `DomainError.code` 与 HTTP envelope 使用同一语义注册表；传输时只做确定的 ASCII snake_case → upper snake case 转换，例如 `revision_conflict → REVISION_CONFLICT`、`lease_busy → LEASE_BUSY`，不得改词或另建分类。`details.domainCode` 保留原 code，`details.retryable` 原样传输领域 boolean；retryable 不授权换 key 重跑网页或盲重发外部动作。持久 Operation.error 使用同样的 code/details 投影。

领域卡内错误按下表固定 HTTP 状态（公开 code 均为原词大写）。其他已列领域错误统一为 409，不通过后缀猜状态；新增错误须随真实 handler 显式登记。`lease_busy` 唯一映射为 423 `LEASE_BUSY`，`operation_payload_mismatch` 唯一映射为 409 `OPERATION_PAYLOAD_MISMATCH`，不能另用 `RESOURCE_BUSY/LEASE_UNAVAILABLE/OPERATION_CONFLICT` 替代。

| HTTP | 领域 code |
|---:|---|
| 404 | `not_found`, `project_scope_mismatch`, `environment_scope_mismatch`, `environment_not_found`, `association_target_missing`, `end_target_missing`, `prepared_content_missing`, `artifact_unavailable` |
| 403 | `capability_scope_denied`, `association_replace_forbidden`, `end_access_revoked` |
| 410 | `dataset_generation_stale`, `record_identity_stale`, `execution_generation_revoked`, `lease_revoked`, `manual_expired` |
| 412 | `impact_changed` |
| 422 | `workflow_invalid`, `capability_missing`, `workflow_dependency_missing`, `workflow_dependency_cycle`, `workflow_not_runnable`, `start_validation_failed`, `unbounded_without_required_input`, `input_ambiguous`, `event_cursor_invalid`, `query_invalid`, `environment_incompatible`, `environment_source_ambiguous`, `resume_prerequisite_missing`, `end_target_precheck_failed` |
| 423 | `lease_busy`, `environment_busy`, `input_group_unavailable` |
| 503 | `storage_failed` |
| 409 | 上述表未覆盖的现有领域卡 code，包括修订冲突、门闩、未知归属、未确认终止和保留失败；未知事实以 details 中原 operationId 查询，不能把冲突当作从未执行。 |

`details` 的稳定形状包括：字段错误 `{fields: Record<string,string>}`；修订冲突 `{expectedRevision,currentRevision,current?: JsonValue}`；依赖阻断 `{blockers: Blocker[]}`；结果不明 `{operationId,status:'unknown'}`；能力缺失 `{capabilities: CapabilityRequirement[]}`。不得把本地路径、凭据、Cookie、远端 token、堆栈或 SQL 放入错误。

| HTTP | 通用代码 | 含义 |
|---:|---|---|
| 400 | `INVALID_COMMAND` | 请求结构合法但动作组合自相矛盾。 |
| 401 | `UNAUTHORIZED` | 缺失或错误的 sidecar bearer token。 |
| 404 | `PROJECT_NOT_FOUND` / `RESOURCE_NOT_FOUND` / `OPERATION_NOT_FOUND` | 作用域内对象不存在；不泄露其他项目对象。 |
| 409 | `REVISION_CONFLICT` / `LIFECYCLE_CONFLICT` / `IDENTITY_CONFLICT` / `OPERATION_PAYLOAD_MISMATCH` | CAS、生命周期、稳定身份或相同幂等键载荷冲突。 |
| 410 | `GENERATION_RETIRED` | `datasetGeneration` 或环境 `contentGeneration` 已换代。 |
| 412 | `PRECONDITION_FAILED` | 影响版本、文件指纹、来源 epoch 或能力前提变化。 |
| 422 | `VALIDATION_ERROR` / `REFERENCE_INVALID` / `WORKFLOW_NOT_RUNNABLE` | 字段、引用、映射、输入或工作流校验失败。 |
| 423 | `PROJECT_CLOSING` / `LEASE_BUSY` / `ENVIRONMENT_BUSY` | closing 门闩或非阻塞 lease/环境竞争。 |
| 429 | `CAPACITY_EXHAUSTED` | 运行/人工现场额度满；`details.retryAfterSeconds` 可选。 |
| 503 | `SERVICE_UNAVAILABLE` / `PROVIDER_UNAVAILABLE` / `CREDENTIAL_STORE_UNAVAILABLE` | 本地服务或受控 provider 暂不可用。 |
| 504 | `OPERATION_RESULT_UNKNOWN` | 外部结果无法在本次请求内确认；必须返回 `operationId`，对应操作保持 `reconciling` 且 `details.resultState='unknown'`。 |

具体资源错误在通用代码上增加前缀明确的代码，例如 `FIELD_IN_USE`、`FORMULA_FIELD_READ_ONLY`、`SYNC_TARGET_AMBIGUOUS`、`RUN_STATE_CONFLICT`、`ENVIRONMENT_CONTENT_CONFLICT`。OpenAPI 为每个 handler 列出实际可产生的错误，不用一张虚假的全量错误表覆盖所有端点。

### 1.3 持久命令、202 和恢复

所有可能持久化事实、启动后台工作或调用外部能力的命令必须携带 UUID `Idempotency-Key`。幂等身份在 workspace 内按操作 key 唯一，规范载荷包含 operation kind、父级作用域和全部目标身份，避免同 key 在不同项目或资源上产生歧义；同一 key 和等价规范载荷永远返回同一 `operationId` 与既有结果，同 key 不同载荷返回 409 `OPERATION_PAYLOAD_MISMATCH`。普通只读 GET、只更新最近打开时间的 `POST .../open` 以及不持久化检查结果的纯预检不要求该 header。

```ts
type OperationStatus = 'accepted'|'running'|'reconciling'|'succeeded'|'failed'
type Operation = {
  operationId: string
  projectId: string | null
  kind: OperationKind
  status: OperationStatus
  statusRevision: number
  resource: ResourceLocator
  result: JsonValue | null
  error: {code:string; message:string; details:Record<string,JsonValue>} | null
  createdAt: string
  updatedAt: string
  completedAt: string | null
}
type OperationAccepted = { operation: Operation }
```

`202 Accepted` 只表示已持久接受，不表示成功。同步完成的短命令可直接返回 200/201 的最终资源；若同一操作已存在，重复请求按现状返回 200（终态）或 202（非终态）。首次响应丢失时，客户端必须先用 §3.7 的同作用域查询路由找回；只有明确未发送或查询确认未接受时，才允许以原 `Idempotency-Key` 重发完全相同的命令；创建项目尚无 projectId，因此使用 workspace 级找回路由。不得生成新 key 盲重试。`Operation.result` 按 `kind` 使用本文定义的结果类型，不使用未定义字典。

> 2026-09-13恢复规则勘误（confirmed，来源：后续获批PM1/PM2实施计划）：上段旧“重发或查询”并列选项由“未知先查询，确认未接受才原键重发”替代。若操作已接受并以失败终结，不重发旧键以企图改写失败结果；需要继续处置的残留清理使用新显式操作身份，保留旧失败事实。此处只同步合同文本，PM0历史报告不改写，不代表本轮运行代码测试。

## 2. 共享对象

以下是 HTTP 投影；领域不变量以 [contracts.md](contracts.md) 为唯一命名来源。

```ts
type JsonScalar = string | number | boolean | null
type JsonValue = JsonScalar | JsonValue[] | {[key:string]:JsonValue}
type DateScalar = {kind:'date';precision:'date'|'datetime';value:string;offset:string|null}
type ScalarValue = string | number | boolean | DateScalar | null
type ProjectLifecycleState = 'active'|'closing'|'archived'|'deleting'|'deleted'
type Project = {projectId:string; name:string; description:string; managementRevision:number; lifecycleState:ProjectLifecycleState; defaultResources:ProjectDefaultResources; createdAt:string; updatedAt:string; lastOpenedAt?:string}
type ProjectCapabilities = Record<'automations'|'data'|'runs'|'environments'|'statistics'|'sync',Availability>
type ProjectSummary = Project & {automationCount?:number; tableCount?:number; activeBatchCount?:number; manualCount?:number; attentionCount?:number;availability:ProjectCapabilities}
type ResourceLocator =
  | {type:'project';projectId:string}
  | {type:'automation';projectId:string;automationId:string}
  | {type:'table';projectId:string;tableId:string}
  | {type:'record';recordRef:RecordRef}
  | {type:'field';fieldRef:FieldRef}
  | {type:'status';projectId:string;tableId:string;statusId:string}
  | {type:'sheetsConnection';projectId:string;connectionId:string}
  | {type:'batch';projectId:string;batchId:string}
  | {type:'task';projectId:string;taskId:string}
  | {type:'environment';projectId:string;environmentId:string}
  | {type:'sync';projectId:string;tableId:string;syncOperationId:string}
type Blocker = {code:string; resource:ResourceLocator; state:string; message:string; operationId?:string}
type Impact = {code:string; resource:ResourceLocator; message:string; blocking:boolean}

type FieldRef = {projectId:string; tableId:string; datasetGeneration:string; fieldId:string}
type RecordKey = {type:'text'|'integer'|'uuid'; value:string}
type RecordRef = {projectId:string; tableId:string; datasetGeneration:string; recordKey:RecordKey}
type EnvironmentRef = {projectId:string; environmentId:string; contentGeneration:number; metadataRevision:number}

type FieldType = 'string'|'number'|'boolean'|'date'
type FieldDefinition = {ref:FieldRef; key:string; name:string; type:FieldType; required:boolean; writable:boolean; formula:boolean; validation:FieldValidation; fieldRevision:number}
type FieldValidation = {minLength?:number; maxLength?:number; minimum?:number; maximum?:number; pattern?:string}
type StatusDefinition = {statusId:string; name:string; color:string; order:number; statusRevision:number}
type SlotDefinition = {slotId:string;name:string;targetTableId:string;required:boolean}
type DataTable = {projectId:string; tableId:string; name:string; description:string; sourceKind:'local'|'excel'|'sheets'|'unconfigured'; datasetGeneration:string; tableRevision:number; slotDefinitions:SlotDefinition[]; recordCount:number; syncSummary:SyncSummary; createdAt:string; updatedAt:string}
type CellValue = {fieldId:string; value:ScalarValue; source:'local'|'remote'|'formula'; readable:boolean; error?:string}
type RecordSlotValue = {slotId:string;target:RecordRef|null}
type DataRecord = {ref:RecordRef; values:CellValue[]; recordSlots:RecordSlotValue[]; statusId:string|null; currentEnvironmentId:string|null; contentRevision:number; statusRevision:number; linkRevision:number; deleted:boolean; createdAt:string; updatedAt:string}

type InputMode = 'independent'|'fixedRecord'|'related'
type InputRelation =
  | {type:'recordSlot';slotId:string;sourceInputId:string}
  | {type:'fieldEquals';sourceInputId:string;sourceFieldRef:FieldRef;targetFieldRef:FieldRef}
  | {type:'sameRecord';sourceInputId:string}
type InputFieldBinding = {inputFieldId:string;inputFieldAlias:string;fieldRef:FieldRef}
type InputDefinition = {inputId:string; alias:string; tableId:string; datasetGeneration:string; mode:InputMode; required:boolean; fixedRecord?:RecordRef; relation?:InputRelation; fieldBindings:InputFieldBinding[]; filter:FilterExpression; orderBy:OrderBy[]}
type InputPlan = {inputs:InputDefinition[]}
type ParameterDefinition = {parameterId:string; name:string; type:'string'|'number'|'boolean'; required:boolean; defaultValue?:JsonScalar}
type ProxySelection = {mode:'sourceDefault'|'none'|'fixed'|'pool';proxyId?:string;proxyPoolId?:string}
type ProjectDefaultResources = {profileId:string|null;proxy:ProxySelection;modelProviderId:string|null}
type EnvironmentSource =
  | {source:'newFromProfile';profileId?:string}
  | {source:'fixedEnvironment';environmentId:string}
  | {source:'inputEnvironment';inputId:string}
type EnvironmentPolicy = EnvironmentSource & {proxyOverride?:ProxySelection}
type CapabilityRequirement = {capability:string; required:boolean; available:boolean; reason?:string}
type CapabilityBinding = {capability:string;provider:string;scope:string;bindingRevision:number}
type RunPolicy = {maxTasks?:number;concurrency:number;maxLiveInstances:number;continueAfterFailure:boolean;automaticExecutionTimeoutSeconds:number;manualDeadlineSeconds:number}
type Automation = {automationId:string; projectId:string; workflowId:string; name:string; description:string; managementRevision:number; inputPlan:InputPlan; parameterSchema:ParameterDefinition[]; environmentPolicy:EnvironmentPolicy; capabilityRequirements:CapabilityRequirement[]; runPolicy:RunPolicy; createdAt:string; updatedAt:string}

type BatchStatus = 'accepted'|'running'|'blocked'|'draining'|'stopping'|'reconciling'|'completed'|'stopped'|'failed'|'interrupted'
type CoreRunStatus = 'queued'|'running'|'waiting_manual'|'resume_queued'|'finishing'|'stopping'|'reconciling'|'succeeded'|'failed'|'cancelled'|'timed_out'|'interrupted'
type TaskStatus = CoreRunStatus
type Batch = {batchId:string; projectId:string; automationId:string; startOperationId:string; status:BatchStatus; statusRevision:number; managementRevision:number; requestedCount?:number; createdTaskCount:number; activeTaskCount:number; createdAt:string; completedAt?:string}
type Task = {taskId:string; projectId:string; batchId:string; runId:string; runRequestId:string; status:TaskStatus; statusRevision:number; inputSnapshotId:string; createdAt:string; completedAt?:string}
type FrozenFieldMapping = {fieldId:string;sourceKey:string;sourceName:string;sourceType:FieldType;inputFieldId:string;inputFieldAlias:string}
type InputSnapshot = {recordRef:RecordRef;recordSlots:RecordSlotValue[];fields:{fieldId:string;value:ScalarValue}[];fieldMappings:FrozenFieldMapping[];statusId:string|null;currentEnvironmentId:string|null;contentRevision:number;statusRevision:number;linkRevision:number;sourceSummary:JsonValue;capturedAt:string}
type TaskInputSnapshot = {inputSnapshotId:string; taskId:string; batchId:string; parameters:Record<string,JsonScalar>; inputs:{inputId:string;inputAlias:string;value:InputSnapshot|null;unavailableReason:null|'no_match'|'busy'}[]; capturedAt:string}
type ResourceRequest =
  | {browser:'none';modelProviderId:string|null}
  | {browser:'newFromProfile';profileId:string;kernelId:string;proxy:{mode:'profile'|'none'|'fixed'|'pool';proxyId?:string;proxyPoolId?:string};modelProviderId:string|null;frozenConfiguration:JsonValue}
  | {browser:'persistent';environmentRef:EnvironmentRef;kernelId:string;proxy:{mode:'savedPolicy'|'none'|'fixed'|'pool';proxyId?:string;proxyPoolId?:string};modelProviderId:string|null;frozenIdentityPackage:JsonValue}
type CoreRun = {runId:string; runRequestId:string; status:CoreRunStatus; statusRevision:number; executionGeneration:number; preparedContentId:string; capabilityBindings:CapabilityBinding[]; resourceRequest:ResourceRequest; lastSequence:number; terminal:boolean; startedAt:string|null; finishedAt:string|null}
type NodeAttempt = {nodeVisitId:string; nodeId:string; attempt:number; status:'running'|'succeeded'|'failed'|'timed_out'|'cancelled'|'interrupted'|'waiting_manual'|'resolved_manually'; startedAt:string|null; completedAt:string|null; error:Operation['error']}
type Preview<T> = {items:T[];total:number;hasMore:boolean;limit:50}
type TaskDetail = {task:Task; inputSnapshot:TaskInputSnapshot; run:CoreRun; nodeAttempts:Preview<NodeAttempt>; outputs:Preview<RunOutput>; cleanup:CleanupSummary}
type RunOutput = {outputId:string; kind:'value'|'table'|'file'|'screenshot'; name:string; value?:JsonValue; artifactId?:string; createdAt:string}
type CleanupSummary = {status:'notRequired'|'pending'|'running'|'succeeded'|'failed'|'unknown'; operationId?:string; message?:string}

type SyncStatus = 'notApplicable'|'idle'|'pending'|'sending'|'verifying'|'confirmed'|'failed'|'unknown'|'paused'
type SyncSummary = {status:SyncStatus; pendingCount:number; unknownCount:number; lastConfirmedAt?:string}
type SyncOperation = {syncOperationId:string; projectId:string; tableId:string; record?:RecordRef; bindingEpoch:number; targetContentRevision:number; status:SyncStatus; statusRevision:number; operationId:string; evidence?:SyncEvidence}
type SyncEvidence = {checkedAt:string; target:string; fields:string[]; outcome:'matched'|'notMatched'|'ambiguous'}
type PersistentEnvironmentState = 'ready'|'unavailable'|'deleting'|'deleted'
type InstanceState = 'reserved'|'starting'|'active'|'waiting_manual'|'closing'|'closed'|'saving'|'retained_unsaved'|'cleaning'|'cleaned'|'cleanup_failed'|'unknown'
type Environment = {ref:EnvironmentRef; name:string; state:PersistentEnvironmentState; profileId:string; unavailableReason:string|null; createdAt:string; updatedAt:string}
type EnvironmentInstance = {instanceId:string;environmentId:string|null;state:InstanceState;activeTaskId:string|null;maintenanceOperationId:string|null;createdAt:string;updatedAt:string}
type ManualItem = {manualItemId:string; projectId:string; taskId:string; runId:string; checkpointRevision:number; status:'waiting'|'resume_requested'|'resolved'|'expired'|'lost'|'cancelled'; expiresAt:string|null; allowedTargets:ResumeTarget[]; statusRevision:number}
type ResumeTarget = {nodeId:string; label:string; missingRequirements:CapabilityRequirement[]}
```

可选输入只有 `required=false` 且确实无匹配或候选暂占时才允许 `value=null`，并必须分别写 `no_match` 或 `busy`。配置错误、读取失败、引用过期或字段映射失效必须拒绝领取，不能复用旧 Task 的输入快照或编码成 null。相同 `RecordRef` 的显式输入别名分别冻结 `inputAlias` 和 `fieldMappings`，但物理 lease 合并。

本地持久资源 ID 和 `datasetGeneration` 是规范 UUID 字符串；核心及来源系统身份遵守其权威类型。`contentGeneration` 是同一 `environmentId` 内从 1 开始单调递增的 JSON 安全整数，不是 UUID。`RecordKey.value` 随 `type` 规范化：`text` 保留经表身份规则验证的文本；`integer` 只有在来源已证明是可靠整数且未越过来源及 JSON 安全精度时，才写成无小数、指数和多余前导零的十进制字符串（零只写 `"0"`），超限来源必须按 text 配置，禁止把已舍入数值转字符串；`uuid` 是规范小写 UUID。`RecordRef` JSON 始终携原始规范 value；记录路径的 `{recordKey}` 则是该 value 的 UTF-8 字节经 base64url 无 padding 编码，服务端严格解码一次、按显式 `recordKeyType` 校验规范后查询，不从 URL 字面值猜类型或身份。这允许 text key 合法包含 `/` 等任意非空文本。

过滤表达式是封闭递归联合：

```ts
type FilterExpression =
  | {type:'all'; items:FilterExpression[]}
  | {type:'any'; items:FilterExpression[]}
  | {type:'not'; item:FilterExpression}
  | {type:'compare'; fieldId:string; operator:'eq'|'neq'|'gt'|'gte'|'lt'|'lte'|'contains'|'startsWith'|'isNull'|'isNotNull'; value?:ScalarValue}
  | {type:'status'; operator:'eq'|'neq'|'isNull'|'isNotNull'; statusId?:string}
type OrderBy = {fieldId?:string; systemField?:'status'|'createdAt'|'updatedAt'|'recordKey'; direction:'asc'|'desc'}
```

## 3. 路由目录

表中“包”是首次真实 handler 所属交付包；后续包可扩展响应事实，但不能先建空端点。`scope` 表示服务端必须从父路径重新校验归属，不能信任 body 内重复 ID。

### 3.1 项目、概览与生命周期

| Method / path | 包 | 请求 | 成功响应 | scope 与主要错误 |
|---|---|---|---|---|
| `GET /api/v1/projects` | PM1-A | `q,lifecycleState,page,pageSize,sort` | `Page<ProjectSummary>` | workspace；422 筛选。 |
| `POST /api/v1/projects` | PM1-A | header key；`{name,description,defaultResources?}` | 201 `Project` | workspace 名称唯一；409 `PROJECT_NAME_CONFLICT`。 |
| `GET /api/v1/projects/{projectId}` | PM1-A | — | `ProjectSummary` | project；404。 |
| `PATCH /api/v1/projects/{projectId}` | PM1-A | header key；`{name?,description?,defaultResources?,expectedManagementRevision}` | 200 `Project` | active project；409 修订/重名，423 closing；资源缺失可保存引用，但运行前明确阻断。 |
| `POST /api/v1/projects/{projectId}/open` | PM1-A | — | 200 `{project,lastOpenedAt}` | project；幂等更新最近访问，不改 `updatedAt`。 |
| `GET /api/v1/projects/{projectId}/overview` | PM1-B→PM7-B | — | `ProjectOverview` | project；首次只返回已接入事实，未知计数使用 `availability`，不填 0。 |
| `GET /api/v1/projects/{projectId}/lifecycle-impact` | PM8-A | `action=archive|delete` | `{impactRevision,blockers,impacts,unsyncedCount}` | project；409 生命周期状态。 |
| `POST /api/v1/projects/{projectId}/archive` | PM8-A | header key；`{impactRevision,expectedManagementRevision}` | 202 `OperationAccepted` | project；412 影响变化；操作负责 closing 和收尾。 |
| `POST /api/v1/projects/{projectId}/restore` | PM8-A | header key；`{expectedManagementRevision}` | 202 `OperationAccepted` | archived project；不会重跑/重发。 |
| `DELETE /api/v1/projects/{projectId}` | PM8-A | header key；`{confirmationName,impactRevision,expectedManagementRevision}` | 202 `OperationAccepted` | archived project；412/423/409；不删外部文件/Sheet/全局资源。 |

```ts
type Availability = 'available'|'notImplemented'|'unavailable'|'stale'
type ProjectOverview = {project:Project; counts:{automations?:number;tables?:number;batches?:number;environments?:number}; availability:ProjectCapabilities; activity:AttentionItem[]; recent:ActivityItem[]}
type AttentionItem = {kind:'batch'|'task'|'manual'|'resource'|'sync'|'cleanup'; resource:ResourceLocator; severity:'info'|'warning'|'error'; message:string; occurredAt:string}
type ActivityItem = {activityId:string; kind:string; resource:ResourceLocator; summary:string; occurredAt:string}
```

### 3.2 自动化

| Method / path | 包 | 请求 | 成功响应 | scope 与主要错误 |
|---|---|---|---|---|
| `GET /api/v1/projects/{projectId}/automations` | PM3-A | `q,page,pageSize,sort` | `Page<Automation>` | project；404。 |
| `POST /api/v1/projects/{projectId}/automations` | PM3-A | header key；`AutomationWrite` | 201 `Automation` | active project；409 workflow 已关联/名称冲突；422 引用。 |
| `GET /api/v1/projects/{projectId}/automations/{automationId}` | PM3-A | — | `Automation` | project + automation；404。 |
| `PUT /api/v1/projects/{projectId}/automations/{automationId}` | PM3-A | header key；`AutomationWrite & {expectedManagementRevision}` | 200 `Automation` | active project；409 revision；缺能力允许保存并在投影标明。 |
| `GET /api/v1/projects/{projectId}/automations/{automationId}/validation` | PM3-A→PM5 | — | `AutomationValidation` | project；实时核对 workflow/字段/来源/资源。 |
| `GET /api/v1/projects/{projectId}/automations/{automationId}/impact` | PM8-A | `action=delete|unlinkWorkflow` | `{impactRevision,impacts,blockers}` | project；包含运行/文档占用。 |
| `DELETE /api/v1/projects/{projectId}/automations/{automationId}` | PM8-A | header key；`{impactRevision,expectedManagementRevision,workflowDisposition:'unlink'|'deleteOwned'}` | 202 `OperationAccepted` | project；独立 workflow 只能 unlink；核心确认无占用后才删 owned 文档。 |

```ts
type AutomationWrite = {name:string;description:string;workflowId:string;inputPlan:InputPlan;parameterSchema:ParameterDefinition[];environmentPolicy:EnvironmentPolicy;runPolicy:RunPolicy}
type AutomationValidation = {valid:boolean;runnable:boolean;issues:{path:string[];code:string;message:string;resource?:ResourceLocator}[];capabilityRequirements:CapabilityRequirement[];checkedAt:string}
```

打开 Studio 是 Desktop IPC（§6），不增加 `POST .../open-studio`。项目管理保存 Automation 和核心保存 Workflow 是两个独立修订；任何一边失败都保留另一边真实状态。

`RunPolicy` 的 `concurrency`（C）和 `maxLiveInstances`（H）都是正整数，且 H 不得低于当前不能立即清理的现场数；默认 H=C。`automaticExecutionTimeoutSeconds` 不计人工等待与恢复排队，`manualDeadlineSeconds` 分别作用于每个人工项。默认秒数只有在核心基线实际验证后才能继承；功能首次启用时最终适用值必须是可见、有限的正数。`maxTasks` 对无必要输入的启动必须存在且有限。`InputPlan` 只描述输入及关联，不重复这些运行政策。

环境身份来源是唯一判别分支：从配置新建时解析 Profile；固定环境和输入记录环境按稳定 `environmentId` 解析其已发布身份包与兼容内核，不回退到 Profile。代理是独立覆盖链，三个身份来源都允许显式覆盖，按“启动明确覆盖 → 自动化 `proxyOverride` → 项目默认 → 身份来源默认”解析；最后一项对新环境是 Profile 代理，对持久环境是保存来源的代理策略。仅环境暂时占用进入 blocked/等待；引用缺失、内容不可用或平台/内核不兼容明确失败，不以通用 `onUnavailable=wait` 持续监听。

### 3.3 数据表、字段、状态和记录

| Method / path | 包 | 请求 | 成功响应 | scope 与主要错误 |
|---|---|---|---|---|
| `GET /api/v1/projects/{projectId}/tables` | PM2-A | `q,sourceKind,page,pageSize,sort` | `Page<DataTable>` | project。 |
| `POST /api/v1/projects/{projectId}/tables` | PM2-A | header key；`{name,description,sourceKind:'local'}` | 201 `DataTable` | active project；409 名称。 |
| `GET /api/v1/projects/{projectId}/tables/{tableId}` | PM2-A | — | `DataTable` | project + table。 |
| `PATCH /api/v1/projects/{projectId}/tables/{tableId}` | PM2-A→PM4-B | header key；`{name?,description?,slotDefinitions?,expectedTableRevision,impactRevision?}` | 200 `DataTable` | active/current generation；槽定义以 slotId 稳定，改目标表/删除时校验自动化、记录和活动运行引用；409/412。 |
| `GET /api/v1/projects/{projectId}/tables/{tableId}/impact` | PM2-B→PM8 | `action=replaceDataset|delete|changeSource` | `{impactRevision,impacts,blockers}` | table；含 lease、automation、sync、link。 |
| `POST /api/v1/projects/{projectId}/mutation-impact` | PM2-A→PM6-C | `MutationImpactRequest`；纯预检不建 Operation | `ImpactReport` | 只读目标/依赖事实；报告绑定精确动作、目标、拟变更及相关修订，跨项目目标拒绝；提交不能拿表级空白确认代替。 |
| `DELETE /api/v1/projects/{projectId}/tables/{tableId}` | PM8-A | header key；`{impactRevision,expectedTableRevision}` | 202 `OperationAccepted` | project；不删原 Excel/Sheet。 |
| `GET /api/v1/projects/{projectId}/tables/{tableId}/fields` | PM2-A | — | `{items:FieldDefinition[];tableRevision:number}` | current dataset。 |
| `POST /api/v1/projects/{projectId}/tables/{tableId}/fields` | PM2-A/PM4-B | header key；`{definition:FieldWrite,expectedTableRevision,existingRecordDefault?:ScalarValue,sourceColumnPolicy:'localOnly'|'mapped'}` | 200 `{field:FieldDefinition;tableRevision:number}` | 409 同名；422 必填/类型；412 来源策略。 |
| `PATCH /api/v1/projects/{projectId}/tables/{tableId}/fields/{fieldId}` | PM2-A/PM4-B | header key；`{definition:FieldWrite,expectedFieldRevision,expectedTableRevision,impactRevision}` | 200 `{field,tableRevision}` | 409/412；公式字段受保护。 |
| `DELETE /api/v1/projects/{projectId}/tables/{tableId}/fields/{fieldId}` | PM4-B | header key；`{expectedFieldRevision,expectedTableRevision,impactRevision}` | 202 `OperationAccepted` | 423 `FIELD_IN_USE`；破坏引用必须拒绝或按影响操作。 |
| `GET /api/v1/projects/{projectId}/tables/{tableId}/statuses` | PM2-A | — | `{items:StatusDefinition[];tableRevision:number}` | table。 |
| `POST /api/v1/projects/{projectId}/tables/{tableId}/statuses` | PM2-A | header key；`{name,color,order,expectedTableRevision}` | 201 `StatusDefinition` | active table；409 名称。 |
| `PATCH /api/v1/projects/{projectId}/tables/{tableId}/statuses/{statusId}` | PM2-A | header key；`{name?,color?,order?,expectedStatusRevision,expectedTableRevision}` | 200 `StatusDefinition` | 409。 |
| `DELETE /api/v1/projects/{projectId}/tables/{tableId}/statuses/{statusId}` | PM2-A | header key；`{expectedStatusRevision,expectedTableRevision,impactRevision}` | 202 `OperationAccepted` | 任一当前记录、筛选、自动化或活动运行引用均阻止；先用独立显式状态命令清空/改设引用，删除动作不暗改记录。 |
| `GET /api/v1/projects/{projectId}/tables/{tableId}/records` | PM2-A | `datasetGeneration,filter,orderBy,page,pageSize` | `Page<DataRecord>` | 410 generation；422 filter。复杂 `filter/orderBy` 是 URL-safe base64url 编码 JSON。 |
| `POST /api/v1/projects/{projectId}/tables/{tableId}/records` | PM2-A/PM4-B | header key；`{datasetGeneration,values}` | 201 `DataRecord` | active table；身份/类型/公式校验；新记录一律 `statusId=null`，初始化须另发显式状态命令。 |
| `GET /api/v1/projects/{projectId}/tables/{tableId}/records/{recordKey}` | PM2-A | `datasetGeneration,recordKeyType` | `DataRecord` | recordKey 为规范 value 的 UTF-8 base64url 无 padding 编码；严格一次解码；404/410。 |
| `PATCH /api/v1/projects/{projectId}/tables/{tableId}/records/{recordKey}` | PM2-A/PM4-B | header key；`{datasetGeneration,recordKeyType,values,expectedContentRevision}` | 200 `DataRecord` | 身份与来源可靠固定时人工普通字段允许 CAS，即使 Task 正持 lease；身份/来源/占用归属未知才 423，409 内容，422 formula。 |
| `PUT /api/v1/projects/{projectId}/tables/{tableId}/records/{recordKey}/status` | PM2-A/PM4-B | header key；`{datasetGeneration,recordKeyType,statusId,expectedStatusRevision,expectedFromStatusId?}`；`statusId` 可 null | 200 `DataRecord` | 人工状态写要求无活动/未知占用；409 状态前提，不改 contentRevision。 |
| `POST /api/v1/projects/{projectId}/tables/{tableId}/record-status-batches/preview` | PM2-A/PM4-B | `RecordStatusBatchRequest`；纯预检 | `RecordStatusBatchPreview` | 校验固定显式选择，显示各块目标与阻断；不持 lease、不授权写入，提交仍逐块重新校验。 |
| `POST /api/v1/projects/{projectId}/tables/{tableId}/record-status-batches` | PM2-A/PM4-B | header key；`RecordStatusBatchRequest` | 202 `OperationAccepted` | 仅接受固定显式 targets；按有限块执行，每块状态更新全成或全冲突。取消只停止尚未开始的块，不回滚已提交块；result=`RecordStatusBatchOutcome`。 |
| `POST /api/v1/projects/{projectId}/tables/{tableId}/record-status-batches/{operationId}/cancel` | PM2-A/PM4-B | header key；`{expectedOperationRevision}` | 202 `OperationAccepted` | 只关闭原批量状态操作的后续块；已提交块及其事件不回滚。 |
| `PUT /api/v1/projects/{projectId}/tables/{tableId}/records/{recordKey}/environment` | PM5-B | header key；`{datasetGeneration,recordKeyType,environmentId,expectedContentGeneration,expectedLinkRevision,replace}`；`environmentId` 可 null | 200 `DataRecord` | 人工关联写要求无活动/未知占用；同项目，409 link/content。 |
| `PUT /api/v1/projects/{projectId}/tables/{tableId}/records/{recordKey}/slots/{slotId}` | PM4-B | header key；`{datasetGeneration,recordKeyType,target:RecordRef|null,expectedLinkRevision}` | 200 `DataRecord` | 校验槽定义、目标表和完整 RecordRef；人工写要求无活动/未知占用，工作流写要求有效 Task lease；只推进 linkRevision。 |
| `DELETE /api/v1/projects/{projectId}/tables/{tableId}/records/{recordKey}` | PM2-A/PM4-B | header key；`{datasetGeneration,recordKeyType,expectedContentRevision,expectedStatusRevision,expectedLinkRevision,impactRevision}` | 202 `OperationAccepted` | 423 lease；Sheets 整行影响须明确。 |

```ts
type FieldWrite = {key:string;name:string;type:FieldType;required:boolean;validation:FieldValidation}
type MutationImpactRequest =
  | {action:'updateField';target:Extract<ResourceLocator,{type:'field'}>;change:FieldWrite}
  | {action:'deleteField';target:Extract<ResourceLocator,{type:'field'}>}
  | {action:'deleteStatus';target:Extract<ResourceLocator,{type:'status'}>}
  | {action:'deleteRecord';target:Extract<ResourceLocator,{type:'record'}>}
  | {action:'updateSlots';target:Extract<ResourceLocator,{type:'table'}>;change:{slotDefinitions:SlotDefinition[]}}
  | {action:'disconnectSheets';target:Extract<ResourceLocator,{type:'sheetsConnection'}>;change:{mode:'disconnect'|'forgetCredential'}}
type ImpactReport = {impactRevision:number;target:ResourceLocator;changeDigest:string;expectedRevisions:Record<string,number>;impacts:Impact[];blockers:Blocker[];calculatedAt:string}
type RecordStatusBatchRequest = {statusId:string|null;targets:{recordRef:RecordRef;expectedStatusRevision:number}[];blockSize:number}
type RecordStatusBlock = {blockIndex:number;targets:{recordRef:RecordRef;expectedStatusRevision:number}[];state:'notStarted'|'committed'|'conflicted';blockers:Blocker[];committedRevisions:{recordRef:RecordRef;statusRevision:number}[]}
type RecordStatusBatchPreview = {request:RecordStatusBatchRequest;blocks:RecordStatusBlock[];checkedAt:string}
type RecordStatusBatchOutcome = {outcome:'processing'|'completed'|'conflicted'|'cancelled'|'failed';request:RecordStatusBatchRequest;blocks:RecordStatusBlock[];changedCount:number;conflictCount:number;notStartedCount:number;cancelled:boolean}
```

`ImpactReport` 的 `impactRevision` 是带有效期的服务端确认记录修订，绑定 project、动作、完整 target locator、拟变更 digest 和 expected revisions；后续命令携该 revision 时，服务端从命令本身重建相同 action/target/change 并比较，任一不符、确认过期或事实变化返回 412 `PRECONDITION_FAILED`。它只是预检证据，不持 lease，也不是业务 Operation。表级 replaceDataset/delete/changeSource 和生命周期专用预检保留各自入口，不能跨动作复用确认。

`RecordStatusBatchRequest.targets` 是列表选择后固定的完整引用/状态版本，接受时去重，不能为空，单请求最多1000行；`blockSize` 为1–100，默认100。重复身份带不同版本应422，不能静默挑一条。按冻结顺序分块，稳定块身份为 `(operationId,blockIndex)`。每块在同一短事务重新检查目标、状态目录、占用和所有行版本，更新、事件、块结果一起提交；一行冲突则整块不写，结果列出具体 blocker 引用。前一块完成不保证后一块成功；取消只在块开始前关闭后续块，不撤销已提交事实。Operation 查询在执行中也返回已有块结果；所有块成功才 succeeded，其余已知冲突/取消为 failed 并保留完整 outcome，error 分别为 `BATCH_STATUS_CONFLICT/BATCH_STATUS_CANCELLED`。未终态 outcome=processing；连续本地事务执行错误经有限重试仍失败时 outcome=failed，Operation.error.code=BATCH_STATUS_EXECUTION_FAILED，保留已经提交与尚未开始的块证据，不冒充状态冲突或取消。取消命令自身的成功仅表示后续块门闩已关闭，result 返回原操作的 operationId。客户端重连可从原 Operation.result 恢复每块已提交修订、冲突或未开始事实；禁止保存 filter 后后台重新求值更换目标。

工作流节点不会逐条调用这些公共管理 URL。核心通过注入的项目能力端口调用 `readProjectRecord/queryProjectRecords/createProjectRecord/writeRecordFields/setRecordStatus/writeRecordSlot/bindRecordEnvironment/addProjectField`；端口重用上述对象、CAS 与错误语义，但携带受验证的 Task capability，不接受 renderer 自称 Task 或 lease。对 Task 此前未持有的动态查询记录，取得动态 lease、校验全部 CAS、实际写入、变化事件、幂等结果和同步意图必须在同一个短事务中全成或全不成，失败不得留下 lease；已有 Task lease 的写也在同一短事务提交写入、修订、事件、结果与同步意图，外部推送另行执行。

### 3.4 Excel、导出与 Sheets 来源

2026-09-13 PM2 修订（confirmed，用户批准）：新建与替换路由分开；新建映射仅 new，替换允许显式已有 fieldId 或新增字段定义，不按显示名称猜测身份。检查结果补齐 issues、ignoredEmptyRowCount、identityCandidates；预览不替代全量检查。候选分段写入不可见，发布时同时检查代次、结构和预览后的相关修改证据；新代次状态全部 null。服务端不得只靠 tableRevision 检测记录修改。

文件选择由主进程验证 main frame 后通过 hostToken 内部登记，正文为 `{selectionToken,path,projectId,windowId,purpose,expiresAt}`；workspace/instance 由服务配置绑定。Renderer 仅持有受控令牌，公开 HTTP 不接收路径。主窗口另经受控 IPC 获取当前实例的窗口证明；内部登记使用 x-autoflow-file-window-token header，公开文件请求使用 x-autoflow-file-window-id 与 x-autoflow-file-window-token 并校验与原选择一致；不能把 windowId 仅作审计字段。选择/提交前可取消；接受后关闭视图不取消操作，通过原身份查询结果。导出先记录原目标与输出摘要，再无覆盖发布；reconcile 只核验既有事实，不另存或覆盖。

| Method / path | 包 | 请求 | 成功响应 | scope 与主要错误 |
|---|---|---|---|---|
| `POST /api/v1/projects/{projectId}/table-imports/excel/inspect` | PM2-B | header key；`{selectionToken}` | 200 `{operation,inspection:ExcelInspection}` | token 由 IPC 签发并在首次有效 inspect 时消费；422 文件格式。检查结果和受控文件句柄归属同一 inspection operation，可按原 key/operation 查询而不再次消费 token。 |
| `POST /api/v1/projects/{projectId}/table-imports/excel` | PM2-B | header key；`ExcelCreateTableRequest` | 202 `OperationAccepted` | 新表与完整数据集原子发布；不预建空壳。 |
| `POST /api/v1/projects/{projectId}/tables/{tableId}/imports/excel` | PM2-B | header key；`ExcelImportRequest` | 202 `OperationAccepted` | 只引用同项目未过期 inspection；重新核验受控句柄、指纹、工作表、影响、generation 和 lease 后原子发布，不再次提交或消费 selectionToken。 |
| `POST /api/v1/projects/{projectId}/tables/{tableId}/exports/xlsx` | PM2-C | header key；`ExportRequest` | 202 `OperationAccepted` | 输出目标只用 `selectionToken`；不接受 path。result=`ExportResult`。 |
| `GET /api/v1/projects/{projectId}/sheets/connections` | PM6-A | — | `{items:SheetsConnection[]}` | project；不返回凭据。 |
| `POST /api/v1/projects/{projectId}/sheets/connections` | PM6-A | header key；`{accountLabel,authorizationToken}` | 202 `OperationAccepted` | authorizationToken 来自受控 OAuth/IPC 流，单次使用；凭据入系统存储。 |
| `DELETE /api/v1/projects/{projectId}/sheets/connections/{connectionId}` | PM6-C | header key；`{impactRevision,mode:'disconnect'|'forgetCredential'}` | 202 `OperationAccepted` | 未知发送先隔离/核验。 |
| `POST /api/v1/projects/{projectId}/tables/{tableId}/sheets/inspect` | PM6-A | header key；`{connectionId:string,spreadsheetId:string,sheetId:number,identityStrategy,mapping}` | 200 `SheetsInspection` | Google `sheetId` 按来源的 JSON 安全整数传输，不与字符串 spreadsheetId 混同；读取、身份、结构、重叠映射分别报告。 |
| `PUT /api/v1/projects/{projectId}/tables/{tableId}/sheets/binding` | PM6-A/C | header key；`SheetsBindingWrite` | 202 `OperationAccepted` | 首绑/改绑统一；412 impact/epoch；新代次不继承状态/关联。 |
| `DELETE /api/v1/projects/{projectId}/tables/{tableId}/sheets/binding` | PM6-C | header key；`{impactRevision,expectedTableRevision}` | 202 `OperationAccepted` | 保留本地副本与历史证据，表变 unconfigured。 |
| `GET /api/v1/projects/{projectId}/tables/{tableId}/sync` | PM6-B | — | `{summary:SyncSummary;binding?:SheetsBinding}` | table。 |
| `POST /api/v1/projects/{projectId}/tables/{tableId}/sync/pull` | PM6-B | header key；`{expectedTableRevision}` | 202 `OperationAccepted` | 不覆盖本地普通值；公式刷新推进内容版本。 |
| `POST /api/v1/projects/{projectId}/tables/{tableId}/sync/push` | PM6-B | header key；`{mode:'due'|'allPending',expectedBindingEpoch}` | 202 `OperationAccepted` | timeout→verifying/unknown，不盲发。 |
| `POST /api/v1/projects/{projectId}/tables/{tableId}/sync/pause` | PM6-C | header key；`{expectedBindingEpoch}` | 200 `{summary:SyncSummary}` | 在途发送仍登记结果。 |
| `POST /api/v1/projects/{projectId}/tables/{tableId}/sync/resume` | PM6-C | header key；`{expectedBindingEpoch}` | 200 `{summary:SyncSummary}` | 只恢复调度，不重发 unknown。 |
| `GET /api/v1/projects/{projectId}/tables/{tableId}/sync-operations` | PM6-B | `status,page,pageSize` | `Page<SyncOperation>` | table。 |
| `GET /api/v1/projects/{projectId}/tables/{tableId}/sync-operations/{syncOperationId}` | PM6-B | — | `SyncOperation` | table + operation。 |
| `POST /api/v1/projects/{projectId}/tables/{tableId}/sync-operations/{syncOperationId}/reconcile` | PM6-B | header key；`{expectedStatusRevision}` | 202 `OperationAccepted` | 核验原目标/epoch；不换目标重放。 |
| `POST /api/v1/projects/{projectId}/tables/{tableId}/sync-operations/{syncOperationId}/abandon` | PM6-C | header key；`{expectedStatusRevision,reason}` | 200 `SyncOperation` | 仅未发送意图可 abandon；已发送 unknown 只能隔离历史。 |

```ts
type ExcelInspection = {inspectionId:string;fingerprint:string;filename:string;sheets:{sheetId:string;name:string;rowCount:number;columns:{index:number;name:string;sample:ScalarValue[]}[]}[];expiresAt:string}
type ExcelMapping = {columnIndex:number;target:{kind:'existing';fieldId:string}|{kind:'new';definition:FieldWrite}}
type ExcelIdentity = {mode:'system'}|{mode:'column';columnIndex:number}
type ExcelCreateTableRequest = {name:string;description:string;inspectionId:string;fingerprint:string;sheetId:string;mapping:ExcelMapping[];identity:ExcelIdentity}
type ExcelImportRequest = {inspectionId:string;fingerprint:string;sheetId:string;mapping:ExcelMapping[];identity:ExcelIdentity;impactRevision:number;expectedDatasetGeneration:string;expectedTableRevision:number}
type ExportRequest = {datasetGeneration:string;selectionToken:string;scope:'all'|'filter';filter?:FilterExpression;fieldIds:string[];includeStatus:boolean}
type ExportResult = {filename:string;saved:true;recordCount:number}
type SheetsConnection = {connectionId:string;accountLabel:string;credentialState:'available'|'missing'|'invalid';readable:boolean;writable:boolean;updatedAt:string}
type SheetsBinding = {connectionId:string;spreadsheetId:string;sheetId:number;bindingEpoch:number;identityStrategy:{kind:'column'|'system';columnId?:string};mapping:{fieldId:string;columnId:string;direction:'read'|'write'|'both';formula:boolean}[];syncPaused:boolean}
type SheetsInspection = {valid:boolean;issues:{code:string;message:string;columnId?:string}[];columns:{columnId:string;name:string;formula:boolean}[];identitySummary:{unique:boolean;missing:number;duplicates:number};overlaps:{projectId:string;tableId:string;columnIds:string[]}[]}
type SheetsBindingWrite = {connectionId:string;spreadsheetId:string;sheetId:number;identityStrategy:SheetsBinding['identityStrategy'];mapping:SheetsBinding['mapping'];impactRevision:number;expectedTableRevision:number;expectedBindingEpoch?:number}
```

### 3.5 批次、任务、人工与统计

| Method / path | 包 | 请求 | 成功响应 | scope 与主要错误 |
|---|---|---|---|---|
| `POST /api/v1/projects/{projectId}/automations/{automationId}/batches` | PM3-B | header key；`BatchStartRequest` | 202 `OperationAccepted`，result 最终为 `{batch:Batch}` | active project；422 runnable/input/resource；429 capacity。key 是 `startOperationId` 的来源。 |
| `GET /api/v1/projects/{projectId}/batches` | PM3-C | `automationId,status,startedFrom,startedTo,page,pageSize,sort` | `Page<Batch>` | project。 |
| `GET /api/v1/projects/{projectId}/batches/{batchId}` | PM3-C | — | `BatchDetail` | project + batch。 |
| `POST /api/v1/projects/{projectId}/batches/{batchId}/stop` | PM3-C/PM8 | header key；`{expectedStatusRevision,reason}` | 202 `OperationAccepted` | 关闭领取并扇出核心 cancel；接受不等于已停止。 |
| `POST /api/v1/projects/{projectId}/batches/{batchId}/force-stop` | PM3-C（PM8-B 复用） | header key；`{expectedStatusRevision,reason}` | 202 `OperationAccepted` | 首次随批次停止闭环交付；显式影响，未知实例隔离。 |
| `GET /api/v1/projects/{projectId}/tasks` | PM3-C→PM7 | `batchId,automationId,status,attention,endedFrom,endedTo,page,pageSize,sort` | `Page<Task>` | project。 |
| `GET /api/v1/projects/{projectId}/tasks/{taskId}` | PM3-C→PM7-A | — | `TaskDetail` | project + task；聚合核心快照，不复制核心状态。 |
| `GET /api/v1/projects/{projectId}/tasks/{taskId}/node-attempts` | PM3-C→PM7-A | `page,pageSize` | `Page<NodeAttempt>` | pageSize 默认 50、上限 200；从核心 C07 `listRunAttempts` 持久历史续读。 |
| `GET /api/v1/projects/{projectId}/tasks/{taskId}/logs` | PM3-C→PM7-A | `afterSequence?,level?,nodeId?,pageSize` | `RunLogPage` | pageSize 默认 50、上限 200；从核心持久日志补读。缺少所需历史/replay 为明确能力未完成或 `RUN_EVENT_HISTORY_UNAVAILABLE`，不能用 snapshot 跳过日志。 |
| `GET /api/v1/projects/{projectId}/tasks/{taskId}/outputs` | PM7-A | `page,pageSize` | `Page<RunOutput>` | project + task。 |
| `POST /api/v1/projects/{projectId}/tasks/{taskId}/follow-up-batches` | PM7-C | header key；`{mode:'originalInputGroup',expectedTaskStatusRevision,parameterOverrides}` | 202 `OperationAccepted` | 创建新 Batch；以选定失败 Task 的每个原 `RecordRef` 候选及原输入组关系为固定候选重新验当前条件/代次/占用，不换行、不重新配对、不重放网页；候选不再有效时可少建或不建 Task，数量不保证等于选中数。 |
| `GET /api/v1/projects/{projectId}/manual-items` | PM5-C | `status,page,pageSize,sort` | `Page<ManualItem>` | project。 |
| `GET /api/v1/projects/{projectId}/manual-items/{manualItemId}` | PM5-C | — | `{item:ManualItem;task:TaskDetail;instance:EnvironmentInstance}` | project；人工操作的是同 Run 的现场，不把持久来源当现场。 |
| `POST /api/v1/projects/{projectId}/manual-items/{manualItemId}/resume` | PM5-C | header key；`{checkpointRevision,targetNodeId,inputs:Record<string,JsonScalar>,expectedStatusRevision}` | 202 `OperationAccepted` | 核心校验合法位置；409 TTL/取消竞争。 |
| `POST /api/v1/projects/{projectId}/manual-items/{manualItemId}/finish` | PM5-C | header key；`ManualFinishRequest` | 202 `OperationAccepted` | 核心拥有 Run 终态；保存并结束进入 `finishing` 并复用 End，保存/关联完成前不得成功。 |
| `GET /api/v1/projects/{projectId}/statistics` | PM7-B | `from,to,timezone,automationId?,tableId?,interval=day|week|month` | `ProjectStatistics` | 按 Task 完成时间；非法时区/范围 422。 |
| `GET /api/v1/projects/{projectId}/statistics/{resultSetId}/tasks` | PM7-B | `result,intervalStart?,page,pageSize` | `Page<Task>` | 只读同一统计结果集合；过期 410 `STATISTICS_RESULT_EXPIRED`。 |

```ts
type BatchStartRequest = {expectedAutomationRevision:number;parameters:Record<string,JsonScalar>;maxTasks?:number;concurrency?:number;environmentOverride?:EnvironmentPolicy}
type BatchDetail = {batch:Batch;statusCounts:Record<TaskStatus,number>;taskCount:number;stopOperation:Operation|null}
type RunLogEntry = {runId:string;sequence:number;eventId:string;executionGeneration:number;nodeVisitId?:string;attempt?:number;level:'debug'|'info'|'warning'|'error';message:string;occurredAt:string}
type RunLogPage = {items:RunLogEntry[];afterSequence:number;lastSequence:number;hasMore:boolean}
type ManualFinishRequest = {expectedCheckpointRevision:number;expectedStatusRevision:number;outcome:'succeeded'|'failed';reason:string;retainEnvironment:{enabled:false}|{enabled:true;mode:'update'|'saveAs';targetEnvironmentId?:string;name?:string;recordTargets:{recordRef:RecordRef;expectedLinkRevision:number;replaceAllowed:boolean}[]}}
type ProjectStatistics = {from:string;to:string;timezone:string;sample:{succeeded:number;failed:number;cancelled:number;timed_out:number;interrupted:number};successRate?:number;averageDurationMs?:number;trend:{bucketStart:string;succeeded:number;failed:number;cancelled:number;timed_out:number;interrupted:number;averageDurationMs?:number}[];resultSetId:string;calculatedAt:string;expiresAt:string}
```

人工继续接受后人工项进入 `resume_requested`、Run 进入 `resume_queued`，但人工期限继续有效；只有恢复真正开始的 CAS 胜出后，人工项才进入 `resolved` 且 Run 回到 `running`。在此之前 TTL、现场丢失、人工结束或停止仍可撤销尚未开始的继续请求，竞争只允许一个转换胜出。

成功率只以 succeeded+failed 为分母；`timed_out` 与 cancelled/interrupted 分列且不进入成功率分母，分母为 0 时 `successRate` 省略。耗时含人工和重试、不含启动前排队；无有效样本时 `averageDurationMs` 省略。上述统计下钻路由返回该 `resultSetId` 固定结果集合的 `Page<Task>`；`expiresAt` 后或结果已淘汰返回 410 `STATISTICS_RESULT_EXPIRED`，不得静默改查实时数据。

### 3.6 环境、保存与清理

| Method / path | 包 | 请求 | 成功响应 | scope 与主要错误 |
|---|---|---|---|---|
| `GET /api/v1/projects/{projectId}/environments` | PM5-A | `state,q,page,pageSize,sort` | `Page<Environment>` | project。 |
| `GET /api/v1/projects/{projectId}/environments/{environmentId}` | PM5-A | — | `{environment:Environment;activeInstance:EnvironmentInstance|null}` | project；持久来源状态与现场 instance 状态分开；历史 task 可保留 deleted 摘要而非可编辑对象。 |
| `GET /api/v1/projects/{projectId}/environment-instances` | PM3-C→PM5-A | `state,taskId,page,pageSize,sort` | `Page<EnvironmentInstance>` | 活动、等待人工、临时和维护现场；未保存现场允许 `environmentId=null`。 |
| `GET /api/v1/projects/{projectId}/environment-instances/{instanceId}` | PM3-C→PM5-A | — | `EnvironmentInstance` | project + instance；现场操作继续通过所属 Task 或 Operation 命令，不新增第二套控制端点。 |
| `PATCH /api/v1/projects/{projectId}/environments/{environmentId}` | PM5-A | header key；`{name,expectedMetadataRevision}` | 200 `Environment` | 409 metadata revision。 |
| `POST /api/v1/projects/{projectId}/environments/{environmentId}/maintenance` | PM5-B | header key；`{expectedContentGeneration}` | 202 `OperationAccepted` | 仅 `ready` 持久来源可预约；423 已占用。result 含独立 `EnvironmentInstance`，不把 starting/active 等现场状态保存到 Environment，也不含目录路径。 |
| `POST /api/v1/projects/{projectId}/environments/{environmentId}/maintenance/save` | PM5-B | header key；`{maintenanceOperationId,mode:'update'|'saveAs',name?,expectedContentGeneration}` | 202 `OperationAccepted` | 发布新 contentGeneration；超时查询同 operation。 |
| `POST /api/v1/projects/{projectId}/environments/{environmentId}/maintenance/discard` | PM5-B | header key；`{maintenanceOperationId}` | 202 `OperationAccepted` | 清理可查询；不发布工作副本。 |
| `GET /api/v1/projects/{projectId}/environments/{environmentId}/impact` | PM8-A | `action=delete` | `{impactRevision,impacts,blockers}` | 自动化固定选择、记录关联、活动/未知/保存/清理。 |
| `DELETE /api/v1/projects/{projectId}/environments/{environmentId}` | PM8-A | header key；`{impactRevision,expectedMetadataRevision,expectedContentGeneration}` | 202 `OperationAccepted` | 活动/未知/待发布阻止；历史 Task 不永久阻止。 |
| `GET /api/v1/projects/{projectId}/environment-operations/{operationId}` | PM5-B | — | `EnvironmentOperationView` | project + operation。 |
| `POST /api/v1/projects/{projectId}/environment-operations/{operationId}/reconcile` | PM5-B/PM8-B | header key；`{expectedStatusRevision}` | 202 `OperationAccepted` | 只核验同一保存/清理。 |
| `POST /api/v1/projects/{projectId}/environment-operations/{endOperationId}/repair-associations` | PM5-B | header key；`EndAssociationRepair` | 202 `OperationAccepted` | `saved_unlinked` 才允许；新写权/版本；不重跑/重存/改历史 Run。 |

```ts
type EnvironmentOutcome = {phase:'reserved'|'copying'|'open'|'closed_candidate'|'publishing'|'saved_unlinked'|'associating'|'completed'|'cleanup'|'unknown';instance:EnvironmentInstance|null;source:EnvironmentRef|null;saved:EnvironmentRef|null;targets:RecordRef[];conflicts:{record:RecordRef;expectedLinkRevision:number;currentLinkRevision:number}[]}
type EnvironmentOperationView = {operation:Operation;outcome:EnvironmentOutcome|null}
type EndAssociationRepair = {targets:{record:RecordRef;expectedLinkRevision:number;replace:boolean}[];disposition:'repair'|'acceptPartial';expectedStatusRevision:number}
```

End 正常保留由核心 `finalizeEnd` 窄端口发起，不公开另一个 renderer “保存 End”端点。端口请求固定 `endOperationId`、原定业务结果、来源 instance、保存模式、目标环境/预期 generation、去重 RecordRef、各自 linkRevision 和替换授权；项目环境/数据协调返回完整或 `saved_unlinked`，核心据此唯一终结 Run。

### 3.7 项目操作查询

| Method / path | 包 | 请求 | 成功响应 | scope 与主要错误 |
|---|---|---|---|---|
| `GET /api/v1/projects/{projectId}/operations` | 各首次命令包 | `kind?,status?,resourceType?,page,pageSize` | `Page<Operation>` | project。 |
| `GET /api/v1/projects/{projectId}/operations/{operationId}` | 各首次命令包 | — | `Operation` | project + operation；404。 |
| `GET /api/v1/projects/{projectId}/operations/by-idempotency-key/{idempotencyKey}` | PM1 起 | — | `Operation` | 同 project/key；404 表示从未接受，只有此时才可按原 key 重发。 |
| `POST /api/v1/projects/{projectId}/operations/{operationId}/reconcile` | 有外部/文件结果包 | header key；`{expectedStatusRevision}` | 202 `OperationAccepted` | 仅 kind 声明支持 reconcile；不会执行新的业务动作。 |
| `GET /api/v1/workspace/operations/by-idempotency-key/{idempotencyKey}` | PM1-A | — | `Operation` | 仅 workspace 作用域 `createProject` 找回；404 表示从未接受。 |
| `GET /api/v1/projects/{projectId}/events` | PM3-C | `afterEventId?` + `Accept: text/event-stream` | `ProjectEvent` stream | 项目聚合失效通知；Run 历史仍来自 core C07。 |

创建项目在接受前没有 projectId，故使用 workspace 级路由找回 `createProject`；其他操作仍走项目作用域查询。按 key 的 GET 只用路径给出的 scope + key 查询，不接收也不比较 request digest；只有客户端重发原命令时，服务端才把该命令的规范 digest 与已存 digest 比较并拒绝不同载荷。

`OperationKind` 是如下封闭联合，但 OpenAPI 枚举项只随真实 handler 增量加入，不能先生成全量空命令框架：

```ts
type OperationKind = 'createProject'|'updateProject'|'archiveProject'|'restoreProject'|'deleteProject'|'createAutomation'|'updateAutomation'|'deleteAutomation'|'createTable'|'updateTable'|'deleteTable'|'mutateField'|'mutateStatus'|'createRecord'|'updateRecord'|'setRecordStatus'|'setRecordStatuses'|'cancelRecordStatuses'|'writeRecordSlot'|'bindRecordEnvironment'|'deleteRecord'|'inspectExcel'|'importExcel'|'exportXlsx'|'connectSheets'|'disconnectSheets'|'inspectSheets'|'changeSheetsBinding'|'removeSheetsBinding'|'syncPull'|'syncPush'|'pauseSync'|'resumeSync'|'reconcileSync'|'abandonSync'|'startBatch'|'stopBatch'|'forceStopBatch'|'createFollowUpBatch'|'resumeManual'|'finishManual'|'updateEnvironment'|'startMaintenance'|'saveEnvironment'|'discardEnvironment'|'deleteEnvironment'|'reconcileEnvironment'|'repairEndAssociation'|'reconcileOperation'|'cleanup'
```

每个实际加入 OpenAPI 的 `OperationKind` 必须同时定义其命令 DTO、终态 result DTO、允许的 `resource` 分支、可产生的错误 code 和是否支持 reconcile；缺任一项不得加入枚举。路由到 kind 的固定映射为：项目/自动化/表/字段/状态/记录 CRUD 分别使用同名 create/update/delete 或 `mutateField/mutateStatus`；后两者规范请求另固定 `action:create|update|delete`，不能跨动作复用同 key。记录状态单条/批量/取消后续块、槽、环境关联分别为 `setRecordStatus/setRecordStatuses/cancelRecordStatuses/writeRecordSlot/bindRecordEnvironment`；Excel 三命令为 `inspectExcel/importExcel/exportXlsx`；Sheets 连接、删除连接、检查来源、绑定、移除绑定为 `connectSheets/disconnectSheets/inspectSheets/changeSheetsBinding/removeSheetsBinding`，sync pull/push/pause/resume/reconcile/abandon 分别为 `syncPull/syncPush/pauseSync/resumeSync/reconcileSync/abandonSync`；Batch start/stop/force-stop/follow-up 为 `startBatch/stopBatch/forceStopBatch/createFollowUpBatch`；人工 resume/finish 为 `resumeManual/finishManual`；环境 PATCH 为 `updateEnvironment`，maintenance/save/discard/delete/reconcile/repair 为 `startMaintenance/saveEnvironment/discardEnvironment/deleteEnvironment/reconcileEnvironment/repairEndAssociation`；通用 reconcile 为 `reconcileOperation`；`cleanup` 仅由 C16 内部协调器创建，可查询但没有 renderer 直接创建路由。GET、纯 impact/validation/批量状态 preview 与 `open` 不创建 Operation。

结果形状按以下表冻结；资源分支按路由目标/ResourceLocator 固定，不能把任意字典当结果。结果是操作提交时的事实快照，后续查询当前资源不会改写既有结果。Operation 非终态或 failed 时 result 可为 null，也可保留明确的部分事实；failed 必须 error 非 null，succeeded 必须给出该 kind 规定的 result 且 error=null。

| kind 组 | result |
|---|---|
| create/update Project，archiveProject/restoreProject | `Project` |
| create/update Automation | `Automation` |
| create/update Table | `DataTable` |
| importExcel | `{table:DataTable,importedRecordCount,previousDatasetGeneration?}`；新表接受时resource为project，发布成功后才变为table。 |
| create/update Record，setRecordStatus/writeRecordSlot/bindRecordEnvironment | `DataRecord` |
| deleteProject/deleteAutomation/deleteTable/deleteRecord | `{target:ResourceLocator,deleted:true}`；已确认残留另记 cleanup，不冒充外部文件已删除 |
| mutateField | create/update：`{action,field:FieldDefinition,tableRevision}`；delete：`{action:'delete',target:FieldRef,deleted:true,tableRevision}` |
| mutateStatus | create/update：`{action,status:StatusDefinition,tableRevision}`；delete：`{action:'delete',statusId,deleted:true,tableRevision}` |
| setRecordStatuses / cancelRecordStatuses | `RecordStatusBatchOutcome` / `{operationId,subsequentBlocksClosed:true}` |
| inspectExcel / exportXlsx / inspectSheets | `ExcelInspection` / `ExportResult` / `SheetsInspection` |
| connectSheets / disconnectSheets | `SheetsConnection` / `{connectionId,mode,disconnected:true}`；mode 与原命令相同 |
| changeSheetsBinding / removeSheetsBinding | `SheetsBinding` / `{table:DataTable,unbound:true}` |
| syncPull / syncPush | `{tableId,summary:SyncSummary}`；未知发送先核验，不以已入队宣称完整同步成功 |
| pauseSync / resumeSync | `{summary:SyncSummary}` |
| reconcileSync / abandonSync | `SyncOperation` |
| startBatch/stopBatch/forceStopBatch/createFollowUpBatch | `{batch:Batch}`；start/follow-up 成功指批次已创建，Run 是否成功仍单独查询 |
| resumeManual / finishManual | `{item:ManualItem,run:CoreRun}`；resume 接受仅202，真正开始或明确结束后才记完成 |
| updateEnvironment | `Environment` |
| startMaintenance/saveEnvironment/discardEnvironment/deleteEnvironment/reconcileEnvironment/repairEndAssociation | `EnvironmentOutcome`；维护启动成功必须含非空 instance |
| reconcileOperation | `{targetOperationId,status:OperationStatus}`；核对原操作，禁止递归包含自身 |
| cleanup | `CleanupSummary` |

本地纯事务命令不支持外部 reconcile；原 key 查询即可。文件导入/导出、Sheets 连接/绑定/同步、环境/清理和停止协调支持核验既有事实。通用 reconcile 仅路由到这些 kind 的已有核验策略；不为不支持者猜测重试。

## 4. 核心 Run：唯一所有者与窄端口

项目管理不提供 `/projects/.../runs` 的创建、派发或状态修改端点，也不新增第二套执行事件。Studio/core 是 `CoreRun`、节点 attempt、日志、输出、checkpoint 和终态的唯一所有者。项目侧仅持久保存 `Task.runId/runRequestId/inputSnapshotId` 并通过进程内应用端口消费：

| 端口 | 调用与事务 | 输入 | 输出/拒绝 |
|---|---|---|---|
| `prepareContent` | 项目启动前调用 core | `workflowId,workflowRevision,entrypoint,dependencyRefs,availableCapabilities,prepareOperationId` | `preparedContentId`、内容摘要、固定依赖 revisions、入口和所需能力；缺文档/依赖明确拒绝。 |
| `prepareRun` | **加入调用方已有 UoW，不提交事务** | `runRequestId,preparedContentId,parameters,inputSnapshotRef|null,resourceRequest,capabilityBindings,uow` | 同身份唯一的 queued `CoreRun`；在同一短事务与 Task、输入快照、lease、环境预约提交。不得 HTTP 自调用。 |
| `dispatchRun` | 上述事务提交后 | `runId,expectedStatusRevision,executionGeneration` | 接受派发或当前状态；派发前重新检查取消/撤权。 |
| `queryRun` | 任意恢复/查询 | `runId` 或 `runRequestId` | 权威 `CoreRun`；`getRunSnapshot(runId)` 才返回 `RunSnapshot`。 |
| `cancelRun/forceStop`（runtime 适配器可命名 `forceStopRun`） | Batch 扇出；各有 operationId | run 身份、期望 generation/statusRevision、原因 | 命令接受结果；资源停止需继续查询。 |
| `validateResume/resumeRun/finishManual` | 人工协调 | run/checkpoint/target/输入/operation 身份 | 合法缺项或同 Run 的唯一转换；TTL/停止竞争只一方成功。 |
| `finalizeEnd/queryEnd` | 核心调用项目 capability | 固定 End 保存与关联请求 | `completed/saved_unlinked/failed/unknown`；Run 终态仍由 core 决定。 |

```ts
type RunSnapshot = {run:CoreRun;nodeAttempts:Preview<NodeAttempt>;outputs:Preview<RunOutput>;checkpoint?:{revision:number;nodeId:string;createdAt:string};lastSequence:number;capturedAt:string}
```

未来核心 HTTP 路由由 Studio 所有者在其命名空间定义并进入统一 OpenAPI；PM0 只冻结项目消费所需的逻辑能力，不虚构当前已有路径。若 Studio 最终公开路由，项目查询 adapter 调用同进程应用服务/端口，不通过 loopback HTTP 调自己。核心迁移（Run、attempt、event、artifact）必须先于引用它的 `pm04_project_runs` 外键迁移。

## 5. Run 事件、sequence 与重连

§3.7 的项目变化流只用于项目聚合通知，`afterEventId?` 不充当 Run sequence。事件 envelope：

```ts
type ProjectEvent = {eventId:string;projectId:string;kind:'projectChanged'|'automationChanged'|'tableChanged'|'recordChanged'|'batchChanged'|'taskChanged'|'environmentChanged'|'syncChanged'|'operationChanged';resource:ResourceLocator;resourceRevision:number;occurredAt:string}
type RunEvent = {eventId:string;runId:string;sequence:number;executionGeneration:number;kind:'runStatus'|'nodeAttempt'|'log'|'output'|'checkpoint';nodeVisitId?:string;attempt?:number;occurredAt:string;payload:JsonValue}
```

项目事件只使查询缓存失效，不携带完整业务对象。Run 事件来自核心唯一事件源，至少含 `runId`、单 Run 单调 `sequence`、`eventId`、`executionGeneration`、节点访问/attempt 身份和提交时间。sequence 在核心持久提交时分配；消费者以 `(runId,sequence)` 去重，旧 generation 或 `sequence <= appliedSequence` 不覆盖当前事实。

客户端持久保留自己的 `lastSeenSequence`。发现 `sequence > lastSeenSequence + 1`、断线、SSE 410 或终态后收到迟到事件时，暂停应用该 Run 的增量，先从核心持久事件接口以 `afterSequence=lastSeenSequence` 补齐历史日志/事件并按 `(runId,sequence)` 去重，再用 `getRunSnapshot` 返回的 `RunSnapshot` 核对状态投影与服务端 `lastSequence`。snapshot 只恢复权威状态投影，不能把客户端游标直接跳到 snapshot 的 `lastSequence` 而丢弃中间日志；核心没有 replay 时该能力未完成，必须明确报历史不可用，不能以 snapshot fallback 宣称完整重连。收到终态后仍以权威快照确认一次；终态只接受一次，迟到事件只能作为诊断证据。页面首次打开按约定起点读历史并查询快照后再订阅，不能假设事件早于订阅会重放。传输 `occurredAt` 对应领域事件的 `committedAt`，均指持久提交时刻，不使用客户端接收时间代替。

当前仓库内核 SSE 并未实现以上持久 sequence、缺口补读和终态保证。实现者必须先在 Studio/core 中提供持久快照/事件能力并做断线、重复、乱序、缺口、迟到终态测试，之后项目 UI 才能声称实时 Run 恢复；不可借用内核下载 SSE 的行为作能力证明。

## 6. Desktop 文件与 Studio IPC

桌面共享契约沿用现有 `DesktopResult<T> = {ok:true,value:T}|{ok:false,error:{code,message}}`；用户取消文件对话框使用成功分支的 `value=null`，不是错误。planned `project-files.ts`：

```ts
type DesktopResult<T> = {ok:true;value:T}|{ok:false;error:{code:string;message:string}}
type FileSelection = {selectionToken:string;displayName:string;kind:'excelInput'|'xlsxOutput';expiresAt:string}
type ProjectFileBridge = {
  chooseExcelInput(projectId:string): Promise<DesktopResult<FileSelection|null>>
  chooseXlsxOutput(projectId:string,suggestedName:string): Promise<DesktopResult<FileSelection|null>>
}
type OpenStudioRequest = {workflowId:string;projectContext?:{projectId:string;automationId:string;managementRevision:number}}
type AutomationStudioBridge = {
  openAutomationStudio(request:OpenStudioRequest): Promise<DesktopResult<{opened:true;workflowId:string}>>
}
```

main 进程校验调用窗口/主 frame、projectId、扩展名和对话框结果，保存规范化绝对路径于内存受控 token 表；renderer 和公开 HTTP 永远只得到 token、显示名和到期时间。token 绑定窗口、工作区、projectId、用途、允许读/写动作并单次兑换：Excel inspect 首次兑换后，由同一 inspection operation 持有受控文件句柄供后续 commit 复验，重查 inspect 或 commit 不重复消耗 token；输出 token 则由一次导出操作兑换。过期、跨窗口、跨项目、用途错误或首次兑换后的另一操作复用分别返回稳定 Desktop/HTTP 错误。sidecar 经 host-only 通道兑换 token，验证真实路径/符号链接/文件指纹后操作；不接受 renderer 提供任意路径，也不让 renderer 指定“渲染/打开”的路径。

现有 `openAutomationStudio()` 无参数且共享类型返回 `Promise<void>`，属于已提交 Studio M1；集成时由 Studio 所有者扩展为上述受控请求并保持单窗口/离开确认规则。这里不修改其文件。打开 Studio 不启动 Run；关闭 Studio 不停止 Run。

## 7. 迁移、OpenAPI 与交付顺序

交付前重新静态核对：主目录b2e95b3的已提交迁移 head 已为 `0005_workflow_documents`，从 `0004_proxy_remote_controls` 派生。原“WIP0005”描述只保留在历史观察中。项目迁移不得改写既有迁移：

1. 集成人先核对实际 Alembic heads；按当前主线先对齐b2e95b3后从 `0005` 建立PM1迁移。若其他隔离分支此前已从 `0004` 派生，合入时由集成人创建明确 merge migration；不能假填依赖或改写任一历史迁移。PM1不等待核心Run执行能力。
2. `pm01_projects`、`pm02_project_data`、`pm03_project_automations` 按真实外键依赖递进。
3. Studio/core 的 Run/attempt/event/artifact 迁移先提交；`pm04_project_runs` 随后引用核心 Run。若形成两个 head，只有集成人创建 merge migration。
4. `pm05_environments`、`pm06_project_sync` 只在对应真实持久事实 handler 同包加入。旧迁移不可修改；升级/降级、空库与 0004/0005 起点都要测试。

每阶段先实现领域/用例/仓储和真实 handler，再为该 handler 增加 Pydantic DTO 与错误响应，最后由主集成人运行 `npm run openapi:generate` 更新唯一 `apps/desktop/src/renderer/shared/api/generated.ts`。禁止先加入全量 DTO、空路由、501 placeholder、第二份 contracts 包或手写前端服务端状态类型。生成后的每个客户端调用必须来自真实 OpenAPI operation；`npm run openapi:check`、后端 contract tests、TypeScript 类型检查与实际页面联调同包通过。

## 8. 静态验收清单

- 路由表中每个 method/path 组合唯一；父路径归属均需重新校验。
- 每个请求、响应、列表、事件、operation result 和错误 details 引用的类型在本文、[contracts.md](contracts.md)或核心 `WorkflowDocument` 契约中定义。
- 所有持久命令有 UUID `Idempotency-Key`、操作查询和首次响应丢失恢复；202 未写成成功。
- 项目没有第二套 Run 创建/派发/终态/事件体系；`prepareRun` 明确参加共享 UoW、不自提交、不 HTTP 自调用。
- Run 事件写明快照、单调 sequence、去重、缺口、断线补读和终态；当前能力缺口明确标记。
- 文件 IPC 使用 `DesktopResult<FileSelection|null>` 和受控 token；取消为成功 null，错误为失败分支；无任意路径或 renderer 选定执行路径。
- 迁移以实际 head 为准，核心外键依赖先行；OpenAPI DTO 与真实 handler 同阶段产生。

## PM1已批准勘误（2026-09-13）

用户批准PM1：Summary数量可省略，Overview/Summary共用六键能力状态，未知不补零。POST省略defaultResources由服务端建立profileId=null/proxy.mode=sourceDefault/modelProviderId=null，显式提供仍完整验证保存；PATCH省略保留。PM1实际仅createProject/updateProject及查询，不开放归档/恢复/删除，组件归属按PM1执行卡细化。上述修订不改数据、运行或环境规则；PM0报告仍为当时事实。

## PM2 实施勘误（2026-09-13）

PM0历史报告不回写。PM2新增表身份策略、写入值形状、Excel创建/替换路由分离、显式映射目标、inspect操作结果及受控文件授权的实施补充，以[PM2执行卡](../../superpowers/plans/2026-09-13-project-management-pm2.md)的“实施契约补充”为准；原正文相冲突的请求形状为superseded。未改变数据复用、独立修订、原子发布和结果未知查询的业务规则。真实OpenAPI随handler交付生成。


### PM2 实际文件操作补充（2026-09-13，实施中）

- `POST /api/v1/projects/{projectId}/tables/{tableId}/imports/excel/impact` 返回 `ExcelReplaceImpact`：目标表、记录数、阻断原因、期望代次/表修订及 impactRevision。提交和最终发布均重新核对该确认与相关 DataChange 事实；一般表修订不替代记录/状态变更证据。
- 当前 importExcel result 统一为 `{table,importedRecordCount,previousDatasetGeneration?}`；create/replace均202接受，终态从原Operation查询。
- 新表数据先保存为 `published=false` 的内部候选，目录和所有公开表读取/编辑均排除。候选表名使用内部唯一占位，不占用用户名称；发布短事务验证并写入规范名称。重新导入的候选代次不成为当前代次，最终只切换当前指向，不逐行复制大量记录。
- 中断的检查/未发布导入会收敛原Operation为明确失败，保留旧表；启动恢复不自动读取旧来源文件。已经发布的导出仅核验原目标与发布前摘要。
- reconcileOperation 的处理中 result 可附 expectedTargetRevision，固定目标并支持重启恢复；终态 result 为 `{targetOperationId,status}`，原导出Operation仍是文件结果权威。

#### PM2 来源展示补充（2026-09-13，已实现）

`DataTableView.source` 可选，兼容已有历史 Operation 快照；本次表查询和新结果返回 `kind`，Excel 表另含 `filename`、`sheetName`、`importedAt`。这些字段来自当前数据代次，不公开文件路径、授权、内部工作表 ID 或指纹。导入原子发布同时保存一条唯一 `DataChange`，重发不重复记账。

新的导入命令必须仍持有当前工作区、当前服务实例的检查授权；重启后的旧检查快照可查询，但不能授权新的文件读取。已接受同键同请求先找回原 Operation，不重新验证旧令牌或读取文件。

## R3 原子字段草稿与状态引用：实际接口（2026-09-14，confirmed）

本节记录当前实现，保留以上 PM0 历史契约及 PM2 事实；冲突的早期请求形状不用于调用本节接口。来源：`adapters/http/project_data_schema.py`、`project_data_schema_schemas.py`、`project_data.py`、`project_data_catalog_schemas.py`、`project_schemas.py`，以及对应 application/domain/database 实现和真实 contract/integration 测试。OpenAPI 生成类型仍为桌面唯一 HTTP 类型来源。

### 路由与请求

统一前缀 `/api/v1/projects/{projectId}/tables/{tableId}`；路径 ID、候选 generation/fieldId/clientId 和提交幂等键均使用规范小写 UUID。

| 方法与后缀 | 请求 | 响应与权限 |
|---|---|---|
| `POST /schema/preview` | `DataSchemaCandidate`，不要求 Idempotency-Key | `200 DataSchemaImpact`；活动项目可预检。保存预览证据，不修改业务字段或记录，不产生成功 Operation。 |
| `POST /schema` | `DataSchemaCommit` 与 UUID `Idempotency-Key` | 首次成功与同请求重放均 `200 DataSchemaResult`；新提交要求活动项目，同键历史成功允许归档后找回。 |
| `GET /statuses/usage` | 无请求体 | `200 DataStatusUsageDirectory`；归档可读。查询失败保持错误，不返回合成零值。 |

三个路由使用现有认证、项目归属检查及应用 quiesce 门闩。新写入在归档时返回 `409 LIFECYCLE_CONFLICT`，closing 时为 `423 PROJECT_CLOSING`；不存在或已删除项目为 `404 PROJECT_NOT_FOUND`，非所属表为 `404 TABLE_NOT_FOUND`。旧 `DataFieldCreate/Patch` 与 `mutateField` 端点继续保留。

```ts
type DataSchemaCandidate = {
  datasetGeneration: string
  expectedTableRevision: number
  fields: Array<
    {kind:'existing'; fieldId:string; expectedFieldRevision:number; definition:DataFieldWrite}
    | {kind:'new'; clientId:string; definition:DataFieldWrite;
       sourceColumnPolicy:'localOnly'; existingRecordDefault?:Scalar}
  >
}
type DataSchemaCommit = {candidate:DataSchemaCandidate; impactRevision:number}
type DataSchemaIssue = {
  code:string; fieldId:string|null; clientId:string|null
  message:string; affectedRecords:number|null
}
type DataSchemaImpact = {
  impactRevision:number; calculatedAt:string; expiresAt:string
  affectedRecords:number; backfillBytes:number
  blockers:DataSchemaIssue[]; warnings:DataSchemaIssue[]
  referenceAvailability:{automations:'notImplemented'; sync:'notImplemented'}
}
type DataSchemaResult = {
  action:'saveSchema'; datasetGeneration:string; tableRevision:number
  fields:DataFieldView[]; createdFieldIds:Record<string,string>; backfilledRecords:number
}
```

这里 `DataFieldWrite`、`DataFieldView`、`Scalar`、`Revision` 直接复用现有 catalog HTTP schema：definition 恰为 `key/name/type/required/validation`；type 为 `string|number|boolean|date`。Scalar 保留 string、number、boolean、DateScalar、null 的真实类型；DateScalar 的 `offset` 可为 null，但不可省略。修订为 1 至 9007199254740991 的严格整数。领域不反向导入 HTTP DTO，使用已有 `validate_field/validate_value` 和纯 candidate 校验。

候选必须包含当前代次每个已有 fieldId 且恰好一次，新 clientId 互异，规范字段 key 不重复。已有 key 不能改变；公式或不可写字段的 definition 整体不变；身份字段只保护 type，其他合法属性沿用旧字段规则。本接口不支持字段删除或来源映射变更。`fields:[]` 对当前空表合法，缺少 fields 属性不合法。

HTTP 使用 `model_dump(by_alias=True, exclude_unset=True)` 保留默认值存在性。省略 `existingRecordDefault` 不回填；显式 null 是真实默认值，仅允许非必填字段；false、0、空串不互相转换。新增必填字段在存在记录且省略默认值时，预检产生 `EXISTING_RECORD_DEFAULT_REQUIRED` blocker；显式提交非法默认值则在值校验阶段返回 422。两者均不能提交业务变更。已有未修改规则的异常值原样保留，不重新执行旧正则或合成“已验证无异常”的声明。

### 预览证据、内部守卫与事务

`impactRevision` 是持久 `DataImpactRow.id`，不是记录变更修订。内部 action 为 `saveTableSchema`，target 绑定 project/table/generation，候选摘要使用排序 key、无额外空格、`ensure_ascii=False`、`allow_nan=False` 的 UTF-8 JSON。非有限数、孤立代理、类型强制转换均不能形成合法提交。

预览先在显式一致读事务读取表、字段、当前未删除记录和守卫，将记录写入可溢出到磁盘的 spool。释放读事务后只执行变更的 type/required/validation 校验及回填计算；字段值校验阶段有 **120 秒**时间预算，在每次字段验证前后及行处理边界检查。该预算不是整个 HTTP 请求的端到端超时。用户正则另保留既有单次执行限制。超时为 `422 FIELD_VALIDATION_TIMEOUT` 或既有 `PATTERN_VALIDATION_TIMEOUT`，不发布成功预览证据。

预览完成后用短 `BEGIN IMMEDIATE` 事务重验 generation、tableRevision、fieldRevision 集合及内部 guard，再保存证据。证据从保存时起 **10 分钟**有效；内部 prepared 的 clientId→fieldId 映射和有界回填行不返回公开 HTTP。预览证据本身不授权当前范围外的写入。

迁移 `pm02_schema_drafts` 从 `pm02_excel_exports` 接续，增加 `DataTableRow.schema_guard_revision`，初值 1。SQLite 触发器在当前代次记录 INSERT/UPDATE/DELETE 的同一事务推进它，保守包含状态/关联变化；UPDATE 同时考虑 NEW/OLD 范围，非当前隐藏代次不推进当前表守卫。它是独立的内部并发守卫，不新增公共通用版本，也不替代 content/status/linkRevision。迁移还增加 `(project_id,table_id,dataset_generation,status_id)` 查询索引。

默认回填上限为 **1000 条实际写入记录、4194304 字节**，两者同时满足；字节按每条记录写后完整 values JSON 的规范 UTF-8 编码计算，不只计算新增字段，多个字段回填同一条记录只计一次。超过任一上限形成 `SCHEMA_BACKFILL_LIMIT` blocker，整候选拒绝；无法原样形成严格 JSON 的旧值会形成 `SCHEMA_BACKFILL_INVALID_JSON`。提交仍重新检查内部 prepared 的预算及原内容修订。

提交使用单个 `BEGIN IMMEDIATE`：先检查项目读取归属并查原幂等键，比较包含 scope/target/candidate/impactRevision 的请求摘要与 kind；相同请求直接返回冻结结果，不用旧 revision 再作 CAS，不重新分配新字段 ID。不同请求为 `409 OPERATION_PAYLOAD_MISMATCH`。只有新操作继续检查 active、generation、table/field/guard 修订、预览绑定/用途/有效期及空 blockers；证据失效为 `409 IMPACT_STALE`，当前 revision 冲突为 `409 REVISION_CONFLICT`，代次替换为 `410 DATASET_GENERATION_GONE`。

字段、回填记录、DataChange 和 Operation 冻结结果在同一事务提交或回滚。每条回填记录 contentRevision 只加 1，status/linkRevision、typed recordKey、record_slots、状态和环境关联保持；实际变更字段 fieldRevision 加 1，新字段为 1。真实变更才推进 tableRevision，无变化允许记录成功 Operation 而不推进业务修订。Excel 来源文件与原来源映射不写入。

`ProjectOperationView.kind` 新增 `saveTableSchema`，result 新增 `DataSchemaResult`（action 为 `saveSchema`），resource 沿用 `{type:'table',projectId,tableId}`。响应丢失使用既有项目 `/operations/by-idempotency-key/{key}` 查询；不新增恢复 URL。桌面在发送前持久保存 candidate、impactRevision、key 及原作用域，未知时先查原请求，明确未接受后才允许原 key/原 body 重试，不能换 key 猜测成功。旧 Operation DTO 成员保持。

### 状态引用投影

```ts
type DataStatusUsageDirectory = {
  datasetGeneration:string; calculatedAt:string
  items:Array<{statusId:string; currentRecords:number; activeBatchOperations:number}>
  configurationReferences:{availability:'notImplemented'}
}
```

状态目录、分组计数和活动批引用在同一个显式读取事务内计算。currentRecords 只统计当前 project/table/generation 的未删除记录，null 状态不归入任一状态，已删除状态不在目录中。activeBatchOperations 统计未取消、Operation 为 accepted/running/reconciling 且仍有 notStarted 块的批操作；同时考虑目标状态以及冻结 typed recordRef 对应的当前记录状态，对同状态按 operation ID 去重。旧代次引用、已完成块和取消操作不计入；批操作数与记录数分别展示，不能相加成“记录数”。

`configurationReferences.availability='notImplemented'` 明确表示配置引用未接通，不能解读为零配置引用；自动化及同步也维持 notImplemented。界面引用读取失败显示不可读取并允许重试，不以失败补零。投影数字不是删除授权，真实删除仍走既有影响预检及最终事务守卫。

性能实测入口为 `scripts/measure-schema-commit.py`，只建立并清理自己的临时数据库，使用真实应用服务；输出分别记录预览、成功 BEGIN IMMEDIATE→COMMIT、数据库大小、规范字节及并发读取响应。本轮证据保存于 [R3 性能报告](../design-alignment/acceptance/gallery-r3/performance/schema-commit.json)，其数字仅代表该次机器与有限样本，不是无限数据量承诺。
