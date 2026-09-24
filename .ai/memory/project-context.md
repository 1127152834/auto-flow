# 项目上下文

- 项目：AutoFlow
- 目标平台：Windows、macOS
- 目标：在新架构中迁移 browser-automation 的功能；项目管理已形成完整设计，PM1项目入口在独立实施分支交付；之后按用户验收逐阶段实施。
- WebRPA：仅作为能力和实现思路参考，重写能力，不做运行时集成或兼容层。
- 前端视觉方向：保留第三个原型的暖灰画布、黏土棕强调色；2026-09-12 用户明确浏览器配置采用单主内容区，无模块侧栏，内核管理从配置表单以弹窗进入。早期该模块“分栏工作台”的描述已 superseded。
- 前端技术约束：React、shadcn/ui、Tailwind CSS，组件先于页面。
- 协作要求：先规格和实施计划，经确认后再开始功能实现；前后端按垂直功能切片一起开发。
- 2026-09-12（confirmed，来源：用户在项目管理审查后的明确纠正）：项目管理先形成相对完整的功能规格、跨模块业务规则、交互和总体实施计划，再小步开发。最小执行链仅是实施验收步骤；关键业务设计不留到各切片开发时临时决定。详见 `.ai/decisions/2026-09-12-project-management-complete-design-first.md`。
- 2026-09-12（confirmed，来源：用户对数据流与环境保留的明确说明）：每表系统维护业务状态；记录再次使用由当前状态和工作流条件决定，不能加消费类型或本批历史排除。工作流可读写多表、增删记录与字段/列，显式决定业务状态变化。结束节点“保留当前环境”包含保存登录上下文并关联相关数据行，不要求额外 Bind 节点。具体关联范围、冲突和恢复为设计推荐；见 `.ai/decisions/2026-09-12-project-data-workflow-semantics.md` 和 `docs/project-management/design/README.md`。此前冲突建议已 superseded。
- 2026-09-13（confirmed，来源：用户对完整设计稿回复“没问题”并要求里程碑计划）：`906deda` 完整设计作为规划基线，包括已有推荐的空白本地表、单表 XLSX 导出和失败后续快捷入口。当前仍只规划，PM0–PM9覆盖全模块，Studio能力按具体契约衔接；见 `.ai/decisions/2026-09-13-project-management-design-approved.md` 与 `docs/superpowers/plans/2026-09-13-project-management-milestones.md`。
- 2026-09-12（confirmed，来源：用户明确实施指令）：代理模块已从 `codex/proxy-management@0ad2fd2` 选择性接入浏览器主线；全局导航和浏览器启动到代理组的调用仍由后续浏览器任务完成。详见 `docs/migration/proxy-management-status.md`。

- 2026-09-12（confirmed，来源：本轮用户授权及隔离worktree验收）：模型管理在 `codex/model-management` / `../autoflow-model-management` 实现，已通过baseline合并验收；保留旧供应商左栏、三步接入与split编辑，凭据仅写系统存储。验收边界见 `docs/migration/model-management-verification.md`。

- 2026-09-12（confirmed，来源：用户合并指令与隔离合并测试）：模型与代理迁移通过0003_merge_proxy_models汇合；不得改写两边已存在的0002版本。接入浏览器客户端06153ca及代理预算修复4a91407后，304个后端、128个前端测试通过，合并边界见docs/migration/model-management-baseline-merge.md。

- 2026-09-12（confirmed，来源：用户对模型选择、模型列表和设计理念的补充要求）：模型管理进入整体重设计研究，参考成熟产品的任务组织与设计语言；旧布局是现有实现记录，不再限制提出新方案。具体新布局尚为 proposed，见 docs/prototype/model-management/redesign-brief.md。继续先原型与规格、后实施，沿用 shadcn/ui + Tailwind。

- 2026-09-12（confirmed，来源：用户最新范围收缩指令）：上一条整体重设计方向 superseded；用户取消原型和整体 UI 改造，认可现有布局，只调整模型管理首页的模型数量提示位置。重设计简报仅留历史，不继续出图或实施其信息架构。

