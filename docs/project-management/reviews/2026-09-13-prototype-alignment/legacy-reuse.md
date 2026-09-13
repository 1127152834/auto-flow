# 旧项目真实代码复用审计

日期：2026-09-13
状态：confirmed（只读核对旧仓当前文件系统与固定 Git 对象）
来源仓库：`/Users/zhangtiancheng/Documents/projects/browser-automation`
固定版本：`324748abe7095f085b4ffb9467be9cb5c8851a5c`

## 结论

不能把旧仓当前工作树中的大量未提交删除视为固定版本从未实现，也不能把“没有 Batch/Task/CoreRun 执行器”扩大成“没有项目、自动化、运行和资源代码”。

固定版本有以下实现与测试代码：项目 CRUD、归档/恢复/删除影响与并发修订；自动化目录、配置、输入表绑定、字段映射、条件、预览、参数设置；四页签管理草稿的聚合解析与原子保存；每自动化运行方案、项目资源默认、资源候选与有效值解析；Automation 内独立 workflow document 的保存、读取、结构校验和节点目录；概览健康状态及对应前端页面。本轮没有重跑固定版本测试。

固定版本没有实现 PM3 所需的真实 Batch、Task、CoreRun、派发、停止、事件日志和持久环境实例。这部分需要新增，但应适配现有配置模型与交互代码，不能把已完成的管理面整体重写。

## 当前文件系统与固定版本的区别

旧仓当前 HEAD 正是上述固定版本，但工作树有大规模未提交删除。本文所有旧代码路径均相对旧仓根目录，因应用位于子目录，路径都以 `autoflow-desktop/` 开头。正确取证命令例如 `git -C /Users/zhangtiancheng/Documents/projects/browser-automation show 324748a:autoflow-desktop/backend/src/autoflow/project_service.py`。没有把当前缺失文件解释为从未实现。

- 当前文件系统仍存在 `autoflow-desktop/backend/src/autoflow/project_service.py`、`automation_management_service.py`、`run_plan_service.py` 等后端源文件。
- 当前文件系统已经删除全部 `autoflow-desktop/src/renderer/features/automations/*`、`features/project-overview/*`，以及 `test_projects.py`、`test_automation_management.py`、`test_run_plans.py` 等测试。
- `autoflow-desktop/backend/src/autoflow/main.py`、`api.py`、`database.py` 和 `models.py` 有未提交修改/裁剪，所以“源文件仍在”不等于当前旧工作树仍可启动这些路由。
- 固定版本中这些文件、路由、迁移和测试都存在。审计对象是固定版本实现，不是当前被裁剪后的运行状态。

## 项目能力

### 后端代码

- `autoflow-desktop/backend/src/autoflow/models.py:39`：`Project` ORM，持久化名称、说明、状态、revision、最近打开和时间。
- `autoflow-desktop/backend/src/autoflow/project_service.py`：`require_project`、`list_projects`、`recent_projects`、`create_project`、`edit_project`、`open_project`、`archive_project`、`restore_project`、`delete_impact`、`delete_project`。实现名称冲突、revision CAS、活动/归档状态和删除影响。
- `autoflow-desktop/backend/src/autoflow/project_api.py:28`：`create_project_router`；提供列表、recent、create/read/edit/open/archive/restore/delete-impact/delete。
- `autoflow-desktop/backend/src/autoflow/project_overview.py`：`source_summary`、`automation_summary`、`default_resource_issues`、`run_resource_summaries`、`overview`，聚合自动化、数据和资源健康事实。
- `autoflow-desktop/backend/alembic/versions/v2_0002_projects.py`：真实 `projects` 表迁移。

### 前端代码

- `autoflow-desktop/src/renderer/features/projects/ProjectDialog.tsx` 与 `ProjectLifecycle.test.tsx`：创建/编辑、脏草稿关闭保护、保存锁、冲突重读、删除影响与名称确认、分页/搜索/返回恢复、项目快速切换隔离。
- `autoflow-desktop/src/renderer/pages/ProjectWorkspacePage.tsx`：项目工作区及 overview/automations/data 等面板路由。
- `autoflow-desktop/src/renderer/features/project-overview/ProjectOverview.tsx`、`ProjectEmptyPanels.tsx`、`RunPlanReferences.tsx`：真实 overview API、空态、问题优先级、资源修复入口和运行方案引用。

### 测试证据

