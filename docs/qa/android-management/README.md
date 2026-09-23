# 安卓模拟器管理验收证据

[自定义候选镜像实测](2026-09-24-custom-image.md)完成基础/候选启动、模板与tag漂移后的固定imageId重启、候选备份恢复，以及模板/实例/备份分别阻止删除。T12.3通过；Google仍not_tested，回退演练和桌面链仍未完成。

[真实恢复空间不足与取消](2026-09-24-restore-cancel-and-disk-full.md)发现并修复命令取消后 SSH 子进程继续写入：4 项真实子进程 RED→GREEN，运行时 63 项通过，Android 聚焦 451 项通过。[多对象清理硬中断](2026-09-24-cleanup-interruption.md)已验证首项删除不被误判为全成功；本轮全后端4035 passed/26 skipped，命令与终态见同一故障报告。T18/T19 已列功能通过，完整目标仍 partial。

[任务逐项证据审计](2026-09-24-task-evidence-audit.md)已核对当前 102 项计划步骤：83 项 passed、16 项 not_run、3 项 blocked；not_run 包含没有找到原始历史 RED 输出的步骤，不用当前 GREEN 追认。代码、契约、迁移、前端、各层测试和真实命令已按 T01–T20 映射。

[真实磁盘不足与传输取消](2026-09-24-backup-failure-verification.md)新增独立 64 MiB 映像的 ENOSPC 与真实在途取消证据，源数据未变且资源已清理；补齐备份未加密/恢复能力边界的可访问说明。

[24 项验收校准](2026-09-23-acceptance-matrix.md)逐项区分通过、部分完成与外部阻塞；不把局部自动化或真实单链推断为四阶段全部完成。

最新 AM1 [真实控制、应用与保留卷验收](2026-09-23-am1-real-control-retention.md)覆盖中文输入、原生/嵌入式切换、30 秒失联回收、HTTP 重启、真实 APK 操作及同卷数据恢复；本轮 RED→GREEN 接通了原本缺失的保留数据 `restore` 入口。此前的[管理操作历史](2026-09-23-operation-history-verification.md)与[控制会话竞态](2026-09-23-control-session-verification.md)分别保留自身证据。真实网络断开及桌面控制同链仍未验收。

[隔离桌面真机链](2026-09-23-desktop-ui-verification.md)新增镜像登记、模板、长名称实例创建/启动/停止/保留/恢复与历史页面证据，修复镜像/旧环境 500、正常设备误报及高缩放状态竖排。应用 125% 和原生五档高缩放已实测；精确 200% 数值、真实网络断开与桌面原生控制同链仍未验收。

[AM2 镜像增量](am2-verification.md)已在真实 Mac/Lima 按固定摘要拉取官方 ReDroid 镜像，并通过认证 HTTP 登记/删除自建 ARM64 测试镜像内容；拉取前来源边界经 RED→GREEN。候选 GApps 账号链、真实断线核实和桌面内容删除仍未验收。[AM3 双实例批量链](2026-09-23-am3-real-bulk-verification.md)完成 start/stop/delete 三批各两项成功、最终容器与卷消失，同时修复真实 HTTP 批次记录泄漏内部字段引起的 500；[审查修复与五实例真实链](2026-09-23-final-review-remediation.md)另覆盖五台 ready、20 次快照、并发预览、文件流备份/恢复和跨重建应用回执核实。十台本机容量阻塞，外部 GApps 条件仍未验收。

[高级日志与十实例容量](2026-09-24-advanced-logs-and-capacity.md)记录单次确认、受限 logcat 元数据导出及真实 ReDroid 196 条结果；十台最低配置加保留需 8192 MiB，本机 Lima 仅 7921 MiB，因此十台真实规模标记 `blocked`。默认诊断继续只含白名单字段。

[批次运行时失败与未知结果](2026-09-24-bulk-runtime-fault.md)新增真实 Docker 容器消失失败、恢复后重试、回执前 SIGKILL、重启核实和未知项不重放；两台数据保留且资源已清理，T13/AM-AC15 通过。

[批次部分失败、重试与取消](2026-09-24-bulk-failure-cancel.md)修复新设备公开修订号与执行比较不一致；两台真实批量停止先得 `[succeeded, failed]`，对修订冲突项显式重试后两项均成功；容量等待子项取消后设备仍停机，三台自建资源最终均清理并只读核实。

