# ProxyPanel API 开发资料

- 日期：2026-09-12
- 状态：confirmed from public docs / proposed for AutoFlow adapter
- 官方来源：[ProxyPanel Developers](https://proxypanel.io/developers)、[ProxyPanel Home](https://proxypanel.io/home)、[旧版 API 文档](https://proxypanel.io/documentation)

## 外部 API 能力矩阵

外部基址：`https://proxypanel.io/api/v1`。认证：`Authorization: Bearer <API_KEY>`。API key 不进入 renderer、SQLite 明文、日志、错误或 OpenAPI 响应。

| Provider port | 外部能力 | 备注 |
| --- | --- | --- |
| `list_proxies` | `GET /proxies` | 分页和 total 未确认。 |
| `get_proxy` | `GET /proxies/{id}` | `?probe=true` 用于实时探测。 |
| `get_credentials` | `GET /proxies/{id}/credentials` | 仅在 sidecar 受控读取并写入 CredentialStore；不返回 renderer。 |
| `rotate_credentials` | `POST /proxies/{id}/credentials/rotate` | 新 secret 只返回一次；不可自动重试。 |
| `change_ip` | `POST /proxies/{id}/rotate` | 有频率限制；需要确认和并发锁。 |
| `relocate` | `POST /proxies/{id}/relocate` | 支持指定 location 或随机位置。 |
| `list_locations` | `GET /locations` | 缓存并手动刷新。 |
| `get_rotation` | `GET /proxies/{id}/rotation-schedule` | null 表示未配置。 |
| `set_rotation` | `PUT /proxies/{id}/rotation-schedule` | 模式/间隔由 adapter 校验。 |
| `delete_rotation` | `DELETE /proxies/{id}/rotation-schedule` | 写操作成功后刷新投影。 |
| `get_ip_auth` | `GET /proxies/{id}/ip-auth` | 返回需脱敏。 |
| `set_ip_auth` | `PUT /proxies/{id}/ip-auth` | 最多 16 个 IPv4 的约束需前后端都校验。 |
| `delete_ip_auth` | `DELETE /proxies/{id}/ip-auth` | 需要确认。 |
| `get_usage` | `GET /proxies/{id}/usage` | since/until；返回结构待联调。 |
| `get_balance` | `GET /balance` | 只读账户摘要。 |

## AutoFlow 内部 API 契约（v1）

这些是 renderer 依赖的本地 sidecar API，不把 ProxyPanel 原始 schema 暴露到前端。

### 通用类型

以下是 OpenAPI 生成前必须冻结的最小模型；字段未标记为 nullable 时均为必填。

```json
{
  "Page<T>": { "items": "T[]", "next_cursor": "string|null", "has_more": "boolean" },
  "ApiError": { "code": "string", "message": "string", "retry_after_seconds": "integer|null", "details": "object|null" },
  "ActionResult<T>": { "status": "completed|accepted|failed", "operation_id": "string|null", "resource": "T|null", "error": "ApiError|null" },
  "Capability": { "key": "string", "enabled": "boolean", "evidence": "confirmed-public|confirmed-authenticated-doc|fixture-verified|unknown" }
}
```

列表接口使用 `cursor`、`limit`（默认 50，最大 100）、`q` 和领域筛选参数；服务端不得把未确认的 Provider `total` 映射成总量。写请求使用 `Idempotency-Key`，重复键返回同一 `operation_id` 或资源结果。

### 连接

- `GET /api/v1/proxy-panel/connections`
- `POST /api/v1/proxy-panel/connections`
- `PUT /api/v1/proxy-panel/connections/{connection_id}`
- `DELETE /api/v1/proxy-panel/connections/{connection_id}`
- `POST /api/v1/proxy-panel/connections/{connection_id}/verify`
- `POST /api/v1/proxy-panel/connections/{connection_id}/sync`

写入请求只接受 API key 的一次性输入，响应只返回 `has_secret`、状态、时间和脱敏错误。

`POST connections` 请求：`{name, api_key}`；响应：`{id, name, provider, has_secret, status, capabilities[], last_verified_at, last_synced_at, last_error}`。`PUT` 只允许修改 `name`；`DELETE` 被代理投影或浏览器配置引用时返回 `PROXY_IN_USE`。

### 代理投影

- `GET /api/v1/proxies`
- `GET /api/v1/proxies/{proxy_id}`
- `POST /api/v1/proxies/{proxy_id}/probe`
- `POST /api/v1/proxies/{proxy_id}/change-ip`
- `POST /api/v1/proxies/{proxy_id}/relocate`
- `GET /api/v1/proxies/{proxy_id}/credentials`
- `POST /api/v1/proxies/{proxy_id}/credentials/copy`
- `POST /api/v1/proxies/{proxy_id}/credentials/rotate`
- `GET/PUT/DELETE /api/v1/proxies/{proxy_id}/rotation-schedule`
- `GET/PUT/DELETE /api/v1/proxies/{proxy_id}/ip-auth`
- `GET /api/v1/proxies/{proxy_id}/usage`
- `GET /api/v1/proxy-operations/{operation_id}`

### 本地代理组

- `GET/POST /api/v1/proxy-groups`
- `GET/PUT/DELETE /api/v1/proxy-groups/{group_id}`
- `PUT /api/v1/proxy-groups/{group_id}/members`
- `POST /api/v1/proxy-groups/{group_id}/select`

`POST /relocate` 请求为 `{location_id, carrier|null}`；`PUT rotation-schedule` 请求为 `{mode, interval_seconds}`；`PUT ip-auth` 请求为 `{enabled, ipv4s[]}`（1–16 个 IPv4）。上述字段在 Provider capability 未达到 `fixture-verified` 时，接口返回 `PROXYPANEL_SCHEMA_UNSUPPORTED`，前端隐藏或禁用对应操作。

代理列表响应为 `Page<ProxyEndpointProjection>`；投影的 `subscription_expires_at`、usage 和 account summary 均为 nullable。`GET /proxy-operations/{id}` 返回 `{id, kind, status: pending|running|completed|failed|cancelled, result, error, created_at, updated_at}`。首版只允许查询，不提供取消，直到 Provider 明确支持取消。

### 同步生命周期和本地组运行语义

同步使用 generation：只有完整分页成功的同步才提交新 generation。单页失败、单条 schema 不匹配或连接中断时保留上一版投影并标记 `stale=true`。远端列表消失的投影标记 `remote_missing=true`；只要仍被浏览器配置或本地组引用，就不得物理删除。

`POST /proxy-groups/{group_id}/select` 在一个事务中锁定组、按成员顺序跳过 disabled、unhealthy 和 remote_missing 成员，返回 `{proxy_id, cursor, skipped_member_ids[]}` 并推进游标。没有可用成员时返回 `PROXY_GROUP_NO_AVAILABLE_MEMBER`。并发请求必须保证同一游标不会被重复消费。

本地代理组成员引用 AutoFlow proxy projection，不创建 ProxyPanel 远程对象。

## 统一响应约定

资源读取响应包含：

- `source_updated_at`
- `last_synced_at`
- `stale`
- `last_error`（脱敏）

写操作允许返回：

```json
{
  "status": "completed|accepted|failed",
  "operation_id": "optional-local-id",
  "resource": {},
  "error": null
}
```

如果外部操作需要轮询，使用本地 operation endpoint；不让 renderer 轮询 ProxyPanel。

内部错误码至少包括：`PROXYPANEL_AUTH_FAILED`、`PROXYPANEL_RATE_LIMITED`、`PROXYPANEL_NOT_FOUND`、`PROXYPANEL_CONFLICT`、`PROXYPANEL_VALIDATION_ERROR`、`PROXYPANEL_UNAVAILABLE`、`PROXYPANEL_SCHEMA_UNSUPPORTED`、`PROXY_IN_USE`、`PROXY_GROUP_IN_USE`、`PROXY_GROUP_NO_AVAILABLE_MEMBER`。

## 证据等级

- `confirmed-public`: 可由无需账号的官方产品页/旧文档直接验证；主要覆盖旧版控制操作和产品能力描述。
- `confirmed-authenticated-doc`: 已在已有登录会话的 developers 页面看到端点，但响应 schema、错误和限制仍需真实 key fixture 验证。
- `locally-derived`: AutoFlow 对 ProxyPanel 端点执行健康探测后计算的字段，例如延迟、出口 IP、异常和本地 stale 状态。
- `unknown`: 公开资料或当前登录会话无法证明，禁止在 UI 里伪造。

因此“即将到期”在第一版默认为不可用：只有 live contract 明确返回到期字段并通过脱敏 fixture 验证后才启用；余额和自动续费不能推导到期日。

### 敏感值边界

`GET /credentials` 只返回 `credential_available` 和受控复制句柄，不返回 password。renderer 只能调用 `POST /credentials/copy`，由 sidecar 从 CredentialStore 读取并写入系统剪贴板，响应 `{copied: true}`；剪贴板内容不进入 DOM、日志、OpenAPI response 或诊断文件。若未来必须在界面显示明文密码，必须单独升级契约并定义一次性过期、禁止缓存和审计规则。
