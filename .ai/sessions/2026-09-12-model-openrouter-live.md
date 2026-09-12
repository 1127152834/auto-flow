# OpenRouter 模型管理真实闭环

- 日期：2026-09-12
- 状态：confirmed
- 来源：用户授权 Key 测试；官方 API 文档、实网 HTTP、CUA 桌面操作、隔离 TestClient＋系统凭据存储、自动化回归。
- 分支：`codex/model-openrouter-live`，隔离 worktree，不改并行自动化工作。
- 发现：OpenRouter `/models` 对无认证／错误 Key 仍返回 200；不得据此认定认证成功。已在 OpenRouter discover 前添加同源 `/key` 验证，补齐目录 name/context_length。
- 反馈：模型领域静态中文错误白名单，402 与 429 说明清楚，不回显远端正文。
- 实证：GPT-4o mini 桌面返回 OK；两个免费模型返回 429。隔离实网 25 项通过／14 个接口，原 Key 回滚、生命周期重建、级联删除和两条系统凭据清理均断言通过。后端全量339通过；前端模型39通过；类型、lint、构建通过。
- 秘密：不保存 Key；报告和截图无凭据明文。临时测试记录与系统凭据已清理，当前桌面原有供应商记录保留。
- 限制：本次不证明 Windows、其他供应商、所有远端模型或长推理模型可用。详情见 docs/migration/model-openrouter-live/README.md。
