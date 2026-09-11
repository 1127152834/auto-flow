# AutoFlow ProxyPanel 代理管理规格说明书

- 日期：2026-09-12
- 状态：proposed，等待用户审查
- 范围：代理管理模块；不实现购买、支付或其他供应商
- 依据：ProxyPanel 官方页面/API 文档、旧项目代理模块、已确认的 ProxyPanel 本地代理组决策

## 1. 目标和边界

AutoFlow 的代理管理模块绑定 ProxyPanel，负责把 ProxyPanel 的专用移动代理舰队投影到本地，并为浏览器配置提供稳定的代理引用、健康状态、位置控制和轮换控制。

本模块不把 ProxyPanel 当作通用代理 CRUD 服务。用户不能在 AutoFlow 中创建一个脱离 ProxyPanel 的任意代理端点；代理列表来自 ProxyPanel，AutoFlow 只维护本地显示名称、启用状态、同步投影、浏览器配置引用和本地代理组。

ProxyPanel 的城市/运营商位置池是远程能力；AutoFlow 的本地代理组是本地编排实体。两者不能共用一个模型或 UI 名称。

不纳入第一版：购买、续费、支付、自动续费写操作、团队/子账号管理、其他代理供应商、旧版 URL-key API 暴露、项目管理。

## 2. 可行性结论和指标规则

| UI 信息 | 第一版规则 |
| --- | --- |
| 总代理 | 只在同步响应有明确 total 或本地投影集合完整时显示；否则显示“已同步 N 个”，不声称账户总量。 |
| 运行中/待启动/未激活 | 使用 ProxyPanel 返回状态；未知值显示状态未知。若 live schema 没有状态字段，则由同步状态和本地探测标记为“可探测/不可探测”，不能冒充远程状态。 |
| 异常 | AutoFlow 本地计算：认证失败、同步失败、实时探测失败、连接超时或最近一次写操作失败。显示来源和时间。 |
| 延迟 | AutoFlow 后端探针测量，不使用首页营销平均值。 |
| 出口 IP | 优先使用实时探测或数据面探针结果；外部响应没有字段时标记为本地探测结果。 |
| 即将到期 | 默认隐藏。只有 live contract 明确返回 `expires_at`/订阅截止时间并通过 fixture 验证后才显示；不能从余额、套餐或自动续费推导。 |
| 用量/余额 | 只有 API 返回可验证字段才显示；没有数据时显示“暂无数据”，不填零。 |

## 3. 领域模型

### ProxyPanelConnection

保存本地连接配置，不保存密钥明文：

- `id`
- `name`
- `provider = proxypanel`
- `api_base_url` 固定为官方 allowlist，不允许用户输入任意地址
- `api_key_secret_ref`
- `has_secret`
- `status`: unconfigured / verifying / connected / failed
- `last_verified_at`
- `last_synced_at`
- `last_error`（脱敏）

### ProxyEndpointProjection

ProxyPanel 远程代理的本地投影：

- `id`（AutoFlow 本地 ID）
- `provider_proxy_id`
- `connection_id`
- `name_override`
- `remote_status`（原始值保留为受控枚举/未知）
- `carrier`
- `city`
- `region`
- `exit_ip`
- `http_host/http_port`
- `socks5_host/socks5_port`
- `endpoint_secret_ref`
- `credential_available`
- `enabled`
- `latency_ms`
- `last_checked_at`
- `health_state`
- `health_error`
- `subscription_expires_at` nullable
- `source_updated_at`
- `last_synced_at`
- `last_error`

API 响应不返回 API key、密码或完整带认证 URL。host/port 可按安全策略返回；复制凭据使用受控一次性 action。

### LocalProxyGroup

本地编排实体：

- `id`
- `name`
- `member_ids` 与 position
- `next_index`
- `created_at/updated_at`

删除或修改被浏览器配置引用的代理/代理组时由后端返回稳定冲突错误。

## 4. Provider 适配器

业务层只依赖 `ProxyProvider` 端口，不依赖 requests/httpx 或 ProxyPanel URL 细节：

- `verify_connection`
- `list_proxies`
- `get_proxy`
- `probe_proxy`
- `get_credentials`
- `rotate_credentials`
- `change_ip`
- `relocate`
- `list_locations`
- `get_rotation_schedule`
- `set_rotation_schedule`
- `delete_rotation_schedule`
- `get_ip_allowlist`
- `set_ip_allowlist`
- `delete_ip_allowlist`
- `get_usage`
- `get_account_summary`

适配器要求：

