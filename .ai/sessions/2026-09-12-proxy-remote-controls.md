# 代理位置与轮换实施

- 日期：2026-09-12
- 状态：confirmed；实现/自动测试/只读 UI 验证完成；实网写入未执行。
- 来源：用户批准实施、官方 v1 文档、当前账号授权只读、测试和构建输出。
- 分支：codex/proxy-remote-controls，从 baseline 17e0870 隔离实施。
- 结果：真实远程状态/地点/计划读取，四种命令单次发送与持久化确认，独立领域组件、草稿和确认/恢复交互。SQLite 0004 新迁移；客户端来自 OpenAPI。
- 当前即时 rotate 阻塞是供应商 not_bound，不自动 start。地点与计划依据各自操作条件执行，不泛化 rotation_available。
- 只有只读调用触及真实账号；未更换 IP、切地点或改计划。非空计划与写操作最终响应尚未实网验收。
- 详细验证：docs/migration/proxy-remote-controls-verification.md。未记录凭据、实际用户代理标识或原始认证响应。
