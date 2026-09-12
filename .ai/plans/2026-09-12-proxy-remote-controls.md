# ProxyPanel 位置与轮换计划索引

- 日期：2026-09-12
- 状态：proposed，待用户确认；仅完成设计和只读核验。
- 规格：docs/superpowers/specs/2026-09-12-proxy-remote-controls-design.md
- 实施：docs/superpowers/plans/2026-09-12-proxy-remote-controls-implementation.md
- 来源：用户“我需要实现，你思考一下如何实现”；官方 Developers/IP rotation 指南、当前源码与授权只读 GET。
- 关键事实：官方 mode 为 same_city/same_city_carriers/full_pool，请求单位为 interval_minutes；计划由供应商服务端执行。当前 4 条 active 代理详情均为 rotation_available=false、bound=false、not_bound；一个空计划 GET 返回 schedule=null。未执行任何真实远程写入。
- 待解决：当前代理写入前置条件、非空计划与命令最终响应；不能把 not_bound 自动等价为暂停、旧产品或永久不支持。现有 operation 表尚无完整执行与轮询，需一并补齐。
