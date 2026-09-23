# Studio 项目接入修正

- 日期：2026-09-23；状态：confirmed（各项仅限列明证据）。
- 任务来源：用户当前目标附件 `375d80e1-3f20-4e27-adec-11c7f6e613b0/pasted-text-1.txt`。
- 基线：`f0c204b3`；范围仍为 213 节点，删除的 14 个通知节点不恢复。保留其他工作树改动。

## 窗口与入口

- 问题来源：复核 `StudioWindowController`、`AutomationDetailPage` 的真实调用。换区成功仍带旧项目/流程参数；并发开窗可共用一次离开确认后销毁新窗口；查询缓存键没有项目；新建自动化的 Studio 按钮只读取空的 baseline。
- 修复：成功换区不携带旧上下文；失败/取消保留原窗口；相同目的地请求合并、竞争目的地明确拒绝；无效上下文拒绝；查询按项目隔离；按钮传当前选择的工作流。
- 验证：新增用例先出现 5 项失败，修复后主进程窗口、自动化详情和编辑器 3 文件 38 项通过；TypeScript 与修改文件 ESLint 通过。
- 限制：这是组件/主进程模拟测试，不是正式 Electron 验收；项目权限、资源、运行/统计归属仍未整体关闭。

## 已确认的后续缺口

- 阻塞文档接入：正式 `exportWorkflow()` 没有 `schemaVersion`，标识为 Nano ID；此前后端测试仅带版本号/UUID 样例，不能代表真实 Studio。
- 阻塞项目归属：现有 `ProjectAutomationRow.workflow_id` 关联尚未被新项目筛选复用；JSON 的 `projectId` 不能替代完整的项目生命周期和授权校验。
- 阻塞结果/统计：现有项目执行器与 Studio 迁入执行器使用不同运行表，项目准备器仍限制四节点顺序链；不得仅凭目录可读宣称 213 节点已接入项目运行或统计。
- 以上按文档与归属 → 共享运行/数据/统计边界 → 正式 UI 链路的依赖处理；不重新设计执行器。

## 文档双向读取（已修复上述文档阻塞）

- 根因：迁入编辑器 `editor-store.ts/exportWorkflow` 输出无版本号的直接图和 21 字符 Nano ID；项目目录只读带包装/UUID 的格式。相反，Studio 直接读取包装文档时没有顶层 nodes，无法导入。
- AutoFlow 必要适配：读取边界解包/包装同一份数据库文档，恢复分离的布局；工作流引用接受既有 UUID 和 Nano ID，其他资源/参数标识仍坚持 UUID。不更换现有文档 ID，不改写数据库历史记录，不把旧 config 节点格式当作新 data.moduleType 格式。
- 证据：真实导出形状用例先出现 3 项失败；反向读取先出现 `KeyError: nodes`。修复后文档/目录/规则/仓储/准备事务共 74 项通过；原始数据只读不改写、保存后 revision +1、节点/连线/变量/位置完整往返均有断言。
- Ruff、7 个后端文件 mypy、OpenAPI 一致性通过。目录仍使用现有项目执行器能力校验，不把可保存或可读取表述为 213 节点项目运行已完成。

## 文档项目归属与写入保护

- 复用 `ProjectAutomationRow.workflow_id` 的唯一绑定作为已关联流程的项目归属；未关联的项目草稿仍保留已接入的 `projectId`，不建立第二套项目 ID 或新数据库表。
- 两个目录/文档读入口统一解析归属；项目列表在 SQL 中先筛选再分页，撤销上一提交中全表加载后过滤的做法。
- 将原项目仓储的生命周期守卫提取为数据库层共享函数；Studio 与目录写入在事务内校验同一状态。省略项目字段不能解绑或绕过归档；不能将其他项目的草稿绑定到当前自动化；删除项目后两个文档目录均不暴露其内容。
- 有项目自动化/历史运行外键引用的工作流删除返回 `WORKFLOW_IN_USE`，保留原文档，不能变成未处理的数据库异常。
- 证据：新增场景先失败 6 项；文档、项目仓储、准备事务、目录合同、自动化及删除合同累计定向回归 58 项通过。TypeScript/ESLint 在本轮窗口提交已通过，renderer/main/preload 构建完成（依赖包注解与动态导入警告保留）。
- 此处只关闭文档归属/写入边界；运行、Debug、拾取、录制的项目资源授权和项目删除中的活动清理、数据资产、统计以及正式 Electron 项目闭环仍未完成。没有更新节点真实验收计数。

## 项目工作流首次加载保护

- 首次读取项目流程期间不挂载编辑器/助手，防止早期编辑被异步载入覆盖；读取失败显示明确错误和重试按钮。
- 重连重读使用请求代次淘汰旧响应，卸载后不导入；读取成功后同工作区重连保留草稿；响应文档 ID 必须与入口 ID 一致。
- 新用例先出现 3 项失败；修复后的 StudioApp、窗口控制、Studio 集成和自动化详情共 46 项通过。TypeScript 和两个变更文件 ESLint 通过。
- 最新加载保护改动后已再次完成 renderer/main/preload 构建；构建记录 `/tmp/autoflow-studio-project-build.log` 仅为本机临时日志，不作为正式包实测证据。
- 当前未运行正式 Electron 项目入口用例。旧 `smoke-studio-window.mjs` 仍断言后端路由不存在且 Mock 存在，不适用于现有真实后端；后续项目专项应复用 `electron-cdp.mjs` 的隔离启动和真实鼠标/键盘操作，不引用这个旧 smoke 的通过状态。

## 台账核对备注

- 当前 `capabilities.json` 的 639 条后端槽位为 617 条通过/22 条待真实执行；但 `backendMigration.status` 仍有 11 个“三槽位全部通过、聚合状态待验收”的条目，故聚合读数是 180/33，不能直接当成新增 11 个实现缺口。下一次核销引用这些已有证据，不重复运行节点族。

## 空项目入口与正式窗口文档闭环

- 来源：项目自动化创建依赖已有工作流，空目录此前没有打开项目 Studio 的入口，导致首个流程无法从项目内创建。
- 修复：目录复用现有开窗 IPC，传当前 workspaceKey/instanceId/projectId；与详情页共用宿主回调；归档不显示编辑入口，刷新/停写期间禁用。
- 验证：目录组件/页面 12 项、项目工作区 20 项、自动化详情 6 项通过；新增入口用例先失败后修复。TypeScript、修改文件 ESLint、renderer/main/preload 构建通过。
- 正式证据：`docs/migration/studio-backend-migration/evidence/project-integration/formal-documents-electron-HMKavH/result.json` 及同目录截图；脚本 `scripts/smoke-studio-project-documents.mjs`。
- macOS arm64 开发构建真实 UI：新建项目 → 空目录 Studio → 配置打开网页节点 → SQLite 保存及项目归属 → 正常关闭取消保留草稿 → 保存后关闭且 revision=2 → 项目入口重开及参数恢复 → 新建自动化选择流程并打开对应文档。未修改真实用户数据库。
- 首次脚本读取旧版 `data.config.url` 失败，改为迁入版 `data.url`；第二次 Cmd+W 未触发预期关闭对话框，未标通过。最终使用 macOS 原生窗口的 AXCloseButton 真实点击通过正常关闭协调，未调用 BrowserWindow.destroy/内部 Store。前两次失败记录保留。
- 已发现但非本块阻塞：正式窗口字段规则和全局快捷键接口返回 404、部分启动命令返回 501；后续服务合同核销时处理，不用当前保存闭环证据掩盖。此次不声明这些接口、项目运行/数据/统计或其他平台完成。

## 运行项目归属与归档清理

