# 项目上下文

- 项目：AutoFlow
- 目标平台：Windows、macOS
- 目标：在新架构中迁移 browser-automation 的非项目管理功能。
- WebRPA：仅作为能力和实现思路参考，重写能力，不做运行时集成或兼容层。
- 前端视觉方向：已选择第三个原型，暖灰画布、黏土棕强调色、分栏工作台。
- 前端技术约束：React、shadcn/ui、Tailwind CSS，组件先于页面。
- 协作要求：先规格和实施计划，经确认后再开始功能实现；前后端按垂直功能切片一起开发。

- 2026-09-12（confirmed，来源：本轮用户授权及隔离worktree验收）：模型管理在 `codex/model-management` / `../autoflow-model-management` 实现，后续再合并；保留旧供应商左栏、三步接入与split编辑，凭据仅写系统存储。验收边界见 `docs/migration/model-management-verification.md`。
