# 内核管理 API 与目录能力

- 日期：2026-09-12
- 状态：confirmed
- 来源：已批准的浏览器管理计划任务 6、`task-6-brief.md`，以及本次本地测试验证。

## 已完成

- 内核 catalog、installed、check-update、License、默认项 CAS、下载/取消/任务快照和删除 HTTP 契约已装配；OpenAPI 已从运行后端重新生成。
- 默认内核使用 `kernel_settings.revision` compare-and-swap；默认行使用 SQLite `INSERT ... ON CONFLICT DO NOTHING` 原子初始化，多个 sidecar 首次启动不会因主键竞争失败。设默认与删除共用 `.install.lock`，不会和安装并发。删除先将安装目录原子移动到 `.trash`，数据库失败立即恢复；启动只恢复通过当前平台 executable 校验的完整遗留安装，部分 purge 残留继续隔离在 `.trash`。
- License 退出和授权下载使用同一 dataDir 下的跨进程 `.license.lock`。授权下载从读取凭据到 queued operation 完成登记一直持锁；退出在同一锁内检查活动授权任务并删除凭据，保证退出成功后不会再有携带旧 key 的任务启动。锁顺序只有 License 门禁到安装门禁，不存在反向嵌套。
- Profile 生产装配使用 `CloakBrowserCatalogProvider` 的真实本机扫描作为 `InstalledKernelLookup`，不再使用默认拒绝实现。
- catalog 与 License wrapper 调用通过父进程监管的一次性 worker RPC；每次使用独立 `.rpc/<id>` 缓存和 owner lock，并具备超时、调用取消、shutdown 终止/强杀/wait 及清理。`.rpc` 与安装 `.staging` 分离，安装恢复不会误处理一次性缓存。
- Electron `revealKernel(ref)` 只接收 edition/version，经 host token 调 sidecar 解析真实安装路径，再验证 sender/main frame、loopback sidecar、实际 dataDir 下的 kernels realpath 和目录身份后调用系统 reveal。renderer 不能传路径；既有 `copyProxyCredentials` 边界保留。

## 验证

- `uv run --directory apps/backend pytest -q`：230 passed。
- `uv run --directory apps/backend ruff check .`：通过。
- `uv run --directory apps/backend mypy src`：通过。
- `npm test -- --run`：55 passed。
- `npm run lint`、`npm run typecheck`、`npm run build`：通过。
- `npm run openapi:check`：通过；内核公开路由已生成，host-only resolve 路由未进入 OpenAPI，License key 标记 write-only。
- `npm run test:scripts`：7 passed。
- 确定性回归覆盖：两个独立 `KernelService`/安装存储共享 dataDir 的 License 读取/登记竞态；退出先完成后的 `LICENSE_INVALID`；缺 executable 的部分 trash 保持隔离；两个真实 Session 同时首次初始化默认行。

## 后续

- 浏览器管理任务 7 消费生成类型，实现 renderer API、查询缓存和 SSE 恢复。