- AutoFlow 必要适配：`WorkflowRunStart`/运行记录增加可选 `projectId`，前端从宿主入口注入；同一事务解析已存文档的权威项目归属并校验生命周期，省略或伪造项目字段不能绕过归档。未保存草稿可运行且不创建文档；旧未分项目启动请求哈希不变。
- 项目归档/删除影响检查纳入迁入执行器的活跃槽位。归档在 `closing` 等待，实际停止并清理后才可完成；旧活跃记录通过已存文档只读解析归属，不改写用户数据或历史迁移。
- 新增失败用例修复后：文档/运行仓储与接口定向回归 52 项；生命周期 14 项；真实 worker 的未保存草稿及暂停调试归档合同 2 项通过。后两项仅执行纯变量节点，不作为浏览器证据。
- TypeScript、修改文件 ESLint、后端 Ruff/mypy、OpenAPI 一致性通过；renderer/main/preload 已构建。首次 OpenAPI 导出因机器负载超过现有 30 秒上限，重试通过，未放宽时限。
- 正式窗口初次项目五节点回归：真实网页动作、PNG、失败暂停与正常关窗停止均完成；最终重开时，历史事件短暂恢复 `running` 后的离开提示没有随终态解除。失败保留于 `evidence/project-integration/formal-electron-PQNROY/`，不标整链通过。
- 共用离开保护修复：仅当原请求没有草稿决策、运行已确认结束且没有其他活跃资源时继续原请求；草稿/服务身份/资源身份检查仍执行。新增用例先失败，现离开保护 42 项通过，运行上下文/事件归属/启动协议连同前一版离开测试共 52 项通过。
- 下一次正式回归在非日志标签下检查终态文字失败，`formal-electron-FtgFds/` 保留；脚本改为真实点击执行日志后检查同一断言，未改执行器或放宽断言。
- 最终重跑通过：`docs/migration/studio-backend-migration/evidence/project-integration/formal-electron-RnPj0V/result.json`，构建 SHA256 `e2c90f67ae61a308702e34991dd44819087f288717ba96037e053a94f7fe51f6`。macOS arm64 开发入口：项目进入 → 五节点真实配置与连线 → 保存/原生关窗取消及保存/重开 → 独立 CloakBrowser 执行、结果与 PNG → Debug 失败保留现场/结束清理 → 长导航中原生关窗取消及放弃停止/重开 → 内核缺失启动失败且无残留。三种运行均具备一致项目归属；不使用 Store 写入，不修改用户数据库。
- 范围限制：这里尚未关闭运行读权限、Profile 等资源授权、拾取/录制归属、项目数据资产/统计/任务运行桥接、正式包和其他平台。213 节点计数及剩余 22 项未变。

## 项目运行历史、结果和事件隔离

- 实际缺口：运行历史未按项目筛选，详情/日志/结果/产物/变量诊断接口忽略传入项目，SSE 回放包含其他项目运行。新增 HTTP 回归先失败 14 项，前端请求绑定先失败 1 项。
- 修复：在既有运行路由集中校验可选 `projectId`，列表在 SQL 过滤后计数和分页；宿主项目覆盖请求中其他项目参数，下载/导出同样带范围。旧记录只读关联原文档归属，归档历史可读，已删除项目不再暴露记录。
- SSE 查询绑定窗口项目，对不属于该项目的运行使用同序号 `studio:cursor` 空事件，不暴露运行身份/内容；沿用原事件序号及断流补读，不引入第二套事件系统。按已存运行归属查询，删除后的项目事件同样隔离。其他非运行服务的项目权限未在此块宣称完成。
- 验证：运行读取/原仓储 23 项；项目生命周期/真实 worker/原运行接口 31 项；读取/SSE/生命周期 32 项；前端历史、结果、诊断合同 14 项；项目请求/断流游标/外来事件保护 7 项通过。TypeScript、ESLint、Ruff/mypy、OpenAPI、renderer/main/preload 构建通过。
- 正式 macOS arm64 开发入口：`evidence/project-integration/formal-electron-hpS5Ek/result.json`。原五节点全链回归，加原项目历史下拉中成功/失败/停止三项、点击成功记录查看日志、正常关闭后从 UI 创建第二项目并打开 Studio，第二项目没有运行历史或原项目日志，后台原项目仍保留三条记录。
- 首次新增 UI 用例误将 Radix `SelectNative` 当作 HTML select 检查 options，保留失败证据 `formal-electron-Mj0nhG/`；修正为真实展开菜单检查三种终态并选择成功记录，没有改产品或放宽运行断言。
- 下一缺口：运行控制/交互命令的项目归属、拾取/录制、资源引用、项目数据/统计。并行的 SSH 五节点仅补专属真实受控服务证据，由主线统一安排 Electron，尚未核销剩余节点槽位。


## 运行控制与交互回传的项目边界

- AutoFlow 必要适配：将既有前端项目 URL 适配集中到 `scopeStudioUrl`，文档、运行、停止/Debug、交互请求及回执都带宿主项目；事件客户端保持创建时的项目身份。后端在分发前检查运行/请求归属，断点在解析实际活跃运行后检查。命令的原始幂等负载和执行语义不变。
- 真实 worker 回归覆盖外项目停止、单步、继续、变量修改/回执拒绝，以及输入请求外项目读取/回答拒绝；原项目回答得到整数 42，重复命令不重复执行。旧流程级变量诊断读/清除同样先按项目筛选。
- 七类交互命令及四类状态查询的合同覆盖共享边界；不将这些路由测试声称为真实语音/脚本/平台动作验收。运行协调器复用既有在途请求身份，普通助手命令仍由原助手服务分发，本块不声明助手项目权限完成。
- 定向后端 52 项、前端 52 项、实际 HTTP 事件/回执 4 项通过；Ruff、mypy、TypeScript、ESLint、renderer/main/preload 构建通过。OpenAPI 首次一致性检查发现生成文件仍缺新增查询字段，重新生成后检查通过，未放宽检查。
- 正式 macOS arm64 开发入口：`evidence/project-integration/formal-electron-GS1ler/result.json`；最新共享边界下，项目五节点、PNG、失败调试、正常关窗取消/保存/停止及第二项目历史隔离完整通过。此处未改真实数据库，未将开发入口计作正式包。
- 专项日志归档：`evidence/project-integration/run-controls-2026-09-23/`。SSH 独立专项已提交 `2ec6e0d7`，正式窗口验收由主线串行执行后再核销。


## SSH 五节点真实窗口核销

- 正式 `smoke-studio-backend-b6-ssh.mjs` 通过，证据 `evidence/b6/formal-ssh-electron-nUEoTd/result.json`。从主窗口真实点击进入 Studio，画布逐一添加/输入/连线/保存，原生正常关窗重开，再真实运行。回环 SSH 使用临时磁盘及受控命令子进程，非 Mock 执行器。
- 命令输出 `ok\n`、退出码 0；上传和下载 59 字节内容一致，SHA-256 在证据中；五节点日志无密码，SSH 连接/命令进程已结束，无遗留受管 worker。用户数据库、密钥和外部主机未使用。
- 独立 worker 认证失败、远端缺文件、断开后执行、命令错误及运行中停止，共 9 项测试通过。UI 异常变体、Intel/Windows、冻结包和外部主机仍待对应验收，未以本次成功替代。
- 能力台账只核销五个 `BE.ssh_*.real-execution`：639 条槽位现为 622 通过/17 待真实执行；聚合状态 185/28（11 个已有槽位但平台限制待核销）。旧 B0 汇总数字不一致已按当前能力台账修正，来源/许可证和修改历史保留。

## 项目永久删除的 Studio 清理

- 复用现有项目删除协调：先清理工作区 runs/<runId>，完成后在同一事务删除该项目运行、关联索引、文档及保存回执。不删除用户绝对输出、其他项目、未归属运行或共享模块。旧运行通过既有文档归属解析；在自动化绑定被删除之前解析所有归属。
- 清理权限失败、路径越界或符号链接均保留 deleting、持久化索引与重试责任；障碍移除后再完成删除。宿主传现有 workspace 路径，不读取或改写用户数据库。
- 证据：`docs/migration/studio-backend-migration/evidence/project-integration/delete-cleanup-2026-09-23/result.json`。旧实现实际对照 3 项失败；当前 18 项真实 SQLite/磁盘回归通过，Ruff/mypy 通过。新增测试的 residue 初始预期不匹配已更正为现有精确边界错误，失败日志保留；保护断言没有减少。
- 这是基础设施与集成证据，不等同于正式 Electron 删除全链、项目统计、录制归属或跨平台验收。

## 项目运行数据读取与正式 UI 验收

