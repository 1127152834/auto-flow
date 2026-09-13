# Project Data Editing Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在正式数据详情页接通记录创建、内容编辑、单行显式状态、记录删除，以及字段创建/影响编辑、状态创建/编辑/影响删除，保留草稿与原命令恢复。

**Architecture:** 保留 `DataTableDetailPage` 现有 TanStack Query 查询和 `RecordFilterEditor` 草稿所有权；增加一个详情写入 controller，只维护当前编辑会话、冻结命令与有效期，不复制查询、表单值或幂等恢复算法。扩展现有 `createDataCommand` 处理删除的 OperationAccepted 包装、只查询恢复和每次实际发送前的准入；三种已有 Editor 采用已交付 `DataTableFormDialog` 的最小生命周期接口。

**Tech Stack:** React 19、TypeScript、TanStack Query、RHF/Zod、现有 shadcn/Radix 控件、generated OpenAPI DTO、Vitest/Testing Library、真实 Electron/sidecar 冒烟。

---

日期：2026-09-13。状态：proposed implementation detail，业务范围 confirmed。来源：批准的 `docs/project-management/implementation/api-contracts.md` §1、§3.3，`docs/superpowers/plans/2026-09-13-project-management-pm2.md` C2/A2g，持续实施授权。本文只规划 C2c；不因本文生成而声称实现或验收通过。

执行工作区仅 `/Users/zhangtiancheng/Documents/projects/autoflow-project-management-implementation`。以下相对路径均相对该工作区，命令显式给出工作目录；主目录和其他 worktree 不写。目录创建/读取/编辑基线 `2813980`、删除核心 `2cded8e`、删除 HTTP/生成类型 `32c3395` 已提交；C2b 只读详情已完成独立审查并提交6552fa8，执行本文保留其最终结果，保留其 query/disabled/代次/leave 修复，不按本文读取时的行号覆盖。

## 范围、依赖与明确边界

- 输入：现有三个 Editor、`DataRecordsTable`、字段/状态目录 DTO、记录 GET 完整快照、表资料、当前 workspace/project/table/generation 与运行时 client/instance。
- 输出：正式页面中可完成九个真实写命令；确定失败保留输入，未知结果保存原 key/body/target 并提供核对；成功后查询刷新反映权威结果。
- 不做：字段删除（PM4-B）、批状态（等待 A2h 耐久接口后独立接入）、Excel IPC、Sheets 远程写、slot/environment 编辑、End/Studio/导航架构改动。不给这些能力增加占位或伪可用按钮。
- 来源本地表先完整验收。Excel 普通本地字段沿现有 `writable/formula` 和后端策略；不把所有 Excel 数据一概只读。身份字段创建时必须填写，编辑时禁止改值。Sheets/未配置来源不突破后端当前能力，后端明确拒绝时显示实际错误，不伪造成功。
- 后端删除已真实返回 **202 `{operation}`**，目前 operation **`status='succeeded'`**，状态删除结果与记录删除结果不同；不能把接受包装当成 DTO、不能只看到 202 就在页面宣布成功、不能引入前端轮询假异步。
- `DataTableDetailPage` 的只读来源仍为项目上下文；`disabled` 是连接不可用。只读禁止新写和重发；允许通过当前可用 client 查询已接受命令。切换 instance 不清空草稿；workspace/project/table 变化隔离会话；generation 变化冻结旧草稿并要求明确处理。

## 文件职责（先锁定边界）

| 文件 | 操作与唯一职责 |
|---|---|
| `apps/desktop/src/renderer/domains/project-data/data-command.ts` | 修改共享命令执行器：DELETE、OperationAccepted 提取、lookup-only、实际发送准入。已有 POST/PATCH/PUT 默认语义不变。 |
| `apps/desktop/src/renderer/domains/project-data/data-command.test.ts` | 新建：共享传输策略的少量独立测试；不把所有 API 测试搬入。 |
| `apps/desktop/src/renderer/domains/project-data/api.ts` 与 `.test.ts` | 表 create/patch/resume 方法透传同一执行策略；原DTO结果不变。 |
| `apps/desktop/src/renderer/domains/project-data/pages/DataTableDirectoryPage.tsx` 与 `.test.tsx` | 迁移已有正式表CRUD消费者的动态发送准入与只读核对；保留原目录查询/草稿/恢复结构，不重写页面。 |
| `apps/desktop/src/renderer/domains/project-data/catalog-api.ts` 与 `.test.ts` | 添加状态删除 preview/delete/result 校验；现有四个写方法仅加可选执行策略透传。 |
| `apps/desktop/src/renderer/domains/project-data/records-api.ts` 与 `.test.ts` | 添加记录删除 preview/delete/result 校验；三个已有写方法透传策略。复用本文件原 key 编码。 |
| `apps/desktop/src/renderer/domains/project-data/use-data-table-editing.ts` 与 `.test.tsx` | 新建唯一 controller：冻结编辑上下文/命令、发送期 ticket、失败/核对/重新编辑；不 own QueryClient、不发目录/分页查询、不 own 字段值草稿。 |
| `apps/desktop/src/renderer/domains/project-data/components/RecordEditorDialog.tsx`、`FieldEditorDialog.tsx`、`StatusEditorDialog.tsx` 及各自现有 `.test.tsx` | 增补 close/saving/recovery/submissionEpoch 接口；继续各自 own RHF/标量草稿和字段级验证。 |
| `apps/desktop/src/renderer/domains/project-data/components/RecordStatusDialog.tsx` 与 `.test.tsx` | 新建单行状态选择表单；唯一业务输入为 `statusId:string|null`，显式“未设置”。复用 Select/Modal，不能使用状态目录编辑器冒充记录状态命令。 |
| `apps/desktop/src/renderer/domains/project-data/components/DataDeletionDialog.tsx` 与 `.test.tsx` | 新建状态/记录共用影响确认展示：target、impacts/blockers、预检/确认/核对；不执行 API、不改记录引用。 |
| `apps/desktop/src/renderer/domains/project-data/pages/DataTableDetailPage.tsx` 与现有 `.test.tsx` | 组装工具栏/对话框，选择完整记录，合并筛选/编辑离开守卫，沿原 query key 刷新。 |
| `scripts/smoke-project-data.mjs` | 扩展已有真实入口冒烟，保留目录验收；用 UI 执行本包动作，HTTP 只做独立断言/制造冲突。 |

不新增第二个 `api.ts`、通用操作队列、通用表单框架、领域内第二套 query cache。`DataRecordsTable` 已有 `onCreate/onStatusChange/onOpen`；本包优先使用它们，在既有记录详情 Modal 内提供编辑/删除，不增加行选择框或批量 toolbar。字段/状态按钮直接位于对应目录条目。共享 `Modal`、`DataTableFormDialog` 无需改；共享 command API 保持默认兼容，但实际Directory消费者必须传准入，不能留下旧scope自动补写漏洞。

## 精确 HTTP 请求与结果

下面 P/T/G 是**冻结会话**的 projectId/tableId/datasetGeneration；K 是规范 UUID `Idempotency-Key`；R 是完整 `DataRecordRef`；E 是 `base64url(UTF8(R.recordKey.value))` 且无 padding，只编码一次。所有 body 使用 generated schema，不手写替代 DTO。

