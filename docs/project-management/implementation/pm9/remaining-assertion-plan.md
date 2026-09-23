# PM9 剩余断言与能力补齐计划

2026-09-23 本机回归收口（confirmed）：生命周期源码94f8e0a8完整后端3472 passed/74 skipped/2 warnings，796.74秒；之后defa1955二进制读取补丁单独16项+真实worker1项、Ruff/mypy407/构建/原15秒sidecar通过，未宣称同一最终本机全量快照。最终三平台35816693045进行中。已完成源生产恢复/删除/服务重启补证及运行目录清理修复；Windows真实PNG409的读取修复待原生确认。旧14df矩阵35811305102两种Mac成功、Windows失败；所有旧状态以此按hash区分。releaseAccepted=false。

2026-09-23 最新候选 defa1955（局部 confirmed，完整验收 pending）：已修复项目删除遗漏 Run 目录；源生产联合链归档→服务重建→恢复不重放→清理残留→服务重建自动续跑1项通过。随后从历史Windows真实PNG GET409定位并修复O_BINARY缺失，二进制契约/证据16项、Mac真实worker1项通过。三平台35816693045进行中；35815127474/35816258910因新缺陷修复取代而取消，不计通过。下文旧候选/计数/状态仅为历史；248/251有范围断言，203partial/48planned/0verified，releaseAccepted=false。

2026-09-23 Windows 截图后续：旧14df候选原生真实截图内容GET409，公共读取缺少O_BINARY；已修复并强化二进制fixture，本机16项与真实worker1项通过，Windows修复后复验待完成。详见 windows-artifact-binary-read.json；未开放S4既有文件能力，不提升覆盖状态。

2026-09-23 生命周期重启补证（confirmed 局部）：真实 worker 联合归档→重建服务→恢复→删除残留→再次重启沿原命令清理已通过（最终仅等待后台自动推进，1 passed/15.15秒）；修复删除遗漏项目运行目录，相关21项、Ruff/mypy407、OpenAPI、构建与原15秒sidecar通过；独立审查无P1/P2。Google/凭据与权限失败仍为受控 fixture，运行目录内文件为已知 fixture。完整回归进行中，旧矩阵35815127474不含本次补丁。PM-04/PM-05/XE-G06补断言但不升 verified；Workspace/G01–G05及外部验收保留。详见 lifecycle-restart-follow-through.json。下列旧轮次结论只对应其历史候选。

2026-09-23 XE-A17 最终本机核对（confirmed）：源码f6a5023e、测试快照9a5a80aa；完整回归3471 passed/74 skipped/1旧准入顺序断言失败（857.72秒），修正后所在文件16 passed（4.33秒）。不称为一次全绿。新三平台35815127474进行中；旧断言矩阵35814591659已取消。真实联合最终1 passed，Sheets worker五项及相关79项通过；Ruff/mypy407/OpenAPI/构建/原15秒sidecar通过。XE-G06仅补归档blocker子范围，248/251有范围断言、3未定位、203partial/48planned/0verified；其余生命周期和外部验收继续保留，releaseAccepted=false。

2026-09-23 XE-A17 收尾补证（confirmed，本段取代此前当前统计）：本机真实 HTTP/SQLite/两 worker/浏览器联合归档通过，已受理保存仅一次，未知写核验前不完成，pending 不重发；同文件 5 passed（60.11秒）。修复归档/核验门禁、任务更新缺同步意图、End 阻塞与取消清理竞态、终态实例残留；新完整回归/三平台仍在推进。台账为 248 有范围断言/3 未定位、203 partial/48 planned/0 verified；没有升级 verified。计划及详细边界见 archive-settlement-follow-through.json，releaseAccepted=false。此前候选与结果均为历史范围。

2026-09-23 XE-G02 子范围复核（confirmed）：本机真实 success/manual-stop 两场景 2 passed/32 deselected（25.21 秒），分别证明有限两次参数运行/日志输出/同键重放/资源回收，以及实际人工等待后的取消和清理；独立通用核心场景证明准备内容不被后续文档编辑替换。强停、归属不明的退出核验与安装包/三平台整组门禁仍未闭合。当前 246 有范围断言/5 未定位、203 partial/48 planned/0 verified，不按数量判断完成率。