- 复用现有运行事件与产物索引，在 SQL 按项目、运行、节点、类型过滤后计数/分页；不建立第二套资产表，不复制文件。新产物记录真实登记时间；旧产物只回退绑定事件时间，无证据时返回 null。
- 数据目录增加自动化运行数据入口：分页、提取 JSON/文本和安全图片预览、完整下载、按 executionId 对应节点日志。大值按需读取，图片/文件校验登记大小与哈希；错误、空状态、迟到响应、Blob URL 回收均有测试。
- 后端 41 项、前端 25 项，TypeScript/ESLint/Ruff/mypy/OpenAPI 和 renderer/main/preload 构建通过。正式证据 `evidence/project-integration/formal-electron-L5Kf5n/result.json`，汇总 `data-assets-2026-09-23/result.json`。macOS arm64 开发构建真实操作完成五节点与项目数据读取，原生保存 PNG 后与登记产物逐字节相等，失败调试/正常关闭停止/重开/第二项目隔离回归通过。
- 失败证据全部保留。早期下载在等待 macOS 保存确认；后续连线失败经被动事件追踪确认是测试 helper 居中滚动返回临时坐标，鼠标点击落入画布。改为 nearest，并使用真实缩放按钮与可见节点落点检查；没有改 Store、产品缩放逻辑或四条连线断言。
- 本块不等于所有数据管理完成：业务表写入桥接、统计、拾取/录制归属、正式包及其他平台仍保留。现有录制会话缺项目字段，不能凭审查文档或工作区总数伪造项目录制统计。节点槽位仍 622/17。

## Studio 运行统计与原始记录下钻

- 复用 ProjectStatisticsService、现有运行/事件/产物/计划执行表；原任务统计及冻结 TaskPage 合同保持原语义。新增 Studio 只读统计按项目、工作流、启动时间和状态在 SQL 聚合，分页读取运行元数据；不构造假 taskId、不加载文档或大值到统计。
- 指标包含真实状态、成功率、总耗时（含暂停/清理）、节点执行/产出结果次数、文件/诊断、Debug、失败节点/流程前十及最新活动。计划启动来源有联查证据才归类，无证据为 unknown；产出结果次数不等于业务记录条数。录制尚无项目归属，recordingCount 明确 null 并说明，未把全工作区总数或零当成项目事实。
- 发现并修复：混合时区 ISO 字符串排序导致最近活动和分页不正确；改为 SQLite julianday 与 aware datetime。首次正式 UI 又发现错误事件名造成节点计数0；原执行器实际写 execution:node_start，修正查询和样本并新增真实 worker 生产事件回归，不支持自造 alias、不改变预期5。
- 26 项后端（含原11项任务统计、1000轮/2001事件、计划来源去重、旧文档归属、真实worker），20项前端通过；类型/lint/OpenAPI/构建通过。完整正式证据 `evidence/project-integration/formal-electron-oV2m53/result.json`：实际1次成功、5次节点执行、1个PNG，从统计真实点击到同运行日志和产物；同时通过此前正常关窗/Debug失败/停止/另一项目隔离。汇总及失败证据见 `statistics-2026-09-23/`。
- 仍保留录制统计、项目资源/任务桥接及拾取录制生命周期；本块仅关闭已有持久运行事实的统计消费，未声明整个项目集成完成。下一步先补会话归属与准入原子边界，再补录制次数。


## 拾取／录制项目归属、生命周期与录制统计

- 已确认并修复启动前无项目占用、录制历史无归属的问题。沿既有 SQLite 生命周期事务发布 browser starting 占用；停止/取消/清理失败保持原 worker/resource 边界，归档收尾看见 starting/ready/closing。HTTP browser/picker/recorder 使用宿主 projectId；关闭和尾部读取在 closing 仍可完成，新采集和审查写入受项目停写保护。
- 0020_recording_project_scope 只增量新增 nullable 归属及 documentId，不改历史迁移，不接触用户数据库。未知历史保留无归属，项目删除按现有 project_id 清理与事件级联。新录制按项目/文档/时间计数，重复命令、暂停/恢复和多个步骤不会重复计数；运行状态筛选下录制指标明确不适用。
- 同session换document和SQLite naive时间两个真实缺陷已由红测发现并修复。stop-tail原测试将两个新commandId错误要求相同；现在明确验证两个指定ID、451步不变，以及原命令重复请求的精确200步回执，未删断言或改生产幂等行为。
- 正式macOS arm64真实证据：project-integration/formal-recording-electron-eUd5nT/result.json；真实项目入口、录制/暂停/恢复、审查生成保存、原生AXCloseButton关闭重开、独立浏览器重放及项目统计1录制/1运行均通过。65项迁移、40项既有关联后端、177项前端通过，专项SQL/HTTP详见 inspection-recording-2026-09-23。类型/lint/OpenAPI/构建通过。
- 上节“录制尚缺归属”被本批结果替代。项目资源权限、任务/业务数据桥接、正式包和未测平台仍未关闭，213节点槽位仍622/17，14项删除不恢复。

- 正式包补验 confirmed：PyInstaller/冻结启动及 macOS arm64 本地 unsigned 包实际录制→审查→生成→保存→原生关窗重开→独立重放通过，证据 `formal-recording-electron-xIkcrm/result.json`。Intel/Windows 未验收。下一块为项目批次五节点准入/执行/产物桥；专项当前 3 红 1 兼容通过，尚未完成。

## 项目五节点任务桥接（开发入口与本地包 confirmed）

- 实际准入红测3失败/1兼容通过，沿原目录/准备/图执行器边界接入五节点。保留Studio完整快照；原四节点链保留原解释，不引入第二套执行器。
- 截图共享存储在原项目事件提交后才确认，结果与失败用途分开。ACK未知保留产物，重复路径/符号链接/取消落盘均受保护。单stdin线程与单异步控制分派避免节点等待无法停止及孤立queue线程窃取回执；失败截图5秒上限、不覆盖原错误。
- 实际UI暴露宿主保存重复创建409，修复Toolbar保存身份，专项65项通过并提交9a5995f9。扩展脚本遗漏等待时限造成即时失败，修复helper默认15秒并保留修订增长断言和失败日志。
- 最新开发入口 formal-electron-A3JoOx 已真实通过：五节点、输出和PNG；导航中停止只执行1节点；失败只执行1节点并登记错误截图；修改恢复后再执行5节点。每批确认临时浏览器已关闭，未改用户数据。共享变更后163项后端通过；项目UI18项通过，类型/lint/OpenAPI/构建通过。证据汇总 project-task-bridge-2026-09-23。
- 冻结/PyInstaller172秒、冻结启动、本地unsigned包均通过；formal-electron-6dbukC复验成功/停止/失败/恢复，记录ASAR/后端哈希和包内容边界。其余项目族、资源权限/业务数据、元数据404/快捷键404/启动命令501继续登记，不宣称整体完成。下一块只读调查发现原版字段元数据实际覆盖全部213，现有导出脚本只取前6组造成69覆盖；按最终源码合并顺序迁入，不自造缺失规则。

## 必填字段服务真实迁入 confirmed

- 修复已有导出器只抽早期6组的根因，按冻结源全部字面量更新顺序读取AUTOFIX和后续人工覆盖。批准213/覆盖213/缺0，保存双源及原许可证SHA；生成生产领域常量并接现有鉴权HTTP，不运行reference。原键盘动作虽有源规则但不在批准集，测试明确排除，没有恢复它。
- 2红15绿的真实合同基线修复后17绿；源213逐项差分5项、前端加载/协议38项、结构/类型/lint/OpenAPI通过。首次UI误用“等待”搜索命中wait_page_load，按实际入口“固定等待”修正测试，保留失败证据；产品规则未变。
- 开发formal-electron-LFZSMd及本次unsigned包（路径见shared-services/required-fields-2026-09-23/result.json）均实际验证URL/模式/邮件配置提示，再回归项目五节点/停止/失败/恢复。未执行邮件，Intel/Windows未测。
- 旧源规则69覆盖结论superseded，F1.required-fields四能力ID引用新后端证据，历史Mock503证据仍独立保留。源元数据自身边界不擅改，不等同全节点执行验收。下一块已定位为原生快捷键404与set_verbose_log/set_current_workflow两命令501；按宿主身份/不可重放动作边界适配，禁止假ACK。

## Studio 原生快捷键 confirmed

- 原版九动作接现有Electron globalShortcut，注册只接受Studio主frame及就绪sidecar；旧窗口/服务回调失效。一次注册失败保留同owner旧映射，不unregisterAll、不影响计划热键。清理在窗口失效、服务停用及退出边界执行。
- 子任务先红测发现owner接管复用旧回调的问题；修复为跨owner重新注册，同owner继续原子更新。关联78项、TypeScript/ESLint/构建通过。
- formal-electron-Lg6un9及本地包formal-electron-3Jp5q2实际OS快捷键前台/后台各保存一次，精确revision+1，AXClose注销、重开恢复但不重放、清除注销。继续项目五节点/停止/失败/恢复通过。汇总shared-services/native-hotkeys-2026-09-23。
- 旧快捷键404结论superseded，不等同hotkey_trigger节点实测，622/17不变。两条启动501下一块按冻结源真实消费者核销：当前workflow仅供原版后端热键定向，现由受控窗口持有；verbose是每连接日志推送偏好，不能全局改动持久历史。

