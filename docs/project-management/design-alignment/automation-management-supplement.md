# 自动化管理四页签补充设计

- 日期：2026-09-13
- 状态：**proposed / 原型对齐补充，尚未批准，禁止直接据此开发**
- 范围：补齐项目管理图库没有提供画板的自动化管理四页签；不声称图库存在这些页面，不修改当前 Studio 或 PM3 业务代码。
- 置信度：旧实现事实与当前主线能力为高；迁移建议为待确认。

## 1. 证据边界

图库的自动化模块包含目录、空态、错误和菜单等画板，但没有“基本信息 / 输入数据 / 参数配置 / 运行设置”四页签画板。因此，本文件不从图库推断四页签的视觉细节。交互与字段事实来自旧仓库 `/Users/zhangtiancheng/Documents/projects/browser-automation` 的固定提交 `324748a`，主要证据如下：

| 证据 | 可证明的内容 |
|---|---|
| `autoflow-desktop/src/renderer/features/automations/ManagementWorkspace.tsx` | 四页签布局、一个共享候选草稿、字段、预览、冲突、离开和资源修复交互 |
| `autoflow-desktop/src/renderer/features/automations/management-api.ts` | `get → resolve → save` 请求顺序，以及 automation、plan、数据表和依赖版本 |
| `autoflow-desktop/src/renderer/features/automations/ManagementPreviewDialog.tsx` | 输入预览的固定快照、分页/排序、过期提示及无占用/无写入语义 |
| `autoflow-desktop/backend/src/autoflow/automation_management_schemas.py` | 聚合候选、版本、诊断、candidate token 和画布准入 DTO |
| `autoflow-desktop/backend/src/autoflow/automation_management_service.py` | 聚合校验、引用快照、资源解析、原子保存与冲突判定 |
| `autoflow-desktop/backend/src/autoflow/run_plan_schemas.py`、`run_plan_service.py` | 运行规模、资源、参数覆盖、解析结果、确认和删除影响 |
| `autoflow-desktop/backend/tests/test_automation_management.py`、前端 `management-workspace.test.tsx` | 全成全不写、候选令牌、并发冲突、草稿保留、只读、迟到响应和资源往返反例 |

当前能力只以主项目 `/Users/zhangtiancheng/Documents/projects/autoflow` 的固定提交 `c657073b2a6f7be07f835ed74ca2501bbae6aa66` 为依据；该目录存在未提交 Studio 工作，WIP 只用于发现风险，不作为已经交付的依赖。具体来源是：

| 当前主线源码 | 已确认事实 |
|---|---|
| `apps/backend/src/autoflow/adapters/http/workflow_schemas.py::WorkflowVariable`、`WorkflowDocument` | 文档变量只有名称、类型和值；文档保存 variables、nodes、edges |
| `apps/backend/src/autoflow/domain/workflows/run_validation.py::initial_values`、`prepare_run` | 解析变量初值/依赖并为一次运行形成准备结果 |
| `apps/backend/src/autoflow/application/workflows/runs.py::WorkflowRuns.start` | 按请求摘要幂等，冻结 document/layout/Profile 快照后启动单个核心 Run |
| `apps/desktop/src/shared/automation-studio.ts::AutomationStudioBridge` | 已提交开窗接口无 project/automation/workflow 定位参数，只有离开和转换锁定回调 |

PM3 文档 `docs/superpowers/specs/2026-09-13-project-management-pm3-design.md` 当前为 paused/proposed，其中参数归属方案尚未获用户确认。

## 2. 旧四页签的真实行为

四个 URL 页签共享同一个 `AutomationManagementCandidate`。页签切换只切视图并恢复各自滚动位置，不保存、重取或拆分草稿。页头始终显示“已保存 / 有未保存修改 / 保存中”，只有一个“保存配置”动作。

### 2.1 基本信息

| 区域 | 字段与行为 |
|---|---|
| 工作流信息 | 工作流名称必填，最多36字符；用途说明最多120字符 |
| 类型摘要 | 平台固定显示 Web 浏览器；执行模式固定显示流水线；二者只读 |
| 进入画布 | 无修改且资源准入通过时进入；有草稿时选择继续编辑、放弃修改或保存后进入；缺内核/浏览器配置时返回运行设置的具体字段 |

