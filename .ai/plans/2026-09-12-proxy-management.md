# ProxyPanel 代理管理计划索引

- 日期：2026-09-12
- 状态：proposed；用户要求先编写设计方案与实施计划，未批准代码实施
- 来源：用户确认的代理原型、官方页面核验、当前仓库结构和设计复核
- 设计：`docs/superpowers/specs/2026-09-12-proxy-management-design.md`
- API：`docs/references/proxypanel-api-contract.md`
- 正式计划：`docs/superpowers/plans/2026-09-12-proxy-management-implementation.md`
- 波次：A 契约/共享组件/凭据基础 → B 连接同步 → C 健康详情 → D 本地组与浏览器引用 → E 逐项验证远程操作。
- 协作：gpt-5.6-sol 后端/前端组件并行；主代理拥有装配、迁移注册、OpenAPI 生成和全局样式；每个切片前后端与测试共同验收。
- 阻塞边界：真实 API 样本缺失不阻塞本地内部设计，但 Provider 状态仍为未验证；synthetic 示例不能打开能力。
- 验证：文档链接、路径、语义一致性和 diff-check；不以旧文档/原型示例承诺即将到期。