- 2026-09-12（confirmed，来源：浏览器计划 Task1–10 独立复审及源代码）：浏览器 UI 使用 desktop shared shadcn/Radix + Tailwind、领域组件、RHF/Zod；查询上下文统一 ApiProvider。同一工作区重连保留编辑树，实际换目录才重置。CloakBrowser wrapper 固定0.5.9，只有其内核能力；后端 worker 处理下载与取消，License 使用共享系统凭据存储。最终页面/平台状态见 docs/migration/browser-management-validation.md。

- 2026-09-12（confirmed，来源：授权实网、脱敏 fixture 和 CUA）：ProxyPanel 列表/凭据/到期字段已接通；SOCKS5 检测通过，HTTP CONNECT 实网超时。数据面密码按需取用且不落库，API Key 保留系统存储。旧“列表一律拒绝”的限制 superseded；远程管理写操作仍未实现。见 docs/migration/proxypanel-live-verification.md。

- 2026-09-13（confirmed，来源：用户明确实施PM0计划）：整体里程碑及PM0执行已授权，旧“当前只规划”的阶段描述 superseded。先在codex/project-management-design完成契约、传输、FX-01–07及覆盖账本，逐里程碑用户验收；PM1才交付页面/API。主目录Studio M1在交付前提交为b2e95b3，包含工作流文档CRUD和0005迁移；旧“只有about:blank/全为WIP”的当前事实 superseded，Run仍不可执行。见 `.ai/decisions/2026-09-13-project-management-pm0-authorized.md`。

- 2026-09-13（confirmed，来源：用户PM1实施授权、真实源码与自动/本机Electron验证）：`codex/project-management-pm1`从1f80f97+PM0构建，已实现项目目录/表单/上下文和10项HTTP；pm01_projects从0005派生，两张表原子保存项目与幂等快照。其余业务能力明确notImplemented。统一控件选择性接入1fb58e1，保留最新基线Studio M1与会话桥；没有第二执行器。见PM1执行卡和机器核验。PM1等待用户验收，旧“项目尚无业务实现”的当前描述superseded，PM2+未开始。

- 2026-09-13（superseded，历史用户持续目标；已被后续 PM2 修订计划覆盖）：PM2–PM9曾授权在独立implementation工作区持续实施，旧逐阶段暂停规则superseded；排除画布编辑器，保留真实核心运行依赖。PM2执行卡已建立，业务实现尚未验收。

- 2026-09-13（confirmed，实际源码与独立审查）：PM2基础包已交付typed身份、原子持久结构、XLSX流式适配、表资料API与组件，字段/状态目录进入真实HTTP集成，字段影响确认已有持久事实绑定。完整记录、五页签、文件IPC仍实施中。主线9490924现有正式Studio M2，旧“核心仍全部WIP”现状superseded；实施分支尚未接入，PM3须核对契约与0006/pm02迁移汇合。证据见pm2-review-foundation.md及current-baseline.md。

- 2026-09-13（confirmed，实际源码/独立审查/自动验证）：PM2记录create/get/update/显式状态与字段影响preview/PATCH已由cc86607、3630e78、7a2986f交付；670后端全量及最后类型增量33定向、461前端回归通过。仍无正式数据页面、文件IPC或运行闭环；详见pm2-records-fields-verification.json，不将基础命令等同完整PM2。

- 2026-09-13（confirmed，提交及核验）：PM2服务端记录筛选/排序/分页和16项数据HTTP已交付，字段/状态客户端与状态组件已提交；最后查询连接池清理竞态修复后698后端/490前端全量通过。最新报告pm2-query-editor-verification.json；尚无正式数据页面/Excel IPC/批状态，不得宣布PM2完成。B2主进程/内部通道盘点完成，旧picker直接返path不能照搬。

- 2026-09-13（confirmed，实际代码/独立审查/最终自动验证）：PM2记录客户端、共享命令恢复、四类型值编辑、字段影响编辑、冻结记录草稿与记录表格已提交至737ce3e；最终564前端/86文件通过，typecheck/lint/build及OpenAPI/scripts/structure通过。后端本轮无源码变化，698测试仍指上轮报告。正式数据五页签和文件IPC尚未挂载，PM2不完整；最新pm2-editors-verification.json，继续C2/删除与耐久批状态/B2。状态删除不能物理清除历史FK引用，下一包采用软删除保持历史事实。

