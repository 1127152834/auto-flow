# R3 字段统一保存与数据闭环 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 完成字段整体草稿、受影响数据预检和有界原子提交，补真实状态引用投影，按原型整理来源/设置并回归全部PM2能力。

**Architecture:** 新聚合用例位于现有project_data分层；沿用DataImpactRow和ProjectOperation，不建立任务队列。SQLite增加当前代次记录变更守卫以缩短最终事务检查；旧单字段接口和历史结果保留。

**Tech Stack:** Python/FastAPI/Pydantic、SQLAlchemy/Alembic/SQLite、React/TypeScript、RHF/Zod、现有Modal Drawer、Vitest、pytest。

---

前置：B0的R3字段和文件/批状态画板已确认；R1控件与R2记录闭环可复用。后台R3-01–04可在R2期间独立推进，生成类型和页面装配由主协调串行合入。以下新类型/路径为实施目标，现存路径以Files清单区分。

## R3-01：冻结聚合DTO与失败语义

**Files:** Create `apps/backend/src/autoflow/adapters/http/project_data_schema_schemas.py`、`apps/backend/src/autoflow/domain/project_data/schema.py`、`apps/backend/tests/unit/test_project_data_schema.py`；Modify `docs/project-management/implementation/api-contracts.md`。本包不挂空HTTP、不提前生成未实现接口。

固定三个新接口：

| 方法/路径（前缀`/api/v1/projects/{projectId}/tables/{tableId}`） | 输入 | 输出/权限 |
|---|---|---|
| POST `/schema/preview` | DataSchemaCandidate | DataSchemaImpact，已认证活动项目；记录预览证据，不写业务字段 |
| POST `/schema` | DataSchemaCommit + Idempotency-Key | DataSchemaResult，首次和幂等重放都200，业务保存与结果同事务 |
| GET `/statuses/usage` | 当前表读取 | DataStatusUsageDirectory，归档可读，失败不返回假零 |

计划使用以下HTTP形状；生产由ApiModel/Pydantic声明camelCase，前端只消费生成类型：

```ts
type DataSchemaExisting = {
  kind: 'existing'; fieldId: string; expectedFieldRevision: number
  definition: DataFieldWrite
}
type DataSchemaNew = {
  kind: 'new'; clientId: string; definition: DataFieldWrite
  sourceColumnPolicy: 'localOnly'; existingRecordDefault?: Scalar
}
type DataSchemaCandidate = {
  datasetGeneration: string; expectedTableRevision: number
  fields: Array<DataSchemaExisting | DataSchemaNew>
}
type DataSchemaCommit = { candidate: DataSchemaCandidate; impactRevision: number }
type DataSchemaIssue = {
  code: string; fieldId: string | null; clientId: string | null
  message: string; affectedRecords: number | null
}
type DataSchemaImpact = {
  impactRevision: number; calculatedAt: string; expiresAt: string
  affectedRecords: number; backfillBytes: number
  blockers: DataSchemaIssue[]; warnings: DataSchemaIssue[]
  referenceAvailability: { automations: 'notImplemented'; sync: 'notImplemented' }
}
type DataSchemaResult = {
  action: 'saveSchema'; datasetGeneration: string; tableRevision: number
  fields: DataFieldView[]; createdFieldIds: Record<string, string>; backfilledRecords: number
}
```

`DataFieldWrite`、`DataFieldView`、`Scalar`均直接复用 `project_data_catalog_schemas.py`；旧DataFieldCreate/Patch、mutateField/FieldMutationResult不变。kind为`saveTableSchema`，挂现有table资源定位与Operation查询，不另造恢复URL。未来automations/sync开放时需扩真实引用合同，不把当前notImplemented当无引用。

- [ ] 写unit反例：完整候选包含每个当前fieldId恰好一次；缺失、重复、未知拒绝；新clientId为UUID且互异；已有字段key保持只读，身份/公式/不可写字段的受保护属性不能改变；新默认值省略与显式null不同。代码目标签名：

