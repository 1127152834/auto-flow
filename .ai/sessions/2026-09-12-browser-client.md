# 浏览器资源客户端与内核事件会话

- 日期：2026-09-12
- 状态：confirmed
- 来源：浏览器管理任务 7；桌面端 74 项测试、OpenAPI 漂移检查、TypeScript、ESLint、构建及后端定向契约验证。

renderer 通过独立 `ApiProvider` 为每个 sidecar `instanceId` 建立 QueryClient；查询键以实例 ID 开头，实例切换时旧 SSE 连接被取消，迟到事件不得写入新会话。profiles、proxy options 和 kernels 使用生成 DTO 的固定 facade，所有 mutation 禁止自动重试。

共享客户端保留代理模块的 204 与 snake_case `ApiError`，同时消费浏览器接口独立生成的 camelCase `BrowserApiError`。普通请求超时覆盖响应正文解析；内核 provider RPC 相关读取及 ProxyPanel 连接、换 Key、同步、探测使用 60 秒预算，其余本地 CRUD 使用默认 10 秒。SSE 使用认证 fetch、仅建连超时和调用方 AbortSignal，按 1/2/5 秒退避重连，每次依赖服务端首帧全量快照恢复，不重放写命令；终态只在状态首次转入 completed/cancelled/failed 时通知。
