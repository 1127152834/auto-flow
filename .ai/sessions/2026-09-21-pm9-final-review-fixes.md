# PM9 最终独立审查修复

- 日期：2026-09-21；状态：confirmed（针对性验证），完整候选三平台回归待运行。
- 来源：8e5564e0..25337abf 一次独立最终审查；4 项 Important，无 Critical。按规则仅一次修复轮，不重新派发审查。
- 人工契约：冻结校验与执行统一使用 data.config（存在时）；嵌套保护变量、类型、End/非法继续位置 4 个拒绝案例先失败，再通过。
- 敏感值：显式子流程输入携带敏感标记，子流程与并行输出合并携带源变量标记；取消包装的子 Task 将实际敏感使用标记返回调用上下文。两个合成秘密测试先失败，再验证内部值不变且事件不泄露；未使用真实秘密。
- 子流程权限：任务表授权是上界，实际请求进一步与当前冻结子节点的 tableGrant 取交集。保留明确输入记录授权，删除子调用中的旧式整表 createRecordTargets。其他表、字段、操作、无声明 4 个越权案例先失败，再拒绝；合法声明仍可创建。
- Windows 启动：父端在 spawn 前创建并持有 Job；子端加入父 Job；父端验证实际拥有的 launcher 出生身份、加入 Job 并持久化证明后才发送 start。取消等待所有权确认；无法确认的进程树保留目录与容量。启动顺序测试先失败，再通过；新增 ready 前取消/超时原生进程树验证，待 Windows CI。
- 验证：人工/图执行 102 passed；能力边界 29 passed；进程/恢复/身份 59 passed、8 原生跳过。ruff 通过，mypy 402 文件通过。前端完整重跑 5459 passed；typecheck/lint/build 通过。
- 保持拒绝：Windows 既有文件覆盖、追加、读取仍无满足完整安全契约的实现。实机、当前打包 Sheets/OAuth、签名仍外部待验收；releaseAccepted=false。

补充验证（confirmed）：26 个真实 HTTP/SQLite/CloakBrowser 场景复跑 274.67 秒全通过；最终边界定向 149 passed、2 原生 skipped；脚本 100 passed。Windows 原生复验 35580013772 的实际 ready 前取消/超时、Job 恢复和文件案例通过，整体为 87 passed、27 skipped、1 failed，失败只在模拟 Job 顺序夹具。修正夹具不启动真实 Job bootstrap，另加身份未知时目录/容量保留断言。其原生复验并入最终完整矩阵，不重复单独探针。

完整本机后端：3297 passed、60 skipped、2 warnings，578.08 秒；随后新增的 unknown-attachment 参数已由 149 项定向单独覆盖。三平台候选 18435502 的 Windows 在较广原生测试集发现旧 list_export 用例仍期待所有 Windows 输出失败，而新文件适配实际成功；改为三平台共用内容、事件、快照一致性断言，既有文件保护不变。生产代码不变，两 Mac 继续当前候选矩阵；既有 workflow 新增可选单平台手动入口，默认 push/PR/dispatch 仍跑三平台，仅对该测试修正重跑 Windows 完整链。

Windows 单平台 35581391812：236 passed、27 skipped、1 failed（foreign-job 恢复后 PID/birth 保守探测仍为 alive）。Job accounting 已确认 active=0，但重新打开正在 rundown 的进程可能缺少可证明退出的访问权限；尚不能据此断言真实残留或测试问题。原生测试改为终止前持有已核验 birth/Job 成员身份的子进程 SYNCHRONIZE 句柄，恢复返回后零等待检查信号，禁止宽限延迟掩盖过早释放。生产安全判断未改，单独原生探针核实后再决定。

2026-09-21 后续原生复验（confirmed）：6f1390a1 原生持有句柄仍返回 WAIT_TIMEOUT，推翻上段仅 PID 探测不确定的猜想。0cee27ca 修复共享 Job 清理：终止前持有成员句柄，accounting 归零后在同一期限内等待退出；35583149567 全部成功，92 passed、27 skipped，原 wrong-birth/denied 恢复返回立即检查退出也通过。详情见 windows-native-boundary-probe.md。

本机 ARM 新构建 DMG（9001b0a6 生产等价，Windows/Sheets 后续修复不在包内）校验、只读挂载、隔离安装、打包侧车认证和退出通过。真实原生打开取消、选择新生成 workbook 的 opaque token、保存取消通过，结果在 install-capabilities-darwin-arm64.json。未注入 dialog 返回值；第一次操作超时没有计为通过。

