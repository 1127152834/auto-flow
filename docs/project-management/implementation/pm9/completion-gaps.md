# PM9 剩余工作复核

2026-09-23 FLOW-A06 原生回归缺陷（confirmed 局部）：旧 defa1955 三平台矩阵的 macOS ARM `data-response-loss` 27 项真实 worker 通过、1 项失败；本机复现同一终态实例清理卡住。原因是 Chromium 所属 PID 已退出而遗留 `SingletonSocket` 目标仍存在；macOS 环境适配器现只在本机锁 PID 已确认退出且锁未变化时忽略遗留标记，其他情况保持保守拒绝。本机同场景 RED→GREEN、环境单元15项、相关所有权/恢复46项通过；最终源码全量和新三平台待验证。旧矩阵不能计三平台通过，详见 [专项报告](response-loss-lock-follow-through.json)，`releaseAccepted=false`。

2026-09-23 DATA-WRITE-13 最新子范围（confirmed）：修复循环索引嵌套引用把 `RecordRef` 对象转成字符串的共用变量解析缺陷。源码真实 HTTP/SQLite/worker/CloakBrowser + 受控 Sheets transport 6 项通过：第二表前两行更新及两条 pending 出站意图在第三行字段校验失败后保留；lease 释放、End 未执行。变量差异测试20项通过。台账 248/251 有范围断言、3 未定位，204 partial/47 planned/0 verified。打包 UI、真实 Google 送达核验、跨平台该组合仍待验收；完整回归和新候选 CI 进行中，`releaseAccepted=false`。详见 [专项报告](sheets-loop-partial-follow-through.json)。下文旧计数均为历史候选。

2026-09-23 本机回归收口（confirmed）：生命周期源码94f8e0a8完整后端3472 passed/74 skipped/2 warnings，796.74秒；之后defa1955二进制读取补丁单独16项+真实worker1项、Ruff/mypy407/构建/原15秒sidecar通过，未宣称同一最终本机全量快照。最终三平台35816693045进行中。已完成源生产恢复/删除/服务重启补证及运行目录清理修复；Windows真实PNG409的读取修复待原生确认。旧14df矩阵35811305102两种Mac成功、Windows失败；所有旧状态以此按hash区分。releaseAccepted=false。

2026-09-23 最新候选 defa1955（局部 confirmed，完整验收 pending）：已修复项目删除遗漏 Run 目录；源生产联合链归档→服务重建→恢复不重放→清理残留→服务重建自动续跑1项通过。随后从历史Windows真实PNG GET409定位并修复O_BINARY缺失，二进制契约/证据16项、Mac真实worker1项通过。三平台35816693045进行中；35815127474/35816258910因新缺陷修复取代而取消，不计通过。下文旧候选/计数/状态仅为历史；248/251有范围断言，203partial/48planned/0verified，releaseAccepted=false。

2026-09-23 Windows 截图后续：旧14df候选原生真实截图内容GET409，公共读取缺少O_BINARY；已修复并强化二进制fixture，本机16项与真实worker1项通过，Windows修复后复验待完成。详见 windows-artifact-binary-read.json；未开放S4既有文件能力，不提升覆盖状态。

2026-09-23 生命周期重启补证（confirmed 局部）：真实 worker 联合归档→重建服务→恢复→删除残留→再次重启沿原命令清理已通过（最终仅等待后台自动推进，1 passed/15.15秒）；修复删除遗漏项目运行目录，相关21项、Ruff/mypy407、OpenAPI、构建与原15秒sidecar通过；独立审查无P1/P2。Google/凭据与权限失败仍为受控 fixture，运行目录内文件为已知 fixture。完整回归进行中，旧矩阵35815127474不含本次补丁。PM-04/PM-05/XE-G06补断言但不升 verified；Workspace/G01–G05及外部验收保留。详见 lifecycle-restart-follow-through.json。下列旧轮次结论只对应其历史候选。

2026-09-23 XE-A17 最终本机核对（confirmed）：源码f6a5023e、测试快照9a5a80aa；完整回归3471 passed/74 skipped/1旧准入顺序断言失败（857.72秒），修正后所在文件16 passed（4.33秒）。不称为一次全绿。新三平台35815127474进行中；旧断言矩阵35814591659已取消。真实联合最终1 passed，Sheets worker五项及相关79项通过；Ruff/mypy407/OpenAPI/构建/原15秒sidecar通过。XE-G06仅补归档blocker子范围，248/251有范围断言、3未定位、203partial/48planned/0verified；其余生命周期和外部验收继续保留，releaseAccepted=false。

2026-09-23 XE-A17 收尾补证（confirmed，本段取代此前当前统计）：本机真实 HTTP/SQLite/两 worker/浏览器联合归档通过，已受理保存仅一次，未知写核验前不完成，pending 不重发；同文件 5 passed（60.11秒）。修复归档/核验门禁、任务更新缺同步意图、End 阻塞与取消清理竞态、终态实例残留；新完整回归/三平台仍在推进。台账为 248 有范围断言/3 未定位、203 partial/48 planned/0 verified；没有升级 verified。计划及详细边界见 archive-settlement-follow-through.json，releaseAccepted=false。此前候选与结果均为历史范围。

2026-09-23 本轮回归收尾（confirmed）：生产候选14dfae7c；本机后端完整3465 passed/73 skipped/2 warnings（966.88秒），前端5471通过，类型/lint/OpenAPI/Ruff/mypy407/前后端构建通过。产物sidecar首次15秒就绪超时；诊断3545ms且健康200，原15秒复测通过，但首发原因未明，不能声称修复。单次新三平台35811305102仍运行，旧c9矩阵因新增checkpoint修复取消。后续aef0f412仅测试/记录，与候选生产源码一致但其新增断言不在该矩阵。releaseAccepted=false。

2026-09-23 XE-G02 子范围复核（confirmed）：本机真实 success/manual-stop 两场景 2 passed/32 deselected（25.21 秒），分别证明有限两次参数运行/日志输出/同键重放/资源回收，以及实际人工等待后的取消和清理；独立通用核心场景证明准备内容不被后续文档编辑替换。强停、归属不明的退出核验与安装包/三平台整组门禁仍未闭合。当前 246 有范围断言/5 未定位、203 partial/48 planned/0 verified，不按数量判断完成率。

2026-09-23 XE-A19 共享核心补证（confirmed）：复用现有真实浏览器持久运行场景，SQL 核验零 Project/仅一 Run；仅 browser 能力准备项目 createRecord 文档被明确拒绝，原文档不变且随后可编辑保存，不隐式建项目。1 passed/3 deselected（11.65 秒）。仅 core/document/worker 子范围由 planned 改 partial；Studio 窗口提示/编辑体验、HTTP 联合和打包验收未完成，新断言不在已启动的14df矩阵中。最新 245 有范围断言/6 未定位、203 partial/48 planned/0 verified；先前计数为历史。

