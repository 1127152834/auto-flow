# 浏览器管理最终修复报告

- 日期：2026-09-12。
- 状态：confirmed，实施和本机验证完成；等待协调者安排的一次定向独立复审。
- 开始 HEAD：`dd86e7260e9a36eac8d174ef8a52ada450216efd`。
- 修复 commit：`3df560943d8fb2d2855327c98afb48e5b7d7a9b1` — `fix(browser): preserve shutdown cleanup and download cancellation`。
- 范围：按 `final-fix-brief.md` 与完整 `final-review.md` 修复 I1/I2/M1/M2/M3，没有新增产品功能、替换技术栈、派子代理或自行复审。
- 置信度：高（本机源码/frozen/Electron 与新增组合回归）；Windows/macOS Intel 实际运行结果仍未知。

## 逐项处理

### I1：SSE、host 与 worker 退出预算

在 `__main__.py` 装配 host-only `POST /internal/lifecycle/shutdown`，幂等地置 `server.should_exit = True`，返回 `{stopping: true}`。复用现有 `/internal/` middleware：只接受 host token，拒绝无 token、renderer instance token，以及带 Origin 的请求；入口仍只绑定 `127.0.0.1`；内部接口 `include_in_schema=False`，未扩展 renderer preload 或生成 DTO。

Electron supervisor 优先调用该内部控制接口，使用 1 秒请求预算；Uvicorn 设置 1 秒 `timeout_graceful_shutdown`，确保常驻 SSE 不能无限推迟 lifespan shutdown。现有 manager 的真实顺序是：取消 RPC tasks 并 gather（RPC 并行清理，每个 TERM 等待最多 3 秒），随后取消受安装锁限制的唯一下载 worker（再最多 3 秒 TERM 等待）。host 的 10 秒上限覆盖 1 秒控制请求、1 秒连接排空、3+3 秒 worker 清理和 2 秒调度/回收余量；正常无 worker 不等待满预算。磁盘或 OS 异常仍由总上限的强杀兜底，不承诺任意环境下无条件正常退出。

POSIX 请求失败后仍可发送 SIGTERM 进入相同有界后端清理；Windows 的 SIGTERM 会强制终止进程，因此已发出 HTTP 后即使响应丢失也保留协作预算，到总上限再 taskkill 进程树。未 ready 的启动取消保留原信号终止路径。

新增真实进程矩阵 `test_sidecar_shutdown.py`（本机 4 项）：host HTTP / SIGTERM × 无 worker / 活动 worker。测试只替换外部 cloakbrowser wrapper，用本地夹具写入 partial 与 PID 并忽略 TERM；真实 `python -m autoflow`、HTTP/SSE、kernel worker 子进程、manager、lifespan 与数据库均运行。保持已收到 snapshot 的 SSE client 打开直到 sidecar 退出，无 worker 限 3 秒、活动 worker 限 8 秒；验证 host 路径 code 0、POSIX signal 路径 -SIGTERM、worker PID 消失、operation 为 cancelled、staging 已删除。Windows 跳过 POSIX signal 两项，其 host 两项待 Windows runner 执行。

Supervisor 平台模拟回归核验 darwin/win32 控制请求只携带 host token、9 秒仍不提前强杀、10 秒触发对应兜底，Windows 响应丢失仍保留预算；另测正常 exit 立即完成，无信号杀进程。模拟不能替代 Windows 实机证据。

source/frozen 与开发/packaged Electron smoke 均增加真实 SSE 保持打开的正常退出断言。Electron 使用 `window.autoflow.quitApplication()`，走 `before-quit → settings.shutdown → supervisor`，8 秒内宿主 code 0 退出且 sidecar health 端口不可连接。

### I2：目录和筛选不能隐藏取消入口