| 动作 | 方法、路径、body | 返回与提取 |
|---|---|---|
| 创建记录 | `POST /projects/P/tables/T/records`：`{datasetGeneration:G,values}` | 201 DataRecordView；新记录 statusId=null，绝不追加状态初始化。 |
| 编辑记录内容 | `PATCH .../records/E`：`{datasetGeneration:G,recordKeyType:R.recordKey.type,values,expectedContentRevision}` | 200 DataRecordView；values 只包含编辑器基于冻结原记录算出的实际变更。 |
| 单行状态 | `PUT .../records/E/status`：`{datasetGeneration:G,recordKeyType:R.recordKey.type,statusId,expectedStatusRevision,expectedFromStatusId}` | 200 DataRecordView；本 UI 显式发送冻结旧 statusId（包括 null），不带 content/link 修订。 |
| 记录删除预检 | `POST /projects/P/mutation-impact`：`{action:'deleteRecord',target:{type:'record',recordRef:R}}` | 200 DeletionImpactReport；无 Idempotency-Key，不建 Operation。 |
| 记录删除 | `DELETE .../records/E`：`{datasetGeneration:G,recordKeyType:R.recordKey.type,expectedContentRevision,expectedStatusRevision,expectedLinkRevision,impactRevision}` | 202 OperationAccepted；kind=deleteRecord；result=`{target:{type:'record',recordRef:R},deleted:true}`。 |
| 创建字段 | `POST .../fields`：`{definition,expectedTableRevision,sourceColumnPolicy:'localOnly',existingRecordDefault?}` | 200 `{field,tableRevision}`；missing 与显式 null 默认值不得合并。 |
| 编辑字段预检 | `POST /projects/P/mutation-impact`：`{action:'updateField',target:{type:'field',fieldRef},change:definition}` | 200 FieldImpactReport；继续使用 FieldEditorDialog 两阶段 preview/confirm。 |
| 编辑字段 | `PATCH .../fields/F`：`{definition,expectedFieldRevision,expectedTableRevision,impactRevision}` | 200 `{field,tableRevision}`；原 fieldRevision/tableRevision 必须与草稿所依赖快照一致。 |
| 创建状态 | `POST .../statuses`：`{name,color,order,expectedTableRevision}` | 201 DataStatusView。 |
| 编辑状态 | `PATCH .../statuses/S`：`{name?,color?,order?,expectedStatusRevision,expectedTableRevision}` | 200 DataStatusView；只发送实际改变项。 |
| 状态删除预检 | `POST /projects/P/mutation-impact`：`{action:'deleteStatus',target:{type:'status',projectId:P,tableId:T,statusId:S}}` | 200 DeletionImpactReport。 |
| 状态删除 | `DELETE .../statuses/S`：`{expectedStatusRevision,expectedTableRevision,impactRevision}` | 202 OperationAccepted；kind=mutateStatus；result=`{action:'delete',statusId:S,deleted:true,tableRevision}`。 |

表中路径统一前缀 `/api/v1`。字段/状态 create/update 恢复不能抽取删除 result；状态删除不能用 `statusResult('update')`，记录删除不能用原 `result(recordKey)`。目录 response 的 `tableRevision` 是该目录会话版本，不能直接用可能尚未刷新的 table view 版本。

## 会话与错误规则

### 单一所有权

controller 的 `Editor` 在打开时 `structuredClone` 保存表资料、相关 fields/statuses 目录、目标完整 field/status/record；同时保存对应目录 tableRevision。记录 edit/status/delete 先使用现有 `detailQuery` GET 成功值，禁止只保存行索引再从刷新后的 page 找回。createRecord 也冻结字段集合。Editor `sessionKey=crypto.randomUUID()` 仅因新开/明确重新编辑改变，不含 instanceId。

每个成功验证后的第一次 Submit 才生成 key，冻结 body；preview 不生成 key。controller 在 `pending` 未确定前不允许修改输入、换 target、关窗/离开或创建新命令。field preview 必须校验返回 target、fieldRevision、tableRevision 与当前冻结编辑上下文相符；否则显示资料已变化并要求明确重新编辑，不能偷换 expected revisions 让旧草稿通过新 CAS。删除 preview 的完整 target 和三 revision/目录 revision 同样核对；blockers 非空禁用确认。

编辑会话绑定 `[workspaceKey,projectId,tableId,generation]`；发送有效期还绑定 `instanceId/client/disabled/editor.session` 和递增 ticket。每次真正 HTTP 写（包括共享 helper 的原 key 重发）前再次读当前 guard。返回后 guard 不匹配时，不关闭新弹窗、不写缓存、不 toast、不导航。instance 变化令在途命令进入待核对、释放旧 UI busy，但保留 pending key/body；重连后使用新 client **查询原 key**。

### 错误决策表

| 事实 | UI 行为/后续可发请求 |
|---|---|
| 网络超时、5xx、返回结果身份/shape不匹配、操作查询无法确定 | 保留 pending；冻结输入；“核对保存结果”只 GET 原操作。不可直接重发/换 key。 |
| 原 operation 查询 succeeded 且 kind/resource/result 完全一致 | 抽取结果、结束当前 pending、刷新当前 scope；只读也允许。 |
| 原查询精确 404 OPERATION_NOT_FOUND | 标记原命令未接受，保留原 body/key；当前 scope 可写才允许用户“重试原请求”。只读仍显示未接受且禁重试；允许明确放弃未接受请求。不能把 PROJECT_NOT_FOUND 当未接受。 |
| 首次写明确 401/403 | 不换身份重发；显示权限/连接事实，允许保留草稿与只读核对；401 由既有会话桥恢复。无 operation 未知时不要冒充已接受。 |
| 明确 409 REVISION_CONFLICT | 原命令不继续重发；保留输入与冻结基线，提供“载入最新资料”→“替换当前草稿？”；同意后 GET 最新原 target、重建 session，用户重新输入/提交生成新 key。 |
| 明确 409 生命周期/SERVICE_QUIESCED | 显示具体原因；重新核对当前 project/table 可写事实后才恢复新提交。不把所有 409 显示成版本冲突。 |
| 410 generation / 404 原 record/status 已不存在 | 保留可查看草稿，标记原目标不可再提交；核对原操作只读。明确放弃后才能进入新 generation；不自动将同值 recordKey 指向新代次。 |
| 412 impact 不匹配/过期/事实变化 | 不自动确认；保留草稿，丢弃旧 impact；重新预检并重新展示影响。若 preview revision 与冻结基线不同，走明确重新编辑，不更新 CAS 偷渡。 |
| 422 校验 / 423 引用或占用 | 展示后端 message/details（含 blockers）；保留草稿。修正输入/事实并重新预检后才新提交；删除状态不暗改引用记录。 |

`403` 是客户端防御处理，不在本次后端新增错误码。只读下查到原命令未接受不得触发原 helper 自动 retry；这是本包必须补的传输门禁，不是“按钮 disabled”可替代的行为。

## Task 1：共享命令支持 OperationAccepted 与受控恢复

**Files:** 修改 `.../project-data/data-command.ts`；新建 `.../project-data/data-command.test.ts`。本节 `...` 仅作为标题简写；文件实际全路径已在职责表列明，命令使用真实路径。

- [x] 写以下 RED 测试（沿既有 `catalog-api.test.ts` 的 client mock 方式），随后补 `lookupOnly` 精确 absent、readonly guard、未改变默认重试的断言：

