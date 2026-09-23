# 安卓模拟器管理完善：阶段索引

- 日期：2026-09-23（校准；原计划 2026-09-19）
- 状态：confirmed（AM1–AM4 全量实施授权）；partial，持续实施中。
- 当前实施基线：`codex/android-management-complete@233c09dd`；原起点 `a92f0688`。
- 实施分支：`codex/android-management-complete`，隔离 worktree。
- 当前阶段：完整目标 active/partial；后端 Android+迁移 head 最近验证 314 passed，前端核验/预览边界已修复，指定 Node22 的 Android 14文件/100项、类型/lint/OpenAPI/结构/build已通过；全量前端及脚本仍失败。逐项命令与剩余工作以最新 QA 记录为准，不用聚焦通过代表完整交付。

正文保存在以下文件，不维护第二份规格：

- [规格说明书](../../docs/superpowers/specs/2026-09-19-android-emulator-management-design.md)
- [实施计划](../../docs/superpowers/plans/2026-09-19-android-emulator-management.md)
- [原规划范围](../decisions/2026-09-19-android-management-scope.md)
- [最新AM1授权及准备记录](../decisions/2026-09-19-android-am1-authorized.md)

| 批次 | 任务 | 范围 | 状态 |
| --- | --- | --- | --- |
| AM1 | T01–T07 | 单实例稳定管理、环境/状态/会话/操作及数据保留 | T01–T03 自动化通过；T04 自动化与同事务投影验证通过；T05–T07 的人工窗口、完整 HTTP 重启和受控中断仍 blocked |
| AM2 | T08–T12 | 镜像、模板、谷歌组件证据 | T08–T10/T12 自动化（含模板生命周期集成）通过；网络拉取、候选镜像和 Google 组件网络/账号验收 blocked |
| AM3 | T13–T16 | 批次、容量、聚合观察、按需预览、应用管理 | 批量、观察、应用和双实例基础证据存在；预览取消及应用核验前端边界已补齐，指定 Node22 验证见 QA 记录。持久容量预留、停止未知预算及启动入口已补齐18项集成与真实双工作区容量实验；批量压力、真实应用动作与规模性能 not_run |
| AM4 | T17–T20 | 停机备份、恢复新实例、安全清理、诊断 | 基础备份/恢复、默认诊断白名单及受限保存 IPC 已实现；安全内部链接和 UID/GID/mode 已补齐25项回归及真实新实例启动读回；xattrs、发布耐久性、临时文件、高级日志及完整失败演练仍待完成 |

## 当前校准

当前唯一 Alembic head 为 `am01_management_operations`，父节点为 `0019_recording_commands`；旧 head 和 `pm07_environments` 父节点描述均已 superseded。隔离 worktree 中的 3 个既有 Studio 文档改动保留，不纳入 Android 提交。原有安卓测试、真实 Mac 条件和网络账号条件分别验证，不能相互替代。

## 验证说明

先前完成的是文档检查，不是业务测试；本轮已补做代码、ADB、Lima、ReDroid 和真实数据卷证据。Google 登录等实际外部条件不足时记录 blocked；测试 APK、人工窗口和多实例指标尚未运行的部分记录 not_run，不能把软件缺口归为环境阻塞。后续每批实际证据记录到实施计划指定的 docs/qa/android-management/ 文件，并更新本索引；当前状态仍为 partial，不自动接入工作流。

- 最新容量证据：[持久预留与真实验收](../../docs/qa/android-management/2026-09-23-capacity-verification.md)。

- 最新校准来源：[9 月 23 日验收](../../docs/qa/android-management/2026-09-23-validation.md)。旧 checkbox 分布尚未完成逐项重审，不作为完成率。

- Node 校准：默认 shell 为26.7.0；规格要求22.x，最终前端门槛使用 npm exec 隔离的22.23.2，不把Node26结果作为指定运行时通过证据。

- 最新 AM4 证据：[归档安全与属性](../../docs/qa/android-management/2026-09-23-archive-verification.md)。
