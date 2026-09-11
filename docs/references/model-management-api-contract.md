# 模型管理 API 与迁移契约

- 日期：2026-09-12
- 状态：confirmed；14 条内部接口已实现并通过契约测试；实际证据见 [验证记录](../migration/model-management-verification.md)
- 范围：本地模型供应商、远端模型目录、模型调用测试、模型选项与凭据生命周期
- 关联：[模型管理原型说明](../prototype/model-management/model-management-interactions.md)
- 旧项目基线：`/Users/zhangtiancheng/Documents/projects/browser-automation/autoflow-desktop`，Git HEAD `324748abe7095f085b4ffb9467be9cb5c8851a5c`

本文冻结模型管理首版的内部 HTTP 契约。它复用旧项目的页面流程和 camelCase JSON，但不复制旧项目的明文密钥存储、读取响应泄密、环境代理继承、重定向跟随和更新绕过连接测试等缺陷。

## 1. 事实、设计与验证边界

### 1.1 已由旧源码确认的事实

旧源码和现有 synthetic mock 测试文件提供以下行为依据（本轮未运行旧测试）：

- 供应商连接测试读取远端模型目录；模型测试会发起一次短生成请求，两者不是同一测试。
- 新建供应商最终保存前会再次读取远端目录，验证所选模型仍然存在，再在一个 SQLite 提交中保存供应商与模型；允许选择零个模型。
- 已保存供应商的 `POST .../test` 在成功和失败时都会更新最近连接状态；`GET .../models/discover` 和模型测试不更新该状态。
- 删除供应商级联删除本地模型；删除模型只删除本地配置；供应商或模型停用后会从 `/models/options` 排除。
- 远端适配器覆盖 OpenAI、OpenAI-compatible、Anthropic、Gemini，以及 Qwen 的目录响应特例。
- 旧前端使用 TanStack Query 5（旧项目版本范围 `^5.90.2`）和 OpenAPI 生成类型。

这些事实来自静态源码与现有 mock 测试文件阅读。**没有在本轮调用真实供应商 API，也没有验证线上目录或生成能力。** `latencyMs` 只代表某次请求的本地观测值，不代表长期健康、吞吐或 SLA。

### 1.2 AutoFlow 新契约的设计决定

- API 前缀为 `/api/v1`，请求继续携带 `x-autoflow-token`。
- JSON 和 OpenAPI 字段统一 camelCase；请求对象拒绝额外字段。
- 删除未被旧 UI 使用的 `POST /model-providers` 直接创建接口；首版共 14 条路由。
- SQLite 只保存不可推导、不可复用的随机 `secretRef`；密钥保存到现有 `CredentialStore` 端口。读取 DTO 不返回 `apiKey` 或 `secretRef`。
- 业务原子性指 SQLite 可见状态原子；不宣称 SQLite 与系统凭据库之间具有 ACID 事务。
- 外部 HTTP 客户端固定 `trust_env=False`、`follow_redirects=False`。模型供应商请求不继承 `HTTP_PROXY`、`HTTPS_PROXY`、`ALL_PROXY` 或 `NO_PROXY`；首版不增加模型专用代理 UI。
- 实施时查询层新增 `@tanstack/react-query`；菜单基础控件若尚缺少则增加同族 `@radix-ui/react-dropdown-menu`；不新增 Router、Zustand 或 HTTP 客户端。页面挂入现有顶部导航，源码路径为 `apps/desktop/src/renderer/domains/models/`。

## 2. 公共 HTTP 约定

### 2.1 成功、删除和错误

- 资源读取和更新返回 200；最终接入与添加模型返回 201；删除返回 204 且响应体为空。
- 前端现有 `ApiClient.request` 必须支持 204：成功且 `response.status === 204` 时返回 `undefined`，不能调用 `response.json()`。
- JSON 请求由新的领域 `api.ts` 在调用现有 request 时显式设置 `Content-Type: application/json` 和 JSON.stringify(body)；共享客户端继续附加 `x-autoflow-token`。当前 request 并不会自动添加 Content-Type。
- 非成功响应统一为：

```json
{
  "error": {
    "code": "MODEL_PROVIDER_NOT_FOUND",
    "message": "模型供应商不存在",
    "details": {},
    "requestId": "2b9cd35e-75ae-47e3-9c17-e46f04d344f2"
  }
}
```

`details` 永远是对象，`requestId` 永远是非空字符串。前端 `ApiClientError` 应保留 `status`、`code`、`details` 和 `requestId`，不要只保留 HTTP 状态。API Key、认证头、完整外部 URL、外部响应 body 和底层异常字符串不得进入错误响应或日志。

