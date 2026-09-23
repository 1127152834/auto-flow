# 安卓模拟器管理验收证据

[24 项验收校准](2026-09-23-acceptance-matrix.md)逐项区分通过、部分完成与外部阻塞；不把局部自动化或真实单链推断为四阶段全部完成。

最新 AM1 [真实控制、应用与保留卷验收](2026-09-23-am1-real-control-retention.md)覆盖中文输入、原生/嵌入式切换、30 秒失联回收、HTTP 重启、真实 APK 操作及同卷数据恢复；本轮 RED→GREEN 接通了原本缺失的保留数据 `restore` 入口。此前的[管理操作历史](2026-09-23-operation-history-verification.md)与[控制会话竞态](2026-09-23-control-session-verification.md)分别保留自身证据。桌面长名称/200% 缩放、真实网络断开及受控硬中断仍未验收。

最新 T19 [应用操作标记](2026-09-23-command-marker-verification.md)修复成功回执落盘前丢失客体完成证据的问题；真实 APK 链重跑后客体标记保持 `5→5`，旧残留和中断上传的 APK 临时文件仍待安全清理。

最新 T17 [真实备份发布前硬中断](2026-09-23-backup-hard-interruption-verification.md)在实际卷归档暂存后发送 `SIGKILL`：重启后原操作为 `needs_verification`，无假成功备份；公开清理删除孤立暂存，源卷探针读回一致。归档传输中断及磁盘不足仍未验收。

最新 T18 [真实恢复写入后发布前硬中断](2026-09-23-restore-hard-interruption-verification.md)在目标卷真实解包完成后发送 `SIGKILL`：重启后仍为待核实，启动/备份/控制被拒绝；目标可删除，同一备份可由新请求正常恢复。tar 解包过程中断仍未验收。

最新 T05/T17/T18 增量见[原生窗口、恢复归属与持久数据属性](2026-09-23-persistent-metadata-verification.md)：118 项最终定向测试与真实 Mac 原生窗口、卷根及扩展属性/ACL、链接保留、部分失败隔离和正常恢复通过；[完整门槛](2026-09-23-full-gates.md)后端 3964 passed、26 skipped。全阶段仍 `partial`。前一增量见[恢复清单与目标身份](2026-09-23-restore-manifest-verification.md)。

状态：`partial`，完整开发与验收目标仍 active。[清理目录与文件保护](2026-09-23-cleanup-verification.md)是前一阶段的 346 项后端快照，其后已补恢复中断隔离和数据属性；APK 遗留临时文件、硬中断等仍待完成。[落盘与事务一致性](2026-09-23-publication-verification.md)、[归档安全与属性](2026-09-23-archive-verification.md)、[持久预留与真实验证](2026-09-23-capacity-verification.md)保留各自执行时的历史结果。最新 T06 后端全量、前端及类型/构建门槛见[操作历史记录](2026-09-23-operation-history-verification.md)；前一 AM4 完整门槛见[历史记录](2026-09-23-full-gates.md)。只有明确缺少外部条件的项标记 `blocked`，未执行的验证标记 `not_run`。

实施计划的旧 checkbox 状态未完成逐项重新审计，不能作为当前完成率；以最新验收记录中的实际命令、输出和剩余工作为准。

审计基线：`codex/android-management-complete`，9 月 22 日历史代码提交 `3ee61947`；本页聚焦计数按隔离 worktree 的可复核输出记录，主工作区既有 Studio 文档改动不属于本模块，未纳入 Android 证据。

## 阶段索引

| 阶段 | 任务 | 证据 | 状态 |
| --- | --- | --- | --- |
| AM1 | T01–T07 | [am1-verification.md](am1-verification.md) | T01–T04 自动验证；T05/T07 真实输入、切端、租约回收、HTTP 重启及保留卷恢复已验，桌面边界与硬中断仍缺证据 |
| AM2 | T08–T12 | [am2-verification.md](am2-verification.md) | 镜像/模板自动化已通过；网络拉取、候选镜像和 GApps 条件不足 |
| AM3 | T13–T16 | [am3-verification.md](am3-verification.md) | 规则、观察、预览和双实例自动化证据存在；单实例真实应用安装/启动/停止/清数据/卸载已验，批量压力仍未验收 |
| AM4 | T17–T20 | [am4-verification.md](am4-verification.md) | 备份/恢复/清理自动化和基础卷证据存在；完整失败演练与最终交付未完成 |
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
