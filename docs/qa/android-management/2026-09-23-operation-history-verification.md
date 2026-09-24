# AM1 管理操作历史增量验收

- 日期：2026-09-23；状态：`confirmed`（本增量），T06 与 AM1 整体验收仍为 `partial`。
- 来源：设计规格 5.2、隔离分支 `codex/android-management-complete@52e1f6a6` 加本增量；复用已有持久操作仓储并修正公开查询契约。`GET /management/operations` 现明确接受 `deviceId`，`GET /management/devices` 接受 `profileId`；OpenAPI 生成类型已同步。数据库表与迁移没有变化，唯一 head 仍为 `am01_management_operations`。

管理首页原来只显示设备的最新操作，历史分页虽有后端契约却没有用户入口。现在每台设备可打开独立操作历史，按设备与后端游标分页，显示动作、状态、阶段、消息和提交时间；仅对服务端标记 `needs_verification` 且允许 `verify` 的条目提供核实入口。请求进行中或失败时旧历史只读，跨设备条目使整页失败关闭。核实弹窗使用原操作 `requestId`，不会重放旧写操作；同时修正了弹窗标题为空、键盘焦点难以到达及关闭后焦点丢失的问题。

独立只读审查发现一个 Critical：原后端参数名为 `device_id`，前端按规格发送 `deviceId` 被忽略，同工作区其他设备的操作可出现在当前设备面板，并可能被误点核实。RED 合约测试证实设备过滤失效，修复后同设备过滤和前端 `targetId` 一致性保护均转绿。审查还确认原后端恰好满页时会错误提供下一页，且仓储允许用其他设备/工作区操作作为分页边界；现以多取一项和同范围游标校验修复。

| RED 场景 | 修复前实际输出 | GREEN |
| --- | --- | --- |
| 历史入口、设备过滤和原请求核实 | `/tmp/android-am1-operation-history-red.log`：`2 failed, 9 passed`，找不到操作历史入口 | `ManagementOverview.test.tsx` 通过，按 `deviceId` 查询并转交 `operationId/requestId`。 |
| 后端游标翻页 | 同上，找不到入口 | 第二页使用 `cursor=operation-1`，返回第一页重新显示原行。 |
| 断线后旧回执只读 | `/tmp/android-am1-operation-history-offline-red.log`：`1 failed, 11 passed`，缓存核实按钮仍可点击 | 查询错误时显示告警、保留旧行并禁用核实及翻页。 |
| 页面核实弹窗和原请求编号 | `/tmp/android-am1-history-dialog-red.log`：`1 failed, 29 passed`，弹窗缺少“核实状态”标题 | 点击历史条目后标题可见，确认请求为 `POST /management/operations/operation-1/verify`，body 使用原 `requestId`。 |
| 设备过滤和末页游标 | `/tmp/android-am1-history-cursor-red.log`：`3 failed`，`deviceId` 被忽略、满 50 条仍给 cursor、跨设备/工作区游标被接收；先修别名后 `/tmp/android-am1-history-cursor-red2.log` 剩 `2 failed` | HTTP 合约覆盖 50/51/200/201 条，只有真实存在下一项才返回 cursor；游标必须属于相同设备和工作区。 |
| 模板公开筛选参数 | `/tmp/android-am1-profile-alias-red.log`：`1 failed`，`profileId` 被忽略 | `profileId` 过滤返回正确空页；生成 OpenAPI query 类型同步。 |
| 键盘进入和退出历史 | `/tmp/android-am1-history-focus-red.log`：`1 failed`，无可访问区域/展开关系和焦点迁移 | 触发按钮关联面板，展开后聚焦标题，关闭后焦点返回触发按钮。 |
| 错设备回执失败关闭 | `/tmp/android-am1-history-target-red.log`：`1 failed`，错设备核实按钮可见 | 返回条目 `targetId` 与当前设备不一致时整页隐藏并告警。 |
| 旧回执刷新期间只读 | `/tmp/android-am1-history-fetch-red.log`：`1 failed, 14 passed`，请求进行中按钮仍可用 | `isFetching` 时核实和翻页禁用，请求成功后恢复。 |

最终定向执行 `uv run pytest tests/contract/test_android_management_devices.py tests/contract/test_android_management_operations.py tests/integration/test_android_management_operations.py -q`：`31 passed, 1 warning`；前端 `npm --workspace @autoflow/desktop test -- src/renderer/domains/android/tests/AndroidPage.test.tsx src/renderer/domains/android/tests/ManagementOverview.test.tsx`：`2 files, 45 passed`。

| 门槛命令（仓库根目录；后端命令先 `cd apps/backend`） | 实际输出摘要 |
| --- | --- |
| `uv run pytest -q` | exit 0；`3969 passed, 26 skipped, 2 warnings in 1257.14s`。warning 是 Starlette/AnyIO 废弃别名及故意重复 APK Manifest 的 ZIP 夹具。 |
| `uv run ruff check src tests`、`uv run python -m compileall -q src tests` | 均 exit 0；Ruff `All checks passed!`，compileall 无错误输出。 |
| `uv run alembic -c src/autoflow/infrastructure/database/alembic.ini heads` | exit 0；`am01_management_operations (head)`，唯一 head；未修改旧迁移。 |
| `npm run openapi:generate`、`npm run openapi:check` | 均 exit 0；生成类型将 `device_id/profile_id` 改为公开的 `deviceId/profileId`，check 无漂移。 |
| `npm run test:scripts`、`npm run test:structure` | 均 exit 0；分别 `95 passed`、`4 passed`。受保护 Studio 文档恢复并逐份核验 SHA-256 不变。 |
| `npm run typecheck`、`npm run lint`、`npm run build` | 均 exit 0；TypeScript/ESLint 无错误，Electron/Vite `built in 1m 55s`。一次与构建并行的 lint 曾因构建临时配置文件移除而 ENOENT；构建结束后单独重跑通过。 |
| `npm --workspace @autoflow/desktop test -- --maxWorkers=1 --testTimeout=15000` | exit 0；`424 passed (424)` 文件、`5619 passed (5619)` 测试，耗时 `1095.22s`。两轮默认 4 worker 重跑在本机高负载下发生跨模块 5 秒等待超时，主动中止并改为单 worker/15 秒；未跳过任何文件或断言。 |
| `git diff --check` | exit 0；无空白错误。 |

未完成：长名称、200% 缩放、真实断线、保留数据恢复及完整 HTTP/真实设备 UI 链尚无同场景验收；本增量的 jsdom 焦点/断线模拟不能替代真实 Mac 窗口与网络失联。完整 AM1–AM4 目标仍为 `partial`。