2026-09-23 XE-C07 最新补证（supersedes 此前 243/8 统计）：真实 TCP/worker 人工等待场景发现 checkpoint 未纳入公开事件投影，导致 JSON/SSE 补读 409；已补最小身份/版本契约及生成类型，内部续跑内容不公开。修复后真实断开/继续/缺口补读、8 次唯一节点访问、3 个输出、日志分页、失败截图摘要和资源回收通过；20 项后端契约/证据与25项相关前端通过，独立审查无 P1/P2。前端 EOF 去重是独立受控测试，尚非安装包 UI 断网联合证据。台账 244 有范围断言/7 未定位、202 partial/49 planned/0 verified；完整回归/新候选 CI 见 verification.json 与 event-reconnect-follow-through.json。releaseAccepted=false。

最新状态（2026-09-23）：C1–C4、R1–R5、D1 已实现。D1 新真实 worker 场景发现并修复声明坏值仍领取的问题，准备与提交重验共享字段校验，未使用坏字段不阻断；本机专属场景和原共享交接共 4 项通过，新生产候选完整回归/三平台见 verification.json。DATA-TABLE-08 拒绝证据已强化，DATA-WRITE-12 已补直接单记录反向冲突；当前 243 条有范围断言、8 未定位、202 partial/49 planned/0 verified。S4 既有文件、未批准 M1–M3、其他未闭合子条件与外部验收仍保留。下文旧计数与“D1 worker 未命中”由本节 supersede；专属 worker 不再归入外部环境缺口。

2026-09-21 共享数据续作：两份方案已获批准，按 C1–C4→R1→R2→R5→R3→R4 实施。C1–C3 已接通公共身份、全部占用入口、独立本地游标、生命周期和旧锁阻断；29 项真实 worker 与最新独立状态 3 项、前端 5460 项通过。C4 后端全量发现 4 个历史迁移 head 断言过期，修正验证及新三平台继续。当前 227 条有范围断言 / 24 未定位，192 partial / 59 planned / 0 verified。R1 表结构查询和 R2 本地字段删除已接通并通过本机实际 worker；R5→R3→R4 继续实施；Windows 既有文件安全操作和外部验收仍未闭合。详见 shared-data-follow-through.json。下文 f580 及更早现状保留为对应候选历史，不代表当前 C1–C3 实现仍缺失。

日期：2026-09-21；状态：confirmed（本轮能力与证据核对），PM9 仍 in_progress。当前生产源码候选 f580b1c6；置信度：高（已运行断言），完整发行验收仍未满足。

**本轮已接通 S1 子流程、S2 声明人工输入/目标、S3 结构化并行和 S5 两个独立 Run；S4 接通 Windows 安全新文件发布及有证明的 Job 清理。** 已修复最终审查的 4 项 Important、Windows Job 成员退出、Sheets 字段/原版本快照，以及最新写成功后核验读取失败。最新定向 Sheets 50 项加一个分块场景通过；f580b1c6 本机完整后端 3329 passed / 60 skipped，三平台仍运行中。旧源码 82c067c9 的 ARM CI 全链通过只留历史，不能覆盖新增生产修复。最新结果见 [本轮报告](runtime-capabilities-follow-through.json) / [verification.json](verification.json)。所有数字均只证明报告列出的范围。

当前可执行缺口还包括已复现的 Sheets 跨项目物理行共享领取缺失（见 shared-sheets-claims-gap.json），不能再仅列缺测试。Windows 已有文件覆盖/追加/安全读取仍拒绝；251 条中 29 条尚未定位直接断言（222 条具备已明确范围的断言），其余也须逐项闭合生产/UI 子条件。外部条件：当前打包 Sheets/OAuth 授权、签名公证身份及三平台完整实机/原生专项。历史 PM6 Sheets 实网与凭据证据、ARM 安装和 Excel 原生子条件继续有效。releaseAccepted=false，草稿 PR 不合并、不发布。

下列初次复核、旧候选和阶段段落保留时间顺序，关于“未获批”“单槽”“S1–S5 未实现”的旧结论已由本轮与文末各片记录取代，不是当前阻塞。

## 1. 初次复核时的能力缺口（历史；当前进度以本页开头和文末切片为准）

| 优先顺序 | 尚缺能力与规格 | 当前实现证据 | 完成条件 |
| --- | --- | --- | --- |
| 1 | 项目子流程，含固定子流程内容、参数/输出、父任务撤权传播；FLOW-08、FLOW-A11、XE-C02/XE-A20 | [项目节点目录](../../../../apps/backend/src/autoflow/domain/workflows/catalog.py) 仅 14 种节点，没有子流程；[准备校验](../../../../apps/backend/src/autoflow/domain/workflows/run_validation.py) 拒绝目录外节点 | 复用共享执行器接通项目端口；验证编辑后仍执行冻结内容、变量隔离、父任务取消后禁止子流程写入。不能只扩白名单。 |
| 2 | 人工处理的合法继续位置和具名输入；XE-C12、XE-A15、XE-G05 | [manual_runtime.py](../../../../apps/backend/src/autoflow/application/project_runs/manual_runtime.py) 的 command 明确拒绝 targetNodeId 和非空 inputs | 声明输入契约、枚举并校验可达位置/调用栈/循环上下文/变量前置，前后端接通并验证竞争。当前从原节点继续已通过。 |
| 3 | 含循环或人工节点的并行图 | [run_validation.py](../../../../apps/backend/src/autoflow/domain/workflows/run_validation.py) 的 _validate_lifecycle_graph 明确拒绝并行根/同路由扇出；R4 Ruling 已记录共享状态限制 | 共享 Runtime 隔离分支控制状态后再开放；核对分支变量、循环与副作用次数、唯一 End 汇合。不能删除准入检查冒充实现。 |
| 4 | Windows 任意路径工作流文件输出，以及缺少原生所有权证据的孤儿进程清理 | [workflow_artifacts.py](../../../../apps/backend/src/autoflow/infrastructure/filesystem/workflow_artifacts.py) 的 _open_output_parent 等分支返回 ARTIFACT_PLATFORM_UNSUPPORTED / 501；[原生进程边界](../../../../apps/backend/src/autoflow/infrastructure/process/browser_processes.py) 保守保留未知归属 | 实现原生安全路径/句柄和所有权验证后，在 Windows CI 验证取消、原子提交、重启与危险路径拒绝。项目 XLSX 导出和受控运行产物已支持，不能混为一项。 |

这几项包含共享运行时或原生安全边界改动；具体设计、契约与实施切片已在 [新增能力方案](../../../superpowers/specs/2026-09-21-pm9-runtime-capability-completion.md) 补齐，新增架构确认前不开放能力。既有安全拒绝保持有效。跨进程人工恢复是当前明确不支持的范围，不因本表而擅自扩大成新的必做功能；原同 Run/存活现场继续与重启中断规则已有证据。