```ts
import { expect, it, vi } from 'vitest'
import { ApiClientError } from '../../shared/api/client'
import { createDataCommand, DataCommandNotAccepted } from './data-command'

it('projects the accepted response and never returns the wrapper', async () => {
  const operation = { projectId: 'p', idempotencyKey: 'k', kind: 'deleteRecord', status: 'succeeded', result: { deleted: true } }
  const request = vi.fn().mockResolvedValue({ operation })
  const command = createDataCommand({ request, health: vi.fn(), stream: vi.fn() }, 'p')
  await expect(command('/delete', 'DELETE', {}, 'k', 'deleteRecord', false,
    op => op.result, { acceptedResponse: true })).resolves.toEqual({ deleted: true })
  expect(request).toHaveBeenCalledTimes(1)
})

it('does not resubmit after lookup-only establishes absence', async () => {
  const request = vi.fn().mockRejectedValue(new ApiClientError('absent', 404, 'OPERATION_NOT_FOUND'))
  const command = createDataCommand({ request, health: vi.fn(), stream: vi.fn() }, 'p')
  await expect(command('/delete', 'DELETE', {}, 'k', 'deleteRecord', true,
    op => op.result, { lookupOnly: true })).rejects.toBeInstanceOf(DataCommandNotAccepted)
  expect(request.mock.calls.map(call => call[0])).toEqual(['/api/v1/projects/p/operations/by-idempotency-key/k'])
})
```

- [x] 在 desktop 工作目录运行 `npm test -- src/renderer/domains/project-data/data-command.test.ts`，预期因 method/options/class 缺失失败；记录 RED 输出。
- [x] 保留现有 `assertFiniteNumbers/definitive`，增加以下完整执行策略和替换 `createDataCommand` 函数体；`DataCommandUncertain` 原类不变：

```ts
export type DataCommandPolicy = {
  acceptedResponse?: boolean
  lookupOnly?: boolean
  canSubmit?: () => boolean
}
export class DataCommandNotAccepted extends Error {
  constructor() { super('原操作尚未接受，可在当前上下文允许时重试原请求'); this.name = 'DataCommandNotAccepted' }
}

export function createDataCommand(client: StreamingApiClient, projectId: string) {
  return async function command<T>(path: string, method: 'POST' | 'PATCH' | 'PUT' | 'DELETE', body: object,
    key: string, kind: Operation['kind'], resume: boolean, projectResult: (operation: Operation) => T,
    policy: DataCommandPolicy = {}): Promise<T> {
    const originalBody = structuredClone(body)
    assertFiniteNumbers(originalBody)
    const project = (operation: Operation): T => {
      if (!operation || operation.projectId !== projectId || operation.idempotencyKey !== key || operation.kind !== kind || operation.status !== 'succeeded') throw mismatch()
      return projectResult(operation)
    }
    const submit = async (): Promise<T> => {
      if (policy.canSubmit && !policy.canSubmit()) throw new DataCommandUncertain(new Error('当前上下文不允许发送原请求'))
      if (!policy.acceptedResponse) return client.request<T>(path, { method, headers: { 'Idempotency-Key': key }, body: originalBody })
      const accepted = await client.request<{ operation: Operation }>(path, { method, headers: { 'Idempotency-Key': key }, body: originalBody })
      return project(accepted.operation)
    }
    if (!resume && !policy.lookupOnly) {
      try { return await submit() } catch (error) {
        if (definitive(error) || error instanceof DataCommandUncertain || (error instanceof DOMException && error.name === 'AbortError')) throw error
      }
    }
    try {
      return project(await client.request<Operation>(`/api/v1/projects/${encode(projectId)}/operations/by-idempotency-key/${encode(key)}`))
    } catch (error) {
      if (!(error instanceof ApiClientError && error.status === 404 && error.code === 'OPERATION_NOT_FOUND')) throw new DataCommandUncertain(error)
      if (policy.lookupOnly) throw new DataCommandNotAccepted()
      try { return await submit() } catch (retryError) {
        if (definitive(retryError)) throw retryError
        throw new DataCommandUncertain(retryError)
      }
    }
  }
}
```

- [x] 增补测试：成功包装缺 operation/错误 kind/错误 key 不得返回成功；guard 在第一次丢包后的 lookup 等待中变 false 时不得出现第二次写；lookupOnly 下 succeeded 可在 guard=false 返回；PROJECT_NOT_FOUND 保持 uncertain；传入 body 修改不改变原发送；401/403/409/410 不自动 lookup/retry。
- [x] 运行 `npm test -- src/renderer/domains/project-data/data-command.test.ts src/renderer/domains/project-data/api.test.ts src/renderer/domains/project-data/catalog-api.test.ts src/renderer/domains/project-data/records-api.test.ts`，预期全 PASS。无新依赖，无 OpenAPI 变化。
- [x] 只 stage 本 task 两个文件，提交 `feat(project-data): recover accepted deletions without unguarded resubmission`。

### Task 1b：把正式 Directory 调用纳入相同发送准入

**Files:** `apps/desktop/src/renderer/domains/project-data/api.ts`、`api.test.ts`、`pages/DataTableDirectoryPage.tsx`、`pages/DataTableDirectoryPage.test.tsx`。紧接Task1完成；不能只迁移新Record入口。

- [x] Directory RED测试以延迟Promise控制：保存表POST丢包→operation查询等待→rerender新instance/readonly/disabled或卸载换workspace→旧查询返回OPERATION_NOT_FOUND，断言没有第二次POST。再验证新client核对succeeded仍取回原表；只读核对NOT_FOUND不发写、原key/body仍可见；恢复可写后点击“重试原请求”只用原key/body。API单测验证policy原对象透传而非调用时算一次boolean。
- [x] desktop运行 `npm test -- src/renderer/domains/project-data/pages/DataTableDirectoryPage.test.tsx src/renderer/domains/project-data/api.test.ts`，预期新迟到补写断言RED。
- [x] `createProjectDataApi`内部command末尾增加 `policy?:DataCommandPolicy`，将其作为 execute 的第8参数；公开签名改为：

```ts
create: (body: TableCreate, key: string, policy?: DataCommandPolicy) => command('createTable', body, key, undefined, false, policy),
patch: (tableId: string, body: TablePatch, key: string, policy?: DataCommandPolicy) => command('updateTable', body, key, tableId, false, policy),
resumeCreate: (body: TableCreate, key: string, policy?: DataCommandPolicy) => command('createTable', body, key, undefined, true, policy),
resumePatch: (tableId: string, body: TablePatch, key: string, policy?: DataCommandPolicy) => command('updateTable', body, key, tableId, true, policy),
```

- [x] Directory保留其已有pending/epoch/scope/mounted，不引入controller替换它。将当前 `current()` 声明移到API调用前，current校验补client/workspace/project；传 `const policy={lookupOnly:resume,canSubmit:()=>current()&&!scope.current.readonly}` 给四个实际API调用。首次写current在每次submit前由helper重新读取；不是只在then/catch判断。readonly不使查询current失效。scope ref加入client/workspace/project并将client变更纳入epoch失效；workspace/project React key仍保留。
- [x] 增加一个 `notAccepted` boolean承载精确 `DataCommandNotAccepted`，catch时保留pending/setRecoveryPending(true)，不要当一般Error清pending。现有DataTableFormDialog的errorActions可直接显示“重试原请求”（disabled当readonly/disabled/busy）与“放弃未接受请求”；前者以原pending调用create/patch `resume=false`并传动态guard，后者才清pending并解除frozen。unknown时不能放弃；notAccepted在有效scope下允许明确放弃且保留草稿。`execute`增加一个显式mode参数区分submit/lookup/retry，禁止依pending存在就无法选择原请求重试。
- [x] 运行Directory/API/表单测试，预期全部PASS；提交 `fix(project-data): guard directory command resubmission across scope changes`。README/导航/表单本体不用改。