`KernelManagerDialog` 从现有 operations 中识别未出现在当前可见 release 卡片的活动任务，在独立“活动内核下载”区复用 `KernelOperationStatus`。现有卡片中的活动任务保持原位置；被筛选或 catalog 降级移出卡片的任务仍显示版本/edition/channel、进度与取消入口。没有构造伪 catalog release，也没有新增任务系统。

新增两项跨组件回归：启动尚未安装的 licensed release 下载后，刷新分别得到 empty catalog 或 local-only catalog；轮换“全部版本/公开版/正式版/已安装”筛选，始终存在可操作取消按钮；cancel API 只发一次，取消期间禁止关闭，终态事件到达后能关闭。

### M1：实际名称冲突字段关联

后端共享 ProfileNameConflict handler 保持稳定 `PROFILE_NAME_CONFLICT`/409，补 `details.fields.name`。契约测试实际创建同名配置与复制同名配置，检查字段 payload。前端沿用既有 ApiClientError fields 映射与 FormField 错误关联，并在错误后聚焦名称输入。

前端测试使用与真实 HTTP 一致的 envelope，断言名称保留、aria-invalid、accessible description 和焦点。error envelope 的 OpenAPI schema 没变，未手改任何生成类型，`openapi:check` 通过。

### M2：断线不推断上次请求未执行

将“当前操作尚未执行”改为“本地服务离线，操作结果可能未确认。恢复连接后请核对列表再重试。”新增响应丢失模拟：server fixture 已标记 committed 后抛网络错误，切 offline/online 保留输入且没有重放，用户再次手动点击才产生第二次写请求。

### M3 与既有非阻塞提示

修正文档：worker smoke 断言动态入口及完成结果（completed/resolvedVersion/executableRelativePath），不再声称此 smoke 断言进度消息。没有因此扩大 worker smoke 的进度需求。

pytest 仍有 2 条 Starlette/httpx 与 anyio 上游弃用；frontend build 仍有第三方 zod 注释提示。未更新整套依赖或广泛过滤告警。

**新增退出日志现象如实记录：** 强制截断长 SSE 排空时 Uvicorn 输出 `Cancel ... running task(s), timeout graceful shutdown exceeded` 与 ASGI `CancelledError` ERROR 日志；随后 host HTTP 路径正常 code 0 退出，真实活动 worker 清理断言通过。输出不完全干净，未隐藏或过滤。PyInstaller 还保留可选数据库 pysqlite2/MySQLdb hidden-import 提示；目录包缺默认应用图标配置且无有效 Developer ID，未签名，不称为发行安装器。

## 验证命令与实际结果

以下均在本次修复代码上运行，lint 与 build 没有并行。最后补 Windows response-lost guard 后重新运行 frontend typecheck/lint/full tests/build/package 及两种 Electron smoke。

