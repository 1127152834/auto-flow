# Studio F4 拾取会话

日期：2026-09-15。状态：confirmed 本切片，整体继续实施。

来源：用户持续实施 F0–F6 授权；原代码对照、内存与 HTTP 协议、组件测试及浏览器 UI。

已实现稳定 sessionId、同参数启动幂等、结果与停止隔离、丢响应查询、未知启动保留清理入口、连接代次保护，以及外部关闭后面板退出拾取模式。使用现有 API 传输边界和生成 OpenAPI 类型，无新依赖。中文单语言与 284 个保留节点范围不变。

验证及实际边界见 docs/migration/studio-frontend-completion/picker-session-validation.md。真实后端浏览器未实施；录制会话、宿主离开与 F6 尚未关闭。保留其他任务的模型/UI/教学文档未提交改动。
