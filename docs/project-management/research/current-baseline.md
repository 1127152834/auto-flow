# AutoFlow 项目管理现实基线（只读核对）

- 日期：2026-09-12。
- 状态：源码/仓库事实 confirmed（静态）；边界建议 proposed；本轮没有执行应用或测试，不能声称 runtime 通过。
- 主仓根：`/Users/zhangtiancheng/Documents/projects/autoflow`；HEAD `2faf2a037f16555482f7213a13efcd89a009eedd`。
- UI 工作树根：`/Users/zhangtiancheng/Documents/projects/autoflow-ui-controls-plan`；HEAD `1fb58e188c3b1063c86e19d4c6d80bba0ecbe92e`；检查时 clean，尚未进入主仓 HEAD（祖先检查非 0）。
- 以下省略主仓绝对前缀；UI 段路径以 UI 根为前缀。行号为本轮读取的文件行。

## 1. 主仓是什么状态

已经读取 AGENTS.md、.ai/README.md、.ai/memory/project-context.md、docs/PROJECT_STRUCTURE.md、docs/architecture/README.md 以及相关浏览器/设置决策。现任务属于产品/架构设计研究，没有业务实施授权，不修改任何仓库文件。

主仓 modified：`.ai/decisions/2026-09-12-model-management-legacy-parity.md`、`.ai/memory/project-context.md`、`docs/automation-studio/PLAN.md`。untracked：`apps/desktop/src/renderer/domains/automation/`、`docs/automation-studio/{MILESTONES,REVERSE_ENGINEERED_DEVELOPMENT_PLAN,WEBRPA_ENTITY_INVENTORY}.md` 及模型设计/审计文档。以下 Studio 新文档与代码均标 working tree，不当成 2faf2a0 的已提交能力。

前端正式导航是总览、浏览器配置、代理管理、模型管理、设置：`apps/desktop/src/renderer/app/ApplicationHeader.tsx:3`；App 的真实页面装配在 `app/App.tsx:139`、`:144`、`:146`。没有项目管理 route，也没有 Studio import/入口。总览是真实资源概况，6 类资源为配置、已启用代理、代理组、内核、供应商、模型；工作入口仍只有四项资源/设置管理（`domains/dashboard/components/DashboardCards.tsx:4`、`:18`）。没有项目数量、项目运行分析、项目卡片或假项目。

后端领域实际只有 profiles/proxies/kernels/models/settings；application 加 dashboard 占位目录，但 dashboard 实现位于 settings/runtime 的聚合查询。检查 `rg --files`、bootstrap 路由、数据库 ORM 后确认没有项目、环境实例、账号、工作流、运行、调度等领域/表/路由。正向证据为 `apps/backend/src/autoflow/bootstrap/app.py:165`（装配状态）和 `:193`（注册路由），以及 `infrastructure/database/models.py:21` 与 `proxy_models.py:19` 的 ORM 表清单。没有某张表的结论来自全目录搜索，不是单个文件猜测。

当前 workspace 是可切换的本地数据根，包含 SQLite、内核、配置目录、日志，不是业务 Project：`infrastructure/filesystem/paths.py:16`；`.ai/decisions/2026-09-12-desktop-settings-ownership.md:6`。一个 workspace 内组织多个项目可作新提案，但不要把切换项目实现成切换 sidecar/数据根。

## 2. 已有资源与可复用边界

### 浏览器配置、内核、测试浏览器

`domain/profiles/models.py:18` 的 ProfileSpec 包含名称、起始页、locale/timezone、geoip、headless、人性化参数、UA、视口、扩展、专家参数、edition/version/channel、proxy_mode/proxy_id/proxy_pool_id。`Profile:186` 在 spec 外持有 id、fingerprint_seed、时间。配置是全局模板，且保存时校验内核/代理存在与可用（`application/profiles/service.py:120`）。复制会生成新 ID 和新 seed（`:74`）；重置 seed 已持久化（`:84`）。

强约束来自 confirmed 决策 `.ai/decisions/2026-09-12-profile-test-browser.md:10`：配置是参数模板，不拥有日常浏览记录或登录会话；未来项目环境负责持久化实例。`:12` 每份配置一个临时测试会话，正常结束清理；`:29` 状态以后端为准、每秒同步、不同配置独立。

`application/profiles/test_browser.py:33` 已协调已保存配置、已安装内核、代理解析、License、worker；`:51` 防重复启动；`:96` 取消/关闭；`:115` 聚合运行态。`domain/profiles/ports.py:58` 的 launcher 只是测试浏览器端口。