```python
# domain/project_data/schema.py
# validate_candidate只做类型/结构/字段规则，不查询数据库；完整集合比较在仓储已有结构快照上做。
def canonical_bytes(value: object) -> bytes:
    import json
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")

class SchemaBackfillLimit(ValueError):
    pass

def backfill_budget(values: list[dict]) -> tuple[int, int]:
    # 调用方只传实际发生写入的整行values_json；不是仅新增字段的字节。
    count = len(values)
    size = sum(len(canonical_bytes(value)) for value in values)
    if count > 1000 or size > 4 * 1024 * 1024:
        raise SchemaBackfillLimit("本次字段变更需要更新的数据量超过一次保存上限")
    return count, size
```

- [ ] `uv run --directory apps/backend pytest tests/unit/test_project_data_schema.py -q`，先因缺模块/边界行为失败。
- [ ] 实现ApiModel新形状和纯校验/规范序列化；JSON字段只允许现有合法typed值，禁止NaN/Infinity、孤立代理和隐式数字转换。预览的内部prepared记录与公共DataSchemaImpact明确分开。
- [ ] 边界测试分别覆盖1000/1001条、4194304/4194305字节、中英文UTF-8差异、false/0/null/缺失。回填多字段同一行只计一次，计算写后全行JSON；超限整候选拒绝。
- [ ] 重跑unit及Ruff/mypy定向文件，提交 `feat: define atomic table schema candidate contracts`。

## R3-02：守卫迁移与预览证据

**Files:** Modify `apps/backend/src/autoflow/infrastructure/database/project_data_models.py`；Create `apps/backend/src/autoflow/infrastructure/database/migrations/versions/pm02_schema_drafts.py`、`apps/backend/src/autoflow/infrastructure/database/project_data_schema.py`、`apps/backend/tests/integration/test_project_data_schema_migration.py`、`apps/backend/tests/integration/test_project_data_schema_preview.py`。

关键事实：当前 `impactRevision` 是 `DataImpactRow.id`，**不是**随记录变更增长的修订；不能比较两次impact ID来证明数据没变。当前单字段require会重新扫描记录，聚合大表不能把全量校验塞进最终写锁。

选择实现：`DataTableRow.schema_guard_revision` 内部整数初值1，配合SQLite触发器在当前代次记录INSERT/UPDATE/DELETE时同事务加一。保守包含状态更新，不影响公开content/status/linkRevision语义；非当前隐藏候选数据不推进当前守卫。字段/状态目录变动继续依tableRevision，换代次显式比较generation。不是新公共“通用版本”。

- [ ] 先写迁移测试，使用临时DB升至旧 `pm02_excel_exports` 再升新head；原Profile/代理/项目/记录保留，新守卫=1。已存在主线分叉不在此任务偷偷合并。
- [ ] 执行 `uv run --directory apps/backend pytest tests/integration/test_project_data_schema_migration.py -q`，先失败。
- [ ] 模型列使用Integer、nullable=False、default=1、server_default="1"，与迁移一致；新迁移down_revision=`pm02_excel_exports`，执行前核对唯一head；如果已有新迁移，停止该文件写入、由主协调顺序接入，不改已交付迁移。触发器以下插入语义，UPDATE/DELETE分别使用NEW/OLD同一复合范围：

```sql
CREATE TRIGGER project_schema_guard_insert AFTER INSERT ON project_data_records
BEGIN
  UPDATE project_data_tables SET schema_guard_revision = schema_guard_revision + 1
  WHERE id = NEW.table_id AND project_id = NEW.project_id
    AND current_generation = NEW.dataset_generation;
END;
```

