# 安卓模拟器管理完善：阶段索引

- 日期：2026-09-24（校准；原计划 2026-09-19）
- 状态：confirmed（AM1–AM4 全量实施授权）；partial，持续实施中。
- 当前实施基线：`codex/android-management-complete@471b816f` 加自定义候选镜像验收增量；原起点 `a92f0688`。
- 实施分支：`codex/android-management-complete`，隔离 worktree。

## 2026-09-23 全分支审查后增量

- 2026-09-24 续行：[真实备份 ENOSPC 与传输取消](../../docs/qa/android-management/2026-09-24-backup-failure-verification.md)通过，无可用备份/暂存残留，原请求不重放，源探针保持；补备份本机未加密和恢复登录/DRM/私钥边界说明（RED 1 failed → GREEN 26 passed）。[任务逐项审计](../../docs/qa/android-management/2026-09-24-task-evidence-audit.md)将当前 102 步全部附证据：84 passed、15 not_run、3 blocked；部分 not_run 为历史 RED 缺证，未追认。
- 2026-09-24 最终只读复审已覆盖运行时、Operation、镜像、批次、备份恢复、清理、诊断及前端，未发现剩余 Critical/Important。修复和先 RED 后 GREEN 的证据见[最终分支审查](../../docs/qa/android-management/2026-09-24-final-branch-review.md)；未完成真实环境矩阵不因代码审查通过而转为通过。

- 状态：`confirmed`（以下定向/真实证据）；完整目标仍 `partial`。来源：[审查修复与真实验收](../../docs/qa/android-management/2026-09-23-final-review-remediation.md)。以下结论覆盖本页下方较早的规模及自动化快照。
- AM1：应用操作持久回执可在控制台重建后按原会话与请求编号核实；未核实完成标记不能被普通设备恢复清除。真实 ReDroid 完成标记、重建控制台、回执提交、恢复和删除通过；真实 HTTP 进程 `SIGKILL` 尚未注入。
- AM2：备份的工作区路径身份加入镜像引用保护；自定义镜像恢复按固定 imageId 实际缓存核实；同摘要每次拉取有独立持久回执；元数据核验与谷歌六项验收分别在契约与界面显示。专用 GApps 镜像/账号链继续 `blocked/not_tested`。
- AM3：真实五实例全部 ready，20 次 HTTP 快照 `median=2.13ms/p95=2.74ms`，两台并发预览及五台内存读数已记录，最终容器/卷为零。[真实部分失败、修订冲突项重试与取消](../../docs/qa/android-management/2026-09-24-bulk-failure-cancel.md)通过，并修复新设备公开修订号与批次比较不一致。十台最低需求 8192 MiB 超过本机 Lima 的 7921 MiB，真实规模标记 `blocked`；[运行时容器消失失败与回执前强杀](../../docs/qa/android-management/2026-09-24-bulk-runtime-fault.md)已验证恢复后重试和未知项只可核实。
- AM4：生产备份/恢复改为 Lima 文件描述符流和逐块摘要；真实 17,868,800 字节备份→新实例读回通过。[高级日志](../../docs/qa/android-management/2026-09-24-advanced-logs-and-capacity.md)已按单次确认/归属/限时限量提供元数据摘要，真实 ReDroid 196 条通过。真实备份磁盘不足与归档传输取消已补；恢复解包中 SIGKILL 已补；目标磁盘不足与取消恢复已验，修复普通/文件命令仅杀父进程导致 SSH 继续写入的根因。
- 自动化：最终审查后[完整软件门槛](../../docs/qa/android-management/2026-09-24-final-full-gates.md)通过：后端 `4031 passed, 26 skipped, 2 warnings in 852.64s`；Node 22 前端在后续 UI 说明增量后再跑 `424` 文件/`5626` 项（894.27s），类型/lint/OpenAPI/构建再次 exit 0；本轮后端命令树有修复，451项聚焦、完整4035 passed/26 skipped及Ruff/compileall/OpenAPI通过；全量终态见[本轮故障报告](../../docs/qa/android-management/2026-09-24-restore-cancel-and-disk-full.md)，旧4031项不冒充新树结果。结构与脚本对应源码未改。定向测试集合有重叠，不相加。
- 当前阶段：完整目标 active/partial；最终审查增量已提交 30eb0926，本次后续故障/说明/审计形成独立有界提交。真实 Mac 输入/切端/租约回收/HTTP 重启、应用动作及跨重建回执、同卷恢复与双实例删除隔离、五实例、部分失败/修订冲突项重试/容量取消、文件流备份恢复、ENOSPC/传输取消和高级日志均有独立证据；十实例受本机容量阻塞，其他故障和外部 GApps 链仍未完成。逐项命令与风险以最新 QA 记录为准。

