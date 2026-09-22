# 安卓模拟器管理验收证据

状态：`partial`（自动化覆盖已扩展；真实 macOS/Lima/网络/GApps/人工窗口条件仍按项 blocked）。本文档只索引实际执行的命令和证据；没有执行或缺少设备、网络、账号、APK、人工窗口条件的项目明确写为 `blocked` 或 `not_run`。

实施计划 100 个 checkbox 当前分布：`passed=25`、`blocked=70`、`not_run=5`、`failed=0`。

审计基线：`codex/android-management-complete`，代码交付提交 `037a27f7`；本页聚焦计数按隔离 worktree 的可复核输出记录，主工作区既有 Studio 文档改动不属于本模块，未纳入 Android 证据。

## 阶段索引

| 阶段 | 任务 | 证据 | 状态 |
| --- | --- | --- | --- |
| AM1 | T01–T07 | [am1-verification.md](am1-verification.md) | T01–T03 自动验证；T04 自动化与同事务投影验证通过；T05–T07 仍有原生窗口、重启和受控中断缺口 |
| AM2 | T08–T12 | [am2-verification.md](am2-verification.md) | 镜像/模板自动化已通过；网络拉取、候选镜像和 GApps 条件不足 |
| AM3 | T13–T16 | [am3-verification.md](am3-verification.md) | 规则、观察、预览和双实例自动化证据存在；批量压力与破坏性应用动作未验收 |
| AM4 | T17–T20 | [am4-verification.md](am4-verification.md) | 备份/恢复/清理自动化和基础卷证据存在；完整失败演练与最终交付未完成 |
| GApps | T11 | [gapps-validation.md](gapps-validation.md) | `blocked` / `not_tested` |

## 全局自动验证

以下输出来自 `2026-09-22-validation.md`，不是对缺失的真实设备或人工步骤的替代：

- Android 后端聚焦集合：`159 passed, 1 warning`。
- Android 前端：`13 files, 45 passed`（含旧设备列表轮询、未知操作核实、stale/unknown 打开保护、镜像/模板和维护入口回归）；typecheck、lint、OpenAPI check、structure 和 build 通过。
- 全后端：`257 passed, 1 warning` 后在既有 `tests/contract/test_proxy_runtime.py::test_runtime_mounts_proxies_but_never_publishes_host_contract` 失败；该断言属于 proxy compatibility，不在 Android 范围。
- 全量前端 `npm test`（最新审计）：`423 files, 417 passed, 6 failed（20 个测试失败）`，失败集中在非 Android 模块，不能视为全量门槛通过。
- 全脚本：历史总记录为 `95 tests: 92 passed, 3 pre-existing Studio inventory/reference failures`；最新审计重跑为 `95 tests: 92 passed, 3 failures`，失败仍为 Studio inventory/reference。
- 本轮真实管理链：环境与能力检查 `available=true`；管理快照返回真实设备；停止操作最终 `succeeded`；备份路由返回 `201 Created/state=available/bytes=18585260`；清理预览和执行返回 `200/state=succeeded`；删除实例后按 workspace/device 标签核验容器和卷均为 `0`。GApps 镜像没有 Google-components 标签，保持 `blocked/not_tested`。
- 真实 Lima/ReDroid：ARM64 环境、固定基础镜像、102 项应用清单、`720x1280` 截图、停止后重连、双实例不同 ADB serial、25,472,000 bytes 数据卷备份恢复通过。

完整原始记录：[2026-09-22-validation.md](2026-09-22-validation.md)。

## 状态定义

- `passed`：该任务的自动或真实证据覆盖了任务要求，且输出可复核。
- `blocked`：已有实现或局部测试，但任务要求依赖当前缺失的设备、网络、账号、APK、人工窗口或压力条件。
- `not_run`：任务要求的专门测试/集成流程/文档证据不存在或没有执行记录。
- `failed`：已有可执行路径与要求冲突，需先修复根因再验收。