- [ ] 迁移追加当前状态计数索引 `(project_id, table_id, dataset_generation, status_id)`，本轮真实消费者是R3-05；downgrade依次删trigger/index/列，不修改旧迁移。测试SQLite真实事务回滚时守卫也回滚、隐藏代次不误推进、旧单条/批状态/删除命令能推进守卫。
- [ ] 预览在一致读事务读取table/field/record和守卫；复用既有spooled校验方法，用户正则等昂贵校验在读事务释放后处理。先验证候选全集和保护规则，再全量检查变化的字段，保留未变字段异常证据。
- [ ] 新clientId对应持久fieldId在预览时分配并存内部prepared映射。回填最多保留1000条/4MiB，其余只计数/形成超限blocker，不无限积累。新必填默认覆盖全部现有记录，非必填无默认不回填；缺失与null语义沿用现有创建规则。
- [ ] 验证完成后的短事务重验tableRevision/generation/schemaGuard，再写DataImpactRow：action=saveTableSchema，target绑定project/table/generation；change_digest=规范candidate摘要；expected_revisions包含table/各field/guard；report内部保存有界回填和ID映射；expires_at沿用10分钟。任何变化则返回影响过期，不能把旧检查发布成新基线。
- [ ] 预览测试包括检查中并发编辑/换代次/批状态、校验失败/超限、过期、未修改异常值保留、记录键不变和源Excel hash不变。运行 `uv run --directory apps/backend pytest tests/integration/test_project_data_schema_migration.py tests/integration/test_project_data_schema_preview.py -q`，提交 `feat: persist schema previews with transactional change guards`。

## R3-03：原子提交与幂等恢复

**Files:** Modify `apps/backend/src/autoflow/infrastructure/database/project_data_schema.py`；Create `apps/backend/src/autoflow/application/project_data/schema.py`、`apps/backend/tests/integration/test_project_data_schema_commit.py`。Read既有 `apps/backend/tests/integration/project_data_catalog.py`、`apps/backend/tests/integration/project_data_impacts.py`、`apps/backend/tests/integration/projects.py`、`apps/backend/tests/integration/domain/projects/models.py`。

仓储类命名 `SqlAlchemyProjectDataSchema`，构造参数为现有session_factory；`preview(project_id, table_id, candidate)`和`commit(project_id, table_id, candidate, impact_revision, operation)`分别持有本任务定义的读/写工作单元。服务层不能在仓储之外自行提交，也不能通过旧HTTP组合。

目标服务：`DataSchemaService.preview(project_id, table_id, candidate)`返回DataSchemaImpact；`commit(project_id, table_id, key, payload)`返回`(result, operation, replay)`，只做规范校验和调仓储。与现有DataCatalogService边界相同，不再引入一层通用引擎。

- [ ] 建立临时DB fixture，沿用 `test_project_data_field_changes.py::ctx` 的ProjectService/DataTableService/DataCatalogService建项目/表方式；新增两字段、两条记录、状态和异常单元格。测试聚合save中第二个字段失败，表/字段/记录/guard/Operation全部回滚。
- [ ] 执行 `uv run --directory apps/backend pytest tests/integration/test_project_data_schema_commit.py -q`，先失败。
- [ ] 仓储单短事务严格按以下顺序实现，不能调用会自行commit的旧create_field/update_field；可提取其纯映射/校验函数复用，但旧端点行为保持：

```text
BEGIN IMMEDIATE
1. 校验当前项目读取归属；查同key Operation，先比规范scope/kind/payload摘要。
   同请求返回原冻结结果（不再比旧revision）；异请求409 OPERATION_PAYLOAD_MISMATCH。
2. 新操作校验active、当前generation/tableRevision、preview身份/用途/有效期/candidate摘要。
3. 比对schema_guard_revision、完整field集合和各fieldRevision；预览blockers必须空。
4. 写入prepared字段/有界记录；每条被回填记录contentRevision只加1，status/link不变。
   变更字段fieldRevision加1，新字段=1；不改变字段则不加。
5. 有真实变化才tableRevision加1；无变化允许完成Operation且不增加修订。
6. 写DataChangeRow及saveTableSchema Operation冻结结果（含clientId→fieldId）。
COMMIT
```