[最终分支审查与边界回归](2026-09-24-final-branch-review.md)补齐修订号别名、镜像/备份并发发布、跨重建 APK 与删除核实、批次容量/重试栅栏、恢复预检与异步清理父操作；真实 Shizuku 安装后控制台重建核实及回收通过。只读复审未见剩余 Critical/Important。真实故障矩阵仍以验收矩阵逐项状态为准。

最新 T19 [应用操作标记](2026-09-23-command-marker-verification.md)修复成功回执落盘前丢失客体完成证据的问题；真实 APK 链重跑后客体标记保持 `5→5`，旧残留仍待安全清理。

最新 T15/T19 [客体 APK 暂存回收](2026-09-23-guest-apk-cleanup-verification.md)在上传前持久登记受控路径，回执确认或重启恢复时清理；真实客体文件与重启状态注入通过。无持久路径的旧标记及真实 ADB 断连仍待验证。

最新 T15/T19 [应用完成标记跨重启隔离](2026-09-23-app-marker-restart-verification.md)修复自动恢复释放未核实结果的问题；真实重启后设备保持隔离，显式核实才清理已确认的标记。无登记的旧客体文件和真实断连仍待验收。

最新 T17 [真实备份发布前硬中断](2026-09-23-backup-hard-interruption-verification.md)在实际卷归档暂存后发送 `SIGKILL`：重启后原操作为 `needs_verification`，无假成功备份；公开清理删除孤立暂存，源卷探针读回一致。其后真实备份 ENOSPC、传输取消及传输中自有进程树 SIGKILL 均已通过，见上方 2026-09-24 增量。

最新 T18 [真实恢复写入后发布前硬中断](2026-09-23-restore-hard-interruption-verification.md)在目标卷真实解包完成后发送 `SIGKILL`：重启后仍为待核实，启动/备份/控制被拒绝；目标可删除，同一备份可由新请求正常恢复。随后[真实解包在途中硬中断](2026-09-24-restore-transfer-interruption.md)也已通过：确有部分文件、重启仍隔离、新请求恢复读回一致。

最新 T05/T17/T18 增量见[原生窗口、恢复归属与持久数据属性](2026-09-23-persistent-metadata-verification.md)：118 项最终定向测试与真实 Mac 原生窗口、卷根及扩展属性/ACL、链接保留、部分失败隔离和正常恢复通过；[完整门槛](2026-09-23-full-gates.md)后端 3964 passed、26 skipped。全阶段仍 `partial`。前一增量见[恢复清单与目标身份](2026-09-23-restore-manifest-verification.md)。

[最终完整自动化门槛](2026-09-24-final-full-gates.md)在审查修复后重跑：后端 `4031 passed/26 skipped`，Node 22 前端 `424` 文件/`5625` 项，类型/lint/OpenAPI/构建、Ruff、迁移、结构与脚本均通过。后续 UI 说明增量重跑前端为 `424` 文件/`5626` 项（894.27s），类型/lint/OpenAPI/build 再次 exit 0，见[故障与说明增量](2026-09-24-backup-failure-verification.md)。早先[门槛快照](2026-09-23-current-full-gates.md)仅保留历史对照；软件门槛不代替[24 项矩阵](2026-09-23-acceptance-matrix.md)中的真实场景与外部条件。

状态：`partial`，完整开发与验收目标仍 active。[清理目录与文件保护](2026-09-23-cleanup-verification.md)是前一阶段的 346 项后端快照，其后已补恢复中断隔离和数据属性；有持久来源的 APK 暂存回收和备份/恢复/清理硬中断已有后续证据；无归属来源的旧文件继续排除。[落盘与事务一致性](2026-09-23-publication-verification.md)、[归档安全与属性](2026-09-23-archive-verification.md)、[持久预留与真实验证](2026-09-23-capacity-verification.md)保留各自执行时的历史结果。最新 T06 后端全量、前端及类型/构建门槛见[操作历史记录](2026-09-23-operation-history-verification.md)；前一 AM4 完整门槛见[历史记录](2026-09-23-full-gates.md)。只有明确缺少外部条件的项标记 `blocked`，未执行的验证标记 `not_run`。

实施计划 checkbox 已逐项校准；步骤通过数不等于产品完成率，整体验收仍受真实未运行项和外部条件约束。

审计基线：`codex/android-management-complete`，9 月 22 日历史代码提交 `3ee61947`；本页聚焦计数按隔离 worktree 的可复核输出记录，主工作区既有 Studio 文档改动不属于本模块，未纳入 Android 证据。

## 阶段索引