旧实现把管理名称、说明写回自动化实体，但不会因打开管理页而升级旧配置或修改工作流文档。

### 2.2 输入数据

每项输入具有稳定 `id`、用途/输入名称、项目数据表身份及名称快照、条件列表和条件表达式。可添加多个输入；同一表重复使用时必须提供互不重复且非空的用途。表选择支持搜索和分页，已失效或在当前搜索页之外的旧选择仍显示为“待核对”，不会静默换表。

更换表会清空该输入的筛选条件并要求明确确认；移除输入也要求确认。条件使用稳定字段/状态身份并保存显示名称快照。历史失效条件可以打开并随不相关修改继续保存；新建或实质修改的无效条件被拒绝。服务端同时比较所引用数据表的 revision，避免候选预览后数据结构变化仍被保存。

“预览结果”固定输入草稿、自动化 revision、各数据表 revision 和来源状态。新输入或换表必须先原子保存完整四页签，再预览已保存事实。已保存输入可读取服务端分页结果并临时调整预览排序和页大小；这些预览控件不反写筛选。数据或草稿变化后旧结果保留但标为过期，用户主动按最新草稿重查。预览明确不占用数据、不写业务状态、不同步来源。

### 2.3 参数配置

旧 `AutomationSetting` 的字段为稳定 `id`、名称、说明、类型（文本/数字/开关/日期）、必填、校验规则及默认值。每个参数还可在 RunPlan 中选择：

- `inherit`：使用参数默认值；
- `value`：本工作流固定覆盖，并保存 typed value；
- `empty`：明确使用空值。

参数身份和大小写归一后的名称均须唯一。改类型前提示会清空默认值、校验规则和对应运行覆盖；移除参数保留旧覆盖为“已失效参数值”，用户核对后单项清除，不能后台丢弃。无参数是合法空态，不阻止进入画布。

这里存在必须正视的旧模型耦合：参数“定义”和其默认值位于自动化配置，运行覆盖位于 RunPlan；它不是当前 Studio 文档变量的同一实体，也没有证明适合直接成为新架构的权威模型。

### 2.4 运行设置

| 区域 | 字段与规则 |
|---|---|
| 浏览器内核 | 选择已安装 CloakBrowser 版本与 edition；首次候选可预选全局默认，明确保存后固定；旧方案可显示 Profile 当时实际生效的内核而不修改 Profile |
| 浏览器配置 | 可指定 Profile 或继承项目默认；失效旧引用保留快照并提示修复 |
| 代理 | 继承项目默认、沿用浏览器配置、明确直连、固定代理、代理池；固定资源使用稳定 ID 和名称快照 |
| 执行规模 | 旧实现支持有限/不限处理次数；有限值为正整数，旧默认100；并发为正整数，默认1，有限时不得超过总次数。此处只记录旧事实，新阶段规则见6.2 |
| 资源修复 | 可离开到项目默认资源、Profile、代理或内核管理；完整四页草稿随导航状态带出，返回后重新解析资源 |
| 高级维护 | 已存在 RunPlan 可先读取影响再删除；删除只删方案，保留自动化、业务数据和全局资源 |

旧解析结果区分资源选择来源，返回有效内核、Profile、代理/池、参数有效值、issues、`can_confirm` 与 `confirmation_current`。资源列表支持搜索分页；不可用代理池或失效引用不会被包装成有效选择。

## 3. 保存、预检、冲突与返回合同

旧实现值得迁移的是行为边界，不是旧 DTO 名称：

