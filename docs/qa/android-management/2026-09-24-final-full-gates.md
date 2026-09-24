# 安卓管理最终分支自动化与真实实例门槛

- 日期：2026-09-24；状态：`confirmed`（以下已结束命令及实际输出）；AM1–AM4 完整验收仍为 `partial`。
- 来源：隔离分支 `codex/android-management-complete` 的最终审查修复后工作树；Apple Silicon macOS、Lima、ReDroid。前端在隔离的 Node `22.23.2` 运行，默认 Node 26 不计作指定运行时验收。
- 本轮只操作独立临时工作区中的自建安卓资源。既有三份 Studio 文档改动按原 SHA-256 保留，不纳入安卓提交。

| 命令 | 实际输出摘要 |
| --- | --- |
| `uv run --project apps/backend pytest -q apps/backend/tests` | exit 0；`4031 passed, 26 skipped, 2 warnings in 852.64s`。警告为 Starlette anyio 别名弃用与故意构造重复 APK Manifest 的 ZIP 提示。 |
| `npm exec --offline --yes --package=node@22.23.2 -c 'npm test -w @autoflow/desktop -- --maxWorkers=1 --testTimeout=15000'` | exit 0；`424 Test Files passed`、`5625 Tests passed`、`Duration 858.55s`。单 worker，完整后端结束后独立执行。 |
| `uv run --project apps/backend ruff check apps/backend/src apps/backend/tests`；`uv run --project apps/backend python -m compileall -q apps/backend/src` | 两项 exit 0；Ruff `All checks passed!`，编译无输出。 |
| `uv run --project apps/backend pytest apps/backend/tests/integration/test_migration_heads.py -q`；`uv run alembic -c src/autoflow/infrastructure/database/alembic.ini heads`（在 `apps/backend`） | `2 passed in 0.23s`；唯一 head `am01_management_operations`。 |
| `npm exec --offline --yes --package=node@22.23.2 -c 'npm run typecheck && npm run lint && npm run openapi:check && npm run build'` | 四项 exit 0；`tsc --noEmit`、ESLint、生成契约核对通过；Electron/Vite 构建 `11751 modules transformed`、`built in 41.67s`。构建仍有既有的 Rollup 注释/拆包提示，不影响退出码。 |
| Node 22 下 `npm run test:structure`、`npm run test:scripts` | exit 0；结构 `4/4`、脚本 `95/95`。脚本执行前保存、结束后逐字节恢复三份既有 Studio 文档修改；当前 SHA-256 与原值一致。 |
| `git diff --check` | exit 0，无输出。 |

上述软件门槛均通过；完整产品验收仍受下述真实条件与未演练故障约束。`test:structure`/`test:scripts` 在最后一轮后端测试夹具及 QA 文档修改前执行，之后没有改动其受测脚本或 Studio 文档，故未无故重跑。

真实 Mac 增量：

- `uv run --project apps/backend python /tmp/autoflow-am1-restart-install-real-20260924.py` exit 0；Shizuku `versionCode=1086` 安装完成标记在控制台重建后按原请求核实成功，标记清除，设备控制可恢复，本次自建实例与卷最终消失。详见[最终分支审查](2026-09-24-final-branch-review.md)。
- `uv run --project apps/backend python /tmp/autoflow-am3-bulk-failure-cancel-real-20260924.py` exit 0；两台停机批次先 `[succeeded,failed]`，对冲突项 `retryFailed` 后 `[succeeded,succeeded]`，容量等待取消为 `cancelled`。生产运行时只读核实本轮三台删除实例均为 `missing`。详见[批次验收](2026-09-24-bulk-failure-cancel.md)。
- 早前同分支真实五台 ready、20 次认证快照、双预览、固定摘要网络拉取、17,868,800 字节文件流备份恢复、备份/恢复发布点硬中断和高级日志仅元数据验收，分别保留在本目录对应 QA 记录；不将这些单链推断为十台或完整故障矩阵通过。

明确 `blocked`：本机 Lima 可用内存 7921 MiB，十实例最低配置加安全预留需 8192 MiB；缺专用候选 GApps 镜像、账号及商店下载条件。仍 `partial/not_run`：真实断网、进程级控制硬中断、运行时瞬时失败及未知结果重试、磁盘不足、归档传输/解包中断、指定桌面窗口/精确 200% 和前台交互指标。完整逐项状态见[24 项矩阵](2026-09-23-acceptance-matrix.md)。
