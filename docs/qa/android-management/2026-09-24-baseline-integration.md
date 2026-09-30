# Android / PM9 baseline 集成验证

日期：2026-09-24；状态：confirmed，本地合并候选验证通过；不代表整体发布验收通过。

输入 baseline `c6e02427`、Android `746c9c5b`。所有本轮验证从独立集成工作区执行；显式 `PYTHONPATH=apps/backend/src` 避免共享 venv 的 editable 安装指向原工作区。共享依赖和只读 WebRPA 参考目录不提交。

## 合并修复

34 个冲突保留两侧语义，新增唯一合并迁移 `0020_merge_android_pm9`。PM9 fork 的 deepcopy 在 Android 新任务隔离栈上报 ContextVar TypeError，现有 9 个测试先失败，复制当前帧列表后通过。旧 worker 调试断言补保留 PM9 callNodeId/callVisitId。前端 28 个字段断言失败来自旧派生清单，按合并代码重新生成后 900 项定向通过。

## 命令与实际结果

完整日志：同名目录 `2026-09-24-baseline-integration/`。定向 RED/GREEN 与合并审查：`.superpowers/sdd/android-baseline-integration/`。

| 命令 | 实际结果 |
|---|---|
| `PYTHONPATH=apps/backend/src npm run openapi:generate` | exit 0 |
| `npm run typecheck` | exit 0 |
| `uv run ruff check src tests`（apps/backend） | All checks passed |
| `uv run python -m compileall -q src`（apps/backend） | exit 0 |
| `npm run lint` | exit 0 |
| `PYTHONPATH=apps/backend/src npm run openapi:check` | exit 0 |
| `npm run build` | exit 0；依赖 PURE annotation 警告保留 |
| `npm run test:scripts` | 首次 103/104，通过项不掩盖缺 WebRPA 参考目录的失败；链接现有只读参考目录后 104 passed |
| `npm run test:structure` | 4 passed |
| `PYTHONPATH=apps/backend/src uv run --directory apps/backend pytest -q` | 4466 passed / 103 skipped / 2 warnings，1174.05s，exit 0；首次旧进程在 fork 修复后主动中止（143），不计通过 |
| `npm test -- --maxWorkers=2`（apps/desktop） | 首次 5724 passed / 1 failed，429 文件，477.46s；变量字段统计基线15/实际16：双方独立新增字段被Git合成一次。修正基线并补两项语义断言后15项定向通过；最终默认4 workers完整重跑：429 files / 5725 passed，212.80s，exit 0 |

最终前端命令：`npm test -- --maxWorkers=4`（apps/desktop）；源码未再改动。

## 独立审查

`review-report.md` 确认未解决 Critical/Important 为 0；唯一并行 fork 问题已闭环，独立 8 项图与迁移检查通过。逐字节核对双方全部既有迁移不变。

## 边界

本轮未重新执行 Electron/Lima/GApps/十实例或跨平台发布验收，不以单元测试替代。Android 原报告的 partial/blocked、PM9 releaseAccepted=false 与既有 CI 失败均继续有效。只合并本地 baseline，不推送或发布。原工作区未提交改动不纳入此次合并。

全分支 `git diff --cached --check` 报告源分支既有 QA 原始日志/patch 空白及一个测试文件末尾空行；保留历史证据原字节。本轮后端/OpenAPI/scripts冲突解决范围检查通过，不将全分支检查记作绿。

首次前端完整日志在重跑时因归档相对路径错误被覆盖；保留已观察工具输出摘要 `frontend-first-failure-summary.txt`，不伪造完整 RED 日志。代理定向 RED/GREEN 原始日志仍在。

最终所有完整测试进程 exit 0。后端103项跳过不计通过，保留pytest原始结果；两个警告为上游Starlette弃用及重复AndroidManifest测试夹具。最终回归后源码/测试/spec的SHA256与记录一致。