2026-09-23 XE-A19 共享核心补证（confirmed）：复用现有真实浏览器持久运行场景，SQL 核验零 Project/仅一 Run；仅 browser 能力准备项目 createRecord 文档被明确拒绝，原文档不变且随后可编辑保存，不隐式建项目。1 passed/3 deselected（11.65 秒）。仅 core/document/worker 子范围由 planned 改 partial；Studio 窗口提示/编辑体验、HTTP 联合和打包验收未完成，新断言不在已启动的14df矩阵中。最新 245 有范围断言/6 未定位、203 partial/48 planned/0 verified；先前计数为历史。

2026-09-23 XE-C07 最新补证（supersedes 此前 243/8 统计）：真实 TCP/worker 人工等待场景发现 checkpoint 未纳入公开事件投影，导致 JSON/SSE 补读 409；已补最小身份/版本契约及生成类型，内部续跑内容不公开。修复后真实断开/继续/缺口补读、8 次唯一节点访问、3 个输出、日志分页、失败截图摘要和资源回收通过；20 项后端契约/证据与25项相关前端通过，独立审查无 P1/P2。前端 EOF 去重是独立受控测试，尚非安装包 UI 断网联合证据。台账 244 有范围断言/7 未定位、202 partial/49 planned/0 verified；完整回归/新候选 CI 见 verification.json 与 event-reconnect-follow-through.json。releaseAccepted=false。

日期：2026-09-21。状态：confirmed（现状和已有验证）；C1–C4 和 R1–R5 设计已批准；M1–M3 仍 proposed。来源：原始设计、coverage.json、本轮生产候选及本轮直接断言复核。

当前 251 条中 246 条有明确范围的断言，5 条尚无已定位断言；203 partially_verified / 48 planned / 0 verified。这个数量不衡量完成率，任一条的未闭合子条件继续保留。历史 73 条失效预定路径仍保留为原意，实际映射另列，未创建空测试文件冒充交付。

2026-09-23 执行更新：DATA-TABLE-08 已用充分字段权限和真实 Sheets 绑定请求替换宽泛拒绝证据；DATA-WRITE-12 已补双任务反向单记录冲突，保留多记录组和生产 worker 重试缺口。D1 真实 worker 场景暴露并修复声明坏值仍领取的缺陷：共享选择/提交重验只校验已选输入的声明字段，保留未使用坏值。专属 worker 及原共享交接 4 项通过，新场景加入既有 CI；完整回归/新三平台结果见 verification.json。后续继续 DATA-WRITE-13 真实循环部分成功、FLOW-A01/A05 参数与可选输入隔离；云端行变更 M1–M3 仍未批准。

## 本轮已经执行的补证

- 2026-09-23 DATA-WRITE-13：真实 worker 的 data-loop-partial 场景通过。第二张本地表循环前两行成功、第三行被字段规则拒绝；前两行/版本/成功操作仍保留，动态 lease 释放、无 End，后续任务取消。本地子范围由 planned 升为 partially_verified；Sheets 意图队列、UI 和跨平台未闭合，不改为 verified。

- DATA-STATE-02：两个已有组件用例分别验证空状态目录的新增入口和 null/失效状态的区分，完整前端 5459 项已覆盖。
- DATA-SCHEMA-09：已有真实并发业务脚本验证 T2 等待人工时 T1 完成兼容加列，T2 保留旧契约后继续写入；不包含新字段写回、异型冲突和删除依赖的所有条件。
- DATA-CLAIM-17：新增无输入、仅可选、有必要输入三个直接规则分支，错误明确归于 maxTasks。
- DATA-SH-06：新增 HTTP/SQLite 与受控网络传输测试，远端普通值变化后本地值、身份、内容/状态版本不变。
- DATA-SH-08：新增远端排序插行后的实际出站重新定位，A/B 分别写回正确行，新增 X 不变，两个原意图 confirmed。
- 后三组同既有相关回归共 34 passed；没有改生产实现，没有把受控网络称作 Google 实网。

- DATA-SH-01 / DATA-SYNC-07：补证复现整行推送覆盖和旧响应确认新版本。已修复为原字段快照、发送登记 CAS 与原快照核验；两项目、发送中编辑和未知后新编辑三个反例 RED→GREEN；相关回归 46 passed。

- DATA-SYNC-01 / DATA-SYNC-06：放弃与发送登记在两个确定性交错下竞争；晚放弃被事务 CAS 拒绝；放弃先胜后再拉取仍保留本地覆盖值。

