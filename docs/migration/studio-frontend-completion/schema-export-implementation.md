# F1 契约导出基础设施切片

日期：2026-09-13；状态：本切片已实现并验证；依据已授权F1.2。

当前generate-api.mjs通过启动完整sidecar再抓/openapi.json生成类型，触发目录、迁移和运行恢复。改为显式schema-only入口，复用与正式app相同的路由注册函数。路由DTO、错误定义和OpenAPI扩展仍由现有adapters维护，不复制接口清单、不维护第二份schema。

导出时仅提供拒绝任何业务调用的占位依赖，用于绑定路由闭包；不能提供假业务返回值，不能启动监听端口、worker、数据库、凭据或迁移。占位依赖若被路由注册意外调用，立即失败。导出函数只返回schema，不把占位app作为可服务应用暴露。

验收：schema-only与正式create_app的OpenAPI完整相等；导出不调用create_app；CLI stdout为单一JSON；生成现有generated.ts内容不变（或明确审查差异）；后端相关pytest/Ruff/mypy、脚本测试、OpenAPI一致性及前端类型检查通过。此切片不表示Studio全部142个服务操作已冻结，后续继续添加真实DTO与消费映射。


## 实测结果

- schema-only 与正式应用完整 OpenAPI 相等；CLI 单一 JSON、无运行初始化，共 3 项契约测试通过。
- 完整后端：402 passed；Ruff 通过；mypy 126 个源文件无问题。
- `npm run openapi:check` 通过，既有 generated.ts 没有变化。
- `npm run test:scripts`：16 passed；前端 TypeScript 通过。
- 证据：`evidence/f1-schema-export.txt`。本次没有运行新的浏览器或正式 Electron 用例，不将这些工程检查算作端到端通过。
