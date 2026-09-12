# 旧项目项目管理核心研究笔记

- 日期：2026-09-12；状态：research_verified（证据核对完成，不是新产品决策）
- 范围：只读研究旧讨论结论、产品/运行契约、配置代码与设计交接。不改任何项目文件，不运行迁移或产品。
- 旧仓库：`/Users/zhangtiancheng/Documents/projects/browser-automation`
- 固定来源提交：`324748abe7095f085b4ffb9467be9cb5c8851a5c`，提交日期 `2026-09-11T17:46:00+08:00`，标题 `docs: add project data design and implementation plan`。
- 旧工作树大量文档/原型文件标为删除。本文通过 `git show <SHA>:<path>` 从提交读取；不能将工作树缺文件解释为用户取消历史设计。
- 下方未写前缀的设计路径均相对 `.ai/01-Project-Management/`。源码路径相对旧仓库。所有行号都对应该固定提交。

## 1. 最重要的裁定

1. 项目是同一业务及同一组业务数据的运行域；自动化是项目内的业务处理定义，一个项目多个自动化。不是通用项目协作软件，也不是一项目一流程。业务历史例子包括注册、找回、申请卡、换绑邮箱、领取卡，共享人员、邮箱、账号数据表。[Product-Definition-and-Information-Architecture.md:14-25；Decisions-and-Rationale-2026-08-31.md:16-21,27-28]
2. 六主面板已被后续用户明确保留：概览、自动化、运行记录、统计、数据、环境；没有第七个项目设置面板、项目内第二侧栏、全局任务中心、跨项目控制。2026-09-10 缩减导航探索已被取代。[README.md:19-25；Product-Definition-and-Information-Architecture.md:49-77]
3. 自动化最新管理方式为四 Tab：基本信息/输入数据/参数配置/运行设置。替代 M8 首次五步向导和独立运行方案动线；四页聚合原子保存，画布独立保存。零输入/零参数合法，缺内核或所需浏览器配置允许草稿但不能进画布。这是旧项目当前事实，是否继续作为新项目准入门槛仍可重新论证。[README.md:47-51；Milestones/Automation-Workspace-R5-Implementation.md:9-13,26-41]
4. 一个自动化一套运行配置。并发只改变同时任务数，不生成资源配置位置、不支持逐槽代理/浏览器/筛选/参数覆盖。所有任务仍有独立可变浏览器环境。[M9-Run-Presets/Concurrency-Contract.md:14-21,36-47]
5. 旧代码拥有真实项目/数据/自动化外围配置和工作流编辑器；运行、统计、人工接管、持久环境不等于已实现。视觉批准不是产品实现或运行验收。[Current-State.md:19-26；ProjectEmptyPanels.tsx:48-68,209-226；HANDOFF-20260911.md:78-85]

置信度：以上高。业务实例来自已接受的旧决策与产品文档；本文未直接访问其引用的 Windows `womeik/ck_runner` 原始业务工程，不把这种转述说成再次亲验该业务运行。

## 2. 对象关系及职责