Sheets 补证发现并修复已有契约内根因（confirmed targeted；full regression pending）：出站从整行实时取值导致两个项目改不同列相互覆盖；原响应核验也误用更新后的行。复用 SyncOperationRow.request JSON 保存字段和值，未发送合并同时推进 statusRevision；发送前用既有事务 CAS 登记 sending，使新编辑生成新意图；重启/手动 allPending 不重发 sending/verifying。明确 null 写入空单元格。旧操作无快照时停止并报告 SYNC_SNAPSHOT_MISSING，不推断历史内容。三个真实 HTTP/SQLite + FakeSheetsTransport 反例先失败再通过；补原意图合并/清空和旧无快照保护后相关 46 passed。没有引入新执行器、数据库表、Google 网络授权或新冻结能力端口。

Sheets 空值协议补证：Google ValueRange 对读取结果省略末尾空行/列，写 null 会跳过、写空字符串才清空（来源 https://developers.google.com/workspace/sheets/api/reference/rest/v4/spreadsheets.values#ValueRange）。将清空用例的受控读取改为实际协议的空列表后先失败；核验单元格提取时将未返回的格视为空字符串，严格 typed _same 比较不变。fed0b4c1 矩阵因该生产修正被替代；等本机定向/全量完成后仅启动一个最终候选矩阵。

发送/放弃交错补证（confirmed）：放弃操作在事务外核对旧状态，却没有给已有 transition 传 expected_status_revision，可能把已确认操作改成放弃。确定性 HTTP 交错先复现失败，再用一行事务 CAS 参数修复；同时覆盖放弃先胜，后续推送不发送，并且拉取仍保留本地值与内容修订。DATA-SYNC-01/06 增加直接映射，216 有断言 / 35 未定位，188 partial / 63 planned / 0 verified 未变。

新增数据能力方案（proposed）：docs/superpowers/specs/2026-09-21-pm9-remaining-data-capabilities.md 明确 R1 只读结构请求、R2 删除影响事务、R3 系统 UUID 原计划核验、R4 来源增列依赖和 R5 只读观察的契约/拒绝/切片/测试；按 AGENTS.md 架构改动规则，尚未实现这五个新增端口，等待确认。已批准修复和回归不依赖此决定。

本机完整回归（confirmed）：fed0b4c1 全后端 3311 passed、60 skipped、2 warnings，587.44 秒；后续空 ValueRange 与放弃 CAS 修改由 60 项相关用例、ruff/mypy 通过，源码候选 82c067c9。此前 95508bfc/fed0b4c1 两个未完成矩阵均只作被替代记录，最终矩阵在本机稳定后启动。

CI 纠正（confirmed）：ccef90e9 的 35584940782 三平台均在 ruff B023 停止；之前“ruff 通过”不能覆盖最后新增的循环闭包夹具，此结论 superseded。没有修改生产逻辑或忽略规则：将两种竞争顺序改成 pytest 参数，完整 ruff check . --no-cache 通过；相关 61 passed、2 warnings（26.24s），mypy 402 文件通过。后续组合命令使用失败即停止并检查各步结果，不能以末项 mypy 的成功推断前项 lint 成功。

当前 ccef90e9 ARM 包（production = 82c067c9）：新 DMG SHA256 1f6aa64deac3bfe95b5cfaa601f62bf9bf3c5bc22fdaec823f6ac86ea685573f。校验、只读挂载、隔离复制、认证侧车启动/退出均通过；真实 native open 取消/选择和 save 取消通过，未注入面板结果。报告 install-final-candidate-darwin-arm64.json，截图只显示合成项目。旧 ARM 证据保留，不虚称此包已验证完整 save/export、OAuth、签名、公证或卸载。

Windows 广集复验 d21197ad / 35585675170：239 passed、27 skipped、1 failed，失败是 durable callback 测试在等待事件的 3 秒外层期限超时（尚未记录该次启动实际阶段）。Job/所有权原生用例均通过。确定性增加 3.2 秒 spawn 延迟可使原测试在任何平台失败，worker 尚未创建，证明该夹具把启动耗时混成 ACK 持久化语义。测试新增该延迟参数、15 秒有界事件等待，并在 worker 提前结束时立即抛其真实异常；finally 回收等待任务/所属 worker。只该正常提交顺序用例使用 10 秒启动期限，生产 90 秒启动/3 秒清理、专门超时/取消用例不变。严格保留提交前无 proof、提交后成功/proof/清理检查。64 passed、8 native skipped（8.89s）；全无缓存 ruff 和映射校验通过。原 Windows 超时具体原因仍未证实，不写成性能要求不达标；Windows 全链复验，Mac 保留当前运行。


## 既有 Sheets 状态与删除补证（confirmed）