| 命令 | 实际输出/结果 |
| --- | --- |
| `uv run --directory apps/backend pytest tests/integration/test_sidecar_shutdown.py tests/contract/test_profiles.py -q` | 12 passed, 2 warnings（16.99s） |
| `npm --workspace @autoflow/desktop test -- src/main/sidecar/supervisor.test.ts` | 8 passed（最终 Windows response-lost 变体由全量再次验证） |
| `npm --workspace @autoflow/desktop test -- src/renderer/domains/profiles/components/ProfileActionDialog.test.tsx` | 5 passed |
| 首轮针对 ManagerDialog/ProfileActionDialog/Supervisor 的组合测试 | 3 files / 25 passed；后续新增 supervisor 3 项纳入最终全量 |
| `uv run --directory apps/backend ruff check src tests` | All checks passed |
| `uv run --directory apps/backend mypy src` | Success: no issues found in 106 source files |
| `uv run --directory apps/backend pytest -q` | **315 passed, 2 warnings in 31.58s** |
| `npm test`（最终一次） | **45 files / 265 tests passed**, 10.50s |
| `npm run typecheck` | passed |
| `npm run lint` | passed |
| `npm run openapi:check` | passed，生成类型没有 diff |
| `npm run test:scripts` | **9 passed** |
| `npm run build`（最终一次） | passed，main/preload/renderer 构建完成；保留 zod 提示 |
| `npm run backend:build` | PyInstaller 6.22.2 / Python 3.11.13 / macOS arm64，Build complete |
| `node scripts/smoke-browser-management.mjs` | browser management smoke passed (source, darwin/arm64)，含 SSE→host HTTP 正常退出 |
| `node scripts/smoke-browser-management.mjs --executable apps/backend/dist/autoflow-backend/autoflow-backend` | browser management smoke passed (packaged, darwin/arm64)，即 frozen backend；含 SSE 正常退出 |
| `node scripts/smoke-browser-management-desktop.mjs`（最终一次） | browser management desktop smoke passed (development, darwin/arm64) |
| `npm run package:dir`（最终一次） | electron-builder 26.15.3，目录包构建成功，未签名 |
| `node scripts/smoke-sidecar.mjs --executable apps/desktop/dist/mac-arm64/AutoFlow.app/Contents/Resources/backend/autoflow-backend` | exit 0，包内 sidecar health/lifecycle 通过 |
| `node scripts/smoke-browser-management.mjs --executable apps/desktop/dist/mac-arm64/AutoFlow.app/Contents/Resources/backend/autoflow-backend` | browser management smoke passed (packaged, darwin/arm64)，包内资源，含 SSE 正常退出 |
| `node scripts/smoke-browser-management-desktop.mjs --executable apps/desktop/dist/mac-arm64/AutoFlow.app/Contents/MacOS/AutoFlow` | browser management desktop smoke passed (packaged, darwin/arm64)，包含真实 before-quit→sidecar 退出 |
| `git diff --check -- <本次13个文件>` | passed |

执行中修正了新测试的 import 排序，以及 Input 组件不支持 ref 类型导致的首次 typecheck 失败（改为本地 form ref 聚焦，没有改共享 Input）；修复后上述检查通过。包内 sidecar 首次命令多写了一层目录，报 executable not found；核对实际 extraResources 布局后使用表内路径通过。这些不是遗留失败。

## 变更路径

本次精准提交仅以下 13 文件，372 insertions / 17 deletions：

- `apps/backend/src/autoflow/__main__.py`
- `apps/backend/src/autoflow/adapters/http/errors.py`
- `apps/backend/tests/contract/test_profiles.py`
- `apps/backend/tests/integration/test_sidecar_shutdown.py`
- `apps/desktop/src/main/sidecar/supervisor.ts`
- `apps/desktop/src/main/sidecar/supervisor.test.ts`
- `apps/desktop/src/renderer/domains/kernels/components/KernelManagerDialog.tsx`
- `apps/desktop/src/renderer/domains/kernels/components/KernelManagerDialog.test.tsx`
- `apps/desktop/src/renderer/domains/profiles/components/ProfileActionDialog.tsx`
- `apps/desktop/src/renderer/domains/profiles/components/ProfileActionDialog.test.tsx`
- `scripts/smoke-browser-management.mjs`
- `scripts/smoke-browser-management-desktop.mjs`
- `docs/migration/browser-management-validation.md`

保留了 automation 目录/文档、协调者 `.ai/plans`、`.ai/sessions` 与 `browser-management-decisions.md` 的未提交修改，没有暂存或覆盖。这份报告位于 ignored 工作目录，未强行提交，交协调者统一归档。

## 未验证与交接

- 没有重新下载真实公开内核；此前公开下载/取消证据未更改。
- Windows x64、macOS Intel 尚无本轮运行证据；Windows 测试代码/模拟和可用 CI 步骤不能代替通过结果。
- 没有真实商业 License，License 校验/授权下载/安装仍未验证。
- 完成当前修复与本机回归，交 root 一次定向独立复审；本报告不冒充独立 PASS。
