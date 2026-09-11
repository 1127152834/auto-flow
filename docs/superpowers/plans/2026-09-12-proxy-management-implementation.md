# ProxyPanel 代理管理实施计划

- 日期：2026-09-12
- 状态：confirmed / integrated；2026-09-12 已从 `codex/proxy-management@0ad2fd2` 选择性接入浏览器主线
- 关联规格：`docs/superpowers/specs/2026-09-12-proxy-management-design.md`
- API 资料：`docs/references/proxypanel-api-contract.md`
- 原型：`docs/prototype/proxy-management/proxy-management-overview.png`
- 目标：按组件先行和前后端垂直切片，交付 ProxyPanel 连接、代理投影与健康详情、AutoFlow 本地代理组、浏览器配置引用，以及经真实契约验证后才启用的远程操作。

本文定义实施顺序、文件归属和验收方式。用户已批准代码实施；具体完成项、真实接入限制和公共文件合并顺序见 [实施状态](../../migration/proxy-management-status.md)。原定测试文件名是计划建议，最终执行命令以该状态记录中的实际文件为准。

## 1. 实施前提与证据边界

当前仓库不存在由真实 ProxyPanel API 响应脱敏得到的 live fixtures，也没有可用于自动联调的真实 API key。可以编写 synthetic 样例验证 AutoFlow 内部模型、错误映射、组件状态和测试工具，但 synthetic 样例不能授予任何能力 `fixture-verified` 等级，也不能证明 ProxyPanel provider contract 已通过。

以下能力必须在真实响应脱敏、字段语义核验和 contract test 通过后才能启用：地点变更、远程轮换计划、凭据轮换、IP 白名单写入、用量、余额、远程状态和订阅到期时间。`subscription_expires_at` 在此前始终为 `null`；UI 不渲染“即将到期”。

规划时仓库只有 `infrastructure/credentials/` 目录骨架，没有 CredentialStore 实现。该前置条件现已在代理独立分支完成；真实端点凭据读取仍受 Provider 证据边界约束，不能因存储适配完成而宣称实网接入。

安全边界如下：

- API key 初次录入时会短暂存在于 renderer 表单内存和到本地 loopback HTTP sidecar 的请求体中（现有通信方式）；提交后立即清空表单，不写入持久化状态、查询缓存、日志、错误、诊断或 OpenAPI 响应。
- Python sidecar 不直接操作系统剪贴板。复制代理凭据由受限 Electron main IPC 完成：renderer 发出明确的 `proxyId` 请求，main 通过受控 sidecar 接口取一次性秘密并写入系统剪贴板，renderer 只收到 `{copied: true}`。
- SQLite 只保存 `secret_ref` 和 `has_secret`，不保存 API key、用户名密码或带认证信息的代理 URL。
- Provider base URL 固定到官方 allowlist；不接受 renderer 传入任意地址。

## 2. 固定目录和公共文件所有权

实施沿用现有工程路径：

```text
apps/backend/src/autoflow/
  domain/proxies/
  application/proxies/
  providers/proxy/
  adapters/http/
  infrastructure/{database,credentials}/
apps/backend/tests/{unit,integration,contract,fixtures}/

apps/desktop/src/
  main/{ipc,platform}/
  preload/
  renderer/domains/{proxies,profiles}/
  renderer/shared/api/generated.ts
```

禁止新增第二套 backend、contracts 包或 `renderer/features/proxies`。OpenAPI 类型只生成到 `apps/desktop/src/renderer/shared/api/generated.ts`。

下列公共文件只由主代理修改，普通实现代理不得同时编辑：

- `apps/backend/src/autoflow/bootstrap/app.py` 和 `adapters/http/openapi.py`
- `apps/backend/src/autoflow/infrastructure/database/models.py`
- Alembic migration head 与迁移注册
- `apps/desktop/src/renderer/app/` 下的全局路由与导航
- `apps/desktop/src/main/index.ts`、`apps/desktop/src/preload/index.ts` 等全局 IPC 装配入口
- `apps/desktop/src/renderer/shared/api/generated.ts`
- 全局 Tailwind/主题样式

## 3. 波次 A：组件和内部契约基线

该波次不连接 ProxyPanel，可以并行进行；完成后才能开始页面组装。

### A1. AutoFlow 内部 OpenAPI 模型

负责人：主代理。

文件归属：

- `apps/backend/src/autoflow/adapters/http/proxy_schemas.py`
- `apps/backend/tests/contract/test_proxy_openapi.py`
- `apps/desktop/src/renderer/shared/api/generated.ts`（只由主代理生成）

任务：

