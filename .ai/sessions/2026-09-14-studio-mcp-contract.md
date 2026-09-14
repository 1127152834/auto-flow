# MCP 文本与服务契约

2026-09-14；有界 verified。文本无静默丢行、旧传输兼容、生成 DTO 和共享 guard、扩展字段无损保存、Mock 重连部分失败与状态一致。专项84、DTO29、工程检查和构建通过；中间全量2880通过但不包含随后19项新增合同/表单用例。实际IAB验证输入错误/取消和 Mock 部分重连失败，最终测试项禁用。

详见 docs/migration/studio-frontend-completion/mcp-service-contract.md 与 mcp-text-validation.md。F0–F6仍未整批完成，继续其他配置服务与运行交互。