- `autoflow-desktop/backend/tests/test_projects.py`：11 个测试覆盖真实 CRUD、输入边界、Unicode casefold 唯一、归档、100 项分页、并发写单赢家、事件提交后发布和重启持久化。
- `autoflow-desktop/backend/tests/test_project_overview.py`、`test_overview_run_resources.py`：概览计数、问题、资源默认/继承、隔离和损坏配置降级。
- `autoflow-desktop/src/renderer/features/projects/ProjectLifecycle.test.tsx`：17 个交互测试。
- `autoflow-desktop/src/renderer/features/project-overview/ProjectOverview.test.tsx`：20 个概览状态测试。

### 复用建议

当前实现的 PM1 模型不能直接复制旧数据库代码，但应逐项对照旧行为和测试反例。尤其应复用产品交互：URL 驱动列表、脏草稿保护、revision 冲突不自动重放、删除影响后名称确认、响应 scope 隔离、归档只读。旧 `project_service` 可作为行为参考和测试移植来源，不宜整体粘贴到现有分层架构。

## 项目数据能力

旧数据模块不是静态原型，其固定版本范围在若干方面超过当前 PM2：除本地表、字段、状态、记录和 Excel 外，还包含 SQLite 外部只读来源、Google Sheets 双向同步、身份系统列、写入 journal、后台 scheduler、冲突核验及来源修复。新 PM2 已采用新的 RecordRef、dataset generation、Operation、文件 proof 和分层架构，不能整体搬运旧模块；但旧实现仍是交互、异常语义和测试反例的重要直接来源。

### 后端代码

- `autoflow-desktop/backend/src/autoflow/models.py:53-266`：`DataModel`、`DataField`、`DataStatus`、`DataSourceBinding`、SQLite generation、记录状态/内容版本/变化、managed file、Sheets binding/push batch 等真实 ORM。
- `autoflow-desktop/backend/src/autoflow/data_model_service.py`：`list_models`、`create_model`、`edit_model`、`write_view_settings`、`write_schema`、`write_source`、`remove_source`、`write_status`、`remove_status`、`delete_impact`、`delete_model`，含项目/归档/revision/引用保护。
- `autoflow-desktop/backend/src/autoflow/data_model_api.py`：数据表目录与详情、schema、source、status、delete impact、SQLite inspect/bind、Excel inspect/import、记录查询与状态写入路由。
- `autoflow-desktop/backend/src/autoflow/excel_service.py`：Excel inspect/import、源文件变化检查、托管副本、取消与旧代次保留。
- `autoflow-desktop/backend/src/autoflow/sqlite_service.py`：SQLite inspect/bind、来源 stamp、只读查询、typed filter、记录状态和详情写入。
- `autoflow-desktop/backend/src/autoflow/sheets_service.py`、`sheets_records.py`、`sheets_scheduler.py`、`sheets_push.py`：Sheets staging/publish、身份、记录 CRUD、push journal、重启恢复和后台同步。
- `autoflow-desktop/backend/alembic/versions/v2_0003_data_models.py` 至 `v2_0013_record_identity.py`：数据、来源、同步、写入与记录身份的连续迁移。

### 前端代码

- `autoflow-desktop/src/renderer/pages/ProjectDataPanel.tsx`、`ProjectDataTablePage.tsx`、`ProjectDataRecordPage.tsx`：目录、表详情和记录详情真实页面。
- `autoflow-desktop/src/renderer/features/project-data/DataModelDrawer.tsx`、`DataTableSections.tsx`、`RecordsPanel.tsx`、`RecordView.tsx`、`RecordEditor.tsx`、`FieldSchemaEditor.tsx`：表、记录、字段和状态管理。
- `autoflow-desktop/src/renderer/features/project-data/ExcelImportDialog.tsx`、`ImportPreview.tsx`、`SqliteBindingDialog.tsx`、`SheetsBindingDialog.tsx`、`SheetsSyncPanel.tsx`、`SourceSettingsSection.tsx`：三类来源及同步 UI。
- `autoflow-desktop/src/renderer/features/project-data/useSourceWizardLifecycle.ts`：来源向导的离开、恢复和请求生命周期；配套 focus/lifecycle 测试可移植。

### 测试证据与复用建议

- `autoflow-desktop/backend/tests/test_data_models.py`：空表、唯一名称、字段稳定 ID/顺序/字面键、失败回滚、状态隔离、CAS、归档竞争、删除与事件/重启。
- `autoflow-desktop/backend/tests/test_excel_imports.py`：重新导入新代次、失败保留旧数据、文件变化、重复提交、取消、100k、公式/布尔/数值身份、managed-file ownership 和重启。
- `autoflow-desktop/backend/tests/test_sqlite_sources.py`：外部只读查询、typed identity、分页/筛选、rebind generation、锁超时、100k、跨项目隔离。
- `autoflow-desktop/backend/tests/test_sheets_sync.py` 及 Sheets 专项测试：本地先提交、推送失败重试、unknown verifying、startup reconcile、scheduler 生存、账号/项目隔离、archive fence。
- `autoflow-desktop/src/renderer/features/project-data/project-data.test.tsx`、`record-write.test.tsx`、`record-reliability.test.tsx`、`excel.test.tsx`、`sqlite.test.tsx`、`sheets.test.tsx` 等覆盖实际页面状态。

