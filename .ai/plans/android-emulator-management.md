# 安卓模拟器管理完善：阶段索引

- 日期：2026-09-19
- 状态：confirmed（AM1–AM4 全量实施授权）；partial，持续实施中。
- 代码基线：`codex/project-management-pm9@a92f0688f206d4339ff4468c1871f3ccdd6816dc`。
- 实施分支：`codex/android-management-complete`，隔离 worktree。
- 当前阶段：基线重新校准已完成；AM1 从 T01 开始，真实设备条件按证据记录。

正文保存在以下文件，不维护第二份规格：

- [规格说明书](../../docs/superpowers/specs/2026-09-19-android-emulator-management-design.md)
- [实施计划](../../docs/superpowers/plans/2026-09-19-android-emulator-management.md)
- [原规划范围](../decisions/2026-09-19-android-management-scope.md)
- [最新AM1授权及准备记录](../decisions/2026-09-19-android-am1-authorized.md)

| 批次 | 任务 | 范围 | 状态 |
| --- | --- | --- | --- |
| AM1 | T01–T07 | 单实例稳定管理、环境/状态/会话/操作及数据保留 | 基础真实实例创建、连接、截图、stop→connect 已通过；人工窗口/完整 HTTP 重启仍待验收 |
| AM2 | T08–T12 | 镜像、模板、谷歌组件证据 | 固定基础镜像 digest、受限拉取/内容删除适配与生命周期通过；Google 组件网络/账号验收 blocked |
| AM3 | T13–T16 | 批次、容量、聚合观察、按需预览、应用管理 | 两实例真实连接/命令隔离、应用清单、3 秒观察与失败退避通过；批量压力和破坏性应用动作待验收 |
| AM4 | T17–T20 | 停机备份、恢复新实例、安全清理、诊断 | 真实数据标记停机备份→新卷恢复、归档摘要/镜像归属校验和按工作区受控清理删除通过；预览引用指纹可检测归属变化；多实例恢复演练和人工清理确认待验收 |

## 当前校准

当前唯一 Alembic head 为 `0019_recording_commands`；原计划中以 `pm07_environments` 为 AM1 父节点的表述已 superseded。主工作区的未提交 Studio 改动不进入本实施 worktree。原有安卓测试、真实 Mac 条件和网络账号条件分别验证，不能相互替代。

## 验证说明

先前完成的是文档检查，不是业务测试；本轮已补做代码、ADB、Lima、ReDroid 和真实数据卷证据。Google 登录、测试 APK、人工窗口和多实例资源不足项仍按 `blocked` 记录，不用 mock 结果替代。后续每批实际证据记录到实施计划指定的 docs/qa/android-management/ 文件，并更新本索引；不自动接入工作流。