| 对象 | 归属及责任 | 证据 |
|---|---|---|
| Project | 业务和数据边界；包含自动化、数据表、运行历史、持久环境，引用全局资源 | Product Definition:14-47 |
| Automation | 用户管理与启动入口；持有名称、数据使用项、参数定义、运行设置以及可独立保存的流程文档 | README:47-51；automation_models.py:12-33 |
| WorkflowDefinition | 自动化中的流程逻辑，不应给用户再造一个并列重复业务容器；现行仅 Web 流水线、流程图/模块条双视图 | README:43-51；automation_models.py:26-33 |
| RunPlan / 运行设置 | 同一自动化唯一配置：次数上限、并发、资源规则、参数值；配置可保存不代表开始执行 | run_plan_models.py:12-25；Concurrency Contract:23-47 |
| DataTable | 用户唯一顶层数据对象，内部有记录/字段规则/数据状态/来源；取消“模型/来源/状态”三个并列模块 | UI-Interaction-and-Health.md:18-29 |
| Table use / 数据使用项 | 引用表的稳定 ID，可按用途多次引用同表；继承表结构，不复制可编辑 schema；每个使用项独立筛选 | M8-Automation/Redesign-V2.md:12-20 |
| WorkflowBatch | 用户一次启动形成的运行边界；固定运行配置快照；并发容量按需领取，达到上限/输入耗尽/用户停止终止新领取 | Workflow-Data-and-Execution-Model.md:138-176 |
| Task | 一组输入记录的一次流程执行；先领取再创建；输入固定，后续同步/数据修改不改变其历史输入 | Workflow Model:34,75,154-176 |
| ExecutionSnapshot | 本次运行的流程/参数/资源固定快照，不是发布版本/工作流仓库 | README:78-90；Workflow Model:12,142-152 |
| Attempt | 节点一次执行/重试；增加尝试记录，不覆盖旧尝试 | Workflow Model:34,199-205 |
| DataLease | 排他占用真实稳定记录，不能用业务状态代替锁；同工作区跨项目共享物理来源也排他，项目业务状态仍独立 | Concurrency Contract:60-87 |
| EnvironmentInstance | 每任务独立，临时默认清理；工作流明确保存才转项目持久环境；全局浏览器配置仅创建来源 | Environment-and-Manual-Takeover.md:12-44 |
| ManualWait | 原任务等待人工的状态，保留数据租约/环境/代理/上下文，释放自动执行槽；不新建批次、不复制任务 | Environment and Manual:46-56 |
| ProjectHealth / Statistics | 派生读模型；健康反映运行可用性，业务推进状态不参与；统计来自真实任务与独立资源采集 | UI Health:72-83；statistics-rules-v2.md:17-28 |

自动化/工作流建议对外口径：以“自动化”为可创建、配置、启动的对象；“工作流”指自动化内部的流程编排。勿呈现“项目→自动化→运行方案→工作流→批次”五层必经导航。这是从最新 UI 与代码关系得出的新方案建议，不是历史文档单句原话。

## 3. 已接受的运行语义（目标契约，尚未执行验收）

- 启动不提前创建全部任务，不全部认领数据；空闲容量每次领取一组有效记录后创建任务。多个必要输入全有或全无，缺任一必要输入不创建半任务；可选输入缺失为空。来源不可达 UNAVAILABLE、配置/结构不合法 INVALID、真实无可领取 EMPTY 分开。[Workflow Model:154-176]
- 输入之间无主从；不按行号配对、不做隐式业务键 JOIN、不做笛卡尔积，也不从各表匹配数推算可运行数。M8 v2 实际未有表级 required，最终多输入组合算法仍欠执行契约。[M9 Design:59-65,89-97；Concurrency Contract:74-79]
- 同一物理来源＋稳定记录身份在同工作区统一排他；独立 Excel 快照不因内容相同自动合并身份；跨多个 Workspace/机器排他不由本地库自然保证。[Concurrency Contract:64-87]
- 业务状态由明确“设置数据状态”节点更改，后续节点失败不隐式回滚；释放租约不修改业务状态；完成后能否再次领取取决于业务筛选，不等于永远只做一次。[Workflow Model:90-117；Concurrency Contract:60]
- 节点重试属于同一任务，保留执行槽/数据/代理/环境。失败任务记录不可变，不提供重跑旧任务；调整数据状态后，由新批次创建新任务。[Workflow Model:199-205]
- 批次仅停止、强制停止。停止停止新领取并使活动任务在安全点结束；强停使旧执行失权、取消执行、释放租约及清理环境，保留历史证据。无批次暂停/恢复。[Workflow Model:207-226]
- 人工接管允许选固定运行快照中的节点继续，须核验输入、环境、当前租约与代次、节点依赖；校验失败允许换节点或失败退出。直接完成/失败必须单独表达。TTL 到期、真实浏览器关闭视为任务失败；仅关闭 UI 不算浏览器关闭。[Environment and Manual:58-100]
- 归档协调活动批次停止后进入只读；只归档项目可永久删除，删除不影响外部数据、其他项目引用或全局资源。[Product Definition:79-113；Implementation-Roadmap.md:60-66]

## 4. 历史冲突及取舍顺序

