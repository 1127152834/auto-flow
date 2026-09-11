# 浏览器管理最终定向复审

- 日期：2026-09-12；状态：confirmed。
- 修复基线：`dd86e7260e9a36eac8d174ef8a52ada450216efd`；修复 HEAD：`3df560943d8fb2d2855327c98afb48e5b7d7a9b1`。
- 范围：`final-review.md` 的 I1/I2/M1/M2/M3 与 `final-rereview.diff` 的 13 文件修复；按 `re-review-prompt.md` 定向复核，没有重启整分支审查、派子代理或重复全量测试。修复包因输出限制分段完整读取。
- 已读取 `final-fix-brief.md`、`final-fix-report.md`、`docs/migration/browser-management-validation.md` 最终复验段，以及修复直接涉及的现有生命周期、认证、worker 清理和组件状态路径。

## 各条发现的结论

### I1：常驻 SSE 阻塞正常退出 —— ADDRESSED

- `apps/backend/src/autoflow/__main__.py:59` 将 Uvicorn 连接排空限制为 1 秒，解决原来在 lifespan shutdown 之前无限等待 SSE 的根因；`:65` 增加隐藏的 host HTTP 退出入口，设置同一 `server.should_exit`。父进程监视仍使用相同状态，原信号路径继续由 Uvicorn 处理。
- `apps/backend/src/autoflow/bootstrap/app.py:177` 对全部 `/internal/` 请求使用现有 host token 校验并拒绝任何 Origin；该接口没有经过 renderer instance token 放行，也没有增加 renderer 权限。`apps/backend/tests/integration/test_sidecar_shutdown.py:60` 验证无 token、仅 renderer token、带 Origin 的 host token 全部 401；`:64` 验证接口不在 OpenAPI 中。应用监听仍受 `__main__.py:29` 的 loopback 限制。
- `apps/desktop/src/main/sidecar/supervisor.ts:156` 在清空对外 host 能力前捕获本轮 host 凭据；`:176` 先注册 exit listener 再发请求，避免正常快速退出漏收事件；`:178` 控制请求限 1 秒；`:175` 总预算为 10 秒。Windows HTTP 响应丢失后不提前发强制 SIGTERM，最终仍走 `taskkill /t /f`；POSIX 请求失败可退到原 SIGTERM。启动尚未 ready 的取消路径仍保留原信号行为。
- 预算与真实清理顺序一致：`apps/backend/src/autoflow/infrastructure/process/kernel_worker.py:262` 先 cancel 并 gather RPC tasks，因此多个 RPC 的 3 秒 TERM 等待并行进行；随后取消安装锁限制的唯一下载 worker。`:553` 的 TERM 等待使用默认 3 秒（`:38`），超时 kill 后等待回收。10 秒包含请求、1 秒排空、两阶段各 3 秒及调度余量；没有将其描述为异常磁盘或 OS 条件下无条件成功的保证。
- `apps/backend/tests/integration/test_sidecar_shutdown.py:20` 的 4 场景确实启动真实源码 sidecar，并保持收到 snapshot 的 SSE 打开直到退出。活动下载场景先等 wrapper 写出 PID，再验证退出码、PID 消失、staging 删除及数据库 cancelled；不是只测试 manager 的假退出。
- `apps/desktop/src/main/sidecar/supervisor.test.ts:123` 覆盖 darwin/win32 控制请求、9 秒不强杀、10 秒兜底及 Windows response-lost；`:166` 覆盖正常 exit 立即完成。`scripts/smoke-browser-management.mjs:175` 与 `scripts/smoke-browser-management-desktop.mjs:117` 的新增 smoke 确实覆盖 SSE 打开、code 0、端口关闭，桌面走真实 quit IPC / before-quit / settings.shutdown。
- 本复审另做了下文唯一聚焦实测：2 个活动 RPC worker + 1 个下载 worker（全部忽略 TERM）+ SSE，同时退出实际耗时 **7.382 秒**，sidecar code 0，3 个 PID 全部消失、RPC cache 与 staging 全清、下载任务 cancelled。这直接核实了 Uvicorn 取消请求与 manager RPC gather 交互，不会在该组合下把并行清理退化为无限等待或超出 10 秒宿主预算。
- 结论置信度：高（macOS arm64 源码与跨层控制流）；Windows 实机结果未知，平台模拟不等于 Windows 运行通过。

### I2：目录或筛选隐藏活动任务取消入口 —— ADDRESSED

- `apps/desktop/src/renderer/domains/kernels/components/KernelManagerDialog.tsx:110` 继续从完整 operations 计算 busy；`:111` 从同一集合找出未被当前可见卡片覆盖的活动任务，判断同时比较 edition、requestedVersion 和 releaseChannel，不依赖 catalog 仍包含目标版本。
- `KernelManagerDialog.tsx:217` 在可见卡片集合外渲染这些活动任务并复用 `KernelOperationStatus`，版本降级为 local-only（channel=null）时也不会误以为已有对应活动卡片。取消复用 `cancelDownload`，未添加平行任务系统或改变 API。
- `apps/desktop/src/renderer/domains/kernels/components/KernelManagerDialog.test.tsx:327` 两组用例确实从下载开始，再刷新成 empty/local-only catalog，轮换全部四种筛选，验证可取消、只发送一次 cancel、cancelling 时不能关闭、终态 SSE 后能关闭。原卡片与补充区域共同保证取消可达；无需强制所有任务永远显示在同一区域。
- 结论置信度：高。

### M1：真实名称冲突未关联名称字段 —— ADDRESSED

