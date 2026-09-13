# PM3：自动化配置与真实参数批次设计

- 日期：2026-09-13。
- 状态：**paused / 原型对齐复审中，尚未开发；不能据此直接实施**。
- 2026-09-13用户要求重新以指定图库和旧实现审查项目管理；随后确认保留顶部导航。见[对齐审查与纠偏建议](../../project-management/reviews/2026-09-13-prototype-alignment/README.md)。本文业务提案保留历史，不代表参数归属等新建议已获批准；后续需补旧自动化管理复用与逐画板验收。
- 依据：用户“继续完成pm3，先设计再开发”；已确认完整设计906deda、PM0提交9c361f4，以及[完整里程碑计划](../plans/2026-09-13-project-management-milestones.md)的PM3。
- 项目实施基线：`codex/project-management-implementation@d02dde4`，工作区干净；PM2本机交付见[核验报告](../../project-management/implementation/pm2-verification.json)。用户继续PM3作为阶段推进授权，不改写PM2历史平台证据。
- 核心参考基线：主项目正式提交`2b5365e`，通过`git show`读取；主目录有Studio/debug等其他任务WIP，不能复制为交付依赖。本设计不修改业务代码、主目录或其WIP。
- 技能：using-superpowers加载流程；brainstorming形成设计及取舍；writing-plans已读取，设计确认后细化逐任务执行卡；ponytail用于检查复用与避免第二套执行器。

## 1. 用户在这个阶段能完成什么

在项目里创建一个自动化，设置本次业务需要的参数、浏览器及运行规模，进入Studio编辑同一份流程。从项目启动后，能看到这个批次实际创建了多少任务、各任务做到了哪一步、输入和输出是什么；可以停止，并能在断线或重启后找回真实结果。

完整交付四个路径：

1. 自动化目录 → 新建 → 四页签管理保存 → Studio编辑/保存 → 返回原自动化。
2. 已保存自动化 → 启动确认 → 参数型批次 → 任务 → 实际节点日志/输出/截图。
3. 执行中 → 停止新任务并请求停止活动执行 → 查询最终处置；必要时明确强制停止。
4. 超时/断线/重启 → 查询原操作和Run → 核对已知事实；不自动重跑网页。

PM3同时完成输入数据的绑定、条件、排序与只读预览。预览展示各输入在当前表上的候选和检查时间，不承诺多表可领取组数、不获取占用；关联定义检查环路、来源输入和字段类型，真正组合与领取在PM4。凡需要真实项目记录注入、占用或写回的流程，明确显示所需数据执行能力尚未开放并阻止运行；不以空输入替代。多表领取/写节点在PM4，人工等待/环境保留在PM5，Sheets在PM6，完整统计和后续批次在PM7，生命周期在PM8。

## 2. 已有能力与必须补齐的差距

以下主线路径均相对主项目，指`2b5365e`正式内容；不能用实施分支M1或主目录WIP替代。

