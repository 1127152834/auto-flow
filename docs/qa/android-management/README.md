# 安卓模拟器管理验收证据

最新 T18 增量见[恢复清单与目标身份](2026-09-23-restore-manifest-verification.md)：44 项定向测试与真实 Mac 部分写入/正常恢复重跑通过；全阶段仍 `partial`。

状态：`partial`，完整开发与验收目标仍 active。最新[清理目录与文件保护](2026-09-23-cleanup-verification.md)：后端346 passed、前端Android104 passed，真实HTTP目录/409/选择删除/恢复互斥通过；APK遗留临时文件与恢复中断等仍待完成。最新发布增量见[落盘与事务一致性](2026-09-23-publication-verification.md)：后端328 passed，真实新实例恢复启动通过；完整目标仍有待办。前一 AM4 增量见[归档安全与属性](2026-09-23-archive-verification.md)：后端314 passed，真实新实例恢复启动及 UID/GID/mode、安全链接通过；xattrs、硬中断恢复等仍待完成。最新容量增量见[持久预留与真实验证](2026-09-23-capacity-verification.md)：后端289 passed，跨工作区unknown预算与核实释放通过；仍不代表AM3整阶段完成。最新证据见 [后端增量](2026-09-23-validation.md)、[前端增量](2026-09-23-frontend-validation.md)及[应用命令语义/真实验证](2026-09-23-command-verification.md)。仍有可继续修复的软件缺口及全量门槛失败；只有明确缺少外部条件的项标记 `blocked`，未执行的验证标记 `not_run`。

实施计划的旧 checkbox 状态未完成逐项重新审计，不能作为当前完成率；以最新验收记录中的实际命令、输出和剩余工作为准。

审计基线：`codex/android-management-complete`，9 月 22 日历史代码提交 `3ee61947`；本页聚焦计数按隔离 worktree 的可复核输出记录，主工作区既有 Studio 文档改动不属于本模块，未纳入 Android 证据。

## 阶段索引

| 阶段 | 任务 | 证据 | 状态 |
| --- | --- | --- | --- |
| AM1 | T01–T07 | [am1-verification.md](am1-verification.md) | T01–T03 自动验证；T04 自动化与同事务投影验证通过；T05–T07 仍有原生窗口、重启和受控中断缺口 |
| AM2 | T08–T12 | [am2-verification.md](am2-verification.md) | 镜像/模板自动化已通过；网络拉取、候选镜像和 GApps 条件不足 |
| AM3 | T13–T16 | [am3-verification.md](am3-verification.md) | 规则、观察、预览和双实例自动化证据存在；批量压力与破坏性应用动作未验收 |
| AM4 | T17–T20 | [am4-verification.md](am4-verification.md) | 备份/恢复/清理自动化和基础卷证据存在；完整失败演练与最终交付未完成 |
| GApps | T11 | [gapps-validation.md](gapps-validation.md) | `blocked` / `not_tested` |

## 全局自动验证

以下为 `2026-09-22-validation.md` 的历史输出；9 月 23 日早一轮后端聚焦（含 migration heads）为 `253 passed, 2 warnings`，最新命令语义增量已达到 `271 passed, 2 warnings`，完整后端及 Ruff 仍失败。历史前端和构建结果不冒充本轮重跑：

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