- DATA-SH-10 / DATA-STATE-12：新增 tombstone 普通/公式列与显式 null/非空状态 × 同步确认/失败/未知 8 个 HTTP/SQLite 场景通过。无新生产源码，不计作实网。

- DATA-XLS-03：真实重复行 XLSX 的系统身份、独立状态和本地 CRUD 不改源字节新增用例通过；相关导入与占用保护 18 passed。

- DATA-ID-03：扩展状态用例，在原行前插入新远端行后直接核对业务状态跟随稳定身份，新行 null/revision 1；6 passed。

- DATA-STATE-10：扩展既有 capability 测试，创建成功后状态权限拒绝，原创建完整快照和 null 保留、原命令重放仍一致。此为直接服务集成，真实 worker 节点链仍待验收。

- DATA-SYNC-08：每次发送上限缩为 1，首块确认、次块失败与后来新版本推送的操作/数据保留直接断言通过；默认 200 行及后台实际唤醒仍未验收。

## 历史能力端口诊断（C1–C4 与 R1–R5 已由文末实施记录取代）

以下不是“已有实现只差测试”，也不能靠新增白名单解决：

1. DATA-SCHEMA-01：工作流查询表/字段结构。现有管理字段列表可复用；需要明确只读命令 DTO、table/dataset/field scope 和返回稳定 fieldId/类型/来源能力/结构修订。先写无授权/错误代次拒绝和读后仍不能写的测试，再接 capability/worker 节点和配置 UI；不赋予隐式写权限。
2. DATA-SCHEMA-06（含 09 的删除子条件）：工作流 deleteField。复用管理删除影响分析；必须设计 Task 结构权限、当前/其他活动依赖和未决同步检查，并在同事务提交前重验影响版本。行 lease 不替代结构独占。先验证身份/映射/其他任务依赖阻断，再测无依赖删除与旧引用失效。
3. DATA-ID-05：Sheets system UUID 初始化仍 501。需独立初始化命令与持久原命令身份，冻结将写入的 UUID/列归属；未知响应先核验原列和原 UUID，不重生成、不占用归属不明同名列。受控 transport 故障可先验证；实网要授权测试表。
4. DATA-SCHEMA-07（含 08 远端子条件）：受控远端增列未有冻结命令。复用本地字段和原同步账本，先规定结构操作与后续值意图的依赖顺序；未确认建列不得推值，失败保留本地字段/数据。对“原列存在但响应丢失”写唯一性验证，不能改为盲重试追加。
5. DATA-SH-06 的剩余子条件：当前 `_ingest` 对普通既有值直接返回 seen，没有记录供查看的远端差异。先设计来源观察记录的键、版本和只读展示契约；观察不推进本地 contentRevision/statusRevision，也不生成出站写。
6. DATA-ID-06 / DATA-SH-13 / DATA-SH-14：实际双绑定生成不同 local leaseKey，缺 Workspace 公共身份排他及异身份列准入门禁，已复现为实现缺失。失败探针与 C1–C4 补充设计见 shared-sheets-claims-gap.json；不计入通过断言。
7. S4 Windows 已存在输出：已测持有拒绝共享目标句柄的 rename 组合不满足安全替换。保持覆盖/追加/读取拒绝；新方案须先给出同一目标身份、原子提交、冲突和取消清理可同时成立的原生实验。不能以松开句柄或字符串路径重开作为实现。

1–5 涉及新增冻结能力/持久协议，不属于已批准 S1–S5 的自动扩展；进入实现前按 AGENTS.md 完成具体 OpenAPI/命令规格、事务约束和垂直切片并确认。已有实现的补测试和缺陷修复继续按当前授权推进。S4 的安全要求已批准，具体 API 组合仍须实验成立，不能降级验收。

新增分类核对：DATA-SH-03/10/11 的云端新增行、删除同步和模板复制是 implementation_missing，不是只有实网待验收；具体 M1–M3 契约/切片见 `docs/superpowers/specs/2026-09-21-pm9-sheets-row-mutations.md`。尚未实施，也不包含在 C/R 待确认问题内。

## 历史 29 条最小场景清单（当前已完成项由文末进展与 coverage.json supersede）

每项先读取原规格对应行与所列既有测试/fixture；复用 HTTP、SQLite 和现有 transport/worker。断言包含业务值、稳定身份、版本、lease/操作事实及负面副作用；文件名或测试总数不构成覆盖。纯本地规则先定向运行，真实端到端只用于对应已接通能力。

