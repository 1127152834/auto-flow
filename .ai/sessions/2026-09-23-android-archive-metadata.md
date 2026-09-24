# 安卓归档安全与文件属性增量

- 日期：2026-09-23。
- 状态：confirmed（本增量）；完整目标 active/partial。
- 来源：隔离分支 `codex/android-management-complete@233c09dd` 的代码与实际命令；完整证据见 `docs/qa/android-management/2026-09-23-archive-verification.md`。
- 修复：归档全图路径/链接验证、恢复 -a 保留 UID/GID、摘要与实际恢复复用同一字节、实时备份状态检查、源设备防覆盖。
- RED：归档/恢复 11 failed；额外状态/源保护 2 failed。GREEN：Android unit/contract/integration + migration heads 314 passed。定向 Ruff、compileall、Node22 OpenAPI generate/check、结构4项通过。
- 真实：源 ef626943-e3d0-4ac5-b84b-c66a65799115 → 新目标 c9af9887-4d5b-4e62-bfed-94a75e5f893b，UID10001/GID2000/mode0640 与安全链接归档往返一致；目标启动后3路径读回正确，源测试条目未变；两个容器/卷均清理0。前两轮仅实验准备失败，原始记录保留。
- 限制：xattrs、恢复中断和发布耐久性仍待办；全量 backend/Ruff/frontend/scripts 失败尚未解决，未宣称完整通过。无新迁移或 API 形状变更，3个既有 Studio 文档未覆盖。
