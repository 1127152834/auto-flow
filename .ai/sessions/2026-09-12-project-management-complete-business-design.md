# 项目管理完整业务设计

- 日期：2026-09-12。
- 状态：proposed 设计已成稿；用户明确业务原则为 confirmed，尚未进入实施。
- 工作区：`autoflow-project-management-design`，分支 `codex/project-management-design`；主项目与旧项目只读。
- 输入：用户本轮状态/多表 CRUD/环境保留说明，旧提交 `324748a` 的源码与设计；主线初始 `2faf2a0`、交付前核对为 `4e3f059`，Studio 空窗口已提交，自动化后端仍未实现。独立 Studio/控件工作稿按实际状态区分。

## 交付

- [完整设计入口](../../docs/project-management/design/README.md)，包含完整功能、数据状态、传递契约、执行与环境四份配套规格；功能条目、状态/异常规则与验收场景可追踪。
- 新业务原则写入 [ADR](../decisions/2026-09-12-project-data-workflow-semantics.md)，总规格与项目记忆同步。历史审查快照原样保留；冲突建议通过 ADR 明确 superseded。
- 三名智能体分别完成产品功能、数据语义、执行与环境设计；主审负责数据传递、来源核对和跨文档整合。最终审查只修复会产生行为冲突的缺口。
- 明确无消费类型/本批去重；并发排他不改变业务复用规则；End 保留为保存与关联组合，部分失败保留事实，修复不重跑网页或改历史 Run 终态。
- 独立流程关联、空白本地表、单表 XLSX 导出与失败后便捷入口给出推荐边界，不能写成用户已逐项批准。

## 验证与限制

本轮验证限文档与来源：本地链接、编号、占位符/冲突语义检查、源码及旧契约身份、Git 变更范围与空白。详细结果见 [核验记录](../../docs/project-management/design/design-verification.json)。未运行业务、真实 Sheets、应用界面或 Windows/macOS 测试。

## 下一步

用户整体审阅完整设计后，使用 Superpowers `writing-plans` 编写覆盖全部确认功能的总体实施计划及依赖明确的子计划；验收 ID 映射到组件、后端契约、联调与真实应用检查。小步实现不缩减已确认的完整模块范围。