## 日志投递与旧启动501核销 confirmed

- 原版连接偏好适配为SSE verboseLog参数，旧current_workflow目标由已验证宿主桥持有。生产不发两条无消费者命令、不假ACK。项目过滤先于日志过滤，空cursor保留序号，历史完整；Mock只做同合同数据投递。
- 恢复冻结源批准节点的重要/系统分类、显式日志级别、独立警告log信封。普通节点success合同保持：初次扩大回归发现改变它使既有导出过滤失败，恢复原合同，断言不改。
- 只读review发现取消旧流仍消费单chunk余帧，新增用例先红后绿，逐帧取消检查保证原afterSeq续读且不取消交互命令。97后端、46前端、类型/lint/OpenAPI/结构通过。
- 开发formal-electron-34nlyy、本地unsigned包formal-electron-VTa59T：真实UI简洁/详细切换、六节点CloakBrowser执行、用户日志保留、完整历史、关窗重开、资源清理通过。PyInstaller170秒、冻结启动通过。失败RIYCJ6/YpG5Mp/jZ4qpZ均保留：只修复测试节点遮挡、原版tooltip及DOM读取boolean，不改产品或验收断言。
- 汇总shared-services/log-delivery-2026-09-23。旧404/501三项已核销；source review另发现节点duration默认0，登记为既有运行诊断缺口，准备在既有调度边界计时。其余项目权限资源/业务数据/全部族准入及17节点实际环境未关闭，用户删除14项不恢复。

## 节点耗时诊断 confirmed

- 恢复冻结源实际毫秒语义，单调时钟计时；真实调试控制器/嵌套Runtime/循环返回失败与抛错取消均覆盖。review发现全worker暂停累计误扣独立分支，改为任务调用祖先计时；复核发现非等待子流程继承祖先，沿原worker后台入口清除计时继承，不改变调试/取消与调用深度。重叠等待仅计一次，不存暂停历史。
- 78关联回归、Ruff/mypy通过；正式开发JYr7gE与最终unsigned包0jega9实际UI创建六节点并执行，五网页动作均记录真实毫秒，用户日志/SSE与持久日志相同，AXClose/重开/资源清理通过。PyInstaller171秒、冻结启动和本地包通过。汇总shared-services/node-duration-2026-09-23。
- 新发现（登记，未核销）：真实worker未注入CredentialReader，凭据管理实现不等同节点可消费；助手会话/命令尚无项目归属。项目现有defaultResources是默认+可覆盖，不是ACL；已异步询问用户是否保持或新增资源白名单，不能擅把默认值变成权限限制。后续继续不依赖此决定的真实凭据消费接入。
- 213节点槽位622/17不变；14通知排除保持；Intel/Windows未测。

## 凭据真实消费 confirmed

- 已核销此前缺CredentialReader：原版variables保持动态get_field，同一StudioCredentialService与系统存储经受管worker私有请求读取。stdin唯一线程直接唤醒解析器；重复/超时/空字段/缺失/EOF/停止有用例，秘密不入SQL/SSE/结果。
- 原生读取daemon每run一项，父3秒预算及20ms停止检查；写锁再次拒绝stopping响应，迟到值丢弃。子流程继承读取器。
- 82关联、8最终实际worker、5管道保护分别通过；Ruff/mypy/OpenAPI/结构通过。开发V7sWWS、最终unsigned包ZMGYx6完整真实UI通过；znjbwe保留前一候选，不冒充最终版本。汇总shared-services/credential-runtime-2026-09-23。
- 下一块高级数据26节点项目任务桥：现有注册和算法可复用，缺catalog准入/resultVariable产出以及无浏览器项目资源链。已有80项用例，先补边界再实际项目任务验收；无新执行器。
- 范围213、622/17及14通知排除不变；项目资源白名单问题未收到答复，其他实现继续。

## 项目资源规则确认 confirmed

来源：本轮用户异步答复。Studio Profile/模型沿用项目默认值，允许任务显式覆盖；不新增资源白名单。此前该问题待确认状态superseded。后续在已有资源边界实现默认继承及显式覆盖，不将默认资源当作ACL。

## 高级数据项目顺序任务桥 confirmed

- 26个列表/字典/CSV节点复用原版迁入执行器；项目catalog准入，resultVariable输出登记，dict_get_path实际JSON null保留。旧四节点格式仍可执行，新数据族保持原字段并使用共享图适配。
- 既有runtime判断实际浏览器需求；纯数据无Profile/内核/代理租约，不预留环境实例，真实worker ACK/停止/持久日志机制不变。重启恢复使用原生身份和每run临时目录标记；真实三个进程用例证明其他运行与用户进程存活。冷进程import回归修复compat re-export循环。
- 26入口81项测试、6项真实worker/保存/无Profile/停止/JSON null/bootstrap恢复，最终关联177项通过；另194广回归及46环境/批次专项保留。Ruff/mypy/OpenAPI/结构通过，冻结约270秒。
- 正式开发IvwKrU及最终unsigned包V8a98L通过无Profile/无内核的CSV解析→扁平化→反转→CSV生成、保存/AXClose/重开、批次与四份持久输出。最终包7k2XEy回归原五节点/PNG/停止/失败/恢复。DQkSqy UI拖动遮挡、CJlcax纯数据仍预留环境的失败证据保留，未放宽断言。
- 汇总project-integration/advanced-data-2026-09-23；26节点旧三槽位未重标，新增项目顺序桥证据，213与622/17不变。公共项目CredentialReader/models端口尚缺，不能把普通Studio凭据通过计到项目任务；控制流/业务表/其余节点族及平台仍保留。下一块依用户明确答复接项目默认Profile/模型且允许覆盖，不新增ACL。

## 项目默认 Profile 与会话覆盖（confirmed）

- 沿用户确认复用 `GET /api/v1/projects/{id}` 的 `defaultResources`；工作区/项目身份下的覆盖仅保留在会话，不混入全局持久配置。项目缺省为空时要求显式选择；已删默认报不可用，不退回全局第一项；非项目 Studio 保留旧第一项行为。
- 工具栏运行、拾取/浏览器共用 `resolveProfile`。修正自动化浏览器显式传旧全局 ID，以及新建计划任务用旧全局 ID 初始化的旁路。已保存计划任务的显式 ID 保持不变。
- 13项专项和六文件60项关联回归通过，类型/lint/OpenAPI/目录检查通过。新建任务通过实际组件选择流程、配置与提交请求核对；Mock只验证消费协议。
- 最终开发证据 `formal-electron-abbWNN`：项目默认第二项、真实选择覆盖、刷新、交互浏览器启动/关闭、编排保存、原生关窗取消与保存、重开恢复默认并再次显式选择、独立CloakBrowser五节点/PNG、Debug失败保留/清理、运行中关窗取消/放弃停止、内核缺失与第二项目隔离全部通过。
- 早期 `NBHTTk` 仅是补交互浏览器旁路之前的开发证据。原生HTML select不等同名字为SelectNative的Radix控件；最终使用焦点明确的WebContents与真实字符键选择，不直接写value/Store。15次失败保留于汇总，包含输入方式、错误断言字段、检查接口漏projectId，以及浏览器starting误认ready的测试脚本问题，不修改生产以掩盖。
- 正式目录包正在验证最新构建；结果统一写入 `project-integration/profile-defaults-2026-09-23/result.json`。模型默认值、项目worker凭据/模型端口仍未完成；213节点及622/17不变。

- 最终 unsigned macOS arm64 目录包 formal-electron-UxcAqm 已通过同一完整链和包内容边界；正式包前次 OZGyVg 的启动等待超时另存失败证据，总16次失败未删。开发/包均真CloakBrowser，Intel/Windows未测。

## 资源变化后的运行重试 confirmed

- 协调器在资源解析前复用原运行资源快照、保留原请求哈希校验；同ID不同草稿/布局/身份/调试参数仍409，不以ID相同绕过内容核验。成功/失败/停止记录重试不重放worker，不重读秘密。
- 3红复现后，14专项及关联总51通过，Ruff/mypy通过。真实SQLite＋模拟worker边界，非真实模型证据；正式入口将在模型默认值闭环中回归。证据project-integration/resource-retry-2026-09-23。

