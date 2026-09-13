# Studio 正式认证传输适配器

2026-09-14；confirmed（适配器协议测试）。createStudioHttpTransport 使用宿主提供的 token，仅向固定同源服务发送 X-AutoFlow-Token；清除旧 WebRPA token，禁用重定向和环境 Cookie，保留正文/文件字节/SSE/取消。复用连接 origin 校验，不改全局 fetch，不存 token。17 项适配器与连接测试、类型/lint/构建/脚本通过。开发入口仍使用 Mock；F5 宿主上下文尚待接入，不宣称正式自动化后端已可用。见 docs/migration/studio-frontend-completion/authenticated-transport.md。