- [ ] 记录值写回始终保留原 `record_slots` 和未改异常证据；原始typed键、状态、环境关联和generation不变。DataChangeRow的operation_id/sequence唯一且覆盖所有实际变更，同一事务写事实。prepared来自可信预览记录，提交仍重新计算有界回填预算与原内容版本，不接受renderer提交的预计算行值。
- [ ] 测试：旧单字段写使聚合preview过期；聚合写使旧单字段CAS失败；预览后内容/状态/删除/重导入均冲突；同key同请求重放新fieldId不变；成功后再次编辑仍返回历史快照；提交后响应丢失通过原项目Operation查询找回；跨项目查询拒绝；并发两个候选只有一个成功。
- [ ] 注入失败分别位于字段写后、记录回填后、Operation写前；不在生产引入fault flag，用SQLAlchemy事件/测试monkeypatch注入。1000/4MiB边界与超限测试全部保留。
- [ ] 重跑schema测试及旧 `test_project_data_catalog.py`、`test_project_data_field_changes.py`、`test_project_data_records.py`（integration目录），确认旧合同无回归。提交 `feat: atomically save bounded table schema drafts`。

## R3-04：HTTP装配、生成类型与前端命令

**Files:** Create `apps/backend/src/autoflow/adapters/http/project_data_schema.py`、`apps/backend/tests/contract/test_project_data_schema.py`、`apps/desktop/src/renderer/domains/project-data/schema-api.ts`、`apps/desktop/src/renderer/domains/project-data/schema-api.test.ts`；Modify `apps/backend/src/autoflow/bootstrap/app.py`、`apps/backend/src/autoflow/adapters/http/project_schemas.py`、`apps/desktop/src/renderer/shared/api/generated.ts`。

POST `/schema`的固定合成请求例（project/table在路由中，Idempotency-Key另传UUID；必须先对相同candidate执行preview得到真实impactRevision）：

```json
{
  "candidate": {
    "datasetGeneration": "11111111-1111-4111-8111-111111111111",
    "expectedTableRevision": 1,
    "fields": [{
      "kind": "new", "clientId": "22222222-2222-4222-8222-222222222222",
      "definition": {"key":"email","name":"邮箱","type":"string","required":false,"validation":{}},
      "sourceColumnPolicy": "localOnly"
    }]
  },
  "impactRevision": 1
}
```

例中数字仅说明JSON类型；contract fixture必须用真实创建表与preview返回值覆盖，不能把1当任意有效确认。响应的action必须是saveSchema，createdFieldIds必须包含该clientId，随后GET fields和Operation查询必须指向同一个持久fieldId。

- [ ] HTTP测试401、跨项目404、归档409/closing423/deleted404、quiesce拒绝、缺key/缺少candidate必填属性422（空表的fields=[]合法，不与缺属性混同）、过期preview409、异payload409、首次/重放200和响应schema完整；不能只测服务函数绕过中间件。
- [ ] 执行 `uv run --directory apps/backend pytest tests/contract/test_project_data_schema.py -q`，路由先404使测试失败。
- [ ] 挂R3-01两个POST真实handler，沿用认证、QuiesceGate、异常封装。ProjectOperationView kind/result联合只新增saveTableSchema/DataSchemaResult，不移除旧成员。预检有持久证据但不是业务成功Operation；响应丢失重新预检无业务副作用，只有commit需要原key恢复。
- [ ] `npm run openapi:generate`，随后 `npm run openapi:check`；生成类型包含两条实际路由，不提前生成PM3未来参数接口。
- [ ] schema-api用createDataCommand调用 `/schema`，新恢复验证同时检查project/table/generation、kind和action，不能信任一个同名字段对象；提交前按现有持久命令方式保存完整candidate+impactRevision+key。返回过期/冲突保留草稿并允许新preview；结果未知只查询，不重建key。
- [ ] 前端测试匹配资源/错资源、同工作区新instance、跨workspace迟到、原key未接受与已接受处理中；复用data-command已有时序，不复制恢复算法。运行 `npm test -- src/renderer/domains/project-data/schema-api.test.ts` 和typecheck、HTTP测试；提交 `feat: expose recoverable schema commands to the desktop`。

## R3-05：真实状态引用投影