| 冲突 | 已核对结论 | 证据 |
|---|---|---|
| 逐槽差异 vs 一套配置 | 逐槽全撤销；M9 Design 明确 superseded，不能取其位置资源继承表当新规范 | M9/Design.md:1-15；Concurrency Contract:14-21,89-105 |
| 多份运行方案 vs 单一运行方案 | 一自动化单一配置；最新模型数据库也 unique automation_id | README:55；run_plan_models.py:12-17 |
| M8 五步向导＋独立方案入口 vs R5 四页管理 | 最新 R5 四 Tab 生效；旧接口兼容≠旧导航继续作为主路径 | README:47-51 |
| flat AND vs 嵌套 AND/OR | R5 支持条件树；旧空树兼容 flat AND，保存不静默压平 | R5:28-41 |
| 发布版本不可变 vs 暂不版本管理 | 2026-09-09 工作流共识覆盖；保留内部 ExecutionSnapshot，暂不发布/仓库 | Decisions:80（旧）；README:43-45（新）；Workflow Model:12 |
| 三个数据顶层对象 vs 数据表 | 统一数据表；字段/状态/来源均从表内管理 | UI Health:18-25 |
| 全来源实时/只读 vs 分类型来源 | 外部 SQLite 稳定业务键实时只读，系统兜底一次导入；Excel 一次导入；Sheets 本地主库＋新增拉取＋业务推送 | README:104；Workflow Model:70-88 |
| “只申请 Sheets 读取” vs 本地变化写回 | UI Health:26 是残留旧说法；README:123-125 及 M5.1 新契约明确读写范围、人工即时/工作流五分钟推送 | UI Health:26；README:123-125；Workflow Model:74 |
| UI Health 全 KPI 必须可点 vs 统计轻量汇总 | 旧健康文档:131 为早期目标；新统计候选:29 仅失败去向下钻、KPI只读。必须作为新方案明确裁定，不说全部旧已确认 | UI Health:131；statistics-rules-v2.md:29 |
| Worker 失联立即释放 vs 防未知结果重发 | 旧目标要求立即释放＋fencing，但承认外部副作用不撤销；后续合同强调超时/失联不等于停止、重启先核对不盲重发 | Workflow Model:195-197；Concurrency Contract:81-87 |
| 审计写 AND/OR 延期 vs R5 已做 | 前者是六面板静态设计批次范围，非否决已授权自动化专项，也不是产品删除 AND/OR | Design Audit:175,203-240；R5:12,28-41 |
| visual approved vs rules approved | 主图/配套视觉可以确认，同时统计耗时算法、快照、资源保存策略仍候选 | README:19-41；statistics rules:1-13；HANDOFF:58-70 |

判断依据优先级建议：当前用户明确指令 → 后续专项确认 → 专项最新代码/验收 → 旧总体契约 → 候选设计/原型。候选设计可被本次方案吸收为 proposed，不能靠时间更新自动升格 accepted。

## 5. 旧项目实际进度证据

- M0/M1 项目框架、真实项目生命周期已验收；M2 数据配置、M3 SQLite、M4 Excel 已验收；M5/M5.1 分阶段交付，Google/OAuth/桌面缺口分别保留。此为历史验收报告，不是本次重跑。[Implementation-Roadmap.md:29-42]
- R5 四 Tab、组合条件、只读预览已本地实现、自动检查及隔离 Electron 证据，待用户验收；未执行真实工作流。[Current-State.md:19-23；R5:59-70]
- W1.2 单链模块条、编辑/撤销、双视图恢复、打印日志静态配置已交付待验收；W1.3 未开始，不存在执行器完成声明。[Current-State.md:24-26]
- `autoflow-desktop/backend/src/autoflow/automation_models.py:12-33`：AutomationDraft 真持久化，流程文档 independent；`:36-48` 有软依赖索引。
- `autoflow-desktop/backend/src/autoflow/run_plan_models.py:12-17`：RunPlan.automation_id unique；`:28-36` 项目默认资源独立记录。
- `autoflow-desktop/backend/src/autoflow/workflow_api.py:21-65`：workflow 读/写/validate/catalog 四类配置接口，不是启动接口。
- `autoflow-desktop/backend/src/autoflow/automation_management_service.py:369-397`：画布资源准入规则已存在。
- `autoflow-desktop/src/renderer/features/automations/ManagementWorkspace.tsx:64-67`：四 Tab 实码；`:80-100` 已保存配置范围当前要求正整数、并发不超过有限处理数，不能复用旧 Design 提议的 1–50 当实测容量。
- `autoflow-desktop/src/renderer/features/project-overview/ProjectEmptyPanels.tsx:48-68`：批次/任务/人工记录及统计占位；`:87-206` 只有项目默认资源真实查询；`:209-226` 实时/人工/持久环境占位。