| 能力 | 真实源码依据 | 当前事实 | PM3处理 |
|---|---|---|---|
| 文档保存/结构校验 | `apps/backend/src/autoflow/application/workflows/service.py`、`infrastructure/database/workflows.py`、`adapters/http/workflows.py` | 已有UUID、revision CAS；缺保存操作身份与项目关联 | 复用并补持久保存结果查询、声明式输入契约和关联守卫 |
| 准备执行内容 | `domain/workflows/run_validation.py::prepare_run` | 深复制/编译为内存PreparedWorkflow，无持久内容身份 | 在原编译器外增加不可变PreparedContent；不复制编译算法 |
| Run启动 | `application/workflows/runs.py::start`、`database/workflow_runs.py::create` | 单工作区单Run，自行提交后立即派发；先占浏览器 | 拆为prepareRun参加调用者事务、提交后dispatch；支持真实并发容量 |
| 执行能力 | `application/workflows/execution.py`、`providers/browser/workflow_executor.py` | 真实浏览器动作、条件/循环/变量已有正式实现 | 继续唯一执行器，项目不遍历图 |
| 参数 | `domain/workflows/run_validation.py::initial_values` | 只有文档变量初值，没有项目参数专用输入身份 | 独立参数上下文，不能覆盖变量初值来冒充传参 |
| 日志/截图 | `database/workflow_runs.py`、`adapters/http/workflow_runs.py`、`filesystem/workflow_artifacts.py` | 单Run序号和afterSeq补读、安全文件登记已有 | 补执行代次、权威快照、项目授权；公共投影移除绝对outputPath |
| 停止/恢复 | `application/workflows/runs.py::stop`、`database/workflow_runs.py::recover_interrupted` | 有停止和启动时标中断；缺持久撤权/核验 | 先撤权核验再释放，不能直接套用旧active_slot恢复 |
| 文件/工作区 | `bootstrap/app.py`、PM2文件桥和Operation | 已有QuiesceGate、workspace blocker和受控文件授权 | 扩展真实未完成Run/清理账本；后台回调也受保护 |
| Studio定位 | `apps/desktop/src/shared/automation-studio.ts`、`renderer/domains/workflows/pages/StudioPage.tsx` | openAutomationStudio无参数；已有编辑和离开保护 | 增加受控workflow/project/automation定位和返回，不复制编辑器 |

核对结论：PM3不能只把当前`start()`套上项目HTTP。**Task和CoreRun同事务创建、执行代次及恢复核验是正式开发前必须安排的核心改造包。** 当前Studio M5/debug WIP不作为这些契约已完成的证据。

## 3. 方案取舍

| 方案 | 优点 | 代价/结论 |
|---|---|---|
| A：在唯一核心中补项目所需契约，项目做配置和批次协调（推荐） | 保留真实执行器；原子创建、停止、事件与恢复有唯一权威 | 本阶段包含核心改造；需要明确共享文件责任和集成回归 |
| B：先只做配置页，运行以后再接 | 更早展示表单 | 不满足PM3“真实流程、停止与恢复”的退出条件；只能作为中间检查点 |
| C：项目自行创建Run/操作浏览器，再与Studio同步 | 初期看似容易独立开发 | 产生第二执行器和事务裂缝；不采用 |

选择A，分包小步验收，但不把B当作完整PM3。

## 4. 页面、组件与产品语言

延续暖灰、黏土棕、shadcn/Radix/Tailwind。只保留现有全局导航与项目页签，不增加项目资源侧栏。

| 页面/组件 | 内容与交互 |
|---|---|
| 自动化目录 | 名称、描述、最近修改、配置问题；搜索/排序/分页；新建、打开、编辑工作流、运行。删除入口随PM8交付，不摆不可用假按钮 |
| 基本信息 | 名称、描述、关联工作流、管理保存/工作流保存各自状态；四页签共用底部保存条 |
| 输入数据 | 按工作流输入定义展示具名输入，选择本项目表和稳定字段，必需性、独立/固定/关联模式、条件、排序、预览及检查时间。不能按同名字段或行号配对 |
| 参数配置 | 参数名称、类型、说明、必填、默认值、本次可填写；零参数是合法空态。定义归属按第5节确认 |
| 运行设置 | 浏览器继承/指定，代理继承/不使用/固定/代理池，数量、并发、超时、失败后停止新任务/继续；展示最终资源及来源 |
| 启动确认弹窗 | 已保存流程/配置摘要、本次参数、实际数量/并发、浏览器/代理来源、预检问题；启动覆盖不会改默认设置 |
| 批次列表与详情 | 状态、创建/活动/成功/失败/取消/中断数量、未继续创建原因；本次冻结配置与当前配置分开 |
| 任务详情 | 原始参数/输入、节点尝试和日志、输出、受控截图、处置结果；只显示真实可用入口 |
| 停止确认 | 说明不再创建任务、哪些活动任务收到停止请求、已发生网页操作不能撤销；强停独立确认 |

PM3只交付批次/任务视图，等待人工、已保存环境和统计保持未开放，不预造模拟数量。