本地认证与外部认证分别映射，统一使用错误信封：

- `SIDECAR_UNAUTHORIZED`：缺少或错误的 `x-autoflow-token`；前端重新获取 sidecar 状态。
- HTTP 409 `MODEL_PROVIDER_AUTH_FAILED`：外部供应商返回 401 或 403；前端保留表单并提示检查 API Key。

当前 sidecar token middleware 仍返回 `{"detail":"Unauthorized"}`；实施模型管理前必须把它纳入统一错误信封，避免同一状态出现两种解析格式。

### 2.2 标识、时间、排序与标准化

- 本地 ID 为不可变 UUID 字符串。Renderer 不构造外部供应商路径。
- 时间为 RFC 3339 UTC；未知时间和数值为 `null`，不填零。
- 供应商列表按 `createdAt`、`id` 升序；供应商内 `models` 按 `createdAt`、`id` 升序；模型选项按 `providerName`、`displayName`、`id` 升序。排序必须稳定。
- `name` 与 `modelKey` 在校验前 trim。空白裁剪后的值用于保存、远端请求和唯一性判断。
- 供应商 `name` 在全局按大小写敏感唯一；`modelKey` 在同一供应商内按大小写敏感唯一。因此 `OpenAI` 与 `openai`、`Model-A` 与 `model-a` 分别可共存。
- `selectedModels` 使用同一 trim 后、大小写敏感规则；不得沿用旧项目的 `casefold()` 去重，否则最终接入和日后手动添加会产生不同语义。
- SQLite 约束必须与应用校验一致：供应商名称使用 BINARY 比较的唯一索引，模型使用 `(provider_id, model_key)` BINARY 复合唯一索引；应用层预查只用于友好错误，数据库约束负责并发下的最终正确性，约束冲突统一映射为对应 409。

## 3. DTO 契约

所有 DTO 都设置 `extra="forbid"` 并生成 camelCase alias。名称、模型标识和显示名称的长度按 trim 后值校验；密钥不 trim、不改写；必填校验用去空白结果判断是否缺失，但有效非空值原样传输。密钥字段使用 `SecretStr`/OpenAPI `writeOnly` 语义，并清除 Pydantic 自动 422 中的敏感 `input`。

### 3.1 枚举

```text
ProviderKind = openai | anthropic | gemini | openai-compatible | custom
ConnectionStatus = untested | connected | failed
```

API Key 可选性由后端预设目录判定，不能信任 Renderer：首版只有 `ollama` 与 `custom-openai-compatible` 可为空，其余已知预设必须非空。未知或空 `presetId` 按必填处理。协议输入仍可独立编辑，不因协议与预设默认值不同而拒绝；Anthropic/Gemini 协议始终需要 Key，其余协议按预设政策处理。

### 3.2 写入 DTO

| DTO | 字段与限制 |
| --- | --- |
| `ModelProviderCreateInput` | `name:string` 1–120；`presetId:string|null` 最长 80，默认 null；`providerKind:ProviderKind` 默认 `openai-compatible`；`baseUrl:string|null` 默认 null；`apiKey:string` 默认 `""`；`enabled:boolean` 默认 true；`description:string` 默认 `""` |
| `ModelProviderConnectInput` | `provider:ModelProviderCreateInput`；`selectedModels:ModelInput[]` 默认 `[]`、最多 500，trim 后 `modelKey` 大小写敏感去重 |
| `ModelProviderMetadataUpdateInput` | 全量三个字段：`name:string` 1–120、`description:string`、`enabled:boolean`；连接字段出现即因 `extra="forbid"` 返回 422 |
| `ModelProviderConnectionUpdateInput` | `name:string` 1–120；`presetId:string|null` 最长 80；`providerKind:ProviderKind`；`baseUrl:string|null`；`apiKey?:string`；`enabled:boolean`；`description:string`。除 `apiKey` 外均为全量字段 |
| `ModelInput` | `modelKey:string` 1–160；`displayName:string` 1–160；`tagsJson:string[]` 默认 `[]`；`contextWindow:number|null` 默认 null；`enabled:boolean` 默认 true；`description:string` 默认 `""` |
| `ModelTestInput` | `modelKey:string` 1–160 |

`contextWindow` 必须是 JavaScript 安全正整数，即 `1 <= contextWindow <= 9_007_199_254_740_991`，或为 `null`；拒绝布尔值、浮点数、字符串、零和负数。远端目录返回的上下文长度只有满足该条件才写入 `RemoteModel.contextWindow`，否则归一为 null。

