# Studio 契约导出基础设施

日期：2026-09-13；状态：本切片 implemented/verified。

已授权 F1.2：正式应用与离线 schema 导出共享路由注册；导出只绑定拒绝业务调用的依赖，不启动 sidecar、迁移或 worker。现有生成类型未变。后端 402 项测试、Ruff、mypy，脚本 16 项测试、OpenAPI 一致性与 TypeScript 通过。证据见 docs/migration/studio-frontend-completion/schema-export-implementation.md。

这不表示 Studio 的 142 个服务操作已经拥有正式后端合同；F1 继续进行。用户要求全量自主推进，完成本切片后继续检查服务消费边界和离开保护，不等待再次确认。