新 PM2 已经重新实现并强化了 Excel 文件桥、代次、批量状态和导出；应保留新合同作为权威。可直接复用的是旧测试场景、表格/记录交互拆分、来源健康与修复表达。SQLite 与 Sheets 明显超出 PM2 当前 Excel/local 交付，应作为后续包的代码来源，不应被误报为旧项目从未实现，也不应未经身份/事务审查直接接回新数据库。

## 自动化管理能力

### 后端模型与服务

- `autoflow-desktop/backend/src/autoflow/automation_models.py:12`：`AutomationDraft`，项目内 casefold 名称唯一，name 36、description 120、revision、`config_json`，以及独立、deferred 的 `workflow_document`。
- `AutomationDependency`：按 `automation_id/input_id/target_kind/target_id` 建唯一依赖和目标索引，用于表/资源引用影响。
- `AutomationRecoverySnapshot`：按原 revision 保存配置和升级变化，支持旧配置恢复/审计。
- `autoflow-desktop/backend/src/autoflow/automation_service.py`、`automation_v2_service.py`：自动化 CRUD、V1/V2 输入/表/条件/设置写入、引用快照与配置升级。
- `autoflow-desktop/backend/src/autoflow/automation_conditions.py`：封闭条件表达式验证。
- `autoflow-desktop/backend/src/autoflow/automation_preview.py`：`preview`、`preview_table`，读取实际绑定数据并返回预览。
- `autoflow-desktop/backend/src/autoflow/automation_health.py`：配置事实、条件校验、健康标签与 issue 投影。
- `autoflow-desktop/backend/src/autoflow/automation_management_service.py:433-500+`：`read_management`、`resolve_management`、`write_management`；把名称/说明、tables、settings、capacity、configuration 作为一个 candidate，校验 automation/plan/model revisions、context token 和 candidate token，再在一次事务写 Automation 与 RunPlan。
- `autoflow-desktop/backend/src/autoflow/automation_management_api.py`：GET management、POST resolve、PUT write。
- `autoflow-desktop/backend/src/autoflow/automation_api.py`：目录 CRUD、inputs、mapping、conditions、preview、tables、settings、setup、upgrade 路由。
- `autoflow-desktop/backend/alembic/versions/v2_0014_automation_drafts.py`、`v2_0015_automation_recovery.py`：真实 ORM 迁移。

### 已实现的数据结构

- `AutomationManagementCandidate`：`name`、`description`、`tables`、`settings`、`capacity`、`configuration`。
- `AutomationManagementDiagnostic.tab` 已固定为 `basic|inputs|parameters|runtime`，说明四页签不是仅有图片。
- `AutomationTableSelection`：稳定 selection id、model id/name、purpose、conditions、递归 condition expression。
- `AutomationSetting`：稳定 id、name/description（继承 `ProjectCreate`）、value type、required、validation rule、default value；它就是旧实现的参数/设置配置。
- `AutomationManagementVersion`：automation revision、可空 plan id/revision、每表 model revision、context token；`AutomationManagementWrite` 再携 candidate token。
- 旧实现确有 36/120 限制，但这是旧代码事实：`AutomationDraft.name String(36)`、description 120，`AutomationManagementCandidate` 同样约束；不能据此声称新规格已经批准沿用。

### 前端代码

- `autoflow-desktop/src/renderer/features/automations/ManagementWorkspace.tsx`：约 2308 行，真实四页签草稿、resolve→write、资源返回、离开保护、诊断聚焦和 Studio 准入。
- `AutomationDraftProvider.tsx`、`draft-context.ts`：旧版聚合草稿生命周期。
- `V2DraftProvider.tsx`、`V2BasicPage.tsx`、`V2TablesPage.tsx`、`V2FiltersPage.tsx`、`V2SettingsPage.tsx`、`V2Frame.tsx`、`V2Routes.tsx`：此前分步/V2 管理界面。
- `AutomationInputsEditor.tsx`、`AutomationMappingEditor.tsx`、`ConditionExpressionEditor.tsx`、`ManagementPreviewDialog.tsx`：输入、映射、递归条件与预览控件。
- `AutomationListPanel.tsx`、`AutomationActionsMenu.tsx`：自动化目录、搜索排序分页、返回和动作菜单。