`tagsJson` 沿用旧规则：逐项 trim、丢弃空项、按精确字符串保留第一次出现的值；大小写不同的标签不合并。标签不是能力声明。

`apiKey` 的写入语义冻结如下：

- 新建预览和最终接入：字段类型为 string、默认 `""`。必填预设的空串或仅空白字符串返回 422；可选预设的空串表示不配置凭据。后端不替用户裁剪或改写非空密钥。
- 编辑连接：字段省略表示保持已有凭据；非空 string 表示替换；`""` 表示明确清除，并且只有可选密钥预设允许。
- `null` 在所有密钥写入 DTO 中都不合法。
- 编辑表单初始化为空并显示“已配置”占位状态。用户未触碰密钥输入时省略 `apiKey`；触碰后留空时发送 `""`。不得新增清除按钮，也不得新增关闭确认。
- `connectionChanged = presetId/providerKind/baseUrl 变化，或 apiKeyTouched`。只改名称、说明、启停调用普通 PUT；连接变化调用连接 PUT。

### 3.3 读取 DTO

| DTO | 字段 |
| --- | --- |
| `ModelRead` | `id`, `providerId`, `modelKey`, `displayName`, `tagsJson`, `contextWindow`, `enabled`, `description`, `createdAt`, `updatedAt` |
| `ModelProviderRead` | `id`, `name`, `presetId`, `providerKind`, `baseUrl`, `apiKeyConfigured:boolean`, `enabled`, `description`, `models:ModelRead[]`, `connectionStatus`, `lastCheckedAt`, `lastCheckLatencyMs`, `lastCheckMessage`, `createdAt`, `updatedAt` |
| `ModelProviderListRead` | `items:ModelProviderRead[]`, `total:number` |
| `RemoteModel` | `modelKey`, `displayName`, `ownedBy:string|null`, `contextWindow:number|null` |
| `ModelDiscoveryRead` | `ok:true`, `items:RemoteModel[]`, `total:number`, `latencyMs:number`, `endpoint:string`, `message:string` |
| `ModelTestRead` | `ok:true`, `modelKey`, `latencyMs:number`, `outputPreview:string`, `reasoningPreview:string`, `message:string` |
| `ModelOption` | `id`, `providerId`, `providerName`, `modelKey`, `displayName`, `tagsJson` |
| `ModelOptionListRead` | `items:ModelOption[]`, `total:number` |

`ModelProviderRead` **不得**包含 `apiKey` 或 `secretRef`。`apiKeyConfigured` 只表示 SQLite 中该供应商的 `secret_ref` 非 null；列表和详情读取不得为计算此值而读取系统凭据。可选密钥供应商为 false 是合法状态。若 SQLite 有引用但凭据实际不存在或不可读，读取 DTO 仍为 true；需要凭据的操作返回 `CREDENTIAL_STORE_UNAVAILABLE`，且不把引用值暴露给 Renderer。

`endpoint` 只用于用户理解本次访问目标，必须脱敏：仅保留 scheme、host、显式 port 与 path；删除 userinfo、query 和 fragment。不得返回 Gemini 的 `key` 参数。

## 4. Base URL 与外部请求约束

### 4.1 URL 校验

- 解析后的 scheme 只能为 `http` 或 `https`，host 必须非空；保存时去掉首尾空白和末尾 `/`。
- 允许 `localhost`、`127.0.0.0/8` 和 `::1`，以支持 Ollama；也允许用户明确配置的其他私网或公网主机。
- 拒绝 URL userinfo、fragment，以及认证型 query 参数。认证型参数至少包括大小写不敏感的 `key`、`api_key`、`apikey`、`token`、`access_token`、`authorization`、`password`。Gemini 的 `key` 只能由 adapter 在发送请求时从 CredentialStore 注入。
- 默认 URL：OpenAI `https://api.openai.com/v1`、Anthropic `https://api.anthropic.com/v1`、Gemini `https://generativelanguage.googleapis.com/v1beta`；没有默认值且请求未给有效 Base URL 时返回 422。默认补全仅为内部 API 容错；旧 UI 仍要求服务地址非空才允许测试，不据此放开按钮。

### 4.2 请求行为