## 项目模型默认值与覆盖 confirmed

- 用户选择沿用默认+覆盖已落地；ModelService复用现有排序和启用选项，协调器仅填执行副本；15 AI入口平铺/嵌套及模块依赖覆盖，无秘密写库。保留原始快照，worker文档ID沿旧身份规范。
- 前端面板/小助手隔离项目覆盖，加载失败保留旧备用配置；迟到结果被代际检查拒绝。12组件+8HTTP专项包含在74关联回归，后端52/45/33分组重叠分别登记。类型/lint/OpenAPI/目录/构建通过。
- 正式开发tBtjEa、最终unsigned包2pmiUF真实UI14节点、保存AXClose重开、受控模型11对话+2媒体、Cloak视觉点击与LangGraph助手默认/覆盖通过；同包RjFuGN完整五节点/Profile/失败Debug/正常关窗与清理回归通过。原RIMkoF、ZhvnYU、zAFzR4脚本定位/硬编码视口失败保留，修改后仍精确断言。
- OpenRouter aion-labs/aion-2.0独立真实worker一次调用通过，8.38秒，原始响应/usage/清理证据单列；主模型DB URI ro+query_only，无主库写入，不混作UI证据。冻结175.6秒，前端构建33.5秒。
- 证据project-integration/model-defaults-2026-09-23。下块项目worker仍缺models/credentials端口，助手会话/命令归属独立待做；17实际环境/平台槽位不变，不恢复14通知。

## 助手项目归属剩余缺口（confirmed，只读追踪，未核销）

- 来源：workflow_ai.py助手路由与workflow_assistant.py仓储、workflow_models.py会话行、api/config.ts和aiAssistantStore.ts。会话无project_id，前端ai-assistant路径不附projectId，Store单份会话历史缺scope隔离。模型选择隔离不等同会话隔离。
- 命令：StudioEventCommandMux.command_run对助手返回None，claim/ack/query未接项目归属；SSE仅过滤runId事件，ai_assistant事件需按session所有者过滤为同序号cursor。
- 产物：AssistantFileStore按全局内容hash读，现路由未验证session/project引用；必须覆盖附件、消息和pending action的实际引用后授权。已确认项目默认资源规则不取消这些数据归属要求。
- 最小依赖：沿既有recording的nullable归属/guard_project/404模式，旧null会话不推断项目，保留standalone历史；共享迁移、服务协议由root统一实现。此项阻塞助手项目完整交付，不阻塞当前项目worker凭据链，按既有剩余清单排队。

## 项目任务凭据消费 confirmed

- ProjectGraphExecutor注入已有CredentialReader；普通worker读取器只加可选项目协议元数据和deadline，项目stdin单线程直接唤醒，事件ACK仍走原异步控制。bootstrap复用StudioCredentialService.resolve，无新秘密库/ACL。
- 实际worker红测7失败→专项通过；复核空part触发协议失联，按普通coordinator保留原文并禁止空part读取。随后真实0.05秒预算/0.25秒原生读取误报成功，新增红测后通过reader任务局部deadline修复，BaseException仅跨过原版引用解析器回退，由provider节点边界转为既有超时失败。敏感结果redaction保留，内部isTimeout布尔分类避免错误文本脱敏后丢失超时类型。
- 最终95关联回归、Ruff/mypy、OpenAPI/目录、98脚本通过。新增测试导入的旧fixture补正确类型注解，不删用例或放宽断言。review独立25关联及普通reader5项通过，与95有重叠不累加。
- 开发Cy7fmp真实UI凭据+项目任务五节点成功，停止/失败/恢复、PNG、系统凭据UI删除与进程清理通过。1iu9Wz失败仅画布搜索栏遮挡节点中心，定位改实际未遮挡内部点；保留原断言与失败截图。
- 最终166秒冻结及本地unsigned包vBd3bn覆盖全部同链，包含deadline修复。汇总project-integration/credential-runtime-2026-09-23。未修改用户数据，Intel/Windows未测；213及622/17不变。
- 下一交付：项目任务模型端口，沿准备/派发/私有worker绑定接主应用ModelService；不能把秘密放入Batch/PreparedContent/CoreRun快照。依赖调查已确认纯数据resource_query/resources早退会丢模型规则，catalog当前只准入31已桥接节点；资源与执行上下文齐备后再放行相应AI族。助手会话项目隔离另有上节直接证据，未核销。

## 项目任务模型端口（后端已验，正式UI待验）

- 用户确认项目资源沿用默认值并允许显式覆盖。项目启动真实SQLite入口已核对：无浏览器AI任务冻结有效modelProviderId，不读取Profile；纯数据任务不因未使用的模型默认值阻塞。
- 15个批准AI入口与实际执行器注册逐项一致。派发器从运行快照的执行副本补默认模型，显式modelId优先；复用ModelService绑定及WorkflowModelGateway，私有worker启动消息传递密钥，不写持久资源/文档/事件。模型错误在启动worker前明确失败。
- 受控本地HTTP模型的真实项目worker调用、输出事件、密钥不落SQLite、缺默认/非法ID失败及项目任务回归通过。关联123项与新增目录注册1项、Ruff/mypy/OpenAPI/结构通过；证据project-integration/project-task-model-2026-09-23/result.json。
- 本批尚无项目AI任务正式Electron UI、最新冻结包或项目任务外部真实模型验收；助手后端项目归属、其余任务节点族/数据桥及17个实际执行槽位仍待完成。下一块先做助手项目归属，正式UI可与此独立推进。

## 小助手会话项目归属（后端和前端合同已验）

- 0021增量迁移将新会话绑定项目，旧会话保留独立入口；HTTP会话、附件、命令、SSE和前端项目Store按归属隔离，活跃会话接入项目归档预检。
- 专项31后端及21前端测试、Ruff/mypy/TypeScript/ESLint/OpenAPI通过，详见 `docs/migration/studio-backend-migration/evidence/project-integration/assistant-project-2026-09-23/result.json`。
- 正式Electron开发入口与本次macOS arm64本地unsigned包均以真实鼠标键盘完成项目小助手会话、工具批准/拒绝、MCP、取消、保存、正常关窗重开恢复和独立入口隔离。PyInstaller冻结与包内启动通过。夹具由公开项目接口设置默认模型；外部真实模型、Intel/Windows及其余项目集成未核销。213节点622/17槽位不变。

## 项目AI任务正式UI与模型端口（confirmed）

- 在既有项目模型端口证据中追加正式Electron开发入口 `formal-project-ai-task-electron-AArRkj` 与macOS arm64本地unsigned包 `formal-project-ai-task-electron-IrOiVg`：真实UI从项目进入Studio、编排并保存AI摘要，关联项目自动化；两次批次真实受管worker分别使用项目默认与节点显式覆盖模型，日志、输出、清理及持久文档均核验。
- 模型来自主应用管理，项目默认提供方由公开项目接口仅作为测试前置数据设置；模型服务是本地受控HTTP夹具。项目任务外部真实模型、其余项目节点族/业务数据桥、Intel/Windows仍未验收。213节点622/17槽位不变。

## 项目任务条件与循环图（confirmed）

- 根因是项目准备层仍强制顺序链，虽然项目worker已复用正式WebRPA图执行器。现对v3图保留原拓扑并使用现有图验证；旧chain/v1路径不变。项目目录放行九个批准且真实注册的基础控制/变量类型，无新执行器或迁移。
- 后端153项关联与54项冻结差分/运行时测试、Ruff/mypy/OpenAPI及PyInstaller通过。正式Electron开发 `formal-project-control-electron-IgPlCr` 和macOS arm64本地unsigned包 `formal-project-control-electron-uL7WoF` 真实UI完成三轮循环、条件真分支、假分支无副作用、输出及清理；包哈希和边界见 `project-integration/control-project-2026-09-23/result.json`。
- 项目UI其余控制分支、子流程/模块依赖、业务数据桥和未测平台仍待核销；普通Studio既有B3源码差分不冒充项目端到端。213节点622/17槽位不变。

## 项目任务控制流同族扩展（2026-09-23）