复用PM2的原命令恢复、异步Operation显示、资源选择、条件编辑、分页与受控文件能力，但不把record-specific editing hook改成万能表单引擎。新增领域组件先测试后装配页面。页面分拆查询、草稿、导航与启动协调，避免继续把业务分支堆到App或千行详情组件。

## 5. 输入和参数的唯一归属（本阶段明确请求确认的细化）

现有完整设计规定“工作流输入定义 → 自动化绑定 → 原始任务证据”三层，但PM0 DTO同时把`parameterSchema`放在AutomationWrite，尚未明确与Studio文档参数定义如何避免双源。本设计推荐如下勘误，确认前不修改公共契约：

- **Studio/core保存唯一输入及参数定义**：稳定inputId/parameterId、名称、类型、说明、必填及流程默认值；Studio独立文档也可拥有这些定义。
- **自动化保存绑定和默认覆盖**：输入映射及筛选、参数默认覆盖、是否允许本次填写；`parameterSchema`只作为核心定义的只读投影，不能独立编辑第二份类型声明。写入DTO使用明确的参数绑定集合。
- 参数页“修改定义”定位到同一Studio文档的输入/参数设置；默认值和本次可填写仍随四页签一次保存。不是悄悄同时保存两份文档。
- 参数值优先级：允许填写的本次覆盖 → 自动化默认覆盖 → 工作流默认值；缺必填或类型不匹配阻止启动。false、0、空字符串、未提供分别判断，不用truthy回退。
- 绑定按稳定ID；批次参数值以parameterId为键并冻结当时显示名称。节点使用核心参数引用选择器产生稳定身份引用，核心统一解析；不把参数文本递归解释为表达式，不开放任意JavaScript/Python求值。改显示名称不换身份，改类型/删除给引用影响。流程契约变化后显示真实问题，不把旧值强转为新类型。
- 核心参数上下文只读；工作流变量每Task从文档初值深复制。需要修改的值先显式赋给变量，不把参数、输出或项目记录混在同一字典中。
- 表/字段/状态绑定仍依据PM2 typed identity和datasetGeneration。重新导入后旧绑定失效，需要显式重新确认，不能同名自动重绑。

这比在自动化与Studio各维护一套参数定义更容易解释和恢复。它是对AU-04操作入口及PM0传输形状的显式细化，不声称原规格已经写清。

### 5.1 本阶段新增的表单约束（proposed）

权威旧规格没有给出自动化数值长度限制；以下是本阶段新建议，不复用Project的36/120：自动化名称trim后1–80个Unicode码点，描述0–1000码点，同项目名称按trim+casefold唯一；参数显示名称1–64码点、用途说明0–500码点，同一工作流参数名唯一，parameterId是引用身份，显示名称不充当记录或变量键。前后端按码点校验，不新增Unicode兼容归一化。字段错误定位到参数行和所属页签。

默认自动执行总超时建议300秒（每Task），不替换已有节点自身超时；UI显示并可修改为有限正数。PM3不提供人工超时编辑，未接入能力不得伪装成可用设置。启动数量/并发为安全正整数，最大可用并发由核心公布的实际容量限制，超限明确报容量不足，不能静默降级。

### 5.2 确认后同步的公共契约勘误

同步AU-04、Automation/AutomationWrite的参数绑定定义、C01校验输出、PreparedContent契约修订身份和冻结参数模型。HTTP启动沿用唯一camelCase `expectedAutomationRevision/parameters/maxTasks/concurrency/environmentOverride`；应用层旧卡`expectedManagementRevision/parameterOverrides/runLimit`作显式内部映射，不对前端公开第二套字段。管理保存缺引用允许草稿；启动必须满足runnable。

## 6. 自动化保存、关联和引用保护

管理保存是单个短事务：基本资料、输入绑定、参数默认覆盖、运行设置全部CAS提交；managementRevision独立于workflowRevision。空输入/空参数可保存，暂缺资源或绑定问题允许保存草稿并返回问题；无效JSON/字段类型等结构错误仍拒绝。

