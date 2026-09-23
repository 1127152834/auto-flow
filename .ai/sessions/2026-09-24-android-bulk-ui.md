# Android 批量 UI 续行

- 日期：2026-09-24；状态：partial；来源：生产代码、真实专用 Mac 实例、Vitest 和工程门禁。
- 已完成：断线保留选择但禁用写操作；活跃批次 GET 进度、读取失败重试读取、终态停止、卸载中止；独立复审无 Critical/Important。
- 验证：Android 150 passed，类型/lint/OpenAPI/build exit 0；完整命令及真实证据见[报告](../../docs/qa/android-management/2026-09-24-bulk-stale-snapshot.md)。
- blocked：Mac 锁屏阻塞最终 UI 自动终态和自建资源清理，已请求手动解锁。没有以 mock 宣称真实通过。
- 下一有界切片：复用 cancelPending 接口，仅取消 queued/waiting_capacity/waiting_device；冻结动作 requestId，传输失败重试原动作，不退回重提原批次；未知/运行中禁止新批次，已确认终态才可重置表单并使用新请求；RED→GREEN、后端现有契约/幂等回归、前端及工程门禁、独立复审、真实桌面验收。
- 依赖冲突：无新 schema/契约依赖；与当前 BulkActions 文件相邻，先提交已验证修复再继续。保留三份 Studio 既有改动，main worktree 不动。
