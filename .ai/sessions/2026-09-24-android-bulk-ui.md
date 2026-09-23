# Android 批量 UI 续行

- 日期：2026-09-24；状态：partial；来源：生产代码、真实专用 Mac 实例、Vitest 和工程门禁。
- 已完成：断线保留选择但禁用写操作；活跃批次 GET 进度、读取失败重试读取、终态停止、卸载中止；独立复审无 Critical/Important。
- 验证：Android 150 passed，类型/lint/OpenAPI/build exit 0；完整命令及真实证据见[报告](../../docs/qa/android-management/2026-09-24-bulk-stale-snapshot.md)。
- blocked：Mac 锁屏阻塞最终 UI 自动终态，已请求手动解锁；自有客户端/sidecar 已退出，自建设备已由生产 HTTP 删除并核实 missing。没有以 mock 宣称真实通过。
- 下一有界切片：复用 cancelPending 接口，仅取消 queued/waiting_capacity/waiting_device；冻结动作 requestId，传输失败重试原动作，不退回重提原批次；未知/运行中禁止新批次，已确认终态才可重置表单并使用新请求；RED→GREEN、后端现有契约/幂等回归、前端及工程门禁、独立复审、真实桌面验收。
- 依赖冲突：无新 schema/契约依赖；与当前 BulkActions 文件相邻，先提交已验证修复再继续。保留三份 Studio 既有改动，main worktree 不动。

## 取消与新批次续行

- 状态：partial；来源：[本轮代码/测试/真实HTTP报告](../../docs/qa/android-management/2026-09-24-bulk-actions.md)。上方下一切片中的软件工作已实施，不代表真实UI已通过。
- 6个源码/测试文件完成前后端增量；取消动作原编号重试，确认终态后新批次才取新revision；筛选零匹配保留批次，不允许首次提交空目标。
- 审查发现并修复容量异步/跨批次读取/核实异步的取消覆盖，真实SQLite+Event有效RED；最终审查无Critical/Important。
- 前端160项、后端47项聚焦通过；真实8192MiB停机实例容量拒绝、取消、HTTP重启原编号回执一致，资源清理missing。最终全量后端4048passed/26skipped/2warnings、前端424文件/5650项及工程门禁通过，上一轮源码变更后主动中止并保留exit130记录。
- 剩余：解锁后的真实取消/新批次/自动终态；T14隐藏页进度读取暂停与性能/探测指标；T09镜像桌面链；T12向前回退演练；最终全分支回归。目标仍active。