- 2026-09-13（confirmed，实际代码与自动/隔离Electron核验）：PM2状态历史墓碑和删除HTTP已交付，head pm02_status_tombstones；正式数据目录与五页签读取已接通。719后端/606前端及本机macOS arm64目录创建/编辑/冲突/重连/重启、已有模块回归通过。旧“正式数据页未挂载”当前结论superseded；记录/字段/状态写UI、批状态、Excel发布仍待C2c/A2h/B2完成，PM2整体未完成。报告pm2-directory-deletions-verification.json；后续共享命令每次原key重发须动态校验scope/只读准入。

- 2026-09-13（confirmed，来源：用户后续批准 PM2 修订实施计划）：当前只实施 PM2，完成后停在 PM2 验收点，不自动进入 PM3。此前连续实施 PM2–PM9 的授权记录已 superseded。原编辑任务六个 WIP 文件仍等待原任务提交；后续接管须依据明确交接。现有组件、后台及目录导入证据不替代详情页完整验收。

- 2026-09-13（confirmed，用户明确交接）：原编辑任务已结束，原六个 WIP 正式由当前任务接管，保留后完成 PM2 集成和验收。此前等待原任务提交的阻塞已解除，PM2 完成后仍不自动进入 PM3。

## PM2 本机完整交付（2026-09-13，confirmed）

来源：pm2-verification.json、四组真实Electron验收。用户确认原编辑任务结束后已完成整合；旧等待记录superseded。记录/字段/状态/表资料编辑、批状态、Excel新建/替换/导出及恢复已接通真实页面。760后端、833前端全量与工程检查通过。编辑命令先持久化再HTTP，稳定工作区身份恢复，旧代次拒绝串写，脏草稿不能静默切代。10000行界面导入4396ms/翻页158ms仅本机单次实测。Windows/x64/打包未执行；原生面板与全流程测试注入范围分开。完成后停PM2验收，不开始PM3；主线Studio迁移分叉仍需后续集成。

2026-09-13最终只读核对主项目HEAD为2b5365e（Studio条件/循环/变量等已继续推进），并有其他任务WIP；此实施分支未合并这些内容。后续主线集成须重新核对实际迁移/共享类型/Studio能力，不把旧M2快照作为现状。数据能力契约最终仅data=available，其余五项未实现；修正提交d05bbe1。

## 项目管理原型对齐复审（2026-09-13，confirmed）

来源：用户指定主项目 gallery.html 要求重新对齐，并明确“导航按照现状，用顶部导航，不要换成侧边”。当前暂停PM3草案的实施推进。PM2功能核验保留，不能将它解释为原型视觉已验收。已确认记录筛选常驻、详情Modal/整页缺失、编辑载体、字段卡片等实际偏差；纠偏建议尚待形成完整对齐规格与确认。旧仓324748a的autoflow-desktop内有自动化四页签/聚合保存/资源解析/项目数据实现与测试代码，应先提取适配，不能因当前工作树删除而判定从未实现。报告见docs/project-management/reviews/2026-09-13-prototype-alignment/README.md；原型112个唯一内容只实际视觉复核20张，本次7张应用截图不是全模块验收。

## 项目管理完整对齐规格（2026-09-13）

来源：`docs/project-management/design-alignment/`及完整prototype-alignment-design规格。confirmed：已看最新阅读集91张和同日候选2张，19历史排除；前轮20图审阅是历史记录，不再代表累计覆盖。顶部全局导航保留；目录卡片、独立记录详情/编辑、字段统一草稿为对齐方向。环境“删除影响预览”原图实际是完成页，不能替代预检。PM2已实现文件/批状态能力保留，字段删除仍未实现；当前外链桥仍需补。

