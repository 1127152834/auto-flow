# ProxyPanel 代理模块可行性核验

- 日期：2026-09-12
- 状态：confirmed（文档核验）；live schema 仍需真实 API key 联调
- 验证方式：读取 ProxyPanel 官方首页、`/developers`、旧版 `/documentation`；对照旧项目 `ProxiesPage.tsx`、proxy API、后端代理服务和测试。没有使用真实 API key，没有执行换 IP、改地点、购买、续费或其他写入操作。

## 能力核验

| 原型能力 | 结论 | 实现边界 |
| --- | --- | --- |
| 代理列表/总量 | confirmed | 新 API 文档列出 `GET /api/v1/proxies`；分页和 total 字段未公开，未确认前只显示返回集合数量，不能承诺服务端总量。 |
| 运行中/待启动/未激活 | confirmed | 使用 ProxyPanel 代理状态；未知状态映射为“状态未知”，不猜测。 |
| 异常 | locally-derived | 由 API 状态异常、实时探测失败、同步失败或本地健康检查失败组合计算；必须标注来源和时间。 |
| 运营商/城市/出口 IP | confirmed | 产品页和开发者 API 页面均展示/支持读取；详情和表格可用。 |
| HTTP/SOCKS5 端点 | confirmed | 通过代理 credentials 能力读取；密码和完整凭据只进入 sidecar 受控复制流程，不返回 renderer。 |
| 延迟/健康 | confirmed | `GET /proxies/{id}?probe=true` 的实时探测能力已在开发者页面说明；延迟和字段 schema 需 fixture/live 联调确认。 |
| Change IP | confirmed | `POST /proxies/{id}/rotate` 或文档对应的轮换能力；有频率限制，不能盲目自动重试。 |
| 改变地点 | confirmed | `POST /proxies/{id}/relocate`；地点目录来自 `GET /locations`。 |
| 轮换计划 | confirmed | `GET/PUT/DELETE /proxies/{id}/rotation-schedule`；模式和参数需要 adapter 校验。 |
| IPv4 白名单 | confirmed | `GET/PUT/DELETE /proxies/{id}/ip-auth`；每代理最多 16 个 IPv4 的限制来自开发者页面。 |
| 用量 | confirmed | `GET /proxies/{id}/usage?since=...&until=...`；返回结构和是否可用于图表仍需联调。 |
| 余额 | confirmed | `GET /balance`；只作为账户摘要，不推导代理到期日。 |
| 即将到期 | conditional | 只有响应含明确 `expires_at`/订阅截止时间且字段语义经 live fixture 验证后才显示；否则隐藏指标或显示“到期信息不可用”。 |
| 续费/购买 | out of scope v1 | 公开文档列出相关端点，但属于支付/账单副作用，字段和确认流程未完成，本阶段不接入写操作。 |
| 分页/速率限制/错误 schema | unknown | 官方公开页面未给完整契约；adapter 需保留状态码、脱敏 body，并处理 429/Retry-After。 |

## 关键决策

1. 只使用新的 `/api/v1` Bearer API；旧版把 key 放在 URL 中的接口只作为兼容资料，不暴露给 UI。
2. ProxyPanel 远程代理舰队与 AutoFlow 本地代理组是两个实体；地点池不是本地代理组。
3. API key 与数据面代理密码分开存储，均使用 CredentialStore；SQLite 只存 secret_ref/has_secret。
4. ProxyPanel 是远程控制面的 source of truth，SQLite 是带同步时间和错误信息的本地投影；不做无界后台轮询。
5. 在真实 key 可用前，所有 provider 响应使用脱敏 fixture；不能把公开页面推测字段写成稳定 schema。