通过真实 HTTP/SQLite 和现有受控 Google transport 补齐普通/公式列拉取不复活 tombstone，以及显式 null/非空状态在确认/失败/未知后的稳定身份、业务状态版本和本地值。新增 8 项通过，相关 sync/recovery/rules 45 passed, 2 warnings in 33.90s；ruff 与 251 映射校验通过。只增加测试与局部断言映射，生产源码仍 82c067c9，218 有断言 / 33 未定位，未提升验收状态。当前 Mac d21197ad 与 Windows 25c9a41b 全链继续；不因测试追加重复跑矩阵。


## Excel 重复行补证（confirmed）

复用既有 host selection token/HTTP 导入与真实工作簿，断言两行同内容身份不同、单行状态与内容修改不影响另一行、本地新建/删除后源 XLSX 字节相同。新增测试先修正了 inspection 已完成返回 200 及只提交 fieldId/value 两个现有 HTTP 契约预期；没有生产修复。导入与占用保护 18 passed, 2 warnings in 15.24s。映射 219 有断言 / 32 未定位；原生面板与打包子条件保留。


## 共享 Sheets 数据领取缺口（confirmed）

实际双项目同物理 Sheet 同业务身份列 A-1 的两个 select_required 均 ready，键含各自 project/table/generation，公共键相等断言失败（1 failed in 2.09s）。这是实现缺失，不能以已有推送协调或原 32 条缺断言描述遮蔽。失败诊断独立保存在 docs/pm9/diagnostics，不加入常规通过回归或映射 checks。C1–C4 共享身份/事务/升级/生命周期方案已完成，proposed，等待架构确认；当前用户的 R1–R5 待确认问题不包含这一新片。生产源未变，releaseAccepted=false。


## 当前 ARM CI 与插行状态补证（confirmed）

d21197ad ARM job 106288334872 success；3313 backend、5459 frontend、15 real worker 及源码/打包/安装产物通过。下载日志核对六份实际业务报告均 passed，已保存 artifact digest/期限；不把 CI DMG 当实机安装。已有状态用例增加远端 B-2 插在 A-1 前，6 passed in 7.74s，原状态身份不迁移。台账 220/31，未升级整体验收。


## Intel 完整回归失败与定向修正（confirmed）

35585675170 Intel 3312 passed / 60 skipped / 1 failed in 1875.04s。失败明确在 shutdown test GET /openapi.json read timeout（5s），未进入 SSE/关停阶段；不将其说成关停失败，也不推断硬件根因。测试为 schema 准备请求单独设 30s，生产码和 3/8s 退出/SSE/worker 清理断言不变；shutdown+node writes 8 passed in 26.58s，完整无缓存 ruff passed。创建后状态权限拒绝仍保留完整 null 新记录的断言补入 DATA-STATE-10，台账221/30，worker证据缺口保留。只派发Intel全链，不重复ARM/Windows。


## 写入后核验读取失败（confirmed，新生产修复）

部分核验第二个 GET 超时实际 RED：原 SheetsApiError 泄漏，推送操作未完成。复用同一 `_verify` 错误转换、每条原意图 unknown、现有 `_runs.fail`，修复推送/只读核验/接受后取凭据三个关联路径；无新存储/协议/执行器。原 push 重放没有额外网络写，v2 原核验不吞掉 v3；reconcile header/cell 失败后原未知写不变、原只读命令明确失败且可新核验。50 相关测试通过，分块上限1的首块确认/次块失败/后续新值单项通过；mypy402/no-cache ruff通过。

旧 Windows35586541932 与 Intel35589713895因生产候选变更取消，非通过。ARM d21197ad 完整成功只覆盖82源码。将冻结本片并进行新完整本机/三平台，不把旧 native DMG 自动称为新完整包。新增DATA-SYNC-08局部映射，222有断言/29未定位，状态不提升。


## 新候选验证派发（confirmed）

生产 f580b1c6、验证提交0303924d，完整三平台35590418456已派发，本机pytest全量并行运行。旧ARM成功已另存ci-capabilities-82c067c9-darwin-arm64.json，避免后续新候选结果覆盖旧报告引用。R1–R5与新共享领取C1–C4已合成一个待确认问题（先C，再R1/R2/R5/R3/R4），替代旧仅R1–R5的问题；未有回复不视为批准。


## Sheets 行变更范围校正（confirmed）

按实际调用核对：_push 缺行只失败，DataDeletion repository 只写本地 tombstone/日志，无远端新增/删除意图或模板复制路径。DATA-SH-03/10/11追加implementation_missing，原通过断言不删除、不夸大。M1–M3 独立具体契约为 proposed，不属于当前C/R确认问题；未修改生产源码，继续f580候选验证。