proposed：本轮完整规格尚未确认，6组补图未生成；参数定义归Studio/core、聚合字段提交及其有界回填预算是建议，不得当已批准能力。R1–R3纠偏可独立于参数裁定；R4/PM3须先裁定稳定参数身份/快照/覆盖并同步PM0 DTO。未知操作先查询由已批准PM1/PM2规则明确，本轮只勘误PM0旧文案，不改历史报告。没有新增业务实现或跨平台验证。

## 对齐设计批准与执行计划（2026-09-13，confirmed）

来源：用户“ok没问题，开始设计后续实施计划”及 `.ai/decisions/2026-09-13-project-alignment-design-approved.md`。4688353设计的推荐参数权威和有界聚合回填已确认，旧“待用户确认”当前状态superseded；缺图/业务实现不因此完成。已形成B0+R1/R2/R3三个切片计划，主入口`docs/superpowers/plans/2026-09-13-project-management-alignment-implementation.md`。本轮仅文档；PM3保留工程准入，参数归属不再阻塞用户决策。

## 原始Gallery直接还原（2026-09-13，confirmed）

用户明确只有全局左菜单改现有顶部导航，其他页面布局/交互跟随gallery具体原PNG。B0衍生图不再是视觉依据；“B0视觉通过”等当前交付解释superseded，功能证据仍只适用其原版本。R1视觉重开，R2部分实现且视觉未通过，R3未完成。当前修订计划与边界见 `.ai/decisions/2026-09-13-project-gallery-only-navigation-change.md`。原图索引共112文件，latest91；本轮重新看17图，其余不冒称再次视觉审阅。


### Gallery G0 执行记录（2026-09-13，confirmed）

用户已授权连续执行。共享Frame及页面装配完成；真实表名面包屑、200%页签换行与保存栏可见性修正。run-AatYpG真实隔离应用14项smoke通过，规格与工程问题闭合。这里只验收共用结构，R1目录与查询、R2原表单/详情、R3聚合字段仍需继续；单字段截图及B0历史评分不能证明全页还原。详见docs/project-management/design-alignment/acceptance/gallery-g0/review.md。

### Gallery R1 退出（2026-09-14，confirmed）

来源：acceptance/gallery-r1/machine-report.json、review.md及原PNG并排。a6a0e8e恢复原目录、项目头、同卡片记录表/工具/查询Popover；997前端测试、32后端定向及真实E2E通过，原图逐页至少85且硬结构通过。R1可进入R2，但用户手动/Windows/打包未执行，不能解释为项目管理全部完成。R2继续原003–007全页与确认；R3聚合字段仍待实施，PM3不在授权推进范围。

### Gallery R2 退出（2026-09-14，confirmed）

来源：acceptance/gallery-r2/machine-report.json、review.md、run-msXqcI真实E2E及原003–007。实现a08c2fe，保留真实typed身份/单命令恢复，通栏新增编辑、自有日历、详情左右区、居中未保存/删除确认。127文件1030前端、38后端、29脚本、3结构及PM2回归通过；逐页86/88/89/91/88。原生http/https外链已验证；原生文件面板完整闭环、R3、Windows、打包、用户手测未执行。连续授权允许进入R3，不进入PM3。

### Gallery R3 实现与验收证据（2026-09-14，confirmed）

来源：本实施分支e467035/b2d1543/800fb01、`docs/project-management/design-alignment/acceptance/gallery-r3/`。R3已实现原008/009/100/010/012/014结构、完整字段草稿及原子保存、真实状态引用、来源和设置。853后端/1126前端、33脚本/3结构与工程检查通过；真实120条部分结果修复了仓储已提交但HTTP拒绝details导致500、结果选择数清零的实际问题。最终同版本截图和回归见machine-report，不将历史B0或小测试冒称完整视觉验收。

原生Excel完整链实际操作于build3，文件实现后续未改；最终build6使用独立真实IPC/HTTP/SQLite文件回归并明确E4选择注入。Windows、其他架构、打包版本和用户手测未执行。记录`gallery-delivery.md`作为统一交付入口，R3后停止，PM3未开始。旧“R3仍未实施”的当前描述由本节取代；旧报告自身不改写。

## 行内新增记录侧分支（2026-09-14，confirmed）