**读请求例外：** GET和mutation-impact的POST是查询，不设置write canSubmit，不用 `method !== 'GET'` 推导权限。preview晚响应仍做scope/ticket隔离；readonly可查询影响和原Operation。该区别是客户端策略；本包不改后端quiesce期间暂停新预检的既有全局行为。

## Task 2：补齐两个删除客户端与精确结果验证

**Files:** `apps/desktop/src/renderer/domains/project-data/{catalog-api.ts,catalog-api.test.ts,records-api.ts,records-api.test.ts}`。

- [x] 在已有 API 测试内先增加 RED：status delete 首次 202 和 recover 均得到 StatusDeleteResult；record delete 首次与 recover 均得到 RecordDeleteResult；输入 literal text `001 / 😀` 路径一次编码，integer `1` 与 text `1` 不同；wrong action/target/generation/deleted=false 均 uncertain 且不重发；preview body 无 key。

```ts
// 追加 catalog-api.test.ts，复用本文件 scope/api/statusOperation。
it('extracts status deletion rather than a status definition', async () => {
  const result = { action: 'delete', statusId: 's', deleted: true, tableRevision: 3 }
  const op = { ...statusOperation, result }
  const request = vi.fn().mockResolvedValueOnce({ operation: op }).mockResolvedValueOnce(op)
  const catalog = api(request)
  const body = { expectedStatusRevision: 1, expectedTableRevision: 2, impactRevision: 7 }
  await expect(catalog.deleteStatus('s', body, 'k')).resolves.toEqual(result)
  await expect(catalog.deleteStatus('s', body, 'k', true, { lookupOnly: true })).resolves.toEqual(result)
  expect(request.mock.calls[0][1]).toMatchObject({ method: 'DELETE', body })
  expect(request).toHaveBeenCalledTimes(2)
})
```

- [x] 运行 `npm test -- src/renderer/domains/project-data/catalog-api.test.ts src/renderer/domains/project-data/records-api.test.ts`，预期缺方法失败。
- [x] 两文件 import `DataCommandPolicy`；所有现有写方法末尾添加 `policy?: DataCommandPolicy`，将其作为共享 command 最后一个参数。保持现有 `resume=false` 位置，旧调用不改。catalog 增加以下函数及返回方法：

```ts
function deletedStatusResult(statusId: string) {
  return ({ resource, result }: Operation): Schema['StatusDeleteResult'] => {
    if (resource.type !== 'status' || resource.projectId !== scope.projectId || resource.tableId !== scope.tableId || resource.statusId !== statusId
      || !result || !('action' in result) || result.action !== 'delete' || !('statusId' in result) || result.statusId !== statusId || !('deleted' in result) || result.deleted !== true) throw mismatch()
    return result
  }
}
// 加入 createDataCatalogApi 的 return 对象。
previewStatusDelete: (statusId: string, signal?: AbortSignal) => client.request<Schema['DeletionImpactReport']>(`${project}/mutation-impact`, {
  method: 'POST', signal, body: { action: 'deleteStatus', target: { type: 'status', projectId: scope.projectId, tableId: scope.tableId, statusId } },
}),
deleteStatus: (statusId: string, body: Schema['StatusDelete'], key: string, resume = false, policy?: DataCommandPolicy) =>
  command(`${base}/statuses/${encode(statusId)}`, 'DELETE', body, key, 'mutateStatus', resume, deletedStatusResult(statusId), { ...policy, acceptedResponse: true }),
```

- [x] records 增加以下函数/返回方法（复用本文件 path/sameScope/sameKey；API 仍在 closure 中复制 scope）：

```ts
function deletedRecordResult(key: RecordKey) {
  return ({ resource, result: snapshot }: Schema['ProjectOperationView']): Schema['RecordDeleteResult'] => {
    if (resource.type !== 'record' || !sameScope(resource.recordRef) || !sameKey(resource.recordRef.recordKey, key)
      || !snapshot || !('target' in snapshot) || snapshot.target.type !== 'record' || snapshot.deleted !== true
      || !sameScope(snapshot.target.recordRef) || !sameKey(snapshot.target.recordRef.recordKey, key)) throw new Error('删除结果与原记录请求不一致')
    return snapshot
  }
}
// 加入 createRecordsApi 的 return 对象。
previewDelete: (recordKey: RecordKey, signal?: AbortSignal) => client.request<Schema['DeletionImpactReport']>(`/api/v1/projects/${encode(scope.projectId)}/mutation-impact`, {
  method: 'POST', signal, body: { action: 'deleteRecord', target: { type: 'record', recordRef: { ...scope, recordKey: { ...recordKey } } } },
}),
delete: (recordKey: RecordKey, body: Omit<Schema['RecordDelete'], 'datasetGeneration' | 'recordKeyType'>, key: string, resume = false, policy?: DataCommandPolicy) =>
  command(path(recordKey), 'DELETE', { ...body, datasetGeneration: scope.datasetGeneration, recordKeyType: recordKey.type }, key, 'deleteRecord', resume, deletedRecordResult({ ...recordKey }), { ...policy, acceptedResponse: true }),
```

- [x] 在 API 测试用 `it.each` 分别验证 resource 与 result 两处 target 身份，不只验证 resource；status create/update 收到 delete result 也拒绝。preview 返回内容由 controller 检验为冻结会话 target/revisions；transport method 负责精确请求。
- [x] 运行两个 API 测试与 `npm run typecheck`，预期通过。提交 `feat(project-data): add scoped status and record deletion clients`。

## Task 3：建立唯一详情写入 controller 与冻结命令

**Files:** 新建 `apps/desktop/src/renderer/domains/project-data/use-data-table-editing.ts` 与 `use-data-table-editing.test.tsx`。

- [ ] 用 Testing Library `renderHook/act` 写 controller RED 测试，先覆盖最危险的窗口：freeze 编辑记录后外部 query 刷新为 revision=9，submit 仍发原 revision=1；首次发送 pending 时换 instance 后旧 resolve 不调用 `onSaved`，调用 recover 仅查询原 key；readonly recover NOT_FOUND 不发写；workspace/table/generation 变化使旧 ticket 无效。测试 client 使用现有 `StreamingApiClient` mock，不 mock 掉 `createDataCommand`。

```ts
// controller 对外签名；实现与测试使用同一组名称，不另造 query hook。
type Schema = components['schemas']
type Scope = CatalogScope & { workspaceKey: string }
type Context = { scope: Scope; table: Schema['DataTableView']; fields: Schema['DataFieldDirectory']; statuses: Schema['DataStatusDirectory'] }
type Editor = Context & { session: string } & (
  | { kind: 'recordCreate' }
  | { kind: 'recordEdit' | 'recordStatus' | 'recordDelete'; record: Schema['DataRecordView'] }
  | { kind: 'fieldCreate' }
  | { kind: 'fieldEdit'; field: Schema['DataFieldView'] }
  | { kind: 'statusCreate' }
  | { kind: 'statusEdit' | 'statusDelete'; status: Schema['DataStatusView'] }
)
type Pending = { key: string; scope: Scope; session: string } & (
  | { kind: 'recordCreate'; body: Omit<Schema['DataRecordCreate'], 'datasetGeneration'> }
  | { kind: 'recordEdit'; target: RecordKey; body: Omit<Schema['DataRecordPatch'], 'datasetGeneration' | 'recordKeyType'> }
  | { kind: 'recordStatus'; target: RecordKey; body: Omit<Schema['DataRecordStatusWrite'], 'datasetGeneration' | 'recordKeyType'> }
  | { kind: 'recordDelete'; target: RecordKey; body: Omit<Schema['RecordDelete'], 'datasetGeneration' | 'recordKeyType'> }
  | { kind: 'fieldCreate'; body: Schema['DataFieldCreate'] }
  | { kind: 'fieldEdit'; target: string; body: Schema['DataFieldPatch'] }
  | { kind: 'statusCreate'; body: Schema['DataStatusCreate'] }
  | { kind: 'statusEdit'; target: string; body: Schema['DataStatusPatch'] }
  | { kind: 'statusDelete'; target: string; body: Schema['StatusDelete'] }
)
```

