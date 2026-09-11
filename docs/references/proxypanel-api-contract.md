# ProxyPanel API 与开发契约

- 日期：2026-09-12
- 状态：proposed；供规格审查，不代表接口已实现
- 关联：[设计方案](../superpowers/specs/2026-09-12-proxy-management-design.md)、[实施计划](../superpowers/plans/2026-09-12-proxy-management-implementation.md)
- 来源：[Developers](https://proxypanel.io/developers)、[登录后使用指南](https://proxypanel.io/docs)、[产品页](https://proxypanel.io/)、[旧版文档](https://proxypanel.io/documentation)

## 1. 证据与当前可交付程度

已通过官方页面确认能力及新 API 路径；**没有真实 API Key 调用记录或 live response fixture**。下表的外部路径是文档依据，不是已经联调通过的契约。外部 JSON 字段、状态枚举、分页、配额、错误结构和异步完成语义，必须由真实响应确认。

证据分开记录，不能混用：

| 证据 | 意义 | 能否用于宣称接入完成 |
| --- | --- | --- |
| confirmed-public | 官方公开产品/旧文档描述能力 | 否，只证明产品能力 |
| confirmed-authenticated-doc | 已登录 Developers 页面列出新 API | 否，不能证明响应结构 |
| fixture-verified | 用户授权真实调用的脱敏样本通过字段审查和契约测试 | 可证明已核验的具体调用；写入最终效果仍需验收 |
| synthetic | 人工构造的内部示例、异常或 UI 测试数据 | 否，不提升 Provider 证据等级 |
| unknown | 缺少依据或存在版本冲突 | 否，操作关闭、数值留空 |

`Capability` 是服务端计算结果，不能由 renderer 或 synthetic fixture 打开。读取和写入分别核验；列表读取成功不代表换 IP、白名单编辑等写操作可用。

## 2. ProxyPanel 外部接口清单

新基址：`https://proxypanel.io/api/v1`，认证：`Authorization: Bearer <API_KEY>`。URL 和认证方式来自登录后文档。只允许该官方来源，禁止跟随跨源重定向携带认证头。旧版将 Key 放入 URL 的接口不作为运行时回退路径。

| 本地 Provider 方法 | 外部方法与路径 | 开发前需核验 |
| --- | --- | --- |
| list_proxies | GET /proxies | items 包装、分页、稳定 ID、是否完整、total |
| get_proxy | GET /proxies/{id} | status、位置、端点、到期字段是否存在及语义 |
| probe_proxy | GET /proxies/{id}?probe=true | 探测状态和出口 IP；不可据此假定返回延迟 |
| get_credentials | GET /proxies/{id}/credentials | username/password、HTTP/SOCKS5 端点、权限 |
| rotate_credentials | POST /proxies/{id}/credentials/rotate | 新密码返回和恢复策略；禁止自动重发 |
| change_ip | POST /proxies/{id}/rotate | 限流、是否异步、完成判据 |
| relocate | POST /proxies/{id}/relocate | body 中位置标识、随机模式、最终完成判据 |
| list_locations | GET /locations | 地点 ID、城市、运营商、可用性；不假定有地点延迟 |
| get_rotation_schedule | GET /proxies/{id}/rotation-schedule | 模式、间隔单位、未设置的表示 |
| set_rotation_schedule | PUT /proxies/{id}/rotation-schedule | 同城/随机/保持运营商模式映射、合法间隔 |
| delete_rotation_schedule | DELETE /proxies/{id}/rotation-schedule | 关闭轮换的结果与读取确认 |
| get_ip_allowlist | GET /proxies/{id}/ip-auth | 是否启用、IPv4 列表、端点 |
| set_ip_allowlist | PUT /proxies/{id}/ip-auth | 参数名、覆盖语义、上限；文档所示 16 条待请求验证 |
| delete_ip_allowlist | DELETE /proxies/{id}/ip-auth | 禁用与清空是否等价，不能猜测 |
| get_usage | GET /proxies/{id}/usage | since/until、单位、时间区间、计数语义 |
| get_account_summary | GET /balance | 币种、金额、返回包装；不得推导到期日 |

认证验证复用无副作用的 `GET /proxies`；不新增臆测的远程 `/verify` 接口，不用换 IP 验证 Key。

轮换限制存在版本差异：旧文档写最小 180 秒、地点切换 3 分钟；产品页描述 5–60 分钟，登录文档中的 one-hit URL 描述每代理 60 秒。它们是不同接口/场景，**不能统一写死为 REST API 的 60 秒限制**。服务端只返回已验证的约束；未知时轮换表单不可提交。

## 3. AutoFlow 内部约定

以下字段名、限制和 HTTP 状态是 **AutoFlow 的设计选择**，不是 ProxyPanel 原始字段。外部映射由 adapter 完成。

- Renderer API 前缀 `/api/v1`，复用 `x-autoflow-token`；只访问本地 sidecar。
- ID 使用本地 UUID 字符串；Provider ID 原样作为内部关联键，不让页面构造外部路径。
- 时间使用 RFC 3339 UTC；展示层按用户时区格式化。未知值为 `null`，不填 0。
- 可修改资源包含递增 `revision`；更新请求包含 `expected_revision`，冲突返回 409。
- 资源 GET 返回 200；本地新建返回 201；删除返回 204；命令返回 200 或 202。
- 非成功响应统一为 `{error: ApiError}`。异常内容按允许字段构造，不把 Provider 原始 body/URL/headers 透传。
- 列表先用本地 `offset`（默认 0）与 `limit`（默认 50，上限 100），顺序固定为创建时间、ID。响应 `{items, offset, limit, matched_count}`，`matched_count` 只表示已同步投影中的筛选结果数量。

### 公共模型

| 模型 | 必填字段（`?` 表示 nullable） |
| --- | --- |
| ApiError | code:string, message:string, request_id:string, field_errors:object, retry_after_seconds:int?, outcome_unknown:bool |
| Capability | key:string, available:bool, evidence:上述证据值, reason:string?, constraints:object |
| ConnectionView | id, name, has_secret:bool, status:unconfigured/verifying/connected/failed, revision:int, last_verified_at:datetime?, last_synced_at:datetime?, last_error:ApiError?, capabilities:Capability[] |
| SyncSnapshot | last_synced_at:datetime?, stale:bool, completeness:complete/partial/unknown, synced_count:int, provider_total:int?, remote_missing_count:int, last_error:ApiError? |
| ProxyView | id, connection_id, name, name_override:string?, enabled:bool, remote_status:string?, remote_missing:bool, carrier:string?, city:string?, region:string?, exit_ip:string?, http_endpoint:Endpoint?, socks5_endpoint:Endpoint?, credential_available:bool, health:HealthSnapshot, subscription_expires_at:datetime?, last_synced_at:datetime?, stale:bool, revision:int, reference_count:int, capabilities:Capability[] |
| Endpoint | host:string, port:int；不含用户名、密码或认证 URL |
| HealthSnapshot | state:untested/checking/healthy/unhealthy, latency_ms:number?, exit_ip:string?, checked_at:datetime?, source:local_probe/provider_probe/none, error:ApiError? |
| LocationView | id:string, city:string, region:string?, carrier:string?, availability:available/unavailable/unknown；不提供未经测量的地点延迟 |
| GroupView | id, name, description, member_ids:string[]（有序且不重复）, revision:int, reference_count:int, created_at, updated_at |
| RotationSchedule | enabled:bool, mode:same_city/random_city/same_carrier/null, interval_seconds:int?；合法值以已验证 constraints 为准 |
| IpAllowlist | enabled:bool, ipv4s:string[]；不支持 hostname、CIDR 或 IPv6 |
| CredentialView | credential_available:bool, username:string?, can_copy:bool, can_rotate:bool；不含密码 |

### 连接与同步

| 方法与路径 | 请求 | 响应/规则 |
| --- | --- | --- |
| GET /proxy-panel/connections | 无 | `{items: ConnectionView[]}`；UI 首版只显示当前连接，不做多账号聚合仪表盘 |
| POST /proxy-panel/connections | `{name, api_key}` | 201 ConnectionView；name trim 后 1–120 字符；api_key 非空，按凭据处理 |
| PATCH /proxy-panel/connections/{id} | `{expected_revision, name?}` | 200 ConnectionView；至少一项变更 |
| PUT /proxy-panel/connections/{id}/api-key | `{expected_revision, api_key}` | 验证新 Key 后原子替换 secret ref；失败保留原 Key；成功使旧投影 stale |
| DELETE /proxy-panel/connections/{id} | 无 | 204；本地断开，绝不删除远程代理；有 profile/group 引用时 409 并返回引用数量 |
| POST /proxy-panel/connections/{id}/verify | `{}` | ActionResult；只读远程验证，成功不表示全部 capability 已验证 |
| POST /proxy-panel/connections/{id}/sync | `{}` | ActionResult；结果为 SyncSnapshot |
| GET /proxy-panel/connections/{id}/locations | `q?, carrier?, refresh=false` | `{items: LocationView[], fetched_at:datetime?, stale:bool}` |
| GET /proxy-panel/connections/{id}/account-summary | 无 | `{balance:string?, currency:string?, fetched_at:datetime?}`；十进制字符串；能力未验证则不可用 |

### 代理读取与操作

| 方法与路径 | 请求 | 响应/规则 |
| --- | --- | --- |
| GET /proxies | `connection_id?, q?, carrier?, city?, health?, enabled?, offset?, limit?` | Page<ProxyView>；搜索本地名称、城市、运营商、出口 IP |
| GET /proxies/{id} | 无 | ProxyView；默认读投影，远程刷新通过命令触发 |
| PATCH /proxies/{id} | `{expected_revision, name_override?, enabled?}` | ProxyView；本地元信息，不创建/修改远程代理；名称 null 恢复远程名称 |
| GET /proxies/{id}/references | 无 | `{profiles:[{id,name}], groups:[{id,name}]}` |
| POST /proxies/{id}/probe | `{protocol:http/socks5}` | ActionResult<HealthSnapshot>；默认 http |
| POST /proxies/{id}/change-ip | `{expected_revision}` | ActionResult<ProxyView>；UI 提示现有会话可能短暂重连 |
| POST /proxies/{id}/relocate | `{expected_revision, location_id}` | ActionResult<ProxyView>；location_id 必须属于当前已验证目录 |
| GET /proxies/{id}/rotation-schedule | 无 | RotationSchedule |
| PUT /proxies/{id}/rotation-schedule | `{expected_revision, mode, interval_seconds}` | ActionResult<RotationSchedule>；模式/间隔必须通过已验证 constraints |
| DELETE /proxies/{id}/rotation-schedule | 无 | ActionResult<RotationSchedule>；成功后 enabled=false |
| GET /proxies/{id}/ip-auth | 无 | IpAllowlist |
| PUT /proxies/{id}/ip-auth | `{expected_revision, enabled, ipv4s}` | ActionResult<IpAllowlist>；覆盖集合；IPv4 去重；启用时至少 1 条，上限来自已验证约束 |
| GET /proxies/{id}/credentials | 无 | CredentialView；不返回明文密码 |
| POST /proxies/{id}/credentials/rotate | `{expected_revision}` | ActionResult<CredentialView>；先落入凭据库再报告完成；不可盲目重试 |
| GET /proxies/{id}/usage | `since, until` | `{available:bool, unit:string?, total:number?, points:[{at,value}], fetched_at:datetime?}`；since<until，最长 31 天是本地限制 |

白名单禁用统一由内部 PUT enabled=false 表达；外部使用 PUT 还是 DELETE 必须在 adapter 阶段确认。用量缺失时 `available=false, total=null, points=[]`；不自动合成请求次数、配额百分比或趋势图。

### 本地代理组和浏览器引用

| 方法与路径 | 请求 | 响应/规则 |
| --- | --- | --- |
| GET /proxy-groups | `q?, offset?, limit?` | Page<GroupView> |
| POST /proxy-groups | `{name, description, member_ids, acknowledge_risk:false}` | 201 GroupView；名称 1–120 字符，描述最多 1000 字符 |
| GET /proxy-groups/{id} | 无 | GroupView |
| PUT /proxy-groups/{id} | `{expected_revision, name, description, member_ids, acknowledge_risk:false}` | GroupView；全量替换本地可编辑字段与成员顺序 |
| DELETE /proxy-groups/{id} | 无 | 204；被浏览器引用时 409 PROXY_GROUP_IN_USE |
| GET /proxy-groups/{id}/references | 无 | `{profiles:[{id,name}]}` |

第一次提交包含未检测/异常成员时返回 409 `PROXY_MEMBER_RISK_CONFIRMATION_REQUIRED` 与成员 ID，不写库；用户确认后携带相同 revision 与 `acknowledge_risk=true` 重提。缺失成员、重复 ID、remote_missing 成员始终拒绝，风险确认不能绕过。

浏览器配置继续使用当前 `proxy_mode=none|proxy|pool`、`proxy_id`、`proxy_pool_id`；`proxy_pool_id` 对应本地 GroupView.id。业务展示统一称“本地代理组”。在数据库迁移中升级当前代理/代理池占位表，不再平行建立另一套可选代理模型。

选择代理属于启动用例：`resolve_proxy_for_profile(profile_id)`，不新增可从 renderer 推进游标的 `/select` HTTP API。后端事务读取成员顺序，跳过 disabled、remote_missing、最近检测失败或凭据不可用的成员，返回一个代理并原子推进游标；同一启动请求重复执行不得推进两次。未检测成员允许选中，但启动前必须探测；探测失败按有界成员集合继续，不无限循环。全不可用返回 `PROXY_GROUP_NO_AVAILABLE_MEMBER`，不得静默直连。

## 4. 命令、轮询与错误

ActionResult：`{status: completed|accepted|failed, operation_id: UUID|null, resource: object|null, error: ApiError|null}`。本地简单 CRUD 直接返回资源，不包 ActionResult。

远程命令与同步使用 `Idempotency-Key`（UUID）。服务端以命令类型、目标 ID、规范请求体摘要和 Key 去重；相同 Key 不同请求返回 409。该键只实现 AutoFlow 内部去重，不代表 ProxyPanel 支持幂等。幂等记录保留 24 小时；密码/API Key 不写入摘要输入日志或持久化命令体。

`GET /proxy-operations/{id}` 返回 `{id, kind, target_id, status, resource_revision, error, created_at, updated_at}`。状态为 queued/running/succeeded/failed/unknown；外部仅确认接收时仍为 running，不能 Toast“成功”。

- Renderer 前台以 1s、2s、5s 逐步间隔查询；隐藏窗口暂停，重新打开后读取现状；终态停止。
- 服务端最长观察 120 秒（本地策略）；超时或进程退出造成结果不明时进入 unknown，展示“结果未确认，请刷新状态”。不自动重放远程写入。
- 同一代理仅一个远程变更运行；冲突返回 409。连接同步另设单飞锁，重复请求复用进行中的 operation。
- 首版无远程取消接口。关闭抽屉只停止查看；提交确认框提交过程中不可关闭，命令受理后可关闭详情。
- 429 有 Retry-After 时按有效秒数/日期解析；没有则不伪造服务端倒计时，提示稍后手动重试。只读 GET 最多两次有界退避；变更请求不自动重试。

| HTTP | 内部错误码 | UI 处理 |
| --- | --- | --- |
| 401 | SIDECAR_UNAUTHORIZED | 恢复本地连接握手 |
| 409 | PROXYPANEL_NOT_CONFIGURED / PROXY_IN_USE / PROXY_GROUP_IN_USE / STALE_PROJECTION / OPERATION_IN_PROGRESS / PROXY_GROUP_NO_AVAILABLE_MEMBER | 根据 code 显示连接、引用、刷新或成员修复入口 |
| 409 | PROXY_MEMBER_RISK_CONFIRMATION_REQUIRED | 展示具体成员与二次确认 |
| 422 | VALIDATION_ERROR | field_errors 绑定表单字段 |
| 404 | RESOURCE_NOT_FOUND | 关闭已消失资源的编辑入口并刷新 |
| 429 | PROXYPANEL_RATE_LIMITED | 禁用重复提交，展示可用的重试时间 |
| 502 | PROXYPANEL_AUTH_FAILED / PROXYPANEL_NOT_FOUND / PROXYPANEL_CONFLICT / PROXYPANEL_VALIDATION_ERROR / PROXYPANEL_SCHEMA_UNSUPPORTED | 保留本地数据，显示脱敏原因 |
| 503 | PROXYPANEL_UNAVAILABLE / CREDENTIAL_STORE_UNAVAILABLE / CAPABILITY_UNAVAILABLE | 显示不可用状态，不假装成功 |
| 504 | PROXYPANEL_OUTCOME_UNKNOWN | 不自动重试；刷新远程状态确认 |

## 5. 敏感值与桌面接口

API Key 首次录入/替换会短暂存在 renderer 表单内存；提交请求后或关闭后清空，不进入 query cache、localStorage、日志和读取响应。数据面 password 不进入 renderer。

`CredentialStore` 已接入浏览器主线。端口位于 `domain/credentials.py`，平台实现位于 `infrastructure/credentials/`；SQLite 只存 secret_ref，sidecar 应用服务才解析明文。凭据库不可用时返回明确错误，禁止明文文件降级。

复制使用受限 preload 方法 `copyProxyCredentials({proxyId, protocol, format: username|password|url}) → {copied:true}`：

1. Electron main 校验 sender 是当前应用窗口，参数为受控枚举；禁止输入 URL/任意 secret_ref。
2. main 调用专用 `POST /internal/proxy-credentials/resolve`，请求 `{proxy_id, protocol, format}`，响应 `{value:string}`；独立 host token 仅存于 main 与 sidecar，不复用暴露给 renderer 的 instance token。
3. 该端点不进入 renderer OpenAPI，响应 no-store，明文仅短暂经过 sidecar/main；main 调用 Electron clipboard 写入，renderer 只收到成功状态。
4. 30 秒后，仅当剪贴板仍是本次内容时清除，不覆盖用户后续复制。复制失败不得 Toast 成功。

host token 启动与鉴权约定：Electron main 用密码学随机源生成 32 字节随机值，每次 sidecar 启动轮换；通过仅该子进程的 `AUTOFLOW_HOST_TOKEN` 环境变量传入，不写磁盘、不进入 ready 输出/preload 状态。main 请求设置 `x-autoflow-host-token`，sidecar 以常量时间比较；token 未配置或不匹配统一 401。`/internal/*` 单独执行这层检查，不能依赖现有仅覆盖 `/api/v1/*` 的 middleware。仍只绑定 loopback；内部路由设置 `include_in_schema=false`，禁止对 renderer 提供 CORS 许可，禁用请求/响应 body 日志。CORS 不是鉴权替代品。

普通 renderer API 的 CORS 仅新增 `Idempotency-Key` 等明确所需 header，不允许 `x-autoflow-host-token`。`{copied:true}` 和复制请求类型归 main/preload IPC 定义，不注册到 renderer OpenAPI；OpenAPI 只含 CredentialView。

Key 请求字段为 writeOnly/SecretStr 语义；Pydantic/FastAPI 校验错误必须去掉敏感 input，防止自动 422 响应或验证日志回显 Key。上述 host token、IPC 与凭据库已接入浏览器主线并通过本机整合测试；跨平台实际验证状态见 `docs/migration/proxy-management-status.md`。

B0 普通只读采样限列表/详情已有的 credential_available 等元信息；不因“读接口”而默认采集 credentials 明文。只有用户明确连接并使用代理或点击复制等已授权功能时，后端才按需读取凭据，原始用户名/密码不得进入 fixture。当前文档工作不触发该流程。Provider 变更现场测试另需明确测试代理和授权操作。

## 6. 开发资料与验收样本清单

将来样本落点 `apps/backend/tests/fixtures/proxypanel/`。每个真实样本必须记录：来源页面/方法/路径模板、采集日期、读或写权限、HTTP status、字段映射、脱敏方式、完整/部分分页、认证账户的数据范围（不记录身份）。

必须覆盖：空/非空列表、两页列表（若支持）、详情缺可选字段、未知状态、到期字段缺失/有效/无效、地点、轮换、白名单、用量/余额缺失、凭据轮换的一次性结果、401/403/404/409/422/429/5xx、网络超时、写入结果不明。缺少真实场景时 synthetic 样例单独标识，不伪称现场验证。

当前交付是文字契约与样本要求。实际 OpenAPI/Pydantic、生成的 TypeScript 类型、Provider adapter、夹具与测试代码统一在用户批准实施后编写。