来源：侧对话用户选择“行尾连续录入”并授权实施；分支 codex/record-grid-entry，基线 a6a0e8e。正常新增改为同表草稿行及一次有界原子保存，旧编辑和旧 pending 恢复保留。这只变更新增交互，不替代父任务其他页面设计。实现与候选证据位于该独立分支，未合并主线；G4 组合恢复 E2E、原生输入法及独立视觉评分仍待完成。


## 主项目整合：行内新增与 R2/R3（2026-09-14，confirmed 代码范围）

来源：`361d4fd`、`dcb1831` 与主线 `cda081d` 的整合。保留最新 WebRPA Studio 前端及其独立窗口，不恢复已退役的 Studio 后端执行器。正常新增记录使用同表草稿行和批量保存；已有记录继续详情/编辑页面，字段继续 R3 聚合草稿与原子保存。本节替代前述“行内新增尚未合入”“Studio/PM迁移尚未汇合”的当前状态；历史报告保持原样，旧 G4 未验收项目不自动转为通过。

- `bootstrap/project_http_routes.py` 同时供真实应用与无副作用 OpenAPI 导出注册项目路由。
- `0009_merge_project_data` 汇合 `0008_workflow_debug` 与 `pm02_schema_drafts`，不重写历史迁移。
- `app/ApiProvider` 每个工作区维持一个 QueryClient；服务重连按实例隔离查询键并刷新活动查询，避免既有 observer 与新缓存分离，保留本地草稿；工作区变化由 App 的 workspace key 隔离。
- 合并核验见 `docs/project-management/design-alignment/acceptance/main-integration/`；源分支保留。


## PM3 独立分支持久执行契约（2026-09-15，confirmed）

来源：`docs/project-management/implementation/pm3/task3-verification.json`。用户已批准 PM3 计划并多次授权继续，历史“不进入 PM3”不再是当前授权边界。工作区固定 `autoflow-project-management-pm3`，主目录只读。Task 2 当前 WebRPA 文档已提交 ffa8df2；Task 3 PreparedContent/CoreRun/RunEvent 与 0011 迁移完成双审、1193 后端测试及工程检查。有历史证据时禁止有损降级；旧只读快照可查询但不能派发。当前进入 Task 4 真实 CloakBrowser worker；不能将持久契约验收冒称网页执行/前端或整个 PM3 通过。

## PM3 管理功能优先（2026-09-15，confirmed）

来源：用户明确调整执行组织，随后排除 Studio demo 联合测试。保留 Task 2/3 与 Task 4 有效成果；自动化管理后端与组件并行推进，原执行卡更新顺序和责任。Studio transport/画布/bridge 联调暂停，不作为管理验收前置。真实管理页面 E2E、截图以及管理端运行所需幂等/原子性/停止/撤权/恢复不变。先完成 Studio 保存运行 UI 的旧门槛 superseded，历史证据保留；不进入 PM4。

### 2026-09-15 PM3 管理配置优先（confirmed）

用户明确 Studio 是 demo，不做联合测试。管理自动化配置持久化、五项 HTTP 与操作恢复已装配；只读工作流目录来自 WorkflowService，不能当作 Studio 集成。当时 resource/capability 适配未完成；resource 在后续 d28dca7 接入，此旧 resource 结论 superseded，capability 仍未接入，因此不把保存配置展示为运行可用。详见 PM3 原执行卡及 management-backend-verification.json。主项目仍只读。

### 2026-09-15 PM3 管理配置接入（confirmed）

来源：PM3 独立工作区代码、管理 HTTP contract 与 `docs/project-management/implementation/pm3/management-runs/run-eSwQYK/result.json`。

- 用户明确取消 Studio demo 联合测试。管理目录/四页签通过真实工作流 ID 关联；QA 工作流经真实服务准备，不伪造 Studio 保存或运行结果。
- 管理界面在 `renderer/domains/project-automations`；查询按工作区/实例/项目隔离，命令恢复身份按工作区/项目/表单持久保存。参数说明保持可省略，模型选择有省略/null/指定三态。
- 内层筛选/排序草稿必须参与外层 dirty/valid 与 resetKey，不能以应用前的旧查询提交整体配置。业务字段查询仅用已绑定字段；状态与系统排序不依赖绑定。
- 项目内创建成功替换 URL 使用 `preserveGuard:true`，防止未卸载页面失去离开保护；真实工作区替换保持默认清除旧 guard。
- 管理配置保存、工作流结构校验、运行准入为不同事实。此次管理 QA 不代表批次/运行管理已交付；PM4 未开始。