在同一文件 export `EditingContext`（上文 Context）和 `DataEditor`（上文 Editor）供 page 使用；Pending 保持内部。目标 target 永远由 Editor 取，不允许提交者传入任意 project/table/id。

- [ ] 运行 `npm test -- src/renderer/domains/project-data/use-data-table-editing.test.tsx`，预期缺模块失败。
- [ ] 在 controller 内实现如下 dispatcher，返回 generated结果联合，无通用 `any`。这是唯一命令分发；每次恢复用当前 client 和冻结 scope 重建既有 API：

```ts
function dispatch(client: StreamingApiClient, pending: Pending, resume: boolean, policy: DataCommandPolicy) {
  const catalog = createDataCatalogApi(client, pending.scope)
  const records = createRecordsApi(client, pending.scope)
  switch (pending.kind) {
    case 'recordCreate': return records.create(pending.body, pending.key, resume, policy)
    case 'recordEdit': return records.update(pending.target, pending.body, pending.key, resume, policy)
    case 'recordStatus': return records.setStatus(pending.target, pending.body, pending.key, resume, policy)
    case 'recordDelete': return records.delete(pending.target, pending.body, pending.key, resume, policy)
    case 'fieldCreate': return catalog.createField(pending.body, pending.key, resume, policy)
    case 'fieldEdit': return catalog.updateField(pending.target, pending.body, pending.key, resume, policy)
    case 'statusCreate': return catalog.createStatus(pending.body, pending.key, resume, policy)
    case 'statusEdit': return catalog.updateStatus(pending.target, pending.body, pending.key, resume, policy)
    case 'statusDelete': return catalog.deleteStatus(pending.target, pending.body, pending.key, resume, policy)
  }
}
```

- [ ] 实现 hook `useDataTableEditing({context,client,instanceId,disabled,readonly,onSaved})`，context类型为 `EditingContext|null`，未载入时open/submit均拒绝，hook仍始终在page顶部调用。输出 `editor,error,busy,recoveryPending,notAccepted,conflict,impact,open,close,submitRecord,submitField,submitStatus,submitRecordStatus,previewDelete,confirmDelete,previewField,recover,retryOriginal,discardUnaccepted,replaceEditor,onDirtyChange,onSavingChange,canLeave`。所有 open/submit 函数依本节签名含义：`open` 接收不含 Context/session 的 Editor 分支，由 hook 合入 clone(context)；`replaceEditor` 接收重新读取的完整 Editor 分支及 Context，只允许没有未知 pending 时执行；`discardUnaccepted` 仅notAccepted=true时清pending/recovery状态而保留editor草稿；`close` 仅清已确认能关闭的会话；`canLeave()` 同步返回 `!busy && !pending`，dirty 确认由 page 统一 own。

实现步骤按以下固定映射分成可运行小步，不建立额外 reducer/状态机文件：

1. `useState<Editor|null>` 保存 clone 会话，`useRef<Pending|null>` 保存 clone 命令，`useRef` 同步锁与 `epoch/mounted/live` 记录当前 scope/client/instance/disabled/readonly/session。`useLayoutEffect` 刷新 live；instance/client/disabled/session 变化推进 epoch，若 pending 存在则 recoveryPending=true；卸载令 mounted=false/epoch++。
2. 各 submit 先检查 editor.kind、pending、同步锁、live scope及可写。创建命令只在验证后的本次调用生成 UUID；设置 pending 后再 await，不允许双提交。把下表 body builder 的结果 `structuredClone`。
3. `execute(mode:'submit'|'recover'|'retry')`：先取得 pending；recover 固定 `resume=true,lookupOnly=true`，其他为 `resume=false`；传 `canSubmit:()=>isCurrent(ticket)&&!live.readonly&&!live.disabled&&sameScope(live.context.scope,pending.scope)`。设置同步锁在 await 前；完成时先 isCurrent 再通知 page。readonly 不影响只读 recover 的 current 检查。
4. catch `DataCommandNotAccepted`：保留 pending 并置 notAccepted=true；catch uncertain：保留并置 recoveryPending=true；明确 API 4xx：清 pending、保留 editor，按错误表选择 conflict/impact失效/目标不可写。finally 只释放同 ticket 锁。
5. `retryOriginal` 仅 notAccepted 且当前可写/同 scope 时允许，保留原 key/body；明确“放弃未接受请求”才可清 pending。成功清 pending/editor 并 `onSaved(pending.kind)`；onSaved 只发当前 scope invalidation，不把异构返回值强塞进 record cache。
6. `previewField/previewDelete` 不生成 pending，使用当前有效 client、冻结 target，持独立同一 epoch 的 busy；返回后核对 target 与 expectedRevisions。preview 的晚返回必须抛出可识别过期错误且不能调用 setImpact/onSaved。校验通过且 blockers=[] 才启用下一次 confirm；412 后清本地 impact。

body builder 明确如下（不从当前 query 变量取版本）：

```ts
// e 是上面 Editor 的对应分支；submission/values/statusId 是已验证的编辑器输出。
// recordCreate
const recordCreateBody = { values }
// recordEdit
const recordEditBody = { values, expectedContentRevision: e.record.contentRevision }
// recordStatus
const recordStatusBody = { statusId, expectedStatusRevision: e.record.statusRevision, expectedFromStatusId: e.record.statusId }
// recordDelete，impact 已通过完整 target 与 revision 核对
const recordDeleteBody = { expectedContentRevision: e.record.contentRevision, expectedStatusRevision: e.record.statusRevision,
  expectedLinkRevision: e.record.linkRevision, impactRevision: impact.impactRevision }
// fieldCreate（条件展开保留 null 与 missing 区别）
const fieldCreateBody = { definition: submission.definition, expectedTableRevision: e.fields.tableRevision,
  sourceColumnPolicy: 'localOnly' as const, ...('existingRecordDefault' in submission ? { existingRecordDefault: submission.existingRecordDefault } : {}) }
// fieldEdit
const fieldEditBody = { definition: submission.definition, expectedFieldRevision: e.field.fieldRevision,
  expectedTableRevision: e.fields.tableRevision, impactRevision: submission.impactRevision }
// statusCreate / statusEdit（StatusSubmission 在对应分支用 statusFormSchema 校验必填）
const statusCreateBody = { ...statusFormSchema.parse(submission), expectedTableRevision: e.statuses.tableRevision }
const statusEditBody = { ...submission, expectedStatusRevision: e.status.statusRevision, expectedTableRevision: e.statuses.tableRevision }
// statusDelete
const statusDeleteBody = { expectedStatusRevision: e.status.statusRevision, expectedTableRevision: e.statuses.tableRevision, impactRevision: impact.impactRevision }
```

上面是分支内独立代码，不顺序粘贴为一个含不兼容 e 的函数；每个 case 由 TypeScript discriminated union 收窄。`sameScope` 对四个 scope 字段严格相等；`isCurrent` 要求 mounted、ticket、session、instance/client 未变化且 !disabled。已读取核对后端事实：status preview的expectedRevisions为tableRevision/statusRevision；record为tableRevision/contentRevision/statusRevision/linkRevision；field为tableRevision/fieldRevision。用冻结会话逐项比较，不创造expected前缀。record preview额外tableRevision用Editor.fields.tableRevision核对；若字段目录已变更须重新编辑，不能将旧字段草稿套新目录。