## 6. 审计与未决事项：成熟方案必须关闭，但本次可提出明确建议

2026-09-10 审计自报77张有效稿、19旧稿排除、15类修正（6 P1/9 P2）；本文阅读审计记录，没有重新逐图审查这77张，不能声称本次视觉 QA。[Design-Audit-20260910/README.md:3-9,251-258]

六项先定规则：统一任务时间证据；统计公式/刷新；运行占用记录编辑与快照；Sheets 拉取/推送两链；字段及整表变更影响；默认资源保存 vs 运行门槛。[Design Audit:24-84]

可复用交互：单一来源感知返回；失败页仍能看运行记录；共用提交中/成功/失败/结果未知/冲突；应用筛选后可解释；长列表与紧凑窗口；任务结果/环境清理/数据租约独立状态。[Design Audit:106-166；HANDOFF:21-33]

统计 v2 候选拟定：成功率 success/(success+failed)，以任务结束时间归窗；耗时 actual execution start→final result，包含人工等待与重试、不含启动前排队或结束后清理，缺失样本不补0；卡片/图/失败下钻绑定同一服务端结果快照；主动刷新推进边界；无自动刷新。全部新增规则明确 pending_review。已确认旧口径只包括结束时间聚合、success/(success+failed)、固定时间范围、运行详情复用/上下文恢复。[statistics-rules-v2.md:1-13,17-65]

环境 v2 候选：有效引用但连接超时允许保存，失效引用阻止保存，清理未知只核验，明确失败且终态/归属/后端许可才能受控重试，清理完成不改变原任务失败或未知数据占用。交接 verification 显式 `approved:false, runtimeAcceptance:false, productSourceModified:false`。[HANDOFF:40-70]

新的方案建议（proposed，不冒充历史决定）：

1. 先冻结批次/任务/尝试/环境/租约各状态机、终态与回收结果再设计停止和人工按钮；“已结束”中性，“全部成功”另算。
2. 未确定外部副作用的任务进入“结果待核实”，不能仅凭租约超时自动重发；fencing 只能约束本系统提交，不能撤回已发网页动作。
3. 人工等待释放执行并发但继续占浏览器、代理及数据，需独立的现场保留数量/内存预算和到期策略，否则无限处理＋大量人工等待可越过并发上限耗尽资源。
4. 配置可保存、可进画布、可启动、运行健康四个判断分开；是否还必须选内核才能编辑纯流程应重新评估，不机械继承旧门槛。
5. 多输入绑定只声明业务输入，不提供隐式 JOIN。首个执行切片需明确必要/可选输入、同表多用途、领取排序及耗尽判定；不能把 M8 预览 total 当可执行数量。
6. 以新架构能力重建运行对象和契约；旧工程只迁移有效业务规则/素材/测试场景，避免把历史 run_plan/v1/v2 兼容包袱复制为新产品层级。

## 缩写来源映射

- Product Definition = `.ai/01-Project-Management/Product-Definition-and-Information-Architecture.md`
- Workflow Model = `.ai/01-Project-Management/Workflow-Data-and-Execution-Model.md`
- Concurrency Contract = `.ai/01-Project-Management/M9-Run-Presets/Concurrency-Contract.md`
- R5 = `.ai/01-Project-Management/Milestones/Automation-Workspace-R5-Implementation.md`
- UI Health = `.ai/01-Project-Management/UI-Interaction-and-Health.md`
- Environment and Manual = `.ai/01-Project-Management/Environment-and-Manual-Takeover.md`
- Design Audit = `.ai/01-Project-Management/Design-Audit-20260910/README.md`
- statistics-rules-v2.md / statistics rules = `.ai/01-Project-Management/Design-Refinement-20260910/statistics-rules-v2/RULES.md`
- Current-State.md = `.ai/00-Core/Current-State.md`