1. **一个草稿。** 四页签共同编辑一份深复制候选；查询刷新不能覆盖脏草稿。
2. **先解析。** `resolve` 对完整候选做归一化、字段/状态/模型引用校验、资源解析和诊断，返回绑定当前事实的 `candidateToken`。
3. **一次写入。** `save` 携带完全相同的候选和 token，在单一数据库事务内写自动化配置与 RunPlan；任一点失败两者都不变。它不是四次页面 PATCH。
4. **多重并发检查。** 请求比较 automation revision、RunPlan 身份和 revision、各数据表 revision、模型/资源依赖形成的 context token；候选或依赖在 resolve 后变化均返回冲突。
5. **冲突不吃草稿。** UI 读取最新保存内容，与“我的修改”并列摘要；选择采用最新基线时仍保留本地候选，用户再次保存。迟到响应不能覆盖更新的查询快照。
6. **离开保护。** 页签内切换不提示；离开管理区、浏览器前进后退、刷新/关闭及进入画布均保护同一草稿。忙碌期禁止重复提交和离开。
7. **资源修复往返。** 离开到资源管理前冻结候选、数值文本和依赖 revisions；返回只恢复原项目/自动化草稿，并按最新资源重新 resolve。失败时草稿仍保留。
8. **只读可查看。** 归档项目仍能看管理和画布，但 resolve/save 被服务端拒绝；前端禁用写动作不能代替服务端准入。

## 4. 当前 Studio 的能力与缺口

固定主线 `c657073b` 的核心工作流文档已有 `variables` 声明，每项由名称、类型和值组成；`initial_values()` 在每次准备运行时解析声明初值和引用，检查循环，再为运行生成独立变量字典。`WorkflowRuns.start()` 冻结本次 document/layout/Profile 快照。当前 Studio 因而具备“文档变量声明与初值”和“单次核心 Run 快照”的真实能力。文档变量与业务参数是不同身份；这些事实既不构成项目参数合同，也不预先决定参数定义必须归属 Studio。

它目前没有以下已交付事实：

- 没有项目自动化四页签或 `AutomationManagementCandidate`；
- 没有独立于文档变量的项目参数定义、参数稳定 `parameterId` 或启动时参数输入合同；
- 没有项目表输入绑定、条件预览和数据领取；
- 没有 RunPlan 聚合、项目默认资源来源投影或四页签原子保存；
- Studio 开窗合同未证明能按 project/automation/workflow 定位并把草稿安全带回项目页。

当前工作树的 Studio/debug/录制 WIP 不改变上述结论。无论最终参数定义归属哪里，PM3 都不能直接改写 `document.variables[].value` 来代替本次参数快照，因为这样会混淆两种身份，并让并发或历史批次失去独立证据。

## 5. `AutomationSetting` 与新参数权威的取舍

以下为 **proposed，需用户确认**。

### 方案 A：Studio 文档拥有定义，自动化拥有绑定与覆盖（推荐）

- Studio/core 维护稳定 `parameterId`、名称、类型、说明、必填和流程默认值；节点以稳定身份引用。
- 项目自动化只保存该工作流参数的投影版本、自动化默认覆盖及是否允许启动时填写，不再编辑第二份类型定义。
- 启动值优先级为：本次明确提供 → 自动化默认覆盖 → 工作流默认值。`false`、`0`、空字符串和未提供分别处理。
- 参数定义变化使自动化绑定进入待修复；旧名称/类型快照保留供用户识别，不静默转型或删除旧值。

该方案便于让独立 workflow 自带可复用参数契约，并让可执行参数定义随文档快照冻结；它仍需新增稳定参数身份及引用影响，不能把现有变量名称直接升级为 `parameterId`。

### 方案 B：自动化拥有定义，Studio 只消费

接近旧实现，迁移页面较快，而且参数与变量保持不同身份。它不是天然错误；但必须明确 workflow 如何声明所需参数契约、独立复用时从哪里取得定义，以及核心如何在不依赖项目数据库细节的前提下校验和冻结参数。若这些合同完整，方案 B 仍可成立；当前材料尚未给出，因此方案 A 暂为推荐。

### 方案 C：继续把参数当变量初值

无需新模型，但无法区分流程默认、本自动化默认和本次输入，启动会修改流程语义，历史与并发隔离不可证明。拒绝。

确认方案 A 之前，PM3 原设计第5节保持 proposed，任何公共 DTO、迁移和页面都不得按该方案先行冻结。

## 6. 推荐迁移方案

### 6.1 保留的产品行为

