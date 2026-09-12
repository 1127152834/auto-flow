# AutoFlow 控件统一专项

2026-09-12。源码盘点为 confirmed；设计与计划已获用户确认。独立 worktree 已实施 T0–T2，T3–T13 尚未实施。

1. [源码盘点与迁移决定](2026-09-12-ui-controls-audit.md)
2. [全部 JSX 使用点](2026-09-12-ui-controls-usage.md)
3. [机器清单与文件哈希](2026-09-12-ui-controls-source-inventory.json)
4. [设计规范、组件 API 与验收矩阵](../superpowers/specs/2026-09-12-unified-ui-controls-design.md)
5. [分阶段实施计划](../superpowers/plans/2026-09-12-unified-ui-controls.md)

开发入口为 `#/__ui`，仅 DEV 环境懒加载，包含令牌/密度、RHF 表单和嵌套弹窗验证骨架。用 `npm run build` 后运行 `npm run smoke:ui-controls` 可在独立临时数据目录复验；脚本结束会关闭自己启动的实例。

- [实施基线](verification/baseline.md)
- [令牌验证](verification/tokens.md)
- [G0 浮层兼容与阶段验收](verification/choice-overlay-gate.md)

展示页仅辅助验收；这次结果不能代表五个真实业务入口、Windows 或读屏流程通过。后续仍须完成共享组件状态库、真实页面迁移和 T13 平台矩阵。