- [ ] 增补 RED→GREEN：refresh 不改变 fields 类型或 record 原值；no-op edit不发请求；新建空系统记录只 POST 一次且无状态写；选择 null状态包含 expectedFromStatusId；412 之后必须新 preview；在 readonly 改变的微任务窗口不能发送；late success/error 不关闭另一个 editor；generation 变化时恢复原操作可查、重发不可行。
- [ ] 运行 controller、三个API测试及 `npm run typecheck`。提交 `feat(project-data): freeze detail edits and original command recovery`。

## Task 4：三种已有编辑器补齐受控恢复与关闭

**Files:** 三个已有 Editor 及各自测试；只读参考 `DataTableFormDialog.tsx/.test.tsx`，不改它。

- [ ] 每个测试文件增加行为测试：dirty + `submissionEpoch` 变化仍保留输入；旧请求晚到不覆盖 error；recoveryPending 冻结字段且显示核对按钮；readonly 核对仍调用 onRecover；busy/unknown 时 Escape、取消、遮罩不能丢命令；外部 onRequestClose 返回 false不关、true只在再次检查 guard后关。StatusEditor 额外测试连续两次 submit只发一次以及异步RHF验证期间变readonly/closed不发请求。

```tsx
// 追加 RecordEditorDialog.test.tsx，复用此文件 field() 和 test environment。
it('keeps drafts and permits lookup-only recovery after reconnect to readonly', async () => {
  const user = userEvent.setup(), recover = vi.fn().mockResolvedValue(undefined)
  const shared = { open: true, mode: 'create' as const, sessionKey: 'same', fields: [field('x')], onOpenChange: vi.fn(), onSubmit: vi.fn(), onRecover: recover }
  const view = render(<RecordEditorDialog {...shared} submissionEpoch="i1" />)
  await chooseOption(user, screen.getByRole('combobox', { name: 'x值状态' }), 'value')
  await user.type(screen.getByLabelText('x'), 'draft')
  view.rerender(<RecordEditorDialog {...shared} submissionEpoch="i2" recoveryPending readonly />)
  expect(screen.getByLabelText('x')).toHaveValue('draft')
  await user.click(screen.getByRole('button', { name: '核对保存结果' }))
  expect(recover).toHaveBeenCalledOnce()
  expect(shared.onSubmit).not.toHaveBeenCalled()
})
```

- [ ] 运行三个 editor 测试，预期新 props/按钮缺失失败。
- [ ] 每个 Editor props 增补以下相同可选接口；这是接口一致化，不抽取第四个通用表单状态机：

```ts
submissionEpoch?: string | number
recoveryPending?: boolean
errorActions?: ReactNode
onRequestClose?(): boolean | void | Promise<boolean | void>
onRecover?(): Promise<unknown>
onSavingChange?(saving: boolean): void
```

按 DataTableFormDialog 已实现的 `requestEpoch/submitLock/recoverLock/closeLock/guard` 完整分支迁移到各现有 Editor：同 session 的 submissionEpoch 改变只撤销请求、不 form.reset、不更换 RecordEditor.context；`frozen=busy||recoveryPending` 作用于所有输入/类型/默认值/预检按钮；调用 onSubmit/onPreview 的异步验证后再次核对 open/readonly/recovery/epoch；busy 通过同步 callback 通知父守卫。FieldEditor 本地 impact 在 reconnect 后清空但 definition 草稿保留；未知命令的 body 已由 controller冻结，恢复不依赖新 impact。

footer 的替换代码（置于每个 Editor 既有取消按钮之后；保存按钮保留各自原 form/name/no-op/protected 条件）统一为：

```tsx
{recoveryPending
  ? <Button type="button" variant="primary" disabled={busy || !onRecover} onClick={recover}>核对保存结果</Button>
  : <Button type="submit" form="record-editor-form" variant="primary" disabled={busy || readonly || (mode === 'edit' && !hasChanges)}>{busy ? '正在保存…' : mode === 'create' ? '创建记录' : '保存修改'}</Button>}
```

FieldEditor 使用其 `field-editor-form/actionChanged/blocked/protectedField`，StatusEditor 使用其 `status-editor-form/hasChanges`；三者 error 区渲染 `errorActions`。recover 实现直接采用 DataTableFormDialog 已验证的同名完整函数（包括 recoverLock/ticket/catch/finally），不通过 submit 模拟恢复；requestClose优先 onRequestClose，内部确认仅在没有外部guard且不是recoveryPending时使用。所有 unmount cleanup 通知 dirty=false/saving=false。

- [ ] 执行三个 Editor 测试与 DataTableFormDialog 回归、typecheck；检查原 missing/null/date、identity/readonly保护、changed-only 测试仍通过。提交 `feat(project-data): preserve editor drafts across guarded recovery`。

## Task 5：单行状态与删除确认组件

**Files:** 新建 `components/RecordStatusDialog.tsx/.test.tsx`、`components/DataDeletionDialog.tsx/.test.tsx`。

- [x] RED 测试先写：status初始来自record.statusId，Select显示“未设置”，未改变不能发、选择null返回null；目录缺旧status不得自动选首项；删除必须先preview，展示所有返回blockers，blockers时无confirm；预检过期后不能确认旧report；两组件busy和recovery禁止close并可只读核对。

```tsx
// RecordStatusDialog 的公开接口；只 own 一项 raw selection 和 dirty，没有网络。
type RecordStatusDialogProps = {
  open: boolean; sessionKey: string; submissionEpoch: string
  record: Schema['DataRecordView']; statuses: Schema['DataStatusView'][]
  readonly: boolean; saving: boolean; recoveryPending: boolean; error: string | null; errorActions?: ReactNode
  onSubmit(statusId: string | null): Promise<unknown>; onRecover(): Promise<unknown>
  onDirtyChange(dirty: boolean): void; onSavingChange(saving: boolean): void
  onRequestClose(): boolean | void | Promise<boolean | void>; onOpenChange(open: boolean): void
}
// DataDeletionDialog 的公开接口；targetName用于用户辨认，完整身份由controller冻结。
type DataDeletionDialogProps = {
  open: boolean; kind: 'record' | 'status'; targetName: string; impact: Schema['DeletionImpactReport'] | null
  saving: boolean; readonly: boolean; recoveryPending: boolean; error: string | null; errorActions?: ReactNode
  onPreview(): Promise<unknown>; onConfirm(): Promise<unknown>; onRecover(): Promise<unknown>
  onRequestClose(): boolean | void | Promise<boolean | void>; onOpenChange(open: boolean): void
}
```

组件内 `Schema=components['schemas']`，导入 ReactNode/Modal/Button/Select 与既有 shared AlertDialog。状态组件采用 Task4 已一致的同步锁/epoch guard；在新 session 时 `selected=record.statusId`，同 session refresh 不覆盖 dirty选择。选择UI最小内容为：

```tsx
<Select aria-label="记录业务状态" value={selected ?? '__unset__'} clearable={false}
  options={[{ value: '__unset__', label: '未设置' }, ...statuses.map(status => ({ value: status.statusId, label: status.name }))]}
  disabled={saving || recoveryPending} readOnly={readonly}
  onValueChange={value => { if (value !== null) setSelected(value === '__unset__' ? null : value) }} />
```