新增自动化提供“新建工作流 / 关联已有工作流”。新建的空文档由核心创建，自动化及所有权关联与新文档在一次本地短事务发布，核心提供文档创建事务参与入口，避免孤立项目文档。普通Studio内容保存仍是独立核心命令。关联已有文档不转移所有权、不复制；workflowId最多有一个活动自动化关联，由数据库唯一约束保证。保存含核心工作流当前revision核验，冲突保留管理草稿。

引用自建立时生效：PM2字段收紧、状态删除和重导入影响检查必须纳入已保存绑定；先持久化引用事实，不能只靠前端扫描。显示名改动不阻断稳定引用；类型/身份不兼容按既有影响规则拒绝或要求重新确认。工作流删除必须检查自动化关联、编辑会话与活动Run；PM8才交付完整生命周期界面。

打开Studio前，脏管理草稿有“保存后打开 / 放弃修改后打开 / 继续编辑”。打开相同文档定位既有会话；切换文档由Studio自身离开保护处理，失败不清除管理草稿。主窗口退出、工作区切换和Studio返回遵循同一个受控桥。

## 7. 真实参数批次和资源规则

默认有限1次、并发1、失败后停止创建新任务。PM3启动只允许零项目记录输入的流程；配置了必需或可选数据输入都不自动忽略。所有本阶段实际启动必须给有限正整数maxTasks；并发是实际执行数量，不能静默把配置2降为1。现场容量默认等于并发，有限任务数量和容量分别校验。

浏览器配置解析顺序：本次明确覆盖 → 自动化指定 → 项目默认；缺失时允许编辑，阻止需要浏览器的启动。代理明确区分继承、不使用、固定、代理池；不能把失效引用当直连。已有代理池解析器负责候选健康规则，批次固定候选及策略，Task保存当次实际选中的代理引用/摘要，不持久化凭据。浏览器seed、内核及Profile内容在批次固定；运行时不因后续编辑而漂移。

纯流程若无浏览器节点，不强制选择Profile或创建浏览器；这要求核心准备阶段输出browser需求，执行器支持无浏览器路径。PM3环境只支持按Profile新建临时工作副本；已保存环境、输入关联环境、End保留和人工现场属于PM5，预检必须明确拒绝需要这些未接入能力的流程。

项目默认资源在运行设置提供“编辑项目默认”真实表单，保存Project自己的managementRevision及Operation；自动化仍保持自身草稿，返回后只刷新资源事实。资源选择复用全局浏览器/代理模块；不增加内核中心、凭据表单或槽位配置。

## 8. 原子创建和执行边界

1. 请求预检：校验project/automation/工作流保存revision、参数/能力及资源；失败返回可定位问题。
2. core prepareContent：持久化不可变流程/布局/当前受支持依赖及摘要。独立操作身份可找回；后续编辑不改变它。不支持的子流程能力明确阻断，不虚构依赖编译。
3. 项目接受Batch：保存启动Operation和冻结配置、内容身份、参数、资源策略；成功只表示批次已创建。
4. 每个Task在**一个短UoW**内重新检查Batch门闩/剩余名额/容量；写Task、不可变TaskInputSnapshot、临时运行现场预约及queued CoreRun。参数型inputs=[]，不造虚假数据lease。core prepareRun不自行commit、不启动进程、不经HTTP自调用。
5. 提交后dispatcher在短事务中以runRequestId、queued状态和有效executionGeneration CAS领取，先持久保存dispatchAttemptId、服务实例/dispatcher身份与launching所有权，再创建目录、解析凭据或启动进程。进程句柄/启动证据另用短事务登记；不能先spawn再补领取事实。仅同一存活服务内从未取得launch claim的queued Run可正常派发；已有claim但无法证明外部动作结果的Run进入撤权核验，绝不重派。派发失败留下原Task和Run的失败事实。
6. 核心推进Run/事件；项目投影Task并聚合Batch，不能由项目页面或协调器直接宣布Run成功。