`providers/browser/worker.py:57` 使用 `launch_context_async`；`:63` 可见测试强制 headless=False；`:99` 创建临时 context；`:135` 删除 cache。这不是持久化 profile runtime，不能把“打开测试浏览器已实现”算作账号环境/自动化执行已实现。未来可以复用已安装内核解析、参数校验、凭据保护、proxy relay、进程取消回收基础，但需新持久化实例模型、路径、占用租约和浏览器运行时契约；不建议复制测试浏览器服务做第二个完整引擎。

`domain/profiles/ports.py:47` 与 `application/profiles/service.py:95` 有目录隔离删除/恢复和使用 guard，可借鉴失败恢复；目前没有项目引用检查。模板更新如何影响已建环境、实例 seed 是否独立、批量创建默认如何生成身份，应由新方案明确，不是当前已有功能。

### 代理

已有代理连接、投影、凭据按需读取、健康、组、轮换选择。`application/proxies/groups.py:126` 的 ResolveProxyForProfile 按 request_id 幂等解析组，支持候选健康探测、修订冲突重试和游标提交（`:131–170`）。`bootstrap/proxies.py:90` 是已接入测试浏览器的组/单代理解析，并优先 SOCKS5。

可复用这些资源与选择逻辑，项目只保存引用或分配策略，不新建代理凭据库、代理连通检测、独立轮换调度器。当前引用查询仅 profiles 与代理组：`infrastructure/database/proxies.py:398`、`:497`。新增环境或自动化绑定后必须扩展引用/删除保护，不可假设已有跨项目保护。

### 模型

供应商/本地模型/发现/测试/系统凭据存储已存在。`domain/models/ports.py:14` ModelGateway 只有 discover/test_model，不能宣称具备通用 AI 执行调用或 AI 节点。`adapters/http/models.py:179` 的 `/api/v1/models/options` 可用于新方案资源选择器。

模型删除尚无项目/工作流引用保护：`application/models/service.py:230` 删除供应商（及仓储关联的模型），`:279` 删除模型。新增引用需要校验禁用/失效/删除阻断或明确失效状态；不要将资源列表可选直接等同于可可靠运行。

### 设置、存储、API/缓存

`infrastructure/filesystem/paths.py:16` 统一路径；`bootstrap/app.py:85` 初始化 workspace 与数据库。`.ai/decisions/2026-09-12-desktop-settings-ownership.md:6–10`：Electron 管理本机偏好/数据根/诊断，切换先检查占用、暂停变更、停止旧服务、验证新服务，失败回退；Python 提供运行占用。`application/settings/runtime.py:17` QuiesceGate 与 `:59` SettingsRuntimeService 可继续消费新环境/运行 blocker；当前只汇总内核与测试浏览器进程 blocker（`bootstrap/app.py:157`）。新增执行后必须纳入，防止运行中换工作区。

统一 OpenAPI 类型、ApiClient、ApiProvider/TanStack Query 可继续复用。`app/App.tsx:90`、`:144` 以实际 workspace 作为 React key；同目录重连保留编辑树。Project 切换是业务上下文变化，不能顺手销毁整个资源缓存或切换 workspace。

## 3. Studio 计划与代码事实

以下均 working tree：

- `docs/automation-studio/PLAN.md:14–16`：Studio 无项目管理也可独立创作/执行；Manager 管项目、自动化关系、资源配置、运行分析、数据支撑。
- `PLAN.md:41–45`：Kernel 独立，不 import 项目管理；Manager 在 application 层组合；CloakBrowser 唯一运行时；窗口是界面宿主；共享后端。
- `PLAN.md:74`、`:84–103`：独立窗口先行，未来可停靠；同 automation 一个 Studio 会话；不直接同步完整 React state；切换模式是桌面壳职责。
- `MILESTONES.md:7` 称 M0 盘点完成，但 `:35–40` 验收勾选仍为空；不能把所有冻结/对照门槛自动认定已通过。
- `REVERSE_ENGINEERED_DEVELOPMENT_PLAN.md:3–26` 状态“供评审，仅规划”；此前自动化后端原型已删除，后端应视为未实现，前端/模拟/真实/平台分开验收。它是 PLAN:3 指定的当前实施顺序依据。
- 逆向计划 R0–R9 依次是行为样例冻结、可编辑前端、当前工作流持久化、真实网页流程、逻辑结果调试、完整网页/定位、录制回放、独立跨平台交付、能力扩展/调度、Manager 组合（`:86`、`:107`、`:126`、`:143`、`:164`、`:183`、`:200`、`:217`、`:232`、`:242`）。Manager 当前只能做方案及独立数据切片，不能承诺已可调度/分析真实自动化。
- `WEBRPA_ENTITY_INVENTORY.md:27` 把 ScheduledTask 归后续 Manager/application；`:702` 排除版本/发布；`:712` 项目/调度/分析/资源/权限不得下沉执行器。573 类型是参考源码盘点，不是 AutoFlow 已迁移节点。