真实状态 ID 是规范 UUID，因此 `__unset__` 不与合法 ID 碰撞；不把空字符串传后端。当前状态不在目录时显示“原状态已不可用，请载入最新资料”，保留原值，禁提交。

- [x] 删除组件用一个 Modal 展示“删除记录/删除状态”、目标名称/typed身份、impacts.message 与 blockers.message/code；仅 `impact && blockers.length===0 && !saving && !readonly && !recoveryPending` 可点“确认删除”。无impact显示“检查删除影响”；恢复时只显示核对按钮。组件没有API、不暗改任何引用。busy 由controller同步锁兜底，关闭调用统一 onRequestClose，不自带第二个放弃确认层。

```tsx
{impact?.blockers.map((blocker, index) => <p key={`${blocker.code}:${index}`} role="alert">{blocker.message}（{blocker.code}）</p>)}
{impact?.impacts.map((item, index) => <p key={`${item.code}:${index}`}>{item.message}</p>)}
<Button type="button" variant={impact ? 'danger' : 'primary'}
  disabled={saving || recoveryPending || Boolean(impact && (readonly || impact.blockers.length))}
  onClick={() => void (impact ? onConfirm() : onPreview())}>{impact ? '确认删除' : '检查删除影响'}</Button>
```

- [x] 运行 `npm test -- src/renderer/domains/project-data/components/RecordStatusDialog.test.tsx src/renderer/domains/project-data/components/DataDeletionDialog.test.tsx`，从 missing module/behavior RED 到 PASS；执行typecheck。提交 `feat(project-data): add explicit status and deletion confirmation dialogs`。

## Task 6：在现有详情页组合写入、刷新与统一离开保护

**Files:** 修改 `apps/desktop/src/renderer/domains/project-data/pages/DataTableDetailPage.tsx/.test.tsx`。先保留 C2b 独立复审新增测试；原“页面不存在写入按钮”断言改成 readonly 场景，而不是删掉测试。

- [ ] 扩展真实client mock区分请求method；RED测试验证“新增记录”→值输入→POST payload、打开真实GET记录→内容修改→PATCH原revision、单行状态→PUT、record删除→preview→DELETE202→operation extractor、field create/edit两阶段、status create/edit/delete。不能让 mock 任何 `/fields` POST 自动返回 GET directory。

```tsx
// 追加到当前 Detail 测试，复用 props/renderPage/api/table/field/record。
it('creates an empty system record through the real command adapter', async () => {
  const { client, request } = api()
  request.mockImplementation(async (path: string, init?: { method?: string; body?: unknown }) => {
    if (path.endsWith('/records') && init?.method === 'POST') return record
    if (path.endsWith('/tables/t')) return table
    if (path.endsWith('/fields')) return { items: [], tableRevision: 3 }
    if (path.endsWith('/statuses')) return { items: [], tableRevision: 3 }
    if (path.includes('/records?')) return { items: [], total: 0, page: 1, pageSize: 50, sort: '[]' }
    throw new Error(path)
  })
  renderPage(<DataTableDetailPage {...props(client)} />)
  await userEvent.click(await screen.findByRole('button', { name: '新增记录' }))
  await userEvent.click(screen.getByRole('button', { name: '创建记录' }))
  await waitFor(() => expect(request.mock.calls.some(([path, init]) => path.endsWith('/records') && init?.method === 'POST')).toBe(true))
  const write = request.mock.calls.find(([path, init]) => path.endsWith('/records') && init?.method === 'POST')!
  expect(write[1]?.body).toEqual({ datasetGeneration: 'g', values: [] })
  expect(request.mock.calls.some(([path, init]) => path.endsWith('/status') && init?.method === 'PUT')).toBe(false)
})
```

把当前测试 `vi.fn` 签名扩成 `StreamingApiClient['request']` 兼容的 `(path,init)`，不以 `as any` 压过类型错误。

- [ ] 页面在 table与目录全部可用、refs generation正确、!generationWarning、!readonly、!disabled 时构造 EditingContext并开放写入口。源于 query 的目录可以刷新，传 Editor 的 props 永远取 `editing.editor.fields/items/record`；不要在 JSX 将活跃 `fields` 直接传入已dirty记录编辑器。记录详情查询仍是唯一GET通道：`onOpen`打开只读详情；“编辑记录/删除记录/修改业务状态”只在当前detailQuery成功后用该快照打开 editor。

接口绑定采用以下固定对应（名称已由 Task3 定义）：

| UI | controller绑定 |
|---|---|
| DataRecordsTable `onCreate` | `open({kind:'recordCreate'})` |
| DataRecordsTable `onStatusChange(row)` | 选择完整 key+generation，沿detailQuery读取后 `open({kind:'recordStatus',record:loaded})`；读取期间禁止第二次open。 |
| 详情“编辑记录/删除记录” | `open({kind:'recordEdit'|'recordDelete',record:detailQuery.data})`，同时关闭详情Modal，避免叠两个主dialog。 |
| 字段目录“新增字段/编辑字段” | `open({kind:'fieldCreate'})` / `open({kind:'fieldEdit',field})`；公式/只读字段禁编辑。 |
| 状态目录“新增状态/编辑状态/删除状态” | 对应 statusCreate/statusEdit/statusDelete，按 statusId确定target。 |
| 三Editor onSubmit | submitRecord / submitField / submitStatus；Field onPreview=previewField |
| 单行状态 onSubmit | submitRecordStatus |
| 删除Dialog onPreview/onConfirm | previewDelete / confirmDelete |
| 全部对话框 recovery | onRecover=recover；notAccepted的errorActions提供“重试原请求”和“放弃未接受请求”。 |

- [ ] 同页仍只注册一个 leave guard。扩展 C2b 当前 guard 为以下逻辑，不能让 Editor 和 filter分别register后互相覆盖：

```ts
const guard = async () => {
  if (!editing.canLeave()) return false
  if (!filterDirtyRef.current && !editorDirtyRef.current) return true
  return askDiscardOnce() // 沿用page已有单一Promise resolver与AlertDialog；下面定义行为。
}
```

`askDiscardOnce` 是将现有 `askLeave` 重命名并扩展后的函数：已有 resolver 时立即 false；否则显示一个 AlertDialog，明确列出当前有“未应用的筛选/排序”和/或“未保存的记录/字段/状态修改”；取消resolve(false)不改任一草稿；确认时再次检查 canLeave，成立才关闭editor并增加filterSession、清dirty，resolve(true)。onRequestClose仅处理editor草稿，不丢筛选；可给同一个确认框设置 `discardTarget:'editor'|'all'` 并分别决定清理范围。generation更新/返回/页签/浏览器历史走同一父导航owner的guard；组件不要直接另改location.hash。

切换记录筛选/页码只改已有query状态，不改变打开editor的冻结target；editor未关闭时不允许打开第二个editor。generation变化若filter或editor dirty或pending，保留旧会话并禁任何写，提供明确处理；未知pending先核对原操作，不能“放弃并载入”绕过。允许只读关闭已确定的未保存草稿。

- [ ] 成功当前scope只invalidate原查询，复用 `prefix=[workspace,instance,'project-data',project,'table',table]`；刷新view、catalog、records与当前detail，不手工合成目录计数/record状态。删除后清对应详情选择；分页total下降时限制到最后有效页，查询失败保留上次成功页并显示错误。字段改变可能使已应用filter失效，服务端422保持原filter并显示修正入口，不悄悄清空过滤条件。参考绑定：

```ts
const onSaved = () => {
  void cache.invalidateQueries({ queryKey: prefix })
  void cache.invalidateQueries({ queryKey: [workspaceKey, instanceId, 'project-data', projectId, 'tables'] })
}
```