- 目录请求 timeout 为 15 秒；模型生成测试 timeout 为 30 秒。
- 2026-09-12 baseline客户端整合（confirmed，来源：实际API客户端与慢响应测试）：前端模型外部操作使用60秒总预算，覆盖目录读取、接入、连接更新、供应商测试与模型生成；本地CRUD沿用共享客户端10秒默认值。后端上述HTTP超时配置不变。
- `httpx.AsyncClient(trust_env=False, follow_redirects=False)`；任何 3xx 都作为远端请求失败处理，绝不把认证信息跟随到新地址。
- OpenAI/OpenAI-compatible：目录 `GET {baseUrl}/models`，测试 `POST {baseUrl}/chat/completions`。
- Anthropic：目录 `GET {baseUrl}/models?limit=1000`，测试 `POST {baseUrl}/messages`，使用 `x-api-key`、`anthropic-version: 2023-06-01`。
- Gemini：目录 `GET {baseUrl}/models?pageSize=1000&key=...`，测试 `POST {baseUrl}/models/{url-encoded-modelKey}:generateContent?key=...`。
- Qwen 目录沿用旧适配特例：保留用户 Base URL 的 scheme/host/port，将 path 改为 `/api/v1/models` 并设置 `page_size=500`；默认地址对应 dashscope.aliyuncs.com。生成仍走所填 Base URL，不硬编码到官方 host。
- 对 OpenAI-compatible/custom/Ollama，密钥为空时完全省略 `Authorization`；禁止发送无效的 `Authorization: Bearer `。Anthropic/Gemini 必须有密钥才构造请求。
- 模型测试提示词固定为 `只回复 OK`，最大输出 16 tokens，不流式传输。OpenAI 官方使用 `max_completion_tokens`，OpenAI-compatible 使用 `max_tokens`，Anthropic 使用 `max_tokens`，Gemini 使用 `generationConfig.maxOutputTokens`。
- `outputPreview` 最多 240 个 Unicode 字符，`reasoningPreview` 最多 2000 个 Unicode 字符。只读取各协议明确响应字段，不按模型名、标签或返回文本推断能力。
- 外部响应解码后最多 8 MiB（8 × 1024 × 1024 bytes），目录和生成一致；使用流式累计读取，在解析 JSON 前超限即返回 MODEL_PROVIDER_RESPONSE_INVALID，不创建新页面状态；错误响应只保留映射后的状态和脱敏消息，不持久化或回传原始 body。

## 5. 路由清单与副作用

以下 14 条路由是首版完整集合。不存在 `POST /model-providers`。

| # | 方法与路径 | 请求 | 成功响应 | SQLite/凭据副作用 |
| --- | --- | --- | --- | --- |
| 1 | `GET /api/v1/model-providers` | 无 | 200 `ModelProviderListRead` | 无 |
| 2 | `POST /api/v1/model-providers/connection-preview` | `ModelProviderCreateInput` | 200 `ModelDiscoveryRead` | 只用请求内候选密钥访问目录；不保存供应商、模型、密钥或状态 |
| 3 | `POST /api/v1/model-providers/connect` | `ModelProviderConnectInput` | 201 `ModelProviderRead` | 重新读取目录、验证全部选择后，按第 7 节保存凭据，并以一次最终 SQLite 事务公开供应商和 0–500 个模型；状态 connected |
| 4 | `GET /api/v1/model-providers/{providerId}` | 无 | 200 `ModelProviderRead` | 无 |
| 5 | `POST /api/v1/model-providers/{providerId}/test` | 无请求体 | 200 `ModelDiscoveryRead` | 使用已保存配置读取目录；成功和失败均提交最近连接状态，失败仍返回对应错误信封 |
| 6 | `GET /api/v1/model-providers/{providerId}/models/discover` | 无 | 200 `ModelDiscoveryRead` | 读取远端目录；不改变连接状态、不修改本地模型 |
| 7 | `POST /api/v1/model-providers/{providerId}/models/test` | `ModelTestInput` | 200 `ModelTestRead` | 发起一次真实短生成；不持久化模型健康、输出、推理内容或连接状态 |
| 8 | `PUT /api/v1/model-providers/{providerId}` | `ModelProviderMetadataUpdateInput` | 200 `ModelProviderRead` | 只更新名称、说明、启停；不访问远端、不改变连接状态 |
| 9 | `PUT /api/v1/model-providers/{providerId}/connection` | `ModelProviderConnectionUpdateInput` | 200 `ModelProviderRead` | 用候选配置读取目录；成功后按第 7 节原子公开新配置并置 connected；失败完整保留旧配置与旧凭据 |
| 10 | `DELETE /api/v1/model-providers/{providerId}` | 无 | 204 空响应 | 一个 SQLite 事务删除供应商、级联模型并登记旧凭据清理；提交后尝试清理凭据 |
| 11 | `POST /api/v1/model-providers/{providerId}/models` | `ModelInput` | 201 `ModelRead` | 仅添加本地模型，不要求模型出现在远端目录 |
| 12 | `PUT /api/v1/models/{modelId}` | `ModelInput` | 200 `ModelRead` | 全量替换模型可编辑字段；`modelKey` 必须与已存值相同，否则 422 VALIDATION_ERROR 绑定 modelKey；`providerId` 不可更改 |
| 13 | `DELETE /api/v1/models/{modelId}` | 无 | 204 空响应 | 只删除本地模型，不调用供应商远端删除 |
| 14 | `GET /api/v1/models/options` | 无 | 200 `ModelOptionListRead` | 无；只返回 `provider.enabled && model.enabled` 的模型 |