正文保存在以下文件，不维护第二份规格：

- [规格说明书](../../docs/superpowers/specs/2026-09-19-android-emulator-management-design.md)
- [实施计划](../../docs/superpowers/plans/2026-09-19-android-emulator-management.md)
- [原规划范围](../decisions/2026-09-19-android-management-scope.md)
- [最新AM1授权及准备记录](../decisions/2026-09-19-android-am1-authorized.md)

| 批次 | 任务 | 范围 | 状态 |
| --- | --- | --- | --- |
| AM1 | T01–T07 | 单实例稳定管理、环境/状态/会话/操作及数据保留 | 自动化与真实 Mac 输入、切端、租约回收、HTTP 重启、保留卷恢复及隔离桌面创建/生命周期通过；Shizuku 安装后重建控制台可核实原回执并恢复控制。真实桌面往返/原生离页/SSH断线恢复已通过；精确200%/指定窗口及桌面应用确认流仍未验收 |
| AM2 | T08–T12 | 镜像、模板、谷歌组件证据 | T08–T10/T12 自动化（含模板生命周期集成）通过；固定摘要官方 ReDroid 仓库真实网络拉取成功且原 tag 未变，自建 ARM64 小镜像经认证 HTTP 登记并实际删除内容。候选 GApps 镜像/账号下载链 blocked；真实断线后拉取核实和桌面内容删除未验收 |
| AM3 | T13–T16 | 批次、容量、聚合观察、按需预览、应用管理 | 真实双实例 start/stop/delete、部分失败后修订冲突项 `retryFailed`、容量等待取消、五实例快照及双预览通过；真实 APK 安装/版本核实、启动、停止、清数据、卸载和重建回执通过。十实例因 Lima 内存预算不足 `blocked`；真实运行时失败后重试和未知项核实已通过，桌面前台与探测指标仍未完整验收 |
| AM4 | T17–T20 | 停机备份、恢复新实例、安全清理、诊断 | 自动化覆盖归档安全、同事务发布、恢复归属、清理保护与脱敏边界；真实文件流备份恢复、持久条目读回、备份/恢复发布点 `SIGKILL` 后隔离、高级日志 196 条仅元数据、实际资源清理通过。真实备份磁盘不足/传输取消已验；恢复解包中 SIGKILL 已验；目标磁盘不足/取消恢复与多对象清理硬中断已验；完整故障矩阵仍未结束，无来源旧文件继续排除 |

## 当前校准

当前唯一 Alembic head 为 `am01_management_operations`，父节点为 `0019_recording_commands`；旧 head 和 `pm07_environments` 父节点描述均已 superseded。隔离 worktree 中的 3 个既有 Studio 文档改动保留，不纳入 Android 提交。原有安卓测试、真实 Mac 条件和网络账号条件分别验证，不能相互替代。

## 验证说明

先前完成的是文档检查，不是业务测试；本轮已补做代码、ADB、Lima、ReDroid、真实数据卷及隔离桌面页面证据。Google 登录等实际外部条件不足时记录 blocked；测试 APK 与原生窗口已在自建实例验证，前台多实例指标、指定窗口/精确缩放及桌面应用确认流仍为 not_run；桌面控制/受控SSH断线已通过，不能把软件缺口归为环境阻塞。后续每批实际证据记录到实施计划指定的 docs/qa/android-management/ 文件，并更新本索引；当前状态仍为 partial，不自动接入工作流。

- 最新容量证据：[持久预留与真实验收](../../docs/qa/android-management/2026-09-23-capacity-verification.md)。

