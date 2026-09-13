# F1 AutoFlow HTTP/SSE 认证传输

2026-09-14；实施范围：正式传输适配器及协议测试，Studio 开发入口继续明确使用 Mock。

同一个适配器供 API、命令、SSE、上传和二进制读取使用。宿主提供服务 origin 和本次连接 token；适配器使用 AutoFlow 的 X-AutoFlow-Token，不读旧 WebRPA 远程凭据，不持久化 token，不拼入 URL。仅允许已配置的同源请求，拒绝重定向，保留请求方法、正文、上传字节、调用方取消信号和服务状态码。

测试门槛：内存与实际本地 HTTP 使用相同认证/JSON/上传断言；跨源输入不调用底层传输；重定向不把 token 带到第二个服务；SSE 逐字节消费且取消可中断。现有 Mock 组合不改成调用尚未实现的正式自动化后端。宿主运行上下文和工作区切换接入仍由 F5 完成，不能把适配器通过记作正式后端已接通。

验证结果：8 项适配器用例加现有连接组合回归共 17 项通过；TypeScript、ESLint、renderer/main/preload 构建、17 项脚本检查通过。上传用例使用 Node 原生 Web API 环境和实际 HTTP 解析，保留 Unicode、NUL 字节及 multipart boundary。证据见 evidence/f1-authenticated-transport。
