# Studio 后端迁入全局约束

- 日期：2026-09-15。
- 来源：侧对话用户明确四条后端要求，并要求补充成完整约束文档；核对现有范围、后端交接、目录与架构说明。
- 状态：四条用户要求 confirmed；继承合同保持原有效状态；正式规格和实施计划已于 2026-09-15 完成，尚未实施后端。

## 用户明确要求

1. 浏览器仅 CloakBrowser，Studio 消费主应用 Profile。
2. 不开发前端批准范围外的节点；当前有效集合为 227 个入口，以范围文档和能力台账核定。
3. 代码及目录遵循 AutoFlow 既有分层、技术栈与开发规则。
4. 小助手使用 LangGraph 重构编排，不继续用简单模型 API 调用承担完整助手逻辑。

## 唯一正文

[后端全局约束](../../docs/automation-studio/BACKEND_GLOBAL_CONSTRAINTS.md)说明来源优先级、范围与配套边界、源码迁入、目录、合同、LangGraph、生命周期、数据和验收；本记录仅索引，不复制规格。

正式实施入口为[后端迁入规格](../../docs/superpowers/specs/2026-09-15-studio-backend-webrpa-migration-design.md)和[后端迁入计划](../../docs/superpowers/plans/2026-09-15-studio-backend-webrpa-migration-implementation.md)。上游许可证副本为 `LICENSE.WebRPA`。项目负责人已确认在本项目范围内获准使用并迁入 WebRPA 源码；不得把这项确认扩写为具体商业授权或公开发布授权。

LangGraph 负责小助手编排；底层模型仍复用 AutoFlow 模型 provider。工作流执行器不因此改为 LangGraph。排除数据库节点不禁止内部 SQLite；仅 CloakBrowser 不排除其必要控制依赖。以上是四项要求与现有架构的边界解释，具体技术选择仍在后端准备阶段验证。

## 本次变更边界

仅增加上述全局约束正文和本索引。不修改主任务现有文件、生产代码、数据库、运行进程或 git 提交；没有重跑历史验收或宣称后端可用。主任务需将本要求纳入后续规格，历史冲突记录不得覆盖最新用户决定。
