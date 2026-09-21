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