| 阶段 | 任务 | 证据 | 状态 |
| --- | --- | --- | --- |
| AM1 | T01–T07 | [am1-verification.md](am1-verification.md) | T01–T04 自动验证；T05/T07 真实输入、切端、租约回收、HTTP 重启及保留卷恢复已验，桌面边界与硬中断仍缺证据 |
| AM2 | T08–T12 | [am2-verification.md](am2-verification.md) | 镜像/模板自动化、固定摘要网络拉取及真实 HTTP 内容删除通过；候选 GApps 镜像/账号链缺条件 |
| AM3 | T13–T16 | [am3-verification.md](am3-verification.md) | 规则、观察、预览和双实例自动化证据存在；真实五实例规模、批量 start/stop/delete、部分失败及容量等待取消已验；真实运行时失败后重试与未知项核实也已通过；十台本机容量 blocked，前台/探测指标未完整记录 |
| AM4 | T17–T20 | [am4-verification.md](am4-verification.md) | 备份/恢复/清理与高级日志自动化、真实文件流读回及 logcat 摘要已验；完整失败演练与最终交付未完成 |
| GApps | T11 | [gapps-validation.md](gapps-validation.md) | `blocked` / `not_tested` |

## 全局自动验证

以下为 `2026-09-22-validation.md` 的历史输出；9 月 23 日已修复当时的后端与 Ruff 失败，最新完整结果见[完整门槛](2026-09-23-full-gates.md)。历史输出只作为当时快照，不冒充最新结果：

- Android 后端聚焦集合：`235 passed, 2 warnings`。
- Android 前端：`13 files, 81 passed`（含旧设备列表轮询、未知操作核实、stale/unknown 打开保护、镜像服务端验证/删除核实、批量失败项重试）；typecheck、lint、OpenAPI check、structure 和 build 通过。
- 全后端：`276 passed, 1 warning` 后在既有 `tests/contract/test_proxy_runtime.py::test_runtime_mounts_proxies_but_never_publishes_host_contract` 失败；该断言属于 proxy compatibility，不在 Android 范围。
- 全量前端 `npm test`（最新审计）：`423 files, 417 passed, 6 failed（20 个测试失败）`，失败集中在非 Android 模块，不能视为全量门槛通过。
- 已补软件回归：批量 workspace hash 归属、删除结果核实、观察器首次快照/逐设备异常、环境探测异常均有 RED→GREEN 测试；源实例复制通过服务端快照契约。APK Manifest/split 校验、安装后版本核对及未知应用操作核实入口已实现；9 月 23 日继续修复完成标记、回执持久化顺序和诊断默认字段白名单。
- 全脚本：历史总记录为 `95 tests: 92 passed, 3 pre-existing Studio inventory/reference failures`；最新审计重跑为 `95 tests: 92 passed, 3 failures`，失败仍为 Studio inventory/reference。
- 本轮真实管理链：环境与能力检查 `available=true`；管理快照返回真实设备；停止操作最终 `succeeded`；备份路由返回 `201 Created/state=available/bytes=18585260`；清理预览和执行返回 `200/state=succeeded`；删除实例后按 workspace/device 标签核验容器和卷均为 `0`。GApps 镜像没有 Google-components 标签，保持 `blocked/not_tested`。
- 最终 guarded smoke（显式 `--allow-device-mutation`，隔离 workspace）返回 `status=passed`：`deviceId=cd0b0480-8d3c-4241-908a-a27308e7613d`、`workspaceId=9eb2124e1b481bbf56e749a8d0aa267e4777126e069687310eed050e5d6a1fbb`、应用 `102/102`、截图 `553476` bytes；停止保留数据、启动、移除运行环境、清理独立数据四个阶段完成，`deleted=true/dataRetained=false`。随后按 workspace 标签查询容器和卷均无输出。
- 真实 Lima/ReDroid：ARM64 环境、固定基础镜像、102 项应用清单、`720x1280` 截图、停止后重连、双实例不同 ADB serial、25,472,000 bytes 数据卷备份恢复通过。

完整原始记录：[2026-09-22-validation.md](2026-09-22-validation.md)。

## 状态定义

- `passed`：该任务的自动或真实证据覆盖了任务要求，且输出可复核。
- `blocked`：已有实现或局部测试，但任务要求依赖当前缺失的设备、网络、账号、APK、人工窗口或压力条件。
- `not_run`：任务要求的专门测试/集成流程/文档证据不存在或没有执行记录。
- `failed`：已有可执行路径与要求冲突，需先修复根因再验收。