| ID | 必须增加的直接场景 | 优先复用入口 |
| --- | --- | --- |
| DATA-CLAIM-09 | 未找到把 Sheets 推送失败、本地身份可靠和领取准入一起断言的测试；需组合真实本地领取与受控网络故障 | tests/fixtures/sheets.py + test_project_sheets_sync.py / recovery.py |
| DATA-ID-05 | 系统 UUID 初始化响应丢失后核验同一批 UUID，且拒绝覆盖归属不明同名列 | tests/fixtures/sheets.py + test_project_sheets_sync.py / recovery.py |
| DATA-ID-06 | 跨项目同一物理 Sheet 行共享排他，而本地业务状态独立 | tests/fixtures/sheets.py + test_project_sheets_sync.py / recovery.py |
| DATA-LIFE-01 | 同账号重授权验证主体和目标、先核验未知操作再恢复 | test_project_lifecycle.py + test_project_sheets_recovery.py |
| DATA-LIFE-07 | 永久失权后隔离旧未知写，并确认旧发送进程停止后才允许目标新写 | test_project_lifecycle.py + test_project_sheets_recovery.py |
| DATA-LIFE-09 | 归档保留待推送本地数据且停止新网络写 | test_project_lifecycle.py + test_project_sheets_recovery.py |
| DATA-SCHEMA-01 | 节点返回当前稳定字段和结构修订，读取不增加写权限 | test_project_capability_fencing.py + test_project_data_catalog.py / node_writes.py |
| DATA-SCHEMA-06 | 工作流删字段不能绕过身份、关联、其他任务、未决同步依赖 | test_project_capability_fencing.py + test_project_data_catalog.py / node_writes.py |
| DATA-SCHEMA-07 | 远端新增列响应未知核验原列，字段数据保留且不重复加列 | tests/fixtures/sheets.py + test_project_sheets_sync.py / recovery.py |
| DATA-SCHEMA-08 | 兼容加列后旧 Patch 仍定位原字段，删本地字段不删远端列 | tests/fixtures/sheets.py + test_project_sheets_sync.py / recovery.py |
| DATA-SH-02 | 两项目重叠写的历史确认与最终值可解释 | tests/fixtures/sheets.py + test_project_sheets_sync.py / recovery.py |
| DATA-SH-03 | 同业务键并发新增云端只保留一行 | tests/fixtures/sheets.py + test_project_sheets_sync.py / recovery.py |
| DATA-SH-13 | P/Q 任务共享物理 lease，释放后按 Q 自己状态领取 | tests/fixtures/sheets.py + test_project_sheets_sync.py / recovery.py |
| DATA-SH-14 | 未证明共享身份对应时保存第二绑定但阻止相关领取 | tests/fixtures/sheets.py + test_project_sheets_sync.py / recovery.py |
| DATA-STATE-08 | 格式错误记录仍可人工设状态，占用或未知则明确阻断 | test_project_capability_fencing.py + test_project_data_catalog.py / node_writes.py |
| DATA-SYNC-09 | 推送失败仍能拉取且不阻断不相关本地运行 | tests/fixtures/sheets.py + test_project_sheets_sync.py / recovery.py |
| DATA-TABLE-08 | 系统状态不能被字段节点改型/删除/映射，业务 status 字段可共存 | test_project_capability_fencing.py + test_project_data_catalog.py / node_writes.py |
| DATA-WRITE-12 | 两个任务反向请求对方记录时不永久等待或半组写 | test_project_run_data_start.py + test_project_data_scheduler.py |
| DATA-WRITE-13 | 真实循环前两行成功第三行失败，前两行效果与队列保留 | test_project_capability_fencing.py + test_project_data_catalog.py / node_writes.py |
| FLOW-A01 | 两次真实参数任务的变量隔离 | test_project_batch_real_cloakbrowser.py + project-runtime-smoke.mjs |
| FLOW-A05 | 可选输入从有到无不读到上一任务记录 | test_project_run_data_start.py + test_project_data_scheduler.py |
| FLOW-A10 | 结果列存在但无项目写节点时表无变化 | test_project_batch_real_cloakbrowser.py + project-runtime-smoke.mjs |
| XE-A01 | 参数网页真实读取、无 lease、资源回收的同一场景联合断言 | test_project_batch_real_cloakbrowser.py + project-runtime-smoke.mjs |
| XE-A17 | 活动 Run/已接受保存/未知 Sheets 推送同时归档的收尾 | test_project_lifecycle.py + test_project_sheets_recovery.py |
| XE-A19 | 无 Project 的 Studio 通用运行与项目写回文档明确缺能力 | test_project_batch_real_cloakbrowser.py + project-runtime-smoke.mjs |
| XE-C07 | 断线后快照/序号/attempt/产物恢复无重跑无重复追加 | test_project_batch_real_cloakbrowser.py + project-runtime-smoke.mjs |
| XE-G02 | 固定参数真实运行的幂等、取消、退出核验整组门禁 | test_project_batch_real_cloakbrowser.py + project-runtime-smoke.mjs |
| XE-G06 | 真实同步/保存/清理 blocker 与归档恢复删除/Workspace 切换闭环 | test_project_lifecycle.py + test_project_sheets_recovery.py |
| XE-G07 | 尚未将完整 Studio 窗口/平台门禁各子条件映射到单独断言；不能用项目 smoke 一个总通过替代 | electron-cdp.mjs + 当前安装包真实窗口/原生 UI |