**Files:** Modify `apps/backend/src/autoflow/application/project_data/catalog.py`、`apps/backend/src/autoflow/domain/project_data/catalog.py`、`apps/backend/src/autoflow/infrastructure/database/project_data_catalog.py`、`apps/backend/src/autoflow/adapters/http/project_data.py`、`apps/backend/src/autoflow/adapters/http/project_data_catalog_schemas.py`；Create `apps/backend/tests/contract/test_project_data_status_usage.py`；Modify `apps/desktop/src/renderer/domains/project-data/catalog-api.ts`、`apps/desktop/src/renderer/domains/project-data/catalog-api.test.ts`、生成类型。

```ts
type DataStatusUsageDirectory = {
  datasetGeneration: string; calculatedAt: string
  items: Array<{statusId:string; currentRecords:number; activeBatchOperations:number}>
  configurationReferences: { availability:'notImplemented' }
}
```

只统计当前generation记录；批状态引用是不同计数，不相加成记录数；活动批操作既要计算目标statusId，也要计算其冻结记录当前引用的状态。历史墓碑不在活动目录；不依全库历史任务模拟引用。

- [ ] 测试旧代次状态行不计入当前数、null不属于任何状态、当前0确实可返回0、批操作一个status引用只计一次operation、取消/完成后解除活动引用、跨项目拒绝和归档读取可用。
- [ ] `uv run --directory apps/backend pytest tests/contract/test_project_data_status_usage.py -q`，先404失败。
- [ ] 一致读快照执行分组COUNT和活动批操作投影，复用现有删除引用逻辑，避免每状态逐次COUNT；返回明确calculatedAt。GET `/statuses/usage`路由不得被statusId路由误匹配，HTTP测试覆盖。
- [ ] 更新生成类型和catalog-api；UI获取失败显示“引用暂时无法读取”，不回落零。删除仍由现有影响确认守卫最终裁决，列表数字不充当授权。
- [ ] 重跑contract、catalog-api及旧状态删除/批状态测试。提交 `feat: expose current business status usage without synthetic counts`。

## R3-06：字段表格、Drawer与整体草稿

**Files:** Create `apps/desktop/src/renderer/domains/project-data/schema-draft.ts`、`apps/desktop/src/renderer/domains/project-data/schema-draft.test.ts`、`apps/desktop/src/renderer/domains/project-data/use-schema-draft.ts`、`apps/desktop/src/renderer/domains/project-data/use-schema-draft.test.tsx`、`apps/desktop/src/renderer/domains/project-data/components/SchemaEditor.tsx`、`apps/desktop/src/renderer/domains/project-data/components/SchemaEditor.test.tsx`、`apps/desktop/src/renderer/domains/project-data/components/SchemaFieldDrawer.tsx`、`apps/desktop/src/renderer/domains/project-data/components/SchemaImpactDrawer.tsx`；Modify `apps/desktop/src/renderer/domains/project-data/components/FieldEditorDialog.tsx`、`apps/desktop/src/renderer/domains/project-data/pages/DataTableDetailPage.tsx`（均在同project-data目录）。

- [ ] 先写状态转换与组件反例：Drawer应用只改本地candidate，0次HTTP；全页保存才preview→commit；取消Drawer不改父draft；dirty后台刷新不覆盖；只变label保留fieldId；已有字段不能从候选删除；重置恢复当前基线。

```ts
// schema-draft.ts：使用生成的DataSchemaCandidate，不维护第二份DTO。
type SchemaDraftPhase = 'clean' | 'dirty' | 'previewing' | 'confirming' | 'saving' | 'uncertain' | 'conflict'
// clean --edit--> dirty --preview--> confirming --commit--> saving --confirmed--> clean
// 修改候选使旧impactRevision作废；preview失败回dirty；CAS失败到conflict并保留candidate。
// 响应未知到uncertain，冻结已发命令；查询原Operation后才解除，不能偷偷重发。
```

