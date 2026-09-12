# ProxyPanel 能力边界与到期指标

- 日期：2026-09-12
- 状态：confirmed；2026-09-12 用户批准实施，位置与轮换能力边界已按用户批准的设计更新
- 来源：ProxyPanel 官方首页、已登录 Developers/Documentation 页面、旧项目代理源码和规格审查。

## 决定

AutoFlow 只把 ProxyPanel 远程代理投影到本地，并维护独立的本地代理组。远程代理状态、位置、凭据、轮换和白名单必须经过真实响应核验和 Provider capability flag 后才可在 UI 中启用。原“没有真实 API 响应样本、列表一律拒绝”结论于同日 superseded：已取得用户授权的列表和按需凭据响应，脱敏样本通过契约测试，SOCKS5 通过实网。只启用 remote_status、subscription_expiry 和有效代理 credentials；人工 synthetic 样例不得提升其他能力证据等级。详见 `docs/migration/proxypanel-live-verification.md`。

“即将到期”不是可推导指标。只有响应明确提供 `expires_at`/订阅截止时间、字段语义经过 fixture 验证时才渲染；否则隐藏或显示“到期信息不可用”。余额、套餐和自动续费不能推导到期日。

API Key 首次录入/替换会短暂经过 renderer 表单，提交/关闭后清空。持久化使用原生 macOS/Windows CredentialStore；数据面 password 不返回 renderer。复制由受限 Electron main IPC 完成，main 经独立 host token 取密后写入剪贴板，仅返回 copied。此前“Key 永不进入 renderer、Python 直接复制”的表述为 superseded。原生存储和主进程复制已在隔离环境完成单元/契约验证，跨平台打包验收仍须 CI。

数据面用户名/密码由 `ProxyCredentialLoader` 在复制或探测时按需读取，只在该操作内存中使用；不持久化端点密码。读取后校验投影 revision、连接 generation/secret_ref 和端点一致性，拒绝过时结果。API Key 的系统存储方式不变。

## 取舍

这会让第一版 UI 少显示一部分账户指标，但避免把 Provider 尚未证明的字段伪装成事实。购买、续费、支付和账户团队管理不纳入第一版。

## 验证入口

- `docs/references/proxypanel-api-contract.md`
- `docs/superpowers/specs/2026-09-12-proxy-management-design.md`
- `docs/superpowers/plans/2026-09-12-proxy-management-implementation.md`

## 位置与轮换实施更新（2026-09-12，confirmed）

旧“所有远程写入必须 evidence=fixture-verified 才能启用”门槛对本次批准的四种操作标记为 superseded。实现已按官方 v1 接通，evidence 仍保留 confirmed-authenticated-doc；available 依据实际运行状态与各操作独立条件决定。自动测试不提升实网证据等级。当前 rotation_available=false / not_bound 只阻止即时 rotate，不推断 relocate/schedule 同样不可调用；服务器明确拒绝始终有效。不调用 start，不改变购买/续费/白名单边界。

远程命令通过 SQLite 唯一键登记、每代理互斥、受监管 asyncio 单次发送、只读确认。应用重启不会重发；未确认的结果保持 unknown，用户可以重新核实或显式结束核实。API Key 不进任务记录，只有内部 secret_ref 用于拒绝连接替换后的旧结果。

真实地点目录存在同 location_id 多城市别名；以目标 ID 分组、容量不累加、显示覆盖城市。切换结果必须满足新 generation、目标覆盖城市、国家与运营商匹配；不保证精确到别名城市。计划使用官方 mode 和 interval_minutes；只显示经文档/当前页面确认的 5/10/30/60 分钟编辑选项，不推算 next_run。

验证与未完成的实网写入验收见 docs/migration/proxy-remote-controls-verification.md。
