# 前端完整交付与后端交接边界

- 日期：2026-09-13
- 状态：confirmed；用户已确认实施，当前按用例推进，F0–F6 未全部验收
- 来源：用户要求前端先完成全部保留节点的配置、交互、业务规则与配套工具，之后仅开发后端。

以 690f13f 的当前 284 个动作入口建立保留清单；不得继续凭泛化“Web-only”删掉剩余能力。已删除节点的专属配置/工具应清理，共享能力按依赖保留。

通过冻结 schema、状态机、契约测试及非内存 HTTP/SSE 夹具验证前端独立性。后端接入不应再要求补页面/Store/工具功能；真实联调缺陷或新需求走明确变更。前端验收与真实执行/进程/持久化验收分别记账。

正式设计与 F0–F6 计划：`docs/superpowers/specs/2026-09-13-studio-frontend-completion-design.md`。

- 文档已拆分：specs/2026-09-13-studio-frontend-completion-design.md 为正式规格；plans/2026-09-13-studio-frontend-completion-implementation.md 为逐任务计划。该文档阶段状态已于2026-09-14被实施状态替代（superseded）；当前逐项结果以 docs/migration/studio-frontend-completion/acceptance.md 及 verified-cases.json 为准。

- 2026-09-14：公共命令包络已通过现有 OpenAPI 生成链发布，真实自动化业务仍未加入。见 command-schema-validation.md；不得将局部 schema 当作 F1 全部冻结。