1. 定义连接、代理投影、健康快照、本地代理组、分页、`ActionResult`、operation 和统一 `ApiError`。
2. 所有外部不确定字段保持 nullable/unknown；响应模型不出现 API key、密码、认证 URL。凭据写请求标记 writeOnly，校验错误去除敏感 input；普通 CORS 增加 Idempotency-Key，不开放 host token header。
3. 冻结 offset/limit、筛选、幂等键和错误码的本地语义。
4. 先将 schema-only 模型注册为 OpenAPI components，不为未实现用例发布假成功路由；运行生成器提交 `generated.ts`。实际 paths 随后续切片路由加入，后续前端禁止手写重复 DTO。

前置依赖：规格和 API 文档获批。

验收命令：

```bash
uv run --directory apps/backend pytest tests/contract/test_proxy_openapi.py -q
npm run openapi:generate
npm run openapi:check
```

### A2. CredentialStore 与受限复制通道

负责人：`gpt-5.6-sol` 后端/桌面基础设施代理；主代理负责合并公共 IPC 入口。

文件归属：

- `apps/backend/src/autoflow/domain/credentials.py`（端口）
- `apps/backend/src/autoflow/infrastructure/credentials/`（实现）
- `apps/backend/tests/unit/test_credential_store.py`
- `apps/desktop/src/main/ipc/proxy-credentials.ts`
- `apps/desktop/src/main/platform/macos/`
- `apps/desktop/src/main/platform/windows/`
- `apps/desktop/src/preload/` 中代理凭据桥接的独立文件
- `apps/desktop/tests/` 中 IPC 安全测试