每Task固定runRequestId且唯一对应runId；重试只查/派发原身份，不能再建Run。每个浏览器工作副本有独立instance身份，Profile不是已保存Environment，也不是工作目录身份。

## 9. 停止、失联与重启

| 时点/动作 | 必须保留的事实和结果 |
|---|---|
| 启动响应丢失 | 原键查Operation找回Batch；同键异载荷冲突，不创建第二批 |
| Task/Run事务回滚 | 两者都不存在，现场预约也不留下 |
| 提交后派发失败 | 保留原Task与核心失败，不能伪装成未创建 |
| 用户停止 | 一个接受事务关闭Batch创建门闩、冻结目标Run集合，为每个目标持久分配稳定child cancelOperationId；提交后按固定身份扇出，接受后继续显示停止中 |
| 强制停止 | 使用独立父forceStopOperationId与期望状态revision，冻结目标及逐Run子命令身份；先持久撤销旧执行代次，再由平台适配器终止进程并核验；网页已发生效果不回滚 |
| 旧Worker迟到 | 所有事件、输出和终态写入检查有效executionGeneration及终态；拒绝旧代次写入 |
| 服务重启 | 已提交终态原样保留；未终态先进入核对，确认旧进程终止或隔离后才释放容量；本批最终中断，不自动继续领任务或重放网页 |
| 磁盘清理失败 | 执行结果与清理结果分开，真实残留进入可查询清理账本；不把未知进程等同清理完成 |

停止扇出中断后只能按原父/子Operation身份查询及续核验，不重算目标并生成新命令。已终态Run返回原事实；部分扇出不报完整停止成功。父操作保持running/reconciling，直到所有目标获得可证明的终态及安全处置；Run仍未知时不能让Batch提前stopped。launch claim已提交但进程证据未保存的窗口按结果不明处理，即使实际尚未spawn也不猜测重派。PM3服务重启后整批停止推进，包括未claim的queued项，不自动恢复任务创建。

PID不能独立作为进程身份，须结合本次服务/启动身份及受控子进程证据；macOS/Windows差异只在进程适配层。无法证明终止则维持隔离/blocker，不能通过人工改状态绕过。所有后台持久变更参加QuiesceGate；未完成Run、停止、核验和资源残留参与退出/工作区切换保护。

Batch状态沿用PM0定义，Task是CoreRun状态投影。completed表示按策略处理完，数量分别展示，不能一概叫“全部成功”；failed/timed_out/interrupted触发默认停建，选择继续时其他任务按配置推进。停止已经成功的Task不改历史成功；修复不改历史Run结果。

## 10. 查询、事件、产物和草稿

复用核心按Run序号持久事件；补充执行代次、事件身份、节点访问/尝试和提交时间。状态更新与事件同事务；快照返回lastSequence。状态快照游标与日志已读游标分开：先显示快照，但日志从本地lastSeenSequence补读（首次从0或明确的历史分页入口），不能直接跳到snapshot.lastSequence。重复丢弃，发现缺口分页补读；游标已清理时重取权威快照恢复状态，同时明确显示缺失历史，不假装日志完整。普通轮询可作为补查，不复制一套项目Run事件源。

项目只提供自动化、Batch、Task查询和Batch启动/停止协调。核心Run创建、派发、状态、日志及截图仍由核心维护；访问runId必须反查Task/project归属，不能用猜测ID跨项目读。产物只返回受控ID/媒体信息，不公开relativePath或绝对outputPath；数据库内部可保留受控relativePath。单个截图/产物查看通过核心受控GET返回内容流，按Task→Run→project反查权限，Renderer不提交路径。PM2选择令牌只覆盖已授权输入或新输出目标，不能拿来授权读取内部artifact。本阶段不新增产物集合导出；后续另存需明确定义新输出purpose，不能扩大Excel令牌的用途。

列表、详情、日志和输入有分页/取消/加载/空态/刷新失败。查询键含工作区、服务实例、项目和资源；草稿及未决命令身份只绑定稳定工作区/资源/表单会话，同工作区重连保留。切工作区后迟到结果不能关当前弹窗、污染缓存或显示成功。保存、启动、停止各持有自己的Operation身份；结果未明先查询，不把取消视图当取消执行。

