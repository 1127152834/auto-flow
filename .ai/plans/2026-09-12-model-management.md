# 模型管理计划索引

- 日期：2026-09-12
- 状态：confirmed；独立分支实现与本机验收完成，尚未合并
- 来源：用户本轮明确要求设计和实施计划；旧源码与实际页面取证、新仓库基础设施核查。
- 设计：`docs/superpowers/specs/2026-09-12-model-management-design.md`
- API：`docs/references/model-management-api-contract.md`
- 正式计划：`docs/superpowers/plans/2026-09-12-model-management-implementation.md`
- 来源/现状：`.ai/knowledge/2026-09-12-model-management-implementation-readiness.md`
- 波次：契约与共享控件并行 → 供应商接入前后端切片 → 模型编辑/测试切片 → 工作台组合 → 桌面/平台验收。
- 协作：gpt-5.6-sol 可承担有界后端与前端组件；主代理拥有共享文件、依赖、迁移 head、OpenAPI 生成、App 装配和审查。
- 复用：保留旧组件状态机和协议算法，拆入 domains/models；不复制明文 Key、全局 api.py、旧数据迁移或另一套主题。
- 当前完成：14条后端接口、供应商向导、模型编辑器、主工作台、测试、桌面/打包验收；详见 [验收记录](../../docs/migration/model-management-verification.md)。
- 证据边界：原型和旧源码不代表新实现验收，mock 不证明当前线上供应商兼容；Windows/macOS 真实凭据验收在实施中分别记录。

- 文档验证：10 个 Markdown 文件、48 个本地链接、14 条路由、7 个任务、14 份旧源码工作树 SHA-256 检查通过；已完成独立交叉复核并修正交互/DTO/缓存与凭据清理矛盾。仅文档检查，不是业务测试通过。

- 实施隔离：分支 `codex/model-management`，worktree `/Users/zhangtiancheng/Documents/projects/autoflow-model-management`，基点 `ad08bdb`；原目录与 proxy worktree 不修改，合并留到实现完成后。

- 未验证：Windows实机、macOS x64、真实线上供应商；不是本机测试失败，不能以fixture代替。
- 合并事项：原checkout仍在并行推进；合并时串行协调App导航、bootstrap/ORM、Alembic唯一head、依赖锁文件、生成DTO及文档。