## PM3 参数批次原子启动（2026-09-15，confirmed）

来源：`implementation/pm3/batches/task11-review.md`、实际代码及有界独立审查。Batch、独立Task输入快照、queued CoreRun、PreparedContent及启动Operation在同一调用者Session提交；Task只投影CoreRun。物理COMMIT失败会失效连接，响应丢失仍按原键找回接受结果。此为Task11后端基础包，尚无管理端启动入口；Task12–16继续。Studio demo联调不在本次范围；不进入PM4。

## PM3 管理功能交付（2026-09-15，confirmed）

来源：`docs/project-management/implementation/pm3/verification.json`、当前源码修订 `bdff9dd` 和真实 Electron 证据。前段“尚无管理端入口/Task12–16继续”由本节取代。

- 自动化管理、参数批次、批次与任务目录、持久日志/输出/截图、普通停止、30秒后强停、旧执行代次撤权、原键恢复、重启查询及双工作区隔离已连接真实 FastAPI、SQLite 与 CloakBrowser。
- 强停测试只对隔离 Electron 后代树中唯一且命令匹配的真实 workflow worker 做受控 SIGSTOP；UI 仍执行真实普通停止、宽限、强停和清理。当前HEAD直接证据为 `pm3/qa-runs/uuid-runs-1789458500247/result.json`。
- 项目模块不复制执行器；核心继续拥有 Workflow/PreparedContent/CoreRun/RunEvent/worker。用户排除 Studio demo UI 联调，不把该路径标为通过。
- PM3 当前授权管理范围通过；原完整 PM3 合同仍 partially_verified。项目数据型执行、持久环境、人工、统计和生命周期属于 PM4–PM8，未提前实现。用户手测、Windows、其他架构及打包未执行。

## PM4 A/B/C/F 管理能力交付（2026-09-16，confirmed）

来源：实施分支提交 `11e44be`、`48e5919`、`64606a2`、`f092551`、`1cc5112`、`c911b6a`、`b4dabf28`，以及 `docs/project-management/implementation/pm4/{a,b,c}-verification.md`、`pm4/verification.json`。

- V1/A/B/C 已交付真实管理侧多表输入、原子领取、本地记录/状态/字段 capability 和有限/不限批次调度；记录复用仅看当前业务状态与工作流条件，不保存批内排除集合。
- 原始输入快照保持不可变；Task 已确认写入推进独立游标；人工再次修改后旧版本写冲突。结果不明按原 operation 身份查询，旧 executionGeneration 无权继续写或释放占用。
- 权威 Electron 证据由真实 FastAPI、SQLite、项目数据服务和 UI 构成，但执行步骤由隔离 fake executor 驱动。不得把它写成真实生产执行核心、CloakBrowser 或 Studio 可用。
- PM4 管理功能交付状态为 delivered、验证状态为 partially_verified：当前源码业务 E2E `f-QHALLW` 绑定 `f07bb83b`，完成第二自动化读取、有限/不限管理链、三类候选态及日志搜索 Enter；`f-4QcXFG` 保留前一提交候选的全量工程与 19 张截图审查，旧 `f-dJVKnL` 为历史候选。`d3a397cf`、`f07bb83b` 补齐人工删除和 Excel 重新导入的活动 lease 保护并通过定向回归；当前源码的 19 张截图同视口视觉复审和阶段全量检查均已通过。PM3 管理前端定向回归 16 文件/121 项、管理后端定向回归 139 项已通过；会启动真实 CloakBrowser/生产执行核心的 `qa-project-management-pm3.mjs` 按边界未执行。真实生产执行核心、CloakBrowser、Studio、Windows、其他架构、打包及用户手测未执行。边界固定为“管理侧通过，真实执行核心接入待验收”；不进入 PM5。

