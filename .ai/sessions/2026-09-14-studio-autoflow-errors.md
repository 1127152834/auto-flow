# Studio 对接主应用错误协议

2026-09-14；confirmed。复用 shared/api/client.ts 的原有 ApiWireError 解析；Studio apiRequest 在非 2xx 时保留结构化错误并显示其中消息。类型来自既有 generated.ts。12 新用例与主应用/旧业务包回归共 51 项通过，TypeScript/ESLint/构建通过。详见 docs/migration/studio-frontend-completion/autoflow-error-envelope.md。