- [ ] `npm test -- src/renderer/domains/project-data/schema-draft.test.ts src/renderer/domains/project-data/components/SchemaEditor.test.tsx`，先失败。
- [ ] 从FieldEditorDialog提取纯字段表单内容用于SchemaFieldDrawer，继续fieldFormSchema校验；外壳用 `<Modal placement="drawer">`，按钮“应用到草稿”，不再在抽屉触发单字段预检或保存。保留旧Dialog兼容消费者直到迁完，最后有调用方扫描才删除无用壳。
- [ ] SchemaEditor用现有Table，显示字段名/键/类型/必填/约束、修改标记，底部重置/保存；无字段删除按钮。影响Drawer显示每字段变化、回填行数和超限阻断、引用未接通提示。默认焦点返回修改/取消，无法确认的候选不放可点击“确认保存”。
- [ ] use-schema-draft绑定稳定workspace/project/table/generation/session，未发草稿与已发命令分开；本地恢复数据先schema验证，跨代次只读保留/可复制，不静默重新映射fieldId。重连刷新事实不reset，旧scope响应不关新Drawer。
- [ ] 表页统一向既有registerLeaveGuard注册聚合保护，避免多个Hook覆盖guard：协调函数先检查任何saving/uncertain，再询问实际dirty表单。内部Drawer关闭保护当前字段draft，离开字段页保护整个schema。关闭影响面板不删除已接受命令。
- [ ] 重跑所有新增组件/Hook、旧FieldEditorDialog、use-data-table-editing及DataTableDetailPage测试，运行typecheck。真实两字段修改→预览→外部改记录→确认冲突→保留draft→重新预检→成功，并查只发生一次整体提交。提交 `feat: compose atomic schema drafts in the field management page`。

## R3-07：状态、来源、设置和文件/批状态画板接入

**Files:** Create `apps/desktop/src/renderer/domains/project-data/components/DataStatusTable.tsx`、`apps/desktop/src/renderer/domains/project-data/components/DataStatusTable.test.tsx`、`apps/desktop/src/renderer/domains/project-data/components/TableSettingsForm.tsx`、`apps/desktop/src/renderer/domains/project-data/components/TableSettingsForm.test.tsx`；Modify `apps/desktop/src/renderer/domains/project-data/pages/DataTableDetailPage.tsx`、`apps/desktop/src/renderer/domains/project-data/components/DataTableSourcePanel.tsx`及其测试、`apps/desktop/src/renderer/domains/project-data/components/ExcelImportWizard.tsx`、`apps/desktop/src/renderer/domains/project-data/components/ExcelExportDialog.tsx`、`apps/desktop/src/renderer/domains/project-data/components/RecordStatusBatchDialog.tsx`及其现有测试（均在同project-data目录）；Read旧项目本轮复用清单。

状态表的展示边界（R3-05生成类型为唯一数据来源）：

```tsx
// currentUsage: DataStatusUsageDirectory | undefined，loadError: string | null。
// 不将未加载/失败映射为0；当前记录数和活动批操作数分列。
<TableCell>
  {loadError ? '引用暂时无法读取' : currentUsage
    ? currentUsage.items.find(item => item.statusId === status.statusId)?.currentRecords ?? '待刷新'
    : '正在读取…'}
</TableCell>
```

`status`来自当前DataStatusDirectory；状态刚创建但旧usage响应尚未刷新时显示待刷新，不能补一个假0。查询key含工作区/实例/表/代次，旧代次usage不与新目录拼接。