管理四页签内导航保留同一草稿；离开自动化、全局导航、工作区切换、浏览器前进后退和打开Studio使用一致保护。取消离开时URL恢复。键盘Tab/Enter/Escape、首个错误定位、对话框焦点恢复、200%缩放、长名、大量选项和浮层滚动列入真实应用验收。

## 11. 文件落点和责任

以下是拟实施路径，**本阶段尚未创建业务文件**。后端均位于`apps/backend/src/autoflow/`，前端均位于`apps/desktop/src/renderer/`。

| 责任包 | 新增/扩展范围 | 单一责任 |
|---|---|---|
| 核心契约 | 现有`domain/workflows/`、`application/workflows/`、`infrastructure/database/workflow_runs.py`；按职责拆出内容准备、派发/恢复用例 | 核心集成负责人；不由项目包复制执行器 |
| 自动化领域 | `domain/project_automations/models.py`、`application/project_automations/service.py`、`core_port.py`、`infrastructure/database/project_automations.py`、`adapters/http/project_automations.py`及schemas | 自动化后端智能体 |
| 项目批次 | `domain/project_runs/models.py`、`application/project_runs/coordinator.py`、`queries.py`、`infrastructure/database/project_runs.py`、`adapters/http/project_runs.py`及schemas | 项目运行后端智能体 |
| 自动化界面 | `domains/project-automations/{components,hooks,pages,tests}`：聚合草稿、4页签、引用检查、资源/参数、启动表单 | 前端组件智能体；先组件再页面 |
| 运行界面 | `domains/project-runs/{components,hooks,pages,tests}`：批次/任务/日志、停止与恢复 | 前端组件智能体；共享Operation显示 |
| Studio桥 | `apps/desktop/src/shared/automation-studio.ts`、main/preload、现有Studio编辑器Hook | 核心集成负责人 |
| 统一装配 | models、迁移、bootstrap、App、generated.ts、覆盖和公共契约 | 主协调，禁止多人同时改 |

新SQLite事实至少包括自动化/工作流关联、PreparedContent、核心幂等操作、Batch、Task/原始输入、临时现场预约与核验记录；复用现有项目Operation和核心事件表，不为每层再造一套通用队列。新事实随实际消费者交付，不预建PM4/PM5空表。

## 12. 分包实施顺序（设计级拆分，确认后细化执行卡）

| 顺序 | 交付物 | 退出检查 |
|---|---|---|
| P0 基线集成与契约冻结 | 新独立`autoflow-project-management-pm3`工作区，从PM2提交创建；接入冻结的主线正式提交并解决资源/Studio冲突；同步本设计勘误 | 两边已有数据与入口回归、唯一迁移head、公共类型一致；不读取WIP作为源 |
| P1 核心准备/派发/撤权 | C01/02/05/06/07/11/16/17本阶段所需子范围，原Studio入口复用 | 共享UoW回滚无孤儿；并发2真实执行；旧代次拒绝；不要求浏览器的流程可运行 |
| P2 自动化垂直切片 | 后端管理/关联/引用 + 组件 + 四页签 + Studio定位 | 一次聚合保存；参数唯一定义；真实打开同文档；缺资源可编辑不可运行 |
| P3 参数批次垂直切片 | 启动冻结、批次接受、调度额度、Task/原始参数/Run原子创建 | 两次参数隔离、同键唯一、内容不漂移、有限数量/真实并发、失败策略 |
| P4 诊断与停止垂直切片 | 真实批次/任务/日志/产物、停止/强停/核验、持久blocker | 停止后不执行下一网页动作、重启不重跑、UI可找回原操作 |
| P5 全阶段验收 | 自动/真实应用、独立规格和工程复审、覆盖/账本/.ai/提交 | 满足下节全部本机范围；未来能力不冒充通过；停PM3验收 |

