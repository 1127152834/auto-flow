# 安卓工作流交接方案索引

- 日期：2026-09-13。
- 状态：confirmed；用户以“开始吧”确认实施，Mac 首版已实现并验证。
- 来源：用户在真实鼠标三组对照通过后，对“先完成接口与状态设计，再接入正式系统”回复“好的 开始吧”；当前 workflows 源码、M2/M3 决策和 Mac 验证记录。
- 规格：[安卓工作流与原生窗口交接](../../docs/superpowers/specs/2026-09-13-android-workflow-handoff-design.md)。
- 计划：[实施计划](../../docs/superpowers/plans/2026-09-13-android-workflow-handoff-implementation.md)。
- 核心取舍：复用正式运行/事件/产物；一次一台且仍一工作区一运行；显式人工节点保留整轮设备占用；关窗不继续；继续先清理原生连接；不把 CUA 当安卓工作流输入驱动。
- 首版专用新设备与旧 Demo 隔离，不接管现有三台；完整创建 UI、批量、混合图和 Windows 实测延期。
- 验证方式：正式 API、单元/契约/React 测试、源码及冻结 sidecar 真实 Android、Mac 打包应用 CUA、浏览器/M3 回归。详见 docs/migration/android-workflow-handoff-validation.md。
- 分支 codex/android-workflow-handoff；与并行 M4 合并待其稳定，不能覆盖其未提交契约和迁移。

2026-09-13 更新：上述“完整创建 UI 延期、M4 合并等待”已 superseded。本轮用户授权并实施正式设备管理与 M4 接入；见 2026-09-13-android-management.md。批量并行与 Windows 仍不在本轮范围。
