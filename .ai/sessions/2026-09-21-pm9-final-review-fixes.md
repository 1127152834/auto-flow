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
