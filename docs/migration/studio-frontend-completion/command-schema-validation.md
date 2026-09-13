# F1 命令公共字段的唯一 schema

2026-09-14，confirmed。沿用 AutoFlow 已有 proxy_openapi 的模型发布方式，workflow_studio_schemas.py 定义 StudioCommandReceipt/StudioCommandLookup，统一注入正式 OpenAPI 和 schema-only 导出。scripts/generate-api.mjs 生成 shared/api/generated.ts；StudioEventClient 直接引用生成类型并在网络边界检查未知输入。未增加自动化运行路由、数据库表、worker 或业务执行。

命令公共字段：commandId 为非空且非全空白字符串；success 必须布尔值。只读查询额外要求 httpStatus 为200–599整数。命令专有结果字段暂按已存在的兼容扩展保留，不将它们冒充完整 typed payload。成功包络不等于网页动作已应用；终态继续取服务事件。

19个新增Python契约用例，含正反例及仅发布模型不注册业务路由；加原schema导出3项，共22通过。后端全量421通过，Ruff通过，mypy128文件通过。前端命令相关36通过，类型/lint/构建、OpenAPI一致性和17脚本检查通过。最近前端全量125文件/1453用例为此类型接入之前的上一批结果，未冒称本批重新跑过全量。证据 evidence/f1-command-schema。

下一步继续覆盖各服务操作输入/输出及事件业务字段；当前只是公共命令包络，完整API路径/operation矩阵、全部payload、会话身份/修订等仍未冻结，F1未完成。
