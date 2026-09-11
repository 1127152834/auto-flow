# 模型管理计划索引

- 日期：2026-09-12
- 状态：in_progress；用户已确认独立分支实施（2026-09-12）
- 来源：用户本轮明确要求设计和实施计划；旧源码与实际页面取证、新仓库基础设施核查。
- 设计：`docs/superpowers/specs/2026-09-12-model-management-design.md`
- API：`docs/references/model-management-api-contract.md`
- 正式计划：`docs/superpowers/plans/2026-09-12-model-management-implementation.md`
- 来源/现状：`.ai/knowledge/2026-09-12-model-management-implementation-readiness.md`
- 波次：契约与共享控件并行 → 供应商接入前后端切片 → 模型编辑/测试切片 → 工作台组合 → 桌面/平台验收。
- 协作：gpt-5.6-sol 可承担有界后端与前端组件；主代理拥有共享文件、依赖、迁移 head、OpenAPI 生成、App 装配和审查。
- 复用：保留旧组件状态机和协议算法，拆入 domains/models；不复制明文 Key、全局 api.py、旧数据迁移或另一套主题。
- 当前完成：可审查开发资料；未开始模型业务实现，未运行尚不存在的模型业务测试。
- 证据边界：原型和旧源码不代表新实现验收，mock 不证明当前线上供应商兼容；Windows/macOS 真实凭据验收在实施中分别记录。

- 文档验证：10 个 Markdown 文件、48 个本地链接、14 条路由、7 个任务、14 份旧源码工作树 SHA-256 检查通过；已完成独立交叉复核并修正交互/DTO/缓存与凭据清理矛盾。仅文档检查，不是业务测试通过。

- 实施隔离：分支 `codex/model-management`，worktree `/Users/zhangtiancheng/Documents/projects/autoflow-model-management`，基点 `ad08bdb`；原目录与 proxy worktree 不修改，合并留到实现完成后。