- 最新校准来源：[102 步逐项追踪](../../docs/qa/android-management/2026-09-24-task-evidence-audit.md)。checkbox 数量仅是步骤证据状态，不作为产品完成率。

- Node 校准：默认 shell 为26.7.0；规格要求22.x，最终前端门槛使用 npm exec 隔离的22.23.2，不把Node26结果作为指定运行时通过证据。

- 最新 AM4 证据：[归档安全与属性](../../docs/qa/android-management/2026-09-23-archive-verification.md)。

- 最新 AM4 发布证据：[落盘与事务一致性](../../docs/qa/android-management/2026-09-23-publication-verification.md)。

- 最新 AM4 发布前硬中断证据：[真实 SIGKILL、待核实、暂存清理与源卷读回](../../docs/qa/android-management/2026-09-23-backup-hard-interruption-verification.md)。

- 最新 AM4 恢复写入后硬中断证据：[真实 SIGKILL、目标隔离与新请求恢复](../../docs/qa/android-management/2026-09-23-restore-hard-interruption-verification.md)。

- 最新 T15/T19 客体暂存增量：[上传前登记与重启回收](../../docs/qa/android-management/2026-09-23-guest-apk-cleanup-verification.md)。

- 最新 T15/T19 结果未知增量：[应用完成标记跨重启隔离](../../docs/qa/android-management/2026-09-23-app-marker-restart-verification.md)。

- 最新 AM4 清理证据：[目录、文件保护与真实HTTP](../../docs/qa/android-management/2026-09-23-cleanup-verification.md)。

- 最新 AM4 恢复证据：[中断隔离与成功发布](../../docs/qa/android-management/2026-09-23-restore-isolation-verification.md)。

- 最新 AM4 清单与身份增量：[恢复清单与目标身份](../../docs/qa/android-management/2026-09-23-restore-manifest-verification.md)。

- 最新原生窗口与 AM4 属性增量：[原生窗口、恢复归属与持久数据属性](../../docs/qa/android-management/2026-09-23-persistent-metadata-verification.md)。

- 最新 AM1 历史增量：[管理操作历史与原请求核实](../../docs/qa/android-management/2026-09-23-operation-history-verification.md)。

- 最新完整自动化门槛：[后端、Node 22 前端、脚本、结构与构建](../../docs/qa/android-management/2026-09-24-final-full-gates.md)。

- 最新桌面真机链：[镜像、模板、生命周期与高缩放](../../docs/qa/android-management/2026-09-23-desktop-ui-verification.md)。

- 最新 AM2 镜像增量：[固定摘要网络拉取、HTTP 内容删除及来源边界](../../docs/qa/android-management/am2-verification.md)。

- 最新 AM3 实例批次：[真实双实例 start/stop/delete 与 HTTP DTO 修复](../../docs/qa/android-management/2026-09-23-am3-real-bulk-verification.md)。

- 2026-09-24 自定义候选镜像：[真实报告](../../docs/qa/android-management/2026-09-24-custom-image.md)完成基础/A启动、tag与模板改指B后旧实例固定A、候选备份恢复及三类引用阻删；T12.3通过，T12回退演练/GApps仍未验。生产代码未改，镜像模板定向40项通过。

- 2026-09-24 桌面控制增量：[真实断线、原生往返及根因修复](../../docs/qa/android-management/2026-09-24-desktop-control.md)：已完成自建设备真实控制/导航/SSH断线/重新连接与清理，补ADB后台服务、切端输入/心跳身份和离线清理回归；最终后端4041passed/26skipped、前端5631passed，类型/lint/OpenAPI/build通过；T05/AC05/AC06关闭，总目标仍partial。

- 2026-09-24 APK执行中断：[真实ADB断线、HTTP强杀与数据保留](../../docs/qa/android-management/2026-09-24-app-interruption.md)完成两种覆盖安装故障，重启后旧包/数据存在仍保持结果未知并锁定控制，三轮5台自建资源清理。生产代码未变，应用回归32项通过；T07.3通过，当前步骤84passed/15not_run/3blocked，桌面确认流仍未验。