唯一 StudioPage（`domains/automation/studio/pages/StudioPage.tsx:25`）是本地 state 演示，只有 5 类候选、固定初始节点、点击添加与选中。`:44`“保存”只 setRunning(false)，“运行”只设本地布尔；`:60` 输入用 defaultValue，不保存到节点配置；`:62` 只显示模拟运行已开始；没有 React Flow、文档序列化/持久化、实际执行、API、日志。`StudioPage.test.tsx:6` 仅测试展示和加一个节点，不能代表 M1/R1 通过。

## 4. 产品级版本库与运行证据的冲突处理（proposed）

`PLAN.md:31` 排除“工作流版本历史、快照、对比和恢复”；`:48` 不做产品级版本管理；`:177` 不建 revision/snapshot/publish/compare 表。`REVERSE...:178` 又明确运行记录必须与工作流版本历史区分。

建议定义：每次运行需要固定已解析参数、资源标识/配置摘要、调用定义摘要以及实际解释/排错必需内容，这是运行证据，不提供可恢复工作流版本、差异对比或发布历史。现有 `Run` 草案 `PLAN.md:182–199` 没有输入/资源/定义固化字段，所以这个设计必须标 proposed 新契约，不写成已确认或已实现。若要求保存整个工作流 JSON 并支持恢复编辑，则实质突破当前排除范围，应单独决策。

核心不得为了 Run 查 Project DB：建议管理层以 ProjectAutomation / ProjectRun 关联 workflowId/runId；Kernel 接收独立运行请求及已经解析的资源/输入，不要求 projectId，Studio 独立使用默认/显式资源即可运行。projectId 最多是上层可选关联元信息。`REVERSE...:240` 要求无 Studio 窗口也能调度，同一运行 application 入口；调度规则管理归 Manager，运行队列/引擎不反向依赖 Manager。以上表名仅建议，并非现有架构契约。

## 5. 最新统一组件分支

UI 根 HEAD 1fb58e1。已有主仓基础 controls，但统一分支比主仓更新，可作为实施依赖候选，不能描述为已合入主线。

最新结果以 `docs/design-system/verification/ui-controls-results.md:3–15` 与 `verification/domain-controls.md:3–14` 为准；`docs/design-system/README.md:3` 仍写 T0–T5、T6–T13 未做，是较旧状态，和最终报告冲突，不取其为最新结论。

可复用：令牌/输入/数字文本/密码/搜索；Button/IconButton；Checkbox/RadioGroup/Switch；Select/Combobox/Autocomplete；ScrollArea；Dialog/AlertDialog/Modal/Drawer；菜单/Tooltip；Tabs/Disclosure；Table/Pagination；Badge/Alert/EmptyState/Skeleton/Progress/Spinner/Toast；FormField 与 FieldGroup。用途可直接覆盖项目列表、环境列表、资源绑定选择器、创建编辑表单、删除确认、运行状态与错误/空态。

`shared/components/ui/table.tsx:3` 是基础语义 Table，并非带完整排序/筛选/列配置的业务 DataTable。`combobox.tsx:11–12` 区分必须选目录项和可自由输入；`:29` 缺失项有不可用回显；`:66` 100 项以上虚拟化。项目资源选择优先 strict Combobox，不容许键入 ID 冒充资源；业务分组/批量操作仍留领域组件。

`verification/domain-controls.md:14` 已收口 Select 唯一入口、FormField render-prop、禁止伪 ChangeEvent；`:33–36` 令牌和浮层层级统一。不要从主线复制旧 select-radix/FormField clone 再造一套。

文档报告该 UI 分支本机自动检查通过，包括 325 测试、类型/lint/build、真实/fixture 页面和 16 组控件检查；这是报告事实，本轮未重跑。`:49–53` 明确 Windows/读屏/实体输入法等人工验收未完成；有 RadioGroup 零间隔合成键盘竞态保留。新项目模块也不能继承“全部平台通过”结论。

## 6. 当前缺口及建议排期边界

缺失：项目实体/列表/生命周期、项目环境持久化实例、账号/身份关联、资源绑定与引用保护、项目自动化关系、运行请求/运行历史/附件/数据输入输出、批次与调度、业务分析。只完成管理页面而没有这些用例和契约不能称成熟模块。

建议先把 Project → Environment（持久化实例）→ 资源引用 的最小闭环作为独立切片，再接已落地的 Workflow/Run 服务。输入队列/业务资产/调度应基于真实业务样例决定最小模型，不默认搭企业权限/审批/分布式调度。项目、资源、自动化和运行各自只有一个事实源；Manager 组合既有全局资源和自动化 API。
