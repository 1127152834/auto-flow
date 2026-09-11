# ProxyPanel 代理模块可行性核验

- 日期：2026-09-12
- 状态：confirmed（已做文档核验）；具体外部 schema 和效果仍为未验证
- 来源：[产品页](https://proxypanel.io/)、[Developers](https://proxypanel.io/developers)、[登录后指南](https://proxypanel.io/docs)、[旧 API 文档](https://proxypanel.io/documentation)、旧项目 ProxiesPage/proxy API/服务测试。
- 实际验证方式：阅读公开页面与已有登录会话中的文档；没有使用真实 API Key 发出请求，没有换 IP、改地点、购买、续费或修改凭据。

## 核验结果

| 能力 | 已有证据 | 尚未证明/落地规则 |
| --- | --- | --- |
| 列表/详情 | 登录文档列出新 `/api/v1/proxies` 与详情接口 | items、分页、ID/状态字段、total 未经真实响应验证；默认“已同步” |
| HTTP/SOCKS5 | 产品页说明支持两种端点；登录文档列出 credentials | 凭据结构需核验；密码不进入 renderer |
| 城市/运营商 | 产品与登录页展示；文档有 locations/relocate | 不证明所有账号返回同一字段或所有位置可用 |
| 换 IP/地点/轮换 | 新文档有相关操作；公开旧文档可旁证产品能力 | body、限额、异步完成语义和成功效果待真实测试 |
| IPv4 白名单 | 新/旧文档均有能力；登录文档描述最多 16 条 | 新请求参数、上限及禁用/清空语义需验证 |
| 远程 probe | 登录文档说明详情支持 probe=true | 不能据此假定返回延迟/丢包；本地 HTTPS 耗时单独测量 |
| 用量/余额 | 登录文档列出 usage/balance | 单位、区间、字段包装未验证；无数据不填零 |
| 即将到期 | 当前无足够字段证据 | 默认隐藏；仅真实明确截止字段核验后开启，不从余额/套餐/自动续费推导 |
| 丢包/地点延迟 | 无可靠证据 | 从第一版移除；HTTP 单次失败不是丢包率 |
| 本地组/排序/引用保护 | 原项目代码与 AutoFlow 本地实现可控 | 本地实体，与 ProxyPanel 位置池分离 |
| 购买/续费 | 文档有能力 | 第一版不做 |

## 需纠正的旧结论

- 早期记录中的 confirmed 表示“文档列出能力”，不表示响应字段或真实调用已确认。字段只有真实调用脱敏并审查后才达到 fixture-verified；synthetic 示例不能作证明。
- 固定 60 秒来自 one-hit URL 场景，旧文档最小 180 秒/地点 3 分钟及产品 5–60 分钟不能套用到所有新 API。
- 原型上的“即将到期 3”“总代理 20”等是条件示意，不是账号真实信息。
- API Key 首次输入必然短暂经过 renderer；“永不进入 renderer”已 superseded。长期持久化只允许系统凭据库；数据面密码通过受限 main IPC 复制。
- Python sidecar 不负责系统剪贴板；该职责归 Electron main。CredentialStore 当前只是目录骨架。

## 实施入口

详细字段与条件见 `docs/references/proxypanel-api-contract.md`；方案和计划状态均为 proposed，等待用户明确实施。缺 Key 时可开发内部结构和本地测试，不能把真实 Provider 接入标记为完成。