- 只调用固定官方 base URL；
- 对路径、query 和错误 body 做脱敏；
- 识别 401/403、404、409、422、429、5xx；
- 429 尊重 Retry-After，不自动高频重试；
- 换 IP、改地点、轮换、凭据旋转不可盲重试，需要并发锁和 request id；
- 对外部字段缺失保持 `null/unknown`，不能填默认零值；
- 响应 schema 不匹配时返回 `PROXYPANEL_SCHEMA_UNSUPPORTED`，保留脱敏诊断。

## 5. AutoFlow 内部 API

### 连接和同步

- `GET/POST /api/v1/proxy-panel/connections`
- `PUT/DELETE /api/v1/proxy-panel/connections/{connection_id}`
- `POST /api/v1/proxy-panel/connections/{connection_id}/verify`
- `POST /api/v1/proxy-panel/connections/{connection_id}/sync`

### 代理投影

- `GET /api/v1/proxies`
- `GET /api/v1/proxies/{proxy_id}`
- `POST /api/v1/proxies/{proxy_id}/probe`
- `POST /api/v1/proxies/{proxy_id}/change-ip`
- `POST /api/v1/proxies/{proxy_id}/relocate`
- `GET /api/v1/proxies/{proxy_id}/credentials`
- `POST /api/v1/proxies/{proxy_id}/credentials/rotate`
- `GET/PUT/DELETE /api/v1/proxies/{proxy_id}/rotation-schedule`
- `GET/PUT/DELETE /api/v1/proxies/{proxy_id}/ip-auth`
- `GET /api/v1/proxies/{proxy_id}/usage`

### 本地代理组

- `GET/POST /api/v1/proxy-groups`
- `GET/PUT/DELETE /api/v1/proxy-groups/{group_id}`
- `PUT /api/v1/proxy-groups/{group_id}/members`

### 写操作结果

同步完成的操作返回 `completed`；外部服务需要异步处理时返回 `accepted + operation_id`。本地 sidecar 提供 operation 状态查询，renderer 不直接轮询 ProxyPanel。

统一错误码：

`PROXYPANEL_NOT_CONFIGURED`、`PROXYPANEL_AUTH_FAILED`、`PROXYPANEL_RATE_LIMITED`、`PROXYPANEL_NOT_FOUND`、`PROXYPANEL_CONFLICT`、`PROXYPANEL_VALIDATION_ERROR`、`PROXYPANEL_UNAVAILABLE`、`PROXYPANEL_SCHEMA_UNSUPPORTED`、`PROXY_IN_USE`、`PROXY_GROUP_IN_USE`、`STALE_PROJECTION`。

## 6. UI 规格

使用单一主内容区，不增加页面内侧栏。

### 主页面

- ProxyPanel 连接卡片：连接名称、状态、最近同步、刷新代理、连接设置；
- 摘要：只显示可验证的运行中、异常、已同步数量；即将到期按第 2 节规则处理；
- 代理舰队表格：名称、状态、运营商、城市、出口 IP、延迟、轮换、关联配置、操作；
- 本地代理组区域：明确标识 AutoFlow 本地编排。

### 详情 Drawer

标签：概览、位置与轮换、凭据与白名单、用量。支持健康检查、Change IP、改地点、轮换计划、凭据轮换、IPv4 白名单和关联配置。

### 状态

必须覆盖加载、未连接、同步失败、健康检查中、429、认证失败、空数据、stale projection、成功 Toast 和危险操作确认。

## 7. 安全与平台边界

- API key 和 endpoint password 只在 sidecar 使用；CredentialStore 只返回 secret ref；
- renderer 不直接访问 ProxyPanel；
- 诊断、日志和异常过滤 key/password/完整 URL；
- Windows/macOS 只通过既有 sidecar、filesystem 和 credential adapter，领域逻辑不判断平台；
- 数据面健康探针默认使用固定探针，不发送用户业务 URL。

## 8. 验收标准

- 真实/脱敏 ProxyPanel fixture 能完成连接验证、同步、详情、探测、位置、轮换、白名单和凭据状态；
- 缺少到期字段时 UI 不显示伪造的“即将到期”；
- 429、401/403、404、409、422、5xx 都映射为稳定错误并脱敏；
- API key、密码、认证 URL 不出现在 renderer、日志、错误、OpenAPI response；
- 本地代理组 Round Robin、成员排序、风险二次确认和浏览器配置引用保护可用；
- 前端只使用生成契约和 hooks，不保留长期 mock-only 页面；
- 后端单测、契约测试、前端交互测试、Electron E2E、macOS/Windows CI 通过；
- 无真实 key 时可以用脱敏 fixture 完成完整测试。
