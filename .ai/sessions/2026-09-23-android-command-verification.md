# Android 应用命令语义完成标记

- 日期：2026-09-23；状态：confirmed，本增量；完整目标 active/partial。
- 来源：基线6098b571，同提交的 `docs/qa/android-management/2026-09-23-command-verification.md`。
- 旧 shell 退出码 0 可与 am/pm 文本失败同时存在，不能证明业务成功。v2 marker 在远端先判断语义，启动等待超时编码124并保持unknown；旧零标记也保持unknown。
- 保留回执先持久化后清理marker、requestId绑定、generation及归属保护；无DB/OpenAPI形状变化。
- 本机 shell RED→GREEN 和 Android 聚焦通过，真实新实例先两轮失败暴露Status timeout，再第三轮启动/停止设置应用与人工丢响应核实通过；每轮仅删自建资源，容器/卷0。完整HTTP重启、应用跨会话恢复和真实APK链路未据此关闭。
- 全后端本轮278通过后停在既有proxy/OpenAPI断言；Ruff全量118问题。最终分支门槛仍未通过。
