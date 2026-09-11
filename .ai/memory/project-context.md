# 项目上下文

- 项目：AutoFlow
- 目标平台：Windows、macOS
- 目标：在新架构中迁移 browser-automation 的非项目管理功能。
- WebRPA：仅作为能力和实现思路参考，重写能力，不做运行时集成或兼容层。
- 前端视觉方向：已选择第三个原型，暖灰画布、黏土棕强调色、分栏工作台。
- 前端技术约束：React、shadcn/ui、Tailwind CSS，组件先于页面。
- 协作要求：先规格和实施计划，经确认后再开始功能实现；前后端按垂直功能切片一起开发。
- 2026-09-12（confirmed，来源：用户明确实施指令）：代理模块已从 `codex/proxy-management@0ad2fd2` 选择性接入浏览器主线；全局导航和浏览器启动到代理组的调用仍由后续浏览器任务完成。详见 `docs/migration/proxy-management-status.md`。
