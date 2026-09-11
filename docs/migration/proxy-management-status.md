# ProxyPanel 代理模块实施状态与合并指引

- 日期：2026-09-12
- 状态：confirmed；代理模块已从 `codex/proxy-management@0ad2fd2` 选择性接入浏览器主线并通过本机全量验收，真实 Provider 与浏览器启动集成仍待验证
- 批准来源：用户“好的 开始实施吧，不要和浏览器管理冲突哦，另一个 agent 在开发浏览器管理模块”
- 规格：[设计方案](../superpowers/specs/2026-09-12-proxy-management-design.md)
- 计划：[实施计划](../superpowers/plans/2026-09-12-proxy-management-implementation.md)

## 1. 工作区和文件所有权

代理实现最初位于分支 `codex/proxy-management`，工作区为 `../autoflow-proxy-management`，从 `2707006` 创建。2026-09-12 已从稳定来源 `0ad2fd2` 选择性接入 `autoflow` 浏览器主线检查点；没有替换 `App.tsx`，也没有改写 profiles/kernels 领域代码。

独占文件为后端 `domain/proxies`、`application/proxies`、`providers/proxy`、独立代理 HTTP / ORM / migration 文件，以及前端 `renderer/domains/proxies`。公共装配修改集中交付，由浏览器主线串行整合。共享 `.ai`、结构文档也应按段落合并，不能整文件覆盖主线的新记录。

## 2. 已实现的内部流程

| 范围 | 本地行为 | 验收边界 |
| --- | --- | --- |
| 连接 | 名称、首次 Key 录入、验证、替换、断开；SQLite 仅保存 secret ref | 假 Provider + 临时真实 SQLite 验证；未使用真实账号 |
| 同步与投影 | 完整/部分/未知同步、旧数据保留、本地别名/启用、分页筛选、引用查询 | 合成输入验证内部逻辑，不代表真实字段映射已完成 |
| 本地代理组 | 创建/修改/成员顺序、风险确认、引用保护、轮询选择用例 | 浏览器启动入口由另一个任务整合；当前没有对 renderer 暴露推进游标的 `/select` API |
| 健康 | 通过 HTTP/SOCKS5 代理请求固定 HTTPS 地址，记录出口 IP、耗时、检查时间和错误 | 隔离 transport 测试；没有真实代理实网验证 |
| 前端 | 连接卡片、摘要、表格、筛选/分页、详情 Drawer、本地设置、组编辑与确认、Toast、错误/未知/加载/空态、429 冷却 | 生成类型 + React 组件/交互测试；不在生产页面填入 mock 代理 |
| 凭据 | macOS/Windows 原生 Keyring 适配；受控复制请求只返回 copied；30 秒后按内容匹配清理剪贴板 | 原生适配选择与模拟后端测试；没有写入真实账号密钥 |
| 远程操作 | 位置、换 IP、轮换、白名单、用量、账户指标等尚不可用 | 控件禁用并说明；公开保留端点返回 `CAPABILITY_UNAVAILABLE`，不伪造成功 |

普通 HTTP 请求和响应模型不返回 API Key 或数据面密码。校验错误不回显提交内容。到期时间默认 `null`；页面不生成“即将到期”、预测地点延迟或丢包率。

## 3. 真实接入尚未完成的具体原因

官方 Developers 页面证明了固定 base URL、Bearer 认证和端点路径，但没有提供可用于冻结映射的实际列表响应。当前没有真实 API Key / 脱敏 live fixture。

因此 `ProxyPanelReadProvider.verify()` 只验证认证读取的 HTTP/JSON 结果；`list_proxies()` 读取后明确返回 `PROXYPANEL_SCHEMA_UNSUPPORTED`，保持本地数据不变。即使用户填入有效 Key，当前版本也不会凭猜测导入代理。UI 会区分“连接已保存”和“代理同步暂不可用”。这项限制不能描述为“ProxyPanel 已完整接入”。

后续只读核验需取得授权的实际列表/详情/分页样本，去除 API Key、用户名、密码和带认证 URL，确认字段语义后替换该明确拒绝分支，并加入 live fixture contract test。端点凭据的真实读取/保存、远程写入、用量和到期时间分别核验，不随列表接口一起自动启用。