## 验证与交付顺序

1. 每个已有能力场景单独完成断言与定向运行；失败先定位根因，禁止把失败改为 skip。新断言只升级其实际证明的 testMapping 子范围，未闭合整项状态不升级。
2. 生产 HTTP/真实 worker 用 `AUTOFLOW_TEST_CLOAKBROWSER=... uv run --directory apps/backend pytest tests/integration/test_project_batch_real_cloakbrowser.py -k <场景>`；离线 Sheets 使用现有 FakeSheetsTransport，报告明确这一边界。
3. 候选生产代码稳定后完整本机回归与默认三平台 CI；仅测试预期或证据工具修正可按源码哈希等价保留已有平台结果，平台受影响时用现有 workflow 的 pm9Platform 选择器重跑该平台完整链。不把跳过的平台视作通过。
4. 当前 PM9 打包 ProjectRun→Sheets 完整链及 OAuth 需要当前授权账号/桌面客户端/可写测试表；签名公证需要相应身份；Windows/Intel 实机与原生交互需要实际环境。历史 PM6 服务账号实网和历史 ARM 安装/Excel 子条件独立保留。
5. 同步 coverage、verification、completion-gaps 和 .ai；现有草稿 PR 提交推送，不合并发布。完整退出条件前 releaseAccepted=false。

## 2026-09-21 共享领取更新

第 6 项原共享领取实现缺失已由 C1–C3 修复和通过断言 supersede。DATA-ID-06、DATA-SH-13、DATA-SH-14 分别补公共键/独立游标、真实 worker 三类交接及身份列冲突拒绝；只升为 partially_verified。后端 20 项共享集成和 UI 22 项、真实 worker 最新状态分支 3 项通过；C4 全量/新三平台继续。Google 实网与具体身份列错误在真实页面展示仍保留待验收。R1→R2→R5→R3→R4 已获批准，不能再写成等待架构决定。

## R1 更新（2026-09-21）

第 1 项工作流表结构查询实现缺失已 superseded：queryTableSchema 在 domain/service/repository/RPC/prepare/节点配置接通，显式 fieldIds 与冻结 scope，当前结构只读投影，原系统状态只读。14 项专属拒绝/无副作用/来源元数据断言、子流程交集、真实 worker data-schema 通过。226 有断言/25 未定位；状态仍 191 partial/60 planned/0 verified。新候选三平台和完整 UI 原生链不由现有 C 矩阵替代。

## R2 更新（2026-09-21）

第 2 项工作流删字段实现缺失已 superseded。复用完整草稿增加单个显式 removedFieldIds、同事务依赖重验；Task 自身纯删除声明可排除，自身其他读写节点和第二 Task 不排除。身份、来源映射、自动化输入引用及未决同步分别保护。成功/冲突两条真实 worker、180 后端定向、18 UI 组件、原键恢复/已退休字段 ID/人工新值保护通过。只删除本地定义和值，不删 Google 列。DATA-SCHEMA-06 升为 partial；09 仅追加独立第二 Task 的删除保护断言。当前 227 有断言/24 无，192 partial/59 planned/0 verified。R5→R3→R4 继续，平台/原生完整链仍待验收。


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

## 历史 16 条尚无定位断言：执行分组（2026-09-22；后续完成项由文末和 coverage.json 取代）

