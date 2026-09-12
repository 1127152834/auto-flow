# ProxyPanel 真实能力补齐

- 日期：2026-09-12
- 状态：confirmed；功能提交 60bc035 已快进合入 codex/architecture-baseline，并在重新启动的正式应用验收。
- 输入：用户报代理无法使用，并要求补齐真实代理能力。
- 根因：Provider 在认证后强制 schema unsupported，缺真实映射和数据面取密；前端失败连接不能重试。
- 完成：按真实返回映射列表/端点/到期时间；按需内存取密及并发校验；HTTP/SOCKS5 显式检测；失败刷新恢复；浏览器可用选项排除过期/失效记录；无新增依赖/迁移。
- 验证：接上 baseline f37a5e1 后 334 后端、268 前端、9 脚本测试；lint/typecheck/mypy/build/OpenAPI 通过。真实账户列表 6 条（4 active / 2 expired），CUA SOCKS5 检测健康；未保存账户身份或凭据。详细证据见 docs/migration/proxypanel-live-verification.md。
- 限制：HTTP CONNECT 超时；没有声称 HTTP 实网通过。远程换 IP、轮换、白名单、用量等尚未实现；浏览器启动执行及 Windows 实机本轮未验收。
- 合并前后原主线其他任务未提交文件哈希一致。CUA 更新前确认当前供应商向导只有第一步选择、无已填写连接内容，正常关闭后更新并重新启动应用。正式代理页同步 6 条，实测一条 SOCKS5 健康（5029 ms）；用户凭据未替换，浏览器配置未修改。