## 有效分支归并（2026-09-17，confirmed）

来源：用户要求整理所有未合并分支，并确认只合入有效能力；源码差异审计、能力矩阵、树不变归并检查和最终验证记录见 `docs/migration/branch-integration/`。

- `codex/project-management-pm3@2bac1b14`、`pm4@fbda6f17`、`pm5@fbda6f17` 的有效项目执行能力经 `a5c5ed98` 接入；项目运行表使用 `project_workflow_*` 命名与当前 Studio 运行时并存，迁移由 `0013_merge_project_runtime.py` 汇合。
- Android 分支的设备持久化、生命周期、环境、批量创建、控制台及手动控制已接入。旧分支的工作流分配/接管直接依赖已退役运行时，因此当前接口明确返回不可用错误，不伪造兼容性。
- UI 控件、全局表格与代理管理已完成能力核对；当前更新实现优先，缺失的独立控件被移植，历史分支以树不变归并纳入提交图。
- `codex/m6-unfinished-checkpoint-20260913@59ae8d44` 与 `codex/studio-before-removal-20260913@4eda2074` 保持排除：前者是未完成检查点，后者是退役前快照，二者均不是当前产品能力来源。

## PM9 基线与发行验收（2026-09-20，confirmed）

来源：本次 Git 归并、`docs/project-management/implementation/pm9/verification.json` 与用户平台安排。

- 有效 Studio checkpoint、Android 规划已合入 `codex/architecture-baseline@8e5564e0` 并推送；已退役两个历史快照继续排除。PM9 基于该基线在 `codex/project-management-pm9` 实施。
- 生产源码/打包 HTTP 与 Electron 管理链、万行数据测量通过；后端 3159 passed / 15 skipped、前端 5445 passed、脚本 94 passed；真实 CloakBrowser 四节点/批次/重建测试 8 passed。
- PM9 仍 in_progress；生产项目执行器尚未接入完整图、项目数据节点、End 和人工检查点。已提交 R1–R4 架构规格等待用户确认，不能将管理侧/四节点证据扩写为完整执行通过。
- 用户指定 Windows x64/macOS Intel 使用现有 GitHub Actions，缺少的实机证据明确待验收。本机 arm64 DMG 已构建但无签名、公证或手工安装证据；CI 实际状态见 PM9 报告。


## 安卓桌面布局与确认焦点（2026-09-24，confirmed，隔离分支）

来源：`codex/android-management-complete` 的 `docs/qa/android-management/2026-09-24-desktop-apps-layout.md`，真实Electron/Lima/ReDroid与22项组件回归。

- 安卓创建页在1280×800/1440×900、100%/200%通过真实布局断言；长设备名标题使用最小高度与换行，避免覆盖详情标签。
- 应用破坏性确认复用共享Dialog；取消初始焦点与键盘圈定，未知结果触发器禁用时回搜索框。卸载请求提交时选择搜索框作为恢复目标，避免异步列表移除按钮后焦点丢失。
- 真实清除/卸载与备份恢复读回已完成，自建资源已清理。本条只确认该有界切片；最终全量门禁与整个AM1–AM4验收状态以QA报告为准。

- 2026-09-24 批次取消增量（confirmed 软件与真实 HTTP；完整 UI partial）：取消未准入项、冻结动作重试、确认终态后的新批次入口及筛选零匹配保留已实现；修复容量 await/跨批次旧快照/核实 await 覆盖取消和幂等回执。前端160项、后端47项定向通过；独立最终复审无Critical/Important；真实ReDroid容量等待取消、服务重启原编号重放保持cancelled且自建资源清理missing。最终全量后端4048passed/26skipped/2warnings、前端424文件/5650项及工程门禁通过；Mac锁屏阻塞真实UI，进度隐藏页检查与T14/T16等剩余项未关闭。见[报告](../../docs/qa/android-management/2026-09-24-bulk-actions.md)。