仅下表列出尚无直接断言的条目；已有 partial 条目的未满足子条件仍以 coverage.json 为准。每项运行前读取原始 source/source_line，先写联合断言，失败后区分实现缺失与测试缺失；不得仅用测试总数关闭。复用既有 HTTP、SQLite、worker、浏览器和恢复脚本。

| 条目 | 当前最小验收场景 | 下一步与条件 |
| --- | --- | --- |
| DATA-LIFE-01 | 同账号重授权验证主体和目标、先核验未知操作再恢复 | 先复用 lifecycle/recovery 受控身份与网络故障；同账号实网重授权另需授权资源。 |
| DATA-LIFE-07 | 永久失权后隔离旧未知写，并确认旧发送进程停止后才允许目标新写 | 先复用 lifecycle/recovery 受控身份与网络故障；同账号实网重授权另需授权资源。 |
| DATA-SH-03 | 同业务键并发新增云端只保留一行 | M1 云端新增行未批准；先等待该独立契约确认，不扩大现有 addRecord。 |
| DATA-TABLE-08 | 系统状态不能被字段节点改型/删除/映射，业务 status 字段可共存 | 可在现有本机 fixture/真实 worker 执行；按记录、版本、队列、lease 原子性联合断言。 |
| DATA-WRITE-12 | 两个任务反向请求对方记录时不永久等待或半组写 | 可在现有本机 fixture/真实 worker 执行；按记录、版本、队列、lease 原子性联合断言。 |
| DATA-WRITE-13 | 真实循环前两行成功第三行失败，前两行效果与队列保留 | 可在现有本机 fixture/真实 worker 执行；按记录、版本、队列、lease 原子性联合断言。 |
| FLOW-A01 | 两次真实参数任务的变量隔离 | 复用现有生产 worker/浏览器与 Studio 契约；逐项运行对应最小实际链，保留未接通边界。 |
| FLOW-A05 | 可选输入从有到无不读到上一任务记录 | 复用现有生产 worker/浏览器与 Studio 契约；逐项运行对应最小实际链，保留未接通边界。 |
| FLOW-A10 | 结果列存在但无项目写节点时表无变化 | 复用现有生产 worker/浏览器与 Studio 契约；逐项运行对应最小实际链，保留未接通边界。 |
| XE-A01 | 参数网页真实读取、无 lease、资源回收的同一场景联合断言 | 复用现有生产 worker/浏览器与 Studio 契约；逐项运行对应最小实际链，保留未接通边界。 |
| XE-A17 | 活动 Run/已接受保存/未知 Sheets 推送同时归档的收尾 | 复用 lifecycle + worker + sync recovery；不扩展为跨进程人工继续。 |
| XE-A19 | 无 Project 的 Studio 通用运行与项目写回文档明确缺能力 | 复用现有生产 worker/浏览器与 Studio 契约；逐项运行对应最小实际链，保留未接通边界。 |
| XE-C07 | 断线后快照/序号/attempt/产物恢复无重跑无重复追加 | 复用现有生产 worker/浏览器与 Studio 契约；逐项运行对应最小实际链，保留未接通边界。 |
| XE-G02 | 固定参数真实运行的幂等、取消、退出核验整组门禁 | 复用现有生产 worker/浏览器与 Studio 契约；逐项运行对应最小实际链，保留未接通边界。 |
| XE-G06 | 真实同步/保存/清理 blocker 与归档恢复删除/Workspace 切换闭环 | 复用 lifecycle + worker + sync recovery；不扩展为跨进程人工继续。 |
| XE-G07 | 尚未将完整 Studio 窗口/平台门禁各子条件映射到单独断言；不能用项目 smoke 一个总通过替代 | 分平台原生窗口/安装/面板/凭据分别取证；缺物理环境明确待验收。 |

### 2026-09-22 原生 CI 期间继续补证（confirmed）

新增两项直接业务场景，生产源码未变：DATA-LIFE-09 在真实 HTTP 归档收尾后保留未发送本地值及原意图，新推送 409、远端无写；DATA-SCHEMA-08 先由未决意图阻断本地字段删除，明确放弃后删除本地字段而同名远端列/值保持，状态与关联修订不变。两个相关完整文件 21 passed（17.71 秒），全目录 Ruff 通过。这两项为当前 Mac 本地追加证据，不混入 d75297fb 冻结 CI 的测试总数。

当前 251 条中 232 有定位断言、19 未定位；197 partially_verified / 54 planned / 0 verified。LIFE-09 的活动 worker/保存/未知写联合链、完整打包和实网条件仍保留，releaseAccepted=false。