- 沿用户已确认的项目默认值＋任务显式覆盖规则执行；本次为纯数据流程，不读取浏览器配置，也不新建资源白名单。
- 同一正式Electron项目工作区以真实UI新增第二条流程：全局列表／字典初值，列表和字典各遍历两轮，无限循环中break、两轮次数循环中continue，最后写出visited=4。开发`formal-project-control-electron-fTx2GB`及同一冻结后端的macOS arm64本地unsigned包`formal-project-control-electron-dsxJew`均通过；每轮尝试、被跳过节点无尝试、输出和进程清理见既有`project-integration/control-project-2026-09-23/result.json`。
- 首次新脚本只等可见成功日志而超时，改为核对项目作用域下持久文档；失败尝试`formal-project-control-electron-dlPeHa`保留。其他嵌套组合、子流程／模块依赖、业务数据桥和未测平台仍待核销，213节点622/17槽位不变。
- 追加列表循环体内的条件分支，正式UI两轮分别命中真假路径各一次。开发`formal-project-control-electron-WNL3g2`与同一冻结包`formal-project-control-electron-iiRx21`通过；其他嵌套组合与模块依赖仍按未验收处理。

## 项目画布子流程与真实网页动作（2026-09-23）

- 项目预检保留未连线的可视定义区，拒绝可视节点参与执行连线及只有可视节点的流程；项目图执行器复用原Studio的`_WorkerCanvasSubflows`，子上下文沿已有事件与变量通道，不新造子流程算法。项目目录新增批准的`subflow`调用入口。
- 单元与真实项目worker验证组内变量仅在调用时产生，尾节点获得42。关联156项、Ruff/mypy/OpenAPI通过；PyInstaller重构建与macOS arm64本地unsigned包均通过。正式UI开发`formal-project-control-electron-Ipn9Fb`、包内`formal-project-control-electron-rOVoqM`从项目页建流程、保存、关联自动化并运行，组内CloakBrowser打开本地受控网页，结束后无浏览器残留。包哈希与失败脚本尝试见原`project-integration/control-project-2026-09-23/result.json`。
- 尚未核销历史`subflow_header`定义、自定义模块冻结依赖、其他嵌套组合、业务数据写回、Intel/Windows及17个环境执行槽位；213节点总范围不变。

## 项目任务外部服务共享入口（2026-09-23，confirmed）

- 来源：项目图执行器原未装配`external_integrations`，使Studio已迁入的API/邮件/SSH等节点在项目批次中无法使用；项目worker现在复用现有`WorkflowIntegrationGateway`并在所有退出路径关闭，不新增执行器。
- 临时工作区真实worker向本地HTTP服务发送中文JSON、写入输出事件，另验证在途请求取消后无输出且worker空闲；关联17项通过，Ruff/mypy通过。证据：`docs/migration/studio-backend-migration/evidence/project-integration/external-gateway-2026-09-23/README.md`。
- 正式项目UI及各外部供应商独有分支仍待验收；自定义模块冻结依赖和项目数据写回不在本块中核销。

## B6 Telegram 正式窗口受控 TLS（2026-09-23，confirmed）

- `notify_telegram` 是保留的213节点之一，未恢复其余14个排除通知节点。正式Studio经真实UI配置、保存重开后，生产执行器及httpx向临时TLS夹具发送中文Bot API JSON，成功与`ok=false`失败各一次；节点日志未泄露测试Token，Electron和夹具端口清理断言通过。
- 前几次失败均是测试夹具路由和同步探针错误，保留原失败记录；证据在`docs/migration/studio-backend-migration/evidence/b6/formal-telegram-electron-JqCVt8/`。节点级台账由629/639变为630/639；第三方真实投递、Intel/Windows及冻结包不算通过。

## 项目任务递归自定义模块（2026-09-23）

- 继承用户确定的项目默认资源＋任务显式覆盖；无资源白名单。项目准备复用既有模块仓储冻结递归依赖，项目 worker 复用 Studio 的模块执行器；保留原模块更新、输出及循环引用语义，未增加第二套调度器。
- 项目任务证据查询现在能返回冻结模块子节点名称和执行作用域，任务详情展示模块与轮次。首次正式验收暴露循环头前后上下文变化被误判为历史损坏，改为使用节点完成时上下文并加回归断言。
- 后端32项、前端28项及Ruff/mypy/TypeScript/ESLint/OpenAPI/构建通过；正式 Electron 开发入口真实 UI 创建模块并运行项目任务，输出42、子节点作用域和清理通过。详见`docs/migration/studio-backend-migration/evidence/project-integration/custom-module-task-2026-09-23/README.md`。
- 冻结包、其他平台、运行期交互命令与跨工作流文件调用仍未核销，不能视作完整项目模块族关闭。
- 在`9b256a25`提交后重建PyInstaller和Electron目录包；正式macOS arm64包从真实UI重跑控制流、画布子流程和项目自定义模块任务全部通过。包内app.asar、backend和Electron可执行文件哈希及独立工作区结果见`formal-project-control-electron-HSqFSS/`。Windows／Intel及运行期交互模块仍待验收。

## 项目任务跨工作流调用（2026-09-23）

- `06171cd2` 复用 Studio 的工作流依赖冻结及嵌套执行器；项目范围内解析 `run_workflow_file`，由项目 Studio 选择稳定工作流 ID。子工作流的浏览器/模型需求、子节点事件和变量回收随运行快照传入项目 worker，跨项目缺失引用在启动前拒绝。无资源白名单；项目默认值与显式覆盖规则保持不变。
- 后端关联 28 项、前端专项 51 项、Ruff/mypy/TypeScript/ESLint/OpenAPI、renderer/main/preload 和 PyInstaller 构建通过。正式 Electron 开发入口 `formal-project-control-electron-IVC9bC` 与 macOS arm64 本地未签名包 `formal-project-control-electron-IHRniA` 均以真实 UI 保存并运行子工作流，受控网页、子节点日志、输出 42 和进程清理通过。证据及包哈希见 `docs/migration/studio-backend-migration/evidence/project-integration/project-workflow-task-2026-09-23/README.md`。
- 开发入口执行时代码尚未提交，`result.json.gitHead` 指向父提交；包内复验在 `06171cd2` 后重建并记录该提交。旧项目运行广域回归四项冻结默认值断言与当前 v3 不改写快照行为不一致，已修正测试为断言快照原样保存；关联 28＋16 项通过。运行期交互子流程、macOS Intel/Windows 与用户真实数据仍未核销。
- 后续真实 worker 用例发现自定义模块内调用子工作流时子节点只保留工作流作用域，外层模块丢失。`7a4a10a0` 在共享嵌套执行器的现有上下文边界传递模块、画布子流程和工作流作用域，共享递归栈与后台任务，不重建调度器。关联项目 29 项、Studio 嵌套/模块针对性 6 项及节点执行器 3 项通过。
- 针对 `7a4a10a0` 重建冻结后端及 macOS arm64 本地 unsigned 包，正式项目 UI 主链 `formal-project-control-electron-h1SA0V` 通过；组合作用域由真实项目 worker 集成用例验证，包内脚本覆盖两类入口的正常主链而未直接编排组合。哈希与边界见原项目跨工作流证据 README。动态运行期生成的子流程引用、交互命令、Intel/Windows 仍待单列。
- `run_workflow_file` 的声明初值引用 `{child_ref}` 与直接 ID 在真实项目 worker 各通过一次；在运行过程中由前序节点才产生的引用仍未冻结，保持未验收，不把此两项覆盖扩大到完整动态分支。

## 项目任务纯文本节点族（2026-09-23）

- 现有八个 WebRPA 文本节点执行器已迁入 Studio，本轮只接入项目任务目录；不新建执行器或资源服务。八节点真实 worker 串联运行、输出及事件一致，浏览器资源请求为空；冻结差分 146 项、项目关联 47 项、Ruff/mypy 通过。证据见 `docs/migration/studio-backend-migration/evidence/project-integration/string-family-2026-09-23/README.md`。
- 项目任务目录为 65 个已接入入口，Studio 批准范围仍为 213 个；最新冻结包与正式 Electron 中八节点组合尚未验收。其他纯数据族按已有执行器与资源依赖继续逐族接入。

## 项目任务基础列表与字典节点族（2026-09-23）

- 在现有 `data_structure.py` 执行器之上，项目目录新增 `list_operation`、`list_get`、`list_length`、`dict_operation`、`dict_get`、`dict_keys` 六个批准入口；真实项目 worker 六节点串联输出和持久事件一致，没有浏览器资源请求，清理完成。项目目录为 71 个，Studio 批准范围仍为 213 个。
- 冻结 WebRPA 差分及项目关联共 194 项通过；两族真实 worker 连续三轮通过，Ruff、生产目录 mypy、OpenAPI 一致性通过。测试中两族一度在无节点事件时被人为的 10 秒 worker 启动预算打断；捕获到 `TimeoutError` 后改用生产默认的 90 秒预算，未更改成功、输出及清理断言。
- `list_export` 因项目产物登记尚未接通而继续禁用。六节点的项目正式 Electron UI 与最新冻结包未验收；证据及边界见 `docs/migration/studio-backend-migration/evidence/project-integration/container-family-2026-09-23/README.md`。