### 测试证据

- `autoflow-desktop/backend/tests/test_automation_management.py`：16 个测试，覆盖四页签聚合保存、冲突/flush/commit 回滚、资源变化、输入/参数/容量/有效资源、归档只读、历史非法配置保留、递归条件、候选 token CAS、计划与表 revision 独立冲突、null kernel 可保存但阻止画布。
- `test_automation_preview.py`、`test_automation_v2.py`、`test_automations.py`、`test_automation_redesign_contract.py`：预览、V2 配置、CRUD、引用/修复和合同。
- `management-workspace.test.tsx`：至少 25 个测试，覆盖四 URL 页签共享草稿、scroll 恢复、后台 refetch 不覆盖 dirty、resolve 后原子保存、unmount/迟到响应撤权、输入破坏影响确认、同表不同用途、参数删除/改型影响、字段级错误聚焦、资源修复返回。

### 复用建议

优先适配 `AutomationManagementCandidate`、resolve/write 两阶段和测试反例，而不是重新设计四个相互独立的保存 API。现有 PM3 新契约可将旧 model/table 身份映射到新 `InputPlan`，将旧 settings 映射到最终确认后的参数引用/默认覆盖，但必须保留 stable id、revision closure、candidate token、原子保存及脏草稿隔离。前端组件应按现应用 design system 改造，业务交互与测试可直接移植。

## Workflow 文档能力

- `autoflow-desktop/backend/src/autoflow/workflow_service.py`：`validate_document`、`read_workflow`、`write_workflow`、`validate_workflow`、`workflow_catalog`。
- `autoflow-desktop/backend/src/autoflow/workflow_api.py`：GET/PUT workflow、POST validate、GET catalog。
- `autoflow-desktop/backend/alembic/versions/v2_0018_workflow_document.py`：给 `automation_drafts` 添加独立 JSON 列。
- `autoflow-desktop/backend/tests/test_workflow_api.py`：结构与未知节点保存、存储 envelope/大小/深度/数值边界、语义连接诊断、项目隔离、归档 CAS、事件、commit rollback、重启持久化。
- `autoflow-desktop/src/renderer/features/workflow-studio/WorkflowStudio.tsx` 及 store/document/sequence 测试：实际编辑器文档交互。

复用限制：旧 workflow document 从属于 Automation 行，不满足新规格中“独立 Studio workflowId、同一文档可显式关联、管理与 Studio 各自 revision”的身份模型。校验器、JSON 边界、未知字段无损保存、事件与冲突测试值得移植；外键/所有权模型需要适配，不能原样复用。

## 运行方案与资源能力

### 后端代码

- `autoflow-desktop/backend/src/autoflow/run_plan_models.py:12`：每个 Automation 唯一 `RunPlan`，name/description/revision/config、confirmed_at 和 confirmation_digest；`ProjectResourceDefaults` 持久化项目级资源默认及 revision。
- `autoflow-desktop/backend/src/autoflow/run_plan_service.py`：`read_plan`、`create_run_plan`、`write_capacity`、`snapshot_resources`、`snapshot_configuration`、`write_configuration`、`resolve_plan`、`confirm_plan`、`delete_plan`、`delete_impact`、`defaults_read/write`、`resource_options`。
- `autoflow-desktop/backend/src/autoflow/run_plan_resolver.py`：资源语义 digest/token、项目默认、Profile/Proxy/Pool/Model 当前事实、kernel 解析、配置设置解析。
- `autoflow-desktop/backend/src/autoflow/run_plan_api.py`：GET/POST plan，PUT capacity/configuration，POST resolve/confirm，delete-impact/delete，项目 resource-defaults resolve/write 与 resource-options。
- `autoflow-desktop/backend/alembic/versions/v2_0016_run_plans.py`：`run_plans`、`project_resource_defaults` 表。

### 已实现语义

- `RunCapacity.iterations` 默认 100、可 null 表示不限，concurrency 默认 1，严格正整数且不得超过有限 iterations。
- `RunResources` 支持 profile、proxy inherit/profile/none/fixed/pool、kernel 快照和 pinned 标志。
- `RunSettingOverride` 支持 inherit/value/empty，保留 0/false/空等标量区别。
- `RunPlanResolved` 给出 candidate token、profile/proxy 来源、context token、issues、有效 kernel/profile/proxy/pool/settings、canConfirm 和 confirmationCurrent。
- 资源名称只是快照；保存和确认使用稳定资源 id、revision/token，防止按名字重绑。

