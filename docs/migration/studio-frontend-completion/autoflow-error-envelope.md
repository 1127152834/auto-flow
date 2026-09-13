# F1 复用 AutoFlow 错误包

2026-09-14；从共享 ApiClient 提取原有错误包解析函数，两处复用，主窗口错误行为不变。Studio 保留可读 error 字符串，并通过 errorDetails 返回 OpenAPI 生成的 ApiWireError 类型，包含错误码、请求标识、字段信息以及代理操作结果未知状态。未知或损坏错误包不虚构结构信息。旧 WebRPA 错误字符串/FastAPI detail 仍兼容。

新增 12 项（内存/实际 HTTP 各 6 项），先复现标准错误包丢失 10 项失败；与旧业务错误及主应用 API 客户端回归共 51 项通过，类型/lint/构建通过。仅解析现有正式协议，未实现 Studio 真实后端或声称全部 142 项服务契约已冻结。证据：evidence/f1-autoflow-errors。