任务：定义 `read/write/delete` secret port、平台安全存储适配器、secret ref 生命周期和错误脱敏；实现只允许复制指定代理凭据的 Electron main IPC。取密端点按 API 资料生成/注入 AUTOFLOW_HOST_TOKEN，并单独保护 /internal/*，禁止复用 renderer 可访问的 instance token，复制后 30 秒按内容匹配清理剪贴板。不得提供任意 key 读取、任意剪贴板写入或把秘密返回 renderer 的通道。

前置依赖：A1 的 CredentialView；复制请求/响应是 main/preload 独立 IPC 类型，不进入 renderer OpenAPI。

验收命令：

```bash
uv run --directory apps/backend pytest tests/unit/test_credential_store.py -q
npm --workspace @autoflow/desktop test -- proxy-credentials
npm run typecheck
```

### A3. 共享 UI 与代理领域展示组件

负责人：`gpt-5.6-sol` 前端组件代理。

文件归属：

- `packages/ui/src/`（有真实跨领域复用的控件，若包尚未注册由主代理统一装配）
- `apps/desktop/src/renderer/shared/components/`（应用专用通用组合）
- `apps/desktop/src/renderer/domains/proxies/components/`
- `apps/desktop/src/renderer/domains/proxies/tests/`

任务：优先复用现有 shadcn/ui 基础控件；补齐 DataTable、状态徽标、摘要卡、Drawer、Dialog、Toast、Skeleton、EmptyState、ErrorState 和确认操作。随后构建连接卡片、代理表格、健康结果、详情 Drawer、位置选择、轮换表单、白名单编辑器和本地组表格。

组件仅接收生成类型与显式回调，不发请求、不读取 secret。覆盖 loading、empty、error、stale、unknown、disabled、submitting 和 429 倒计时状态。

前置依赖：领域组件等待 A1 生成的 `generated.ts`；A1 未完成时先验证/补齐无业务字段的基础控件，不建立临时的第二套 DTO。

验收命令：

```bash
npm --workspace @autoflow/desktop test -- proxies
npm run typecheck
npm run lint
```

## 4. 波次 B：连接与同步垂直切片

目标：用户能录入 ProxyPanel API key、验证连接并同步本地投影；在没有 live fixture 时只证明 AutoFlow 内部流程，不宣称真实 Provider 通过。

### B0. 只读 Provider 证据入口

主代理在用户提供可用连接条件后，仅采集授权的只读列表、详情、地点，以及这些响应已有的 credential_available 元信息，按 API 资料脱敏并核验分页/字段；不把普通采样扩大到 credentials 明文读取。后续用户连接并使用代理/请求复制的授权流程才按需取密，真实秘密不得进入 fixture。没有真实响应时 B1–B3 仍可用 synthetic 数据开发本地用例，但 B 切片不得标记“真实接入完成”。只读 schema 的核验不延迟到远程写操作波次。

### B1. 后端连接、同步和投影

负责人：`gpt-5.6-sol` 后端代理。

文件归属：

- `apps/backend/src/autoflow/domain/proxies/`
- `apps/backend/src/autoflow/application/proxies/connections.py`
- `apps/backend/src/autoflow/application/proxies/sync.py`
- `apps/backend/src/autoflow/providers/proxy/`
- 对应 `apps/backend/tests/{unit,contract}/`

任务：实现 Connection、Projection、capability/evidence、provider port、固定 base URL、认证头注入、错误映射、generation/tombstone 同步和 stale 保留。先用 fake provider/synthetic 数据验证应用层；adapter contract 保持未通过状态，直到真实脱敏 live fixture 到位。

前置依赖：A1、A2。

### B2. 数据库和 HTTP API

负责人：主代理负责数据库公共文件和路由装配；后端代理提供独立 repository/route 文件。

文件归属：

- `apps/backend/src/autoflow/infrastructure/database/proxy_*.py`
- 新 Alembic migration
- `apps/backend/src/autoflow/adapters/http/proxies.py`
- `apps/backend/tests/integration/test_proxy_sync.py`
- `apps/backend/tests/contract/test_proxy_connections_api.py`

任务：持久化 connection metadata、secret ref、projection generation、remote_missing、stale 和脱敏 last_error；提供 connection create/update/delete、verify、sync 和 projection list/detail API。

前置依赖：B1；迁移变更由主代理串行合并。

### B3. 前端连接与同步页面

负责人：`gpt-5.6-sol` 前端代理。

文件归属：

- `apps/desktop/src/renderer/domains/proxies/api.ts`
- `apps/desktop/src/renderer/domains/proxies/hooks/`
- `apps/desktop/src/renderer/domains/proxies/pages/ProxyManagementPage.tsx`
- 对应 tests

任务：组装连接卡、摘要、筛选和代理表格；提交 API key 后立即清空本地表单；实现同步中、认证失败、429、服务不可用、stale、空数据和成功 Toast。摘要只显示可验证数据。

前置依赖：A3、B2、最新 `generated.ts`。

切片验收：

```bash
uv run --directory apps/backend pytest tests/unit tests/integration/test_proxy_sync.py tests/contract/test_proxy_connections_api.py -q
npm run openapi:check
npm --workspace @autoflow/desktop test -- proxies
npm run typecheck
```

## 5. 波次 C：健康检查与详情垂直切片

### C1. 后端健康探针和详情用例

负责人：`gpt-5.6-sol` 后端代理。

文件归属：

- `apps/backend/src/autoflow/application/proxies/health.py`
- `apps/backend/src/autoflow/providers/proxy/probe.py`
- `apps/backend/src/autoflow/adapters/http/proxies.py` 中本领域端点
- 对应 unit/contract tests

任务：实现受控数据面探针、超时、延迟和出口 IP 采集；明确这些字段为 locally-derived。失败不得覆盖最后一次成功投影；记录脱敏 health_error 和时间。

### C2. 前端详情 Drawer

负责人：`gpt-5.6-sol` 前端代理。

文件归属：

- `apps/desktop/src/renderer/domains/proxies/components/ProxyDetailDrawer.tsx`
- `apps/desktop/src/renderer/domains/proxies/hooks/use-proxy-health.ts`
- 对应 tests

任务：接入概览和健康检查，显示数据来源与检查时间；支持 checking、success、timeout、unknown 和 stale。用量、位置、凭据等未验证标签只显示能力不可用状态，不提供假数据。

前置依赖：B 完成；C1/C2 可先并行开发，最终以生成契约联调。

切片验收：

```bash
uv run --directory apps/backend pytest tests/unit/test_proxy_health.py tests/contract/test_proxy_health_api.py -q
npm --workspace @autoflow/desktop test -- proxy-health
npm run typecheck
```

## 6. 波次 D：本地代理组与浏览器引用垂直切片

### D1. 本地代理组领域、仓储和 API

负责人：`gpt-5.6-sol` 后端代理；主代理合并迁移和路由。

文件归属：

- `apps/backend/src/autoflow/domain/proxies/groups.py`
- `apps/backend/src/autoflow/application/proxies/groups.py`
- `apps/backend/src/autoflow/infrastructure/database/proxy_groups.py`
- `apps/backend/src/autoflow/adapters/http/proxy_groups.py`
- 对应 unit/integration/contract tests

任务：实现组 CRUD、成员顺序、风险二次确认、引用保护和事务内 Round Robin；选择属于 resolve_proxy_for_profile 应用用例，不暴露可推进游标的 renderer /select API。跳过 disabled、unhealthy、remote_missing、凭据不可用成员；未检测成员启动前探测，有界尝试，原子推进游标；同一启动请求幂等，无可用成员返回稳定错误。

### D2. 本地代理组 UI

负责人：`gpt-5.6-sol` 前端代理。

文件归属：

- `apps/desktop/src/renderer/domains/proxies/components/LocalProxyGroup*.tsx`
- `apps/desktop/src/renderer/domains/proxies/hooks/use-proxy-groups.ts`
- 对应 tests

任务：实现创建、编辑、成员排序、删除确认和风险确认；清楚标注“AutoFlow 本地编排”。

### D3. 浏览器配置引用

负责人：主代理或独立 `gpt-5.6-sol` profiles 代理，禁止与 D2 编辑同一文件。

文件归属：

- `apps/backend/src/autoflow/domain/profiles/`
- `apps/backend/src/autoflow/application/profiles/`
- `apps/desktop/src/renderer/domains/profiles/`
- 对应 tests

任务：代理模式支持 none、单个 ProxyPanel 投影和本地代理组；保存的是本地 ID，renderer 不接触代理凭据。验证删除引用保护、禁用成员不会被启动选择、全部失效不静默直连以及同步后选择器刷新；沿用当前 proxy_mode/proxy_id/proxy_pool_id，proxy_pool_id 对应本地组。

前置依赖：B、C 和 D1；D2 与 D3 可并行。

切片验收：

```bash
uv run --directory apps/backend pytest tests/unit/test_proxy_groups.py tests/integration/test_proxy_groups.py tests/contract/test_proxy_groups_api.py -q
npm --workspace @autoflow/desktop test -- proxy-groups
npm --workspace @autoflow/desktop test -- profiles
npm run openapi:check
npm run typecheck
```

## 7. 波次 E：已验证远程操作

该波次的可选读取在具备真实 API key/脱敏样本后开始；写操作还必须具备明确测试代理、授权操作和可恢复条件，仅有只读授权不能执行换 IP/地点/凭据变更。每项能力独立升级证据等级，不能因一个端点通过而批量开启其他端点。

任务顺序：

1. 采集并脱敏 list/detail、错误和分页响应；验证字段、nullable、时间、枚举、total、Retry-After 和错误 body。
2. 让真实 fixture 驱动 `providers/proxy` contract tests；通过后把对应 capability 标记为 `fixture-verified`。
3. 依次实现只读地点列表、用量、余额。
4. 在明确副作用、幂等和速率限制后，逐项实现 Change IP、relocate、rotation schedule、IP allowlist 和 credential rotate。
5. 每个写操作增加单资源锁、`Idempotency-Key`、明确确认框和操作后刷新；禁止盲重试。

凭据轮换后产生的新秘密持久化到 CredentialStore。受控复制通过 Electron main IPC；面向 renderer 的 HTTP API 与 DOM 不返回密码，host-only 内部取密端点仅向 main 短暂返回明文。

Provider 验收命令：

```bash
uv run --directory apps/backend pytest tests/contract/test_proxypanel_provider.py -q
uv run --directory apps/backend pytest tests/unit/test_proxypanel_errors.py tests/unit/test_proxypanel_redaction.py -q
npm --workspace @autoflow/desktop test -- proxy-remote-actions
```

没有真实脱敏 fixtures 时，上述 provider contract 必须报告“未验证/未运行”，不能用 synthetic 样例获得通过结论。

## 8. 最终验收与提交顺序

每个垂直切片独立提交，提交顺序为：A 内部契约与组件基线 → B 连接同步 → C 健康详情 → D 本地组和浏览器引用 → E 已验证远程操作。一个提交中保持后端契约、生成类型、组件/页面、测试和相关文档一致。

全量验收：

```bash
uv run --directory apps/backend pytest -q
uv run --directory apps/backend ruff check src tests
uv run --directory apps/backend mypy src
npm run openapi:check
npm test
npm run typecheck
npm run lint
npm run build
npm run test:structure
```

跨平台 CI 至少覆盖 macOS arm64/x64 和 Windows x64 的 CredentialStore、sidecar 生命周期、Electron IPC、数据目录、打包和启动 smoke。真实账号联调不得自动执行购买、续费、凭据轮换、Change IP 或位置变更。

## 9. 停止条件

出现以下任一情况时停止扩展功能，先修订 API 文档、规格、fixture 和生成类型：

- live schema 与已冻结内部映射冲突；
- 响应包含未被脱敏的 key、密码或认证 URL；
- 无法确认分页完整性、错误语义、幂等行为或 429 冷却时间；
- CredentialStore 或受限 Electron IPC 尚未通过安全测试；
- `subscription_expires_at`、远程状态、余额或用量缺少可靠字段证据：仅暂停对应能力，不阻塞已验证的本地组和其他读取；
- 多个代理需要同时编辑公共装配文件，无法保持文件所有权隔离。