仅当前成功ticket调用 onSaved；目录缓存第二条用于返回目录后的recordCount/tableRevision更新。recordsQuery/page的最后页修正复用目录page使用的 `Math.max(1,Math.ceil(total/pageSize))` 判断，不建立第二份分页源。

- [ ] “载入最新资料”明确确认后先 `tableApi.get(tableId)`核对generation，再读取当前目标目录/记录；如与冻结generation不同，不以新代次同key替换旧record，显示目标已换代并要求关闭旧稿；同代次才 `replaceEditor` 使用新UUID session和最新字段集合/record/版本。加载错误保留原草稿，不先clear。任何reload的late响应同样经过scope/ticket guard。
- [ ] RED→GREEN集成边界测试：dirty filter+dirty editor一次确认全部/只关闭editor；取消保存双草稿；pending unknown阻止所有关闭；readonly核对accepted/absent；后台field类型变更不改变编辑中的ScalarValueEditor；同实例refresh不覆盖record原快照；client/instance换代旧成功与失败不串UI；workspace/table切换无旧cache；generation变更不重发；412明确重预检；409 reload需确认；删除最后一页回到有效页；来源/设置五页签事实回归。
- [ ] 运行 `npm test -- src/renderer/domains/project-data/pages/DataTableDetailPage.test.tsx src/renderer/domains/projects/pages/ProjectsWorkspace.test.tsx src/renderer/app/navigation.test.tsx`、typecheck、lint；提交 `feat(project-data): connect recoverable detail editing workflows`。

## Task 7：真实入口验收、独立复审与证据

**Files:** `scripts/smoke-project-data.mjs`；执行时由root统一更新已有PM2执行卡/`.ai`验收记录（不在本文生成任务改共享文件）。脚本现写 `docs/migration/project-data-directory-qa/run-*`，沿用这个真实目录，并在checks说明新增表内编辑覆盖，不另造截图脚本。

- [ ] 先扩展冒烟目标断言使旧只读页失败：删除当前“Fields/statuses/records are setup through real APIs”正常流程，改为 UI 新建字段、状态、记录。保留HTTP用于查询核验和制造冲突。每个动作UI完成后GET断言真实值和revision，不仅检查toast。
- [ ] 用已有 `click/input/visible/api/capture` 助手实现顺序：新建本地表→字段页新建文本字段→字段编辑预检/确认→状态页创建/编辑“可再次使用”→记录页创建→记录详情编辑→单行状态设该status→删除该status预检被阻止且GET记录状态不变→显式清空状态→再preview/删除status→record preview/delete→GET记录404、目录total下降且operation查询确认deleted结果。记录删除前的CAS/body与操作key由捕获的真实请求/operation列表验证。

关键独立断言代码可直接放入脚本对应动作后（`project/table/base` 为脚本现有变量）：

```js
const afterCreate = (await api(`${base}/records?datasetGeneration=${table.datasetGeneration}`)).items[0]
assert.equal(afterCreate.statusId, null)
assert.equal(afterCreate.values.find(cell => cell.fieldId === fieldId).value, '合成客户甲')
const operations = await api(`/projects/${project.projectId}/operations?kind=deleteRecord&resourceType=record`)
const deletion = operations.items[0]
assert.equal(deletion.status, 'succeeded')
assert.equal(deletion.result.deleted, true)
assert.deepEqual(deletion.result.target, deletion.resource)
assert.deepEqual(deletion.resource.recordRef, afterCreate.ref)
```

fieldId 从UI创建后的GET fields取得（不猜UUID）；对预期404使用新增 `apiResponse` helper或原生fetch检查status，因为现有api helper对非2xx会直接throw。不要为了测试跳过真实UI直接DELETE。

- [ ] 第二条冒烟：记录编辑中后台HTTP改另一值造成409，UI原输入不变；明确载入最新→重新编辑→保存。第三条：记录dirty时真实restartSidecar，同workspace输入保留；新client下提交成功。第四条：在UI命令被服务端接受后，让renderer fetch丢弃**一次对应写响应**，查询原operation恢复；捕获请求确保单个key且没有第二条create事实。fetch注入仅安装于本机临时验收renderer，用try/finally恢复原fetch，不写业务逻辑。
- [ ] 增加截图：record-editor、field-impact、status-delete-blocked、record-delete-confirm、record-conflict、reconnect-draft；native200%缩放下Editor内容与footer可达、Select/Modal不越界；仅真实执行后写checks PASS，macOS证据不声称Windows通过。
- [ ] 依序执行以下命令，全部cwd为工作区根；失败先修对应最小范围后再继续：

```bash
npm --workspace @autoflow/desktop test -- src/renderer/domains/project-data
npm --workspace @autoflow/desktop test -- src/renderer/domains/projects/pages/ProjectsWorkspace.test.tsx src/renderer/app/navigation.test.tsx
npm run typecheck
npm run lint
npm run build
npm run openapi:check
npm run test:structure
npm run test:scripts
node scripts/smoke-project-data.mjs
git diff --check
```

后端仅合同回归，不因前端包改迁移：

```bash
cd apps/backend
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q tests/contract/test_project_data_deletions.py tests/contract/test_project_data_field_changes.py tests/contract/test_project_data_catalog.py tests/contract/test_project_data_records.py tests/contract/test_project_data_queries.py
```

- [ ] 提交前运行前端完整 `npm test` 一次，确认共享command默认兼容目录/字段/记录原恢复；提交脚本 `test(project-data): verify detail writes in the real desktop`。不stage其他实施者文件；root统一提供实际通过数量、截图路径、`.ai`记录与PM2执行卡更新。
- [ ] 用 requesting-code-review 完成独立规格审查后再工程审查；输入本计划、批准契约、实际diff、测试结果和真实截图。发现影响恢复/身份/CAS的缺陷必须修复再复查。C2c完成不等于PM2完成，A2h批状态和文件IPC仍由其他执行卡交付。

## 计划自查与已解决的技术差异

- 覆盖九个真实写命令，field删除/批状态/End/Studio均明确排除；原HTTP无须改。
- 202包装与普通DTO的差异由同一command策略处理；删除结果分别提取且严格验证target，未用模糊联合强转。
- 表目录现有resume在NOT_FOUND后可自动retry；本包在原算法上增加lookupOnly和每次发送guard，Task1b将正式Directory与table API一起迁移，Task2/3迁移catalog/records与Detail。未知恢复在只读时无写副作用，无新恢复引擎。
- 表单草稿留在已有Editor；controller只冻结初始上下文与已验证payload。字段更新、recordSnapshot refresh、instance变化不会悄悄改变dirty基线。
- 新建两个小组件分别对应不同真实业务输入：记录状态选择与删除影响确认。没有复用状态目录编辑器去发记录状态，没有给记录列表新增批量选择。
- C2b现有leave/query修复是输入依赖。本文实现者先读最终文件再做增量修改；同一 Detail 文件由一个实施者维护，API与组件可按文件责任分工但不可并行修改controller/page。
- 无需root新增业务决策。剩余执行协调仅为等待C2b复审最终落点、分配唯一Detail/controller写入者、统一记录验收证据；不重新向用户索要已有授权。

Task5实际API补充：DataDeletionDialog新增可选submissionEpoch以在同会话重连时撤销旧busy；父层按editor.session设置React key。RecordStatusDialog的submissionEpoch支持string|number，onRecover可省略以明确禁用连接不可用时的核对；其余接口同计划。最终两组件15测试、11独立探针及类型/lint通过，详见审查记录；页面挂载另属Task6。