当前所有合成样例仅用于测试内部事务、映射输入、错误和组件状态，不提高外部能力的 evidence 等级。

## 4. 浏览器主线串行整合结果

下列公共入口已按段落完成整合；第 8 项全局导航和其后的浏览器启动解析仍由后续浏览器任务完成。

1. **系统凭据和依赖**：复用 `domain/credentials.py` / `infrastructure/credentials/system.py`；后端依赖包含 `keyring>=25,<26`、`httpx[socks]>=0.28,<1`。合并 pyproject 后重新锁定，避免覆盖主线的新依赖。
2. **SQLite 外键**：`create_session_factory` 的 engine connect 回调开启 `PRAGMA foreign_keys=ON`。两个物理连接和非法外键插入已纳入测试。不要只依赖 Python 层检查。
3. **代理迁移**：`0002_proxy_management` 当前父版本为 `0001_browser_resources`；保持唯一 Alembic head。如果主线已经增加迁移，应串行调整父链后验证新库升级和已有库升级，不创建并行 head。新增表扩展现有 `ProxyRow` / `ProxyPoolRow`，不替换其 ID。
4. **后端启动**：调用 `configure_proxy_management(app, paths.database)`，退出时调用其返回的关闭函数。与主线自己的 profiles/kernel lifespan 合并，不能覆盖其初始化或清理。
5. **认证**：`Settings.host_token` 从 `AUTOFLOW_HOST_TOKEN` 获取；`/internal/*` 仅接受独立 host token，并拒绝带 Origin 的浏览器请求。普通 renderer token 不能取密。CORS 允许普通 `Idempotency-Key`，不开放 host token header。
6. **桌面主进程**：`SidecarSupervisor` 每次启动生成独立 host token，仅向 child 环境传递；`getStatus()` 不包含它，`getHostStatus()` 只供 main 的复制 handler 使用；停止后失效。
7. **受控复制**：主进程注册 `autoflow:copy-proxy-credentials`，preload 暴露 `copyProxyCredentials({proxyId, protocol, format}) → {copied:true}`。允许当前窗口主 frame；输入不接受任意 URL、secret ref 或剪贴板内容。
8. **前端入口（待后续任务）**：由主线的全局导航导入 `ProxyManagementPage`，传入已就绪的 `ApiClient`。本次没有修改 `App.tsx`，也没有增加代理模块内部侧栏。
9. **生成类型与错误**：合并实际路由后重新运行 `npm run openapi:generate`，不要手工拼接两个 generated.ts。保留 `ApiClientError.error` 和 204 空响应处理。合并 proxy validation handler 时保留 profiles 的既有错误处理。
10. **样式构建**：electron-vite renderer 使用 `react()` 与 `@tailwindcss/vite`；复用主线已存在的插件配置，不重复安装或重复注册。
11. **后端打包**：PyInstaller spec 必须把 `alembic.ini` 和 `migrations` 作为数据文件打包。缺少时源码模式可用，但 frozen sidecar 会因缺失迁移配置而启动失败；合并后必须运行实际可执行文件 smoke。

浏览器配置字段继续使用 `proxy_mode = none | proxy | pool`、`proxy_id` 和 `proxy_pool_id`；后者对应 AutoFlow 本地组。代理任务不改这套契约。代理组启动解析入口为 `ResolveProxyForProfile(uow_factory, probe).resolve_group(group_id, request_id)`；`request_id` 对应一次浏览器启动，重试沿用同一个 ID。应接入浏览器启动服务，不能由 renderer 先“选一个”再启动，也不能在失败时静默直连。检查失败的成员需要显式重新检测成功后恢复参与选择，当前不自动重试失败成员。

## 5. 独立预览

在代理工作区执行：

```bash
node scripts/preview-proxies.mjs
```

脚本输出当前本地预览 URL。使用单独的 sidecar、按工作区隔离的数据目录和真实本地 API，不加载生产 mock，也不会占用浏览器主线的 SQLite。浏览器预览没有 Electron IPC，因此凭据复制按钮禁用；桌面主线合并后才提供该能力。