- `apps/backend/src/autoflow/adapters/http/errors.py:162` 为真实 `ProfileNameConflict` 返回稳定 409 / `PROFILE_NAME_CONFLICT` 及 `details.fields.name`，并从通用空 details 映射中移除该异常。
- `apps/backend/tests/contract/test_profiles.py:76` 实际创建同名与复制同名两条 HTTP 路径，验证两者 fields.name 一致。前端 `ProfileActionDialog.tsx:60` 现有字段映射因此可达；`:38` 聚焦名称控件；`:73` 继续经 FormField 建立错误关联。
- `apps/desktop/src/renderer/domains/profiles/components/ProfileActionDialog.test.tsx:33` 使用与后端一致的 envelope，并断言 aria-invalid、accessible description、焦点、输入保留和弹窗未关闭。修复没有手工改生成类型，schema 无需改变。
- 结论置信度：高。

### M2：离线文案错误断言操作尚未执行 —— ADDRESSED

- `apps/desktop/src/renderer/domains/profiles/components/ProfileActionDialog.tsx:71` 改成“操作结果可能未确认。恢复连接后请核对列表再重试”，不再用连接状态推断服务端未提交。
- `ProfileActionDialog.tsx:43` 的请求仍只由显式提交触发；新增 effect 只负责字段聚焦，没有写请求重放。
- `apps/desktop/src/renderer/domains/profiles/components/ProfileActionDialog.test.tsx:73` 在 fixture 标记 committed 后抛出响应丢失，验证离线提示、禁用写入、恢复后的输入保留、fetch 次数仍为 1，以及用户手动再次提交才变成 2。该用例是响应丢失模拟，不冒充真实数据库提交后的网络故障注入。
- 结论置信度：高。

### M3：worker smoke 文档过度声称验证进度 —— ADDRESSED

- `docs/migration/browser-management-validation.md:17` 现在明确 smoke 验证动态入口及完成结果、不断言进度；与 `scripts/smoke-browser-management.mjs:90` 只检查末条 completed、resolvedVersion、executableRelativePath 的代码一致。
- 文档 `:64` 至 `:78` 区分最终修复后的检查、既有提示与未验证平台；没有把本轮 fixture、平台模拟或历史公开下载冒充真实商业 License 成功。
- 结论置信度：高。

## 修复 diff 里的新破坏

- **Critical：无。Important：无。**
- **Minor 观察（非阻塞）：** `apps/backend/src/autoflow/__main__.py:61` 的有界排空会产生 Uvicorn timeout / ASGI CancelledError 日志。新增聚焦组合实测也看到了这些日志；尚未完成的两个 License RPC HTTP 请求在退出期间各收到 500，随后进程 code 0 退出、worker 与临时数据清理完成。这发生在明确请求关闭后的取消阶段，不是已验证的正常运行期失败、数据损坏或 worker 泄漏。实现报告和 `docs/migration/browser-management-validation.md:76` 已披露 ERROR 输出，不能再称输出完全干净；不要求因此开启新修复循环。

## 实际检查与证据边界

- 逐项对照实现报告中的测试名称、参数、断言和 diff。报告记录 backend **315 passed**、frontend **45 files / 265 tests passed**、scripts **9 passed**，以及 ruff/mypy/typecheck/lint/OpenAPI/build、源码/frozen 与开发/packaged Electron smoke。它们是实现者的已报告运行结果，本复审没有重复执行或冒称自己再次跑过。
- 唯一新增实测以 `uv run --directory apps/backend python -` 执行临时内联脚本，全部数据位于 `TemporaryDirectory(prefix='autoflow-rereview-rpc-shutdown-')`。仅在临时 PYTHONPATH 提供 cloakbrowser wrapper：`ensure_binary` 与 `validate_license` 进入阻塞函数，设置 SIGTERM ignore，在各自 cache 写 partial 与 worker.pid 后 sleep。通过真实 HTTP 启动 1 个 public download 与 2 个并发 License 验证请求，**先断言存在 3 个 PID 文件**再保持 SSE snapshot 连接并请求 host shutdown。因此不存在把等待请求误计成已启动 RPC worker 的情况。
- 该脚本没有网络下载，License 使用仅供本地阻塞夹具的假值，验证函数未返回，不触发凭据写入。进程退出后以 PID liveness、目录检查和真实 SQLAlchemy repository 读取验证清理。脚本 exit 0，临时目录自动删除；输出为：

```json
{"result":"PASS","exitCode":0,"elapsedSeconds":7.382,"workerCount":3,"workersReaped":true,"stagingRemoved":true,"rpcCachesRemoved":true,"operationState":"cancelled","pendingRpcHttpResults":[500,500]}
{"boundedDrainErrorLogged":true,"cancelledErrorLogged":true}
```

- 复审没有修改业务源码、索引、HEAD、分支、automation 或协调者未提交文档；唯一持久写入为本报告。没有重新运行完整测试、公开下载、真实 License、Windows/macOS Intel 或发行安装器验证。

## 范围外的观察

- 无新增范围外问题。既有 pytest 上游弃用、第三方 zod 提示和未签名目录包限制继续按实现报告保留，不重复列为修复 diff 引入的问题。

## 结论

**本轮修复：PASS。I1/I2/M1/M2/M3 全部 ADDRESSED，无新的 Critical/Important 破坏。置信度：高。**

本结论允许结束这轮定向修复复审；不把 Windows x64、macOS Intel 新运行证据、真实商业 License 或签名发行安装器改写为已验收。