- [ ] 测试状态引用加载/错误/真实0分别显示，删除只以影响预检通过允许；settings页内修改有guard而非二次Modal；归档禁编辑/重导入但可导出；接受导入后关闭进度不显示取消成功。
- [ ] 执行 `npm test -- src/renderer/domains/project-data/components/DataStatusTable.test.tsx src/renderer/domains/project-data/components/TableSettingsForm.test.tsx src/renderer/domains/project-data/components/DataTableSourcePanel.test.tsx`，新增布局/交互断言先失败。
- [ ] 状态表组合真实usage查询和现有StatusEditorDialog/DataDeletionDialog；表设置提取DataTableFormDialog字段与验证，改为页内保存/取消，不改tableEdit命令。内置系统状态初始仍为空。
- [ ] 来源卡明确本地/Excel、文件名/工作表/导入时间；更换文件只是启动既有检查向导。按确认补图调整导入六步、导出选列/筛选、批状态进度与部分结果；保留现有持久操作、文件授权和进度查询，不重写服务。
- [ ] 产品文案统一业务状态、未设置、数据已更新；错误按现有code/details归一到可行动中文，未知错误可展开requestId，不能把UUID/Content was modified作为主要反馈。未接通Sheets或引用明确说明，不塞假数量。
- [ ] 重跑上述及ExcelImport/Export/RecordStatusBatch组件测试，真实空白表/文件/批状态流程各走一遍。提交 `refactor: align status source and settings flows with approved prototypes`。

## R3-08：故障、性能与全模块退出

**Files:** Modify `scripts/smoke-project-data.mjs`、`scripts/smoke-pm2-detail-flows.mjs`（适配路由和统一字段保存但不删除原断言）；Create `scripts/smoke-project-alignment.mjs`、`scripts/measure-schema-commit.py`；Create `docs/project-management/design-alignment/acceptance/r3/README.md`、`docs/project-management/design-alignment/acceptance/r3/verification.json`及截图；Modify本轮implementation-ledger及 `.ai/`、`docs/PROJECT_STRUCTURE.md`。

新smoke沿用electron-cdp.mjs的renderer.command/evaluate接口；窗口范围断言：

```js
const layout = await renderer.evaluate(`({
  viewport: { width: innerWidth, height: innerHeight },
  fits: document.documentElement.scrollWidth <= innerWidth + 1,
  recordPage: Boolean(document.querySelector('main [aria-label="记录详情"]')),
  modalCount: document.querySelectorAll('[role="dialog"]').length
})`)
assert.equal(layout.fits, true)
assert.equal(layout.recordPage, true)
assert.equal(layout.modalCount, 0)
```

断言在详情正常状态执行，字段Drawer和确认弹窗另有对应截图；不能把某个隐藏元素当正式页面。导出文件内容与来源hash继续使用现有PM2测试站/工作簿校验，而不是只断言页面出现成功Toast。

- [ ] 新smoke复用`scripts/electron-cdp.mjs`现有Electron/CDP驱动，临时workspace与测试文件；必须从真实表单建立记录/字段，不能HTTP预置代替新增界面验收。HTTP仅用于制造外部CAS冲突或读取事实。
- [ ] 真实链：目录→表→记录整页编辑→返回条件；新增两字段→统一预检→一次保存；状态设置/清空与批部分结果；导入→本地编辑→重新导入→旧引用拒绝；当前筛选选列导出→核对文件→重启查回结果→两个工作区隔离。
- [ ] `measure-schema-commit.py`用临时DB测1000行/4MiB边界、1001行与超字节阻断、1万行无需回填的规则预检。分别记录预检时间、最终BEGIN到COMMIT时间、DB大小、行数、编码字节、并发读响应。性能记录不只报端到端耗时，不用小样本宣称无限大表。
- [ ] 在200%缩放/长字段/长键下截图，检查上下文页头、Popover不撑宽、Drawer内滚动、错误定位、页脚不挡内容、通知不挡表操作、键盘与焦点。选择文件取消、跨frame拒绝等主进程测试保留。
- [ ] 按总计划运行完整pytest/Ruff/mypy、Vitest/OpenAPI/typecheck/lint/build/scripts/structure及三个真实smoke；新脚本执行 `node scripts/smoke-project-alignment.mjs`、`uv run --directory apps/backend python ../../scripts/measure-schema-commit.py`。
- [ ] 每包规格审查→工程审查→修正复核；记录真实失败与修正，不把无截图的项勾通过。Windows/其他架构/打包未执行保持null与原因；本机Electron新截图与原图ID对应。提交 `test: verify aligned project data flows and bounded schema commits`。

完成R3后停在纠偏验收点。PM2历史报告不覆盖，PM3参数/核心合同及迁移汇合按总计划G1处理。