规格依据：[数据流与契约 FLOW-08](../../design/data-flow-and-contracts.md)、[执行与环境 §6、XE-C12/XE-A15](../../design/execution-and-environment.md)、[PM9 总计划](../../../superpowers/plans/2026-09-13-project-management-milestones.md)。当前 14 种项目节点也不等于全部 Studio 节点均可用于项目；其他节点应按已确认业务场景逐个接入，不以目录数量确定完成范围。

## 2. 覆盖台账与真实场景仍未闭合

后续复核：251 条已补 `testMapping`，200 条有实际断言引用，51 条明确未定位直接场景测试；73 条失效预定路径全部补了映射或缺口。原 22 条 verified 发现未闭合子条件，已逐项退回 partial，并保留 statusBeforeReview。补入本轮真实场景后，当前合计为 0 verified / 188 partially_verified / 63 planned（206 条有断言，45 条仍未定位直接场景）。详情见 [test-mapping-review.md](test-mapping-review.md)。以下表格是复核前快照，已被本段当前统计取代。

此前 d59607f3 验收已把 DATA-LINK-05、FLOW-A16、XE-C12、XE-C18、XE-G04、XE-G05 六项直接匹配的三平台成功链补入台账，状态从 planned 改为 partially_verified；没有将一部分断言升级为整项 verified。

| 类别 | 总数 | verified | partially_verified | planned |
| --- | ---: | ---: | ---: | ---: |
| 功能 | 48 | 4 | 44 | 0 |
| DATA/FLOW/XE 场景 | 178 | 17 | 91 | 70 |
| 执行契约与门禁 | 25 | 1 | 18 | 6 |
| 合计 | 251 | 22 | 153 | 76 |

以上是**旧证据台账快照，不是功能完成百分比**。旧快照 229 项未闭合；本轮逐项复核后全部 251 项仍各有未闭合子条件，不等于 251 项没写代码。特别是多数历史阶段使用隔离执行器，只有直接覆盖的场景才能换成生产证据。

73 条登记指向 5 个不存在的预定文件：test_project_excel.py、test_project_environment_retention.py、test_project_claims.py、test_project_full_scenarios.py、test_project_manual_actions.py。已有测试分散在 Excel services/exports、environment persist/restore/real browser、project input groups/data scheduler、project batch real browser 等文件；必须逐条核对断言，不能仅凭近似文件名自动改为通过。

应优先补的真实场景：

1. DATA-E2E-01/03/06：多输入与显式状态连续任务；人工版本冲突；运行中新增字段、第二表记录和并发旧结构任务。
2. FLOW-A03/04/06/07/13：任务自身版本推进、人工新值保护、写成功响应丢失、后续节点失败仍保留已写效果、同记录释放后可再次领取。
3. XE-A10/12/14/23/24/25：旧环境候选发布冲突、saved_unlinked 仅修复关联、人工继续/到期竞争、混合初始输入与新建记录的 End 关联、禁止替换其他身份、新增字段后关联新记录。
4. DATA-E2E-04/05 与 DATA-SH/SYNC/LIFE：跨项目远端字段写入、发送未知/重启核验、重新授权/绑定和归档时未决操作。

其中 DATA-E2E-06 并发部分已确认是**实现缺失**（见下），其余条目按 coverage 中分类核对生产端到端证据，没有断言相关单元/集成测试不存在。完整逐项列表见 [coverage-audit.json](coverage-audit.json)，原文与已有报告见 [coverage.json](../coverage.json)。本轮 73 条路径映射已完成；剩余完整业务组合、UI 与外部专项按实际缺口继续补证。

## 3. 外部与发行证据

- **Sheets 不是从未实网验证。** [PM6 报告](../pm6/verification.json) 已记录 2026-09-19 服务账号、真实 Google REST、真实系统凭据库、拉取/推送确认和解绑删除；已检查对应 live-result.json 的 passed 结果。缺少本次 PM9 代码与打包应用的完整项目→运行→Sheets 推送核验，以及 OAuth 桌面客户端路径。历史验收使用的原生配置文件选择框被测试入口替代，不能证明原生面板。该次结束已删除本机凭据，当前资源授权是否可复用尚未确认；本轮未读取或复用秘密、未触碰远端表。
- **三平台实机安装与原生专项。** CI 已构建 EXE/Intel DMG/ARM DMG 并运行包内应用，但安装向导、系统阻拦提示、原生文件选择/保存、凭据创建/读取/删除和卸载残留没有三平台完整手工证据。按用户要求明确保留待验收。
- **签名/公证。** 当前构建不等于带签名发行。需对应签名身份和公证条件，以及正式产物核验；现有证据不支持宣称完成。
- **用户验收与合并。** PM9 PR #1 仍为草稿，当前工作位于 codex/project-management-pm9-runtime；尚未将 PM9 改动合回 baseline。此前要求的“先合并历史有效代码，再从 baseline 创建 PM9 分支”已完成。这是最终交付收口，不是测试缺陷。

## 4. 性能数据不另造阻塞

历史 d59607f3 中，Windows 五路万条准备 725733 ms，真实 worker 537 日志/分钟；两个 Mac 对应 104904/85377 ms 和 1642/1539 日志/分钟。各平台固定每分钟 1000 条**合成输入**均读回通过。PM9 原始规格要求的是这一合成负载，并未给 worker 吞吐或万条创建耗时 SLO，因此 Windows 性能是已量化的优化项，不能虚构成“未达到原规定千条 worker 吞吐”的失败。

后续工作已开始修改生产代码：人工到期与已接受继续命令的竞争已复现并修复，扩展真实场景见 follow-through 计划。d59607f3 报告仅保留为历史基线，新候选需要重新验证。完成证据闭合与实际功能缺口前，releaseAccepted 继续为 false。

## 5. 本轮新增完成项

- 251 条规格已逐条给出实际断言范围或明确缺口；引用校验通过。
- 人工继续/到期两种交错均有真实 worker 失败复现，修复采用同一状态版本 CAS，本机当前共 18 个真实浏览器场景通过，包含实际 HTTP 在途继续与 TTL 先胜竞争；最后占用修正另复测旧候选真实链。
- 生产环境操作造成通用操作列表 500 已修复；列表、ID、项目原键返回既有环境 DTO，生成客户端同步，workspace 作用域不扩大。
- 生产 HTTP 双输入、任务连续写、人工新值保护、失败保留提交、混合关联、禁止替换、关联修复和基础旧代次拒绝均通过。关联提交边界另有实际 worker linkRevision 竞争及全组回滚断言。
- 本轮具体运行与故障注入边界见 [follow-through.json](follow-through.json)。候选 52936b6a 的 ARM 全量/源码/打包 CI 已通过；Windows 全量/源码/打包 CI 亦已通过；Intel 前端首次元素等待失败，保留记录，原 SHA 仅 Intel 重跑已接受（attempt 2），不沿用旧报告。

XE-A10 已增加真实 worker 关闭/候选暂存后在发布边界注入 ENOSPC、T2 发布 g2、旧 T1 冲突与另存；修复 retained_unsaved 的状态、现场额度和原子重获占用。发布结果不明仍保留占用，原生 UI/物理磁盘故障仍未证明。