路径参数不存在时，供应商路由返回 `MODEL_PROVIDER_NOT_FOUND`，模型路由返回 `MODEL_NOT_FOUND`。路由 5 的失败状态持久化必须在抛出映射错误前单独提交；路由 2、6、7 的任何结果均不得改变持久状态。对已保存供应商的长请求先捕获连接快照和 updated_at；最终事务内比较，记录删除返回404、记录有较新修改返回409 MODEL_PROVIDER_CHANGED。POST test 成功和失败都比较；连接更新若已写新 Key 而比较失败，新引用的清理记录保留供补偿。不得把旧测试结果或旧metadata写回覆盖。

`connect` 允许 `selectedModels=[]`。它必须按 trim 后、大小写敏感的 `modelKey` 与最终重新发现的目录精确匹配；任何选中项缺失时返回 409 `MODEL_PROVIDER_MODEL_NOT_DISCOVERED`，`details.modelKeys` 为缺失值，且不公开供应商、模型或密钥。远端目录的 `contextWindow` 只在请求模型值为 null 且远端值合法时补入。

## 6. 错误映射

| HTTP | 错误码 | 触发与 UI 行为 |
| --- | --- | --- |
| 401 | `SIDECAR_UNAUTHORIZED` | 本地实例令牌缺失/失效；重新握手，不把它显示为供应商密钥错误 |
| 409 | `MODEL_PROVIDER_AUTH_FAILED` | 外部 401/403；保留当前表单或对象，提示检查 API Key |
| 404 | `MODEL_PROVIDER_NOT_FOUND` | 供应商已不存在；在当前窗口保留错误/草稿并刷新列表，不擅自自动关闭 |
| 404 | `MODEL_NOT_FOUND` | 模型已不存在；在当前窗口保留错误/草稿并刷新列表，不擅自自动关闭 |
| 409 | `MODEL_PROVIDER_EXISTS` | trim 后、大小写敏感的供应商名称冲突；`details.fields.name` 可绑定名称字段 |
| 409 | `MODEL_EXISTS` | 同一供应商内 trim 后、大小写敏感的模型标识冲突；绑定 `modelKey` |
| 409 | `MODEL_PROVIDER_CHANGED` | 长请求期间供应商已被更新；保留当前草稿，刷新本地列表，由用户再次提交，不覆盖较新记录 |
| 409 | `MODEL_PROVIDER_MODEL_NOT_DISCOVERED` | 最终保存时选择已从最新目录消失；返回 `details.modelKeys:string[]` |
| 409 | `MODEL_PROVIDER_ENDPOINT_NOT_FOUND` | 外部 404；检查 Base URL 或模型标识 |
| 409 | `MODEL_PROVIDER_RATE_LIMITED` | 外部 429；可透传有效 `Retry-After` 为 `details.retryAfterSeconds`，不伪造倒计时 |
| 409 | `MODEL_PROVIDER_REQUEST_FAILED` | 外部其他 3xx/4xx/5xx；只返回 `details.status`，不返回 body |
| 409 | `MODEL_PROVIDER_RESPONSE_INVALID` | JSON 或协议结构不符合已支持格式 |
| 409 | `MODEL_PROVIDER_UNREACHABLE` | DNS、连接、TLS 等请求错误；不回传底层异常文本 |
| 422 | `VALIDATION_ERROR` | Pydantic/领域字段校验；使用 `details.fields:{camelCaseField:message}`，额外字段同样归此错误 |
| 422 | `MODEL_PROVIDER_BASE_URL_REQUIRED` | 无默认 URL 且 Base URL 为空 |
| 422 | `MODEL_PROVIDER_API_KEY_REQUIRED` | 必填预设没有可用候选密钥，或试图对必填预设清空密钥 |
| 422 | `MODEL_PROVIDER_BASE_URL_INVALID` | scheme、host、userinfo、fragment 或认证 query 不合约 |
| 503 | `CREDENTIAL_STORE_UNAVAILABLE` | 系统凭据读取/写入不可用，或应存在的凭据缺失；禁止明文降级 |
| 504 | `MODEL_PROVIDER_TIMEOUT` | 目录 15 秒或生成 30 秒超时；mutation 不自动重试 |

