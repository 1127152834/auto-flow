# Studio AI 快照恢复

日期：2026-09-14；状态：confirmed / implemented。

沿已授权 F0–F6 继续处理前端数据保护。restoreSnapshot 默认保留编辑历史，完整克隆并恢复节点、连线、名称和变量；模块退出显式 resetHistory 保留原隔离边界。AI 时间线记录变量且仅在成功返回后登记，回退按钮复用 Store 恢复。取消命令不再留下成功动作记录。

验证：回归先失败后修复，相关 60 项及完整 99 文件 / 1,178 项前端测试通过，类型/lint/构建通过。规格与证据见 docs/migration/studio-frontend-completion/assistant-snapshot-recovery.md。

未完成：完整模块会话备份/离开保护、异步 AI 动画竞态及正式宿主生命周期。F0–F6 仍未全部完成，Mock 不代表真实后端执行。