XE-A23 的消耗邮箱筛选与共享人员/新账号后继已在下述新本机链完成；当前仍缺 DATA-E2E-06 的并发旧契约。运行中兼容字段/新建记录/修改/状态的串行真实链已补，但并发缺少生产多 Run 能力。上述基础机制有测试不代表这些整组已验收；UI 反馈亦逐项保留 gap。四项新增架构已出具体方案，等待确认。

候选校正（confirmed）：f25b3867 的三平台 CI 均在类型检查失败，未运行生产链。此前 typecheck passed 记录有误，cleanupResidue 未接纳环境操作 DTO；已修复并通过新本机类型检查，后续候选重新验证。

本机安装包补证（confirmed）：已下载 52936b6a 的 ARM DMG，完成镜像校验、只读挂载、隔离复制、真实应用启动、认证 sidecar 健康和父进程退出清理；镜像已卸载。见 [install-follow-through-darwin-arm64.json](install-follow-through-darwin-arm64.json)。随后通过真实 macOS open-panel/save-panel 完成 Excel 导入与导出，读回保留文本 001/中文，源工作簿 hash 不变；未使用 QA 面板替代。这只关闭 ARM 安装包挂载/复制/启动及该 Excel 原生路径子条件，不证明 Gatekeeper、其他原生专项、凭据、签名或完整卸载验收。

新增并发边界（confirmed）：52936b6a ARM 包的第二参数批次 blocked、Task queued，旧人工任务占据唯一执行槽。串行加列/新建/修改/状态成功见 [补测报告](business-combinations-darwin-arm64.json)，不能作为并发旧契约成功。FLOW-A02 与 DATA-E2E-06 新增 implementation_missing；多 Run owner/资源集合租约与单 Run 分支隔离是不同工作，详见 [独立补充方案与切片](../../../superpowers/specs/2026-09-21-pm9-multi-run-capacity.md)，尚未获批。

当前 Windows 候选实测（52936b6a）：五路万条写入 1007788 ms、2 次明确 busy 重试；合成 60 秒发出/读回 1000 条，最大批次延迟 188 ms。原始指标见 ci-follow-through-win32-x64.json；不据这些数据虚构 worker 吞吐 SLO。

最新候选更新（confirmed）：XE-A23 完整补测发现 inputEnvironment 在开始批次时错误要求无关默认 Profile，且 atTaskStart 未由调度器消费。已修复为领取事务重验输入后冻结所选环境 Profile；无关默认配置不参与检查，解析失败无 Task/lease。54 定向及独立复审通过，新 frozen backend 的完整人员/邮箱/账号恢复链通过，包括人员原本已有关联且未被替换；详见 input-environment-follow-through.json。该生产修改需要新三平台矩阵，52936b6a 的 Intel 重跑已因候选变更取消，旧 Windows/ARM 成功只留历史。当前 188 partial/63 planned/0 verified，新候选结果以 verification.json 为准。