P1核心后端与P2已冻结契约下的组件可并行；P3依赖P1的真实事务门槛，不能以mock准入。边界明确的实现继续优先gpt-5.6-sol；集成及审查独立于实现。每包按失败测试→实现→定向通过→规格审查→工程审查→修复复核→提交。

主线已存在`0007_workflow_artifacts`，PM2为`pm02_excel_exports`。集成后以新增merge revision汇合真实heads，再依次增加核心契约迁移、`pm03_project_automations`、`pm04_project_runs`；不改已应用迁移、不用stamp跳过。开始编码前重新核对head，避免与主线未提交0008冲突；迁移文件统一由集成者写。分别验证空库、PM2库、冻结主线库升级和已有资源/流程/数据保留。

## 13. 验收矩阵

| 范围 | 必须证明的行为 | 拟测试文件/证据 |
|---|---|---|
| 自动化 | 四页签全成/全不写、CAS/原键恢复、同流程唯一绑定、引用保护、缺资源草稿 | `apps/backend/tests/contract/test_project_automations.py`；前端AutomationDetailPage测试 |
| 参数/内容 | FLOW-A01：两次启动参数和变量隔离；运行中编辑不改原输入/内容；false/0及必填 | `apps/backend/tests/integration/test_project_run_start.py` |
| 原子与并发 | 事务任一点失败无半Task/Run；提交后失败有真实历史；双击/丢响应仅一Batch；N=3/C=2不多建 | 同上；核心repository/dispatch tests |
| 停止/恢复 | 停止/派发竞争、强停先撤权、迟到事件拒绝、重启不重放、未知资源不提前释放 | `apps/backend/tests/integration/test_project_crash_recovery.py` |
| 诊断/授权 | afterSeq断线补读、重复/缺口、快照一致、跨项目拒绝、产物路径不泄露 | `apps/backend/tests/contract/test_project_runs.py`；核心Run contracts |
| 桌面 | 相同文档定位、脏保存/Escape/前后退、双工作区/实例迟到、关闭Studio不擅自终止后台Task | App/Studio IPC与前端领域tests；真实Electron |
| 回归 | PM2编辑/批状态/Excel、浏览器/代理/模型/设置、独立Studio保存执行 | 原smoke及隔离迁移/全量测试 |

真实验收使用受控本地fixture页面：输入本次参数→点击→页面显示结果及提交计数→读取并截图；两次启动显示不同参数，各Task变量初值独立。并发2、总量3核对计数；长等待期间停止，核对后续点击未发生；服务中断后查询既有历史，不重新点击。fixture预留登录态检测只供后续PM5，PM3不假称保留环境通过。

阶段门禁：后端pytest/Ruff/mypy；前端Vitest/typecheck/lint/build；OpenAPI、scripts、structure、diff检查；PM3覆盖脚本核对完整48功能/178验收/18契约/7门槛集合及本阶段子范围。特别纳入容易漏掉的C17和数据引用保护，不只数3个管理包。历史PM0–PM2报告保留，后续场景不提前填证据。

Windows/macOS都为目标平台；本机实跑记录具体OS/架构和开发/打包模式，未执行平台显式标记。无法满足真实核心门槛时，该包保持未完成，不能用启动按钮或接口返回202替代运行验收。

## 14. 当前确认点与自审

本次仅设计文档与协作记录；没有业务代码、数据库迁移、页面占位或主线合并。待确认的整体选择是方案A，以及第5节参数唯一定义/自动化默认覆盖的契约细化。确认后按writing-plans生成详细单阶段任务和测试，再按确认的计划开发。

自审：已区分正式核心与WIP、PM3配置与PM4数据执行、PM5环境持久化；Task/Run同事务、操作接受与运行成功、清理与历史结果分离；未减少已确认的重复使用规则；每包有实际退出条件。未为未实现功能新增假页面或假成功计数。

独立复核闭合：已补launch claim先落库的崩溃窗口、Batch停止逐Run稳定子操作身份，以及内部artifact GET与用户文件选择授权的分界。重启后不自动恢复本批；上述修订仍属本次待确认设计。