## 项目任务数学／统计节点族（2026-09-23，confirmed）

- 沿用用户确认的项目默认资源＋任务显式覆盖，无资源白名单。项目目录新增 31 个现有 Studio 数学／统计节点，项目真实 worker 31 节点串联输出及持久尝试通过；冻结差分与关联测试共 270 项通过。Studio 批准范围 213 不变，项目目录为 102。
- 正式 Electron 开发入口以真实 UI 保存三节点流程，关闭 Studio 后运行项目自动化，输出 6、6、7 且无浏览器残留。首次正式验收发现数学节点可见的默认输出名未写入工作流文档；在节点创建共用入口补齐 31 类默认值，专项 14 项、类型、lint、构建及正式链路复验通过。
- PyInstaller 冻结后端与 macOS arm64 本地未签名 Electron 目录包构建后，同一真实 UI 链路包内复验通过；哈希、开发及包内证据见 `docs/migration/studio-backend-migration/evidence/project-integration/math-family-2026-09-23/README.md`。Intel/Windows 和 `list_export` 项目产物链尚未核销。

## 项目任务实用数据工具节点族（2026-09-23，confirmed）

- 项目目录接入冻结 WebRPA 实用工具源码已批准的九个现有执行器，真实项目 worker 和原版差分／关联回归共 166 项通过；项目目录为 111 个，Studio 批准范围 213 不变。Ruff、mypy、OpenAPI 检查通过。
- 正式 Electron 开发入口及 macOS arm64 本地未签名包以真实 UI 保存并运行 URL 编码→MD5→SHA，输出、节点记录与清理正确；共享验收脚本下拉选择操作调整后，数学链路在同一新包复验通过。完整证据及包哈希见 `docs/migration/studio-backend-migration/evidence/project-integration/utility-family-2026-09-23/README.md`。
- `list_export` 项目任务仍受文本产物发布与 SQLite ACK 不确定性安全边界阻塞；该问题源于 `ProjectScreenshotWriter.write_text` 尚未接通，不能用截图删除规则处理已发布的用户输出文件。其余工具族、Intel/Windows 和正式用户数据未据此验收。

## 项目任务基础网页节点族（2026-09-23，confirmed）

- 冻结 WebRPA `basic.py` 已迁入 Studio 的 11 类网页节点复用项目图执行器及 CloakBrowser 会话；项目目录从 111 增至 122，Studio 批准范围 213 不变。项目默认 Profile＋任务显式覆盖规则已由用户确认，无资源白名单。
- 真实项目批次两项任务逐项执行十五节点链，核验导航历史、悬停、弹窗、脚本变量、iframe、输出与 worker 清理。关联回归 274 项、真实批次 5 项、敏感输出专项 2 项，Ruff/mypy/OpenAPI/构建通过。
- 正式 macOS arm64 开发入口及本地 unsigned 包经真实 UI 编排、保存关窗、项目自动化运行、CloakBrowser 启动与清理通过。包内哈希、证据和未核销边界见 `docs/migration/studio-backend-migration/evidence/project-integration/web-basic-family-2026-09-23/README.md`。其他项目节点族、Intel/Windows 和用户数据库未因此关闭。

## 项目任务页面加载节点族（2026-09-23，confirmed）

- 继续复用已迁入的 WebRPA `basic.py` 两种页面加载节点；项目目录由 122 增至 124。项目事件适配按原字段 `saveToVariable` 输出真实布尔值，缺省 `page_loaded`；未产生变量时不构造节点输出。
- 真实项目批次两项任务均执行打开网页、等待加载、状态探测，`page_ready=true`，输出与进程清理通过；关联回归 202 项、真实 CloakBrowser 项目批次 2 项、专项 2 项、Ruff/mypy/OpenAPI 通过。正式 macOS arm64 开发入口真实 UI 闭环通过，临时工作区且无用户数据库改动。详情见 `docs/migration/studio-backend-migration/evidence/project-integration/page-load-family-2026-09-23/README.md`。
- 冻结后端和本地 unsigned Electron 包重建并通过相同正式 UI 链路；上一网页基础族在同一包的回归也通过。包哈希、两份项目任务结果及未实测平台见页面加载节点族证据 README。现有高级网页节点的下载、图片产物需要共享项目产物写入边界，未因此开放。

## 项目任务高级网页节点族（2026-09-23，confirmed）

- 冻结 WebRPA `advanced_browser.py` 的 11 个批准执行器一次接入项目目录，124→135；Studio 有效范围仍为 213。仅扩展共享项目产物适配，截图、下载文件和保存图片均经原子写入、持久事件确认、受控路径及哈希读取；旧截图保持兼容。
- 两条真实 CloakBrowser 项目任务各执行 13 节点链，项目默认 Profile、下载、图片、变量、尝试与清理通过；关联后端 209 项、项目真实批次 7 项、前端项目运行 156 项通过。Ruff、mypy、TypeScript、ESLint、OpenAPI、构建通过。
- 正式 Electron 开发入口和 macOS arm64 本地 unsigned 包均经真实 UI 保存关窗、项目任务运行、产物读取和图片预览；证据及包哈希见 `docs/migration/studio-backend-migration/evidence/project-integration/advanced-browser-family-2026-09-23/README.md`。Intel/Windows、用户数据库与余下项目节点族不据此关闭。

## 项目任务标签页切换（2026-09-23，confirmed）

- 用户再次确认项目默认资源可被任务显式覆盖，无白名单；沿用已实现的 Profile/模型选择边界。项目目录新增冻结源码 `switch_tab`，135→136，Studio 范围 213 不变。项目事件适配分别登记索引、标题和 URL，敏感 URL 不进入公开输出。
- 真实 CloakBrowser 项目批次八个场景、冻结源码差分和适配专项通过；正式 Electron 开发入口及 macOS arm64 本地 unsigned 包经真实 UI 编排、保存、正常关窗、项目运行、任务结果及浏览器清理验收。证据和哈希见 `docs/migration/studio-backend-migration/evidence/project-integration/tab-switch-2026-09-23/README.md`。
- 网络采集受项目事件消息容量限制，仍需大结果合同；`list_export` 的文本产物安全发布亦未解决。Intel/Windows 与用户数据库未验收。

## 项目任务 JSON／随机数／时间变量族（2026-09-24，confirmed）

- 依赖已就绪的三个冻结源码执行器接入项目目录，136→139；项目输出读取实际变量值。JSON解析节点同时存在旧默认`resultVariable`与用户设置`variableName`时，项目登记以原执行器写入的后者为准。真实项目 worker 与关联差分 84 项通过，Ruff/mypy/OpenAPI通过。
- 正式 Electron 开发入口与 macOS arm64 本地 unsigned 包经真实 UI 声明初值、配置、保存、正常关窗和项目任务启动；三项输出准确，未启动 CloakBrowser。先前测试脚本的 Tab 自动补全导致变量名被旧建议覆盖，改为 Escape 关闭建议再离开输入框，未改产品控件。证据及包哈希见 `docs/migration/studio-backend-migration/evidence/project-integration/variable-family-2026-09-24/README.md`。
- Base64文件分支仍受项目产物端口约束，打印日志成功级别尚未纳入项目日志合同，网络采集还需大结果合同；这些未被本族核销。Intel/Windows及用户数据库仍未实测。

## 项目任务列表导出（2026-09-24，confirmed）

- `list_export` 使用已迁入的冻结 WebRPA 执行器，项目目录 139→140。共享 `WorkflowArtifactStore` 在发布目标文件前执行可选 64 MiB 上限；项目 worker 以既有事件 ACK 登记覆盖、追加及空文件的不可变快照，下载类型收敛为安全附件 MIME。节点成功在产物事件确认之后提交。
- 独立临时工作区的真实项目 worker 三次导出与可读取产物、共享文件边界、项目 ACK 等 76 项通过；Ruff、mypy、OpenAPI 和脚本语法检查通过。正式 Electron 开发入口与 macOS arm64 本地未签名包均通过真实 UI 编排、保存、正常关窗、项目任务、内容哈希和任务页下载入口验收。完整证据见 `docs/migration/studio-backend-migration/evidence/project-integration/list-export-2026-09-24/README.md`。
- 二进制文件读写、`export_log` 的项目日志记录消费、网络大结果等仍按各自依赖处理；Intel/Windows 与用户数据库未实测。本族未改变 Studio 213 节点批准范围。

