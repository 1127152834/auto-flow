# 项目上下文

- 项目：AutoFlow
- 目标平台：Windows、macOS
- 目标：在新架构中迁移 browser-automation 的功能；项目管理现处于完整设计与计划阶段，之后分批实现。
- WebRPA：仅作为能力和实现思路参考，重写能力，不做运行时集成或兼容层。
- 前端视觉方向：保留第三个原型的暖灰画布、黏土棕强调色；2026-09-12 用户明确浏览器配置采用单主内容区，无模块侧栏，内核管理从配置表单以弹窗进入。早期该模块“分栏工作台”的描述已 superseded。
- 前端技术约束：React、shadcn/ui、Tailwind CSS，组件先于页面。
- 协作要求：先规格和实施计划，经确认后再开始功能实现；前后端按垂直功能切片一起开发。
- 2026-09-12（confirmed，来源：用户在项目管理审查后的明确纠正）：项目管理先形成相对完整的功能规格、跨模块业务规则、交互和总体实施计划，再小步开发。最小执行链仅是实施验收步骤；关键业务设计不留到各切片开发时临时决定。详见 `.ai/decisions/2026-09-12-project-management-complete-design-first.md`。
- 2026-09-12（confirmed，来源：用户对数据流与环境保留的明确说明）：每表系统维护业务状态；记录再次使用由当前状态和工作流条件决定，不能加消费类型或本批历史排除。工作流可读写多表、增删记录与字段/列，显式决定业务状态变化。结束节点“保留当前环境”包含保存登录上下文并关联相关数据行，不要求额外 Bind 节点。具体关联范围、冲突和恢复为设计推荐；见 `.ai/decisions/2026-09-12-project-data-workflow-semantics.md` 和 `docs/project-management/design/README.md`。此前冲突建议已 superseded。
- 2026-09-12（confirmed，来源：用户明确实施指令）：代理模块已从 `codex/proxy-management@0ad2fd2` 选择性接入浏览器主线；全局导航和浏览器启动到代理组的调用仍由后续浏览器任务完成。详见 `docs/migration/proxy-management-status.md`。

- 2026-09-12（confirmed，来源：本轮用户授权及隔离worktree验收）：模型管理在 `codex/model-management` / `../autoflow-model-management` 实现，已通过baseline合并验收；保留旧供应商左栏、三步接入与split编辑，凭据仅写系统存储。验收边界见 `docs/migration/model-management-verification.md`。

- 2026-09-12（confirmed，来源：用户合并指令与隔离合并测试）：模型与代理迁移通过0003_merge_proxy_models汇合；不得改写两边已存在的0002版本。接入浏览器客户端06153ca及代理预算修复4a91407后，304个后端、128个前端测试通过，合并边界见docs/migration/model-management-baseline-merge.md。

- 2026-09-12（confirmed，来源：浏览器计划 Task1–10 独立复审及源代码）：浏览器 UI 使用 desktop shared shadcn/Radix + Tailwind、领域组件、RHF/Zod；查询上下文统一 ApiProvider。同一工作区重连保留编辑树，实际换目录才重置。CloakBrowser wrapper 固定0.5.9，只有其内核能力；后端 worker 处理下载与取消，License 使用共享系统凭据存储。最终页面/平台状态见 docs/migration/browser-management-validation.md。

- 2026-09-12（confirmed，来源：授权实网、脱敏 fixture 和 CUA）：ProxyPanel 列表/凭据/到期字段已接通；SOCKS5 检测通过，HTTP CONNECT 实网超时。数据面密码按需取用且不落库，API Key 保留系统存储。旧“列表一律拒绝”的限制 superseded；远程管理写操作仍未实现。见 docs/migration/proxypanel-live-verification.md。