错误中的 `endpoint` 与 URL 细节必须先按第 3.3 节脱敏。远端认证错误沿用旧项目的 409，与本地实例令牌 401 区分。外部 403 也映射为认证失败，因为该适配层无法可靠区分无权限与密钥无效；这是首版明确语义。

## 7. 凭据、事务与恢复

### 7.1 持久结构

供应商表保存 nullable、唯一的 `secret_ref`，该字段不进入 OpenAPI。`secretRef` 必须由密码学安全随机源生成，带模型域前缀，并且不能从 provider ID、名称、预设或 Key 推导；删除后永不复用，也不得在供应商之间共享。

新增小型持久表 `model_credential_cleanup`：

| 字段 | 约束 |
| --- | --- |
| `secret_ref` | 主键，随机引用 |
| `created_at` | UTC 时间 |

该表只是一份待清理引用集合，不保存秘密、provider ID、请求体或外部响应。清理器删除前必须再次查询供应商表：任何仍被供应商引用的 `secret_ref` 都不得删除，只保留记录等待后续恢复/人工排查。

### 7.2 新建或替换凭据

候选连接必须先用请求内密钥（或编辑时读取的现有密钥）完成远端验证。验证失败不写 CredentialStore，也不修改 SQLite 可见业务状态。

需要写入新密钥时严格按以下顺序：

1. 生成新的、不可复用的 `newRef`。
2. 在独立 SQLite 事务中插入 `model_credential_cleanup(newRef)` 并提交。
3. 调用 `CredentialStore.write(newRef, keyBytes)`。失败则保留清理记录，返回 503；不公开供应商变更。
4. 在一个最终 SQLite 事务中保存/更新供应商及模型，令供应商引用 `newRef`，删除 `newRef` 的清理意图；若是替换，同时插入旧引用的清理意图，然后提交。
5. 提交后尝试删除旧引用；成功后删除其清理记录。失败则保留清理记录供下次启动恢复，不回滚已经公开的新配置。

若第 4 步失败，`newRef` 的清理意图仍存在，启动恢复会删除孤立凭据。最终 SQLite 事务是供应商与模型对 Renderer 的唯一可见提交点。

编辑连接但省略 `apiKey` 时，验证和最终更新沿用旧 `secretRef`，不创建新引用。对可选密钥预设发送 `apiKey:""` 时，候选验证不带认证头；成功后最终事务把 `secret_ref` 置 null 并把旧引用加入清理表。对必填预设发送空值在远端调用前返回 422。

### 7.3 删除与启动恢复

删除供应商时，在一个 SQLite 事务中完成供应商删除、模型级联删除和旧引用清理登记。事务提交后尝试 `CredentialStore.delete(oldRef)`：

- 删除成功：删除清理记录。
- 系统凭据删除失败：保留清理记录并记录不含秘密的结构化告警；本地供应商删除仍返回 204。

应用启动时只遍历 `model_credential_cleanup` 中的引用。每条都先检查当前供应商引用：仍被引用则绝不删除；未被引用才尝试删除并在成功后清除记录。运行时补偿也只能处理当前命令明确登记的引用，不扫描或删除 CredentialStore 中的其他键。

CredentialStore 不可用时不得把 Key 回退到 SQLite、JSON、环境变量或日志。预览和测试请求中的明文只在进程内短暂存在，完成后释放引用；OpenAPI 标记 writeOnly，Renderer 不把它放入 query cache、localStorage、错误对象或测试快照。

## 8. 前端 ApiClient、查询与失效

### 8.1 依赖与生成类型

- 在 `apps/desktop` 实施时添加 `@tanstack/react-query`，版本范围沿用来源 ^5.90.2，保持 Query 5 语义；锁文件记录实际解析版本。
- 继续使用 `apps/desktop/src/renderer/shared/api/client.ts` 的 fetch request 封装和仓库现有 OpenAPI 生成流程。扩展现有 `ApiClient` 域方法或建立薄的 model API 模块；不复制旧 `openapi-fetch` 客户端。
- 生成 DTO 是 TypeScript 契约来源，不手写一套重复响应类型。
- `ApiClient.request` 解析统一错误信封、处理 204，并只在有 JSON body 时解析。密钥请求对象不得保存到缓存或错误详情。向导 mutation 不把含 Key body 传入 variables；使用短生命周期闭包，完成后 reset、卸载后 gcTime=0，清除请求草稿引用。

