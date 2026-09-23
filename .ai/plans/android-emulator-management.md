# 安卓模拟器管理完善：阶段索引

- 日期：2026-09-23（校准；原计划 2026-09-19）
- 状态：confirmed（AM1–AM4 全量实施授权）；partial，持续实施中。
- 当前实施基线：`codex/android-management-complete@52e1f6a6` 加本次隔离增量；原起点 `a92f0688`。
- 实施分支：`codex/android-management-complete`，隔离 worktree。
- 当前阶段：完整目标 active/partial；Android 定向恢复与属性测试 118 passed、1 warning，真实 Mac 新卷恢复及持久属性/链接实验通过。本次 T06 历史增量定向后端 31 项、前端 45 项通过，修复 `deviceId/profileId` 公开参数、跨设备历史和末页游标；最新全量后端 3969 passed、26 skipped，完整前端 424 文件、5619 项通过。逐项命令与剩余工作以最新 QA 记录为准，不用聚焦通过代表完整交付。

正文保存在以下文件，不维护第二份规格：

- [规格说明书](../../docs/superpowers/specs/2026-09-19-android-emulator-management-design.md)
- [实施计划](../../docs/superpowers/plans/2026-09-19-android-emulator-management.md)
- [原规划范围](../decisions/2026-09-19-android-management-scope.md)
- [最新AM1授权及准备记录](../decisions/2026-09-19-android-am1-authorized.md)

| 批次 | 任务 | 范围 | 状态 |
| --- | --- | --- | --- |
| AM1 | T01–T07 | 单实例稳定管理、环境/状态/会话/操作及数据保留 | T01–T04 后端自动化通过；T05 原生窗口进程及关闭后实例存活已真实验证，页面迟到响应/旧输入/路由守卫/原生归属/回收核实经 RED→GREEN；详情移除退役分配及 `/runs` 查询。T06 可见操作历史、正确设备过滤/游标、原请求核实、键盘聚焦及模拟断线只读已补；人工输入、切端、完整 HTTP 重启、长名称/缩放/真实断线和受控中断仍未验收 |
| AM2 | T08–T12 | 镜像、模板、谷歌组件证据 | T08–T10/T12 自动化（含模板生命周期集成）通过；网络拉取、候选镜像和 Google 组件网络/账号验收 blocked |
| AM3 | T13–T16 | 批次、容量、聚合观察、按需预览、应用管理 | 批量、观察、应用和双实例基础证据存在；预览取消及应用核验前端边界已补齐，指定 Node22 验证见 QA 记录。持久容量预留、停止未知预算及启动入口已补齐18项集成与真实双工作区容量实验；批量压力、真实应用动作与规模性能 not_run |
| AM4 | T17–T20 | 停机备份、恢复新实例、安全清理、诊断 | 基础备份/恢复、默认诊断白名单及受限保存 IPC、安全内部链接、UID/GID/mode、备份发布和清理互斥已验证；恢复意图与持久操作/设备前置绑定，失败隔离和成功原子发布已验证；客体侧 tar 的 xattrs/ACL 经真实 1792 项持久条目一致性验证，根目录属性及硬/软链接另经客体实验验证；硬进程中断、APK 遗留临时文件、高级日志及完整失败演练仍待完成 |

## 当前校准

当前唯一 Alembic head 为 `am01_management_operations`，父节点为 `0019_recording_commands`；旧 head 和 `pm07_environments` 父节点描述均已 superseded。隔离 worktree 中的 3 个既有 Studio 文档改动保留，不纳入 Android 提交。原有安卓测试、真实 Mac 条件和网络账号条件分别验证，不能相互替代。

## 验证说明

先前完成的是文档检查，不是业务测试；本轮已补做代码、ADB、Lima、ReDroid 和真实数据卷证据。Google 登录等实际外部条件不足时记录 blocked；测试 APK、人工窗口和多实例指标尚未运行的部分记录 not_run，不能把软件缺口归为环境阻塞。后续每批实际证据记录到实施计划指定的 docs/qa/android-management/ 文件，并更新本索引；当前状态仍为 partial，不自动接入工作流。

- 最新容量证据：[持久预留与真实验收](../../docs/qa/android-management/2026-09-23-capacity-verification.md)。

- 最新校准来源：[9 月 23 日验收](../../docs/qa/android-management/2026-09-23-validation.md)。旧 checkbox 分布尚未完成逐项重审，不作为完成率。

- Node 校准：默认 shell 为26.7.0；规格要求22.x，最终前端门槛使用 npm exec 隔离的22.23.2，不把Node26结果作为指定运行时通过证据。

- 最新 AM4 证据：[归档安全与属性](../../docs/qa/android-management/2026-09-23-archive-verification.md)。

- 最新 AM4 发布证据：[落盘与事务一致性](../../docs/qa/android-management/2026-09-23-publication-verification.md)。

- 最新 AM4 清理证据：[目录、文件保护与真实HTTP](../../docs/qa/android-management/2026-09-23-cleanup-verification.md)。

- 最新 AM4 恢复证据：[中断隔离与成功发布](../../docs/qa/android-management/2026-09-23-restore-isolation-verification.md)。

- 最新 AM4 清单与身份增量：[恢复清单与目标身份](../../docs/qa/android-management/2026-09-23-restore-manifest-verification.md)。

- 最新原生窗口与 AM4 属性增量：[原生窗口、恢复归属与持久数据属性](../../docs/qa/android-management/2026-09-23-persistent-metadata-verification.md)。

- 最新 AM1 历史增量：[管理操作历史与原请求核实](../../docs/qa/android-management/2026-09-23-operation-history-verification.md)。