- 2026-09-24 隐藏页与观察增量（confirmed 软件/真实后端，整体partial）：批次状态GET隐藏时暂停、可见恢复，一行修复经RED 1 failed→GREEN 69 passed；1/5台真实API P95为6.177/12.495ms，列表内inspect均0，后台间隔3.23–3.34/4.15–4.21秒，停机约15.8秒；5台自建资源均核实missing。Mac锁屏继续阻塞桌面隐藏页/前台/新批次入口，十台及GApps条件未变。完整前端424文件/5651项（722.44s）及类型/lint/OpenAPI/build全部exit0；结构4/脚本95/迁移6项通过，当前102步骤85passed/14not_run/3blocked不虚增。见[完整证据](../../docs/qa/android-management/2026-09-24-observation.md)。

- 2026-09-24 规格复核修复（confirmed软件定向，真实桌面blocked）：原T13.4逐项结果证据范围过宽，本轮直接渲染冻结result.items的全部状态/错误/重试来源，accepted不再误报未知但继续冻结；镜像未知拉取补现有POST核实、原编号重试及A成功/B响应丢失的身份栅栏。4项初始RED加1项连续请求RED后，Android166项/类型/lint通过，最终增量复审无Critical/Important；完整前端424文件/5656项通过（750.46s），类型/lint/OpenAPI/build均exit0，真实UI仍受Mac锁屏阻塞。见[实际证据](../../docs/qa/android-management/2026-09-24-item-results-image-recovery.md)。

- 2026-09-24 持久拉取恢复（confirmed 软件/真实HTTP，桌面blocked）：重启后按工作区分页发现未知拉取、原编号显式核实、新拉取冻结及422前置拒绝恢复输入已实现；后端34项、Android171项及类型/lint/OpenAPI/build通过，增量审查无C/I。真实强杀重启列表total1→核实→0，pull仅1次，基础镜像保留；未创建用户设备。AM-R12磁盘预检仍待实现，不能归为外部blocked。见[证据](../../docs/qa/android-management/2026-09-24-persistent-pull.md)。

- 2026-09-24 最快验收（confirmed，整体不通过/partial）：当前Android后端477项、前端177项、迁移6项及工程门禁通过；真实备份磁盘预检零写入拒绝、释放后估计=实际18595840字节、传输取消及自有资源清理通过。最终限时审查新增备份跨动作未知编号覆盖已RED→GREEN关闭；创建/拉取磁盘准入和宿主/VM数值展示仍Important。Mac已解锁，最终构建首页/无效拉取恢复输入实机通过，其余完整UI改记not_run；十台/GApps仍blocked。最后候选全仓全量未重跑，旧数字不代替；见[完整验收命令及输出](../../docs/qa/android-management/2026-09-24-final-acceptance.md)。

- 2026-09-24 磁盘观测（confirmed，整体partial）：宿主workspace与VM实际DockerRootDir可用字节分别透传HTTP/OpenAPI并展示，0与unknown分开；真实Mac只读路由及最终构建页面刷新通过。创建/拉取准入仍未实现，不能以两侧数值展示代替。证据：[验证报告](../../docs/qa/android-management/2026-09-24-disk-observation.md)。 最终本候选完整后端4069passed/26skipped/2warnings（880.33s）、前端424文件/5670项（213.55s）、Android后端485/前端180、迁移6及类型/lint/OpenAPI/结构4/脚本95/build通过；增量审查无新增C/I。

- 2026-09-24（confirmed，整体partial）：18b75c49镜像拉取磁盘准入、严格未知确认和请求冻结已实现；真实未确认0pull、确认后强杀/重启/核实1pull通过。真实Electron批量筛选选择保留、目标冻结、取消未开始项、新批次通过，AC15关闭；两台自建资源已清理。创建/复制/恢复准入与最终全仓验证待Task4，不能沿用旧完整结果当本候选通过。见[验收证据](../../docs/qa/android-management/2026-09-24-pull-disk-and-bulk.md)。

2026-09-24后续confirmed：真实Electron重启发现未知pull、核实前拒绝新请求、显式核实succeeded并清空历史、改引用撤销确认已验；自有登记已撤销。c4b6159d修复202/failed重放误报已接受，187前端回归通过，独立复审进行中。