### 2026-09-22 状态边界补证与新来源缺口

STATE-08 已有坏业务值 fixture 的真实 HTTP 状态标记、held/reconciling 拒绝、模拟确认释放后清空及原值/内容版本/空出站队列联合断言通过；相关共享领取文件 17 passed/19.73 秒。只证明已存在记录的状态边界，不冒充来源保留或真实 worker 收尾。最初直接从 Sheets 引入非数字金额时 422，已把 TABLE-02/SH-05 的这项条件记录为 implementation_missing，D1 规格和实施切片另待确认。

最新机器统计为 251 条、233 有断言、18 未定位、196 partial/55 planned/0 verified。此前文末写成 197/54 是手工统计错误：LIFE-09 原本已为 partial，新增断言不应再计一次状态升级；本节纠正该统计，不改变任何条目状态。

### 2026-09-22 共享重叠写与失败后领取映射

SH-02 新增两种写入顺序，逐次远端值/原历史 confirmed/双方完整本地快照/R5 观察/无多余写全部断言；完整同步文件 35 passed/39.99 秒。SYNC-09 复核既有拒绝推值后双拉取与真实 Task 领取冻结快照，映射到具体断言；它不证明 worker 全程执行。仅此两项从 planned 改 partial；原生/实网/完整 UI 条件保留。机器统计 235 有断言/16 未定位/198 partial/53 planned/0 verified。

2026-09-23 后续参数场景：parameter-isolation 在真实 HTTP/SQLite/worker/CloakBrowser 本机运行通过（1 passed/30 deselected，28.56s）。两个 Task 的 taskLocal 初值均为 0，前一任务写入不进入第二任务；结果可查询，无 DataLease；同名项目结果列的原记录及版本完全不变。FLOW-A01 增加范围断言，FLOW-A10 由 planned 升为 partial；当前 240 有断言/11 未定位、200 partial/51 planned/0 verified。此前一次退出 TimeoutError 已保留，根因未确认；本机最终通过不代替该场景的打包/三平台证据。

2026-09-23 FLOW-A05：同一自动化两个独立单任务批次的可选输入从有到无，真实 worker 验收 1 passed/31 deselected（37.63 秒）。第二次两次 inputs capability 输出与持久快照均空，零 lease，首次快照保持且资源回收；不是同批次、变量表达式或打包 UI 证据。独立复审无 P1/P2。最新 241 有断言/10 未定位、201 partial/50 planned/0 verified。

当前未定位的 5 条：DATA-LIFE-01、DATA-SH-03、XE-A17、XE-G06、XE-G07。以上仍按表中最小联合场景执行；已有部分断言的条目也保留其未闭合子条件。

2026-09-23 XE-A01：parameter-single 真实 worker 场景 1 passed/32 deselected（38.06 秒）；无表、参数 first 网页填写/读取、同键重放后唯一 Batch/Task/Run、零 lease 和资源回收联合通过。仅本机源码证据，不扩大为打包 UI/三平台或 XE-G02 全部门禁。当前 242 有断言/9 未定位、201 partial/50 planned/0 verified。

2026-09-23 生命周期补审：LIFE-01/02 不能再仅写缺测试——连接无原位重授权/稳定主体契约，普通改绑无条件新建数据代次。LIFE-07 临时真实 HTTP 探针复现旧 unknown 仍在时重绑并再次云写；L0 在改绑新/旧目标及解绑复用持久值发送围栏，4 个直接反例 RED→GREEN。L0只拒绝绕过，不完成永久失权隔离；L1→L2→L3 具体规格/计划已保存，新增能力尚待批准。最新 243 有范围断言/8 未定位、202 partial/49 planned/0 verified。生产候选已改变，旧 c2 矩阵不能证明此修复，新完整矩阵见 verification.json。
2026-09-23 DATA-WRITE-13 Sheets 续证（confirmed 局部）：原第二本地表循环子范围已补绑定 Sheets 的真实 worker 场景，断言前两条 pending 意图、原远端未变及第三次校验失败后的版本/lease/End。共用变量解析修复嵌套索引完整引用类型，20 个变量差异测试和 6 个 Sheets 真实场景通过。248/251 有范围断言、204 partial/47 planned/0 verified；打包 UI/真实 Google/跨平台同场景未验收。详见 sheets-loop-partial-follow-through.json，releaseAccepted=false。