## 项目任务日志节点族（2026-09-24，confirmed）

- `print_log`、`export_log` 复用冻结源码执行器，项目目录 140→142；项目运行上下文记录节点日志，产物沿用已确认的安全文件写入与 ACK。用户主动打印错误级日志不把成功任务改判失败；日志证据增加 `isUserLog`，任务页按中文级别展示并保留用户原文。
- 临时工作区真实 worker、项目日志筛选/事件补读、JSON 导出和不可变文件检查通过；正式 Electron 开发入口及 macOS arm64 本地未签名包均通过真实 UI 编排、保存、正常关窗、项目任务、级别筛选、TXT 产物内容与 SHA-256 核对。证据和包哈希见 `docs/migration/studio-backend-migration/evidence/project-integration/log-family-2026-09-24/README.md`。
- 开发入口首次验收读取旧 renderer 构建而失败，重建后同一脚本通过，失败现场保留。Intel/Windows、用户数据库和项目目录余下 71 个批准节点未据此验收。

## 项目任务表格节点族（2026-09-24，confirmed）

- `extract_table_data` 和七个数据表节点复用已迁入的冻结 WebRPA 执行器，项目目录 142→150；项目文件端口支持受限 XLSX 二进制读写并等待产物持久回执。项目输出边界对这些节点按执行器实际写入的 `variableName` 登记，避免旧默认 `resultVariable` 遮蔽用户值。
- 冻结源码差分 79 项、项目与共享产物关联回归 120 项、真实 CloakBrowser 双任务提取、Ruff/mypy/OpenAPI/目录检查通过。正式 Electron 开发入口和 macOS arm64 未签名包真实 UI 完成十节点链，三份 XLSX/CSV 文件、SHA-256、任务下载入口及浏览器清理通过；详见 `docs/migration/studio-backend-migration/evidence/project-integration/table-family-2026-09-24/README.md`。
- Studio 有效范围仍为 213，项目目录余下 63 个节点待接入。macOS Intel、Windows、用户数据库未实测；本轮只使用临时工作区。

## 项目任务出站 HTTP 节点族（2026-09-24，confirmed）

- 冻结源码 `external_http.py` 中依赖现有出站服务的 `api_trigger`、`api_request`、`webhook_request`、`notify_webhook` 进入项目目录 150→154。项目输出按执行器实际变量值登记，Webhook 多项响应变量逐项写入，避免节点结果包装对象或旧默认名称取代用户变量。
- 独立临时工作区真实 worker、本地受控 HTTP 服务、取消和原版差分关联 66 项通过；Ruff/mypy/OpenAPI/目录检查通过。正式 Electron 开发入口和 macOS arm64 未签名包真实 UI 完成四节点顺序链；请求轨迹、输出、节点状态及无浏览器资源结果见 `docs/migration/studio-backend-migration/evidence/project-integration/http-family-2026-09-24/README.md`。
- `webhook_trigger` 的被动触发依赖项目交互命令通道，未被出站服务证明；Studio 有效范围 213 不变，项目目录余下 59 个批准节点。Intel/Windows及用户数据库未实测。

## 项目任务等待、断言与停止节点族（2026-09-24，confirmed）

- 已迁入的冻结 WebRPA `wait`、`assert_checkpoint`、`stop_workflow` 执行器接入项目目录 154→157。项目输出边界读取断言写入的布尔变量，停止节点后的步骤不会执行。
- 项目真实 worker、两任务 CloakBrowser 元素等待与断言、原版差分及关联回归通过；正式 Electron 开发入口和 macOS arm64 本地未签名包经真实 UI 配置、保存、正常关窗、项目运行及任务结果验收。证据和包哈希见 `docs/migration/studio-backend-migration/evidence/project-integration/control-primitives-2026-09-24/README.md`。
- Studio 有效范围 213 不变，项目目录余下 56 个节点。项目网络采集尚需核实大输出事件合同；Intel/Windows 与用户数据库未实测。

## 项目任务网页网络采集节点族（2026-09-24，confirmed）

- 冻结 WebRPA 的 `network_capture`、`network_monitor_start`、`network_monitor_wait`、`network_monitor_stop` 通过现有 CloakBrowser 监听器接入项目任务目录 157→161；项目输出读取执行器实际变量，worker 输入维持 1 MiB、输出事件上限 16 MiB。大输出回执、网络差分及项目关联回归通过。
- 正式 Electron 开发入口与 macOS arm64 未签名包均以真实 UI 保存六节点网络流程，项目任务在临时工作区捕获两次受控请求并展示三个脱敏输出，浏览器完成清理。证据和包哈希见 `docs/migration/studio-backend-migration/evidence/project-integration/network-family-2026-09-24/README.md`。Studio 的 213 节点范围未变，项目任务目录余下 52 个。
- 网络抓包面板移除 Web 范围外的系统／代理模式；旧文档显示明确修正提示。等待请求超时按执行器实际秒单位呈现。扩大字段台账时发现 14 个已排除通知节点历史用例在加载阶段崩溃，现以单独测试提交 `0103fdfc` 显式核对排除范围；完整字段台账另有 28 个 AI 面板清单差异，未据此宣称全量通过。Intel/Windows、用户数据库及真实公网服务未实测。

## 项目任务 Allure 报告节点族（2026-09-24，confirmed）

- 冻结 WebRPA 的六个 Allure 节点与单文件 HTML 生成器接入项目目录 161→167。项目运行器为报告节点分配现有文件写入器；共享文件边界准入 HTML，保留路径防逃逸、64 MiB 上限和持久回执。项目真实 worker、报告内容、产物回执与路径失败专项通过。
- 正式 Electron 开发入口与 macOS arm64 本地未签名包均由真实 UI 编排六节点、保存、正常关窗后运行项目任务；产物 HTML 包含套件、用例、步骤和附件，任务页下载与 SHA-256 核对通过。证据和包哈希见 `docs/migration/studio-backend-migration/evidence/project-integration/allure-family-2026-09-24/README.md`。Studio 批准范围仍为 213，项目目录余下 46 个入口；Intel/Windows、用户数据库未实测。

## 项目任务 SSH 节点族（2026-09-24，confirmed）

- 延续用户确认的项目默认资源＋显式覆盖。五个既有 SSH 执行器进入项目目录 167→172；项目文档允许精确托管凭据引用，仍拒绝密码原文。复用现有文件端口、Paramiko 服务和运行清理，没有第二套 SSH 实现。
- 真实项目 worker 成功、空文件、非零退出和停止；SSH/SFTP、产物及文档关联 60 项通过。正式 Electron 开发入口和 macOS arm64 本地包真实 UI 主链通过，活动 SSH 连接归零，命令进程退出，下载内容及 SHA-256 一致。证据：`docs/migration/studio-backend-migration/evidence/project-integration/ssh-family-2026-09-24/README.md`。
- 测试服务修复已接受通道被回收导致的偶发断开；正式包凭据使用唯一测试名，保存原固定名失败证据。没有改系统凭据实现，没有用 Mock 替代。项目目录仍有 41 个入口待核销，Intel/Windows、用户数据库及外部主机未实测。

## 项目任务定时与概率节点族（2026-09-24，confirmed）

- 既有 `timing_probability.py` 两节点进入项目目录 172→174；没有重写时钟、随机或图执行器。真实 worker 验证两个分支、日期/延迟、错误和停止；原版差分与 SSH 关联共 19 项通过。
- 正式 Electron 开发入口和 macOS arm64 本地包真实 UI 编排分支、保存、正常关闭后运行项目任务均通过；未选分支无日志和尝试记录。证据：`docs/migration/studio-backend-migration/evidence/project-integration/timing-family-2026-09-24/README.md`。
- E2E 首轮画布落点被遮挡，快速点击缩放尝试又出现收藏选择器，保留两个失败现场。后者根因未确定，排队核实，未宣称修复；正常可见区域编排闭环已通过。未改用户数据库、未恢复通知节点；项目目录余下 39 个入口。下一块 Base64 全模式所需文件端口已由 SSH 批次提供。