- 四个 URL 页签、同一草稿、每页滚动恢复和统一保存状态；视觉外壳采用当前项目顶部导航与项目页签，不复制旧全局框架。
- 输入的稳定身份、多表用途、条件表达式、危险更换确认、快照预览和过期重查。
- 参数的 typed 输入、必填/规则、类型变更影响、孤儿覆盖保留与明确清除。
- 资源选择来源、失效快照、资源修复往返、画布准入定位。
- 完整候选 resolve 后一次原子提交、多 revision/CAS、冲突比较与草稿保留。

### 6.2 必须适配而非照搬

- 旧 `DataModel` 映射为 PM2 `DataTable`、稳定 field/status IDs、dataset generation 与 table/content/impact revisions；不得按名称猜字段或跨代次沿用记录。
- PM3 只允许保存和预览数据输入配置；数据领取、占用和写回到 PM4，不能因旧预览能读记录就提前声称可执行。
- Profile、代理、代理池和内核继续使用当前主线各自的稳定 DTO、revision 与可用性，不复制旧资源表或 resolver。
- RunPlan 中“处理次数/并发”适配为项目 Batch 策略，并遵守已确认阶段规则：PM3-B 参数型批次默认有限1次，零输入或只有可选输入时禁止不限；PM4-C 才交付有必要数据输入的有限/不限完整调度语义。旧默认100和直接以 `iterations=null` 开放不限均不迁移到PM3。
- 旧“进入画布”改为受控 Studio 定位同一 workflow document；管理保存与 Studio 文档保存是两项事实，不能跨窗口偷偷联写。
- 删除 RunPlan 属生命周期/影响能力，按已确认里程碑准入；本补充只记录旧行为，不提前放按钮。

### 6.3 建议的聚合边界

管理候选建议包含：自动化名称/说明、workflow document 关联及期望 revision、输入绑定、参数绑定/默认覆盖、资源策略、Batch 默认策略。`resolveManagement` 在一致读快照中返回 typed diagnostics、依赖 revisions、有效资源摘要、输入预览准入和候选 digest。`saveManagement` 使用 idempotency key、原请求 digest、automation revision、关联 document revision、输入表/代次/结构 revisions、资源 revisions 与 candidate digest，在一个短事务中提交全部项目配置。

预览本身是只读查询，不参加保存事务；响应必须注明 inspectedAt 和所依据的 table generation/revisions。预览过期后保留原结果并要求重查。保存不应遍历或复制数据记录。

## 7. 最小验收证据

实现前只需确认参数权威；执行次数已经由总里程碑 PM3-B/PM4-C 分阶段确定。确认后的第一条完整切片至少证明：

1. 四页签切换、刷新查询、资源修复往返均不丢同一草稿；跨工作区/项目不恢复错误草稿。
2. resolve 后任一 automation/document/table/resource revision 改变，旧 save 都冲突且数据库无半写。
3. 聚合写在 automation、RunPlan/Batch defaults 或绑定写入任一点故障时全回滚；同幂等键同请求返回原结果，不同请求拒绝。
4. 输入换表不会保留旧字段条件；预览不占用、不写状态，代次变化后不能把旧记录当新代次事实。
5. `false`、`0`、空字符串、明确空值和未提供参数均按合同冻结；两次启动互不污染文档默认或彼此输入。
6. 参数改名保持身份，改类型/删除给出引用影响；孤儿覆盖保持可见直到用户清除。
7. 进入 Studio 打开同一文档；保存失败、冲突、取消离开和迟到响应均不丢管理草稿或覆盖新作用域。
8. 归档只读由前后端共同执行；资源缺失允许保存待修复草稿，但阻止进入可运行状态。

## 8. 待用户确认

1. 是否采用方案 A：参数定义由 Studio/core 文档唯一维护，项目自动化只保存绑定、默认覆盖和启动填写策略。
输入预览推荐沿用旧实现：新输入或换表先明确保存完整四页签，再预览已保存事实；不隐式保存。不把可推定的默认选择另列为阻塞问题。若未来需要未保存候选预览，另补候选 digest 与依赖版本合同。

上述设计确认前，本文件只作为旧能力证据与迁移建议，不改变已确认的 PM0–PM2 合同，也不解除 PM3 的 paused 状态。
