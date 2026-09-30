# 安卓管理当前分支完整自动化门槛

- 日期：2026-09-23；状态：`confirmed`（下列命令与输出）；AM1–AM4 整体验收仍为 `partial`。
- 基线：隔离分支 `codex/android-management-complete`，代码提交 `4fc50eac`、`c3f9d94e`、`0c100c76`；镜像边界增量 `a5bf3073` 随后单独重跑后端全量。测试时另有 Android QA 文档未提交；三份既有 Studio 文档修改未纳入 Android 提交。
- 平台：Apple Silicon macOS；前端门槛以隔离的 Node `22.23.2` 运行，默认 shell 的 Node 26 不作为规格运行时证据。

| 命令 | 实际输出摘要 |
| --- | --- |
| `uv run --project apps/backend pytest apps/backend/tests -q` | 含 `a5bf3073` 的最新工作树 exit 0；`3990 passed, 26 skipped, 2 warnings in 831.70s`。此前未含该提交的工作树亦 exit 0；`3986 passed, 26 skipped, 2 warnings in 1362.43s`。警告为 Starlette 的 anyio 别名弃用及损坏 APK 测试的重复 ZIP 项。 |
| `npm exec --offline --yes --package=node@22.23.2 -c 'npm test -w @autoflow/desktop -- --maxWorkers=1 --testTimeout=15000'` | exit 0；`424 Test Files passed, 5622 Tests passed`，`818.97s`。 |
| Node 22 下 `npm run typecheck`、`npm run lint`、`npm run openapi:check`、`npm run build` | 四项均 exit 0；构建 `11751 modules transformed`、`built in 41.25s`。构建的 Rollup 注释/拆包警告不影响退出码。 |
| Node 22 下 `npm run test:structure`、`npm run test:scripts` | exit 0；分别 `4/4`、`95/95`。脚本测试会重写 Studio 清单，运行前保存、完成后逐字节恢复三份既有修改，并恢复额外生成的 `capabilities.json`；最终三份 SHA-256 与前值一致。 |
| `uv run --project apps/backend ruff check apps/backend/src apps/backend/tests`、`uv run --project apps/backend python -m compileall -q apps/backend/src` | 均 exit 0；Ruff `All checks passed!`。 |
| `uv run --project apps/backend pytest apps/backend/tests/integration/test_migration_heads.py -q`；在后端目录执行 `uv run alembic -c src/autoflow/infrastructure/database/alembic.ini heads` | `2 passed in 1.54s`；唯一 head `am01_management_operations`。 |
| `git diff --check` | exit 0。 |

第一次并行执行 Node 22 前端全量和后端全量时，两个无关页面测试超过原 5 秒超时；该轮被中止，不能算全量通过。后端独立完成后，前端用上述单 worker/15 秒配置独立重跑，`5622/5622` 通过。第一次后端全量曾在冻结手势差分夹具的 MediaPipe 全局初始化处挂起；单项复现后仅在差分夹具导入期间隔离该初始化，单项 `2 passed in 3.21s`，其后完整后端重跑才得出表中通过结果。

上述自动化不替代仍缺的真实断网、专用 GApps 账号/下载、5/10 台规模、归档传输/解包中断、磁盘不足及高级日志验收。当前逐项状态见[24 项验收矩阵](2026-09-23-acceptance-matrix.md)。