## 6. 验证记录

### 6.1 代理独立工作区

本次在代理独立工作区、macOS arm64 上执行：

| 命令 / 检查 | 结果 |
| --- | --- |
| `uv run --directory apps/backend pytest -q` | 106 passed，含 10 个多 Session / 多线程并发回归 |
| `uv run --directory apps/backend ruff check src tests` | 通过 |
| `uv run --directory apps/backend mypy src` | 54 个源码文件通过 |
| `npm test` | 46 passed，含 10 个代理页面交互测试 |
| `npm run typecheck` / `npm run lint` / `npm run build` | 通过 |
| 代理预览独立生产构建 | 通过；直接以 `proxy-preview.html` 为入口，验证实际代理模块打包，产物位于忽略的验证目录 |
| `npm run openapi:check` | 通过，host-only 接口未进入公开 schema |
| `npm run test:scripts` | 7 passed，包含目录检查 |
| `npm run backend:build` | 通过；最终代码再次打包并执行 frozen sidecar smoke |
| frozen sidecar smoke / `npm run smoke:desktop` | 通过；后者为开发 Electron 与实际 sidecar 的生命周期检查 |
| `git diff --check` | 通过 |

测试覆盖系统凭据存储、主进程复制、健康探针、API 客户端、临时 SQLite HTTP 契约、host token 隔离和敏感校验错误。并发回归包含 stale revision、旧 token 的晚失败、API Key 替换、同请求幂等、不同请求同时选中相同候选后的重选。测试通过不等于合并浏览器主线后通过，主线仍须重新生成 OpenAPI 并整体回归。

pytest 报告两条来自 Starlette/httpx 测试适配的弃用提示，无失败；本轮没有为消除提示而升级整套公共测试依赖。

CUA 已检查真实未连接预览与连接弹窗；另以显式标注“合成数据 · 视觉测试”的临时入口，在 1280×900 下检查有数据表格、详情 Drawer 和组编辑。发现的操作按钮/状态逐字换行已修复并复验，长名称和失效成员可完整显示。合成入口没有真实 Key、没有向 ProxyPanel 发请求，也没有往交付预览的数据库注入测试账号。截图暂存 `.superpowers/verification/proxy-visual/`（忽略目录），仅作为本机视觉证据；不替代键盘、读屏或实网验收。布局小修复后再次通过 10 个代理交互测试、TypeScript 与 ESLint。

### 6.2 浏览器主线整合后

| 命令 / 检查 | 结果 |
| --- | --- |
| `uv run --directory apps/backend pytest -q` | 207 passed；2 条既有 Starlette/httpx 弃用提示 |
| `uv run --directory apps/backend ruff check src tests` | 通过 |
| `uv run --directory apps/backend mypy src` | 81 个源码文件通过 |
| `npm test` | 47 passed |
| `npm run typecheck` / `npm run lint` / `npm run build` | 通过 |
| `npm run openapi:generate` / `npm run openapi:check` | 通过；类型由合并后实际路由生成，internal 端点未公开 |
| `npm run test:scripts` | 7 passed |
| Alembic head / 新库 / 既有 `0001_browser_resources` 库升级 | 唯一 head 为 `0002_proxy_management`，两条升级路径通过 |
| `npm run backend:build` / `npm run smoke:sidecar` | 通过；frozen 产物包含迁移资源并可启动 |
| `npm run smoke:desktop` | 通过；开发 Electron 连接 sidecar，宿主退出后 sidecar 回收 |
| `git diff --check` | 通过 |

主线整合专门保留了既有 profiles、kernel worker、SSE 和 shutdown 处理；shutdown 测试同时断言 kernel worker 与代理 session 的关闭函数均被调用。用户既有 Vite、automation、model 和 UI 草稿没有纳入本次提交。

真实 ProxyPanel 响应映射/账号联调：**未验证**。Windows x64、macOS Intel 的本轮构建运行：**未在本机执行**，沿用 CI 矩阵进行平台验收。全局导航与浏览器启动到代理组的端到端调用：**待后续浏览器任务整合**。