交付候选：4f392ed595fc42ca6310aad47106003283c615fd 已推送，新的三平台 Actions 为 [35566462369](https://github.com/1127152834/auto-flow/actions/runs/35566462369)。下文/历史段落中的 52936b6a 结果不覆盖新增修复。


## S1 冻结项目子流程（2026-09-21）

本轮“继续实现”已批准 S1–S5，见 `.ai/decisions/2026-09-21-pm9-runtime-capabilities-approved.md`。此前“新增架构待批准”为历史状态，不再阻塞实施。

S1 接通既有 canvas gateway 与共享 WorkflowRuntime：prepare 校验依赖/调用环/32 层深度/节点归属；显式 JSON 输入与声明输出隔离；调用路径绑定独立 visit；父端核对冻结定义、父调用存活及原 Task 权限；子 End 和未隔离的并行控制仍拒绝。源 HTTP/真实 worker/browser 验证 prepare 后修改源子图不改变两 Task 结果、同一子图双调用独立写入，根 End 关联。父 Run 取消测试核对迟到写拒绝且首次写入保留。

S2–S5 继续实施；当前源链不代表三平台打包和实机验收完成。覆盖状态未批量升级，releaseAccepted=false。


## S2 声明人工输入与合法继续位置（2026-09-21）

已接通 frozen inputSchema/resumeTargets、严格字段/类型/枚举、当前调用前置变量、同一 scope 直接后继和原检查点/Run/实例所有权 CAS。worker 只注入声明变量，scheduler 只执行选择分支。人工详情支持字段表单和无候选的原位置继续；环境入口统一进入同一详情。响应丢失保留原键和草稿，先查原 operation，不创建新命令。

实际 Electron 表单暴露并修复 SQLite 人工日期缺时区：数据库公共映射现在将 UTC 日期带时区输出，详情/列表一致，东八区不再误判到期。122 后端、12 UI、100 脚本检查；两个三场景真实 worker 测试组和完整源码桌面运行链通过。证据见 manual-follow-through.json、manual-desktop-darwin-arm64.json。当前源码证据不代表新候选三平台或实机放行；S3 分支隔离/人工排队、S4 Windows、S5 多 Run 仍未完成。


## S3 结构化并行控制（2026-09-21）

共享 Runtime 已隔离分支变量、循环帧、调度状态和调用路径；只合并声明输出。prepare 保留未声明并行控制的拒绝，对明确 fork/join 验证分支归属、出口与汇合独占。父端验证每个并行 scope 的冻结分支和活跃 fork visit。已修复两项真实缺陷：直接取消 scheduler 时节点操作未回收；外层循环内 join 被父调度器延迟到最后一轮。

人工资格在 worker 内排队，等待在途节点操作结束后才发送创建检查点请求；继续先交接下一项，finish/stop 取消队列。真实 worker 的两个不同次数循环生成 10 条记录、仅两次根 End 关联各自最后输出；失败分支保留先前 2 条已写记录；并行人工继续/终结/停止分别核对节点次数、串行建项、TTL 与无后台浏览器读取。单元另覆盖嵌套外层循环、局部 break、分支子调用、异步清理和原变量保留。见 parallel-follow-through.json。

当前剩余实施为已获批的 S4 Windows 原生输出/同句柄进程终止、S5 多 Run。S1–S3 新候选仍需完整回归和三平台打包验证；历史 4f392ed5 的 Windows/ARM 成功、Intel 最后浏览器管理 smoke 的状态刷新时序失败不覆盖这些新代码。releaseAccepted=false；覆盖状态未升级。


## S5 独立多 Run（2026-09-21）

S4 原生文件实验等待期间继续独立的 S5。dispatcher/worker 按 Run 和拥有的执行代次隔离 task、预算、资源租约、控制锁与清理事实。项目装配开放 2 槽；单参数批次仍顺序生成，多数据任务沿用原领取事务和额度。资源集合内部共享原 OS 保护锁，末个确认清理的租约才释放；原生释放失败保留 workspace 保护与失败事实。历史非终态恢复未确认时不能因内存 owner 为空而开放准入。

125 定向、实际双子进程 ACK/取消隔离、跨进程 OS 锁排除，以及当前源码构建的生产 HTTP/真实浏览器组合通过。T2 人工等待期间 T1 加列/新建/写内容/状态完成，T2 原契约继续；取消另一个实际 Run 不打断 T2。同数据批次两任务同时等待，领取记录不同、相同来源 Profile 的 cookie 和同名变量隔离；先结束一项另一项继续，maxTasks=2 不多领第三项。见 multi-run-follow-through.json 和 multi-run-business-darwin-arm64.json。此段取代此前 capacity=1 的当前结论，旧包观察仍保留为历史证据。

当前覆盖 207 有断言 / 44 未定位；188 partial / 63 planned / 0 verified。S4 覆盖/追加安全路径及 Windows 孤儿恢复尚未完成，三平台当前候选验证、签名、专项授权和实机条件仍保留。releaseAccepted=false。


## S4 Windows 子集与整体边界（2026-09-21）

原生实验在持有拒绝删除/写入共享的目标句柄时，FileRenameInfoEx flags 1/3 都未能替换；原文件保持不变。没有松开句柄绕过该约束，也没有引入已被 Microsoft 劝退的新 TxF 依赖。既有文件覆盖/追加/读取仍 501，完整 S4 未完成；下一实施切片必须先证明条件身份与原子发布同时成立。

已完成子集沿用快照/摘要/登记：逐层持有 Windows 目录句柄、拒绝 junction/重解析点和保留名，暂存文件写完 fsync 后按同一文件句柄发布到不存在的路径。目标冲突不覆盖；取消/登记失败按自己的句柄删除。真实 --workflow-worker Base64 写入与 artifact 快照哈希一致，未扩展项目 Studio 节点白名单。

进程复用现有 kill-on-close Job，保存 Run/generation/random name/pid/birth，监督者持有已核验 Job 直到全部成员退出。Windows venv launcher 与实际解释器是两个进程：只有直接拥有它的监督者能在核验 birth 后把 launcher 纳入同一 Job，恢复路径不能增添成员。缺证明/错 birth/外部 Job/权限拒绝保留 blocker。原生 CI 35577767754 的实际进程、父退出、恢复和文件 worker 通过；后续 junction 与保留名加固在最终矩阵复验。安装包实机、权限受限用户环境与未知孤儿仍按各自条件保留。


## 最终审查修复与当前验收边界（2026-09-21）

人工嵌套配置采用与执行一致的有效配置；敏感标记跨取消 Task、子流程输入输出和并行输出保留，合成凭据不出现在事件中；子节点表权限与任务授权取交集，拒绝借用其他节点的表/字段/操作；Windows 在启动命令前创建并持久化 Job 所有权，ready 前取消也等待整树确认，身份未知继续占用容量。均有先失败后通过的直接测试。一次最终审查后仅此修复轮，没有反复派发审查。

原生复验 35580013772：87 passed、27 skipped、1 个模拟夹具失败；真实 ready 前取消/超时与后代退出均通过。失败原因是虚拟 Job 句柄的顺序测试不应启动真实 Job bootstrap，已修正夹具；最终三平台会验证该修正。不能把这次整轮 CI 写成通过。

完整 S4 的已存在文件覆盖/追加/读取仍未实现；已验证的新文件发布和有证明 Job 恢复不填补这一缺口。最新 37 条无直接断言是测试台账缺口，不全等于实现缺失；其余项目仍按每条生产、UI、实机条件验收。旧 PM6 实网和历史安装证据不删除，当前专项需要自己的版本与授权证据。


## 剩余台账的进一步分类（2026-09-21）

定位到已有组件与真实并发断言后，当前 209 条含具体断言、42 条未定位；188 partial / 63 planned / 0 verified 不变。DATA-STATE-02 已映射空目录创建入口及 null/失效状态显示；DATA-SCHEMA-09 已映射 T1 兼容加列时 T2 旧契约保持可运行，异型冲突、新字段写回、删除依赖仍不能据此推定。

确认的实现缺口还包括工作流表/字段结构查询与 deleteField 端口、Sheets 系统 UUID 初始化和受控远端建列。前两项不能用现有管理端能力代替，后两项不能用历史服务账号实网读写代替。具体后续验收切片见 [剩余断言实施计划](remaining-assertion-plan.md)；这次 S1–S5 候选不冒称已经交付这些额外端口。

### 2026-09-21 原生退出与 Sheets 数据一致性补齐

当前映射为 214 有断言 / 37 未定位；状态仍 188 partial / 63 planned / 0 verified。补齐可审查的 [剩余断言计划](remaining-assertion-plan.md)，新增能力端口与已有能力缺证分开。

Windows Job active=0 仍有子进程句柄未退出的真实反例已修复：共享清理在终止前取得成员句柄并等待退出。0cee27ca 原生 Actions 35583149567 成功，92 passed / 27 skipped。S4 既有文件安全覆盖/追加/读取仍未完成。

双项目 Sheets 不同字段相互覆盖、未知原操作错误核验新值、发送中编辑被旧响应确认，三个反例 RED→GREEN。复用现有 request JSON 冻结字段和值、未发送合并推进版本、事务 CAS 登记发送；旧无快照意图拒绝猜测。相关 46 passed；受控传输不称为 Google 实网。该修复影响各平台，旧 18435502 矩阵被后续候选替代，新候选需完整三平台回归。

本机新 ARM 能力包完整性、隔离安装启动/退出、真实原生打开选择/取消和保存取消通过（见 install-capabilities-darwin-arm64.json）；包早于本次 Sheets 修复，不能当作其打包验证。完整退出条件未满足，releaseAccepted=false。

最终本机回归：fed0b4c1 完整后端 3311 passed / 60 skipped / 2 warnings，587.44 秒。其后空格响应提取和放弃 CAS 两个有界修复在 60 项相关回归、ruff/mypy 中通过；82c067c9 新完整三平台矩阵承接最终源码验证。当前 216 有断言 / 35 未定位，状态不升级。新增数据能力的具体契约/切片已写入待确认附录 docs/superpowers/specs/2026-09-21-pm9-remaining-data-capabilities.md。


2026-09-21 追加既有能力补证（confirmed）：DATA-SH-10 的普通/公式列 tombstone 防复活及 DATA-STATE-12 的 null/非空状态 × confirmed/failed/unknown 共 8 场景通过；相关 Sheets 同步/恢复/规则共 45 passed。生产源码无变化，台账 218 有断言 / 33 未定位；状态仍 188 partial / 63 planned / 0 verified。

2026-09-21 Excel 追加补证（confirmed）：DATA-XLS-03 已增加真实同内容工作簿两行系统身份/独立状态/本地 CRUD 后源字节不变断言；导入和占用保护 18 passed。当前 219 有断言 / 32 未定位，未提升整体验收状态。

2026-09-21 共享 Sheets 领取复核（confirmed）：两个项目实际绑定和拉取同物理行后，select_required 生成不同 local leaseKey，公共键应相等的探针失败。已将 DATA-ID-06/SH-13/SH-14 改列 implementation_missing；待确认补充方案明确共享身份、全调用点、旧占用升级及验证切片。该失败不是通过的覆盖，既有出站字段隔离通过证据不受影响。

2026-09-21 当前 ARM CI 完整通过（confirmed）：d21197ad 的后端 3313 passed / 60 skipped，前端 5459 passed，选定真实 worker 15 passed，源码/打包/安装产物全链成功。五路万条写入 48091 ms；合成 60 秒发出/读回 1000，最大批次延迟 168 ms。报告 ci-capabilities-darwin-arm64.json；该 CI DMG 本身尚未实机安装，独立本机构建原生检查另有报告。DATA-ID-03 扩展 6 个原行前插行场景通过；当前台账 220 有断言 / 31 未定位。

2026-09-21 Intel d21197ad 失败保留（confirmed）：3312 passed / 60 skipped / 1 failed，失败为 SSE 关停测试准备阶段 GET /openapi.json 的 5 秒 ReadTimeout，尚未进入关停计时。仅为 schema 准备设独立 30 秒界限，实际 3/8 秒退出和 worker/SSE 断言未变；定向 shutdown/node writes 8 passed。DATA-STATE-10 同时补入创建后状态命令权限失败、原 null 记录保留的服务集成断言，真实节点链仍待验收。台账当前 221/30。

2026-09-21 核验读取失败根因修复（confirmed）：实际写入已成功后，第二记录的核验 GET 超时抛出未处理 SheetsApiError，导致命令悬空。已统一转换读取异常、逐意图记录 unknown 并继续其他结果；reconcile 读取失败明确完成该只读命令为失败，原未知写不改，后续新核验不重发写入；pull/push 接受后取凭据失败亦完成原命令。相关 50 passed / 2 warnings in 40.66s，另一个分块场景通过，mypy 402 与完整无缓存 ruff 通过。该变更是新生产候选：此前 ARM d21197ad 完整成功保留历史，未结束 Windows 25c9a41b 和 Intel 7dab6b13 已取消，稳定后重跑三平台。当前台账222/29，releaseAccepted=false。

2026-09-21 源码分类校正（confirmed）：DATA-SH-03 的云端新增、DATA-SH-10 删除同步、DATA-SH-11 新行公式模板复制缺实际路径，已追加 implementation_missing。tombstone 不复活与公式刷新测试继续有效，但只证明各自范围。独立 M1–M3 方案为 proposed，未包含在此前 C1–C4/R1–R5 问题中，不因网络授权可用就自动视为已实现。计数222/29不变。

2026-09-21 f580b1c6 本机验证（confirmed）：完整后端3329 passed、60 skipped、2 warnings in611.65s。当前生产源码重新构建ARM DMG，hash a0ff707abb65cdff7eb5eb9b2f537b899bc0d4c71ce2209235c0b37dfdf48a47；镜像校验/只读挂载/隔离安装复制/卸载镜像、包内sidecar健康与父退出、真实原生打开取消/选择生成工作簿/保存取消通过。应用及临时数据已清理，报告install-read-fix-darwin-arm64.json；完整原生导入导出/凭据/签名/卸载仍未据此通过。


### 2026-09-21 R5 来源观察（confirmed，局部证据）

普通远端值通过现有 SyncRecordMarkRow.inboundObservation 保存最近每字段观察；与 identity/outbound 证据合并。当前 generation/epoch、字段/映射与记录存在性约束后，只读 HTTP/详情显示来源值、观察时本地值和修订。普通值、状态/关联、内容修订和待发送意图不改；公式保留既有刷新。重复身份不更新观察。无采纳/回滚/云写入口。

59 项后端、18 项组件/客户端检查通过；ruff/mypy(404)、typecheck/lint/OpenAPI/build 通过。DATA-SH-06 移除对应 implementation_missing，仍 partially_verified；251 条、227 有定位断言、24 无定位断言、192 partially_verified/59 planned/0 verified 均不变。早期 PM6 记录对“远端差异可查看”的范围已明确纠正，不否定其既有服务账号实网及系统凭据证据。

C4 35597323657 @21f8bb1e：ARM 已通过；Windows 全量后端 3338 passed/74 skipped、前端 5460 passed/406 files，但真实 worker 13 failed/5 passed/11 deselected，进程失联原因待诊断；Intel 当时仍在运行。以上 C 候选不含 R1/R2/R5；不得算当前候选三平台通过。R3/R4 仍按批准顺序待实施，releaseAccepted=false。

### 2026-09-22 R3 与 C4 更新（confirmed，局部验收）

R3 已冻结原操作 UUID、身份列归属及行证据，单次 Sheets batchUpdate 新列/值/metadata。未知响应仅核验；仅证明未发送的原计划允许重试，UUID 不重生成。原操作发布绑定与成功状态同事务；资料修订变化须重新预览影响后明确核验。复用本工作区已验证系统列不云写；同名未知归属拒绝。UUID 拉取/推值接通，文本视图和 UUID 本地键解析同一公共 lease。未决结构发送阻断其他绑定推值、领取和改绑；值发送未知先阻断结构发送。共享 GoogleAccess 使用标准库 RLock 序列化读计划到发送，并以现有 SQLite 账本保留跨请求/重启的未决围栏。没有第二执行器。

90 项后端相关检查、25 项组件/客户端通过，ruff/mypy（406）、typecheck/lint/OpenAPI/build 通过。覆盖账本 251 条中 228 有定位断言、23 未定位，193 partially_verified / 58 planned / 0 verified。DATA-ID-05 只升级 partial；真实 Google 和当前打包完整应用链仍待验收。

C4 Mac @21f8bb1e 的 ARM/Intel 全部通过；Windows @07619b6d 完整流水线 35605861737 通过：3384 后端（77 平台 skip）、5464 前端（407 文件）、21 真实 worker、源码/包链/安装包和万行写入。万行发生 8 次明确 busy 重试，不构造新的性能门槛。两份源码范围分别保留，R3 不包含在这些 CI 中。此前 C4 “Intel pending/Windows failed”当前状态由本节 supersede；失败日志仍保留历史。R4 接续，完整当前候选矩阵与一次整批复审在 R4 后执行。releaseAccepted=false。

### 2026-09-22 R4 受控增列（confirmed，局部验收）

显式选择普通本地字段、列名并确认远端写入后，原操作冻结目标/epoch/field/revision/owner，在网格末尾单次追加列、表头和归属 metadata。未知响应只核验原列；同名外部列、移动/改名/缺 metadata/非空列不猜测接管。仅确认未发送可原计划重试或取消，取消保留本地字段和值。确认事务兼容扩展 mapping、保持 generation/epoch/记录版本，并将已有新字段值放入现有队列，值发送依赖原列成功。既有冻结 Task 可以继续旧字段修改，不能因此扩大新字段权限；后续同步重验已创建列归属。

HTTP/SQLite/受控 transport 相关回归 113 passed（138.65 秒），组件/客户端 38 passed（5 文件），ruff/mypy（407）、typecheck/lint/OpenAPI/build 通过。另发现通用放弃接口跨项目及结构命令越界，两项 HTTP 反例复现，修复范围限定共享入口的项目归属与内容意图类型。覆盖账本仅 DATA-SCHEMA-07 新增具体断言并改 partial：251 条中 229 有定位断言、22 未定位，194 partially_verified / 57 planned / 0 verified。现有历史统计按日期保留。

R1/R2/R5/R3/R4 与 C1–C4 已有实现和分范围证据；最终整批独立审查、当前完整回归和三平台矩阵接续。真实 Google、当前打包完整 Sheets 链、OAuth、物理安装和签名仍未验收；S4 已存在文件安全覆盖/追加/读取与未批准 M1–M3 仍为实际缺口。releaseAccepted=false。

### 2026-09-22 整批审查修复与映射复核（confirmed，回归进行中）

一次独立审查发现 3 项 Important：UUID 公共 lease 查询未归一类型、未知值核验缺来源归属检查、推送明确发现坏身份后未失效旧领取证据。均已用直接 HTTP/SQLite 反例复现，按共享入口修复；推送与核验复用完整身份观察，可靠身份的普通推值失败不受牵连。新组合断言明确失败意图和本地新值保留、后续拉取正常、真实 Task 领取冻结本地值并继续公共排他。新增 R4 测试也直接证明加列后旧 Patch 推回原 B 列与旧 Task 权限兼容。

DATA-CLAIM-09、DATA-SCHEMA-08 仅新增上述范围映射，未证明的来源读取失败/界面提示、删除本地字段不删远端和生产端到端条件仍保留。当前 251 条中 231 有定位断言、20 未定位，196 partially_verified / 55 planned / 0 verified。完整前端 5469 passed / 409 文件 / 198.85 秒，前端源码之后未改；最终后端和三平台仍在验证。详见 shared-data-final-review.json。releaseAccepted=false。

### 2026-09-22 原生 CI 期间继续补证（confirmed）

新增两项直接业务场景，生产源码未变：DATA-LIFE-09 在真实 HTTP 归档收尾后保留未发送本地值及原意图，新推送 409、远端无写；DATA-SCHEMA-08 先由未决意图阻断本地字段删除，明确放弃后删除本地字段而同名远端列/值保持，状态与关联修订不变。两个相关完整文件 21 passed（17.71 秒），全目录 Ruff 通过。这两项为当前 Mac 本地追加证据，不混入 d75297fb 冻结 CI 的测试总数。

当前 251 条中 232 有定位断言、19 未定位；197 partially_verified / 54 planned / 0 verified。LIFE-09 的活动 worker/保存/未知写联合链、完整打包和实网条件仍保留，releaseAccepted=false。

2026-09-22 最新补证：已有坏业务值 fixture 的 HTTP 状态设置/占用 held 与 reconciling 拒绝/模拟释放后清空通过；17 项共享领取回归。D1 实现后，Sheets/XLSX 普通来源业务格式错误保留原值并派生诊断；身份与 unsafe wire scalar 严格拒绝；必填来源缺失保持缺失；Sheets 先全量预校验再物化，避免坏身份造成半批发布。真实 worker、打包完整链和实网授权仍未验收。当前机器统计 251/235 有断言/16 未定位，198 partial/53 planned/0 verified；前文 197/54、233/18 为阶段性手工统计，本节 supersede。未改变任何条目状态。当前补跑固定 0d7524d9，后补的状态场景单独保留本机范围。

### 2026-09-22 D1 review修复与三平台候选（confirmed）

D1 独立审查发现的三个重要问题已 RED→GREEN：Excel 身份字段业务格式错误不再降级为文本身份；Excel/Sheets 必填来源缺失不写入 values，由当前字段快照派生 REQUIRED_FIELD_MISSING；Sheets 先全量预校验身份和 unsafe wire scalar，再写入任何记录，晚到坏身份不会留下半批物化。D1 相关定向后端 138 passed、2 warnings；RecordFieldsView/RecordDetailPage 11 passed；Ruff 全目录、mypy 407、OpenAPI、typecheck 通过。UI 诊断为字段列表后的聚合面板，仍能区分格式问题与读取失败，记作 Minor 表达差异。

候选 ae347de9f5fc1922efa7c4af99c0e606e6bde26a 的 Actions 35677887974 在 Windows x64、macOS Intel、Apple Silicon 全部通过：各平台后端 3443/3453 passed（平台 skip 保留）、前端 5470 passed、21 个既有真实 worker 场景通过；同提交源码/打包链、五路万行写入和 1000 条/分钟合成日志报告已保存为 ci-d1-final-*.json。这证明 CI 平台链，不等于物理安装、签名、公证或真实 Google/OAuth 验收；native probe/worker probe job 被跳过。

当前台账为 251 条、236 条有明确范围断言、15 条未定位，198 partially_verified、53 planned、0 verified。D1 专门坏业务值 worker 筛选未命中，仍未宣称；S4 已存在文件覆盖/追加/读取、M1–M3、真实 Google/OAuth、完整打包 Sheets 链和三平台实机安装/签名仍是实际或外部条件缺口。releaseAccepted=false，草稿 PR 不合并、不发布。

2026-09-22 DATA-TABLE-08 补证：新增真实 SQLite/能力服务联合场景，证明固定系统状态元数据只读、业务 `status` 字段共存、伪造改型/删除/来源映射拒绝且无半写，业务状态写入仍成功。`test_project_table_schema_capability.py` 15 项通过。该项只补本机直接断言，不改变生产 worker、打包、实网或三平台原生验收边界。

2026-09-23 后续参数场景：parameter-isolation 在真实 HTTP/SQLite/worker/CloakBrowser 本机运行通过（1 passed/30 deselected，28.56s）。两个 Task 的 taskLocal 初值均为 0，前一任务写入不进入第二任务；结果可查询，无 DataLease；同名项目结果列的原记录及版本完全不变。FLOW-A01 增加范围断言，FLOW-A10 由 planned 升为 partial；当前 240 有断言/11 未定位、200 partial/51 planned/0 verified。此前一次退出 TimeoutError 已保留，根因未确认；本机最终通过不代替该场景的打包/三平台证据。

2026-09-23 FLOW-A05：同一自动化两个独立单任务批次的可选输入从有到无，真实 worker 验收 1 passed/31 deselected（37.63 秒）。第二次两次 inputs capability 输出与持久快照均空，零 lease，首次快照保持且资源回收；不是同批次、变量表达式或打包 UI 证据。独立复审无 P1/P2。最新 241 有断言/10 未定位、201 partial/50 planned/0 verified。

2026-09-23 XE-A01：parameter-single 真实 worker 场景 1 passed/32 deselected（38.06 秒）；无表、参数 first 网页填写/读取、同键重放后唯一 Batch/Task/Run、零 lease 和资源回收联合通过。仅本机源码证据，不扩大为打包 UI/三平台或 XE-G02 全部门禁。当前 242 有断言/9 未定位、201 partial/50 planned/0 verified。

2026-09-23 生命周期补审：LIFE-01/02 不能再仅写缺测试——连接无原位重授权/稳定主体契约，普通改绑无条件新建数据代次。LIFE-07 临时真实 HTTP 探针复现旧 unknown 仍在时重绑并再次云写；L0 在改绑新/旧目标及解绑复用持久值发送围栏，4 个直接反例 RED→GREEN。L0只拒绝绕过，不完成永久失权隔离；L1→L2→L3 具体规格/计划已保存，新增能力尚待批准。最新 243 有范围断言/8 未定位、202 partial/49 planned/0 verified。生产候选已改变，旧 c2 矩阵不能证明此修复，新完整矩阵见 verification.json。

2026-09-23 当前 ARM DMG 隔离安装补证（confirmed，本机限定）：生产源码 6d1f1d83 的 ARM DMG 校验、只读挂载、临时目录复制安装、包内 sidecar 和完整桌面运行通过。运行脚本修正终态 `cleaned`/`retained_unsaved` 处置：前者由调度器回收，后者才显式放弃。当前本机完整重跑包含真实浏览器 worker、人工输入、失败保留、归档/恢复、五路万行写入（53560 ms，0 次 busy 重试）、固定 60 秒合成日志 1000 条（最大批次滞后 40 ms）、21 页记录分页、200% 缩放及应用重启。此前一次合成写入期间分页等待超时根因未知，已保留失败并补诊断，不能称为长期稳定。详见 installed-arm-dmg-follow-through.json。旧矩阵 35819716149 ARM 在未修脚本的源码冒烟发多余 End，403 后失败；新脚本本机通过，旧 Windows/Intel 未完作业随后取消、不计通过。未证明 Finder/Gatekeeper、签名公证、其他平台实机、当前打包 Sheets 实网与 OAuth；`releaseAccepted=false`。

覆盖台账当前尚无直接断言定位的 3 项分别是 DATA-LIFE-01（L1 同主体重授权功能未获批实施）、DATA-SH-03（M1 云端并发新增行功能未获批实施）和 XE-G07（完整双窗口与三平台实机门禁）。本机 ARM 的缩放、第二窗口及隔离安装只是 XE-G07 子范围，仍缺原生窗口停靠、文件面板/凭据和其他平台实机证据；不能仅凭 smoke 文件名或安装包构建将整项改为 verified。

2026-09-23 当前三平台 CI 收口（confirmed，来源：Actions 35822065171 @1b2979ea）：Windows x64、macOS Intel、Apple Silicon 的 checks job 均 success；各自全量后端/前端、29 项真实 worker、源码及打包生产链、万行写入、固定千条合成日志与安装包构建均通过。Windows 后端 3462 passed/87 skipped、前端 5471 passed、五路万行 670182 ms/0 busy 重试；实际 worker 1004 日志/100723 ms，观察 598 条/分钟，不能用合成 1000 条/60 秒替代。两种 Mac 后端各 3474 passed/75 skipped、前端各 5471 passed；具体数据及原生 probe skipped 见 ci-final-follow-through.json。此为 CI 平台链而非三平台物理安装、原生面板/凭据、Google/OAuth、签名公证验收；S4、L1–L3、M1–M3 和 251 条完整条件仍未闭合，`releaseAccepted=false`，草稿 PR 不合并、不发布。

2026-09-23 S4 现有普通文件读取子片（confirmed，限定 2fe33528）：Windows 原生专项 [35829751668](https://github.com/1127152834/auto-flow/actions/runs/35829751668) 102 passed/28 skipped，含父目录 junction 拒绝、持有目标句柄时写/删被拒、父目录改名被拒及真实 worker 的 Base64 PNG 读取。公共读取仍检查大小、取消和读前/读后身份；后补的读取前取消断言尚待最终候选验证。详见 [证据](windows-existing-output-read.json)。既有文件覆盖/追加继续 501，S4 整体和 PM9 release 均未完成；三平台完整回归及打包链需针对最终候选复验。

同日最终候选前补审：读缺失路径原会沿写入入口创建父目录，新增直接测试先失败后通过；POSIX/Windows 读取均改为只打开现存父目录，缺失返回 `missing`。本机定向 34 passed/17 Windows-only skipped，Ruff/mypy（407）通过。Actions 35830250231/35830254336 因该已知副作用主动取消，均不计最终候选通过；下一矩阵必须覆盖这个补丁。

Actions 35830710429 @0bac3886 的 Windows 原生边界步骤 250 passed/28 skipped/1 failed：新读取、缺失路径、真实 worker 全部通过，唯一失败为旧表格 worker 用例仍断言 Windows 必须返回 501，实际新文件 Excel 已成功（result 0）。其他两个平台作业因该失败取消，不计通过。移除过时拒绝断言，并让新文件 CSV/XLSX 的三个差分用例在 Windows 真跑；本机相关 127 passed/17 Windows-only skipped，Ruff 通过。原生专项扩大覆盖后再运行完整矩阵。

第一次扩充原生专项 35831675395 @bde396de 的真实表格 worker 用例通过，但误把需 `reference/WebRPA` 的整个差分文件加入不含参考仓库的专项，32 项因缺来源依赖失败；另一项绝对盘符路径在应用层仍被明确拒绝。该专项不计通过，已缩到两个真正适用的相对新文件表格用例；绝对盘符路径继续跳过并登记为独立实现缺口，不通过扩大准入伪称接通。前段“**三个**差分用例在 Windows 真跑”由此更正为**两个**。

收窄后的 Windows 原生专项 [35832075007](https://github.com/1127152834/auto-flow/actions/runs/35832075007) @113668fd 成功：127 passed/28 skipped，现有二进制读取、缺失路径无目录副作用、真实 Base64 和表格 worker、两项相对路径新文件 CSV/XLSX 均通过。完整三平台矩阵仍须针对最终候选运行；绝对盘符表格输出与既有文件覆盖/追加不因本结果开放。

后续 S4 新文件绝对路径（confirmed，覆盖前段绝对路径缺口）：表格应用层仅在本机 `Path` 确认为绝对盘符路径时放行，UNC、盘符相对路径及 `..` 继续拒绝，最终仍交给原生 `output_target`/固定目录句柄校验。真实表格 worker 由绝对路径导出 XLSX，并核对登记快照；Windows 原生专项 [35832925704](https://github.com/1127152834/auto-flow/actions/runs/35832925704) @680fd0ca 131 passed/29 skipped。旧 35832710320 仅因测试按字符串比较等价斜杠而 1 failed，已改按 `Path` 比较，不作为通过。既有文件覆盖/追加仍 501；三平台完整回归与打包链仍待最终候选。
