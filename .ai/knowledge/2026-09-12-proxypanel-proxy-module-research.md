# ProxyPanel 代理模块调研

- 日期：2026-09-12
- 状态：confirmed（公开页面和 API 文档验证）；架构建议标记为 proposed
- 验证方式：读取 ProxyPanel 官方首页、开发者 API 页面、旧版文档，并只读检查旧项目 `ProxiesPage.tsx`、proxy API、测试和后端代理服务；未执行购买、轮换、写入或外部账号操作。

## ProxyPanel 已确认能力

来源：

- https://proxypanel.io/home
- https://proxypanel.io/developers
- https://proxypanel.io/documentation

新 API 的控制面基址为 `https://proxypanel.io/api/v1`，使用 Bearer API key；开发者页面说明 key 创建后只显示一次。已确认的能力包括：列出账户代理、读取单代理状态和实时探测、读取/轮换凭据、启动、换 IP、改地点、轮换计划、自动续费、IP 白名单、指纹、用量、地点、余额和子账号。

ProxyPanel 的对象是专用移动代理舰队，而不是用户自建的通用代理池。每个代理拥有状态、运营商、城市、出口 IP、HTTP/SOCKS5 连接信息、凭据、IPv4 白名单和续费信息；一个代理一次只有一个活动出口位置。

旧版文档仍并存，使用 URL 中的 API key、username 和 nickname，并提供换 IP、地点、轮换和 IPv4 白名单操作。AutoFlow 不应把旧版 URL 结构暴露到 UI，也不应同时实现两套控制面契约。

尚未从公开文档确认：新 API 的分页响应、完整错误 schema、通用速率限制和 Retry-After 约定。实现适配器时必须保留 HTTP 状态码和响应体，并对 429 做保守处理，待真实 key 联调验证。

## 旧项目已确认能力

来源：`browser-automation/autoflow-desktop/src/renderer/pages/ProxiesPage.tsx`、`features/proxies/proxy-api.ts`、`backend/src/autoflow/proxy_service.py`、相关测试。

旧项目支持代理 CRUD、HTTP/HTTPS/SOCKS5、批量导入预览、单项健康检测、代理池 CRUD、Round Robin 成员顺序、成员健康摘要、失败成员二次确认、引用保护删除和错误 Toast。

这些交互行为需要保留，但实体边界应改为 ProxyPanel 代理舰队与本地浏览器配置引用，不能继续假设用户可以自由创建任意外部代理。

## proposed 架构方向

- `ProxyPanelConnection`：连接标签、API key secret_ref、验证状态、最近验证时间。
- `ProxyEndpoint`：ProxyPanel proxy id、名称、协议、host/port、endpoint credential secret_ref、运营商、城市、出口 IP、状态、健康结果和启用状态。
- `LocationCatalog`：ProxyPanel 返回的地点/运营商目录缓存。
- `RotationSchedule`：模式、间隔、下次执行状态；后端强制最小间隔。
- `ProxyPool`：仅在产品确实需要本地 Round Robin 时保留；ProxyPanel 的城市池和 AutoFlow 的本地成员池不能混为一个实体。

控制面 API key 与数据面代理密码必须分开存储；SQLite 只存 secret_ref/hasSecret，凭据进入既有 CredentialStore。API key 不能进入 renderer、日志、错误或 OpenAPI 响应，provider adapter 必须对 URL 和异常做脱敏。

默认 UI 以本地缓存投影为 source of truth，ProxyPanel 为控制面 source of truth。连接验证、地点刷新、换 IP、改地点、轮换计划和白名单变更都由 sidecar provider adapter 完成，操作成功后显式刷新本地投影；不做无边界后台轮询。