### 前端与测试

- `autoflow-desktop/src/renderer/features/run-plan/*`：`RunPlanEntry`、`PlanSummary`、资源默认编辑、资源修复返回草稿、API client。
- `autoflow-desktop/src/renderer/pages/RunPlanPage.tsx`：独立运行方案页面。
- `autoflow-desktop/backend/tests/test_run_plans.py`：容量边界、候选 token、纯读不触碰业务表、名称变化不误伤确认、伪造引用拒绝、cascade、依赖闭包、默认影响和真实导入后确认。
- `test_run_plan_contract.py`：资源解析及并发/冲突合同；`test_run_plan_acceptance.py`：非有限数和 override 模式；`test_run_plan_migration.py`、`test_run_plan_process_token.py`、`test_run_plan_resource_events.py`：迁移、跨进程 token、资源事件。
- `run-plan.test.tsx`、`resource-defaults.test.tsx`、`navigation-state.test.tsx`：有限/不限、窄视口、草稿、归档、资源返回与导航。

### 复用建议

资源选择器、解析器、候选 token、稳定引用、项目默认继承、修复返回草稿和测试可以直接作为 PM3 适配来源。新规则的环境身份来源、代理优先链、maxLiveInstances、超时及停止政策超出旧 RunPlan，需要扩展。旧默认 iterations=100 与新 PM3 参数型默认 1 冲突，不能照搬。

## 真实运行、状态与停止能力

固定版本中没有 `Batch`、`Task`、`CoreRun`、持久环境或环境实例 ORM；没有 `/batches`、`/tasks`、start/dispatch/stop/force-stop/run events 路由。代码检索只命中 `RunPlan` 配置，不是执行记录。`ProjectOverview` 的 run resource summary 也是运行配置健康投影，不是运行状态。

因此下列能力仍需新增：Batch/Task/CoreRun 原子接受，prepared workflow content，提交后派发，稳定 operation/runRequestId，真实状态机，停止/强停、execution generation 撤权，日志/事件补读，未知恢复和 Quiesce blocker。

这项缺口不能反向抹掉前述已实现的运行方案与资源配置。准确说法应是：“旧项目有成熟的运行前配置和确认面，没有真实批次执行器。”

## 环境能力

固定版本没有项目持久 `Environment`、临时 `EnvironmentInstance`、人工现场或保存/恢复环境的领域模型与 API。已有的相关实现是：

- Profile、Proxy、ProxyPool、ModelProvider ORM 与服务；
- RunPlan 中 Profile/代理/代理池/kernel 的选择、项目默认、有效值解析、缺失/禁用问题；
- 全局 kernel manager 和 CloakBrowser provider 基础适配器；
- overview 对资源问题的投影及修复导航。

这些可以复用作资源目录读取和新建环境的种子选择，但不能声称已实现每 Task 隔离实例、持久来源 generation、独占、停止核验或 End 保存。

## 对新实施计划的直接修正

1. PM3-A 不应从空白重建自动化管理。先把旧 `AutomationManagementCandidate`、resolve/write、四页签草稿和测试映射到新分层及新 DTO。
2. 参数合同裁定应先核对旧 `AutomationSetting`：旧代码已经把参数/设置作为 Automation 管理配置，支持 stable id、type、required、validation/default 和改型/删除影响。若改为 Studio 唯一参数定义，必须明确迁移与合同变更，不能称旧项目没有参数模型。
3. 运行设置应适配旧 `RunPlan`/resolver；保留 candidate token、resource id、来源展示和修复返回。替换旧 iterations 默认 100，并补环境身份/超时/停止字段。
4. Workflow 需要身份模型迁移，但校验、文档无损保存、大小/数值边界和冲突测试应复用。
5. PM3-B/C 的 Batch/Task/CoreRun 是真实新增范围；它应消费已适配的 Automation 与 RunPlan，而不是再造第二套管理配置。
6. 旧前端虽在当前工作树被删除，固定版本中有大量可恢复代码和交互测试。应通过 `git show 324748a:<path>` 或独立 checkout 提取，避免直接恢复旧仓全部未提交删除并污染当前工作。

## 验证方式与限制

本审计执行了固定 HEAD 文件清单、当前工作树状态、固定对象源码/符号/路由/迁移/测试名检查，并对关键 schema 和 ORM 逐行读取。没有在旧仓当前工作树运行测试：测试文件和大量装配已被未提交删除，直接运行只会验证裁剪后的工作树，不能验证固定版本。上述“测试证据”表示固定提交包含具体可执行测试及其断言范围，不冒充本轮重跑通过。
