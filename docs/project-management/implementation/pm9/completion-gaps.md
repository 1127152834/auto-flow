# PM9 剩余工作复核

日期：2026-09-21；状态：confirmed（本轮能力与证据核对），PM9 仍 in_progress。当前生产源码候选 82c067c9；置信度：高（已运行断言），完整发行验收仍未满足。

**本轮已接通 S1 子流程、S2 声明人工输入/目标、S3 结构化并行和 S5 两个独立 Run；S4 接通 Windows 安全新文件发布及有证明的 Job 清理。** 最终独立审查的 4 项 Important 已修复，26 个真实项目 worker 场景复跑通过；完整后端 3297 和前端 5459 通过的版本边界见报告。后续补证又修复 Windows Job 成员退出和 Sheets 字段/原版本快照，原生 92 项与 Sheets 相关 46 项定向通过，fed0b4c1 完整三平台验证运行中。最新结果见 [本轮报告](runtime-capabilities-follow-through.json) / [verification.json](verification.json)。这些数字不代表整项规格或实机安装包已经验收。

当前可执行缺口：Windows 已有文件覆盖/追加/安全读取仍拒绝；251 条中 32 条尚未定位直接断言（219 条具备已明确范围的断言），其余也须逐项闭合生产/UI 子条件。外部条件：当前打包 Sheets/OAuth 授权、签名公证身份及三平台完整实机/原生专项。历史 PM6 Sheets 实网与凭据证据、ARM 安装和 Excel 原生子条件继续有效。releaseAccepted=false，草稿 PR 不合并、不发布。

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
