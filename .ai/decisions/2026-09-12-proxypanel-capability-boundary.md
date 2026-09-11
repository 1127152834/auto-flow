# ProxyPanel 能力边界与到期指标

- 日期：2026-09-12
- 状态：confirmed（文档核验）；live schema 仍待脱敏 fixture 验证
- 来源：ProxyPanel 官方首页、已登录 Developers/Documentation 页面、旧项目代理源码和规格审查。

## 决定

AutoFlow 只把 ProxyPanel 远程代理投影到本地，并维护独立的本地代理组。远程代理状态、位置、凭据、轮换和白名单必须经过 Provider capability flag 与脱敏 fixture 验证后才可在 UI 中启用。

“即将到期”不是可推导指标。只有响应明确提供 `expires_at`/订阅截止时间、字段语义经过 fixture 验证时才渲染；否则隐藏或显示“到期信息不可用”。余额、套餐和自动续费不能推导到期日。

API key 与数据面密码只在 sidecar/CredentialStore 中处理。renderer 只获得脱敏状态，复制密码由 sidecar 受控写入系统剪贴板并返回 `copied`，不返回明文。

## 取舍

这会让第一版 UI 少显示一部分账户指标，但避免把 Provider 尚未证明的字段伪装成事实。购买、续费、支付和账户团队管理不纳入第一版。

## 验证入口

- `docs/references/proxypanel-api-contract.md`
- `docs/superpowers/specs/2026-09-12-proxy-management-design.md`
- `docs/superpowers/plans/2026-09-12-proxy-management-implementation.md`