### 8.2 Query keys 与默认行为

Query key 必须包含当前 sidecar `instanceId`，防止重启后沿用旧进程缓存：

```ts
['model-providers', instanceId]
['model-provider-discovery', instanceId, providerId]
['model-options', instanceId]
```

- 供应商列表和模型选项是本地 SQLite 查询，可按页面需要读取。
- discovery `staleTime: 30_000`、`retry: false`。
- 所有 mutation `retry: false`。
- 窗口重新获得焦点不得自动触发外部目录调用；discovery 显式设置 `refetchOnWindowFocus: false`。
- “同步并添加”先使对应 discovery key 失效，再打开/读取目录；普通“添加模型”可以使用 30 秒内缓存。用户明确测试连接时始终调用 mutation，不把普通 query refetch 当成测试。

连接更新 mutation 开始前取消对应 discovery query；queryFn 透传 AbortSignal，不支持中断的请求按世代丢弃。更新成功后再 invalidate，防止旧目录晚回覆盖新连接缓存。必须在向导切片中覆盖该竞态。

### 8.3 Mutation 失效矩阵

| 成功操作 | 必须 invalidate/remove 的缓存 |
| --- | --- |
| `connect` | invalidate 供应商列表、模型选项；移除本次临时预览状态 |
| 普通供应商更新 | invalidate 供应商列表和模型选项（名称与启用均影响 options） |
| 连接更新 | invalidate 供应商列表、模型选项与该供应商 discovery |
| 已保存供应商测试（成功或失败） | invalidate 供应商列表；测试结果作为本次页面 FeedbackCard 数据，不写 query 中的持久健康模型 |
| 添加/更新/删除模型 | invalidate 供应商列表和模型选项 |
| 删除供应商 | invalidate 供应商列表和模型选项；remove 该供应商 discovery |
| 发现目录 | 只更新该供应商 discovery；不改供应商列表 |
| 模型测试 | 不失效持久查询；结果仅留当前页面 FeedbackCard 或 Modal 会话，不能跨供应商/窗口串入 |

当 `instanceId` 变化时，组件切换到新 key；旧实例 key 不再渲染，并可统一 remove。请求期间关闭 Modal 只遵循已确认旧交互：连接测试/保存锁定；模型测试允许关闭且结果不得写回后来打开的新 Modal。

## 9. 复用来源与必须改写部分

### 9.1 可复用

- `backend/src/autoflow/model_provider_service.py`：协议分支、远端目录归一化、短生成请求和显式响应字段提取可迁移为 provider adapter 的起点。
- `backend/src/autoflow/schemas.py`：字段名称、旧长度限制、标签归一化和 camelCase 基类可作为 DTO 参考。
- `backend/src/autoflow/api.py`：14 路由的用户可见语义、连接状态副作用、最终接入目录复验、级联删除和 options 双层启停过滤可作为应用服务验收依据。
- `src/renderer/features/models/model-api.ts` 与 `ProviderWizard.tsx`：操作拆分、Wizard 步骤和 mutation 调用意图可复用；页面布局以已确认原型为准。
- `backend/tests/test_model_provider_service.py`：`httpx.MockTransport` 的 OpenAI-compatible、Anthropic、Gemini 与认证失败测试模式可迁移。
- `backend/tests/test_models.py`：预览不落库、最终接入原子、连接更新失败保留旧配置、测试状态持久化、级联删除与 enabled options 场景可改造成新契约测试。

### 9.2 禁止原样复制

- 旧 ORM 的明文 `api_key` 列、`ModelProviderRead` 回传密钥和测试中的明文读取断言。
- 旧 `POST /model-providers` 未测试直建路由。
- 普通 PUT 接受连接字段并可绕过远端验证的 DTO。
- `selectedModels` 的 casefold 去重与数据库大小写敏感唯一之间的不一致。
- 空 Key 仍发送 `Authorization: Bearer `。
- `httpx` 默认 `trust_env=True` 和旧实现 `follow_redirects=True`。
- 向错误 `details` 放外部 response body、完整 URL 或底层异常字符串。
- 任何 capabilities、价格、额度、P95、成功率、长期健康或模型名称推断。

## 10. 测试与验收

### 10.1 后端契约测试

至少覆盖：

