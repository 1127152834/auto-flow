# 项目上下文

- 项目：AutoFlow
- 目标平台：Windows、macOS
- 目标：在新架构中迁移 browser-automation 的非项目管理功能。
- WebRPA：仅作为能力和实现思路参考，重写能力，不做运行时集成或兼容层。
- 前端视觉方向：已选择第三个原型，暖灰画布、黏土棕强调色、分栏工作台。
- 前端技术约束：React、shadcn/ui、Tailwind CSS，组件先于页面。
- 协作要求：先规格和实施计划，经确认后再开始功能实现；前后端按垂直功能切片一起开发。
- 2026-09-12（confirmed，来源：用户明确实施指令）：代理模块已从 `codex/proxy-management@0ad2fd2` 选择性接入浏览器主线；全局导航和浏览器启动到代理组的调用仍由后续浏览器任务完成。详见 `docs/migration/proxy-management-status.md`。

- 2026-09-12（confirmed，来源：本轮用户授权及隔离worktree验收）：模型管理在 `codex/model-management` / `../autoflow-model-management` 实现，已通过baseline合并验收；保留旧供应商左栏、三步接入与split编辑，凭据仅写系统存储。验收边界见 `docs/migration/model-management-verification.md`。

- 2026-09-12（confirmed，来源：用户合并指令与隔离合并测试）：模型与代理迁移通过0003_merge_proxy_models汇合；不得改写两边已存在的0002版本。接入浏览器客户端06153ca及代理预算修复4a91407后，304个后端、128个前端测试通过，合并边界见docs/migration/model-management-baseline-merge.md。