1. OpenAPI 只有上述 14 条模型路由；不存在直接创建路由；所有 JSON 字段 camelCase。
2. 所有 Provider 读取响应没有 `apiKey`/`secretRef`，只有正确的 `apiKeyConfigured`。
3. 统一错误信封、本地401与远端认证409区分、camelCase `details.fields`、验证错误不含密钥 input。
4. 新建允许零模型；最终复验缺失模型时无供应商、模型和孤立凭据可见。
5. 名称和模型标识 trim 后大小写敏感唯一；connect、添加、更新完全一致。
6. `contextWindow` 接受 null 和 JS 安全正整数，拒绝边界外及错误类型。
7. 普通 PUT 多传任一连接字段返回 422；连接 PUT 的 omitted/nonempty/empty/null 四种密钥语义。
8. 连接更新验证失败保留旧字段、旧状态和旧凭据；成功替换后旧引用进入可恢复清理。
9. `/test` 成功与失败都更新状态；discover 和模型测试完全不更新状态。
10. 供应商删除级联模型；凭据删除失败仍返回 204，清理记录可在启动恢复后消失。
11. 清理器绝不删除仍被任一供应商引用的 ref，也不扫描未登记 ref。
12. `/models/options` 同时过滤停用供应商和停用模型；204 客户端不解析 JSON。

### 10.2 Provider adapter 隔离测试

测试文件为 `apps/backend/tests/unit/test_model_provider.py`；使用计划任务3定义的 MockTransport handler 与显式注入的 HttpModelProvider。每个场景必须断言调用次数、实际请求、结果或错误，不能只确认函数被调用：

| 合成输入 | 必须断言 |
| --- | --- |
| Ollama，空 Key，302 Location 指向另一 host | 原请求不含 Authorization；只调用一次；MODEL_PROVIDER_REQUEST_FAILED；不访问 Location |
| OpenAI/compatible、Anthropic、Gemini/Qwen 目录样本 | 路径、认证方式、参数和归一化字段符合 §4；Qwen 保留自定义 host |
| 构造客户端 | spy 断言 trust_env=False、follow_redirects=False 与15/30秒 timeout；MockTransport 成功不是环境代理配置证据 |
| JSON无效/超过8MiB/错误结构/超时 | 对应响应无效或超时码；无原始 body、Key、URL query进入错误/日志 |
| 短生成正文及思考长样本 | 提示与16tokens参数正确；输出/思考最多240/2000字符；无能力推断 |

所有值为合成夹具，不访问真实供应商。

### 10.3 应用服务故障注入

测试文件为 `apps/backend/tests/unit/test_model_service.py` 与 `tests/integration/test_model_repository.py`。MemoryCredentialStore 和可控远端 helper 显式导入 `tests/fixtures/model_management.py`，接口及 app fixture 定义见实施计划任务3。清理表仅包含 secret_ref/created_at，不要求 reason 列。

| 失败点 | SQLite可见状态与清理断言 |
| --- | --- |
| 候选远端验证失败 | 原供应商/凭据不变，无新引用意图 |
| 新凭据写入失败 | 原供应商/凭据不变，新引用有清理记录，返回503 |
| 最终DB事务或并发比较失败 | 原供应商/模型/旧引用不变；newRef清理记录仍在，不能部分成功 |
| 提交后旧凭据删除失败 | 新配置已生效或供应商已删除；旧引用记录仍在，启动可再次清理 |
| 应用重启 | 仅处理登记且未引用的ref；仍在使用的ref永不删；成功删除后清记录 |
| 测试晚于更新/删除返回 | 不写入旧连接检查；分别409 MODEL_PROVIDER_CHANGED或404 |

断言的是 SQLite 原子可见性、凭据引用集合和恢复能力，不假设跨存储 ACID。

### 10.4 前端测试

- ProviderWizard 编辑态：密钥输入初始空且呈现已配置状态；untouched 提交省略 `apiKey`；touched 空提交 `""`；必填预设由后端 422 回绑字段。
- 连接签名只因协议、Base URL、预设或 `apiKeyTouched` 变化；普通字段走 metadata PUT，连接变化走 connection PUT，按钮文案维持已确认交互。
- Query key 包含 `instanceId`；sidecar 重启不显示旧缓存；discovery 30 秒 fresh；窗口聚焦不产生外部请求；mutation 不重试。
- 204 删除成功不抛 JSON parse error；删除供应商后清除其 discovery，并刷新 providers/options。
- 模型测试关闭 Modal 后的迟到响应不污染下一次编辑会话；测试结果不进入持久 query cache。

## 11. 完成判据

只有当 OpenAPI/生成类型、后端契约测试、provider adapter mock、CredentialStore 故障注入、前端 ApiClient 与 Query 测试全部通过，才可称内部模型管理契约实现完成。真实目录和模型生成仍须在用户授权后使用专门测试账号逐供应商核验；mock 通过不能升级为线上兼容声明。
